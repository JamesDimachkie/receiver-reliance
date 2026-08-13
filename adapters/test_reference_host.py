"""Historical regressions for the non-shipping WP1 adapter experiment."""

from __future__ import annotations

import base64
import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from adapters.fixture_extract import PINS, verify as verify_fixtures
from adapters.outcome_receipt import RECEIPT, TABLE, replay
from adapters.preflight import FORMAT_VERSION, canonical_json_bytes, sha256_upper
from adapters.reference_host import (
    EXPERIMENTAL_NON_SHIPPING,
    HOST_OBLIGATION_MAP,
    ProfilePreflightError,
    SQLiteNonceStore,
    ValidatedProfile,
    adapt_record,
    build_engine_request,
    build_transcript_entry,
    effect_receipt_sha256,
    host_effect_binding_sha256,
    preflight_profile,
    reconcile_effect_log,
    validate_transcript_entry,
)

IMPL = REPO / "baseline-run" / "implementation-output-0.3"
if str(IMPL) not in sys.path:
    sys.path.insert(0, str(IMPL))
import pcb_runner

HASH_A = "A" * 64
HASH_B = "B" * 64


def ref_record(**overrides):
    row = {
        "record_id": "REC_REF",
        "family": "REF",
        "state_revision": "7",
        "native": {"referenced_record": "authority.md", "claimed_sha256": HASH_A},
        "observations": {"referenced_record_found": True, "observed_sha256": HASH_A},
    }
    row.update(overrides)
    return row


def scope_record(**overrides):
    row = {
        "record_id": "REC_SCOPE",
        "family": "SCOPE",
        "state_revision": "3",
        "native": {"claimed_paths": ["owned/**"], "result_commit_named": True, "status": "done"},
        "observations": {"commit_found": True, "commit_changed_paths": ["owned/a.txt"]},
    }
    row.update(overrides)
    return row


def supersede_record(**overrides):
    row = {
        "record_id": "REC_SUPER",
        "family": "SUPERSEDE",
        "state_revision": "9",
        "native": {"correction_ordinal": 2},
        "observations": {
            "corrected_version_sha256": HASH_B,
            "corrected_first_added_epoch": 20,
            "doc_first_added_epochs": {"later.md": 21},
            "later_docs_citing_invalidated": ["later.md"],
            "later_docs_citing_any_later_member": [],
        },
    }
    row.update(overrides)
    return row


def lifecycle_record(*, effective_time=10, acknowledgment_time=20, **overrides):
    row = {
        "record_id": "REC_LIFE",
        "family": "LIFECYCLE",
        "state_revision": "2",
        "native": {"status": "done"},
        "observations": {
            "lifecycle_events": [
                {"event_type": "EFFECTIVE", "occurred_at": effective_time, "sequence": 1},
                {"event_type": "ACKNOWLEDGMENT", "occurred_at": acknowledgment_time, "sequence": 2},
            ]
        },
    }
    row.update(overrides)
    return row


def observer_for(record):
    return lambda: copy.deepcopy(record)


def capability_for(record):
    outcome = adapt_record(record)
    if not outcome.ready:
        raise AssertionError(outcome.issues)
    return preflight_profile(record, outcome.profile, observer=observer_for(record))


def preflight_issues(record, profile, **kwargs):
    try:
        preflight_profile(record, profile, **kwargs)
    except ProfilePreflightError as exc:
        return exc.issues
    return ()


def codes(problems):
    return {problem.code for problem in problems}


def engine_exchange(record):
    request, request_raw = build_engine_request(capability_for(record), REPO)
    response, exit_code = pcb_runner._execute(request_raw)
    return request, request_raw, response, canonical_json_bytes(response) + b"\n", exit_code


