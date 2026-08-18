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

The robustness program admits five further Windows-authored CRLF surfaces on
the same custody terms (three WP5 documents, the WP5 receipt verifier, and
the WP4 author increment receipt, whose raw bytes are published pins), and
exactly one error-class diagnostic: the WP4 author increment receipt pins
``second-implementation/findings/F-WP4-003.md`` byte-exactly
(``author-file-hash`` in ``verify_artifacts.py``), so its terminal blank
line is admitted under the same hash-locked rule instead of normalized.
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
    # Robustness-program surfaces authored on Windows and committed with
    # CRLF endings under ``* -text``; git reports each carriage return as
    # trailing whitespace.  The WP4 author increment receipt's raw bytes are
    # published pins (``raw_sha256`` rows verified by ``verify_artifacts.py``),
    # and the WP5 documents/verifier are admitted on the same byte-exact
    # custody terms rather than normalized.
    "perf/COST_MODEL.md": (
        174,
        "6E89886BC7F69F66548BC39E4705568FB3186658B04ACFFB8BAD5078FE37ECC9",
    ),
    "perf/PROFILE_ROBUSTNESS_20260811.md": (
        146,
        "AC0D43543BA6376F180053A6FCEE521CD603F797CEC463B92A4CBB6D3DAA679D",
    ),
    "perf/SIDECAR.md": (
        133,
        "64915A8199D4EDDFD9DC3EAC925B6EB6A5864C8E74265782377C59431E9932AE",
    ),
    "perf/sidecar/verify_receipts.py": (
        228,
        "E657B67E967A1D646507EE1B1EF09A2F45913E4B77A5DA38814460A39D5B9554",
    ),
    "second-implementation/receipts/AUTHOR_INCREMENT_RECEIPT_0_1.json": (
        189,
        "CB42DDBF8B839B2DAA95D1D8658E1C9644D83798EB6B3C74B5F1C1E7ECC90933",
    ),
    "second-implementation/receipts/BOUNDED_DEEP_PREFLIGHT_0_1.json": (
        1,
        "4DFDB3647C787C725993B60128F7C4CA6899C4B4A6C219DBE7E03DD7751710A7",
    ),
    "second-implementation/receipts/COVERAGE_STEERING_SMOKE_0_1.json": (
        1,
        "45407C175B05CCC0A7C4961AAED5818CFA6CD57676F6BF06304CF677A4185FB5",
    ),
}
# Error-class diagnostics admitted byte-exactly.  The WP4 author increment
# receipt publishes this file's raw SHA-256 (verified by
# ``verify_artifacts.py`` as ``author-file-hash``), so the terminal blank
# line cannot be normalized without invalidating a published pin.
ALLOWED_DIAGNOSTICS = {
    "second-implementation/findings/F-WP4-002.md": (
        "new blank line at EOF",
        1,
        "854EC88B9BD5186C517020897107650465BA757D6EA1374E8093DDB4F23A957F",
    ),
    "second-implementation/findings/F-WP4-003.md": (
        "new blank line at EOF",
        1,
        "8FF3BE2603A8505D1674D99376B2A1468F69257786ED27E3EC570C350BF1EFE9",
    ),
    "second-implementation/findings/F-WP4-010.md": (
        "new blank line at EOF",
        1,
        "970303D7DCFC8567C8951BAABD39D4AA8DDB79310DBAD1419CEF22BB81C707E6",
    ),
    "second-implementation/findings/F-WP4-011.md": (
        "new blank line at EOF",
        1,
        "F10FCDF58C067585116E2DB5B2B29C81DCCB87F4E18B388C2AB5A34C3F0F2038",
    ),
    "second-implementation/findings/F-WP4-012.md": (
        "new blank line at EOF",
        1,
        "124F16C9978E44F26A2428C14ED1930611D92EC2257F44C591C5C7C521547D6D",
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
    admitted: Counter[str] = Counter()
    errors: list[str] = []
    for line in diagnostics:
        match = WARNING.fullmatch(line)
        if match:
            path = match.group("path").replace("\\", "/")
            kind = match.group("kind")
            if kind == "trailing whitespace":
                warnings[path] += 1
            elif (
                path in ALLOWED_DIAGNOSTICS
                and kind == ALLOWED_DIAGNOSTICS[path][0]
            ):
                admitted[path] += 1
            else:
                errors.append(line)
        elif not line.startswith("+"):
            errors.append(line)

    expected_counts = Counter({path: value[0] for path, value in ALLOWED.items()})
    if warnings != expected_counts:
        errors.append(
            f"warning inventory mismatch: expected={dict(expected_counts)!r} "
            f"observed={dict(warnings)!r}"
        )
    expected_admitted = Counter(
        {path: value[1] for path, value in ALLOWED_DIAGNOSTICS.items()}
    )
    if admitted != expected_admitted:
        errors.append(
            f"admitted diagnostic inventory mismatch: "
            f"expected={dict(expected_admitted)!r} observed={dict(admitted)!r}"
        )
    for relative, (_, expected_hash) in ALLOWED.items():
        observed_hash = _sha256(REPO / relative)
        if observed_hash != expected_hash:
            errors.append(
                f"custody hash mismatch for {relative}: "
                f"expected={expected_hash} observed={observed_hash}"
            )
    for relative, (_, _, expected_hash) in ALLOWED_DIAGNOSTICS.items():
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
        f"admitted_diagnostics={sum(expected_admitted.values())} "
        f"unexpected_diagnostics=0 "
        f"custody_hashes={len(ALLOWED) + len(ALLOWED_DIAGNOSTICS)}"
        f"/{len(ALLOWED) + len(ALLOWED_DIAGNOSTICS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
