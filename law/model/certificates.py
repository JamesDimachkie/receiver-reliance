"""Universal unsatisfiability certificates.

Search can only ever report "no witness inside the abstraction".  To upgrade
such a negative into a claim about *every* schema-valid input, the checker must
produce an argument that does not depend on the abstraction at all.

This module holds a small library of those arguments.  Each certificate is
derived mechanically from the sealed schema plus the sealed predicate node, is
sound by a one-line semantic argument recorded alongside it, and is only ever
*offered* — the runner applies certificates exclusively to disjuncts that the
exhaustive search already failed to satisfy, so a missing certificate degrades
the result to PROVEN-BOUNDED rather than producing a false claim.

Adding a certificate can only turn "bounded" into "proven"; it can never turn
an unsatisfiable row into a satisfiable one.
"""

from __future__ import annotations

from typing import Any

from . import predicates as P


def _domain_values(dom, field: str, member: str | None = None) -> list[Any] | None:
    """The complete set of values a field (or object member) may take, or None
    when the schema domain is not finite."""
    spec = dom.specs.get(field)
    if spec is None:
        return None
    if member is not None:
        if spec.kind == "array" and spec.items is not None:
            spec = spec.items.props.get(member)
        elif spec.kind == "object":
            spec = spec.props.get(member)
        else:
            return None
        if spec is None:
            return None
    if spec.kind == "enum" and spec.enum is not None:
        return list(spec.enum) + ([None] if spec.nullable else [])
    if spec.kind == "boolean":
        return [False, True] + ([None] if spec.nullable else [])
    return None


def _field(pointer: str) -> str:
    return pointer[len("/facts/") :].split("/")[0]


def _conjuncts(node: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a conjunction into its atomic and negated-atomic parts."""
    if "all" in node:
        out: list[dict[str, Any]] = []
        for child in node["all"]:
            out.extend(_conjuncts(child))
        return out
    return [node]


def certify_unsat(dom, node: dict[str, Any]) -> dict[str, Any] | None:
    """Return a universal-unsatisfiability certificate for ``node``, or None."""
    parts = _conjuncts(node)
    atoms = [p for p in parts if P.is_atom(p)]
    negated = [p["not"] for p in parts if "not" in p and P.is_atom(p["not"])]

    # C1 - NOT_FUNCTIONAL_BY needs two items that AGREE on `key` and DIFFER on
    # `value`.  If the schema domain of the `value` member holds at most one
    # value, no two items can ever differ on it.
    for atom in atoms:
        if atom.get("op") == "NOT_FUNCTIONAL_BY":
            field = _field(atom["path"])
            values = _domain_values(dom, field, atom["value"])
            if values is not None and len(values) <= 1:
                return {
                    "certificate": "SINGLETON_VALUE_MEMBER",
                    "operator": "NOT_FUNCTIONAL_BY",
                    "pointer": atom["path"],
                    "key_member": atom["key"],
                    "value_member": atom["value"],
                    "value_member_domain": values,
                    "argument": (
                        f"NOT_FUNCTIONAL_BY fires only when two items of {atom['path']} share "
                        f"{atom['key']} and differ on {atom['value']}. The sealed schema fixes "
                        f"{atom['value']} to the {len(values)}-value domain {values!r}, so two "
                        "items can never differ on it. Unsatisfiable for every schema-valid "
                        "input, at any array length."
                    ),
                }

    # C2 - ABSENT on a member the schema forbids from being null.
    for atom in atoms:
        if atom.get("op") == "ABSENT":
            spec = dom.specs.get(_field(atom["path"]))
            if spec is not None and not spec.nullable and spec.kind in ("enum", "boolean", "integer", "string", "array", "object"):
                return {
                    "certificate": "NON_NULLABLE_ABSENT",
                    "operator": "ABSENT",
                    "pointer": atom["path"],
                    "argument": (
                        f"ABSENT is 'value is JSON null'; the sealed schema for {atom['path']} "
                        "admits no null. Unsatisfiable for every schema-valid input."
                    ),
                }

    # C3 - the same pointer required both PRESENT and ABSENT.
    present = {a["path"] for a in atoms if a.get("op") == "PRESENT"}
    absent = {a["path"] for a in atoms if a.get("op") == "ABSENT"}
    present |= {a["path"] for a in negated if a.get("op") == "ABSENT"}
    absent |= {a["path"] for a in negated if a.get("op") == "PRESENT"}
    clash = sorted(present & absent)
    if clash:
        return {
            "certificate": "CONTRADICTORY_PRESENCE",
            "pointer": clash[0],
            "argument": (
                f"The conjunction requires {clash[0]} to be simultaneously null and non-null. "
                "Unsatisfiable for every input."
            ),
        }

    # C4 - EQ against a value outside a finite schema domain.
    for atom in atoms:
        if atom.get("op") == "EQ" and "path" in atom and "value" in atom:
            values = _domain_values(dom, _field(atom["path"]))
            if values is not None and atom["value"] not in values:
                return {
                    "certificate": "IMPOSSIBLE_ENUM_EQ",
                    "pointer": atom["path"],
                    "required_value": atom["value"],
                    "schema_domain": values,
                    "argument": (
                        f"EQ requires {atom['path']} == {atom['value']!r}, which the sealed "
                        f"finite domain {values!r} excludes. Unsatisfiable for every "
                        "schema-valid input."
                    ),
                }

    # C5 - the same pointer pinned to two different values, or EQ and NE of one value.
    pinned: dict[str, set[str]] = {}
    for atom in atoms:
        if atom.get("op") == "EQ" and "path" in atom and "value" in atom:
            pinned.setdefault(atom["path"], set()).add(repr(atom["value"]))
    for path, vals in sorted(pinned.items()):
        if len(vals) > 1:
            return {
                "certificate": "CONTRADICTORY_EQ",
                "pointer": path,
                "required_values": sorted(vals),
                "argument": (
                    f"The conjunction pins {path} to two different values at once. "
                    "Unsatisfiable for every input."
                ),
            }
    for atom in atoms:
        if atom.get("op") == "NE" and "path" in atom and "value" in atom:
            if repr(atom["value"]) in pinned.get(atom["path"], set()):
                return {
                    "certificate": "CONTRADICTORY_EQ_NE",
                    "pointer": atom["path"],
                    "value": atom["value"],
                    "argument": (
                        f"The conjunction requires {atom['path']} both equal and unequal to "
                        f"{atom['value']!r}. Unsatisfiable for every input."
                    ),
                }
    return None
