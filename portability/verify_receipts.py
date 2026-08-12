"""Independently re-verify the committed durable receipts, byte for byte.

Stdlib-only and read-only.  This program re-derives every custody property of
the committed evidence spine instead of trusting recorded summaries:

- the final local expanded-gate receipt: raw SHA-256, self-zeroed embedded
  hash, canonical byte identity, manifest order, per-stream byte counts and
  hashes, and a full validator rerun over every decoded transcript;
- both rejected gate receipts: quarantined status and recorded stop points;
- the independent N=48 refuter receipt: raw hash, source-file bindings,
  capture binding, and the capture-embedded canonical model receipt's
  self-zeroed hash;
- both clean concurrency receipts: raw hashes, clean-source binding, and
  independent recomputation of worker-run and audited-envelope totals.

The single summary line is machine-parseable by the matrix runner:
``verify-receipts: checks=<n> failures=<n>``.  Exit 0 only when every check
passes.  A change to any committed receipt, or to the sources a receipt
binds, fails this program; refreshing the constants below is an explicit,
reviewable act.
"""
from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import sys
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[1]
SANDBOX = REPO / "portability" / "sandbox"
if str(SANDBOX) not in sys.path:
    sys.path.insert(0, str(SANDBOX))

import expanded_gate  # noqa: E402

GATE_RECEIPT = REPO / "portability" / "receipts" / "local-expanded-gate-release-audit.json"
REJECTED_1 = REPO / "portability" / "receipts" / "local-expanded-gate-release-audit-rejected1.json"
REJECTED_2 = REPO / "portability" / "receipts" / "local-expanded-gate-release-audit-rejected2.json"
REFUTER_RECEIPT = REPO / "portability" / "model" / "receipts" / "N48-independent-refuter-20260811.json"
N48_CAPTURE = REPO / "portability" / "model" / "receipts" / "N48-postF3-attempt1.stdout.txt"
EXPECTED_COUNTS = REPO / "portability" / "model" / "EXPECTED_COUNTS.json"
CONC_NORMATIVE = (
    REPO / "portability" / "concurrency" / "receipts"
    / "normative-release-audit-head-8a525b1-attempt3.json"
)
CONC_SMOKE = (
    REPO / "portability" / "concurrency" / "receipts"
    / "smoke-release-audit-head-8a525b1-attempt3.json"
)

# Published custody constants.  These are the same values recorded in
# PORTABILITY_VALIDATION.md and the external task claim; a mismatch means a
# committed receipt or bound source changed after publication.
CLEAN_SOURCE_HEAD = "8a525b167b95a3b6b512282938199eba09594a24"
GATE_RAW_SHA256 = "4039ED94D885B9001C4B18B70C76BD7D70F6158A43946556C9062D66E7B361A3"
GATE_EMBEDDED_SHA256 = "F50D05B07985D21F37F4A8B1ACBDCCDED4D7CEF370343C9039F0D90AF34F0309"
REJECTED_1_RAW_SHA256 = "31F9C49E8D7E808372A399C9E868D624533D2171D99FB4CBC37EDDDB2E42AA73"
REJECTED_2_RAW_SHA256 = "B82AF20209165F3EBBDAD61C42F5454266693109EA2AE3BE0343EB1E4ADCDE53"
REFUTER_RAW_SHA256 = "3A8D4BF8FC862818A87F7B16B76D4565F32DBCF1507EB800490B193225BF9FF8"
MODEL_RECEIPT_SHA256 = "CD6210F8706C7B37B6CD25A9EF67B53696207EAFED716284151D67B20444732E"
CURRENT_REJECTED_ALIAS_EDGES = 20531838
CONC_NORMATIVE_RAW_SHA256 = "B1782A43E4E4615569948953FFC45659BF0A820BEB67136F73FEDFDEAFE29998"
CONC_SMOKE_RAW_SHA256 = "8CBA926DFB61B2C729C5CEAB95FF89350B99AFAF03809CBDDEAF6B8AC7719030"
CONC_WORKER_RUNS = 32
CONC_AUDITED_ENVELOPES = 242400


