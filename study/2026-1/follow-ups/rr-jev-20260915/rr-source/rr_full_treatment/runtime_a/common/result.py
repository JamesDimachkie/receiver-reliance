"""Authority-defined ten-field decision construction."""

from __future__ import annotations

import hashlib
from typing import Any

from .wire import Fault, ZERO64, frame, jcs

FORMAT = "RR-STUDY-TREATMENT-DECISION-5"

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


def input_digest(entrypoint: str, common: object, state: object) -> str:
    if type(common) is not bytes or type(state) is not bytes:
        return ZERO64
    preimage = (
        b"RR-STUDY-TREATMENT-INPUT-5\0"
        + frame(entrypoint.encode("ascii"))
        + frame(common)
        + frame(state)
    )
    return hashlib.sha256(preimage).hexdigest().upper()


def decision_bytes(
    entrypoint: str,
    module: str,
    common: object,
    state: object,
    code: str,
    stage: str,
    pointer: str = "",
    occurrence: int = 0,
    semantic_evidence: Any = None,
    remediation: str = "NONE",
) -> bytes:
    disposition, reason = PUBLIC_RESULTS.get(code, ("DEFER", "UNRESOLVED_HOLD"))
    if disposition == "PASS":
        remediation = "NONE"
    digest = input_digest(entrypoint, common, state)
    evidence = {
        "code": code,
        "module": module,
        "occurrence": occurrence,
        "pointer": pointer,
        "semantic_evidence": semantic_evidence,
        "stage": stage,
    }
    witness_preimage = (
        b"RR-STUDY-TREATMENT-WITNESS-5\0"
        + frame(entrypoint.encode("ascii"))
        + bytes.fromhex(digest)
        + frame(disposition.encode("ascii"))
        + frame(reason.encode("ascii"))
        + frame(remediation.encode("ascii"))
        + frame(jcs(evidence))
    )
    witness = hashlib.sha256(witness_preimage).hexdigest().upper()
    return jcs(
        {
            "code": code,
            "disposition": disposition,
            "format": FORMAT,
            "input_digest": digest,
            "occurrence": occurrence,
            "pointer": pointer,
            "reason": reason,
            "remediation": remediation,
            "stage": stage,
            "witness_digest": witness,
        }
    )


def presemantic_bytes(
    entrypoint: str,
    module: str,
    common: object,
    state: object,
    fault: Fault,
    common_admitted: bool,
    refetch_enabled: bool,
) -> bytes:
    remediation = "REFETCH" if common_admitted and refetch_enabled else "NONE"
    return decision_bytes(
        entrypoint,
        module,
        common,
        state,
        fault.code,
        fault.stage,
        fault.pointer,
        fault.occurrence,
        None,
        remediation,
    )


def boundary_exception(entrypoint: str, common: object, state: object) -> bytes:
    return decision_bytes(
        entrypoint,
        "PUBLIC_BOUNDARY",
        common,
        state,
        "BOUNDARY_EXCEPTION",
        "INTERNAL",
        "",
        0,
        None,
        "NONE",
    )
