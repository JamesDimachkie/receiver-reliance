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
  independent recomputation of worker-run and audited-envelope totals;
- the hosted receipt custody tree: the manifest's raw hash, fail-closed
  directory enumeration, byte-for-byte binding of every listed file, the
  validated 28-row outcome vector and counts of the committed hosted
  matrix summary, the sandbox host receipt's status, source, and committed
  Dockerfile binding, and the hosted expanded-gate receipt's command exits
  and load-bearing suite totals.

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
PORTABILITY = REPO / "portability"
if str(PORTABILITY) not in sys.path:
    sys.path.insert(0, str(PORTABILITY))

MATRIX = REPO / "portability" / "matrix"
if str(MATRIX) not in sys.path:
    sys.path.insert(0, str(MATRIX))

import expanded_gate  # noqa: E402
import receipt as matrix_receipt  # noqa: E402
import strict_ingest  # noqa: E402

GATE_RECEIPT = REPO / "portability" / "receipts" / "local-expanded-gate-release-audit.json"
CLOSE_GATE_RECEIPT = REPO / "portability" / "receipts" / "local-expanded-gate-close.json"
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
EXPECTED_COUNTS_RAW_SHA256 = (
    "05DA6CC670CA3F3553B1B7B2807EC312E70ABAFF10D3E8FCE458DA5CC3C2282C"
)
CURRENT_REJECTED_ALIAS_EDGES = 20531838
CONC_NORMATIVE_RAW_SHA256 = "B1782A43E4E4615569948953FFC45659BF0A820BEB67136F73FEDFDEAFE29998"
CONC_SMOKE_RAW_SHA256 = "8CBA926DFB61B2C729C5CEAB95FF89350B99AFAF03809CBDDEAF6B8AC7719030"
CONC_WORKER_RUNS = 32
CONC_AUDITED_ENVELOPES = 242400
CONC_STATUS = REPO / "portability" / "concurrency" / "receipts" / "STATUS.md"

# Source pins published by ``portability/concurrency/receipts/STATUS.md``.  That
# table says any change to one of these files invalidates the receipt binding
# and requires a new receipt.  Nothing enforced it: ``_verify_concurrency``
# binds the receipt bytes and recomputes the run totals, but never rehashed the
# sources the receipts name.  Keys are repository-relative POSIX paths.
CONCURRENCY_SOURCE_PINS = {
    "portability/concurrency/ladder.py": (
        "B5436C851C849CFB2B39A7EC2B35C258E501E3171A2ECD6BE6AF913329CC27E6"
    ),
    "portability/concurrency/test_ladder.py": (
        "926D75C5C64A3D44D18FB40D85CA59CE3AC0BF2600C12ACE2BCBF749EF364630"
    ),
    "portability/oracle/oracle.py": (
        "2148F0C9C4ED38692B9C6658EC48CDD9628688E6C1708345C89A44AB91A05F17"
    ),
    "portability/oracle/__init__.py": (
        "747CF1373F63C6DFB7F1A01744EB0B9A9D91FED17F127FFD0C510AF924AA3BFF"
    ),
}
# ERRATA E12.  ``ladder.py``'s published digest is its bytes at 4ea69dc, the
# commit that bound the clean v3 receipts.  ca1ccfe then changed one line —
# ``AUDITED_FORMAT_VERSION`` 0.4 to 0.4.1, the F-MATRIX-016 migration — which
# moved the bytes.  The pin is deliberately NOT refreshed: rewriting it would
# assert that today's bytes produced the recorded 213.937-second run, which is
# false.  The erratum records both digests instead, so the stale pin stays
# honest and a SECOND undisclosed move cannot hide behind the first.
# path -> (digest published in STATUS.md, digest of the current bytes).
SOURCE_PIN_ERRATA = {
    "portability/concurrency/ladder.py": (
        "B5436C851C849CFB2B39A7EC2B35C258E501E3171A2ECD6BE6AF913329CC27E6",
        "D40F692AEC6197C005E74F12BE996C860A4FF1A5FF821E828B84CFA1585E044A",
    ),
}

