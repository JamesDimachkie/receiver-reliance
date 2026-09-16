"""Admission of the ``/a2_raw_shared_bundle`` subtree against the accepted schema.

``document_schemas.COMMON.types_and_values`` says the COMMON field rows are
exhaustive "except the complete pinned A2 subtree, whose exact closed
Draft-2020-12 schema is delegated by content hash".  This module is that
delegation, and ``schema_resolution_and_atomic_constructor.a2_resolution`` is the
reading it implements:

* only local RFC6901 ``$ref`` is resolved, siblings apply conjunctively, and a
  cycle or an unresolved reference rejects;
* ``allOf`` is merged;
* ``if`` is evaluated against the preimage and the active ``then`` is included;
* ``oneOf`` requires exactly one preimage-valid branch, and is a kind gate:
  a value outside every branch's kinds is refused by the node's own type
  gate, while a value inside them that satisfies no single branch is a
  value violation;
* every contract normalises to ``allowed_value_kinds``, so a ``const`` or
  ``enum`` node that carries no ``type`` keyword admits exactly the kinds of its
  own literals and a value outside that set is that node's own type gate;
* ``properties`` wins, else typed ``additionalProperties`` applies, and ``false``
  forbids;
* ``items`` resolves every realized array element;
* ``format`` is annotation-only -- the accepted date-time ``pattern`` is the
  assertion;
* a boolean is not an integer, lengths are Unicode scalar counts, and
  ``uniqueItems`` equality is canonical JSON equality.

The schema bytes are embedded (``a2_schema_data``) and verified against
``accepted_schema_sha256`` at import, so admitting a document reaches no
filesystem.
"""

import json
import re

from . import a2_schema_data
from . import faults as fault_mod
from . import vocab
from . import wire

_RAW = wire.b64decode_strict("".join(a2_schema_data.A2_SCHEMA_B64))
if len(_RAW) != a2_schema_data.A2_SCHEMA_BYTE_LENGTH:
    raise ImportError("embedded A2 schema byte length does not match its pin")
if wire.sha256_upper(_RAW) != a2_schema_data.A2_SCHEMA_SHA256:
    raise ImportError("embedded A2 schema SHA-256 does not match its pin")

SCHEMA = json.loads(_RAW.decode("utf-8"))
SCHEMA_BYTES = _RAW

_PATTERN_CACHE = {}


def _compiled(pattern):
    got = _PATTERN_CACHE.get(pattern)
    if got is None:
        got = re.compile(pattern)
        _PATTERN_CACHE[pattern] = got
    return got


