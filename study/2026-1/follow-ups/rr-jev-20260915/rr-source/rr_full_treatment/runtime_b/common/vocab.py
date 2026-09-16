"""Closed vocabularies and the diagnostic orders, transcribed from the authority.

Nothing here is inferred from the registry.  ``closed_vocabularies``,
``diagnostic_authority.stage_order``, ``diagnostic_authority.code_order_by_stage``,
``diagnostic_authority.document_order``, ``diagnostic_authority.public_results``
and ``output_schema.domains`` are the sources.
"""

ENTRYPOINTS = ("DECIDE_R", "DECIDE_S", "DECIDE_U")
DOCUMENT_IDS = ("COMMON", "STATE_R", "STATE_S", "STATE_U")
FAMILY_IDS = (
    "ARGUMENT_REPRESENTATION",
    "CROSS_FIELD",
    "SCHEMA_MEMBER",
    "WIRE_AND_ADMISSION",
)
VALUE_KINDS = (
    "ARRAY",
    "BOOLEAN",
    "INTEGER",
    "NONBYTES",
    "NULL",
    "OBJECT",
    "RAW_BYTES",
    "STRING",
)

# diagnostic_authority.stage_order
STAGE_ORDER = (
    "INTERNAL",
    "PYTHON_TYPE",
    "ADMISSION",
    "WIRE_UNICODE",
    "JSON",
    "VALUE_UNICODE",
    "CANONICAL",
    "CLOSED_SCHEMA",
    "MODULE_SEMANTICS",
)

# diagnostic_authority.code_order_by_stage
CODE_ORDER_BY_STAGE = {
    "INTERNAL": ("BOUNDARY_EXCEPTION",),
    "PYTHON_TYPE": ("ARGUMENT_TYPE",),
    "ADMISSION": (
        "COMMON_OVERSIZE",
        "STATE_OVERSIZE",
        "DEPTH_LIMIT",
        "COLLECTION_LIMIT",
        "STRING_LIMIT",
    ),
    "WIRE_UNICODE": ("UTF8", "BOM"),
    "JSON": ("SYNTAX", "DUPLICATE_KEY", "INTEGER_RANGE", "FLOAT_FORBIDDEN"),
    "VALUE_UNICODE": ("SURROGATE", "NFC"),
    "CANONICAL": ("NONCANONICAL",),
    "CLOSED_SCHEMA": (
        "UNKNOWN_FIELD",
        "MISSING_FIELD",
        "FIELD_TYPE",
        "FIELD_VALUE",
        "CROSS_FIELD",
    ),
    "MODULE_SEMANTICS": (
        "U_TRANSPARENT",
        "S_COMPONENT_UNRESOLVED",
        "S_THRESHOLD_CLEAR",
        "S_THRESHOLD_REACHED",
        "R_DERIVATION_UNRESOLVED",
        "R_ENGINE_CONCLUSIVE",
        "R_ENGINE_UNRESOLVED",
        "R_LINEAGE_CONCLUSIVE",
        "R_LINEAGE_UNRESOLVED",
        "R_ACCEPTANCE_APPLICABLE",
        "R_ACCEPTANCE_INAPPLICABLE",
        "R_ACCEPTANCE_CONFLICT",
        "R_ACCEPTANCE_UNKNOWN",
    ),
}

# diagnostic_authority.document_order
DOCUMENT_ORDER = ("COMMON", "STATE")

# schema_resolution_and_atomic_constructor.type_order -- "the exact six-member
# list NULL, BOOLEAN, INTEGER, STRING, ARRAY, OBJECT ... scanned in that order".
TYPE_ORDER = ("NULL", "BOOLEAN", "INTEGER", "STRING", "ARRAY", "OBJECT")

# replacement_descriptor_authority.evaluation_primitives.type_representatives.
# These are authority values; the registry table of the same name is their
# mirror (evaluation_primitives.mirror_obligation).
TYPE_REPRESENTATIVES = {
    "NULL": None,
    "BOOLEAN": False,
    "INTEGER": 0,
    "STRING": "x",
    "ARRAY": [],
    "OBJECT": {},
}

