"""Deterministic all-408 WP1 fallback measurement and receipt generator."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from collections import Counter
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
FIXTURES = HERE / "fixtures"
RECEIPTS = HERE / "receipts"
CORPUS = FIXTURES / "parent_corpus_408.jsonl"
TRUTH = FIXTURES / "parent_truth_408.jsonl"
RECEIPT = RECEIPTS / "WP1_OUTCOME_RECEIPT.json"
TABLE = HERE / "OUTCOME.md"
HOSTED_MANIFEST = REPO / "portability" / "receipts" / "hosted" / "MANIFEST.json"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from adapters.fixture_extract import verify as verify_fixtures  # noqa: E402
from adapters.portable_preflight import (  # noqa: E402
    INSUFFICIENT_EVIDENCE,
    READY,
    REJECTED_INVALID,
    canonical_json_bytes,
    preflight,
)

IMPL = REPO / "baseline-run" / "implementation-output-0.3"
PROOF = REPO / "proof"
for path in (IMPL, PROOF):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
import arm_b1 as measurement_adapter  # noqa: E402
import pcb_runner as mutable_measurement_runner  # noqa: E402

EXPECTED = {
    "parent_corpus_raw_sha256": "09B4B05FE26CF46F063EC637C1A4D27B4D5190961756888099F96254C49B334E",
    "parent_truth_raw_sha256": "4FEEF9BE65DD7523849CEE71B5A43EA6F7667710745E71D79C0EE5B054E3E2C7",
    "source_proof_results_raw_sha256": "3883F504C349D8884701586DB0B8B29744D094EBB6B7C6A5DB69456FAEC9C032",
    "source_proof_adapter_raw_sha256": "978BEE0A3F278BAE083B390A36153C08C1CDF4ABB0F9581A4EAE8860957BE12E",
    "hosted_manifest_raw_sha256": "9DC261CA316C4F8E83342FE6AD24EBF15C3A21F3FD38AE6565EE28651569D5E6",
}


def _load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _raw_sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _response_behavior(response: dict[str, Any]) -> str:
    if not response.get("ok"):
        return "PROTOCOL_ERROR"
    return response["output"]["result_object"]["behavior_class"]


def _measurement_behavior(record: dict[str, Any]) -> str:
    """Exercise the pinned proof adapter/runner only inside this receipt.

    This mutable local harness is not imported by the portable fallback,
    exported from ``adapters``, or claimable as shipped integration behavior.
    """

    previous = measurement_adapter.CALIBRATED
    try:
        measurement_adapter.CALIBRATED = False
        facts, _fabricated = measurement_adapter.derive_facts(record)
        request = measurement_adapter.build_request(record, facts)
        response, _exit = mutable_measurement_runner._execute(
            canonical_json_bytes(request) + b"\n"
        )
    finally:
        measurement_adapter.CALIBRATED = previous
    return _response_behavior(response)


def _fallback_counts() -> Counter[str]:
    return Counter(
        ready_clean_pass=0,
        ready_clean_false_hold=0,
        ready_defect_detected=0,
        ready_defect_missed=0,
        rejected_invalid_clean=0,
        rejected_invalid_defect_detected=0,
        insufficient_evidence_clean=0,
        insufficient_evidence_defect=0,
        protocol_error=0,
    )


def replay() -> tuple[dict[str, Any], bytes, bytes]:
    provenance = verify_fixtures()
    pins_to_check = {
        "parent_corpus_raw_sha256": CORPUS,
        "parent_truth_raw_sha256": TRUTH,
        "source_proof_results_raw_sha256": PROOF / "results.json",
        "source_proof_adapter_raw_sha256": PROOF / "arm_b1.py",
        "hosted_manifest_raw_sha256": HOSTED_MANIFEST,
    }
    for key, path in pins_to_check.items():
        actual = _raw_sha(path)
        if actual != EXPECTED[key]:
            raise RuntimeError(f"raw SHA pin failed for {path}: {actual} != {EXPECTED[key]}")

    records = _load_jsonl(CORPUS)
    truths = {row["record_id"]: row for row in _load_jsonl(TRUTH)}
    if len(records) != 408 or len(truths) != 408:
        raise RuntimeError("WP1 parent snapshot is not the pinned 408-record protocol")

    historical = Counter(
        clean_pass=0,
        clean_false_hold=0,
        defect_detected=0,
        defect_missed=0,
        protocol_error=0,
    )
    fallback = _fallback_counts()
    historical_behaviors: Counter[str] = Counter()
    ready_behaviors: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    family_status_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()

    for record in records:
        # Runtime classification receives only native/observation structure.
        # Truth is joined afterward and is used solely by this offline scorer.
        result = preflight(record)
        status_counts[result.status] += 1
        family_status_counts[f"{record['family']}:{result.status}"] += 1
        issue_counts.update(problem.code for problem in result.issues)

        defective = bool(truths[record["record_id"]]["defective"])
        old_behavior = _measurement_behavior(record)
        historical_behaviors[old_behavior] += 1
        if old_behavior == "PROTOCOL_ERROR":
            historical["protocol_error"] += 1
        elif defective:
            historical["defect_missed" if old_behavior == "VALID" else "defect_detected"] += 1
        else:
            historical["clean_pass" if old_behavior == "VALID" else "clean_false_hold"] += 1

        if result.status == REJECTED_INVALID:
            fallback[
                "rejected_invalid_defect_detected" if defective else "rejected_invalid_clean"
            ] += 1
        elif result.status == INSUFFICIENT_EVIDENCE:
            fallback[
                "insufficient_evidence_defect" if defective else "insufficient_evidence_clean"
            ] += 1
        elif result.status == READY:
            behavior = _measurement_behavior(record)
            ready_behaviors[behavior] += 1
            if behavior == "PROTOCOL_ERROR":
                fallback["protocol_error"] += 1
            elif defective:
                fallback[
                    "ready_defect_missed" if behavior == "VALID" else "ready_defect_detected"
                ] += 1
            else:
                fallback[
                    "ready_clean_pass" if behavior == "VALID" else "ready_clean_false_hold"
                ] += 1
        else:  # pragma: no cover - PreflightResult enforces the closed taxonomy.
            raise RuntimeError(f"unexpected preflight status {result.status}")

    expected_historical = {
        "clean_pass": 257,
        "clean_false_hold": 133,
        "defect_detected": 18,
        "defect_missed": 0,
        "protocol_error": 0,
    }
    expected_fallback = {
        "ready_clean_pass": 182,
        "ready_clean_false_hold": 0,
        "ready_defect_detected": 10,
        "ready_defect_missed": 0,
        "rejected_invalid_clean": 0,
        "rejected_invalid_defect_detected": 8,
        "insufficient_evidence_clean": 208,
        "insufficient_evidence_defect": 0,
        "protocol_error": 0,
    }
    expected_statuses = {READY: 192, REJECTED_INVALID: 8, INSUFFICIENT_EVIDENCE: 208}
    if (
        dict(historical) != expected_historical
        or dict(fallback) != expected_fallback
        or dict(status_counts) != expected_statuses
    ):
        raise RuntimeError(
            "outcome drift: "
            f"historical={dict(historical)}, fallback={dict(fallback)}, "
            f"statuses={dict(status_counts)}"
        )

    portable_sha = _raw_sha(HERE / "portable_preflight.py")
    hosted_manifest = json.loads(HOSTED_MANIFEST.read_text(encoding="utf-8"))
    hosted_json_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(HOSTED_MANIFEST.parent.rglob("*.json"))
    )
    hosted_command_present = "adapters/test_portable_preflight.py" in hosted_json_text
    hosted_hash_present = portable_sha in hosted_json_text
    if hosted_command_present or hosted_hash_present:
        raise RuntimeError("hosted-evidence classification changed; inspect before claiming pending")

    receipt: dict[str, Any] = {
        "format_version": "RR-WP1-OUTCOME-RECEIPT-3",
        "producer": "adapters/outcome_receipt.py",
        "scope": "all 408 raw-SHA-pinned native proof records",
        "provenance": provenance,
        "pins": {
            **EXPECTED,
            "portable_preflight_raw_sha256": portable_sha,
            "fixture_extract_raw_sha256": _raw_sha(HERE / "fixture_extract.py"),
            "outcome_runner_raw_sha256": _raw_sha(pathlib.Path(__file__)),
        },
        "historical_forced_reexecution": {
            "classification": "current re-execution of the raw-SHA-pinned historical forced arm",
            "counts": dict(historical),
            "engine_behavior_counts": dict(sorted(historical_behaviors.items())),
            "false_hold_rate_clean": "34.1%",
            "detection": "18/18",
        },
        "portable_fallback_reexecution": {
            "classification": "portable native-evidence preflight followed by measurement-only engine replay for READY rows",
            "result_format_version": "RR-PORTABLE-PREFLIGHT-1",
            "status_counts": dict(sorted(status_counts.items())),
            "family_status_counts": dict(sorted(family_status_counts.items())),
            "issue_counts": dict(sorted(issue_counts.items())),
            "counts": dict(fallback),
            "ready_engine_behavior_counts": dict(sorted(ready_behaviors.items())),
            "false_hold_rate_clean": "0.0%",
            "detection": "18/18",
            "detection_components": {
                "rejected_invalid_before_applicability": "8/18",
                "ready_engine_detection": "10/18",
            },
            "rejected_invalid_is_detection": True,
            "insufficient_evidence_is_abstention": True,
            "insufficient_evidence_counted_as_pass": False,
            "rejected_invalid_counted_as_pass": False,
            "runtime_truth_labels_used_by_preflight": False,
        },
        "measurement_boundary": {
            "mutable_runner_status": "NON_SHIPPING_MEASUREMENT_ONLY",
            "exported_from_adapters": False,
            "claimable_as_fallback_capability": False,
            "scope": "READY-row replay in this raw-SHA-pinned all-408 receipt only",
        },
        "charter_assessment": {
            "delivery_mode": "FALLBACK_CALIBRATION_PLUS_PORTABLE_PREFLIGHT",
            "required_current_detection": "18/18",
            "measured_current_detection": "18/18",
            "outcome_bar_met": True,
            "fallback_surface_delivered": True,
            "runtime_evidence_bar_met": True,
            "package_complete": True,
            "package_status": "FALLBACK_DELIVERED_RUNTIME_BAR_MET",
            "reason": "paired all-408 measure is met; local CPython 3.12/3.13/3.14 suite evidence is recorded for these bytes in adapters/RUNTIME_EVIDENCE.md (2026-08-13 re-pin)",
        },
        "runtime_evidence": {
            "cpython_3_12": "local suite evidence recorded separately for these bytes",
            "cpython_3_13": "local suite evidence recorded separately for these bytes",
            "cpython_3_14": "local suite evidence recorded separately for these bytes",
            "evidence_bar_met": True,
            "hosted_evidence_inspection": {
                "manifest_raw_sha256": EXPECTED["hosted_manifest_raw_sha256"],
                "hosted_head_sha": hosted_manifest["head_sha"],
                "current_wp1_command_present": hosted_command_present,
                "current_portable_preflight_sha_present": hosted_hash_present,
                "conclusion": "existing hosted rows do not exercise current WP1 fallback bytes",
            },
        },
        "receipt_sha256": "0" * 64,
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        canonical_json_bytes(receipt)
    ).hexdigest().upper()
    receipt_raw = json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    receipt_raw_sha = hashlib.sha256(receipt_raw).hexdigest().upper()
    table = f"""# WP1 portable fallback outcome — all-408 replay