# Close evidence: the clean-tree expanded gate at the reconciliation commit.
CLOSE_SOURCE_HEAD = "8104874a9e4081fca62c1cc142f68988e87751eb"
CLOSE_GATE_RAW_SHA256 = (
    "0A9B28FF9F255752309E3CD9F2EE0C8381122BB35B064F4C8367AD4D4DA8D81C"
)
CLOSE_GATE_EMBEDDED_SHA256 = (
    "AE20E36517C11E701371C50362BCA0E7343BC189D9616ABC3A6E5D85AC5C5FFF"
)

# Hosted receipt custody (green run 31562391384 on the pushed head).
HOSTED_DIR = REPO / "portability" / "receipts" / "hosted"
HOSTED_MANIFEST = HOSTED_DIR / "MANIFEST.json"
HOSTED_MANIFEST_RAW_SHA256 = (
    "9DC261CA316C4F8E83342FE6AD24EBF15C3A21F3FD38AE6565EE28651569D5E6"
)
HOSTED_HEAD = "7facfa34bb7b841fd0a7d911f15b4da71efde95b"
HOSTED_RUN_ID = 31562391384
HOSTED_SUMMARY_COUNTS = {
    "normative": {"INFRA_UNAVAILABLE": 3, "PASS": 16},
    "off_contract": {
        "INFRA_UNAVAILABLE": 1,
        "OBSERVED_DIVERGENCE": 1,
        "RECEIPT_MISSING": 1,
    },
    "stress": {"INFRA_UNAVAILABLE": 4, "PASS": 2},
}
HOSTED_ROW_OUTCOMES = {
    "normative-cpython-3-12-ubuntu-latest-x64": "PASS",
    "normative-cpython-3-12-ubuntu-24-04-arm-arm64": "PASS",
    "normative-cpython-3-12-macos-latest-arm64": "PASS",
    "normative-cpython-3-12-macos-13-x64": "INFRA_UNAVAILABLE",
    "normative-cpython-3-12-windows-latest-x64": "PASS",
    "normative-cpython-3-12-windows-11-arm-arm64": "PASS",
    "normative-cpython-3-13-ubuntu-latest-x64": "PASS",
    "normative-cpython-3-13-ubuntu-24-04-arm-arm64": "PASS",
    "normative-cpython-3-13-macos-latest-arm64": "PASS",
    "normative-cpython-3-13-macos-13-x64": "INFRA_UNAVAILABLE",
    "normative-cpython-3-13-windows-latest-x64": "PASS",
    "normative-cpython-3-13-windows-11-arm-arm64": "PASS",
    "normative-cpython-3-14-ubuntu-latest-x64": "PASS",
    "normative-cpython-3-14-ubuntu-24-04-arm-arm64": "PASS",
    "normative-cpython-3-14-macos-latest-arm64": "PASS",
    "normative-cpython-3-14-macos-13-x64": "INFRA_UNAVAILABLE",
    "normative-cpython-3-14-windows-latest-x64": "PASS",
    "normative-cpython-3-14-windows-11-arm-arm64": "PASS",
    "stress-cpython-3-14t-ubuntu-latest-x64": "PASS",
    "stress-cpython-3-14-dev-mode-ubuntu-latest-x64": "PASS",
    "stress-cpython-3-14-pydebug-ubuntu-latest-x64": "INFRA_UNAVAILABLE",
    "off-contract-pypy-3-12-ubuntu-latest-x64": "INFRA_UNAVAILABLE",
    "off-contract-pypy-3-11-ubuntu-latest-x64": "OBSERVED_DIVERGENCE",
    "off-contract-graalpy-24-0-ubuntu-latest-x64": "RECEIPT_MISSING",
    "stress-non-substitute-cpython-3-12-macos-15-intel-x64": "INFRA_UNAVAILABLE",
    "stress-non-substitute-cpython-3-13-macos-15-intel-x64": "INFRA_UNAVAILABLE",
    "stress-non-substitute-cpython-3-14-macos-15-intel-x64": "INFRA_UNAVAILABLE",
    "expanded-gate-cpython-3-12-ubuntu-latest-x64": "PASS",
}
# Load-bearing hosted expanded-gate totals: id -> (field, expected values).
HOSTED_GATE_TOTALS = {
    "accepted-0.2": ("count_totals", [800]),
    "composed-0.3-all": ("count_totals", [800, 107]),
    "grounded-0.4-regression": ("checks", [504]),
    "lint-gate-meta": ("checks", [7]),
    "grounded-properties": ("checks", [2296]),
    "audit-adversarial": ("checks", [6497]),
    "synthetic-proof-harness": ("tests", [7]),
    "seeded-fuzz-smoke": ("count_totals", [31, 31]),
    "batch-performance-gate": ("checks", [2160]),
    "single-pass-benchmark": ("checks", [1142]),
}
SANDBOX_DOCKERFILE = REPO / "portability" / "sandbox" / "Dockerfile"
# The two committed expanded-gate receipts are sealed portability-era
# evidence; their streams replay through the validators that governed that
# era, not the current-tree pins.
LEGACY_GATE_VALIDATORS = {
    "grounded_0_4_regression": "checks_504",
    "lint_gate_meta": "checks_7",
}
# The committed hosted tree is run 31562391384 at HOSTED_HEAD.  Its rows were
# never replayed through the matrix's own plan-aware row validator here — only
# through hardcoded manifest, count and outcome constants — so this file could
# accept stale custody as proof of the current cross-platform gate.  The rows do
# replay, but only against the command manifest of their own era, on the same
# principle as LEGACY_GATE_VALIDATORS above.  Two things differed at that run:
# the plan had no ``portable-bundle-gate`` command (added later; F-MATRIX-015
# migrated the planned count 17 to 18 in the same change), and three suite
# expectations have since moved.  Declaring the era in code keeps the drift
# visible instead of leaving the evidence unvalidated.
HOSTED_ERA_ABSENT_COMMANDS = ("portable-bundle-gate",)
HOSTED_ERA_EXPECTATIONS = {
    "verify-committed-receipts": {"checks": [62], "failures": [0]},
    "grounded-0.4-regression": {"checks": [504], "failures": [0]},
    "lint-gate-meta": {"checks": [7], "failures": [0]},
}
# The GraalPy row is rejected by the current row validator for a reason that is
# a defect in the validator rather than in the evidence: it derives a
# CPython-style prerelease suffix from ``version_info`` and requires it at the
# start of ``sys.version``, which truthful GraalPy metadata does not satisfy
# (``full_version`` starts "3.10.13", ``version_info`` says alpha).  Recorded
# and declared here rather than silently skipped.
HOSTED_ERA_ROW_EXCEPTIONS = {
    "off-contract-graalpy-24-0-ubuntu-latest-x64": (
        "runtime full_version disagrees with version_info release metadata"
    ),
}


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


