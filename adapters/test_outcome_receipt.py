"""Measurement-only regressions for the deterministic all-408 receipt."""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from adapters.outcome_receipt import RECEIPT, TABLE, replay
from adapters.portable_preflight import (
    INSUFFICIENT_EVIDENCE,
    READY,
    REJECTED_INVALID,
    canonical_json_bytes,
)


class OutcomeReceiptTests(unittest.TestCase):
    def test_receipt_has_exact_paired_counts_and_boundary(self):
        receipt, receipt_raw, table_raw = replay()
        self.assertEqual(RECEIPT.read_bytes(), receipt_raw)
        self.assertEqual(TABLE.read_bytes(), table_raw)
        fallback = receipt["portable_fallback_reexecution"]
        self.assertEqual(
            fallback["status_counts"],
            {INSUFFICIENT_EVIDENCE: 208, READY: 192, REJECTED_INVALID: 8},
        )
        self.assertEqual(fallback["counts"]["ready_clean_false_hold"], 0)
        self.assertEqual(fallback["counts"]["rejected_invalid_defect_detected"], 8)
        self.assertEqual(fallback["counts"]["ready_defect_detected"], 10)
        self.assertEqual(fallback["counts"]["insufficient_evidence_clean"], 208)
        self.assertEqual(fallback["counts"]["insufficient_evidence_defect"], 0)
        self.assertEqual(fallback["detection"], "18/18")
        boundary = receipt["measurement_boundary"]
        self.assertFalse(boundary["exported_from_adapters"])
        self.assertFalse(boundary["claimable_as_fallback_capability"])
        assessment = receipt["charter_assessment"]
        self.assertTrue(assessment["outcome_bar_met"])
        self.assertTrue(assessment["package_complete"])
        self.assertIn("RUNTIME_BAR_MET", assessment["package_status"])

    def test_receipt_self_seal(self):
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        claimed = receipt["receipt_sha256"]
        receipt["receipt_sha256"] = "0" * 64
        import hashlib

        self.assertEqual(claimed, hashlib.sha256(canonical_json_bytes(receipt)).hexdigest().upper())

    def test_transitive_measurement_tampering_fails_closed(self):
        cases = (
            (
                pathlib.Path(
                    "baseline-run/implementation-output-0.3/b1_capabilities.py"
                ),
                "_outcome_receipt_b1_capabilities",
            ),
            (
                pathlib.Path(
                    "baseline-run/fixtures/"
                    "PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json"
                ),
                "measurement fixture pack",
            ),
        )
        for relative_path, label in cases:
            with self.subTest(path=relative_path), tempfile.TemporaryDirectory(
                prefix="rr-outcome-tamper-"
            ) as temporary:
                mirror = pathlib.Path(temporary) / "receiver-reliance"
                shutil.copytree(
                    REPO,
                    mirror,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
                )
                target = mirror / relative_path
                raw = target.read_bytes()
                target.write_bytes(bytes((raw[0] ^ 1,)) + raw[1:])
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-B",
                        str(mirror / "adapters/outcome_receipt.py"),
                        "--check",
                    ],
                    cwd=mirror,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=120,
                )
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(completed.stdout, b"")
                self.assertEqual(
                    completed.stderr.decode("utf-8").rstrip().splitlines()[-1],
                    f"RuntimeError: {label} failed byte authentication",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