class DerivationTests(unittest.TestCase):
    def test_all_measured_families_derive_closed_zero_fabrication_profiles(self):
        for record in (ref_record(), scope_record(), supersede_record(), lifecycle_record()):
            with self.subTest(record["family"]):
                outcome = adapt_record(record)
                self.assertTrue(outcome.ready, outcome.issues)
                profile = outcome.profile
                self.assertEqual(profile["format_version"], FORMAT_VERSION)
                self.assertEqual(profile["fabricated_fields"], [])
                self.assertEqual(set(profile["facts"]), set(profile["derivations"]))
                self.assertIsInstance(capability_for(record), ValidatedProfile)

    def test_ref_derives_conflicting_hash_testimony_for_engine(self):
        record = ref_record(observations={"referenced_record_found": True, "observed_sha256": HASH_B})
        versions = adapt_record(record).profile["facts"]["record_versions"]
        self.assertEqual([row["revision_sha256"] for row in versions], [HASH_B, HASH_A])

    def test_scope_glob_reduction_exposes_outside_use(self):
        inside = adapt_record(scope_record()).profile["facts"]
        outside = adapt_record(
            scope_record(observations={"commit_found": True, "commit_changed_paths": ["other/x"]})
        ).profile["facts"]
        self.assertEqual(inside["declared_scope_sha256"], inside["recorded_use_scope_sha256"])
        self.assertNotEqual(outside["declared_scope_sha256"], outside["recorded_use_scope_sha256"])

    def test_supersession_blame_is_temporally_derived(self):
        record = supersede_record(
            observations={
                "corrected_version_sha256": HASH_B,
                "corrected_first_added_epoch": 20,
                "doc_first_added_epochs": {"before": 19, "after": 21, "current": 22},
                "later_docs_citing_invalidated": ["before", "after", "current"],
                "later_docs_citing_any_later_member": ["current"],
            }
        )
        facts = adapt_record(record).profile["facts"]
        self.assertEqual(facts["invalidated_path_ids"], ["after"])

    def test_typed_lifecycle_fields_come_from_explicit_event_types(self):
        facts = adapt_record(lifecycle_record(effective_time=11, acknowledgment_time=29)).profile["facts"]
        self.assertEqual(facts["effective_at"], 11)
        self.assertEqual(facts["acknowledged_at"], 29)
        self.assertEqual(facts["event_sequences"], [1, 2])


class Finding001LifecycleTests(unittest.TestCase):
    def test_untyped_timestamps_refuse_h4_even_with_two_events(self):
        record = lifecycle_record(
            observations={"lifecycle_event_timestamps": [10, 20]}
        )
        outcome = adapt_record(record)
        self.assertFalse(outcome.ready)
        self.assertEqual(codes(outcome.issues), {"H4"})
        self.assertIn("timestamps alone", outcome.issues[0].message)

    def test_terminal_other_event_is_not_acknowledgment(self):
        record = lifecycle_record(
            observations={
                "lifecycle_events": [
                    {"event_type": "EFFECTIVE", "occurred_at": 10, "sequence": 1},
                    {"event_type": "OTHER", "occurred_at": 20, "sequence": 2},
                ]
            }
        )
        self.assertEqual(codes(adapt_record(record).issues), {"H4"})

    def test_duplicate_typed_sequences_refuse_h1(self):
        record = lifecycle_record(
            observations={
                "lifecycle_events": [
                    {"event_type": "EFFECTIVE", "occurred_at": 10, "sequence": 1},
                    {"event_type": "ACKNOWLEDGMENT", "occurred_at": 20, "sequence": 1},
                ]
            }
        )
        self.assertEqual(codes(adapt_record(record).issues), {"H1"})

    def test_ack_timestamp_not_after_effective_refuses_h4(self):
        record = lifecycle_record(effective_time=20, acknowledgment_time=10)
        self.assertEqual(codes(adapt_record(record).issues), {"H4"})

    def test_ack_before_effective_sequence_refuses_h4(self):
        record = lifecycle_record(
            observations={
                "lifecycle_events": [
                    {"event_type": "ACKNOWLEDGMENT", "occurred_at": 20, "sequence": 1},
                    {"event_type": "EFFECTIVE", "occurred_at": 10, "sequence": 2},
                ]
            }
        )
        self.assertEqual(codes(adapt_record(record).issues), {"H4"})

    def test_ack_must_be_terminal_not_followed_by_other(self):
        record = lifecycle_record(
            observations={
                "lifecycle_events": [
                    {"event_type": "EFFECTIVE", "occurred_at": 10, "sequence": 1},
                    {"event_type": "ACKNOWLEDGMENT", "occurred_at": 20, "sequence": 2},
                    {"event_type": "OTHER", "occurred_at": 30, "sequence": 3},
                ]
            }
        )
        self.assertEqual(codes(adapt_record(record).issues), {"H4"})

    def test_terminal_predecessor_is_observed_immediate_event(self):
        record = lifecycle_record(
            observations={
                "lifecycle_events": [
                    {"event_type": "EFFECTIVE", "occurred_at": 10, "sequence": 1},
                    {"event_type": "OTHER", "occurred_at": 15, "sequence": 2},
                    {"event_type": "ACKNOWLEDGMENT", "occurred_at": 20, "sequence": 3},
                ]
            }
        )
        facts = adapt_record(record).profile["facts"]
        self.assertEqual(facts["terminal_predecessor_sequences"], [2])

    def test_intermediate_timestamp_contradiction_refuses_h4(self):
        record = lifecycle_record(
            observations={
                "lifecycle_events": [
                    {"event_type": "EFFECTIVE", "occurred_at": 10, "sequence": 1},
                    {"event_type": "OTHER", "occurred_at": 5, "sequence": 2},
                    {"event_type": "ACKNOWLEDGMENT", "occurred_at": 20, "sequence": 3},
                ]
            }
        )
        self.assertEqual(codes(adapt_record(record).issues), {"H4"})


