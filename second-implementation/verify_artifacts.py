"""Verify WP4 receipt bindings, import closure, and runtime read set."""

from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from unittest import mock


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from raw_preflight_cases import raw_cases  # noqa: E402
from rr2 import (  # noqa: E402
    AUTHORITY_PATHS,
    PACKET_REL,
    PACKET_URI,
    PRIMARY_CONTRACT_REL,
    PROJECTION_REL,
    PROJECTION_URI,
    SUPPLEMENTAL_CONTRACT_REL,
    SUPPLEMENTAL_CONTRACT_SHA256,
    Contracts,
    sha256_upper,
)


AUTHOR_RECEIPT = HERE / "receipts/AUTHOR_INCREMENT_RECEIPT_0_1.json"
PREFLIGHT_RECEIPT = HERE / "receipts/BOUNDED_DEEP_PREFLIGHT_0_1.json"
COVERAGE_RECEIPT = HERE / "receipts/COVERAGE_STEERING_SMOKE_0_1.json"
SUPPLEMENTAL_ACCEPTANCE_RECEIPT = ROOT / "supplemental-0_3/receipts/SUPPLEMENTAL_FIXTURE_ACCEPTANCE_RECEIPT_0_3.json"
REQUIRED_STEERING = {
    "_dispatch",
    "_eval_atomic",
    "_execute",
    "_parse",
    "classify",
    "eval_predicate",
    "schema_errors",
}
EXPECTED_CANDIDATE_PATHS = {
    "second-implementation/PROVENANCE.md",
    "second-implementation/README.md",
    "second-implementation/bounded_preflight.py",
    "second-implementation/cli.py",
    "second-implementation/coverage_campaign.py",
    "second-implementation/findings/F-WP4-001.md",
    "second-implementation/findings/F-WP4-002.md",
    "second-implementation/findings/F-WP4-003.md",
    "second-implementation/findings/F-WP4-004.md",
    "second-implementation/findings/F-WP4-005.md",
    "second-implementation/findings/F-WP4-006.md",
    "second-implementation/findings/F-WP4-007.md",
    "second-implementation/process_harness.py",
    "second-implementation/raw_preflight_cases.py",
    "second-implementation/rr2.py",
    "second-implementation/test_cross.py",
    "second-implementation/verify_artifacts.py",
    "orchestration/REIMPLEMENTERS_GUIDE.md",
}


def _load_json(path: Path):
    return json.loads(path.read_bytes().decode("utf-8"))


def _record(failures: list[str], condition: bool, name: str) -> None:
    if not condition:
        failures.append(name)


def _verify_authority_provenance(failures: list[str]) -> tuple[int, int]:
    acceptance_raw = SUPPLEMENTAL_ACCEPTANCE_RECEIPT.read_bytes()
    matches = re.findall(rb'"contract_raw_sha256"\s*:\s*"([A-F0-9]{64})"', acceptance_raw)
    _record(failures, matches == [SUPPLEMENTAL_CONTRACT_SHA256.encode("ascii")], "supplemental-external-digest")

    original_read_bytes = Path.read_bytes
    reads: list[Path] = []

    def logged_read_bytes(path: Path) -> bytes:
        reads.append(path.resolve())
        return original_read_bytes(path)

    with mock.patch.object(Path, "read_bytes", logged_read_bytes):
        contracts = Contracts(ROOT)

    expected_reads = Counter((ROOT / rel).resolve() for rel in AUTHORITY_PATHS)
    actual_reads = Counter(reads)
    _record(failures, actual_reads == expected_reads, "runtime-authority-read-set")

    primary = contracts.supp["generation_basis"]["accepted_0_2"]["contract"]
    declared = {
        PRIMARY_CONTRACT_REL: (primary["byte_length"], primary["raw_sha256"]),
        PACKET_REL: contracts._resolver_pin(  # noqa: SLF001 - verifier checks the exact runtime declaration path
            PACKET_URI,
            expected_path="../../access/SANITIZED_PRIMARY_BASELINE_IMPLEMENTER_PACKET_0_1.json",
            rel=PACKET_REL,
        ),
        PROJECTION_REL: contracts._resolver_pin(  # noqa: SLF001
            PROJECTION_URI,
            expected_path="../../access/A2_SHARED_DOMAIN_VOCABULARY_BASELINE_PROJECTION_0_1.schema.json",
            rel=PROJECTION_REL,
        ),
    }
    for rel, (length, digest) in declared.items():
        raw = (ROOT / rel).read_bytes()
        _record(failures, len(raw) == length and sha256_upper(raw) == digest, "declared-authority-pin:" + rel)
    supplemental_raw = (ROOT / SUPPLEMENTAL_CONTRACT_REL).read_bytes()
    _record(failures, sha256_upper(supplemental_raw) == SUPPLEMENTAL_CONTRACT_SHA256, "supplemental-runtime-pin")
    return len(actual_reads), len(declared) + 1


