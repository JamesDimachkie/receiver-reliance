"""Arm S-all -- the independently implemented static comparator.

``architecture.arm_isolation``: S imports common code plus
``rr_full_treatment.static_kernel``.  It imports neither ``receiver_reliance`` nor either
other arm.  The accepted-dependency pins are proved against the worktree before
that import happens and re-asserted before every accepted call.

``s_semantics.accepted_component`` fixes the component construction and the
nine-field acceptance test; ``s_semantics.extended_bits_order`` fixes the
thirteen extended predicates and their order; ``s_semantics.result`` fixes the
score and the threshold comparison.  ``architecture.scientific_role`` records
that the outer threshold domain 0..17 is fully registered and that this authority
selects none, so the threshold is read from the STATE document and never chosen
here.
"""

from .common import admission
from .common import pins
from .common import seam
from .common import wire

pins.verify_at_import()

from rr_full_treatment import static_kernel as _kernel  # noqa: E402  (pins gate this import)

pins.bind_module("rr_full_treatment.static_kernel", _kernel, "rr_full_treatment/static_kernel.py")

ENTRYPOINT = "DECIDE_S"

# s_semantics.component_policy, transcribed verbatim, with its declared SHA-256.
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
COMPONENT_POLICY_SHA256 = (
    "A917BAEA48B5923BBDC31B236AFB1FF3A5DA92B5860FF93EBEEEAF843C4C7BF3"
)

CANDIDATE_FORMAT = "RR-SCIENTIFIC-ARM-NEUTRAL-CANDIDATE-1"
TASK_FORMAT = "RR-SCIENTIFIC-CLOSED-TASK-1"
INPUT_FORMAT = "RR-SCIENTIFIC-S-ALL-INPUT-1"
OUTPUT_FORMAT = "RR-SCIENTIFIC-S-ALL-DECISION-1"
PROFILE = "static-reference-revision-digest/1"
PASS_REASON = "S_SCORE_BELOW_THRESHOLD"

DECISION_FIELDS_EXACT = (
    "candidate_sha256",
    "disposition",
    "feature_bits",
    "format",
    "input_sha256",
    "module_semantics_id",
    "policy_sha256",
    "reason_code",
    "risk_score",
)

# s_semantics.extended_bits_order
EXTENDED_BITS_ORDER = (
    "receiver_capability_mismatch",
    "purpose_mismatch",
    "scope_mismatch",
    "action_class_mismatch",
    "owner_or_principal_or_authority_mismatch",
    "direct_parents_mismatch",
    "route_or_slot_or_carrier_mismatch",
    "representation_sha256_mismatch",
    "origin_not_finalized",
    "generation_mismatch",
    "revocation_active",
    "fence_stale",
    "use_time_outside_inclusive_interval",
)


class _Unresolved(Exception):
    """The accepted component did not answer in its required shape."""


def _build_candidate(common):
    """The exact accepted candidate, from raw task, artifact, transfer and lineage."""
    task_facts = common["task_instruction_constraints"]
    transfer = common["requested_delivered_transfer"]
    return {
        "format": CANDIDATE_FORMAT,
        "lineage": common["source_lineage_observation"],
        "task": {
            "constraints": task_facts["constraints"],
            "format": TASK_FORMAT,
            "instruction": task_facts["instruction"],
            "task_id": common["task_id"],
        },
        "transfer": {
            "declared_sha256": transfer["declared_sha256"],
            "delivered_artifact": common["delivered_artifact_envelope"],
            "delivered_artifact_id": transfer["delivered_artifact_id"],
            "delivered_revision": transfer["delivered_revision"],
            "requested_artifact_id": transfer["requested_artifact_id"],
            "requested_revision": transfer["requested_revision"],
        },
    }