def _verify_clean_gate_receipt(
    v: _Verifier,
    prefix: str,
    path: pathlib.Path,
    raw_sha: str,
    embedded_sha: str,
    source_head: str,
) -> None:
    raw = path.read_bytes()
    v.check(f"{prefix}.raw_sha256", _sha256_upper(raw) == raw_sha)
    doc = strict_ingest.load_safe(raw)
    embedded = doc.pop("receipt_sha256")
    v.check(
        f"{prefix}.self_zeroed_hash",
        _sha256_upper(_canonical(doc)) == embedded == embedded_sha,
    )
    doc["receipt_sha256"] = embedded
    v.check(f"{prefix}.canonical_byte_identity", _canonical(doc) + b"\n" == raw)
    v.check(f"{prefix}.status", doc["status"] == "PASS")
    v.check(
        f"{prefix}.source_binding",
        doc["git"]["head"] == source_head
        and doc["git"]["clean"] is True
        and doc["git"]["status_bytes"] == 0,
    )
    commands = doc["commands"]
    v.check(
        f"{prefix}.manifest_order",
        [item["gate_id"] for item in commands]
        == [spec.gate_id for spec in expanded_gate.GATES],
    )
    specs = {spec.gate_id: spec for spec in expanded_gate.GATES}
    for item in commands:
        gate_id = item["gate_id"]
        spec = specs[gate_id]
        v.check(
            f"{prefix}.{gate_id}.exit",
            item["exit_code"] == 0 and item["timed_out"] is False,
        )
        stdout = base64.b64decode(item["stdout_b64"], validate=True)
        stderr = base64.b64decode(item["stderr_b64"], validate=True)
        v.check(
            f"{prefix}.{gate_id}.stream_binding",
            len(stdout) == item["stdout_bytes"]
            and _sha256_upper(stdout) == item["stdout_sha256"]
            and len(stderr) == item["stderr_bytes"]
            and _sha256_upper(stderr) == item["stderr_sha256"],
        )
        validator = LEGACY_GATE_VALIDATORS.get(gate_id, spec.validator)
        try:
            observed = expanded_gate.validate_gate_output(validator, stdout, stderr)
            v.check(f"{prefix}.{gate_id}.validator_rerun", observed == item.get("observed"))
        except (expanded_gate.GateFailure, UnicodeError, ValueError) as error:
            v.check(f"{prefix}.{gate_id}.validator_rerun", False, str(error))


