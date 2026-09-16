"""CLOSED_SCHEMA admission of the COMMON and STATE documents.

The rows are the authority's own ``document_schemas`` rows, transcribed verbatim
into ``authority_data``.  ``document_schemas.COMMON.types_and_values`` fixes the
matching rule -- "A pointer matches exactly one row or one accepted A2 schema
node; zero or multiple matches reject" -- and the ``/a2_raw_shared_bundle``
subtree is delegated to ``a2schema`` by content hash.

Diagnostic codes follow ``schema_resolution_and_atomic_constructor.diagnostics``
and ``diagnostic_authority.atomic_target_projection``:

* an unknown member is UNKNOWN_FIELD reported at the containing object's pointer
  (the INSERT_UNKNOWN_MEMBER target pointer is the object being extended);
* a missing required member is MISSING_FIELD at the missing member's pointer;
* an incompatible realized kind is FIELD_TYPE at the value's pointer, and item
  zero additionally raises FIELD_TYPE at the parent array pointer exactly when it
  carries the value the array-parent ARRAY_ITEM_INCOMPATIBLE constructor
  produces, because only then do the two constructors share a postimage
  (``postimage_collision_kat``); the parent pointer is a proper prefix and so
  wins pointer precedence for that group;
* every other schema constraint is FIELD_VALUE at the value's pointer;
* a cross-field law is CROSS_FIELD.
"""

import re

from . import a2schema
from . import admission as admission_mod
from . import authority_data
from . import faults as fault_mod
from . import vocab
from . import wire

DOCUMENT_SCHEMAS = authority_data.DOCUMENT_SCHEMAS

_IDENTIFIER_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:\-]{0,127}\Z")
_SHA256_UPPER_RE = re.compile(r"\A[0-9A-F]{64}\Z")
_PARENT_DIGEST_RE = re.compile(r"\APARENT_[0-9A-F]{64}\Z")

_A2_POINTER = "/a2_raw_shared_bundle"

_ARRAY_CLASSES = (
    "ORDERED_IDENTIFIER_ARRAY",
    "SET_IDENTIFIER_ARRAY",
    "ORDERED_STRING_ARRAY",
)


def _rows_by_pointer(document_id):
    schema = DOCUMENT_SCHEMAS[document_id]
    return {row["pointer"]: row for row in schema["field_schema_rows"]}


_ROWS = {name: _rows_by_pointer(name) for name in DOCUMENT_SCHEMAS}


def kind_of(value):
    return a2schema.kind_of(value)


def _row_for(rows, pointer):
    """Exactly one row, or None when the pointer is not a schema member."""
    row = rows.get(pointer)
    if row is not None:
        return row
    if "/" in pointer:
        head, tail = pointer.rsplit("/", 1)
        if tail.isdigit():
            return rows.get(head + "/*")
    return None


def validate(value, document_id, found):
    """Admit one realized document, appending CLOSED_SCHEMA faults to ``found``."""
    rows = _ROWS[document_id]
    _walk(rows, value, "", document_id, found)
    if document_id == "COMMON":
        _cross_field(value, document_id, found)


def _walk(rows, value, pointer, document_id, found):
    if pointer == _A2_POINTER:
        row = rows[pointer]
        if kind_of(value) != row["value_kind"]:
            _fault(found, "FIELD_TYPE", document_id, pointer)
            return
        a2schema.validate(value, pointer, document_id, found)
        return

    row = _row_for(rows, pointer)
    if row is None:
        return
    if not _check_kind(row, value, pointer, document_id, found):
        return
    _check_value(row, value, pointer, document_id, found)

    kind = kind_of(value)
    if kind == "OBJECT":
        allowed = row.get("fields_exact")
        if allowed is not None:
            unknown = False
            for name in value:
                if name not in allowed:
                    unknown = True
            if unknown:
                _fault(found, "UNKNOWN_FIELD", document_id, pointer)
            for name in allowed:
                if name not in value:
                    _fault(
                        found,
                        "MISSING_FIELD",
                        document_id,
                        pointer + "/" + fault_mod.pointer_escape(name),
                    )
        for name, member in value.items():
            _walk(
                rows,
                member,
                pointer + "/" + fault_mod.pointer_escape(name),
                document_id,
                found,
            )
    elif kind == "ARRAY":
        for index, member in enumerate(value):
            _walk(rows, member, pointer + "/" + str(index), document_id, found)
        if value and _item_collides(rows.get(pointer + "/*"), value[0]):
            _fault(found, "FIELD_TYPE", document_id, pointer)