def _verify_imports(failures: list[str]) -> tuple[int, int]:
    python_files = sorted(HERE.glob("*.py"))
    local_modules = {path.stem for path in python_files}
    allowed = set(sys.stdlib_module_names) | local_modules | {"__future__"}
    imported: set[str] = set()
    frozen_source_prefix = "baseline-run/" + "implementation-output"
    for path in python_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        if frozen_source_prefix in source.replace("\\", "/") and path.name != "coverage_campaign.py":
            failures.append("frozen-source-path-outside-blackbox:" + path.name)
    _record(failures, imported <= allowed, "non-stdlib-imports:" + ",".join(sorted(imported - allowed)))

    runtime_allowed = {
        "__future__", "base64", "binascii", "hashlib", "json", "pathlib", "re", "rr2", "sys", "typing", "unicodedata"
    }
    runtime_imports: set[str] = set()
    for name in ("rr2.py", "cli.py"):
        tree = ast.parse((HERE / name).read_text(encoding="utf-8"), filename=name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                runtime_imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                runtime_imports.add(node.module.split(".", 1)[0])
    _record(failures, runtime_imports <= runtime_allowed, "runtime-import-closure")
    return len(python_files), len(imported)


def _verify_receipts(failures: list[str]) -> tuple[int, int]:
    author = _load_json(AUTHOR_RECEIPT)
    preflight = _load_json(PREFLIGHT_RECEIPT)
    coverage = _load_json(COVERAGE_RECEIPT)

    candidate_rows = author.get("candidate_files", [])
    candidate_paths = {row.get("path") for row in candidate_rows}
    _record(failures, candidate_paths == EXPECTED_CANDIDATE_PATHS, "author-candidate-path-set")
    for row in candidate_rows:
        path = ROOT / row["path"]
        _record(failures, path.is_file() and sha256_upper(path.read_bytes()) == row.get("raw_sha256"), "author-file-hash:" + row["path"])

    subordinate = (
        ("bounded_raw_preflight_receipt", PREFLIGHT_RECEIPT, preflight),
        ("coverage_steering_smoke_receipt", COVERAGE_RECEIPT, coverage),
    )
    for key, path, receipt in subordinate:
        binding = author.get(key, {})
        _record(failures, sha256_upper(path.read_bytes()) == binding.get("raw_sha256"), "author-subreceipt-hash:" + key)
        _record(failures, receipt.get("divergence_count") == 0 and receipt.get("status") == "PASS", "subreceipt-status:" + key)

    stream = hashlib.sha256()
    names: list[str] = []
    families: Counter[str] = Counter()
    for identity, case in enumerate(raw_cases()):
        digest = hashlib.sha256(case.raw).digest()
        stream.update(identity.to_bytes(8, "big")); stream.update(digest)
        names.append(case.name)
        families[case.family] += 1
    _record(failures, preflight.get("case_names") == names, "preflight-case-set")
    _record(failures, preflight.get("executed_cases") == len(names), "preflight-case-count")
    _record(failures, preflight.get("family_counts") == dict(sorted(families.items())), "preflight-family-counts")
    _record(failures, preflight.get("stream_sha256") == stream.hexdigest().upper(), "preflight-stream")
    _record(failures, preflight.get("surfaces_per_case") == ["frozen-composed-reference-black-box", "candidate-api", "candidate-cli"], "preflight-surfaces")

    required = set(coverage.get("steering_code_objects_required", []))
    falsifier = coverage.get("execute_only_falsifier", {})
    _record(failures, required == REQUIRED_STEERING, "coverage-required-set")
    _record(failures, not coverage.get("steering_code_objects_missing_monitored"), "coverage-missing-monitored")
    _record(failures, not coverage.get("steering_code_objects_missing_observed"), "coverage-missing-observed")
    _record(failures, coverage.get("steering_requirements_satisfied") is True, "coverage-required-observed")
    _record(failures, falsifier.get("rejected") is True and bool(falsifier.get("missing_monitored")) and bool(falsifier.get("missing_observed")), "coverage-execute-only-falsifier")
    _record(failures, coverage.get("requested_identities", 50_000) < 50_000, "coverage-smoke-nonqualifying")
    _record(failures, author.get("house_scale_campaign_receipt") is None, "house-campaign-not-launched")
    _record(failures, author.get("official_author_strike_count") == 2, "author-strike-count")
    return len(candidate_rows), len(names)


def main() -> int:
    failures: list[str] = []
    runtime_reads, authority_pins = _verify_authority_provenance(failures)
    python_files, import_roots = _verify_imports(failures)
    candidate_files, raw_cases_count = _verify_receipts(failures)
    result = {
        "authority_pins_verified": authority_pins,
        "candidate_files_verified": candidate_files,
        "failures": failures,
        "import_roots_observed": import_roots,
        "python_files_censused": python_files,
        "raw_preflight_cases_rebound": raw_cases_count,
        "runtime_authority_reads": runtime_reads,
        "status": "PASS" if not failures else "FAIL",
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
