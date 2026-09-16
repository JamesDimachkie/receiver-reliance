"""Shared canonical admission and closed-schema validation."""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any

from ._a2_data import A2_SCHEMA
from ._field_rows import COMMON_ROWS, STATE_R_ROWS, STATE_S_ROWS, STATE_U_ROWS
from .result import presemantic_bytes
from .wire import Fault, child_pointer, cj6, jcs, parse_document, select_fault

COMMON_LIMIT = 1_048_576
STATE_LIMIT = 262_144
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
SHA256_UPPER = re.compile(r"[0-9A-F]{64}\Z")
PARENT_DIGEST_IDENTIFIER = re.compile(r"PARENT_[0-9A-F]{64}\Z")

COMMON_FIELDS = {
    "a2_raw_shared_bundle",
    "comparison_facts",
    "delivered_artifact_envelope",
    "format",
    "guard_observation_facts",
    "remediation",
    "requested_delivered_transfer",
    "source_lineage_observation",
    "task_id",
    "task_instruction_constraints",
}

COMPARISON_FIELDS = {
    "carrier_fence",
    "consumed_representation_sha256",
    "current_fence",
    "expected_action_class",
    "expected_authority",
    "expected_carrier",
    "expected_direct_parents",
    "expected_generation",
    "expected_owner",
    "expected_principal",
    "expected_purpose",
    "expected_receiver_capability",
    "expected_representation_sha256",
    "expected_route",
    "expected_scope",
    "expected_slot",
    "observed_action_class",
    "observed_authority",
    "observed_carrier",
    "observed_direct_parents",
    "observed_generation",
    "observed_owner",
    "observed_principal",
    "observed_purpose",
    "observed_receiver_capability",
    "observed_route",
    "observed_scope",
    "observed_slot",
    "origin_finalized",
    "revocation_active",
    "use_time_ns",
    "valid_from_ns",
    "valid_until_ns",
}

NESTED_FIELDS = {
    "/comparison_facts": COMPARISON_FIELDS,
    "/delivered_artifact_envelope": {
        "artifact_id",
        "content_b64",
        "format",
        "media_type",
        "revision",
    },
    "/guard_observation_facts": {
        "consumption_state",
        "effect_receipt_count",
        "effect_sha256",
        "execution_receipt_effect_sha256",
        "grant_expires_at",
        "grant_not_before",
        "invocation_nonce",
        "invocation_time",
        "prior_invocation_nonces",
        "revocation_checked_at",
        "revoked_at",
    },
    "/remediation": {"attempt_ordinal", "refetch_budget"},
    "/requested_delivered_transfer": {
        "declared_sha256",
        "delivered_artifact_id",
        "delivered_revision",
        "requested_artifact_id",
        "requested_revision",
    },
    "/source_lineage_observation": {
        "format",
        "source_artifact_id",
        "source_revision",
        "source_sha256",
    },
    "/task_instruction_constraints": {"constraints", "instruction"},
}


def _kind(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) is int:
        return "integer"
    if type(value) is str:
        return "string"
    if type(value) is list:
        return "array"
    if type(value) is dict:
        return "object"
    return "invalid"


# schema_resolution_and_atomic_constructor.type_order and replacement_descriptor_authority
# .evaluation_primitives.type_representatives: the array-parent ARRAY_ITEM_INCOMPATIBLE constructor
# writes at item zero the representative of the FIRST kind in type_order absent from the item's
# allowed kinds (first_incompatible). Only that exact value shares the parent constructor's
# postimage (postimage_collision_kat); any other wrong-kind value at index 0 keeps its own pointer.
_TYPE_ORDER = ("null", "boolean", "integer", "string", "array", "object")
_TYPE_REPRESENTATIVES: dict[str, Any] = {"null": None, "boolean": False, "integer": 0, "string": "x", "array": [], "object": {}}