def _verify_gate_receipt(v: _Verifier) -> None:
    _verify_clean_gate_receipt(
        v,
        "gate",
        GATE_RECEIPT,
        GATE_RAW_SHA256,
        GATE_EMBEDDED_SHA256,
        CLEAN_SOURCE_HEAD,
    )
    _verify_clean_gate_receipt(
        v,
        "close_gate",
        CLOSE_GATE_RECEIPT,
        CLOSE_GATE_RAW_SHA256,
        CLOSE_GATE_EMBEDDED_SHA256,
        CLOSE_SOURCE_HEAD,
    )


def _verify_rejected(v: _Verifier) -> None:
    for label, path, raw_sha, stop_gate in (
        ("rejected1", REJECTED_1, REJECTED_1_RAW_SHA256, "grounded_0_4_regression"),
        ("rejected2", REJECTED_2, REJECTED_2_RAW_SHA256, "synthetic_proof_harness"),
    ):
        raw = path.read_bytes()
        v.check(f"{label}.raw_sha256", _sha256_upper(raw) == raw_sha)
        doc = strict_ingest.load_safe(raw)
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
    doc = strict_ingest.load_safe(raw)
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
    body = strict_ingest.load_safe(capture_raw.rstrip(b"\r\n"), label="model.capture")
    embedded = body.pop("receipt_sha256")
    v.check(
        "model.capture_self_zeroed_hash",
        _sha256_upper(_canonical(body)) == embedded == MODEL_RECEIPT_SHA256,
    )
    counts_raw = EXPECTED_COUNTS.read_bytes()
    # Review correction: bind the full raw bytes, not only the embedded
    # receipt hash — every other field of EXPECTED_COUNTS.json is equally
    # load-bearing published state.
    v.check(
        "model.expected_counts_raw_sha256",
        _sha256_upper(counts_raw) == EXPECTED_COUNTS_RAW_SHA256,
    )
    expected_counts = strict_ingest.load_safe(counts_raw)
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
        doc = strict_ingest.load_safe(raw)
        v.check(
            f"{label}.clean_source_binding",
            doc["status"] == "PASS"
            and doc["git"]["clean"] is True
            and doc["git"]["head"] == CLEAN_SOURCE_HEAD,
        )
    normative = strict_ingest.load_safe(CONC_NORMATIVE.read_bytes())
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


