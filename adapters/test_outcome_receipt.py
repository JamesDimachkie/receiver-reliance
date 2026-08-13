"""Measurement-only regressions for the deterministic all-408 receipt."""

from __future__ import annotations

import json
import pathlib
import sys
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