def _allowed_kinds(schema: dict[str, Any]) -> set[str]:
    expected = schema.get("type")
    if expected is not None:
        return {expected} if type(expected) is str else set(expected)
    allowed: set[str] = set()
    if "const" in schema:
        allowed.add(_kind(schema["const"]))
    if type(schema.get("enum")) is list:
        allowed.update(_kind(member) for member in schema["enum"])
    return allowed


def _collides_with_parent_constructor(value: Any, allowed: set[str]) -> bool:
    for kind in _TYPE_ORDER:
        if kind not in allowed:
            return cj6(value) == cj6(_TYPE_REPRESENTATIVES[kind])
    return False


def _resolve_ref(schema: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if "$ref" not in schema:
        return schema, []
    ref = schema["$ref"]
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return {}, []
    target: Any = A2_SCHEMA
    for raw in ref[2:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if type(target) is not dict or token not in target:
            return {}, []
        target = target[token]
    siblings = {key: value for key, value in schema.items() if key != "$ref"}
    return target, [siblings] if siblings else []


def _matches(value: Any, schema: dict[str, Any]) -> bool:
    return not _schema_faults(value, schema, "", "COMMON", boolean_only=True)


def _schema_faults(
    value: Any,
    schema: dict[str, Any],
    pointer: str,
    document: str,
    *,
    boolean_only: bool = False,
) -> list[Fault]:
    resolved, siblings = _resolve_ref(schema)
    if not resolved and "$ref" in schema:
        return [Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document)]
    faults: list[Fault] = []
    schema = resolved

    for part in schema.get("allOf", []):
        if type(part) is dict:
            faults.extend(_schema_faults(value, part, pointer, document, boolean_only=boolean_only))
    for sibling in siblings:
        faults.extend(_schema_faults(value, sibling, pointer, document, boolean_only=boolean_only))

    if "if" in schema and type(schema["if"]) is dict and _matches(value, schema["if"]):
        then = schema.get("then")
        if type(then) is dict:
            faults.extend(_schema_faults(value, then, pointer, document, boolean_only=boolean_only))

    one_of = schema.get("oneOf")
    if type(one_of) is list:
        branches = [part for part in one_of if type(part) is dict]
        by_kind = [part for part in branches if _kind(value) in _allowed_kinds(_resolve_ref(part)[0] if "$ref" in part else part)]
        if len(by_kind) == 1:
            faults.extend(_schema_faults(value, by_kind[0], pointer, document, boolean_only=boolean_only))
        else:
            matching = [part for part in branches if _matches(value, part)]
            if len(matching) != 1:
                faults.append(
                    Fault("CLOSED_SCHEMA", "FIELD_TYPE", pointer, document=document, own_type_gate=True)
                )
                return faults
            faults.extend(_schema_faults(value, matching[0], pointer, document, boolean_only=boolean_only))

    # The node's admissible value kinds: the explicit type keyword when present, otherwise the
    # kinds of its const / enum literals (schema_resolution_and_atomic_constructor.a2_resolution
    # normalizes every contract to allowed_value_kinds; a const or enum node admits exactly the
    # kinds of its literals).  A realized value outside that set is the node's own type gate and
    # projects CLOSED_SCHEMA/FIELD_TYPE (REPLACE_INCOMPATIBLE_TYPE), never FIELD_VALUE.
    expected = schema.get("type")
    if expected is not None:
        allowed = {expected} if type(expected) is str else set(expected)
    else:
        allowed = set()
        if "const" in schema:
            allowed.add(_kind(schema["const"]))
        if type(schema.get("enum")) is list:
            allowed.update(_kind(member) for member in schema["enum"])
    if allowed and _kind(value) not in allowed:
        faults.append(
            Fault("CLOSED_SCHEMA", "FIELD_TYPE", pointer, document=document, own_type_gate=True)
        )
        return faults

    if "const" in schema and cj6(value) != cj6(schema["const"]):
        faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
    if "enum" in schema and all(cj6(value) != cj6(member) for member in schema["enum"]):
        faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))

    if type(value) is int and type(value) is not bool:
        if "minimum" in schema and value < schema["minimum"]:
            faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
        if "maximum" in schema and value > schema["maximum"]:
            faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
    elif type(value) is str:
        if "minLength" in schema and len(value) < schema["minLength"]:
            faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
        if "pattern" in schema:
            try:
                matched = re.search(schema["pattern"], value) is not None
            except re.error:
                matched = False
            if not matched:
                faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
    elif type(value) is list:
        if "minItems" in schema and len(value) < schema["minItems"]:
            faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
        if schema.get("uniqueItems") is True:
            encoded = [cj6(member) for member in value]
            if len(set(encoded)) != len(encoded):
                faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
        item_schema = schema.get("items")
        if type(item_schema) is dict:
            for index, member in enumerate(value):
                item_pointer = child_pointer(pointer, index)
                item_faults = _schema_faults(
                    member,
                    item_schema,
                    item_pointer,
                    document,
                    boolean_only=boolean_only,
                )
                # postimage_collision_kat: the array-parent ARRAY_ITEM_INCOMPATIBLE constructor
                # ("when nonempty replace item zero") and the element-child
                # REPLACE_INCOMPATIBLE_TYPE constructor AT ITEM ZERO produce identical bytes, and
                # postimage_oracle_resolution binds both to the parent-pointer FIELD_TYPE output
                # (a proper prefix wins).  At index >= 1 the group is a singleton and the item's own
                # pointer is the oracle (atomic_target_projection: the pointer is the target pointer
                # except for DELETE_ARRAY_ITEM).  So only the index-0 own type gate is re-pointed;
                # the marker is cleared so an outer array never re-points a nested one.
                for item_fault in item_faults:
                    if (
                        index == 0
                        and item_fault.own_type_gate
                        and item_fault.pointer == item_pointer
                        and _collides_with_parent_constructor(member, _allowed_kinds(_resolve_ref(item_schema)[0] if "$ref" in item_schema else item_schema))
                    ):
                        item_fault.pointer = pointer
                        item_fault.own_type_gate = False
                faults.extend(item_faults)
    elif type(value) is dict:
        required = schema.get("required", [])
        for name in required:
            if name not in value:
                faults.append(
                    Fault("CLOSED_SCHEMA", "MISSING_FIELD", child_pointer(pointer, name), document=document)
                )
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for name in sorted(value, key=lambda item: item.encode("utf-8")):
            member_pointer = child_pointer(pointer, name)
            if name in properties:
                faults.extend(
                    _schema_faults(
                        value[name],
                        properties[name],
                        member_pointer,
                        document,
                        boolean_only=boolean_only,
                    )
                )
            elif additional is False:
                # INSERT_UNKNOWN_MEMBER binds the containing object's pointer, not the inserted
                # member's (diagnostic_authority.atomic_target_projection: the diagnostic pointer
                # is parent(pointer) only for DELETE_ARRAY_ITEM and is the target pointer
                # otherwise, and the insertion target is the object being extended).
                faults.append(Fault("CLOSED_SCHEMA", "UNKNOWN_FIELD", pointer, document=document))
            elif type(additional) is dict:
                faults.extend(
                    _schema_faults(
                        value[name],
                        additional,
                        member_pointer,
                        document,
                        boolean_only=boolean_only,
                    )
                )
        property_names = schema.get("propertyNames")
        if type(property_names) is dict and "pattern" in property_names:
            try:
                bad_name = next(
                    (name for name in sorted(value) if re.search(property_names["pattern"], name) is None),
                    None,
                )
            except re.error:
                bad_name = next(iter(value), "")
            if bad_name is not None:
                faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
    return faults