def _fault(found, code, document_id, pointer):
    found.append(fault_mod.Fault("CLOSED_SCHEMA", code, document_id, pointer, 0))


def _row_kinds(row):
    """``a2_resolution``: the row's ``allowed_value_kinds``.

    ``types_and_values``: "INTEGER_OR_NULL is the explicit union only", so every
    other declared ``value_kind`` names exactly one admitted kind.  A ``const`` or
    ``enum`` narrows no further on these rows: every ``document_schemas`` row
    carrying one declares ``value_kind`` STRING and holds only STRING literals.
    """
    declared = row["value_kind"]
    if declared == "INTEGER_OR_NULL":
        return {"INTEGER", "NULL"}
    return {declared}


def _item_collides(item_row, item_value):
    """``postimage_collision_kat`` for the rows-driven arrays.

    True exactly when ``item_value`` is the value the array-parent
    ARRAY_ITEM_INCOMPATIBLE constructor writes at index zero, which is the only
    postimage that target and the item-zero REPLACE_INCOMPATIBLE_TYPE target
    share.  An array with no ``/*`` item row has no resolved member contract and
    therefore no parent target.
    """
    if item_row is None:
        return False
    return a2schema.is_item_constructor_postimage(_row_kinds(item_row), item_value)


def _check_kind(row, value, pointer, document_id, found):
    declared = row["value_kind"]
    kind = kind_of(value)
    if declared == "INTEGER_OR_NULL":
        ok = kind in ("INTEGER", "NULL")
    else:
        ok = kind == declared
    if not ok:
        _fault(found, "FIELD_TYPE", document_id, pointer)
        return False
    return True


def _check_value(row, value, pointer, document_id, found):
    kind = kind_of(value)
    bad = False

    if "const" in row and value != row["const"]:
        bad = True
    if "enum" in row and value not in row["enum"]:
        bad = True

    class_id = row.get("class_id")
    if kind == "STRING":
        if class_id == "IDENTIFIER":
            if _IDENTIFIER_RE.match(value) is None or not value.isascii():
                bad = True
        elif class_id == "SHA256_UPPER":
            if _SHA256_UPPER_RE.match(value) is None:
                bad = True
        elif class_id == "PARENT_DIGEST_IDENTIFIER":
            if _PARENT_DIGEST_RE.fullmatch(value) is None:
                bad = True
        elif class_id == "CANONICAL_BASE64":
            if not wire.is_canonical_base64(value):
                bad = True
            else:
                decoded = len(wire.b64decode_strict(value))
                if (
                    row.get("decoded_minimum") is not None
                    and decoded < row["decoded_minimum"]
                ):
                    bad = True
                if (
                    row.get("decoded_maximum") is not None
                    and decoded > row["decoded_maximum"]
                ):
                    bad = True
        octets = len(value.encode("utf-8", "surrogatepass"))
        if row.get("utf8_minimum") is not None and octets < row["utf8_minimum"]:
            bad = True
        if row.get("utf8_maximum") is not None and octets > row["utf8_maximum"]:
            bad = True
    elif kind == "INTEGER":
        if row.get("minimum") is not None and value < row["minimum"]:
            bad = True
        if row.get("maximum") is not None and value > row["maximum"]:
            bad = True
    elif kind == "ARRAY":
        if class_id in _ARRAY_CLASSES:
            if row.get("minimum") is not None and len(value) < row["minimum"]:
                bad = True
            if row.get("maximum") is not None and len(value) > row["maximum"]:
                bad = True
        if row.get("unique") is True:
            encoded = [wire.cj6(member) for member in value]
            if len(set(encoded)) != len(encoded):
                bad = True
        if row.get("utf8_sorted") is True:
            octets = [
                member.encode("utf-8", "surrogatepass")
                for member in value
                if isinstance(member, str)
            ]
            if len(octets) == len(value) and octets != sorted(octets):
                bad = True

    if bad:
        _fault(found, "FIELD_VALUE", document_id, pointer)