def kind_of(value):
    """The ``closed_value_kind_vocabulary`` kind of a realized JSON value."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, str):
        return "STRING"
    if isinstance(value, list):
        return "ARRAY"
    if isinstance(value, dict):
        return "OBJECT"
    raise ValueError("value outside the admitted JSON domain")


_JSON_TYPE_TO_KIND = {
    "null": "NULL",
    "boolean": "BOOLEAN",
    "integer": "INTEGER",
    "string": "STRING",
    "array": "ARRAY",
    "object": "OBJECT",
}

_ALL_KINDS = frozenset(vocab.TYPE_REPRESENTATIVES)


def allowed_value_kinds(flat, value=None, seen=frozenset()):
    """``a2_resolution``: normalise one flattened contract to allowed kinds.

    "Resolve only local RFC6901 $ref and apply siblings conjunctively ... Merge
    allOf" -- so the kind gates a node states are conjunctive.  ``type`` states
    its kinds directly.  A ``const`` node admits exactly the kind of its literal
    and an ``enum`` node exactly the kinds of its members: a value of any other
    kind cannot be that literal under canonical equality, so it is refused by the
    node's own type gate and not by a value comparison.

    ``oneOf`` is a kind gate by the same sentence.  "For oneOf require exactly
    one preimage-valid branch" and "every contract normalises to
    allowed_value_kinds": a value whose kind lies outside *every* branch cannot
    make any branch preimage-valid, so it is refused by this node's own type gate
    and its target is REPLACE_INCOMPATIBLE_TYPE, which
    ``diagnostic_authority.atomic_target_projection`` projects as FIELD_TYPE at
    the value's own pointer.  The admitted set is therefore the union of the
    branches' own allowed kinds, intersected with whatever the node states
    itself.  A value whose kind is inside the union but which satisfies no branch
    (or more than one) is a value violation, not a type violation, and is
    reported as FIELD_VALUE by ``_check`` below -- "all_other_schema_constraints"
    in ``schema_resolution_and_atomic_constructor.diagnostics``.

    A node that states none of the four gates no kind.
    """
    kinds = set(_ALL_KINDS)
    declared = flat.get("type")
    if declared is not None:
        names = [declared] if isinstance(declared, str) else list(declared)
        kinds &= {_JSON_TYPE_TO_KIND[name] for name in names}
    if "const" in flat:
        kinds &= {kind_of(flat["const"])}
    if "enum" in flat:
        kinds &= {kind_of(member) for member in flat["enum"]}
    if "oneOf" in flat:
        union = set()
        for branch in flat["oneOf"]:
            union |= allowed_value_kinds(_flatten(branch, value, seen), value, seen)
        kinds &= union
    return kinds


def first_incompatible_kind(kinds):
    """The first ``type_order`` kind absent from ``kinds``, or None."""
    if kinds is None:
        return None
    for kind in vocab.TYPE_ORDER:
        if kind not in kinds:
            return kind
    return None


def is_item_constructor_postimage(item_kinds, item_value):
    """True when ``item_value`` is what the parent array constructor produces.

    ``schema_operation_rules`` ARRAY_ITEM_INCOMPATIBLE: "when nonempty replace
    item zero with first TYPE_ORDER kind incompatible with its resolved item
    contract; when empty replace array by [null]".  ``first_incompatible(C,X)``
    also excludes a representative canonically equal to the preimage value X, but
    that clause can never bind here: a realised preimage item is contract-valid,
    so its kind is in ``allowed_value_kinds`` while the representative's kind is
    not, and canonical equality implies equal kinds.  The representative is
    therefore a function of the item contract alone.

    ``postimage_collision_kat``: exactly on this postimage do the array-parent
    ARRAY_ITEM_INCOMPATIBLE constructor and the element-child
    REPLACE_INCOMPATIBLE_TYPE constructor produce identical call bytes, so under
    ``postimage_oracle_resolution`` both targets bind the parent-pointer
    FIELD_TYPE oracle.  At any other realised index, and for any other item
    value, the group is a singleton and the item pointer is the diagnostic
    pointer.
    """
    kind = first_incompatible_kind(item_kinds)
    if kind is None:
        return False
    return wire.cj6(item_value) == wire.cj6(vocab.TYPE_REPRESENTATIVES[kind])


class _Cycle(Exception):
    pass


def _deref(node, seen):
    """Resolve a local ``$ref`` chain, applying siblings conjunctively."""
    while isinstance(node, dict) and "$ref" in node:
        ref = node["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#"):
            raise ValueError("only local RFC6901 $ref is admitted")
        if ref in seen:
            raise _Cycle(ref)
        seen = seen | {ref}
        target = _resolve_pointer(SCHEMA, ref[1:])
        siblings = {key: value for key, value in node.items() if key != "$ref"}
        if not siblings:
            node = target
            continue
        merged = dict(target)
        for key, value in siblings.items():
            merged[key] = value
        node = merged
    return node


def _resolve_pointer(root, pointer):
    if pointer == "":
        return root
    if not pointer.startswith("/"):
        raise ValueError("unresolved $ref")
    node = root
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and token in node:
            node = node[token]
        elif isinstance(node, list):
            node = node[int(token)]
        else:
            raise ValueError("unresolved $ref")
    return node


def _flatten(node, value, seen=frozenset()):
    """Merge ``$ref``, ``allOf`` and the active ``if``/``then`` for one occurrence."""
    node = _deref(node, seen)
    if not isinstance(node, dict):
        raise ValueError("schema node is not an object")
    merged = {}
    _absorb(merged, node)
    for sub in node.get("allOf", ()):
        flat = _flatten(sub, value, seen)
        _absorb(merged, flat)
    if "if" in node:
        if _valid(node["if"], value):
            then = node.get("then")
            if then is not None:
                _absorb(merged, _flatten(then, value, seen))
    merged.pop("allOf", None)
    merged.pop("if", None)
    merged.pop("then", None)
    return merged


_MERGE_LISTS = ("required",)


def _absorb(target, node):
    for key, value in node.items():
        if key in ("allOf", "if", "then", "$ref"):
            continue
        if key in _MERGE_LISTS and key in target:
            combined = list(target[key])
            for member in value:
                if member not in combined:
                    combined.append(member)
            target[key] = combined
            continue
        if key == "properties" and key in target:
            combined = dict(target[key])
            combined.update(value)
            target[key] = combined
            continue
        target[key] = value


def _valid(node, value):
    """True when ``value`` satisfies ``node`` with no fault recorded."""
    found = []
    try:
        _check(node, value, "", found, "COMMON", frozenset())
    except (ValueError, _Cycle, RecursionError):
        return False
    return not found


def validate(value, base_pointer, document_id, found):
    """Admit one realized A2 bundle, appending CLOSED_SCHEMA faults to ``found``."""
    _check(SCHEMA, value, base_pointer, found, document_id, frozenset())


def _record(found, code, document_id, pointer):
    found.append(fault_mod.Fault("CLOSED_SCHEMA", code, document_id, pointer, 0))


def _check(node, value, pointer, found, document_id, seen):
    """Admit one occurrence; return the ``allowed_value_kinds`` it resolved to."""
    flat = _flatten(node, value, seen)
    kind = kind_of(value)

    kinds = allowed_value_kinds(flat, value, seen)
    if kind not in kinds:
        # REPLACE_INCOMPATIBLE_TYPE projects FIELD_TYPE
        # (diagnostic_authority.atomic_target_projection).
        _record(found, "FIELD_TYPE", document_id, pointer)
        return kinds

    if "const" in flat and wire.cj6(value) != wire.cj6(flat["const"]):
        _record(found, "FIELD_VALUE", document_id, pointer)
    if "enum" in flat:
        encoded = wire.cj6(value)
        if all(encoded != wire.cj6(member) for member in flat["enum"]):
            _record(found, "FIELD_VALUE", document_id, pointer)

    if "oneOf" in flat:
        matches = [branch for branch in flat["oneOf"] if _valid(branch, value)]
        if len(matches) != 1:
            _record(found, "FIELD_VALUE", document_id, pointer)
        else:
            _check(matches[0], value, pointer, found, document_id, seen)

    if kind == "STRING":
        _check_string(flat, value, pointer, found, document_id)
    elif kind == "INTEGER":
        _check_integer(flat, value, pointer, found, document_id)
    elif kind == "ARRAY":
        _check_array(flat, value, pointer, found, document_id, seen)
    elif kind == "OBJECT":
        _check_object(flat, value, pointer, found, document_id, seen)
    return kinds


def _check_string(flat, value, pointer, found, document_id):
    length = len(value)
    minimum = flat.get("minLength")
    maximum = flat.get("maxLength")
    if minimum is not None and length < minimum:
        _record(found, "FIELD_VALUE", document_id, pointer)
    if maximum is not None and length > maximum:
        _record(found, "FIELD_VALUE", document_id, pointer)
    pattern = flat.get("pattern")
    if pattern is not None and _compiled(pattern).search(value) is None:
        _record(found, "FIELD_VALUE", document_id, pointer)


def _check_integer(flat, value, pointer, found, document_id):
    minimum = flat.get("minimum")
    maximum = flat.get("maximum")
    if minimum is not None and value < minimum:
        _record(found, "FIELD_VALUE", document_id, pointer)
    if maximum is not None and value > maximum:
        _record(found, "FIELD_VALUE", document_id, pointer)


def _check_array(flat, value, pointer, found, document_id, seen):
    minimum = flat.get("minItems")
    maximum = flat.get("maxItems")
    if minimum is not None and len(value) < minimum:
        _record(found, "FIELD_VALUE", document_id, pointer)
    if maximum is not None and len(value) > maximum:
        _record(found, "FIELD_VALUE", document_id, pointer)
    if flat.get("uniqueItems") is True:
        encoded = [wire.cj6(member) for member in value]
        if len(set(encoded)) != len(encoded):
            _record(found, "FIELD_VALUE", document_id, pointer)
    items = flat.get("items")
    if items is None:
        # ARRAY_ITEM_INCOMPATIBLE applies only when the realised item zero "has a
        # resolved member contract", so an itemless array has no parent target.
        return
    collides = False
    for index, member in enumerate(value):
        item_kinds = _check(
            items, member, pointer + "/" + str(index), found, document_id, seen
        )
        if index == 0:
            collides = is_item_constructor_postimage(item_kinds, member)
    if collides:
        # postimage_collision_kat: this postimage is shared by the array-parent
        # ARRAY_ITEM_INCOMPATIBLE target, whose diagnostic pointer is the array
        # pointer -- a proper prefix, so it wins UTF-8 pointer precedence in the
        # postimage_oracle_resolution group minimum.
        _record(found, "FIELD_TYPE", document_id, pointer)


def _check_object(flat, value, pointer, found, document_id, seen):
    properties = flat.get("properties", {})
    required = flat.get("required", ())
    additional = flat.get("additionalProperties", True)
    names = flat.get("propertyNames")

    for name in required:
        if name not in value:
            _record(
                found,
                "MISSING_FIELD",
                document_id,
                pointer + "/" + fault_mod.pointer_escape(name),
            )
    unknown = False
    for name in value:
        if names is not None and not _valid(names, name):
            _record(found, "FIELD_VALUE", document_id, pointer)
        if name in properties:
            continue
        if additional is False:
            unknown = True
    if unknown:
        _record(found, "UNKNOWN_FIELD", document_id, pointer)

    for name, member in value.items():
        child = pointer + "/" + fault_mod.pointer_escape(name)
        if name in properties:
            _check(properties[name], member, child, found, document_id, seen)
        elif isinstance(additional, dict):
            _check(additional, member, child, found, document_id, seen)