# diagnostic_authority.public_results
PUBLIC_RESULTS = {
    "BOUNDARY_EXCEPTION": ("DEFER", "UNRESOLVED_HOLD"),
    "R_ACCEPTANCE_APPLICABLE": ("PASS", "ALLOW"),
    "R_ACCEPTANCE_CONFLICT": ("BLOCK", "CONCLUSIVE_HOLD"),
    "R_ACCEPTANCE_INAPPLICABLE": ("BLOCK", "CONCLUSIVE_HOLD"),
    "R_ACCEPTANCE_UNKNOWN": ("DEFER", "UNRESOLVED_HOLD"),
    "R_DERIVATION_UNRESOLVED": ("DEFER", "UNRESOLVED_HOLD"),
    "R_ENGINE_CONCLUSIVE": ("BLOCK", "CONCLUSIVE_HOLD"),
    "R_ENGINE_UNRESOLVED": ("DEFER", "UNRESOLVED_HOLD"),
    "R_LINEAGE_CONCLUSIVE": ("BLOCK", "CONCLUSIVE_HOLD"),
    "R_LINEAGE_UNRESOLVED": ("DEFER", "UNRESOLVED_HOLD"),
    "S_COMPONENT_UNRESOLVED": ("DEFER", "UNRESOLVED_HOLD"),
    "S_THRESHOLD_CLEAR": ("PASS", "ALLOW"),
    "S_THRESHOLD_REACHED": ("BLOCK", "CONCLUSIVE_HOLD"),
    "U_TRANSPARENT": ("PASS", "ALLOW"),
}
PRESEMANTIC_DEFAULT = ("DEFER", "UNRESOLVED_HOLD")

# output_schema
OUTPUT_FORMAT = "RR-STUDY-TREATMENT-DECISION-5"
OUTPUT_FIELDS_EXACT = (
    "code",
    "disposition",
    "format",
    "input_digest",
    "occurrence",
    "pointer",
    "reason",
    "remediation",
    "stage",
    "witness_digest",
)
DISPOSITIONS = ("BLOCK", "DEFER", "PASS")
REASONS = ("ALLOW", "CONCLUSIVE_HOLD", "UNRESOLVED_HOLD")
REMEDIATIONS = ("NONE", "REFETCH")

# canonical_wire.input_digest / witness_digest domains
INPUT_DOMAIN = b"RR-STUDY-TREATMENT-INPUT-5\x00"
WITNESS_DOMAIN = b"RR-STUDY-TREATMENT-WITNESS-5\x00"

# document_schemas formats
COMMON_FORMAT = "RR-STUDY-TREATMENT-COMMON-5"
STATE_FORMAT_BY_DOCUMENT = {
    "STATE_R": "RR-STUDY-TREATMENT-STATE-R-5",
    "STATE_S": "RR-STUDY-TREATMENT-STATE-S-5",
    "STATE_U": "RR-STUDY-TREATMENT-STATE-U-5",
}

STATE_DOCUMENT_BY_ENTRYPOINT = {
    "DECIDE_R": "STATE_R",
    "DECIDE_S": "STATE_S",
    "DECIDE_U": "STATE_U",
}
MODULE_BY_ENTRYPOINT = {"DECIDE_R": "R", "DECIDE_S": "S", "DECIDE_U": "U"}


def stage_index(stage: str) -> int:
    return STAGE_ORDER.index(stage)


def code_index(stage: str, code: str) -> int:
    return CODE_ORDER_BY_STAGE[stage].index(code)


def diagnostic_document(document_id: str) -> str:
    """diagnostic_authority.document_projection."""
    if document_id == "COMMON":
        return "COMMON"
    if document_id in ("STATE_R", "STATE_S", "STATE_U"):
        return "STATE"
    raise ValueError("unknown document_id")


def document_index(document_id: str) -> int:
    return DOCUMENT_ORDER.index(diagnostic_document(document_id))
