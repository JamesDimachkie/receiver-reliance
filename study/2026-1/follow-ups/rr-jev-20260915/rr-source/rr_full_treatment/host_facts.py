"""Candidate evidence assembly from explicit capture/use/history observations.

No historical K0/K1 acceptance data, answer key, condition label or arm enters
this module. It does not decide whether an artifact may be released. Host
observations remain trusted inputs until the separate host path is qualified.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import re


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def identity(kind: str, value) -> str:
    return kind + "_" + sha(canonical(value))


@dataclass(frozen=True)
class CapturedArtifact:
    content: bytes
    artifact_id: str
    revision: int
    sender_envelope_sha256: str
    requested_artifact_id: str
    requested_revision: int
    observed_parent_refs: tuple[str, ...]
    observed_generation: int
    observed_receiver: str
    observed_purpose: str
    observed_scope: tuple[str, ...]
    observed_action_class: str


@dataclass(frozen=True)
class UseContext:
    episode_id: str
    receiver: str
    sender: str
    purpose: str
    scope: str
    policy: str
    expected_parent_refs: tuple[str, ...]
    generation: int
    route: str
    slot: str
    carrier: str
    owner: str
    principal: str
    authority: str
    action_class: str
    observed_at: str
    use_at: str
    valid_from: str
    valid_until: str
    use_ns: int
    valid_from_ns: int
    valid_until_ns: int
    fence: int
    decision_ref: str
    context_ref: str
    nonce: str


def envelope(artifact: CapturedArtifact) -> dict:
    if type(artifact.content) is not bytes or type(artifact.revision) is not int:
        raise ValueError("Capture must preserve bytes and an integer revision")
    return {"format": "RR-SCIENTIFIC-CLOSED-ARTIFACT-1",
            "artifact_id": artifact.artifact_id, "revision": artifact.revision,
            "media_type": "application/json",
            "content_b64": base64.b64encode(artifact.content).decode("ascii")}


def subject(artifact: CapturedArtifact) -> str:
    return "CLAIM_" + sha(canonical(envelope(artifact)))


def assemble(artifact: CapturedArtifact, use: UseContext, *, task: dict,
             source_content: bytes, mandates: list[dict], declarations: list[dict],
             included_refs: list[str], declared_basis_refs: list[str],
             guard_observation: dict, closure: dict, transport: dict,
             refetch_budget: int, attempt_ordinal: int) -> bytes:
    """Build the exact COMMON wire document from a receiver observation.

    The caller must supply actual ledger history and separately captured grant
    observations. No declaration is manufactured merely because content exists.
    closure describes the host's finite-history census, not semantic truth.
    transport describes observed route/slot/carrier/fence and revocation state.
    Source content is provenance only; no support assessment is inferred from it.
    """
    for ref in use.expected_parent_refs:
        if not re.fullmatch(r"PARENT_[0-9A-F]{64}", ref):
            raise ValueError("Expected parents require full observed byte identities")
    env = envelope(artifact)
    exact_claim = subject(artifact)
    use_id = identity("USE", [use.episode_id, use.receiver, use.context_ref, exact_claim, use.use_at])
    ledger_id = identity("LEDGER", [use.episode_id, use.receiver, use.context_ref])
    source_id = "SOURCE_" + sha(source_content)
    interval = {"effective_from": use.valid_from, "effective_until": use.valid_until}
    use_record = {
        "use_id": use_id, "action_or_decision_ref": use.decision_ref,
        "decision_context_ref": use.context_ref, "declared_basis_refs": list(declared_basis_refs),
        "episode_id": use.episode_id, "exact_claim_version_id": exact_claim,
        "occurred_at": use.use_at, "purpose_id": use.purpose,
        "receiver_capability_id": use.receiver, "scope_id": use.scope,
    }
    # A pre-use snapshot contains only the caller's actual recorded frontier.
    # The later reliance-request record is supplied to the query separately;
    # the serializer must not retroactively insert it into that snapshot.
    all_refs = list(included_refs)
    raw = {
        "format_version": "EH-G0-A2-SHARED-0.1",
        "bundle_id": identity("BUNDLE", [use_id, sha(artifact.content)]),
        "domain_vocabulary": {
            "vocabulary_id": "RR_LOCAL_WORKFLOW_VOCAB", "vocabulary_version": "1.0",
            "domain_id": "RR_LOCAL_CONSTRUCTED_WORKFLOW",
            "canonicalization_method_ref": "EH_CANONICAL_JSON_0_1",
            "selector_language_id": "EH-SELECTOR-CORE-0_1",
            "purpose_entries": [{"id": use.purpose, "description": "Registered receiver operation"}],
            "scope_entries": [{"id": use.scope, "description": "Registered constructed task scope"}],
        },
        "episodes": [{"cross_party_episode_id": use.episode_id,
            "domain_vocabulary_ref": "RR_LOCAL_WORKFLOW_VOCAB", "episode_family_id": "RR_LOCAL_WORKFLOW",
            "interval": interval, "purpose_id": use.purpose, "scope_id": use.scope,
            "receiver_capability_id": use.receiver, "receiver_role_id": "ROLE_RECEIVER",
            "sender_capability_id": use.sender, "sender_role_id": "ROLE_SENDER"}],
        "capabilities": [{"capability_id": actor, "episode_id": use.episode_id,
                          "role_id": "ROLE_REGISTERED_ACTOR"}
                         for actor in sorted({use.sender, use.receiver,
                             *(m["subject_capability_id"] for m in mandates)})],
        "claim_versions": [{"claim_id": exact_claim, "exact_claim_version_id": exact_claim,
            "payload": artifact.content.decode("utf-8", errors="strict"),
            "source_record_refs": [source_id], "version": artifact.revision}],
        "source_records": [{"source_record_id": source_id, "source_kind": "DOCUMENT",
            "observed_at": use.observed_at, "payload": source_content.decode("utf-8", errors="strict")}],
        "recorded_support_assessments": [],
        "recorded_action_grants": [],
        "domain_mandate_records": mandates,
        "declaration_records": declarations,
        "use_records": [use_record],
        "ledger_observations": [{"action_or_decision_ref": use.decision_ref,
            "captured_at": use.observed_at, "committed_frontier": len(all_refs),
            "decision_context_ref": use.context_ref, "included_record_refs": all_refs,
            "ledger_id": ledger_id, "nonce": use.nonce}],
        "closure_attestations": [{"closed_record_classes": closure["record_classes"],
            "closed_through": closure["through"], "source_extent": closure["source_extent"],
            "closure_attestation_id": identity("CLOSURE", [ledger_id, len(all_refs), closure]),
            "committed_frontier": len(all_refs), "ledger_id": ledger_id,
            "verification_method_ref": "REGISTERED_FINITE_HISTORY_CENSUS"}],
        "observable_external_facts": [],
    }
    facts = {
        "carrier_fence": transport["carrier_fence"], "current_fence": use.fence,
        "expected_receiver_capability": use.receiver,
        "observed_receiver_capability": artifact.observed_receiver,
        "expected_direct_parents": list(use.expected_parent_refs),
        "observed_direct_parents": list(artifact.observed_parent_refs),
        "expected_generation": use.generation, "observed_generation": artifact.observed_generation,
        "expected_purpose": use.purpose, "observed_purpose": artifact.observed_purpose,
        "expected_scope": [use.scope], "observed_scope": list(artifact.observed_scope),
        "expected_action_class": use.action_class, "observed_action_class": artifact.observed_action_class,
        "expected_representation_sha256": artifact.sender_envelope_sha256,
        "consumed_representation_sha256": sha(canonical(env)),
        "origin_finalized": transport["origin_finalized"],
        "revocation_active": transport["revocation_active"],
        "use_time_ns": use.use_ns, "valid_from_ns": use.valid_from_ns,
        "valid_until_ns": use.valid_until_ns,
    }
    for name in ("route", "slot", "carrier", "owner", "principal", "authority"):
        facts["expected_" + name] = getattr(use, name)
        facts["observed_" + name] = transport[name]
    common = {
        "format": "RR-STUDY-TREATMENT-COMMON-5", "a2_raw_shared_bundle": raw,
        "comparison_facts": facts, "delivered_artifact_envelope": env,
        "guard_observation_facts": guard_observation,
        "remediation": {"attempt_ordinal": attempt_ordinal, "refetch_budget": refetch_budget},
        "requested_delivered_transfer": {"declared_sha256": artifact.sender_envelope_sha256,
            "delivered_artifact_id": artifact.artifact_id, "delivered_revision": artifact.revision,
            "requested_artifact_id": artifact.requested_artifact_id,
            "requested_revision": artifact.requested_revision},
        "source_lineage_observation": {"format": "RR-SCIENTIFIC-CLOSED-LINEAGE-OBSERVATION-1",
            "source_artifact_id": source_id, "source_revision": 0, "source_sha256": sha(source_content)},
        "task_id": identity("TASK", task),
        "task_instruction_constraints": {"instruction": task["instruction"], "constraints": task["constraints"]},
    }
    return canonical(common)