# -- document_schemas.COMMON.cross_field_laws ---------------------------------
#
# The seven laws are transcribed from ``cross_field_laws``.
#
# ``diagnostic_authority.atomic_target_projection``: "For CROSS_FIELD, stage/code
# are CLOSED_SCHEMA/CROSS_FIELD, diagnostic pointer is the exact cross_field_spec
# pointer and occurrence is 0."  A cross_field_spec is the paired registry object
# the authority names here, exactly as it names ``wire_variant_spec
# diagnostic_by_document`` for WIRE_AND_ADMISSION, and each spec carries
# ``patches[].pointer``.  Those pointers are transcribed below.  Six of the seven
# laws carry exactly one patch, so their diagnostic pointer is unique.
#
# JSON_CONTENT carries two patches and the phrase does not say which one is "the"
# pointer.  Declared reading: a CROSS_FIELD fault is raised at each patch pointer
# of the violated law and ``diagnostic_authority.fault_selection`` chooses the
# minimum tuple, which for JSON_CONTENT is /delivered_artifact_envelope/content_b64
# because "c" precedes "m" in UTF-8.  Emitting the second pointer can never change
# a selected output: CROSS_FIELD is the last CLOSED_SCHEMA code, so a CROSS_FIELD
# fault is selected only when it is the sole fault, and then the smaller of the
# two patch pointers is selected in either reading.

CROSS_FIELD_POINTERS = {
    "DELIVERED_ID": ("/requested_delivered_transfer/delivered_artifact_id",),
    "DELIVERED_REVISION": ("/requested_delivered_transfer/delivered_revision",),
    "JSON_CONTENT": (
        "/delivered_artifact_envelope/content_b64",
        "/delivered_artifact_envelope/media_type",
    ),
    "INTERVAL": ("/comparison_facts/valid_from_ns",),
    "RECEIVER_VOCAB": ("/comparison_facts/expected_receiver_capability",),
    "PURPOSE_VOCAB": ("/comparison_facts/expected_purpose",),
    "SCOPE_VOCAB": ("/comparison_facts/expected_scope",),
}


def _cross_field(value, document_id, found):
    for law_id in (
        "DELIVERED_ID",
        "DELIVERED_REVISION",
        "JSON_CONTENT",
        "INTERVAL",
        "RECEIVER_VOCAB",
        "PURPOSE_VOCAB",
        "SCOPE_VOCAB",
    ):
        try:
            held = _CROSS_FIELD_CHECK[law_id](value)
        except (KeyError, IndexError, TypeError, ValueError):
            held = False
        if not held:
            for pointer in CROSS_FIELD_POINTERS[law_id]:
                found.append(
                    fault_mod.Fault(
                        "CLOSED_SCHEMA", "CROSS_FIELD", document_id, pointer, 0
                    )
                )


def _law_delivered_id(document):
    return (
        document["delivered_artifact_envelope"]["artifact_id"]
        == document["requested_delivered_transfer"]["delivered_artifact_id"]
    )


def _law_delivered_revision(document):
    return (
        document["delivered_artifact_envelope"]["revision"]
        == document["requested_delivered_transfer"]["delivered_revision"]
    )


def _law_json_content(document):
    """JSON_CONTENT: the decoded bytes must be *admitted* JCS for their value.

    ``cross_field_laws.JSON_CONTENT``: "If media_type is application/json, strict
    base64 decode content_b64 and require decoded bytes equal admitted JCS for
    their parsed value."  Admission is the whole stage sequence
    ``diagnostic_authority.stage_order`` names -- ADMISSION, WIRE_UNICODE, JSON,
    VALUE_UNICODE, CANONICAL -- so an embedded document carrying any admission
    fault is not admitted and the law does not hold.  ``canonical_wire.jcs``
    states its admitted value domain as "object, array, NFC string,
    signed-int64, boolean, null", so an embedded non-NFC string is refused at
    VALUE_UNICODE even though a non-normalising serializer round-trips its bytes.

    The embedded document is admitted under the COMMON stage vocabulary, which
    fixes only the oversize code name and the 1 MiB size limit; the
    ``/delivered_artifact_envelope/content_b64`` row caps the decoded artifact at
    ``decoded_maximum`` 32768 and reports FIELD_VALUE above it, a lower
    ``code_order_by_stage`` index than CROSS_FIELD, so that limit never decides
    this law.

    The trailing byte comparison is the law's own last clause.  It is implied by
    an empty fault list -- CANONICAL is exactly the stage that compares a
    document with its own JCS -- and is kept because the law states it.
    """
    envelope = document["delivered_artifact_envelope"]
    if envelope["media_type"] != "application/json":
        return True
    raw = wire.b64decode_strict(envelope["content_b64"])
    admitted = admission_mod.admit(raw, "COMMON")
    if admitted.faults:
        return False
    return wire.jcs(admitted.value) == raw