def _component_bits(common):
    """Invoke the accepted component and read its three feature bits."""
    pins.assert_verified("rr_full_treatment.static_kernel")

    candidate = _build_candidate(common)
    # "obtain candidate bytes only from accepted canonical_bytes"
    candidate_bytes = _kernel.canonical_bytes(candidate)
    if type(candidate_bytes) is not bytes:
        raise _Unresolved("accepted canonicalisation did not return bytes")
    candidate_sha256 = wire.sha256_upper(candidate_bytes)

    component_input = {
        "candidate": candidate,
        "candidate_sha256": candidate_sha256,
        "format": INPUT_FORMAT,
        "profile": PROFILE,
    }
    input_bytes = _kernel.canonical_bytes(component_input)
    policy_bytes = _kernel.canonical_bytes(COMPONENT_POLICY)
    if wire.sha256_upper(policy_bytes) != COMPONENT_POLICY_SHA256:
        raise _Unresolved("the component policy is not the frozen policy")

    raw = _kernel.decide(input_bytes, policy_bytes)
    if type(raw) is not bytes:
        raise _Unresolved("the accepted component did not return bytes")
    decision = _parse_component_decision(raw)

    if decision["format"] != OUTPUT_FORMAT:
        raise _Unresolved("unexpected component format")
    if decision["module_semantics_id"] != PROFILE:
        raise _Unresolved("unexpected component profile")
    if decision["candidate_sha256"] != candidate_sha256:
        raise _Unresolved("component candidate digest mismatch")
    if decision["input_sha256"] != wire.sha256_upper(input_bytes):
        raise _Unresolved("component input digest mismatch")
    if decision["policy_sha256"] != wire.sha256_upper(policy_bytes):
        raise _Unresolved("component policy digest mismatch")

    bits = decision["feature_bits"]
    if not isinstance(bits, list) or len(bits) != 3:
        raise _Unresolved("component feature bits are not a triple")
    for bit in bits:
        if not isinstance(bit, bool):
            raise _Unresolved("component feature bit is not a boolean")
    risk = decision["risk_score"]
    if isinstance(risk, bool) or not isinstance(risk, int):
        raise _Unresolved("component risk score is not an integer")
    if risk != sum(1 for bit in bits if bit):
        raise _Unresolved("component risk score does not match its bits")
    if decision["disposition"] != "PASS":
        raise _Unresolved("component disposition is not PASS")
    if decision["reason_code"] != PASS_REASON:
        raise _Unresolved("component reason is not the below-threshold reason")
    return [1 if bit else 0 for bit in bits]


def _parse_component_decision(raw):
    """Read the accepted component's exact nine-field decision document."""
    admitted = admission.admit(raw, "COMMON")
    if not admitted.parsed:
        raise _Unresolved("the component decision is not admitted JSON")
    for fault in admitted.faults:
        if fault.stage in ("JSON", "VALUE_UNICODE"):
            raise _Unresolved("the component decision is not admitted JSON")
    decision = admitted.value
    if not isinstance(decision, dict):
        raise _Unresolved("the component decision is not an object")
    if tuple(sorted(decision)) != DECISION_FIELDS_EXACT:
        raise _Unresolved("the component decision field set is not exact")
    return decision


def _extended_bits(common):
    """The thirteen extended predicates, in ``s_semantics.extended_bits_order``."""
    facts = common["comparison_facts"]
    values = {
        "receiver_capability_mismatch": facts["expected_receiver_capability"]
        != facts["observed_receiver_capability"],
        "purpose_mismatch": facts["expected_purpose"] != facts["observed_purpose"],
        "scope_mismatch": facts["expected_scope"] != facts["observed_scope"],
        "action_class_mismatch": facts["expected_action_class"]
        != facts["observed_action_class"],
        "owner_or_principal_or_authority_mismatch": (
            facts["expected_owner"] != facts["observed_owner"]
            or facts["expected_principal"] != facts["observed_principal"]
            or facts["expected_authority"] != facts["observed_authority"]
        ),
        "direct_parents_mismatch": facts["expected_direct_parents"]
        != facts["observed_direct_parents"],
        "route_or_slot_or_carrier_mismatch": (
            facts["expected_route"] != facts["observed_route"]
            or facts["expected_slot"] != facts["observed_slot"]
            or facts["expected_carrier"] != facts["observed_carrier"]
        ),
        "representation_sha256_mismatch": facts["expected_representation_sha256"]
        != facts["consumed_representation_sha256"],
        "origin_not_finalized": not facts["origin_finalized"],
        "generation_mismatch": facts["expected_generation"]
        != facts["observed_generation"],
        "revocation_active": bool(facts["revocation_active"]),
        "fence_stale": facts["current_fence"] > facts["carrier_fence"],
        "use_time_outside_inclusive_interval": not (
            facts["valid_from_ns"] <= facts["use_time_ns"] <= facts["valid_until_ns"]
        ),
    }
    return [1 if values[name] else 0 for name in EXTENDED_BITS_ORDER]


def _evaluate(canonical_common_value, canonical_module_state_value):
    try:
        component = _component_bits(canonical_common_value)
    except _Unresolved:
        return "S_COMPONENT_UNRESOLVED", None
    except Exception:
        # s_semantics: any failure of the accepted component leaves the
        # component unresolved; it never improves a disposition.
        return "S_COMPONENT_UNRESOLVED", None

    extended = _extended_bits(canonical_common_value)
    score = sum(component) + sum(extended)
    threshold = canonical_module_state_value["operating_threshold"]
    evidence = {
        "component_bits": component,
        "extended_bits": extended,
        "score": score,
        "threshold": threshold,
    }
    if score >= threshold:
        return "S_THRESHOLD_REACHED", evidence
    return "S_THRESHOLD_CLEAR", evidence


_SEMANTICS = seam.Semantics(ENTRYPOINT, _evaluate)


def decide(canonical_common_bytes: bytes, canonical_module_state_bytes: bytes) -> bytes:
    """The production entrypoint DECIDE_S."""
    return seam.decide(
        _SEMANTICS, canonical_common_bytes, canonical_module_state_bytes
    )


decide_s = decide
