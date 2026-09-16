"""Receiver-local R-all arm."""

from __future__ import annotations

import copy
import hashlib
from datetime import datetime

from .common.pins import RECEIVER_PINS, verify as _verify_pins

# accepted_dependencies.accepted_source_files: the accepted receiver dependency is verified before
# it is imported, so a pin mismatch stops the implementation instead of silently running tampered
# bytes.
_verify_pins(RECEIVER_PINS)

from receiver_reliance import decide_audited  # noqa: E402  (import gated by the pin check above)

from ._r_data import HANDOFF_CLEAN  # noqa: E402
from ._policy import POLICY  # noqa: E402
from .common.admission import admit_pair  # noqa: E402
from .common.result import boundary_exception, decision_bytes  # noqa: E402
from .common.wire import jcs  # noqa: E402

ENTRYPOINT = "DECIDE_R"
MODULE = "R"

REQUIRED_CLASSES = {
    "CLAIM_VERSION",
    "DECLARATION_RECORD",
    "MANDATE_RECORD",
    "USE_RECORD",
}
REQUIRED_EXTENT = {"SOURCE_MANDATE", "SOURCE_PRIMARY"}


def _result(
    common_bytes: bytes,
    state_bytes: bytes,
    code: str,
    refetch: bool,
    evidence: dict | None = None,
) -> bytes:
    return decision_bytes(
        ENTRYPOINT,
        MODULE,
        common_bytes,
        state_bytes,
        code,
        "MODULE_SEMANTICS",
        semantic_evidence=evidence,
        remediation="REFETCH" if refetch else "NONE",
    )


def _converted(raw: dict) -> tuple[dict, dict, dict]:
    """Convert only declared frontier members, keeping the namespaces explicit."""
    order = raw["ledger_observations"][0]["included_record_refs"]
    if len(order) != len(set(order)):
        raise ValueError("repeated ledger reference")
    roots = {}
    for row in raw["domain_mandate_records"]:
        key = row["mandate_version_ref"]
        if key in roots:
            raise ValueError("duplicate mandate")
        roots[key] = row
    included = set(order)
    records = {}
    for row in raw["declaration_records"]:
        key = row["declaration_version_ref"]
        if key not in included:
            continue
        if key in records or key in roots:
            raise ValueError("duplicate or ambiguous declaration identity")
        records[key] = row
    grants, grant_ids = {}, set()
    for key, row in records.items():
        if row["declaration_kind"] != "DELEGATION_DECLARED":
            continue
        grant_id = row["grant_id"]
        if grant_id in grant_ids or grant_id in records or grant_id in roots:
            raise ValueError("duplicate or ambiguous grant identity")
        if row["standing_basis_ref"] not in roots:
            raise ValueError("grant root is unresolved or not a root mandate")
        grant_ids.add(grant_id)
        grants[key] = row
    return roots, records, grants


def _derivation_ready(raw: dict) -> bool:
    uses = raw.get("use_records")
    ledgers = raw.get("ledger_observations")
    closures = raw.get("closure_attestations")
    if type(uses) is not list or len(uses) != 1:
        return False
    if type(ledgers) is not list or len(ledgers) != 1:
        return False
    if type(closures) is not list or len(closures) != 1:
        return False
    use = uses[0]
    ledger = ledgers[0]
    closure = closures[0]
    if (
        ledger.get("action_or_decision_ref") != use.get("action_or_decision_ref")
        or ledger.get("decision_context_ref") != use.get("decision_context_ref")
        or ledger.get("captured_at", "") >= use.get("occurred_at", "")
        or closure.get("ledger_id") != ledger.get("ledger_id")
        or closure.get("committed_frontier") != ledger.get("committed_frontier")
    ):
        return False
    try:
        _converted(raw)
    except (KeyError, TypeError, ValueError):
        return False
    return True