class Finding002FreshnessAndAliasTests(unittest.TestCase):
    def test_conflicting_ref_aliases_refuse_h1(self):
        record = ref_record(
            native={
                "claimed_path": "archive/authority.md",
                "referenced_record": "authority.md",
                "claimed_sha256": HASH_A,
            }
        )
        self.assertEqual(codes(adapt_record(record).issues), {"H1"})

    def test_equal_ref_aliases_are_accepted(self):
        record = ref_record(
            native={
                "claimed_path": "authority.md",
                "referenced_record": "authority.md",
                "claimed_sha256": HASH_A,
            }
        )
        self.assertTrue(adapt_record(record).ready)

    def test_preflight_requires_freshness_proof(self):
        record = ref_record()
        profile = adapt_record(record).profile
        self.assertEqual(codes(preflight_issues(record, profile)), {"H1"})

    def test_observer_detects_mutation_before_preflight(self):
        record = ref_record()
        changed = copy.deepcopy(record)
        changed["observations"]["observed_sha256"] = HASH_B
        profile = adapt_record(record).profile
        self.assertEqual(codes(preflight_issues(record, profile, observer=lambda: changed)), {"H1"})

    def test_observer_detects_mutation_after_preflight_at_build(self):
        record = ref_record()
        current = copy.deepcopy(record)
        profile = adapt_record(record).profile
        capability = preflight_profile(record, profile, observer=lambda: copy.deepcopy(current))
        current["state_revision"] = "8"
        with self.assertRaises(ProfilePreflightError) as caught:
            build_engine_request(capability, REPO)
        self.assertEqual(codes(caught.exception.issues), {"H1"})

    def test_revision_only_path_is_removed(self):
        record = ref_record()
        profile = adapt_record(record).profile
        with self.assertRaises(TypeError):
            preflight_profile(record, profile, verified_state_revision="7")


