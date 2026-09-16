"""Benign assembly controls; no model or host qualification is claimed."""
from dataclasses import replace
import json
import unittest

from .host_facts import CapturedArtifact, UseContext, assemble, canonical, envelope, sha, subject


def control(*, delegated=False, answer=7, receiver="CAP_R1", episode="EP_CONTROL"):
    receiver = "CAP_" + sha(receiver.encode())[:24]
    source_actor = "CAP_" + sha(b"source")[:24]
    delegate_actor = "CAP_" + sha(b"delegate")[:24]
    issuer_mandate = "STANDING_" + sha(b"issuer-mandate")[:24]
    root_mandate = "STANDING_" + sha(b"root-mandate")[:24]
    content = canonical({"answer": answer, "source": "synthetic-control"})
    artifact = CapturedArtifact(content, "ART_CONTROL", 1, "", "ART_CONTROL", 1,
        ("PARENT_" + "A" * 64,), 1, receiver, "PURPOSE_SUM", ("SCOPE_TASK",), "PERMIT")
    artifact = replace(artifact, sender_envelope_sha256=sha(canonical(envelope(artifact))))
    use = UseContext(episode, receiver, source_actor, "PURPOSE_SUM", "SCOPE_TASK", "POLICY_SHARED_0_1",
        ("PARENT_" + "A" * 64,), 1, "ROUTE_CONTROL", "SLOT_CONTROL", "CARRIER_CONTROL",
        "OWNER_LOCAL", source_actor, "AUTH_LOCAL", "PERMIT",
        "2026-09-05T12:00:00Z", "2026-09-05T12:00:01Z",
        "2026-09-05T11:00:00Z", "2026-09-05T13:00:00Z", 1001, 0, 10000, 1,
        "ACTION_" + sha(b"control-action")[:24], "CONTEXT_CONTROL", "NONCE_CONTROL")
    interval = {"effective_from": use.valid_from, "effective_until": use.valid_until}
    issuer = delegate_actor if delegated else source_actor
    mandate = {"mandate_version_ref": issuer_mandate, "subject_capability_id": issuer,
        "permitted_record_kinds": ["ADOPTION_DECLARED"], "purpose_ids": [use.purpose],
        "scope_ids": [use.scope], "policy_ref": use.policy, "interval": interval}
    declaration = {"declaration_kind": "ADOPTION_DECLARED", "declaration_version_ref": "DECL_USE",
        "episode_id": episode, "exact_claim_version_id": subject(artifact),
        "interval": interval, "issuer_capability_id": issuer, "mandate_version_ref": issuer_mandate,
        "policy_ref": use.policy, "purpose_id": use.purpose, "scope_id": use.scope,
        "receiver_capability_id": receiver, "recorded_at": use.observed_at,
        "standing_basis_ref": "DECL_GRANT" if delegated else issuer_mandate}
    mandates, declarations = [mandate], [declaration]
    if delegated:
        mandates.append({**mandate, "mandate_version_ref": root_mandate,
            "subject_capability_id": source_actor, "permitted_record_kinds": ["DELEGATION_DECLARED"]})
        declarations.insert(0, {**declaration, "declaration_kind": "DELEGATION_DECLARED",
            "declaration_version_ref": "DECL_GRANT", "issuer_capability_id": source_actor,
            "mandate_version_ref": root_mandate, "standing_basis_ref": root_mandate,
            "delegate_capability_id": delegate_actor, "grant_id": "GRANT_CONTROL"})
    inputs = {
        "task": {"instruction": "Add the two supplied synthetic integers.", "constraints": []},
        "source_content": canonical({"numbers": [3, 4]}), "mandates": mandates,
        "declarations": declarations,
        "included_refs": [row["declaration_version_ref"] for row in declarations],
        "declared_basis_refs": ["DECL_USE"],
        "guard_observation": {"consumption_state": "UNUSED", "effect_receipt_count": 1,
            "effect_sha256": sha(content), "execution_receipt_effect_sha256": sha(content),
            "grant_expires_at": 2000, "grant_not_before": 0, "invocation_nonce": "NONCE_INGRESS",
            "invocation_time": 1000, "prior_invocation_nonces": [],
            "revocation_checked_at": 1000, "revoked_at": None},
        "closure": {"record_classes": ["CLAIM_VERSION", "DECLARATION_RECORD", "MANDATE_RECORD", "USE_RECORD"],
            "through": use.use_at, "source_extent": ["SOURCE_MANDATE", "SOURCE_PRIMARY"]},
        "transport": {"carrier_fence": 1, "origin_finalized": True, "revocation_active": False,
            **{name: getattr(use, name) for name in ("route", "slot", "carrier", "owner", "principal", "authority")}},
        "refetch_budget": 1, "attempt_ordinal": 0,
    }
    return artifact, use, inputs


class HostAssemblyChecks(unittest.TestCase):
    def test_actual_content_receiver_and_use_replace_template_identities(self):
        documents = []
        for answer, receiver, episode in ((7, "CAP_R1", "EP_1"), (9, "CAP_R2", "EP_1"), (7, "CAP_R1", "EP_2")):
            artifact, use, inputs = control(answer=answer, receiver=receiver, episode=episode)
            document = json.loads(assemble(artifact, use, **inputs))
            documents.append(document)
            raw = document["a2_raw_shared_bundle"]
            self.assertEqual(raw["claim_versions"][0]["payload"].encode(), artifact.content)
            self.assertEqual(raw["use_records"][0]["receiver_capability_id"], use.receiver)
            self.assertEqual(raw["declaration_records"][0]["exact_claim_version_id"], subject(artifact))
            self.assertEqual(raw["recorded_support_assessments"], [])
        self.assertEqual(len({sha(canonical(d["a2_raw_shared_bundle"]["use_records"][0])) for d in documents}), 3)
        self.assertNotEqual(documents[0]["a2_raw_shared_bundle"]["claim_versions"], documents[1]["a2_raw_shared_bundle"]["claim_versions"])

    def test_absent_declaration_is_not_created_by_assembly(self):
        artifact, use, inputs = control()
        inputs.update(declarations=[], included_refs=[], declared_basis_refs=[])
        raw = json.loads(assemble(artifact, use, **inputs))["a2_raw_shared_bundle"]
        self.assertEqual(raw["declaration_records"], [])
        self.assertEqual(raw["use_records"][0]["declared_basis_refs"], [])

    def test_sender_digest_is_preserved_instead_of_repaired(self):
        artifact, use, inputs = control()
        artifact = replace(artifact, sender_envelope_sha256="B" * 64)
        common = json.loads(assemble(artifact, use, **inputs))
        self.assertEqual(common["requested_delivered_transfer"]["declared_sha256"], "B" * 64)
        self.assertNotEqual(common["comparison_facts"]["consumed_representation_sha256"], "B" * 64)

    def test_no_implicit_coercion_of_generation_or_observed_parent(self):
        artifact, use, inputs = control()
        artifact = replace(artifact, observed_generation="unobserved", observed_parent_refs=("unobserved",))
        common = json.loads(assemble(artifact, use, **inputs))
        self.assertEqual(common["comparison_facts"]["observed_generation"], "unobserved")
        self.assertEqual(common["comparison_facts"]["observed_direct_parents"], ["unobserved"])


if __name__ == "__main__":
    unittest.main()