KIND_SETS = {
    "OBJECT": {"object"},
    "STRING": {"string"},
    "INTEGER": {"integer"},
    "BOOLEAN": {"boolean"},
    "ARRAY": {"array"},
    "NULL": {"null"},
    "INTEGER_OR_NULL": {"integer", "null"},
}
COMMON_INDEX = {row["pointer"]: row for row in COMMON_ROWS}
STATE_INDEX = {
    "STATE_R": {row["pointer"]: row for row in STATE_R_ROWS},
    "STATE_S": {row["pointer"]: row for row in STATE_S_ROWS},
    "STATE_U": {row["pointer"]: row for row in STATE_U_ROWS},
}


def _identifier(value: Any) -> bool:
    return type(value) is str and IDENTIFIER.fullmatch(value) is not None


def _sha(value: Any) -> bool:
    return type(value) is str and SHA256_UPPER.fullmatch(value) is not None


def _canonical_base64(value: str, minimum: int, maximum: int) -> bool:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError, UnicodeError):
        return False
    return base64.b64encode(decoded).decode("ascii") == value and minimum <= len(decoded) <= maximum


def _row_faults(value: Any, pointer: str, row: dict[str, Any], index: dict[str, dict[str, Any]], document: str) -> list[Fault]:
    """document_schemas.*.field_schema_rows applied under diagnostic_authority.atomic_target_projection:
    a realized kind outside the row's value_kind is FIELD_TYPE at the pointer (the value's own type
    gate); every other constraint of the row is FIELD_VALUE at the pointer; an exact-field object
    reports UNKNOWN_FIELD at the object pointer and MISSING_FIELD at the member pointer; array
    members are validated at their own pointers by the row keyed <array>/* with the same index-0
    collision rule as the A2 walker.  Class ids: IDENTIFIER, SHA256_UPPER, CANONICAL_BASE64,
    SIGNED_NONNEGATIVE_INT64 / REVISION / EXACT_RANGE_0_1 (min/max), ORDERED_IDENTIFIER_ARRAY,
    SET_IDENTIFIER_ARRAY (unique, utf8_sorted), ORDERED_STRING_ARRAY (member byte lengths)."""
    faults: list[Fault] = []
    kind = _kind(value)
    if kind not in KIND_SETS[row["value_kind"]]:
        faults.append(Fault("CLOSED_SCHEMA", "FIELD_TYPE", pointer, document=document, own_type_gate=True))
        return faults
    if "const" in row and cj6(value) != cj6(row["const"]):
        faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
    if "enum" in row and all(cj6(value) != cj6(member) for member in row["enum"]):
        faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
    class_id = row.get("class_id")
    if kind == "string":
        bad = False
        if class_id == "IDENTIFIER" and not _identifier(value):
            bad = True
        if class_id == "SHA256_UPPER" and not _sha(value):
            bad = True
        if class_id == "PARENT_DIGEST_IDENTIFIER" and PARENT_DIGEST_IDENTIFIER.fullmatch(value) is None:
            bad = True
        if class_id == "CANONICAL_BASE64" and not _canonical_base64(value, int(row.get("decoded_minimum", 0)), int(row.get("decoded_maximum", 1 << 62))):
            bad = True
        if "utf8_minimum" in row or "utf8_maximum" in row:
            length = len(value.encode("utf-8"))
            if length < int(row.get("utf8_minimum", 0)) or length > int(row.get("utf8_maximum", 1 << 62)):
                bad = True
        if bad:
            faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
    elif kind == "integer":
        if ("minimum" in row and value < row["minimum"]) or ("maximum" in row and value > row["maximum"]):
            faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
    elif kind == "array":
        count = len(value)
        bad = ("minimum" in row and count < row["minimum"]) or ("maximum" in row and count > row["maximum"])
        if row.get("unique") is True:
            encoded = [cj6(member) for member in value]
            if len(set(encoded)) != len(encoded):
                bad = True
        if row.get("utf8_sorted") is True and all(type(member) is str for member in value):
            if value != sorted(value, key=lambda member: member.encode("utf-8")):
                bad = True
        if bad:
            faults.append(Fault("CLOSED_SCHEMA", "FIELD_VALUE", pointer, document=document))
        item_row = index.get(pointer + "/*")
        if item_row is not None:
            for position, member in enumerate(value):
                item_pointer = child_pointer(pointer, position)
                item_faults = _row_faults(member, item_pointer, item_row, index, document)
                for item_fault in item_faults:
                    if (
                        position == 0
                        and item_fault.own_type_gate
                        and item_fault.pointer == item_pointer
                        and _collides_with_parent_constructor(member, KIND_SETS[item_row["value_kind"]])
                    ):
                        item_fault.pointer = pointer
                        item_fault.own_type_gate = False
                faults.extend(item_faults)
    elif kind == "object":
        if pointer == "/a2_raw_shared_bundle":
            faults.extend(_schema_faults(value, A2_SCHEMA, pointer, document))
            return faults
        fields = row.get("fields_exact")
        if fields is not None:
            field_set = set(fields)
            for name in sorted(set(value) - field_set, key=lambda item: item.encode("utf-8")):
                faults.append(Fault("CLOSED_SCHEMA", "UNKNOWN_FIELD", pointer, document=document))
            for name in sorted(field_set - set(value), key=lambda item: item.encode("utf-8")):
                faults.append(Fault("CLOSED_SCHEMA", "MISSING_FIELD", child_pointer(pointer, name), document=document))
            for name in sorted(value, key=lambda item: item.encode("utf-8")):
                if name not in field_set:
                    continue
                member_pointer = child_pointer(pointer, name)
                member_row = index.get(member_pointer)
                if member_row is not None:
                    faults.extend(_row_faults(value[name], member_pointer, member_row, index, document))
    return faults


