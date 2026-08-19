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

# Event B (2026-08-19): the re-execution witness E12 and F-CONC-004 named as
# absent since the first disclosed move.  A full normative ladder run at the
# fourth-move bytes reproduced the sealed run's totals exactly -- 32 worker
# runs, 242,400 audited envelopes -- and a smoke sibling matches the v3
# shape.  Each is bound to its own recorded clean head; the v3 receipts above
# stay sealed chronology.
RECONC_NORMATIVE = (
    REPO / "portability" / "concurrency" / "receipts"
    / "normative-regeneration-head-2f29e6b-attempt1.json"
)
RECONC_SMOKE = (
    REPO / "portability" / "concurrency" / "receipts"
    / "smoke-regeneration-head-93a659f-attempt1.json"
)
RECONC_NORMATIVE_RAW_SHA256 = (
    "609AB7983085B14EFF78BCF68A4F327FB6B00C4332D5F8E2705C9A62CF781484"
)
RECONC_SMOKE_RAW_SHA256 = (
    "069F6072023DD1258215620E780CC54F8B8764B0BE807DAEFA8AAFF9F7438BB7"
)
RECONC_NORMATIVE_HEAD = "2f29e6b3ae3e5daaf95052ce24edf9a60ea1eb6c"
RECONC_SMOKE_HEAD = "93a659fa4163b9b4d7c8c35c2444abd6abcbe713"

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
# commit that bound the clean v3 receipts.  The pin is deliberately NOT
# refreshed: rewriting it would assert that today's bytes produced the recorded
# 213.937-second run, which is false.  The erratum records the published digest
# and the digest of the current bytes instead, so the stale pin stays honest and
# no undisclosed move can hide behind a disclosed one.  Four changes have moved
# the file since the binding, all four recorded in ERRATA E12:
#   ca1ccfe  AUDITED_FORMAT_VERSION 0.4 -> 0.4.1, the F-MATRIX-016 migration
#            (digest D40F692A...).
#   the pinned_tools adoption, which replaced the ladder's bare ``git`` argv
#            with pinned_tools.git() (digest 7CF10CC6...).  This guard is what
#            forced that second move to be disclosed rather than absorbed.
#   the 0.4.2 count-migration completion: AUDITED_FORMAT_VERSION 0.4.1 -> 0.4.2
#            after 0ff243c moved the audit format and left this pin behind;
#            the hosted normative cells rejected every fresh envelope
#            (audited_envelope_version) until it moved (digest CB7D1FA5...).
#   the ERRATA E15 redaction adoption, which routed the ladder receipt through
#            portability/receipt_paths.py at its single write boundary so a
#            new receipt stops recording the operator home directory in
#            runtime.executable and in a controller traceback (digest CD725088...).
#            The fourth move, and the second this guard forced into disclosure
#            rather than an author remembering to record it.
# path -> (digest published in STATUS.md, digest of the current bytes).
SOURCE_PIN_ERRATA = {
    "portability/concurrency/ladder.py": (
        "B5436C851C849CFB2B39A7EC2B35C258E501E3171A2ECD6BE6AF913329CC27E6",
        "CD725088C497E36BA9906DB49104F451ECBB7AA1DCF3C2E3F9627722B81050E3",
    ),
}