class Finding003CapabilityTests(unittest.TestCase):
    def test_plain_profile_mapping_cannot_build(self):
        profile = adapt_record(ref_record()).profile
        with self.assertRaisesRegex(TypeError, "ValidatedProfile"):
            build_engine_request(profile, REPO)

    def test_capability_constructor_rejects_forgery(self):
        with self.assertRaises(TypeError):
            ValidatedProfile({}, "x", None, None, None)
        forged = ValidatedProfile()
        with self.assertRaisesRegex(TypeError, "ValidatedProfile"):
            build_engine_request(forged, REPO)

    def test_tampered_fact_or_derivation_cannot_mint_capability(self):
        record = scope_record()
        for field in ("facts", "derivations", "calibration"):
            profile = copy.deepcopy(adapt_record(record).profile)
            if field == "facts":
                profile[field]["recorded_use_scope_sha256"] = HASH_A
                expected_code = "H3"
            elif field == "derivations":
                profile[field]["recorded_use_scope_sha256"] = "asserted"
                expected_code = "H3"
            else:
                profile[field]["native_precondition"] = "anything"
                expected_code = "H4"
            self.assertIn(expected_code, codes(preflight_issues(record, profile, observer=observer_for(record))))

    def test_mutating_detached_profile_copy_cannot_change_built_facts(self):
        record = ref_record()
        capability = capability_for(record)
        detached = capability._profile
        detached["facts"]["record_versions"] = [
            {"record_id": "LATEST", "revision_sha256": HASH_B}
        ]
        request, _raw = build_engine_request(capability, REPO)
        self.assertEqual(
            request["decision_input"]["facts"], adapt_record(record).profile["facts"]
        )
        self.assertNotIn("LATEST", json.dumps(request))

    def test_mutating_sealed_profile_bytes_fails_h3(self):
        capability = capability_for(ref_record())
        object.__setattr__(capability, "_profile_raw", b"{}")
        with self.assertRaises(ProfilePreflightError) as caught:
            build_engine_request(capability, REPO)
        self.assertEqual(codes(caught.exception.issues), {"H3"})

    def test_mutating_all_capability_fields_cannot_replace_registry_seal(self):
        capability = capability_for(ref_record())
        forged_profile = capability._profile
        forged_profile["facts"]["record_versions"] = [
            {"record_id": "LATEST", "revision_sha256": HASH_B}
        ]
        forged_raw = canonical_json_bytes(forged_profile)
        object.__setattr__(capability, "_profile_raw", forged_raw)
        object.__setattr__(capability, "_profile_sha256", sha256_upper(forged_raw))
        with self.assertRaises(ProfilePreflightError) as caught:
            build_engine_request(capability, REPO)
        self.assertEqual(codes(caught.exception.issues), {"H3"})


class Finding004TranscriptTests(unittest.TestCase):
    def test_exact_core_transcript_validates_by_reexecution(self):
        request, request_raw, _response, response_raw, exit_code = engine_exchange(ref_record())
        entry = build_transcript_entry(request_raw, response_raw, exit_code, REPO)
        self.assertEqual(entry["format_version"], "RR-HOST-CORE-TRANSCRIPT-2")
        self.assertEqual(entry["request_id"], request["request_id"])
        self.assertEqual(validate_transcript_entry(entry, REPO), ())

    def test_wrong_format_literal_fails_h5(self):
        _request, request_raw, _response, response_raw, exit_code = engine_exchange(ref_record())
        entry = build_transcript_entry(request_raw, response_raw, exit_code, REPO)
        entry["format_version"] = "RR-HOST-CORE-TRANSCRIPT-1"
        self.assertIn("H5", codes(validate_transcript_entry(entry, REPO)))

    def test_mixed_request_response_ids_fail_h5(self):
        _request, request_raw, response, _response_raw, exit_code = engine_exchange(ref_record())
        response["request_id"] = "RUN_" + "F" * 24
        response_raw = canonical_json_bytes(response) + b"\n"
        entry = {
            "format_version": "RR-HOST-CORE-TRANSCRIPT-2",
            "request_id": json.loads(request_raw)["request_id"],
            "request_raw_base64": base64.b64encode(request_raw).decode("ascii"),
            "request_raw_sha256": sha256_upper(request_raw),
            "decision_input": json.loads(request_raw)["decision_input"],
            "decision_input_sha256": sha256_upper(canonical_json_bytes(json.loads(request_raw)["decision_input"])),
            "response_raw_base64": base64.b64encode(response_raw).decode("ascii"),
            "response_raw_sha256": sha256_upper(response_raw),
            "engine_exit_code": exit_code,
        }
        problems = validate_transcript_entry(entry, REPO)
        self.assertIn("H5", codes(problems))
        self.assertTrue(any("correlate" in problem.message for problem in problems))

    def test_semantically_forged_response_fails_exact_reexecution(self):
        _request, request_raw, response, _response_raw, exit_code = engine_exchange(ref_record())
        response["output"]["result_object"]["behavior_class"] = "MALFORMED_OR_BOUNDARY"
        forged_raw = canonical_json_bytes(response) + b"\n"
        with self.assertRaises(ProfilePreflightError):
            build_transcript_entry(request_raw, forged_raw, exit_code, REPO)

    def test_non_json_response_fails_h5(self):
        _request, request_raw, _response, _response_raw, exit_code = engine_exchange(ref_record())
        with self.assertRaises(ProfilePreflightError):
            build_transcript_entry(request_raw, b"not-json\n", exit_code, REPO)