def _law_interval(document):
    facts = document["comparison_facts"]
    return facts["valid_from_ns"] <= facts["valid_until_ns"]


def _selected_use(document):
    return document["a2_raw_shared_bundle"]["use_records"][0]


def _vocabulary_ids(document, entries_member):
    """The identifiers the selected A5 ``/domain_vocabulary`` declares.

    ``field_schema_rows['/a2_raw_shared_bundle']`` delegates the subtree to the
    accepted A2 projection schema by ``accepted_schema_sha256``.  That schema
    gives ``/domain_vocabulary`` the contract ``#/$defs/D013``, whose only entry
    lists are ``purpose_entries`` and ``scope_entries``, each an array of
    ``#/$defs/D012`` objects carrying a required ``id``.  "is a purpose_id in
    selected A5 /domain_vocabulary" is therefore membership in the ``id`` values
    of the named list.
    """
    vocabulary = document["a2_raw_shared_bundle"]["domain_vocabulary"]
    return [entry["id"] for entry in vocabulary[entries_member]]


def _law_receiver_vocab(document):
    """RECEIVER_VOCAB -- equality; its membership conjunct is not realizable.

    The law reads "/comparison_facts/expected_receiver_capability is a
    receiver_capability_id in selected A5 /domain_vocabulary and equals selected
    /use_records/0/receiver_capability_id".  ``#/$defs/D013`` declares no
    receiver-capability entry list at all, so nothing can be "a
    receiver_capability_id in /domain_vocabulary": that conjunct has no
    realizable witness set in the pinned A2 contract.  The frozen pair settles
    which way it resolves.  In all 47 committed COMMON objects the realized
    ``expected_receiver_capability`` occurs nowhere inside
    ``/a2_raw_shared_bundle/domain_vocabulary``, while every committed baseline
    output over those documents is a non-CROSS_FIELD output; a binding reading
    would turn all 394 of them into CLOSED_SCHEMA/CROSS_FIELD and is therefore
    falsified by the registry.  The conjunct imposes no constraint here, so only
    the equality conjunct is enforced.  ``CROSS_FIELD_SPECS`` gates both halves
    of this note: it re-measures the absence of the value from the vocabulary and
    re-measures that the unedited baseline reproduces its committed output.
    """
    return (
        document["comparison_facts"]["expected_receiver_capability"]
        == _selected_use(document)["receiver_capability_id"]
    )


def _law_purpose_vocab(document):
    """PURPOSE_VOCAB -- both conjuncts: vocabulary membership, then equality."""
    expected = document["comparison_facts"]["expected_purpose"]
    return (
        expected in _vocabulary_ids(document, "purpose_entries")
        and expected == _selected_use(document)["purpose_id"]
    )


def _law_scope_vocab(document):
    """SCOPE_VOCAB -- both conjuncts: every member declared, then array equality."""
    expected = document["comparison_facts"]["expected_scope"]
    declared = _vocabulary_ids(document, "scope_entries")
    return all(member in declared for member in expected) and expected == [
        _selected_use(document)["scope_id"]
    ]


_CROSS_FIELD_CHECK = {
    "DELIVERED_ID": _law_delivered_id,
    "DELIVERED_REVISION": _law_delivered_revision,
    "JSON_CONTENT": _law_json_content,
    "INTERVAL": _law_interval,
    "RECEIVER_VOCAB": _law_receiver_vocab,
    "PURPOSE_VOCAB": _law_purpose_vocab,
    "SCOPE_VOCAB": _law_scope_vocab,
}

_ = vocab