def _entries(vocabulary: dict[str, Any], name: str) -> set[str]:
    # Only string identifiers form the membership set: an entry whose `id` has another kind was
    # already faulted by the schema stage (FIELD_TYPE at that entry, a lower code than
    # CROSS_FIELD), and an unhashable kind must never raise out of the cross-field stage
    # (confirmation review M-2).
    rows = vocabulary.get(name)
    if type(rows) is not list:
        return set()
    return {row["id"] for row in rows if type(row) is dict and type(row.get("id")) is str}


def validate_common(value: Any) -> list[Fault]:
    faults = _row_faults(value, "", COMMON_INDEX[""], COMMON_INDEX, "COMMON")
    if type(value) is not dict:
        return faults

    # Cross-field laws are evaluated only after closed member contracts; every operand is
    # type-guarded so a member the schema stage already faulted can never raise here (the
    # INTERNAL result is reserved for genuine internal faults, never for a registered postimage).
    artifact = value.get("delivered_artifact_envelope")
    transfer = value.get("requested_delivered_transfer")
    comparison = value.get("comparison_facts")
    if type(artifact) is dict and type(transfer) is dict:
        if artifact.get("artifact_id") != transfer.get("delivered_artifact_id"):
            faults.append(Fault("CLOSED_SCHEMA", "CROSS_FIELD", "/requested_delivered_transfer/delivered_artifact_id"))
        if artifact.get("revision") != transfer.get("delivered_revision"):
            faults.append(Fault("CLOSED_SCHEMA", "CROSS_FIELD", "/requested_delivered_transfer/delivered_revision"))
        if artifact.get("media_type") == "application/json" and type(artifact.get("content_b64")) is str:
            try:
                decoded = base64.b64decode(artifact["content_b64"], validate=True)
                parsed, wire_fault = parse_document(decoded, "COMMON", 32768)
                json_ok = wire_fault is None and jcs(parsed) == decoded
            except (binascii.Error, ValueError, UnicodeError):
                json_ok = False
            if not json_ok:
                faults.append(Fault("CLOSED_SCHEMA", "CROSS_FIELD", "/delivered_artifact_envelope/content_b64"))
    if type(comparison) is dict:
        if all(name in comparison for name in ("valid_from_ns", "valid_until_ns")) and type(comparison["valid_from_ns"]) is int and type(comparison["valid_until_ns"]) is int and comparison["valid_from_ns"] > comparison["valid_until_ns"]:
            faults.append(Fault("CLOSED_SCHEMA", "CROSS_FIELD", "/comparison_facts/valid_from_ns"))
        a2 = value.get("a2_raw_shared_bundle")
        if type(a2) is dict:
            uses = a2.get("use_records")
            vocabulary = a2.get("domain_vocabulary")
            if type(uses) is list and len(uses) == 1 and type(uses[0]) is dict and type(vocabulary) is dict:
                use = uses[0]
                purposes = _entries(vocabulary, "purpose_entries")
                scopes = _entries(vocabulary, "scope_entries")
                if comparison.get("expected_receiver_capability") != use.get("receiver_capability_id"):
                    faults.append(Fault("CLOSED_SCHEMA", "CROSS_FIELD", "/comparison_facts/expected_receiver_capability"))
                if type(comparison.get("expected_purpose")) is not str or comparison.get("expected_purpose") not in purposes or comparison.get("expected_purpose") != use.get("purpose_id"):
                    faults.append(Fault("CLOSED_SCHEMA", "CROSS_FIELD", "/comparison_facts/expected_purpose"))
                expected_scope = comparison.get("expected_scope")
                if type(expected_scope) is not list or any(type(item) is not str or item not in scopes for item in expected_scope) or expected_scope != [use.get("scope_id")]:
                    faults.append(Fault("CLOSED_SCHEMA", "CROSS_FIELD", "/comparison_facts/expected_scope"))
    return faults