def _verify_source_pins(v: _Verifier) -> None:
    """Bind the sources the concurrency receipts name, not just the receipts.

    Three of the four published digests must equal the current bytes exactly.
    The fourth carries ERRATA E12: its published digest stays as recorded, and
    the current bytes are bound to the erratum's second digest, so the file
    cannot move again without failing here.
    """
    status = CONC_STATUS.read_text(encoding="utf-8")
    for rel, published in sorted(CONCURRENCY_SOURCE_PINS.items()):
        v.check(
            f"source_pin.published.{rel}",
            published in status,
            "STATUS.md no longer publishes this digest",
        )
        source = REPO / pathlib.PurePosixPath(rel)
        actual = _sha256_upper(source.read_bytes()) if source.is_file() else ""
        errata = SOURCE_PIN_ERRATA.get(rel)
        if errata is None:
            v.check(
                f"source_pin.binds.{rel}",
                actual == published,
                f"published={published} actual={actual}",
            )
            continue
        recorded_published, recorded_current = errata
        v.check(
            f"source_pin.errata_matches_status.{rel}",
            recorded_published == published,
            "the erratum must quote the digest STATUS.md still publishes",
        )
        v.check(
            f"source_pin.errata_current.{rel}",
            actual == recorded_current,
            f"errata={recorded_current} actual={actual}",
        )
    v.check(
        "source_pin.errata_disclosed",
        "ERRATA E12" in status,
        "STATUS.md must carry the E12 cross-reference beside the stale pin",
    )


def _hosted_era_plan() -> dict[str, Any]:
    """Today's matrix plan, restated as the command manifest of the hosted run."""
    plan = matrix_receipt._json_load(MATRIX / "plan.json")
    for profile, commands in plan["profiles"].items():
        era: list[dict[str, Any]] = []
        for command in commands:
            if command["id"] in HOSTED_ERA_ABSENT_COMMANDS:
                continue
            expected = HOSTED_ERA_EXPECTATIONS.get(command["id"])
            era.append({**command, "expected": expected} if expected else command)
        plan["profiles"][profile] = era
    return plan


def _verify_hosted_rows_against_plan(v: _Verifier) -> None:
    """Replay every committed hosted row through the matrix row validator."""
    plan = _hosted_era_plan()
    for path in sorted(HOSTED_DIR.glob("receipt-*.json")):
        row = strict_ingest.load_safe(path.read_bytes(), label=path.name)
        entry_id = row.get("entry_id")
        try:
            entry = matrix_receipt.find_entry(plan, entry_id)
            error = matrix_receipt._receipt_validation_error(row, entry, plan)
        except Exception as failure:  # noqa: BLE001 - report, never abort
            error = f"{type(failure).__name__}: {failure}"
        expected_error = HOSTED_ERA_ROW_EXCEPTIONS.get(entry_id)
        if expected_error is None:
            v.check(f"hosted.row_validation.{entry_id}", error is None, str(error))
        else:
            v.check(
                f"hosted.row_validation_declared_exception.{entry_id}",
                error == expected_error,
                f"expected={expected_error!r} actual={error!r}",
            )


