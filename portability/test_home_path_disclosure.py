"""Enforce ERRATA E15's disclosure of maintainer home-directory paths.

E15 discloses that tracked files in this public repository record absolute
paths under the maintainer's home directory. Before this gate existed the
disclosure said "ten" and the true count was fifty-two, so the one page whose
job is exhaustive honesty could be falsified by a single grep. That is the
failure class the repository already names twice (a claim that documents a
risk without retiring it, and a control that sits outside the decision path),
so the fix is not only to correct the number but to make the number checkable.

This gate RECOMPUTES from current bytes. It enumerates the tracked files, reads
each one, and compares the set that actually carries a home-directory path
against the declared inventory below. Any new instance fails; any declared
instance that disappears also fails, because a silently shrinking disclosure is
a stale disclosure. It replays nothing.

The pattern is assembled from fragments so that this file is not itself an
instance of what it searches for.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO / "portability") not in sys.path:
    sys.path.insert(0, str(REPO / "portability"))

import pinned_tools  # noqa: E402

# Assembled, never written literally: this file must not match its own search.
_USERS = "Users"
_ACCOUNT = "james"
# A character class holding both separators, built without writing either
# escape literally, so this file stays outside its own search.
_SEP = "[/" + chr(92) + chr(92) + "]"
HOME_PATH = re.compile(
    _USERS + _SEP + "+" + _ACCOUNT + "(?=" + _SEP + "|$)", re.IGNORECASE
)

# ERRATA E15's table, as data. Class meanings:
#   frozen    - digest-pinned by another tracked file, a manifest, or a
#               candidate-file receipt row. Editing destroys what it attests.
#   recorded  - not digest-pinned, but a record of an observed run or a
#               historical witness pinned on purpose. Editing it would make the
#               repository's evidence disagree with what was observed.
# There is no third class: nothing here is both unpinned and non-evidentiary.
DECLARED: dict[str, str] = {
    "adapters/fixtures/parent_corpus_408.jsonl": "frozen",
    "orchestration/FUZZ_CAMPAIGN.md": "recorded",
    "orchestration/MATRIX.md": "recorded",
    "orchestration/fuzz-streams/T1B_SOL.md": "recorded",
    "orchestration/fuzz-streams/T1C_SOL.md": "recorded",
    "orchestration/refuters/RI2.md": "frozen",
    "orchestration/refuters/RI3.md": "frozen",
    "orchestration/refuters/RI4.md": "frozen",
    "perf/PROFILE_BASELINE.md": "frozen",
    "perf/receipts/robustness/profile-windows-cpython-3.12-20260811-attempt2.json": "frozen",
    "perf/receipts/robustness/profile-windows-cpython-3.12-20260811.json": "frozen",
    "perf/receipts/robustness/profile-windows-cpython-3.12-20260812-attempt3.json": "frozen",
    "perf/receipts/robustness/profile-windows-cpython-3.12-20260812-attempt4.json": "frozen",
    "perf/receipts/robustness/profile-windows-cpython-3.12-20260812-attempt5.json": "frozen",
    "perf/receipts/robustness/profile-windows-cpython-3.12-20260812-attempt6.json": "frozen",
    "perf/receipts/robustness/profile-windows-cpython-3.12-20260812-attempt7.json": "frozen",
    "perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260811-attempt2.json": "frozen",
    "perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260811.json": "frozen",
    "perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260812-attempt10.json": "frozen",
    "perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260812-attempt3.json": "frozen",
    "perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260812-attempt4.json": "frozen",
    "perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260812-attempt5.json": "frozen",
    "perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260812-attempt6.json": "frozen",
    "perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260812-attempt7.json": "frozen",
    "perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260812-attempt8.json": "frozen",
    "perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260812-attempt9.json": "frozen",
    "portability/concurrency/receipts/normative-clean-oracle-attempt2.json": "frozen",
    "portability/concurrency/receipts/normative-correction-attempt1.json": "recorded",
    "portability/concurrency/receipts/normative-correction-attempt3.json": "frozen",
    "portability/concurrency/receipts/normative-release-audit-head-8a525b1-attempt3.json": "frozen",
    "portability/concurrency/receipts/smoke-correction-attempt1.json": "recorded",
    "portability/concurrency/receipts/smoke-correction-attempt3.json": "frozen",
    "portability/concurrency/receipts/smoke-release-audit-head-8a525b1-attempt3.json": "frozen",
    "portability/concurrency/receipts/smoke.json": "recorded",
    "portability/model/receipts/N48-POST-F-MODEL-003-SUMMARY.md": "recorded",
    "portability/model/receipts/N48-independent-refuter-20260811.json": "frozen",
    "portability/model/receipts/N48-postF3-attempt1.memsample.txt": "frozen",
    "portability/oracle/findings/F-ORACLE-001.md": "frozen",
    "portability/oracle/findings/F-ORACLE-002.md": "frozen",
    "portability/oracle/findings/F-ORACLE-003.md": "frozen",
    "portability/oracle/findings/F-ORACLE-004.md": "frozen",
    "portability/oracle/findings/F-ORACLE-005.md": "frozen",
    "portability/receipts/local-expanded-gate-close.json": "frozen",
    "portability/receipts/local-expanded-gate-release-audit-rejected1.json": "frozen",
    "portability/receipts/local-expanded-gate-release-audit-rejected2.json": "frozen",
    "portability/receipts/local-expanded-gate-release-audit.json": "frozen",
    "portability/sandbox/F-SANDBOX-018.md": "recorded",
    "portability/sandbox/F-SANDBOX-019.md": "recorded",
    "portability/sandbox/F-SANDBOX-020.md": "recorded",
    "portability/sandbox/F-SANDBOX-021.md": "recorded",
    "portability/sandbox/test_sandbox.py": "recorded",
    "second-implementation/PROVENANCE.md": "frozen",
}
DECLARED_TOTAL = 52


def _classify(path: str) -> str | None:
    return DECLARED.get(path)


def _tracked() -> list[str]:
    out = subprocess.run(
        [pinned_tools.git(), "-C", str(REPO), "ls-files", "-z"],
        capture_output=True,
        check=True,
    ).stdout
    return [p.decode("utf-8") for p in out.split(b"\0") if p]


def main() -> int:
    failures: list[str] = []
    observed: dict[str, str] = {}

    for rel in _tracked():
        try:
            data = (REPO / rel).read_bytes()
        except (OSError, ValueError):
            continue
        text = data.decode("utf-8", errors="ignore")
        if HOME_PATH.search(text):
            cls = _classify(rel)
            if cls is None:
                failures.append(
                    f"UNDECLARED: {rel} records a maintainer home-directory path "
                    f"and is not in ERRATA E15's disclosure"
                )
            else:
                observed[rel] = cls

    for rel in DECLARED:
        if rel not in observed:
            failures.append(
                f"STALE: ERRATA E15 declares {rel} but it no longer records a "
                f"home-directory path; correct the disclosure"
            )

    if len(observed) != DECLARED_TOTAL:
        failures.append(
            f"COUNT: ERRATA E15 declares {DECLARED_TOTAL} files; "
            f"{len(observed)} observed"
        )

    counts = {"frozen": 0, "recorded": 0}
    for cls in observed.values():
        counts[cls] += 1

    print(
        "home-path-disclosure: "
        + json.dumps(
            {
                "declared": DECLARED_TOTAL,
                "observed": len(observed),
                "frozen": counts["frozen"],
                "recorded": counts["recorded"],
                "failures": len(failures),
            },
            sort_keys=True,
        )
    )
    for line in failures:
        print("  " + line)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
