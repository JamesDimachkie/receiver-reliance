"""CLI and deterministic receipt builder for finite model M."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from .closures import RAW_CLOSURES, TRANSPORT_CLOSURES
from .domain import (
    ASSUMPTIONS,
    BASE_ALPHABET,
    EXCLUSIONS,
    MAX_CALLERS,
    MAX_CHUNK_SPLITS_COMPLETE,
    MAX_DEPTH,
    MAX_DUPLICATES_PER_OBJECT,
    MAX_REQUEST_BYTES,
    MAX_REQUESTS_PER_STREAM,
    MAX_WRITE_SPLITS,
    MODEL_ID,
    R3_SCHEDULE_SEED,
    SYMMETRY_REDUCTIONS,
    TOKENS,
)
from .parser_model import explore_parser
from .transport_model import explore_scheduler, materialize_r3_schedule, partition_receipt


def _sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii")
    return hashlib.sha256(raw).hexdigest().upper()


def _load_r3_schedules() -> dict[str, Any]:
    path = Path(__file__).with_name("r3_schedules.json")
    return json.loads(path.read_text(encoding="utf-8"))


def build_receipt(
    parser_progress: Callable[[int, int, int], None] | None = None,
) -> dict[str, Any]:
    parser = explore_parser(progress=parser_progress)
    schedulers = [asdict(explore_scheduler(callers, requests)) for callers in (1, 2) for requests in (1, 2)]
    r3 = _load_r3_schedules()
    if r3["seed"] != f"0x{R3_SCHEDULE_SEED:08X}":
        raise AssertionError("R=3 schedule seed drift")
    r3_replays = [materialize_r3_schedule(spec, r3["seed"]) for spec in r3["schedules"]]
    receipt: dict[str, Any] = {
        "format_version": "RR-PORTABILITY-M-RECEIPT-1",
        "model_id": MODEL_ID,
        "bounds": {
            "alphabet_base_symbols": len(BASE_ALPHABET),
            "concrete_variant_labels": len(TOKENS),
            "N_max_expanded_bytes": MAX_REQUEST_BYTES,
            "D_max": MAX_DEPTH,
            "K_max_duplicates_per_object": MAX_DUPLICATES_PER_OBJECT,
            "C_complete_split_set_size_max": MAX_CHUNK_SPLITS_COMPLETE,
            "W_split_set_size_max": MAX_WRITE_SPLITS,
            "R_max": MAX_REQUESTS_PER_STREAM,
            "P_max": MAX_CALLERS,
        },
        "alphabet": [
            {"symbol": token.symbol, "variant": token.variant, "raw_hex": token.raw.hex()}
            for token in TOKENS
        ],
        "parser": {
            "quotient_states": parser.states,
            "quotient_transitions": parser.transitions,
            "terminal_transitions": parser.terminal_transitions,
            "symbolic_terminal_traces": parser.symbolic_terminal_traces,
            "excluded_frontier_edges": parser.excluded_edges,
            "excluded_trace_prefixes": parser.excluded_trace_prefixes,
            "terminal_classes": parser.terminal_classes,
            "representative_hex": parser.representative_hex,
            "quotient_material_sha256": parser.quotient_material_sha256,
        },
        "transport": {
            "complete_scheduler_products": schedulers,
            "partitions": partition_receipt(),
            "r3_recorded": {**r3, "replays": r3_replays},
        },
        "historical_raw_closures": [asdict(item) for item in RAW_CLOSURES],
        "historical_transport_closures": list(TRANSPORT_CLOSURES),
        "assumptions": list(ASSUMPTIONS),
        "symmetry_reductions": list(SYMMETRY_REDUCTIONS),
        "exclusions": list(EXCLUSIONS),
        "claim": "Every quotient state, admissible token transition, terminal action, complete P<=2/R<=2 scheduler transition, and declared partition multiplicity in finite model M was explored.",
        "nonclaims": "No efficacy, novelty, security, fuzzing-completeness, external-standard, universal-portability, or post-parse semantic-completeness claim.",
    }
    receipt["receipt_sha256"] = _sha256_json(receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compact", action="store_true", help="emit compact canonical JSON")
    parser.add_argument("--check", type=Path, help="compare the generated receipt with a committed JSON file")
    parser.add_argument("--progress", action="store_true", help="emit per-length parser progress to stderr")
    args = parser.parse_args(argv)
    started = time.monotonic()

    def report_progress(length: int, states: int, transitions: int) -> None:
        print(
            "MODEL_PROGRESS "
            f"N={length}/{MAX_REQUEST_BYTES} states={states} transitions={transitions} "
            f"elapsed_seconds={time.monotonic() - started:.3f}",
            file=sys.stderr,
            flush=True,
        )

    receipt = build_receipt(report_progress if args.progress else None)
    if args.check is not None:
        expected = json.loads(args.check.read_text(encoding="utf-8"))
        if receipt != expected:
            print("MODEL_RECEIPT_MISMATCH")
            return 1
        print(f"MODEL_RECEIPT_OK {receipt['receipt_sha256']}")
        return 0
    if args.compact:
        print(json.dumps(receipt, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
    else:
        print(json.dumps(receipt, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