This file is deterministic generator output from `adapters/outcome_receipt.py`.
Do not edit it independently; `--write` regenerates it together with
`adapters/receipts/WP1_OUTCOME_RECEIPT.json`, and `--check` requires both byte
sequences to match the current generator and pinned inputs.

The fallback preflight classified all 408 raw-SHA-pinned native records before
the offline scorer joined truth. `REJECTED_INVALID` is detection;
`INSUFFICIENT_EVIDENCE` is abstention. Neither is a pass. `READY` only permits
the receipt's bounded, measurement-only engine replay and is not itself a pass.

| arm | ready clean pass | new false holds | insufficient clean | rejected-invalid detection | ready engine detection | total detection | clean false-hold rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| historical forced arm | 257/390 | 133 | 0 | 0/18 | 18/18 | 18/18 | 34.1% |
| portable fallback | 182/390 | 0 | 208 | 8/18 | 10/18 | 18/18 | 0.0% |

The portable taxonomy is exact: 192 `READY`, 8 `REJECTED_INVALID`, and 208
`INSUFFICIENT_EVIDENCE`. Five stale REF alias/path contradictions and three
equal/non-increasing lifecycle timestamp contradictions are rejected before
applicability. The 208 untyped, noncontradictory lifecycle rows abstain because
timestamps do not establish acknowledgment semantics. No defective row is in
the insufficient-evidence bucket.

