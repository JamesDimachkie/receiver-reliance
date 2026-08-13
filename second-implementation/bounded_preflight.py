from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from coverage_campaign import ReferenceBlackBox  # noqa: E402
from process_harness import CLI_FLAGS, run_candidate_cli  # noqa: E402
from raw_preflight_cases import raw_cases  # noqa: E402
from rr2 import Implementation, sha256_upper  # noqa: E402


def _error_tuple(raw: bytes) -> tuple[str | None, str | None]:
    try:
        response = json.loads(raw)
        error = response["errors"][0]
        return error.get("code"), error.get("pointer")
    except (KeyError, IndexError, TypeError, ValueError):
        return None, None


def main() -> int:
    reference = ReferenceBlackBox()
    candidate = Implementation(ROOT)
    divergences = []
    stream = hashlib.sha256()
    names = []
    family_counts: dict[str, int] = {}
    for identity, case in enumerate(raw_cases()):
        names.append(case.name)
        family_counts[case.family] = family_counts.get(case.family, 0) + 1
        raw = case.raw
        digest = sha256_upper(raw)
        stream.update(identity.to_bytes(8, "big")); stream.update(bytes.fromhex(digest))
        ref_code, ref_out, ref_err = reference.execute(raw)
        api_code, api_out = candidate.execute_bytes(raw)
        cli = run_candidate_cli(raw)
        reference_error = _error_tuple(ref_out)
        expected = (case.expected_code, case.expected_pointer)
        if (
            reference_error != expected
            or (api_code, api_out, b"") != (ref_code, ref_out, ref_err)
            or (cli.returncode, cli.stdout, cli.stderr) != (ref_code, ref_out, ref_err)
        ):
            divergences.append({
                "identity": identity,
                "family": case.family,
                "name": case.name,
                "input_sha256": digest,
                "expected_error": list(expected),
                "reference_error": list(reference_error),
                "reference_exit": ref_code,
                "reference_stdout_sha256": sha256_upper(ref_out),
                "api_exit": api_code,
                "api_stdout_sha256": sha256_upper(api_out),
                "cli_exit": cli.returncode,
                "cli_stdout_sha256": sha256_upper(cli.stdout),
                "cli_stderr_sha256": sha256_upper(cli.stderr),
            })
    receipt = {
        "format_version": "RR2-BOUNDED-RAW-PREFLIGHT-0.2",
        "case_names": names,
        "executed_cases": len(names),
        "family_counts": dict(sorted(family_counts.items())),
        "surfaces_per_case": ["frozen-composed-reference-black-box", "candidate-api", "candidate-cli"],
        "candidate_cli_flags": list(CLI_FLAGS),
        "candidate_cli_pycache_policy": "Every child uses -B and a unique existing empty temporary -X pycache_prefix; any artifact fails the preflight.",
        "stream_sha256": stream.hexdigest().upper(),
        "divergence_count": len(divergences),
        "first_divergence": divergences[0] if divergences else None,
        "status": "PASS" if not divergences else "FAIL",
    }
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if not divergences else 1


if __name__ == "__main__":
    raise SystemExit(main())