class Finding008TranscriptTotalityTests(unittest.TestCase):
    def valid_entry(self):
        _request, request_raw, _response, response_raw, exit_code = engine_exchange(ref_record())
        return build_transcript_entry(request_raw, response_raw, exit_code, REPO)

    def test_nan_and_infinity_wire_values_return_h5_issues(self):
        for prefix in ("request", "response"):
            for constant in (b"NaN", b"Infinity", b"-Infinity"):
                with self.subTest(prefix=prefix, constant=constant):
                    entry = self.valid_entry()
                    raw = b'{"value":' + constant + b"}\n"
                    entry[f"{prefix}_raw_base64"] = base64.b64encode(raw).decode("ascii")
                    entry[f"{prefix}_raw_sha256"] = sha256_upper(raw)
                    problems = validate_transcript_entry(entry, REPO)
                    self.assertIn("H5", codes(problems))

    def test_nonfinite_retained_decision_input_returns_h5_issue(self):
        entry = self.valid_entry()
        entry["decision_input"] = {"facts": {"bad": float("nan")}}
        problems = validate_transcript_entry(entry, REPO)
        self.assertIn("H5", codes(problems))

    def test_reexecution_exception_is_totalized_to_h5_issue(self):
        entry = self.valid_entry()
        with mock.patch(
            "adapters.reference_host._execute_core_request",
            side_effect=RuntimeError("adversarial engine failure"),
        ):
            problems = validate_transcript_entry(entry, REPO)
        self.assertIn("H5", codes(problems))
        self.assertTrue(any("failed deterministically" in problem.message for problem in problems))

    def test_cached_runner_module_substitution_cannot_spoof_reexecution(self):
        entry = self.valid_entry()
        fake = mock.Mock()
        fake._execute.return_value = ({"forged": True}, 0)
        with mock.patch.dict(sys.modules, {"pcb_runner": fake}):
            problems = validate_transcript_entry(entry, REPO)
        self.assertEqual(problems, ())
        fake._execute.assert_not_called()


def effect_expectation(effect_id, digest):
    preimage = {
        "operation_handle": "OPR_6D9FA44D4442950313EA8047",
        "obligation_id": "OBL-19",
        "request_id": "RUN_" + effect_id[-1] * 24,
        "decision_input": {"facts": {"effect_id": effect_id}},
        "operation_fields_object": {
            "receipt_event_sequence": 1,
            "evidence_evaluation_sha256": HASH_A,
            "authorization_sha256": HASH_A,
            "gate_decision_sha256": HASH_A,
            "workflow_state_sha256": HASH_A,
            "invocation_sha256": HASH_A,
            "observed_effect_sha256": digest,
        },
    }
    engine_receipt = effect_receipt_sha256(**preimage)
    return {
        "effect_sha256": digest,
        "effect_receipt_sha256": engine_receipt,
        "host_effect_binding_sha256": host_effect_binding_sha256(
            effect_id=effect_id,
            effect_sha256=digest,
            engine_effect_receipt_sha256=engine_receipt,
            preimage=preimage,
        ),
        "preimage": preimage,
    }


