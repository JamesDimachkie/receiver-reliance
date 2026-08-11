"""Focused regressions for the concurrency harness's two proof layers."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from portability.concurrency import ladder  # noqa: E402
from portability.oracle import FixtureOracle, jcs_bytes  # noqa: E402


class ComparatorSeparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.oracle = FixtureOracle()
        cls.raw = b"\n"
        cls.physical = ladder._isolated_physical_record(cls.raw, {})

    def test_isolated_physical_comparator_is_cached_and_never_calls_oracle(self) -> None:
        original_run = subprocess.run
        cache: dict[bytes, bytes] = {}
        with (
            mock.patch.object(ladder.subprocess, "run", side_effect=original_run) as run,
            mock.patch.object(
                FixtureOracle,
                "expected_record",
                side_effect=AssertionError("semantic oracle entered physical comparator"),
            ),
        ):
            first = ladder._isolated_physical_record(self.raw, cache)
            second = ladder._isolated_physical_record(self.raw, cache)
        self.assertEqual(first, second)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(json.loads(first)["format_version"], ladder.AUDITED_FORMAT_VERSION)

    def test_physical_stream_mismatch_is_not_misreported_as_semantic(self) -> None:
        inputs = {0: [self.raw]}
        with self.assertRaises(ladder.InvariantFailure) as raised:
            ladder._assert_physical_outputs(
                "library", inputs, {0: self.physical}, {0: self.physical[:-2] + b"X\n"}
            )
        self.assertEqual(raised.exception.divergence["kind"], "physical_transport_mismatch")
        self.assertIn("never semantic", raised.exception.divergence["semantic_nonclaim"])

    def test_physical_cache_binding_binds_both_request_and_output(self) -> None:
        baseline = ladder._physical_cache_binding_sha256({self.raw: self.physical})
        self.assertNotEqual(
            baseline,
            ladder._physical_cache_binding_sha256({b"{}\n": self.physical}),
        )
        self.assertNotEqual(
            baseline,
            ladder._physical_cache_binding_sha256({self.raw: self.physical + b"x"}),
        )

    def test_framed_digest_binds_caller_boundaries(self) -> None:
        self.assertNotEqual(
            ladder._framed_outputs_sha256({0: b"a", 1: b"bc"}),
            ladder._framed_outputs_sha256({0: b"ab", 1: b"c"}),
        )


class IndependentSemanticAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.oracle = FixtureOracle()
        cls.raw = b"\n"
        cls.physical = ladder._isolated_physical_record(cls.raw, {})

    def _object(self) -> dict[str, object]:
        return json.loads(self.physical)

    def test_real_audited_envelope_projects_to_exact_oracle_bytes(self) -> None:
        projected = ladder._audit_semantic_record(self.raw, self.physical, self.oracle)
        self.assertEqual(projected, self.oracle.expected_record(self.raw))

    def test_corrupted_sealed_response_fails_semantic_oracle(self) -> None:
        value = self._object()
        value["sealed_response"]["request_id"] = "RUN_000000000000000000000001"
        zeroed = dict(value)
        zeroed["audit_sha256"] = "0" * 64
        value["audit_sha256"] = ladder._sha256(jcs_bytes(zeroed))
        corrupted = jcs_bytes(value) + b"\n"
        with self.assertRaises(ladder.InvariantFailure) as raised:
            ladder._audit_semantic_record(self.raw, corrupted, self.oracle)
        self.assertEqual(raised.exception.divergence["kind"], "semantic_oracle_divergence")

    def test_missing_envelope_field_fails_before_projection(self) -> None:
        value = self._object()
        del value["audited_behavior_class"]
        with self.assertRaises(ladder.InvariantFailure) as raised:
            ladder._audit_semantic_record(self.raw, jcs_bytes(value) + b"\n", self.oracle)
        self.assertEqual(raised.exception.divergence["kind"], "audited_envelope_fields")

    def test_wrong_envelope_version_fails_before_projection(self) -> None:
        value = self._object()
        value["format_version"] = "B1-AUDITED-DECISION-9.9"
        with self.assertRaises(ladder.InvariantFailure) as raised:
            ladder._audit_semantic_record(self.raw, jcs_bytes(value) + b"\n", self.oracle)
        self.assertEqual(raised.exception.divergence["kind"], "audited_envelope_version")

    def test_noncanonical_envelope_fails_even_when_json_value_is_unchanged(self) -> None:
        noncanonical = json.dumps(
            self._object(), ensure_ascii=False, separators=(", ", ": ")
        ).encode("utf-8") + b"\n"
        with self.assertRaises(ladder.InvariantFailure) as raised:
            ladder._audit_semantic_record(self.raw, noncanonical, self.oracle)
        self.assertEqual(raised.exception.divergence["kind"], "audited_envelope_canonicality")

    def test_duplicate_envelope_member_is_rejected(self) -> None:
        duplicate = self.physical.replace(
            b'{"audit":', b'{"audit_sha256":"0","audit":', 1
        )
        with self.assertRaises(ladder.InvariantFailure) as raised:
            ladder._parse_audited_envelope(duplicate)
        self.assertEqual(raised.exception.divergence["kind"], "audited_envelope_json")

    def test_corrupted_audit_seal_is_rejected(self) -> None:
        value = self._object()
        value["audit_sha256"] = "0" * 64
        with self.assertRaises(ladder.InvariantFailure) as raised:
            ladder._audit_semantic_record(self.raw, jcs_bytes(value) + b"\n", self.oracle)
        self.assertEqual(raised.exception.divergence["kind"], "audited_envelope_audit_seal")

    def test_corrupted_outer_exit_semantics_are_rejected(self) -> None:
        value = self._object()
        value["exit_code"] = 0
        zeroed = dict(value)
        zeroed["audit_sha256"] = "0" * 64
        value["audit_sha256"] = ladder._sha256(jcs_bytes(zeroed))
        with self.assertRaises(ladder.InvariantFailure) as raised:
            ladder._audit_semantic_record(self.raw, jcs_bytes(value) + b"\n", self.oracle)
        self.assertEqual(raised.exception.divergence["kind"], "audited_envelope_semantics")

    def test_request_hash_binding_is_checked_independently(self) -> None:
        value = self._object()
        value["audit"]["request_raw_sha256"] = "0" * 64
        zeroed = dict(value)
        zeroed["audit_sha256"] = "0" * 64
        value["audit_sha256"] = ladder._sha256(jcs_bytes(zeroed))
        with self.assertRaises(ladder.InvariantFailure) as raised:
            ladder._audit_semantic_record(self.raw, jcs_bytes(value) + b"\n", self.oracle)
        self.assertEqual(raised.exception.divergence["kind"], "audited_envelope_request_binding")

    def test_multi_caller_semantic_receipt_binds_all_projections(self) -> None:
        inputs = {0: [self.raw], 1: [self.raw, self.raw]}
        outputs = {0: self.physical, 1: self.physical * 2}
        receipt = ladder._audit_semantic_outputs(inputs, outputs, self.oracle)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["compared_audited_envelopes"], 3)


@unittest.skipUnless(os.name == "nt", "Windows process-handle regression")
class WindowsProcessAliveTests(unittest.TestCase):
    def test_waited_process_is_not_alive_while_popen_handle_is_retained(self) -> None:
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", "import sys; sys.stdin.buffer.read(1)"],
            stdin=subprocess.PIPE,
        )
        try:
            self.assertTrue(ladder._process_alive(process.pid))
            process.communicate(input=b"x", timeout=10.0)
            self.assertEqual(process.returncode, 0)
            self.assertFalse(ladder._process_alive(process.pid))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5.0)


if __name__ == "__main__":
    unittest.main()