def _request(common: dict) -> bytes:
    request = copy.deepcopy(HANDOFF_CLEAN)
    request["decision_input"]["facts"] = copy.deepcopy(common["guard_observation_facts"])
    inner = request["inner_request"]
    inner["input"] = copy.deepcopy(common["a2_raw_shared_bundle"])
    request["inner_input_sha256"] = hashlib.sha256(jcs(inner["input"])).hexdigest().upper()
    request["inner_request_raw_sha256"] = hashlib.sha256(jcs(inner) + b"\n").hexdigest().upper()
    return jcs(request) + b"\n"


def _engine(request_bytes: bytes) -> tuple[str, dict | None]:
    try:
        envelope = decide_audited(request_bytes)
    except BaseException:
        return "UNRESOLVED", None
    if type(envelope) is not dict:
        return "UNRESOLVED", None
    native = envelope.get("audited_behavior_class")
    if native in ("MALFORMED_OR_BOUNDARY", "BINDING_OR_CONFLICT"):
        return "CONCLUSIVE", envelope
    if native in ("OMISSION_OR_INCOMPLETE", "AUDIT_INCOMPLETE", "PROTOCOL_ERROR"):
        return "UNRESOLVED", envelope
    if native != "VALID":
        return "UNRESOLVED", envelope
    if type(envelope.get("audit")) is not dict or type(envelope.get("sealed_response")) is not dict:
        return "UNRESOLVED", envelope
    return "VALID", envelope


def _lineage_code(facts: dict) -> str | None:
    if not facts["origin_finalized"]:
        return "R_LINEAGE_UNRESOLVED"
    if (
        facts["observed_receiver_capability"] != facts["expected_receiver_capability"]
        or facts["observed_direct_parents"] != facts["expected_direct_parents"]
        or facts["observed_route"] != facts["expected_route"]
        or facts["observed_slot"] != facts["expected_slot"]
        or facts["observed_carrier"] != facts["expected_carrier"]
        or facts["observed_generation"] != facts["expected_generation"]
        or facts["revocation_active"]
        or facts["current_fence"] > facts["carrier_fence"]
        or not (facts["valid_from_ns"] <= facts["use_time_ns"] <= facts["valid_until_ns"])
    ):
        return "R_LINEAGE_CONCLUSIVE"
    return None


ACCEPTANCE_KINDS = {"ADOPTION_DECLARED", "INTENDED_USE_DECLARED"}


def _contains(interval: dict, instant: str) -> bool:
    return interval["effective_from"] <= instant <= interval["effective_until"]


def _matches(row: dict, use: dict, roots: dict, grants: dict) -> bool:
    """Only called after every active acceptance's references have resolved."""
    basis = row["standing_basis_ref"]
    mandate = roots[row["mandate_version_ref"]]
    instant = use["occurred_at"]
    if not all(row[key] == use[key] for key in (
        "receiver_capability_id", "episode_id", "exact_claim_version_id", "purpose_id", "scope_id"
    )):
        return False
    if not (
        row["recorded_at"] <= instant
        and _contains(row["interval"], instant)
        and row["issuer_capability_id"] == mandate["subject_capability_id"]
        and row["declaration_kind"] in mandate["permitted_record_kinds"]
        and row["purpose_id"] in mandate["purpose_ids"]
        and row["scope_id"] in mandate["scope_ids"]
        and row["policy_ref"] == mandate["policy_ref"]
        and _contains(mandate["interval"], instant)
    ):
        return False
    if basis in roots:
        return basis == row["mandate_version_ref"]
    grant = grants[basis]
    grant_root = roots[grant["standing_basis_ref"]]
    return (
        all(grant[key] == row[key] for key in ("purpose_id", "scope_id", "policy_ref"))
        and grant["delegate_capability_id"] == row["issuer_capability_id"]
        and _contains(grant["interval"], instant)
        and "DELEGATION_DECLARED" in grant_root["permitted_record_kinds"]
        and grant_root["subject_capability_id"] == grant["issuer_capability_id"]
    )


