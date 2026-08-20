"""Recompute what the receipts assert, instead of replaying what they recorded.

``verify_receipts.py`` is a REPLAY verifier.  It binds committed receipt bytes,
rehashes the sources they name, and re-runs the recorded transcripts through the
gate validators.  Every one of those properties is worth checking and none of
them can tell you whether the artifact still passes its own gates, because the
transcript it validates was captured in the past.  That gap is not theoretical:
commit 3985356 took ``proof/test_proof_harness.py`` from 7 tests to 9 and left
the charter gate pinned at 7.  The live gate was red for four commits while
``verify_receipts`` reported ``checks=193 failures=0``, truthfully, because the
recorded stdout it replays says "Ran 7 tests".

This program is the recompute half.  It executes the whole charter gate at the
current bytes and holds the live output against both declared
authorities — the gate's own validators and the matrix plan's expectations — and
against what the sealed receipt recorded.  A difference from the sealed receipt
is not a failure by itself, because the sealed receipt describes an earlier era;
it is a failure when nobody declared it.  Undeclared drift is the defect.

    python -B portability/verify_live.py

The summary line is machine-parseable::

    verify-live: gates=<n> passed=<n> declared_era_divergences=<n> \
undeclared_divergences=<n> failures=<n>

Exit 0 only when every gate passes live, the two authorities agree, and every
divergence from the sealed receipt is declared.  Stdlib-only.  It writes no
receipt and needs no clean worktree, so it can be run on any checkout.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[1]
for _extra in ("portability/sandbox", "portability", "portability/matrix"):
    _path = str(REPO / pathlib.PurePosixPath(_extra))
    if _path not in sys.path:
        sys.path.insert(0, _path)

import expanded_gate  # noqa: E402
import receipt as matrix_receipt  # noqa: E402
import strict_ingest  # noqa: E402
import verify_receipts  # noqa: E402

PLAN = REPO / "portability" / "matrix" / "plan.json"
SEALED_GATE = REPO / "portability" / "receipts" / "local-expanded-gate-close.json"

# Charter gate id -> matrix plan command id.  Written out rather than derived by
# string munging, because the two namespaces genuinely differ and a silent
# mistranslation here would weaken the cross-check this program exists to make.
GATE_TO_PLAN_ID = {
    "frozen_0_2_parity": "accepted-0.2",
    "composed_0_3_parity": "composed-0.3-all",
    "grounded_0_4_regression": "grounded-0.4-regression",
    "contract_lint": "contract-lint",
    "lint_gate_meta": "lint-gate-meta",
    "grounded_properties": "grounded-properties",
    "audit_adversarial": "audit-adversarial",
    "synthetic_proof_harness": "synthetic-proof-harness",
    "fuzz_ci_smoke": "seeded-fuzz-smoke",
    "batch_perf": "batch-performance-gate",
    "single_pass_audit_benchmark": "single-pass-benchmark",
    "engine_manifest": "engine-manifest-tests",
    "audit_seal": "audit-seal-tests",
    "observability": "observability-tests",
    "portable_preflight": "portable-preflight-tests",
    "mcp_gate": "mcp-gate-regression",
    "admission_profile": "admission-profile-tests",
    # These two are declared once, in the plan's ``portability_checks``
    # profile, where every focused matrix row already runs them.  A second copy
    # under ``expanded_extra`` would be two declarations of one command that can
    # drift apart, which is the whole failure class this file exists to catch,
    # so the charter binds the declaration that already exists.
    "decision_law_structural": "decision-law-structural",
    "incident_replay_corpus": "incident-replay-corpus",
    "release_identity": "release-identity",
}
if set(GATE_TO_PLAN_ID) != {spec.gate_id for spec in expanded_gate.GATES}:
    raise AssertionError(
        "GATE_TO_PLAN_ID must name exactly the charter's gate_ids: a new "
        "GateSpec needs a matrix plan command to check it a second time"
    )

# Gates the charter gained after the sealed close receipt was written.  The
# sealed receipt cannot carry an observation for a command that did not exist
# when it was recorded, and that absence is not drift — but an absence nobody
# declared is indistinguishable from a gate_id silently renamed, so it is
# declared under the same law as LEGACY_GATE_VALIDATORS.  Derived from the era
# manifest rather than hand-listed, because a hand-listed complement is one more
# copy to forget; main() then checks it against the sealed receipt's own bytes,
# so neither the derivation nor the receipt can drift alone.
POST_SEAL_GATES = frozenset(
    {spec.gate_id for spec in expanded_gate.GATES}
    - set(expanded_gate.SEALED_ERA_GATE_MANIFEST)
)

# What no amount of recomputation here can convert from replay to recompute, and
# why.  Printed on every run so the split is stated rather than assumed.
REPLAY_ONLY = (
    (
        "portability/receipts/hosted/",
        "45 files from hosted matrix run 31562391384: six OS/architecture rows "
        "on three interpreters, plus the daemon-real container gate. Reproducing "
        "them needs that hosted fleet, not this host.",
    ),
    (
        "portability/concurrency/receipts/*release-audit*",
        "the 242,400-envelope normative ladder run (213.937 s) and its smoke "
        "preflight. Re-running the ladder produces new evidence, not these "
        "receipts; ERRATA E12 records that its harness source has since moved.",
    ),
    (
        "portability/model/receipts/N48-*",
        "the independent N=48 refuter enumeration and its 20,531,838 "
        "inadmissible alias edges.",
    ),
    (
        "portability/receipts/local-expanded-gate-*.json",
        "past charter-gate executions at their own heads. This program re-runs "
        "the charter's commands at the current bytes and compares.",
    ),
)


def _run(spec: expanded_gate.GateSpec, environment: dict[str, str]) -> tuple[int, bytes, bytes]:
    cwd = REPO / pathlib.PurePosixPath(spec.cwd).relative_to("/repo")
    completed = subprocess.run(
        [sys.executable, *spec.argv[1:]],
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=expanded_gate.COMMAND_TIMEOUT_SECONDS,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def main() -> int:
    plan = matrix_receipt._json_load(PLAN)
    plan_expected: dict[str, Any] = {}
    for commands in plan["profiles"].values():
        for command in commands:
            plan_expected[command["id"]] = command.get("expected")
    sealed = strict_ingest.load_safe(SEALED_GATE.read_bytes(), label=SEALED_GATE.name)
    sealed_observed = {
        item["gate_id"]: item.get("observed") for item in sealed["commands"]
    }
    absent_from_seal = {
        spec.gate_id
        for spec in expanded_gate.GATES
        if spec.gate_id not in sealed_observed
    }
    if absent_from_seal != POST_SEAL_GATES:
        print(
            "FAIL post_seal_declaration: sealed receipt is missing "
            f"{sorted(absent_from_seal)}; POST_SEAL_GATES declares "
            f"{sorted(POST_SEAL_GATES)}",
            file=sys.stderr,
        )
        return 1

    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "TZ": "UTC",
        }
    )

    print("replayed, and why it cannot be recomputed here:")
    for target, reason in REPLAY_ONLY:
        print(f"  {target}\n      {reason}")
    print(f"recomputed here: the {len(expanded_gate.GATES)}-command charter gate,")
    print("      validated by BOTH the gate's own validators and the matrix plan's")
    print(f"      expectations, at {REPO.name} HEAD as checked out.")
    print()

    passed = 0
    failures: list[str] = []
    declared: list[str] = []
    undeclared: list[str] = []

    for spec in expanded_gate.GATES:
        gate_id = spec.gate_id
        try:
            code, stdout, stderr = _run(spec, environment)
        except subprocess.TimeoutExpired:
            failures.append(f"{gate_id}: timed out")
            print(f"FAIL {gate_id}: timed out")
            continue
        if code != 0:
            failures.append(f"{gate_id}: exited {code}")
            print(f"FAIL {gate_id}: exited {code}")
            continue
        try:
            observed = expanded_gate.validate_gate_output(spec.validator, stdout, stderr)
        except (expanded_gate.GateFailure, UnicodeError, ValueError) as error:
            failures.append(f"{gate_id}: gate validator: {error}")
            print(f"FAIL {gate_id}: gate validator: {error}")
            continue

        # Second, independent authority over the same live bytes.
        plan_id = GATE_TO_PLAN_ID[gate_id]
        expected = plan_expected.get(plan_id)
        if expected is None:
            failures.append(f"{gate_id}: matrix plan declares no expectation for {plan_id}")
            print(f"FAIL {gate_id}: matrix plan declares no expectation for {plan_id}")
            continue
        actual = matrix_receipt.parse_suite_counts(stdout, stderr)
        mismatches = matrix_receipt._expectation_mismatches(expected, actual)
        if mismatches:
            failures.append(f"{gate_id}: matrix plan: {'; '.join(mismatches)}")
            print(f"FAIL {gate_id}: matrix plan: {'; '.join(mismatches)}")
            continue

        passed += 1
        recorded = sealed_observed.get(gate_id)
        if recorded == observed:
            print(f"PASS {gate_id} {json.dumps(observed, sort_keys=True)}")
            continue
        if gate_id in POST_SEAL_GATES:
            live = json.dumps(observed, sort_keys=True)
            declared.append(f"{gate_id} (added after the sealed era): live={live}")
            print(f"PASS {gate_id} declared post-seal gate; live={live}")
            continue
        era = verify_receipts.LEGACY_GATE_VALIDATORS.get(gate_id)
        detail = (
            f"sealed={json.dumps(recorded, sort_keys=True)} "
            f"live={json.dumps(observed, sort_keys=True)}"
        )
        if era is None:
            undeclared.append(f"{gate_id}: {detail}")
            print(f"UNDECLARED-DIVERGENCE {gate_id} {detail}")
        else:
            declared.append(f"{gate_id} (era validator {era}): {detail}")
            print(f"PASS {gate_id} declared era divergence via {era}; {detail}")

    print()
    print(
        f"verify-live: gates={len(expanded_gate.GATES)} passed={passed} "
        f"declared_era_divergences={len(declared)} "
        f"undeclared_divergences={len(undeclared)} failures={len(failures)}"
    )
    for line in failures + undeclared:
        print(f"  {line}", file=sys.stderr)
    return 1 if failures or undeclared else 0


if __name__ == "__main__":
    raise SystemExit(main())
