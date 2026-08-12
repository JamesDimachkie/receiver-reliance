"""Fail-closed branch hygiene check with custody-bound raw-receipt exceptions.

The four admitted model captures preserve CRLF bytes under ``* -text``.
Git therefore reports their carriage returns as trailing whitespace.  Those
bytes cannot be normalized without invalidating the published SHA-256 values.
The merged blind-review evidence file ``evidence/A1_CAPABILITY_FLOOR_0_1.md``
is admitted on the same terms: its single trailing-whitespace byte (line 5)
is sealed by the published ``gate0_a1_pin`` byte length and raw SHA-256 in
``supplemental-0_3/A1_FLOOR_COUNT_SUPPLEMENTAL_REGISTER_0_1.json``, so it
cannot be normalized either.  This verifier admits exactly the known warning
counts only while each complete file retains its admitted hash; every other
``git diff --check`` diagnostic is an error.
"""
from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
BASE = "4e788d21e882a30bdda2aec3f780537161f81644"
ALLOWED = {
    "portability/model/receipts/N48-postF3-attempt1.memsample.txt": (
        76,
        "55FD53A62677D3FEAAF43E40B800F34A1563C0BC0B1295329FB32C618AEF2313",
    ),
    "portability/model/receipts/N48-postF3-attempt1.stderr.txt": (
        49,
        "0BF3067D55683F6EB725E2790165D665735B86C13EFE95A8CBAC4E39D63FA601",
    ),
    "portability/model/receipts/N48-postF3-attempt1.stdout.txt": (
        1,
        "AB53DCB62E8C60D9E6D9DD59A249174E34CA97CDBF199C810B72F36AAEBC985A",
    ),
    "portability/model/receipts/precheck-retained-vs-streaming.txt": (
        12,
        "DC5DE278C57BE84EC380031C24E886022AB0257A5037C16D69A4AB6E5C2170B1",
    ),
    # Sealed by gate0_a1_pin in the supplemental register; merged from the
    # continuation evidence branch.
    "evidence/A1_CAPABILITY_FLOOR_0_1.md": (
        1,
        "3C694ECBD17CCCF3F2E52D0C13F5B03EDBE400D443F1B63E0561A29EB39C7FCE",
    ),
}
WARNING = re.compile(r"^(?P<path>.+):(?P<line>[0-9]+): (?P<kind>.+)\.$")


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=BASE)
    parser.add_argument("--end")
    args = parser.parse_args(argv)

    command = ["git", "diff", "--check", args.base]
    if args.end:
        command.append(args.end)
    completed = subprocess.run(
        command,
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )
    diagnostics = completed.stdout.splitlines()
    warnings: Counter[str] = Counter()
    errors: list[str] = []
    for line in diagnostics:
        match = WARNING.fullmatch(line)
        if match:
            path = match.group("path").replace("\\", "/")
            if match.group("kind") != "trailing whitespace":
                errors.append(line)
            else:
                warnings[path] += 1
        elif not line.startswith("+"):
            errors.append(line)

    expected_counts = Counter({path: value[0] for path, value in ALLOWED.items()})
    if warnings != expected_counts:
        errors.append(
            f"warning inventory mismatch: expected={dict(expected_counts)!r} "
            f"observed={dict(warnings)!r}"
        )
    for relative, (_, expected_hash) in ALLOWED.items():
        observed_hash = _sha256(REPO / relative)
        if observed_hash != expected_hash:
            errors.append(
                f"custody hash mismatch for {relative}: "
                f"expected={expected_hash} observed={observed_hash}"
            )

    if errors:
        for error in errors:
            print(f"HYGIENE_ERROR {error}", file=sys.stderr)
        return 1
    print(
        f"HYGIENE_PASS allowed_raw_receipt_warnings={sum(expected_counts.values())} "
        f"unexpected_diagnostics=0 custody_hashes={len(ALLOWED)}/{len(ALLOWED)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