def _acceptance(raw: dict) -> tuple[str, str | None]:
    use = raw["use_records"][0]
    ledger = raw["ledger_observations"][0]
    closure = raw["closure_attestations"][0]
    age = (datetime.fromisoformat(use["occurred_at"]) - datetime.fromisoformat(ledger["captured_at"])).total_seconds()
    if (
        set(closure.get("source_extent", [])) != REQUIRED_EXTENT
        or set(closure.get("closed_record_classes", [])) != REQUIRED_CLASSES
        or closure.get("closed_through", "") < use.get("occurred_at", "")
        or age > POLICY["max_snapshot_age_seconds"]
    ):
        return "UNKNOWN", None
    roots, records, grants = _converted(raw)
    inactive, unknown, conflict = set(), False, False
    for row in records.values():
        if row["declaration_kind"] not in ("DECLARATION_WITHDRAWN", "DECLARATION_REPLACED"):
            continue
        target = row["target_declaration_version_ref"]
        target_row = records.get(target)
        if target_row is None:
            unknown = True
        elif row["effective_at"] <= use["occurred_at"]:
            if target_row.get("declaration_kind") not in ACCEPTANCE_KINDS:
                conflict = True
            else:
                inactive.add(target)
    active = [row for key, row in records.items()
              if row["declaration_kind"] in ACCEPTANCE_KINDS and key not in inactive]
    for row in active:
        if (row["standing_basis_ref"] not in roots and row["standing_basis_ref"] not in grants
                or row["mandate_version_ref"] not in roots):
            unknown = True
    declared = use.get("declared_basis_refs", [])
    if unknown or any(ref not in records for ref in declared):
        return "UNKNOWN", None
    qualifying = [row for row in active if _matches(row, use, roots, grants)]
    if conflict or len(qualifying) > 1:
        return "CONFLICT", None
    if len(qualifying) == 1:
        selected = qualifying[0]["declaration_version_ref"]
        if selected in declared:
            return "APPLICABLE", selected
    return "INAPPLICABLE", None


def decide(canonical_common_bytes: bytes, canonical_module_state_bytes: bytes) -> bytes:
    try:
        common, _state, refusal, refetch = admit_pair(
            ENTRYPOINT,
            MODULE,
            "STATE_R",
            canonical_common_bytes,
            canonical_module_state_bytes,
        )
        if refusal is not None:
            return refusal
        raw = common["a2_raw_shared_bundle"]
        if not _derivation_ready(raw):
            return _result(canonical_common_bytes, canonical_module_state_bytes, "R_DERIVATION_UNRESOLVED", refetch)
        engine_class, envelope = _engine(_request(common))
        if engine_class == "CONCLUSIVE":
            return _result(canonical_common_bytes, canonical_module_state_bytes, "R_ENGINE_CONCLUSIVE", refetch)
        if engine_class != "VALID" or envelope is None:
            return _result(canonical_common_bytes, canonical_module_state_bytes, "R_ENGINE_UNRESOLVED", refetch)
        lineage = _lineage_code(common["comparison_facts"])
        if lineage is not None:
            return _result(canonical_common_bytes, canonical_module_state_bytes, lineage, refetch)
        acceptance, selected = _acceptance(raw)
        code = "R_ACCEPTANCE_" + acceptance
        engine_output = jcs(envelope) + b"\n"
        use_bytes = jcs(raw["use_records"][0])
        evidence = {
            "acceptance_class": acceptance,
            "engine_class": "VALID",
            "engine_output_sha256": hashlib.sha256(engine_output).hexdigest().upper(),
            "lineage_class": "COMPLETE",
            "recorded_use_sha256": hashlib.sha256(use_bytes).hexdigest().upper(),
            "selected_issuance_id": selected,
        }
        return _result(canonical_common_bytes, canonical_module_state_bytes, code, refetch, evidence)
    except BaseException:
        return boundary_exception(ENTRYPOINT, canonical_common_bytes, canonical_module_state_bytes)


decide_r = decide

__all__ = ("decide", "decide_r")