The accepted-core runner and pinned proof adapter used after `READY` are
mutable local measurement machinery. They are non-shipping, absent from the
exported fallback API, and not claimable as integration capability.

The paired outcome bar is met at 0 new false holds and 18/18 detection. The
runtime evidence bar is met: local CPython 3.12/3.13/3.14 suite evidence for
these bytes is recorded in `RUNTIME_EVIDENCE.md` (2026-08-13 re-pin). Existing
hosted receipts still do not cover these bytes.

- Receipt raw SHA-256: `{receipt_raw_sha}`
- Parent corpus raw SHA-256: `{EXPECTED['parent_corpus_raw_sha256']}`
- Parent truth raw SHA-256: `{EXPECTED['parent_truth_raw_sha256']}`
- Row-binding SHA-256: `{provenance['row_bindings_sha256']}`

Reproduce with `python -B adapters/fixture_extract.py --check` and
`python -B adapters/outcome_receipt.py --check`. Regeneration is explicit:
`python -B adapters/outcome_receipt.py --write`.
""".encode("utf-8")
    return receipt, receipt_raw, table


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    receipt, receipt_raw, table_raw = replay()
    if args.write:
        RECEIPTS.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(receipt_raw)
        TABLE.write_bytes(table_raw)
    else:
        if not RECEIPT.exists() or RECEIPT.read_bytes() != receipt_raw:
            raise SystemExit("WP1 receipt is absent or non-deterministic; run --write")
        if not TABLE.exists() or TABLE.read_bytes() != table_raw:
            raise SystemExit("WP1 outcome table is absent or non-deterministic; run --write")
    fallback = receipt["portable_fallback_reexecution"]
    assessment = receipt["charter_assessment"]
    print(
        "WP1 all-408 fallback replay: "
        f"{fallback['counts']['ready_clean_false_hold']} new false holds, "
        f"{fallback['status_counts'][INSUFFICIENT_EVIDENCE]} insufficient, "
        f"detection {fallback['detection']}; "
        f"{assessment['package_status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
