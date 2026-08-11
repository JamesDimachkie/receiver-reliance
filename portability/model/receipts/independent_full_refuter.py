"""Durable independent traversal for the admitted N=48 model receipt.

This probe deliberately does not call ``explore_parser`` or ``build_receipt``.
It owns a separate Counter-based layer traversal, reconstructs the transport
and envelope fields from the frozen primitives, and compares canonical receipt
bytes with the captured post-F-MODEL-003 receipt.  It also counts the rejected
member of the sole raw-token alias group independently at every reachable
context where that raw spelling fits inside N.

The parser transition relation is necessarily shared with model M; traversal,
multiplicity retention, receipt construction, comparison, and alias accounting
are independent.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import json
import pathlib
import platform
import sys
import time
from typing import Any, Callable

REPO = pathlib.Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from portability.model.closures import RAW_CLOSURES, TRANSPORT_CLOSURES
from portability.model.domain import (
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
from portability.model.parser_model import (
    INITIAL_STATE,
    pack_state,
    terminal_class,
    token_label_is_admissible,
    transition,
    unpack_state,
)
from portability.model.transport_model import (
    explore_scheduler,
    materialize_r3_schedule,
    partition_receipt,
)

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_CAPTURE = HERE / "N48-postF3-attempt1.stdout.txt"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _source_hashes() -> dict[str, str]:
    paths = {
        "closures.py": HERE.parent / "closures.py",
        "domain.py": HERE.parent / "domain.py",
        "independent_full_refuter.py": pathlib.Path(__file__).resolve(),
        "parser_model.py": HERE.parent / "parser_model.py",
        "r3_schedules.json": HERE.parent / "r3_schedules.json",
        "transport_model.py": HERE.parent / "transport_model.py",
    }
    return {name: _sha256_bytes(path.read_bytes()) for name, path in paths.items()}


def independent_parser(
    max_request_bytes: int,
    progress: Callable[[int, int, int, int], None] | None = None,
) -> tuple[dict[str, Any], int]:
    if not 0 <= max_request_bytes <= MAX_REQUEST_BYTES:
        raise ValueError(
            f"max_request_bytes must be in [0, {MAX_REQUEST_BYTES}]"
        )

    non_lf = tuple(token for token in TOKENS if token.symbol != "LF")
    lf = next(token for token in TOKENS if token.symbol == "LF")
    aliases = tuple(token for token in non_lf if token.raw == b'"a"')
    if tuple(token.symbol for token in aliases) != ("KEY_A", "KEY_A_REPEAT"):
        raise AssertionError("frozen raw-token alias group drift")

    pending = [Counter() for _ in range(max_request_bytes + 1)]
    pending[0][pack_state(INITIAL_STATE)] = 1
    states = 0
    transitions = 0
    terminal_transitions = 0
    excluded_edges = 0
    excluded_trace_prefixes = 0
    inadmissible_alias_edges = 0
    classes: dict[str, dict[str, int]] = defaultdict(
        lambda: {"quotient_terminals": 0, "symbolic_traces": 0}
    )
    material = hashlib.sha256()

    for length, layer in enumerate(pending):
        states += len(layer)
        for packed in sorted(layer):
            state = unpack_state(packed, length)
            multiplicity = layer[packed]
            material.update(repr(state).encode("utf-8"))
            material.update(b"\n")

            if length:
                cls = terminal_class(state, False)
                terminal_transitions += 1
                classes[cls]["quotient_terminals"] += 1
                classes[cls]["symbolic_traces"] += multiplicity
            if length + len(lf.raw) <= max_request_bytes:
                cls = terminal_class(state, True)
                terminal_transitions += 1
                classes[cls]["quotient_terminals"] += 1
                classes[cls]["symbolic_traces"] += multiplicity

            if length + len(aliases[0].raw) <= max_request_bytes:
                admitted = [
                    token for token in aliases if token_label_is_admissible(state, token)
                ]
                if len(admitted) != 1:
                    raise AssertionError(
                        f"alias exclusivity failure at length={length}: {admitted!r}"
                    )
                rejected = aliases[0] if admitted[0] is aliases[1] else aliases[1]
                if transition(state, rejected) is not None:
                    raise AssertionError("rejected alias retained a transition")
                inadmissible_alias_edges += 1

            for token in non_lf:
                if length + len(token.raw) > max_request_bytes:
                    excluded_edges += 1
                    excluded_trace_prefixes += multiplicity
                    continue
                nxt = transition(state, token)
                if nxt is None:
                    excluded_edges += 1
                    excluded_trace_prefixes += multiplicity
                    continue
                if nxt.byte_length <= length:
                    raise AssertionError("transition did not increase byte length")
                transitions += 1
                pending[nxt.byte_length][pack_state(nxt)] += multiplicity
        pending[length] = Counter()
        if progress is not None:
            progress(length, states, transitions, inadmissible_alias_edges)

    parser = {
        "quotient_states": states,
        "quotient_transitions": transitions,
        "terminal_transitions": terminal_transitions,
        "symbolic_terminal_traces": sum(
            value["symbolic_traces"] for value in classes.values()
        ),
        "excluded_frontier_edges": excluded_edges,
        "excluded_trace_prefixes": excluded_trace_prefixes,
        "terminal_classes": dict(sorted(classes.items())),
        "representative_hex": {
            "ERR_DUPLICATE_KEY": b'{"a":1,"a"\n'.hex(),
            "ERR_EMPTY_INPUT": b"\n".hex(),
            "ERR_JSON": b"}\n".hex(),
            "ERR_NFC": '"e\u0301"\n'.encode("utf-8").hex(),
            "ERR_UTF8": b"\xff\n".hex(),
            "PARSE_OK": b"1\n".hex(),
        },
        "quotient_material_sha256": material.hexdigest().upper(),
    }
    return parser, inadmissible_alias_edges


def independent_receipt(parser: dict[str, Any]) -> dict[str, Any]:
    r3_path = HERE.parent / "r3_schedules.json"
    r3 = json.loads(r3_path.read_text(encoding="utf-8"))
    if r3["seed"] != f"0x{R3_SCHEDULE_SEED:08X}":
        raise AssertionError("R=3 schedule seed drift")
    schedulers = [
        asdict(explore_scheduler(callers, requests))
        for callers in (1, 2)
        for requests in (1, 2)
    ]
    replays = [materialize_r3_schedule(spec, r3["seed"]) for spec in r3["schedules"]]
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
            {
                "symbol": token.symbol,
                "variant": token.variant,
                "raw_hex": token.raw.hex(),
            }
            for token in TOKENS
        ],
        "parser": parser,
        "transport": {
            "complete_scheduler_products": schedulers,
            "partitions": partition_receipt(),
            "r3_recorded": {**r3, "replays": replays},
        },
        "historical_raw_closures": [asdict(item) for item in RAW_CLOSURES],
        "historical_transport_closures": list(TRANSPORT_CLOSURES),
        "assumptions": list(ASSUMPTIONS),
        "symmetry_reductions": list(SYMMETRY_REDUCTIONS),
        "exclusions": list(EXCLUSIONS),
        "claim": "Every quotient state, admissible token transition, terminal action, complete P<=2/R<=2 scheduler transition, and declared partition multiplicity in finite model M was explored.",
        "nonclaims": "No efficacy, novelty, security, fuzzing-completeness, external-standard, universal-portability, or post-parse semantic-completeness claim.",
    }
    receipt["receipt_sha256"] = _sha256_bytes(_canonical_bytes(receipt))
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-bytes", type=int, default=MAX_REQUEST_BYTES)
    parser.add_argument("--expected", type=pathlib.Path, default=DEFAULT_CAPTURE)
    args = parser.parse_args(argv)
    started = time.monotonic()

    def report(length: int, states: int, transitions: int, aliases: int) -> None:
        print(
            "INDEPENDENT_MODEL_PROGRESS "
            f"N={length}/{args.max_bytes} states={states} transitions={transitions} "
            f"inadmissible_alias_edges={aliases} "
            f"elapsed_seconds={time.monotonic() - started:.3f}",
            file=sys.stderr,
            flush=True,
        )

    parser_counts, alias_edges = independent_parser(args.max_bytes, report)
    if args.max_bytes != MAX_REQUEST_BYTES:
        print(
            json.dumps(
                {
                    "format_version": "RR-MODEL-INDEPENDENT-PROBE-1",
                    "max_request_bytes": args.max_bytes,
                    "parser": parser_counts,
                    "inadmissible_alias_edges": alias_edges,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "source_sha256": _source_hashes(),
                    "status": "BOUNDED_COMPLETE",
                },
                sort_keys=True,
            )
        )
        return 0

    expected_raw = args.expected.read_bytes()
    expected_body = expected_raw.rstrip(b"\r\n")
    expected = json.loads(expected_body.decode("ascii"))
    candidate = independent_receipt(parser_counts)
    candidate_body = _canonical_bytes(candidate)
    receipt = {
        "format_version": "RR-MODEL-INDEPENDENT-PROBE-1",
        "status": "PASS" if candidate_body == expected_body else "MISMATCH",
        "command": "python -B portability/model/receipts/independent_full_refuter.py",
        "runtime": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "source_sha256": _source_hashes(),
        "expected_capture": {
            "path": args.expected.as_posix(),
            "bytes": len(expected_raw),
            "sha256": _sha256_bytes(expected_raw),
        },
        "candidate_receipt_sha256": candidate["receipt_sha256"],
        "expected_receipt_sha256": expected.get("receipt_sha256"),
        "canonical_receipt_bytes_identical": candidate_body == expected_body,
        "inadmissible_alias_edges": alias_edges,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