class Finding005EffectTests(unittest.TestCase):
    def setUp(self):
        self.expected_ids = ["EFFECT_A", "EFFECT_B"]
        self.log = [
            {"effect_id": "EFFECT_B", "effect_sha256": HASH_B},
            {"effect_id": "EFFECT_A", "effect_sha256": HASH_A},
        ]
        self.expectations = {
            "EFFECT_A": effect_expectation("EFFECT_A", HASH_A),
            "EFFECT_B": effect_expectation("EFFECT_B", HASH_B),
        }

    def test_complete_log_normalizes_and_passes(self):
        result = reconcile_effect_log(
            expected_effect_ids=self.expected_ids,
            observed_effect_log=self.log,
            expectations=self.expectations,
        )
        self.assertTrue(result.ok, result.issues)
        self.assertEqual(result.normalized_observed_log[0][0], "EFFECT_A")

    def test_subset_log_fails_cardinality(self):
        result = reconcile_effect_log(
            expected_effect_ids=self.expected_ids,
            observed_effect_log=self.log[:1],
            expectations=self.expectations,
        )
        self.assertFalse(result.ok)

    def test_duplicate_log_fails(self):
        duplicate = [self.log[0], copy.deepcopy(self.log[0])]
        self.assertFalse(
            reconcile_effect_log(
                expected_effect_ids=self.expected_ids,
                observed_effect_log=duplicate,
                expectations=self.expectations,
            ).ok
        )

    def test_digest_mismatch_and_receipt_mismatch_fail(self):
        changed_log = copy.deepcopy(self.log)
        changed_log[0]["effect_sha256"] = HASH_A
        self.assertFalse(
            reconcile_effect_log(
                expected_effect_ids=self.expected_ids,
                observed_effect_log=changed_log,
                expectations=self.expectations,
            ).ok
        )
        changed_expectations = copy.deepcopy(self.expectations)
        changed_expectations["EFFECT_A"]["effect_receipt_sha256"] = HASH_B
        self.assertFalse(
            reconcile_effect_log(
                expected_effect_ids=self.expected_ids,
                observed_effect_log=self.log,
                expectations=changed_expectations,
            ).ok
        )

    def test_missing_binding_field_fails_closed_shape(self):
        changed_expectations = copy.deepcopy(self.expectations)
        del changed_expectations["EFFECT_A"]["host_effect_binding_sha256"]
        result = reconcile_effect_log(
            expected_effect_ids=self.expected_ids,
            observed_effect_log=self.log,
            expectations=changed_expectations,
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("wrong closed shape" in issue.message for issue in result.issues))

    def test_copying_same_digest_evidence_to_another_effect_id_fails(self):
        same_digest_log = [
            {"effect_id": "EFFECT_A", "effect_sha256": HASH_A},
            {"effect_id": "EFFECT_B", "effect_sha256": HASH_A},
        ]
        expectations = {
            "EFFECT_A": effect_expectation("EFFECT_A", HASH_A),
            "EFFECT_B": effect_expectation("EFFECT_B", HASH_A),
        }
        expectations["EFFECT_B"] = copy.deepcopy(expectations["EFFECT_A"])
        result = reconcile_effect_log(
            expected_effect_ids=self.expected_ids,
            observed_effect_log=same_digest_log,
            expectations=expectations,
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("exact host effect ID" in issue.message for issue in result.issues))


class OperationalTests(unittest.TestCase):
    def test_concurrent_replay_admits_exactly_one(self):
        with tempfile.TemporaryDirectory(prefix="rr-wp1-") as tmp:
            store = SQLiteNonceStore(pathlib.Path(tmp) / "nonces.sqlite3")
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(store.consume_once, ["NONCE_A", "NONCE_A"]))
            self.assertEqual(sum(result.admitted_to_engine for result in outcomes), 1)

    def test_general_h1_h6_experiment_is_not_the_public_fallback(self):
        docs = (HERE / "README.md").read_text(encoding="utf-8")
        self.assertEqual(set(HOST_OBLIGATION_MAP), {f"H{i}" for i in range(1, 7)})
        self.assertTrue(EXPERIMENTAL_NON_SHIPPING)
        self.assertNotIn("build_transcript_entry", docs)
        self.assertNotIn("reconcile_effect_log", docs)
        self.assertNotIn("SQLiteNonceStore", docs)


