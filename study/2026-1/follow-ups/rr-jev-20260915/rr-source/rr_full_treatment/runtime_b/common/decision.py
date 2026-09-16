"""Construction of the exact ten-field decision bytes.

``output_schema`` fixes the field set and the two digest laws; ``canonical_wire``
fixes ``input_digest`` and ``witness_digest``; ``diagnostic_authority.public_results``
maps a code to its disposition and reason; ``diagnostic_authority.remediation``
fixes the remediation.
"""

import hashlib

from . import vocab
from . import wire

_EXPECTED_REMEDIATION = {"attempt_ordinal": 0, "refetch_budget": 1}


def input_digest_bytes(entrypoint, common_bytes, state_bytes):
    """``canonical_wire.input_digest`` as raw digest bytes.

    ``ZERO64`` when either argument is not exact built-in bytes; the caller
    supplies that case by passing ``None``.
    """
    if common_bytes is None or state_bytes is None:
        return None
    return hashlib.sha256(
        vocab.INPUT_DOMAIN
        + wire.frame(entrypoint.encode("ascii"))
        + wire.frame(common_bytes)
        + wire.frame(state_bytes)
    ).digest()


def module_evidence(code, module, occurrence, pointer, semantic_evidence, stage):
    """``output_schema.module_evidence``: the witness-only exact object."""
    return {
        "code": code,
        "module": module,
        "occurrence": occurrence,
        "pointer": pointer,
        "semantic_evidence": semantic_evidence,
        "stage": stage,
    }


def witness_digest(
    entrypoint, digest_bytes, disposition, reason, remediation, evidence
):
    """``canonical_wire.witness_digest``."""
    return wire.sha256_upper(
        vocab.WITNESS_DOMAIN
        + wire.frame(entrypoint.encode("ascii"))
        + digest_bytes
        + wire.frame(disposition.encode("ascii"))
        + wire.frame(reason.encode("ascii"))
        + wire.frame(remediation.encode("ascii"))
        + wire.frame(wire.jcs(evidence))
    )


def resolve_remediation(disposition, common_schema_passed, common_value):
    """``diagnostic_authority.remediation``.

    NONE for PASS.  For BLOCK or DEFER it is REFETCH exactly when COMMON fully
    passed CLOSED_SCHEMA and ``/remediation`` is exactly
    ``{attempt_ordinal:0, refetch_budget:1}``.
    """
    if disposition == "PASS":
        return "NONE"
    if not common_schema_passed:
        return "NONE"
    if not isinstance(common_value, dict):
        return "NONE"
    remediation = common_value.get("remediation")
    if not isinstance(remediation, dict):
        return "NONE"
    if set(remediation) != set(_EXPECTED_REMEDIATION):
        return "NONE"
    for key, expected in _EXPECTED_REMEDIATION.items():
        got = remediation[key]
        if isinstance(got, bool) or got != expected:
            return "NONE"
    return "REFETCH"


def build(
    entrypoint,
    digest_bytes,
    stage,
    code,
    pointer,
    occurrence,
    module,
    semantic_evidence,
    remediation,
):
    """Serialise the exact ten-field decision document."""
    disposition, reason = vocab.PUBLIC_RESULTS.get(code, vocab.PRESEMANTIC_DEFAULT)
    if disposition == "PASS":
        remediation = "NONE"
    if digest_bytes is None:
        digest_hex = wire.ZERO64
        digest_raw = bytes.fromhex(wire.ZERO64)
    else:
        digest_hex = digest_bytes.hex().upper()
        digest_raw = digest_bytes
    evidence = module_evidence(
        code, module, occurrence, pointer, semantic_evidence, stage
    )
    witness = witness_digest(
        entrypoint, digest_raw, disposition, reason, remediation, evidence
    )
    document = {
        "code": code,
        "disposition": disposition,
        "format": vocab.OUTPUT_FORMAT,
        "input_digest": digest_hex,
        "occurrence": occurrence,
        "pointer": pointer,
        "reason": reason,
        "remediation": remediation,
        "stage": stage,
        "witness_digest": witness,
    }
    if set(document) != set(vocab.OUTPUT_FIELDS_EXACT):
        raise ValueError("output field set is not exact")
    return wire.jcs(document)