def _verify_hosted(v: _Verifier) -> None:
    raw = HOSTED_MANIFEST.read_bytes()
    v.check("hosted.manifest_raw_sha256", _sha256_upper(raw) == HOSTED_MANIFEST_RAW_SHA256)
    manifest = strict_ingest.load_safe(raw)
    v.check(
        "hosted.manifest_identity",
        manifest["schema"] == "receiver-reliance/hosted-receipt-manifest-1"
        and manifest["run_id"] == HOSTED_RUN_ID
        and manifest["head_sha"] == HOSTED_HEAD,
    )
    listed = manifest["files"]
    on_disk = {
        p.relative_to(HOSTED_DIR).as_posix()
        for p in HOSTED_DIR.rglob("*")
        if p.is_file() and p.name != "MANIFEST.json"
    }
    v.check(
        "hosted.directory_enumeration",
        on_disk == set(listed),
        f"unlisted={sorted(on_disk - set(listed))} missing={sorted(set(listed) - on_disk)}",
    )
    for rel, entry in sorted(listed.items()):
        data = (HOSTED_DIR / rel).read_bytes() if rel in on_disk else b""
        v.check(
            f"hosted.file_binding.{rel}",
            rel in on_disk
            and len(data) == entry["bytes"]
            and _sha256_upper(data) == entry["sha256"].upper(),
        )

    summary = strict_ingest.load_safe((HOSTED_DIR / "matrix-summary.json").read_bytes())
    v.check("hosted.summary_counts", summary["counts"] == HOSTED_SUMMARY_COUNTS)
    v.check(
        "hosted.summary_gating",
        summary["gating_errors"] == []
        and summary["normative_failures"] == []
        and summary["upstream_job_results"]
        == {"expanded_gate": "success", "normative_matrix": "success"},
    )
    rows = {row["entry_id"]: row for row in summary["rows"]}
    v.check(
        "hosted.summary_row_outcomes",
        {entry_id: row["outcome"] for entry_id, row in rows.items()}
        == HOSTED_ROW_OUTCOMES,
    )
    for entry_id, row in sorted(rows.items()):
        git = row.get("git")
        if not isinstance(git, dict) or git.get("github_sha") is None:
            continue
        if git.get("unavailable") is True:
            # Predeclared synthesized rows never had a checkout: the workflow
            # SHA must still bind, and no execution state may be asserted.
            bound = git.get("sha") is None and git.get("clean") is None
        else:
            bound = git.get("sha") == HOSTED_HEAD and git.get("clean") is True
        v.check(
            f"hosted.summary_source_binding.{entry_id}",
            git["github_sha"] == HOSTED_HEAD and bound,
        )

    sandbox = strict_ingest.load_safe((HOSTED_DIR / "sandbox-receipt.json").read_bytes())
    v.check(
        "hosted.sandbox_verdict",
        sandbox["status"] == "PASS"
        and sandbox["inner_receipt"]["status"] == "PASS"
        and sandbox["git"]["sha"] == HOSTED_HEAD
        and sandbox["git"]["clean"] is True,
    )
    v.check(
        "hosted.sandbox_dockerfile_binding",
        sandbox["image"]["dockerfile_sha256"].upper()
        == _sha256_upper(SANDBOX_DOCKERFILE.read_bytes()),
    )

    gate = strict_ingest.load_safe(
        (HOSTED_DIR / "receipt-expanded-gate-cpython-3-12-ubuntu-latest-x64.json").read_bytes()
    )
    v.check(
        "hosted.gate_verdict",
        gate["outcome"] == "PASS"
        and gate["git"]["github_sha"] == HOSTED_HEAD
        and len(gate["commands"]) == 11,
    )
    v.check(
        "hosted.gate_command_exits",
        all(
            item["exit"] == 0
            and item["timed_out"] is False
            and item["expectation_mismatches"] == []
            for item in gate["commands"]
        ),
    )
    suites = {suite["id"]: suite for suite in gate["suite_counts"]}
    for suite_id, (field, expected) in sorted(HOSTED_GATE_TOTALS.items()):
        suite = suites.get(suite_id, {})
        v.check(
            f"hosted.gate_totals.{suite_id}",
            suite.get(field) == expected
            and all(failure == 0 for failure in suite.get("failures", [])),
        )


def main() -> int:
    verifier = _Verifier()
    _verify_gate_receipt(verifier)
    _verify_rejected(verifier)
    _verify_model_receipts(verifier)
    _verify_concurrency(verifier)
    _verify_source_pins(verifier)
    _verify_hosted(verifier)
    _verify_hosted_rows_against_plan(verifier)
    print(
        f"verify-receipts: checks={verifier.checks} "
        f"failures={len(verifier.failures)}"
    )
    return 1 if verifier.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