# Hardening-branch evidence: the clean-tree charter gate re-run after the E13
# repair, on CURRENT suite counts.  This is the only committed gate receipt whose
# observations equal what the suites produce today; the two below it record their
# own eras and replay through LEGACY_GATE_VALIDATORS.  It is bound
# here so the recompute is custody-tracked, not just asserted in prose.
# Regenerated at the 0.4.2 commit, and again at the 19-gate charter
# extension (506829e), where the eleven-command receipts became era history.  This receipt is checked with
# era_validators=False -- its whole purpose is to be at CURRENT suite counts, so
# when the grounded suite moved 517 -> 521 it had to be re-recorded rather than
# era-mapped.  The 7d1c6cb receipt stays on disk as immutable chronology; it is
# simply no longer the current-counts binding.
#
# REGENERATION IS DUE.  The charter gate grew from eleven commands to nineteen,
# so this receipt's recorded manifest is a prefix of the live one and
# `hardening_gate.manifest_order` is RED by design.  Faking it would mean
# era-mapping the one receipt whose entire purpose is to be un-era-mapped.
# At the FINAL merged tip, with a clean worktree (the runner refuses a dirty
# one, and refuses to overwrite an existing receipt):
#
#   python -B portability/run_local_expanded_gate.py \
#       --receipt portability/receipts/local-expanded-gate-hardening-<head7>.json
#
# <head7> is the first seven characters of that tip, the convention 0ff243c and
# 7d1c6cb already follow.  Then rebind the four constants below from that run:
# HARDENING_GATE_RECEIPT to the new filename, HARDENING_SOURCE_HEAD to the full
# 40-character head the receipt records in `git.head`, HARDENING_GATE_RAW_SHA256
# to the uppercase SHA-256 of the file's bytes, and
# HARDENING_GATE_EMBEDDED_SHA256 to the receipt's own `receipt_sha256` member.
#
# THE REGENERATION ALSO MOVES THIS PROGRAM'S OWN CHECK COUNT, and that is not
# optional bookkeeping: _verify_clean_gate_receipt spends three checks per
# recorded command (.exit, .stream_binding, .validator_rerun), so a hardening
# receipt carrying N commands instead of eleven takes the total from 267 to
# 267 + 3 * (N - 11).  At N = 19 that is 291, measured, not predicted.  Four
# pins carry the old number and move in the SAME commit as the rebinding above,
# or this program's own gate rejects it:
#   portability/matrix/plan.json        verify-committed-receipts expected
#   portability/test_strict_ingest.py   test_verify_receipts_reports_its_pinned_
#                                       check_count, and its docstring
#   README.md                           "Expected: verify-receipts: checks=267"
#   DIAGRAMS.md                         the C4 Replay row and the C4 Sources
#                                       quote of that README line
# HOSTED_ERA_EXPECTATIONS["verify-committed-receipts"] stays at 62: that is the
# hosted era's count and does not move.  They are deliberately NOT pre-migrated
# here, because until the rebinding lands this program really does report 267
# and a pin describing a state that does not exist yet is the defect this file
# exists to catch.
#
# Then, in this order: verify_receipts <new count>/0, then verify_live green at
# gates=19, then portability/test_strict_ingest.py green -- it runs
# verify_receipts end to end, so it is red until this binding is current and is
# the second observation of this one root cause, not a second defect.  The old
# receipt stays on disk as chronology, exactly as 7d1c6cb did.
HARDENING_GATE_RECEIPT = (
    REPO / "portability" / "receipts" / "local-expanded-gate-hardening-506829e.json"
)
HARDENING_SOURCE_HEAD = "506829ed245c05eaf71c09bbd5b19475e7e9d08c"
HARDENING_GATE_RAW_SHA256 = (
    "2964947C99C5F8B39FDE5189FB048EB88B4AA6690A4B35F0A43A1864825FC3CD"
)
HARDENING_GATE_EMBEDDED_SHA256 = (
    "82B96D1751C596F4D6EFA38C62B0C225028FFD379C625CE6D7B60AB59AB08291"
)

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
    # 0.4.2 sealed the decision table into governing_authorities, which added
    # four mutation arms to the grounded suite: 517 -> 521.  The GateSpec now
    # says checks_521; every sealed receipt keeps its own era's count here.
    # Same law as checks_504 below and unittest_7 further down -- a pinned
    # program-era truth moves in the same change as the truth (F-MATRIX-013..017).
    "grounded_0_4_regression": "checks_504",
    "lint_gate_meta": "checks_7",
    # 3985356 added two regressions to proof/test_proof_harness.py, taking it
    # from 7 tests to 9, and left the GateSpec pinned at unittest_7.  The live
    # charter gate went red at gate 8 of 11 and stayed red for four commits
    # while this file kept reporting green, because it replays recorded stdout
    # that says "Ran 7 tests".  The GateSpec now says unittest_9; the sealed
    # receipts keep their own era's count here.
    "synthetic_proof_harness": "unittest_7",
}
# The same law, applied to the manifest instead of a count.  Both sealed
# portability-era receipts recorded the eleven-command charter; the charter has
# since grown, and checking sealed bytes against a charter written after them
# would make immutable chronology permanently red for having been recorded on
# time.  Only receipts carrying era_validators=True get this reading.  The
# hardening receipt deliberately does not: it is the current-counts binding, so
# it is held against the live GATES manifest and goes red the moment the charter
# set moves, which is the signal that says regenerate it.  The manifest itself
# is declared once, beside the charter it is the ancestor of.
LEGACY_GATE_MANIFEST = expanded_gate.SEALED_ERA_GATE_MANIFEST
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
#
# The decision-law and incident-replay lanes landed later still and moved the
# planned count 18 to 20.  The hosted rows could not have executed either
# command, so they join the same era declaration rather than being validated
# against a manifest that postdates them.  This gate is what caught the
# addition: adding the two plan rows alone took it to 23 failures.
#
# The consumer-surface sweep then moved the planned count 20 to 42 by putting
# every remaining deterministic suite -- the engine and audit-seal gates, the
# admission profile, the four adapter surfaces including the MCP gate, the
# ingest/tool-pinning/home-path gates, the authority and public-surface gates,
# the wrapper-hardening and WP4 artifact verifiers, and the conformance
# authority gate -- on every normative cell.  None of them existed in run
# 31562391384's manifest either, so all twenty-two join the same declaration.
# With them absent the hosted era stays exactly the 17-command manifest that
# run executed, which is the invariant this tuple exists to hold.
#
# The charter-gate extension then mirrored six of those suites into the
# expanded profile, which composes from baseline_nonperformance +
# expanded_extra and never sees portability_checks.  Three of its ids are
# already declared above; the other three (the expanded profile's own names
# for the observability, preflight and MCP-gate commands) join here.  Same
# declaration, same reason: run 31562391384's expanded manifest predates
# them all.
HOSTED_ERA_ABSENT_COMMANDS = (
    "portable-bundle-gate",
    "decision-law-structural",
    "incident-replay-corpus",
    "engine-manifest-check",
    "engine-manifest-tests",
    "audit-seal-tests",
    "observer-equivalence-tests",
    "admission-profile-tests",
    "admission-extent-check",
    "outcome-receipt-tests",
    "outcome-receipt-check",
    "reference-host-tests",
    "adapter-fixture-provenance",
    "mcp-gate-calibration",
    "mcp-gate-tests",
    "mcp-gate-demo",
    "strict-ingest-tests",
    "pinned-tools-tests",
    "home-path-disclosure-tests",
    "authority-legibility-tests",
    "authority-table-check",
    "public-surface-tests",
    "wrapper-hardening-tests",
    "second-implementation-artifacts",
    "conformance-authority",
    "observability-tests",
    "portable-preflight-tests",
    "mcp-gate-regression",
)
HOSTED_ERA_EXPECTATIONS = {
    "verify-committed-receipts": {"checks": [62], "failures": [0]},
    "grounded-0.4-regression": {"checks": [504], "failures": [0]},
    "lint-gate-meta": {"checks": [7], "failures": [0]},
    "synthetic-proof-harness": {"tests": [7]},
    # Both moved by the W6 zero-cascade regressions: the matrix suite gained six
    # ambiguity cases and the sandbox suite seven.  The hosted run recorded 48
    # and 77, and this gate is what caught the plan.json migration leaving the
    # era declaration behind.
    "matrix-receipt-tests": {"tests": [48]},
    "sandbox-spec-tests": {"tests": [77]},
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
    era_validators: bool = True,
) -> None:
    """Re-derive one charter-gate receipt, byte for byte.

    ``era_validators`` selects which law the recorded transcripts replay under.
    The two portability-era receipts need their own era's counts, which is what
    LEGACY_GATE_VALIDATORS supplies.  A receipt recorded at current suite counts
    must NOT get that indulgence: it replays under the live validators, so if a
    suite moves after it was written, this fails rather than quietly agreeing.
    """
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
    expected_manifest = (
        list(LEGACY_GATE_MANIFEST)
        if era_validators
        else [spec.gate_id for spec in expanded_gate.GATES]
    )
    v.check(
        f"{prefix}.manifest_order",
        [item["gate_id"] for item in commands] == expected_manifest,
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
        validator = (
            LEGACY_GATE_VALIDATORS.get(gate_id, spec.validator)
            if era_validators
            else spec.validator
        )
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
    _verify_clean_gate_receipt(
        v,
        "hardening_gate",
        HARDENING_GATE_RECEIPT,
        HARDENING_GATE_RAW_SHA256,
        HARDENING_GATE_EMBEDDED_SHA256,
        HARDENING_SOURCE_HEAD,
        era_validators=False,
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


def _contained_source(name: str, *roots: pathlib.Path) -> pathlib.Path | None:
    """Resolve a receipt-supplied source name inside one of the custody roots.

    The name comes from inside a receipt, so it is lower-trust input even after
    the receipt's raw digest matched.  Before this check it was joined straight
    onto ``portability/model`` and then probed and read, so a name carrying
    ``..`` or an absolute spelling reached the filesystem outside custody
    (csf_f1c9c558).  Returns None when the name is not admissible; the caller
    turns that into a recorded failure rather than a dereference.
    """
    if not name or name != name.strip():
        return None
    pure = pathlib.PurePosixPath(name)
    if pure.is_absolute() or any(
        part in ("", ".", "..") for part in pure.parts
    ):
        return None
    if "\\" in name or ":" in name:
        return None
    for root in roots:
        candidate = root / pure
        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(root.resolve())
        except (OSError, ValueError):
            continue
        if resolved.is_file():
            return resolved
    return None


def _verify_model_receipts(v: _Verifier) -> None:
    raw = REFUTER_RECEIPT.read_bytes()
    raw_bound = _sha256_upper(raw) == REFUTER_RAW_SHA256
    v.check("refuter.raw_sha256", raw_bound)
    if not raw_bound:
        # A receipt whose bytes do not match its published digest is not
        # evidence, and its contents must not steer further filesystem work.
        # Before this guard every subsequent check kept consuming the mismatched
        # document, including the source names it supplies (csf_f1c9c558).
        v.check("refuter.mismatch_halts_dereference", False, "raw digest mismatch")
        return
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
    model_root = REPO / "portability" / "model"
    for name, recorded in sorted(doc["source_sha256"].items()):
        candidate = _contained_source(name, model_root, model_root / "receipts")
        v.check(
            f"refuter.source_binding.{name}",
            candidate is not None
            and _sha256_upper(candidate.read_bytes()) == recorded,
            "name escapes the model custody roots" if candidate is None else "",
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
    # The regeneration pair: same recompute, each bound to its own clean head.
    for label, path, raw_sha, head in (
        (
            "concurrency.regeneration.normative",
            RECONC_NORMATIVE,
            RECONC_NORMATIVE_RAW_SHA256,
            RECONC_NORMATIVE_HEAD,
        ),
        (
            "concurrency.regeneration.smoke",
            RECONC_SMOKE,
            RECONC_SMOKE_RAW_SHA256,
            RECONC_SMOKE_HEAD,
        ),
    ):
        raw = path.read_bytes()
        v.check(f"{label}.raw_sha256", _sha256_upper(raw) == raw_sha)
        doc = strict_ingest.load_safe(raw)
        v.check(
            f"{label}.clean_source_binding",
            doc["status"] == "PASS"
            and doc["git"]["clean"] is True
            and doc["git"]["head"] == head,
        )
    regen = strict_ingest.load_safe(RECONC_NORMATIVE.read_bytes())
    runs = 0
    envelopes = 0
    for section in list(regen["levels"]) + list(regen["soaks"]):
        participants = section["participants"]
        for mode in section["modes"]:
            for run in mode["runs"]:
                runs += 1
                envelopes += participants * run["requests_per_caller"]
    v.check("concurrency.regeneration.worker_runs", runs == CONC_WORKER_RUNS)
    v.check(
        "concurrency.regeneration.audited_envelopes",
        envelopes == CONC_AUDITED_ENVELOPES,
    )


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


def _hosted_row_error(plan: dict[str, Any], row: dict[str, Any]) -> str | None:
    """Validate one hosted row under the hosted era own binding authority.

    The committed hosted tree is run 31562391384 at HOSTED_HEAD.  That commit,
    not whatever commit the verifying process happens to sit on, is the run
    these receipts must belong to -- the law LEGACY_GATE_VALIDATORS already
    applies to sealed transcripts, moved to the row validator.  This is the
    single site that supplies the authority; RunCurrencyAuthorityTests in
    portability/matrix/test_receipt.py calls this function with a forged
    foreign-run row and requires rejection, so dropping the argument here goes
    red there.
    """
    try:
        entry = matrix_receipt.find_entry(plan, row.get("entry_id"))
        return matrix_receipt._receipt_validation_error(row, entry, plan, HOSTED_HEAD)
    except Exception as failure:  # noqa: BLE001 - report, never abort
        return f"{type(failure).__name__}: {failure}"


def _verify_hosted_rows_against_plan(v: _Verifier) -> None:
    """Replay every committed hosted row through the matrix row validator."""
    plan = _hosted_era_plan()
    for path in sorted(HOSTED_DIR.glob("receipt-*.json")):
        row = strict_ingest.load_safe(path.read_bytes(), label=path.name)
        entry_id = row.get("entry_id")
        error = _hosted_row_error(plan, row)
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
