"""Static-comparator S-all arm."""

from __future__ import annotations

import hashlib
import json

from .common.pins import KERNEL_PINS, verify as _verify_pins

# accepted_dependencies.accepted_source_files: the accepted kernel is verified before it is
# imported, so a pin mismatch stops the implementation instead of silently running tampered bytes.
_verify_pins(KERNEL_PINS)

from rr_full_treatment import static_kernel as kernel  # noqa: E402  (import gated by the pin check above)

from .common.admission import admit_pair  # noqa: E402
from .common.result import boundary_exception, decision_bytes  # noqa: E402

ENTRYPOINT = "DECIDE_S"
MODULE = "S"

COMPONENT_POLICY = {
    "boundary": "WITHHOLD_IF_SCORE_GE_THRESHOLD",
    "format": "RR-SCIENTIFIC-S-ALL-POLICY-1",
    "operating_threshold": 4,
    "policy_state": "FROZEN",
    "refusal_map": {
        "ambiguous": "DEFER",
        "inconsistent": "DEFER",
        "malformed": "DEFER",
        "missing": "DEFER",
        "noncanonical": "DEFER",
        "oversized": "DEFER",
        "runtime_failure": "DEFER",
        "stale": "DEFER",
        "unknown": "DEFER",
    },
    "selection_rule": "MIN_RISK_THEN_MAX_COVERAGE_THEN_MIN_CLEAN_WITHHOLDING",
    "selection_tie_break": "HIGHEST_THRESHOLD",
    "target_clean_withholding": {"denominator": 1, "numerator": 0},
}
COMPONENT_POLICY_BYTES = kernel.canonical_bytes(COMPONENT_POLICY)
COMPONENT_POLICY_SHA256 = "A917BAEA48B5923BBDC31B236AFB1FF3A5DA92B5860FF93EBEEEAF843C4C7BF3"


def _component(common: dict) -> list[int] | None:
    task = common["task_instruction_constraints"]
    artifact = common["delivered_artifact_envelope"]
    transfer = common["requested_delivered_transfer"]
    candidate = {
        "format": "RR-SCIENTIFIC-ARM-NEUTRAL-CANDIDATE-1",
        "lineage": common["source_lineage_observation"],
        "task": {
            "constraints": task["constraints"],
            "format": "RR-SCIENTIFIC-CLOSED-TASK-1",
            "instruction": task["instruction"],
            "task_id": common["task_id"],
        },
        "transfer": {
            "declared_sha256": transfer["declared_sha256"],
            "delivered_artifact": artifact,
            "delivered_artifact_id": transfer["delivered_artifact_id"],
            "delivered_revision": transfer["delivered_revision"],
            "requested_artifact_id": transfer["requested_artifact_id"],
            "requested_revision": transfer["requested_revision"],
        },
    }
    candidate_bytes = kernel.canonical_bytes(candidate)
    candidate_sha = hashlib.sha256(candidate_bytes).hexdigest().upper()
    component_input = {
        "candidate": candidate,
        "candidate_sha256": candidate_sha,
        "format": "RR-SCIENTIFIC-S-ALL-INPUT-1",
        "profile": "static-reference-revision-digest/1",
    }
    input_bytes = kernel.canonical_bytes(component_input)
    output_bytes = kernel.decide(input_bytes, COMPONENT_POLICY_BYTES)
    try:
        output = json.loads(output_bytes)
        if kernel.canonical_bytes(output) != output_bytes:
            return None
    except BaseException:
        return None
    expected_keys = {
        "candidate_sha256",
        "disposition",
        "feature_bits",
        "format",
        "input_sha256",
        "module_semantics_id",
        "policy_sha256",
        "reason_code",
        "risk_score",
    }
    if type(output) is not dict or set(output) != expected_keys:
        return None
    bits = output.get("feature_bits")
    if type(bits) is not list or len(bits) != 3 or any(type(bit) is not bool for bit in bits):
        return None
    if (
        output.get("format") != "RR-SCIENTIFIC-S-ALL-DECISION-1"
        or output.get("module_semantics_id") != "static-reference-revision-digest/1"
        or output.get("candidate_sha256") != candidate_sha
        or output.get("input_sha256") != hashlib.sha256(input_bytes).hexdigest().upper()
        or output.get("policy_sha256") != COMPONENT_POLICY_SHA256
        or output.get("risk_score") != sum(bits)
        or output.get("disposition") != "PASS"
        or output.get("reason_code") != "S_SCORE_BELOW_THRESHOLD"
    ):
        return None
    return [int(bit) for bit in bits]


def _extended(common: dict) -> list[int]:
    facts = common["comparison_facts"]
    return [
        int(facts["observed_receiver_capability"] != facts["expected_receiver_capability"]),
        int(facts["observed_purpose"] != facts["expected_purpose"]),
        int(facts["observed_scope"] != facts["expected_scope"]),
        int(facts["observed_action_class"] != facts["expected_action_class"]),
        int(
            facts["observed_owner"] != facts["expected_owner"]
            or facts["observed_principal"] != facts["expected_principal"]
            or facts["observed_authority"] != facts["expected_authority"]
        ),
        int(facts["observed_direct_parents"] != facts["expected_direct_parents"]),
        int(
            facts["observed_route"] != facts["expected_route"]
            or facts["observed_slot"] != facts["expected_slot"]
            or facts["observed_carrier"] != facts["expected_carrier"]
        ),
        int(facts["consumed_representation_sha256"] != facts["expected_representation_sha256"]),
        int(not facts["origin_finalized"]),
        int(facts["observed_generation"] != facts["expected_generation"]),
        int(facts["revocation_active"]),
        int(facts["current_fence"] > facts["carrier_fence"]),
        int(not (facts["valid_from_ns"] <= facts["use_time_ns"] <= facts["valid_until_ns"])),
    ]


def decide(canonical_common_bytes: bytes, canonical_module_state_bytes: bytes) -> bytes:
    try:
        common, state, refusal, refetch = admit_pair(
            ENTRYPOINT,
            MODULE,
            "STATE_S",
            canonical_common_bytes,
            canonical_module_state_bytes,
        )
        if refusal is not None:
            return refusal
        component_bits = _component(common)
        if component_bits is None:
            return decision_bytes(
                ENTRYPOINT,
                MODULE,
                canonical_common_bytes,
                canonical_module_state_bytes,
                "S_COMPONENT_UNRESOLVED",
                "MODULE_SEMANTICS",
                semantic_evidence=None,
                remediation="REFETCH" if refetch else "NONE",
            )
        extended_bits = _extended(common)
        score = sum(component_bits) + sum(extended_bits)
        threshold = state["operating_threshold"]
        code = "S_THRESHOLD_REACHED" if score >= threshold else "S_THRESHOLD_CLEAR"
        evidence = {
            "component_bits": component_bits,
            "extended_bits": extended_bits,
            "score": score,
            "threshold": threshold,
        }
        return decision_bytes(
            ENTRYPOINT,
            MODULE,
            canonical_common_bytes,
            canonical_module_state_bytes,
            code,
            "MODULE_SEMANTICS",
            semantic_evidence=evidence,
            remediation="REFETCH" if refetch else "NONE",
        )
    except BaseException:
        return boundary_exception(ENTRYPOINT, canonical_common_bytes, canonical_module_state_bytes)


decide_s = decide

__all__ = ("decide", "decide_s")
