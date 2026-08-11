"""Extract the declared counts and hashes from a captured explorer receipt.

Authored additively for the post-F-MODEL-003 N=48 enumeration.  Read-only: it
parses one captured stdout file and prints what it found.  It deliberately does
not compare anything against EXPECTED_COUNTS.json. It is an independent count
extractor; admission remains bound to the complete receipt and custody record.

Run from the repository root:
    python -B portability/model/receipts/extract_counts.py <captured-stdout.json>
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    path = pathlib.Path(argv[1])
    raw = path.read_bytes()
    print(f"CAPTURE path={path.as_posix()}")
    print(f"CAPTURE bytes={len(raw)}")
    print(f"CAPTURE sha256={hashlib.sha256(raw).hexdigest().upper()}")

    receipt = json.loads(raw.decode("ascii"))
    print(f"RECEIPT format_version={receipt['format_version']}")
    print(f"RECEIPT model_id={receipt['model_id']}")
    print(f"RECEIPT receipt_sha256={receipt['receipt_sha256']}")

    print("BOUNDS " + json.dumps(receipt["bounds"], sort_keys=True))

    parser = receipt["parser"]
    for key in (
        "quotient_states",
        "quotient_transitions",
        "terminal_transitions",
        "symbolic_terminal_traces",
        "excluded_frontier_edges",
        "excluded_trace_prefixes",
        "quotient_material_sha256",
    ):
        print(f"PARSER {key}={parser[key]}")

    total_terminals = 0
    total_traces = 0
    for name, table in sorted(parser["terminal_classes"].items()):
        total_terminals += table["quotient_terminals"]
        total_traces += table["symbolic_traces"]
        print(
            f"TERMINAL_CLASS {name} quotient_terminals={table['quotient_terminals']} "
            f"symbolic_traces={table['symbolic_traces']}"
        )
    print(f"TERMINAL_CLASS_TOTAL quotient_terminals={total_terminals} symbolic_traces={total_traces}")
    print(
        "TERMINAL_CLASS_TOTAL_CONSISTENT "
        f"terminal_transitions={total_terminals == parser['terminal_transitions']} "
        f"symbolic_terminal_traces={total_traces == parser['symbolic_terminal_traces']}"
    )
    for name, value in sorted(parser["representative_hex"].items()):
        print(f"REPRESENTATIVE {name} raw_hex={value}")

    for entry in receipt["transport"]["complete_scheduler_products"]:
        print("SCHEDULER " + json.dumps(entry, sort_keys=True))

    # Recompute the receipt hash over the receipt with its own hash field removed,
    # exactly as explorer._sha256_json builds it, as an integrity check on the capture.
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    recomputed = hashlib.sha256(
        json.dumps(body, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii")
    ).hexdigest().upper()
    print(f"RECEIPT_SHA_RECOMPUTED {recomputed}")
    print(f"RECEIPT_SHA_SELF_CONSISTENT {recomputed == receipt['receipt_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
