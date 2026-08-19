"""Schema-driven finite abstraction of each operation's ``facts`` domain.

The sealed ``decision_input_schema`` gives every fact field a JSON Schema.  This
module compiles each field into

  * a *finiteness verdict* — whether the schema domain is genuinely finite and
    small enough to enumerate exhaustively (enum, boolean, null, small integer
    range, and finite products of those), and
  * a *candidate list* — a small set of schema-valid values used as the bounded
    abstraction for every other field.

Candidate lists are built from three sources, all mechanical:
  1. the field's own schema (enum members, type, bounds);
  2. the literals that the operation's own predicate rows mention;
  3. a shared per-operation atom pool, so that cross-field relations
     (MEMBER, INTERSECTS, NOT_SUBSET, ...) can be satisfied and falsified.

Nothing here decides whether a predicate holds.  Candidate values are only
*proposals*; truth is always decided by the shipped evaluators in
``model/evaluators.py`` and schema-validity by ``jsonschema`` against the sealed
schema.  A wrong proposal can therefore only cost coverage, never soundness.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import jsonschema

from . import predicates as P

# Shared string atoms.  The first atom is deliberately reused as the default
# for every plain string field so that cross-field coincidences (self loops,
# duplicate keys, set intersections) are inside the abstraction.
ATOMS = ["a0", "a1", "a2"]
# Used only for length-matching array templates, never in the cross product.
LONG_ATOMS = [f"a{i}" for i in range(8)]
HEX64 = [
    hashlib.sha256(seed.encode()).hexdigest().upper() for seed in ("h0", "h1")
]
# Format archetypes for string fields.  Which of these survive is decided by
# the sealed schema (each candidate is validated against the field's own
# schema), so this list narrows coverage rather than asserting anything.
B64_VALID = ["YTA=", "YTE=", "YWIxMg=="]
# Encodings that are *lexically* base64 but not canonical: strict decode then
# re-encode does not reproduce the input (non-zero padding bits), plus shapes
# that fail decoding outright.  Whether any of these is schema-valid for a
# given field is left to the schema.
B64_NONCANONICAL = ["YT==", "YTB=", "YTI="]
B64_INVALID = ["!!!!", "YTA"]
# How many object variants take part in the ordered-pair templates.
OBJECT_POOL_CAP = 8


@dataclass
class FieldSpec:
    name: str
    schema: dict[str, Any]
    kind: str  # enum|string|integer|boolean|array|object|unknown
    nullable: bool
    enum: list[Any] | None
    items: "FieldSpec | None"
    props: dict[str, "FieldSpec"] = field(default_factory=dict)
    finite: bool = False
    finite_size: int | None = None
    candidates: list[Any] = field(default_factory=list)
    exhaustive: bool = False  # candidates == the complete schema domain


def _unwrap(schema: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Collapse ``oneOf: [X, {"type": "null"}]`` into (X, nullable)."""
    if "oneOf" in schema and len(schema) == 1:
        branches = schema["oneOf"]
        nulls = [b for b in branches if b.get("type") == "null"]
        others = [b for b in branches if b.get("type") != "null"]
        if nulls and len(others) == 1:
            inner, inner_nullable = _unwrap(others[0])
            return inner, True or inner_nullable
    return schema, False


def build_spec(name: str, schema: dict[str, Any]) -> FieldSpec:
    inner, nullable = _unwrap(schema)
    enum = inner.get("enum")
    if "const" in inner:
        enum = [inner["const"]]
    kind = "unknown"
    items = None
    props: dict[str, FieldSpec] = {}
    if enum is not None:
        kind = "enum"
    else:
        t = inner.get("type")
        if t == "array":
            kind = "array"
            items = build_spec(name + "[]", inner.get("items", {}))
        elif t == "object":
            kind = "object"
            props = {k: build_spec(f"{name}.{k}", v) for k, v in inner.get("properties", {}).items()}
        elif t in ("string", "integer", "number", "boolean"):
            kind = t
    spec = FieldSpec(
        name=name, schema=schema, kind=kind, nullable=nullable, enum=enum, items=items, props=props
    )
    _finiteness(spec, inner)
    return spec


FINITE_INT_SPAN = 8  # a schema integer range is only called finite if this small


def _finiteness(spec: FieldSpec, inner: dict[str, Any]) -> None:
    base: int | None
    if spec.kind == "enum":
        base = len(spec.enum or [])
    elif spec.kind == "boolean":
        base = 2
    elif spec.kind == "integer":
        lo, hi = inner.get("minimum"), inner.get("maximum")
        base = (hi - lo + 1) if (lo is not None and hi is not None and hi - lo + 1 <= FINITE_INT_SPAN) else None
    elif spec.kind == "object":
        base = 1
        for p in spec.props.values():
            if not p.finite or p.finite_size is None:
                base = None
                break
            base *= p.finite_size
    else:
        base = None  # unbounded string, or array (maxItems is 256 in this contract)
    if base is None:
        spec.finite, spec.finite_size = False, None
    else:
        spec.finite = True
        spec.finite_size = base + (1 if spec.nullable else 0)