def validate_state(value: Any, state_document: str) -> list[Fault]:
    index = STATE_INDEX.get(state_document, STATE_INDEX["STATE_U"])
    return _row_faults(value, "", index[""], index, "STATE")


def admit_pair(
    entrypoint: str,
    module: str,
    state_document: str,
    common_arg: object,
    state_arg: object,
) -> tuple[Any | None, Any | None, bytes | None, bool]:
    if type(common_arg) is not bytes or type(state_arg) is not bytes:
        fault = Fault("PYTHON_TYPE", "ARGUMENT_TYPE")
        return None, None, presemantic_bytes(entrypoint, module, common_arg, state_arg, fault, False, False), False

    # diagnostic_authority.fault_selection: collect every fault whose prerequisites were reached
    # across BOTH documents, then take the minimum of
    # [stage_index, code_index, document_index, pointer_utf8, occurrence].  A parser-stage fault
    # prevents only the later stages of its OWN document, so COMMON never gates STATE:
    # document_index is the third tuple element and cannot outrank stage or code.
    faults: list[Fault] = []
    common, common_parse_fault = parse_document(common_arg, "COMMON", COMMON_LIMIT)
    if common_parse_fault is not None:
        faults.append(common_parse_fault)
    else:
        faults.extend(validate_common(common))
    state, state_parse_fault = parse_document(state_arg, "STATE", STATE_LIMIT)
    if state_parse_fault is not None:
        faults.append(state_parse_fault)
    else:
        faults.extend(validate_state(state, state_document))

    # diagnostic_authority.remediation: REFETCH only when COMMON fully passed CLOSED_SCHEMA.
    common_admitted = common_parse_fault is None and not any(
        fault.document == "COMMON" for fault in faults
    )
    refetch_enabled = common_admitted and common["remediation"] == {
        "attempt_ordinal": 0,
        "refetch_budget": 1,
    }

    selected = select_fault(faults)
    if selected is not None:
        return (
            common,
            None,
            presemantic_bytes(
                entrypoint,
                module,
                common_arg,
                state_arg,
                selected,
                common_admitted,
                refetch_enabled,
            ),
            refetch_enabled,
        )
    return common, state, None, refetch_enabled