class Finding006OutcomeTests(unittest.TestCase):
    def test_fixture_extraction_is_row_bound_to_all_408_parent_rows(self):
        result = verify_fixtures()
        self.assertEqual(result["parent_rows"], 408)
        self.assertEqual(result["e7_rows"], 211)
        self.assertEqual(result["pins"], PINS)

    def test_current_and_historical_results_are_not_conflated(self):
        receipt, receipt_raw, table_raw = replay()
        self.assertEqual(RECEIPT.read_bytes(), receipt_raw)
        self.assertEqual(TABLE.read_bytes(), table_raw)
        self.assertEqual(receipt["historical_forced_reexecution"]["detection"], "18/18")
        current = receipt["portable_fallback_reexecution"]
        self.assertEqual(current["detection"], "18/18")
        self.assertEqual(current["counts"]["ready_clean_false_hold"], 0)
        self.assertEqual(current["counts"]["insufficient_evidence_clean"], 208)
        self.assertEqual(current["counts"]["rejected_invalid_defect_detected"], 8)
        self.assertFalse(current["insufficient_evidence_counted_as_pass"])
        self.assertFalse(current["rejected_invalid_counted_as_pass"])
        assessment = receipt["charter_assessment"]
        self.assertEqual(
            assessment["delivery_mode"], "FALLBACK_CALIBRATION_PLUS_PORTABLE_PREFLIGHT"
        )
        self.assertEqual(assessment["required_current_detection"], "18/18")
        self.assertEqual(assessment["measured_current_detection"], "18/18")
        self.assertTrue(assessment["outcome_bar_met"])
        self.assertTrue(assessment["package_complete"])

    def test_receipt_self_seal(self):
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        claimed = receipt["receipt_sha256"]
        receipt["receipt_sha256"] = "0" * 64
        self.assertEqual(claimed, sha256_upper(canonical_json_bytes(receipt)))


class Finding007RuntimeEvidenceTests(unittest.TestCase):
    def test_313_evidence_recorded_and_bar_met(self):
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        evidence = receipt["runtime_evidence"]
        self.assertNotIn("PENDING", evidence["cpython_3_13"])
        self.assertIn("local suite evidence", evidence["cpython_3_13"])
        self.assertTrue(evidence["evidence_bar_met"])
        inspection = evidence["hosted_evidence_inspection"]
        self.assertFalse(inspection["current_wp1_command_present"])
        self.assertFalse(inspection["current_portable_preflight_sha_present"])


class Finding009FallbackBoundaryTests(unittest.TestCase):
    def test_mutable_runner_and_general_adapter_are_not_claimable(self):
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        boundary = receipt["measurement_boundary"]
        self.assertEqual(boundary["mutable_runner_status"], "NON_SHIPPING_MEASUREMENT_ONLY")
        self.assertFalse(boundary["exported_from_adapters"])
        self.assertFalse(boundary["claimable_as_fallback_capability"])


class ScopeDigestAgreementTests(unittest.TestCase):
    """The measurement arm and the shipping preflight derive one digest law.

    F-WP1-013: both surfaces digest the canonical JSON array of the sorted
    path set (injective), never a newline join.  The historical join survives
    only in the sealed ``proof/arm_b1.py`` receipts.
    """

    def test_scope_digest_matches_portable_and_is_injective(self):
        from adapters.portable_preflight import _scope_hash as portable_hash
        from adapters.reference_host import _scope_hash as host_hash

        for items in ([], ["a"], ["a", "b"], ["a\nb"], ["src/**", "docs/x.md"]):
            with self.subTest(items=items):
                self.assertEqual(portable_hash(items), host_hash(items))
        self.assertNotEqual(host_hash(["a\nb"]), host_hash(["a", "b"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