class OperationDomain:
    """The finite abstraction of one operation's ``facts`` object."""

    def __init__(self, operation, law) -> None:
        self.op = operation
        self.facts_schema = operation.facts_schema
        self.specs: dict[str, FieldSpec] = {
            k: build_spec(k, v) for k, v in self.facts_schema["properties"].items()
        }
        self.required = list(self.facts_schema.get("required", []))
        rows = [operation.class_predicates[c] for c in law.defect_precedence]
        lits: list[Any] = []
        for r in rows:
            lits.extend(P.literals(r))
        self.string_literals = sorted({x for x in lits if isinstance(x, str)})
        self.int_literals = sorted({x for x in lits if isinstance(x, int) and not isinstance(x, bool)})
        # Literal *lists* attached to a specific field (NOT_CONTAINS_ALL,
        # NOT_SUBSET_VALUES, MEMBER_VALUE ...) become array templates.
        self.value_lists: dict[str, list[list[Any]]] = {}
        self.b64_paths: set[str] = set()
        self.digest_pairs: list[tuple[str, str]] = []
        for r in rows:
            for atom in P.atoms(r):
                if "values" in atom:
                    for ptr in P.node_pointers(atom):
                        self.value_lists.setdefault(_fieldof(ptr), []).append(list(atom["values"]))
                if atom["op"] == "ANY_PRESENT_STRICT_BASE64_DECODE_FAILURE":
                    self.b64_paths.update(_fieldof(p) for p in atom.get("paths", []))
                if atom["op"] == "BASE64_SHA256_NE":
                    self.b64_paths.add(_fieldof(atom["base64_path"]))
                    self.digest_pairs.append(
                        (_fieldof(atom["base64_path"]), _fieldof(atom["digest_path"]))
                    )
        # Array lengths that some row's literal list makes significant, so that
        # COUNT_NE_PATH and ordering rows can be driven both ways.
        self.length_targets: set[int] = {1, 2, 3}
        for lists in self.value_lists.values():
            for values in lists:
                self.length_targets.add(len(values))
        self.validator = jsonschema.Draft202012Validator(operation.input_schema)
        for name, spec in self.specs.items():
            self._fill(name, spec)
        self._couple_digests()
        self.default = {name: self.specs[name].candidates[0] for name in self.specs}

    def _couple_digests(self) -> None:
        """Derived-value coupling for BASE64_SHA256_NE.

        A digest field can only be *agreed* with its base64 field by a value
        that no independent enumeration will ever guess.  For each sealed
        (base64_path, digest_path) pair, the true digest of every base64
        candidate is added to the digest field's candidate list.  This only
        widens coverage; truth is still decided by the shipped evaluators.
        """
        import base64 as _b64

        for b64_field, digest_field in self.digest_pairs:
            src, dst = self.specs.get(b64_field), self.specs.get(digest_field)
            if src is None or dst is None:
                continue
            validator = jsonschema.Draft202012Validator(dst.schema)
            for value in list(src.candidates):
                if not isinstance(value, str):
                    continue
                try:
                    raw = _b64.b64decode(value, validate=True)
                    if _b64.b64encode(raw).decode("ascii") != value:
                        continue
                except Exception:
                    continue
                digest = hashlib.sha256(raw).hexdigest().upper()
                if digest not in dst.candidates and validator.is_valid(digest):
                    dst.candidates.append(digest)
            dst.exhaustive = bool(
                dst.finite and dst.finite_size is not None and len(dst.candidates) == dst.finite_size
            )

    # -- candidate construction ------------------------------------------
    def _scalar_pool(self, name: str, spec: FieldSpec) -> list[Any]:
        if spec.kind == "enum":
            return list(spec.enum or [])
        if spec.kind == "boolean":
            return [False, True]
        if spec.kind == "integer":
            pool = [0, 1, 2] + [v for v in self.int_literals] + [v + 1 for v in self.int_literals] + [-1]
            seen, out = set(), []
            for v in pool:
                if v not in seen:
                    seen.add(v)
                    out.append(v)
            return out
        if spec.kind == "string":
            pool: list[str] = []
            if _leaf(name) in self.b64_paths:
                pool += B64_VALID + B64_NONCANONICAL + B64_INVALID
            pool += ATOMS + HEX64 + self.string_literals
            seen, out = set(), []
            for v in pool:
                if v not in seen:
                    seen.add(v)
                    out.append(v)
            return out
        return [None]

    def _object_pool(self, name: str, spec: FieldSpec) -> list[dict[str, Any]]:
        """Base object plus one single-property variant per property.

        This is exactly the shape the relational operators need: two items that
        agree on every member but one (NOT_FUNCTIONAL_BY, HAS_SELF_LOOP,
        NOT_MEMBER_BY_KEY, ANY_NONPOSITIVE_SPAN, cycle detection).
        """
        per: dict[str, list[Any]] = {}
        for pname, pspec in spec.props.items():
            vals = self._valid_values(f"{name}.{pname}", pspec, pspec.schema)
            per[pname] = vals[:3] if vals else [None]
        base = {k: v[0] for k, v in per.items()}
        pool = [base]
        for pname, vals in sorted(per.items()):
            for alt in vals[1:2]:
                obj = dict(base)
                obj[pname] = alt
                pool.append(obj)
        return pool[:OBJECT_POOL_CAP]

    def _valid_values(self, name: str, spec: FieldSpec, schema: dict[str, Any]) -> list[Any]:
        raw: list[Any]
        if spec.kind == "array":
            raw = self._array_pool(name, spec)
        elif spec.kind == "object":
            raw = self._object_pool(name, spec)
        else:
            raw = self._scalar_pool(name, spec)
        if spec.nullable:
            raw = [None] + raw
        validator = jsonschema.Draft202012Validator(schema)
        out = [v for v in raw if validator.is_valid(v)]
        return out or ([None] if spec.nullable else raw[:1])

    def _array_pool(self, name: str, spec: FieldSpec) -> list[list[Any]]:
        assert spec.items is not None
        item_schema = spec.items.schema
        item_vals = self._valid_values(name + "[]", spec.items, item_schema)
        if not item_vals:
            return [[]]
        item_ok = jsonschema.Draft202012Validator(item_schema).is_valid
        i0 = item_vals[0]
        i1 = item_vals[1] if len(item_vals) > 1 else i0
        i2 = item_vals[2] if len(item_vals) > 2 else i1
        pool: list[list[Any]] = [[], [i0], [i0, i0], [i0, i1], [i1], [i1, i0], [i0, i1, i2]]

        if spec.items.kind == "object":
            # Every ordered pair over the single-member-variant pool, so
            # "two items agreeing on all members but one" is inside the
            # abstraction (NOT_FUNCTIONAL_BY, HAS_SELF_LOOP, cycles, ...).
            for a in item_vals[:OBJECT_POOL_CAP]:
                for b in item_vals[:OBJECT_POOL_CAP]:
                    pool.append([a, b])
        else:
            # Literal-bearing templates: a predicate that tests membership of a
            # literal can only be falsified if the literal can appear.
            lits = [v for v in self.string_literals if item_ok(v)]
            for lit in lits:
                pool.append([lit])
                pool.append([lit, i0])
            if lits:
                pool.append(list(lits))
                if len(lits) > 1:
                    pool.append(list(lits[1:]))
            # Length-matching templates, so count-linked and ordering-linked
            # rows (COUNT_NE_PATH against a fixed literal list,
            # NOT_STRICTLY_INCREASING) can be satisfied AND falsified.
            for k in sorted(self.length_targets):
                if spec.items.kind == "integer":
                    inc = list(range(k))
                    if all(item_ok(v) for v in inc):
                        pool.append(inc)
                        pool.append(inc[::-1])
                else:
                    seq = [v for v in LONG_ATOMS[:k]]
                    if len(seq) == k and all(item_ok(v) for v in seq):
                        pool.append(seq)

        for values in self.value_lists.get(_leaf(name), []):
            pool.append(list(values))
            if len(values) > 1:
                pool.append(list(values[1:]))
            pool.append(list(values) + [i0])

        deduped: list[list[Any]] = []
        seen: set[str] = set()
        for v in pool:
            key = repr(v)
            if key not in seen:
                seen.add(key)
                deduped.append(v)
        return deduped

    def _fill(self, name: str, spec: FieldSpec) -> None:
        spec.candidates = self._valid_values(name, spec, spec.schema)
        # A field is exhaustively covered when its candidate list IS the whole
        # schema domain.  Only then can a negative search result be a proof.
        spec.exhaustive = bool(
            spec.finite and spec.finite_size is not None and len(spec.candidates) == spec.finite_size
        )

    # -- document assembly -------------------------------------------------
    def document(self, facts: dict[str, Any]) -> dict[str, Any]:
        full = dict(self.default)
        full.update(facts)
        return {
            "format_version": self.op.input_schema["properties"]["format_version"]["const"],
            "operation_handle": self.op.operation_handle,
            "obligation_id": self.op.obligation_id,
            "facts": full,
        }

    def is_schema_valid(self, document: dict[str, Any]) -> bool:
        return self.validator.is_valid(document)

    def summary(self) -> dict[str, Any]:
        return {
            "obligation_id": self.op.obligation_id,
            "fields": len(self.specs),
            "finite_fields": sum(1 for s in self.specs.values() if s.finite),
            "exhaustive_fields": sum(1 for s in self.specs.values() if s.exhaustive),
            "candidate_counts": {k: len(v.candidates) for k, v in sorted(self.specs.items())},
        }


def _fieldof(pointer: str) -> str:
    return pointer[len("/facts/") :].split("/")[0] if pointer.startswith("/facts/") else pointer


def _leaf(name: str) -> str:
    return name.split(".")[0].split("[")[0]