def _sha256_upper(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


class _Verifier:
    def __init__(self) -> None:
        self.checks = 0
        self.failures: list[str] = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        self.checks += 1
        if not condition:
            self.failures.append(f"{name}{': ' + detail if detail else ''}")
            print(f"FAIL {name} {detail}".rstrip(), file=sys.stderr)


def _verify_gate_receipt(v: _Verifier) -> None:
    raw = GATE_RECEIPT.read_bytes()
    v.check("gate.raw_sha256", _sha256_upper(raw) == GATE_RAW_SHA256)
    doc = json.loads(raw)
    embedded = doc.pop("receipt_sha256")
    v.check(
        "gate.self_zeroed_hash",
        _sha256_upper(_canonical(doc)) == embedded == GATE_EMBEDDED_SHA256,
    )
    doc["receipt_sha256"] = embedded
    v.check("gate.canonical_byte_identity", _canonical(doc) + b"\n" == raw)
    v.check("gate.status", doc["status"] == "PASS")
    v.check(
        "gate.source_binding",
        doc["git"]["head"] == CLEAN_SOURCE_HEAD
        and doc["git"]["clean"] is True
        and doc["git"]["status_bytes"] == 0,
    )
    commands = doc["commands"]
    v.check(
        "gate.manifest_order",
        [item["gate_id"] for item in commands]
        == [spec.gate_id for spec in expanded_gate.GATES],
    )
    specs = {spec.gate_id: spec for spec in expanded_gate.GATES}
    for item in commands:
        gate_id = item["gate_id"]
        spec = specs[gate_id]
        v.check(f"gate.{gate_id}.exit", item["exit_code"] == 0 and item["timed_out"] is False)
        stdout = base64.b64decode(item["stdout_b64"], validate=True)
        stderr = base64.b64decode(item["stderr_b64"], validate=True)
        v.check(
            f"gate.{gate_id}.stream_binding",
            len(stdout) == item["stdout_bytes"]
            and _sha256_upper(stdout) == item["stdout_sha256"]
            and len(stderr) == item["stderr_bytes"]
            and _sha256_upper(stderr) == item["stderr_sha256"],
        )
        try:
            observed = expanded_gate.validate_gate_output(spec.validator, stdout, stderr)
            v.check(f"gate.{gate_id}.validator_rerun", observed == item.get("observed"))
        except (expanded_gate.GateFailure, UnicodeError, ValueError) as error:
            v.check(f"gate.{gate_id}.validator_rerun", False, str(error))


def _verify_rejected(v: _Verifier) -> None:
    for label, path, raw_sha, stop_gate in (
        ("rejected1", REJECTED_1, REJECTED_1_RAW_SHA256, "grounded_0_4_regression"),
        ("rejected2", REJECTED_2, REJECTED_2_RAW_SHA256, "synthetic_proof_harness"),
    ):
        raw = path.read_bytes()
        v.check(f"{label}.raw_sha256", _sha256_upper(raw) == raw_sha)
        doc = json.loads(raw)
        last = doc["commands"][-1]
        v.check(
            f"{label}.quarantined",
            doc["status"] != "PASS"
            and last["gate_id"] == stop_gate
            and last.get("status") == "FAIL",
        )


def _verify_model_receipts(v: _Verifier) -> None:
    raw = REFUTER_RECEIPT.read_bytes()
    v.check("refuter.raw_sha256", _sha256_upper(raw) == REFUTER_RAW_SHA256)
    doc = json.loads(raw)
    v.check(
        "refuter.verdict",
        doc["status"] == "PASS"
        and doc["canonical_receipt_bytes_identical"] is True
        and doc["candidate_receipt_sha256"] == MODEL_RECEIPT_SHA256
        and doc["expected_receipt_sha256"] == MODEL_RECEIPT_SHA256,
    )
    v.check(
        "refuter.alias_accounting",
        doc["inadmissible_alias_edges"] == CURRENT_REJECTED_ALIAS_EDGES,
    )
    for name, recorded in sorted(doc["source_sha256"].items()):
        candidate = REPO / "portability" / "model" / name
        if not candidate.exists():
            candidate = REPO / "portability" / "model" / "receipts" / name
        v.check(
            f"refuter.source_binding.{name}",
            candidate.exists() and _sha256_upper(candidate.read_bytes()) == recorded,
        )
    capture_raw = N48_CAPTURE.read_bytes()
    capture = doc["expected_capture"]
    v.check(
        "refuter.capture_binding",
        pathlib.PurePosixPath(capture["path"]).name == N48_CAPTURE.name
        and len(capture_raw) == capture["bytes"]
        and _sha256_upper(capture_raw) == capture["sha256"],
    )
    body = json.loads(capture_raw.rstrip(b"\r\n").decode("ascii"))
    embedded = body.pop("receipt_sha256")
    v.check(
        "model.capture_self_zeroed_hash",
        _sha256_upper(_canonical(body)) == embedded == MODEL_RECEIPT_SHA256,
    )
    expected_counts = json.loads(EXPECTED_COUNTS.read_text(encoding="utf-8"))
    v.check(
        "model.expected_counts_binding",
        expected_counts.get("final_receipt_sha256") == MODEL_RECEIPT_SHA256,
    )


def _verify_concurrency(v: _Verifier) -> None:
    for label, path, raw_sha in (
        ("concurrency.normative", CONC_NORMATIVE, CONC_NORMATIVE_RAW_SHA256),
        ("concurrency.smoke", CONC_SMOKE, CONC_SMOKE_RAW_SHA256),
    ):
        raw = path.read_bytes()
        v.check(f"{label}.raw_sha256", _sha256_upper(raw) == raw_sha)
        doc = json.loads(raw)
        v.check(
            f"{label}.clean_source_binding",
            doc["status"] == "PASS"
            and doc["git"]["clean"] is True
            and doc["git"]["head"] == CLEAN_SOURCE_HEAD,
        )
    normative = json.loads(CONC_NORMATIVE.read_bytes())
    runs = 0
    envelopes = 0
    for section in list(normative["levels"]) + list(normative["soaks"]):
        participants = section["participants"]
        for mode in section["modes"]:
            for run in mode["runs"]:
                runs += 1
                envelopes += participants * run["requests_per_caller"]
    v.check("concurrency.worker_runs", runs == CONC_WORKER_RUNS)
    v.check("concurrency.audited_envelopes", envelopes == CONC_AUDITED_ENVELOPES)


def main() -> int:
    verifier = _Verifier()
    _verify_gate_receipt(verifier)
    _verify_rejected(verifier)
    _verify_model_receipts(verifier)
    _verify_concurrency(verifier)
    print(
        f"verify-receipts: checks={verifier.checks} "
        f"failures={len(verifier.failures)}"
    )
    return 1 if verifier.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
