#!/usr/bin/env python3
"""Deterministic-workload baseline profiler for the receiver-reliance engine.

The workload and ordering are fixed by the two committed semantic fixture
packs.  Timing is necessarily observational and machine-dependent; the JSON
output keeps the repeated samples and identifies which probes are direct
measurements versus non-additive approximations.

Only the Python standard library is used.  Wall timing uses
``time.perf_counter_ns`` and Python-allocation peaks use ``tracemalloc``.
"""
from __future__ import annotations

import argparse
import base64
import gc
import json
import math
import os
import pathlib
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
from dataclasses import dataclass
from typing import Any, Callable


REPO = pathlib.Path(__file__).resolve().parent.parent
IMPL = REPO / "baseline-run" / "implementation-output-0.3"
GROUNDED = REPO / "grounded-0_4"
RUNNER = IMPL / "pcb_runner.py"
PACK_PATHS = (
    REPO / "baseline-run" / "fixtures" / "PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json",
    REPO / "supplemental-0_3" / "fixtures" / "B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
)
EXPECTED_ENTRY_COUNT = 124

if str(GROUNDED) not in sys.path:
    sys.path.insert(0, str(GROUNDED))
if str(IMPL) not in sys.path:
    sys.path.insert(0, str(IMPL))

import rr_api  # noqa: E402

b1 = rr_api.b1
pcb_runner = rr_api.pcb_runner


@dataclass(frozen=True)
class Fixture:
    entry_id: str
    pack: str
    raw: bytes
    expected: bytes
    expected_exit: int
    request: dict[str, Any]
    response: dict[str, Any]


def bounded_int(minimum: int, maximum: int) -> Callable[[str], int]:
    def parse(value: str) -> int:
        parsed = int(value)
        if not minimum <= parsed <= maximum:
            raise argparse.ArgumentTypeError(
                f"must be between {minimum} and {maximum}, inclusive"
            )
        return parsed

    return parse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--warmups",
        type=bounded_int(0, 10),
        default=1,
        help="unreported warmup rounds per timed callable (default: 1)",
    )
    parser.add_argument(
        "--repetitions",
        type=bounded_int(3, 30),
        default=5,
        help="reported samples per aggregate; minimum 3 (default: 5)",
    )
    parser.add_argument(
        "--inner-loops",
        type=bounded_int(1, 100),
        default=5,
        help="calls averaged within each in-process timing sample (default: 5)",
    )
    parser.add_argument(
        "--stdio-warmups",
        type=bounded_int(0, 3),
        default=1,
        help="unreported subprocess calls per fixture (default: 1)",
    )
    parser.add_argument(
        "--memory-loops",
        type=bounded_int(1, 20),
        default=1,
        help="full-corpus loops in each peak-allocation sample (default: 1)",
    )
    parser.add_argument(
        "--child-timeout",
        type=bounded_int(1, 300),
        default=30,
        help="timeout in seconds for each child process (default: 30)",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        help="write JSON to this path instead of stdout",
    )
    return parser.parse_args()


def load_fixtures() -> list[Fixture]:
    fixtures: list[Fixture] = []
    for path in PACK_PATHS:
        pack = json.loads(path.read_text(encoding="utf-8"))
        for entry in pack["entries"]:
            raw = base64.b64decode(entry["semantic_request_jcs_lf_base64"], validate=True)
            expected = base64.b64decode(
                entry["expected_response_jcs_lf_base64"], validate=True
            )
            request = json.loads(raw.decode("utf-8"))
            response = json.loads(expected.decode("utf-8"))
            fixtures.append(
                Fixture(
                    entry_id=entry["entry_id"],
                    pack=path.relative_to(REPO).as_posix(),
                    raw=raw,
                    expected=expected,
                    expected_exit=response["exit_code"],
                    request=request,
                    response=response,
                )
            )
    fixtures.sort(key=lambda fixture: fixture.entry_id.encode("utf-8"))
    if len(fixtures) != EXPECTED_ENTRY_COUNT:
        raise RuntimeError(
            f"expected {EXPECTED_ENTRY_COUNT} semantic fixtures, got {len(fixtures)}"
        )
    ids = [fixture.entry_id for fixture in fixtures]
    if len(ids) != len(set(ids)):
        raise RuntimeError("semantic fixture entry_id values are not unique")
    return fixtures


def percentile(values: list[float], percentage: float) -> float:
    """Linear interpolation over the sorted samples, with documented endpoints."""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot summarize an empty sample")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentage / 100.0
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def summary(values: list[float]) -> dict[str, float | int]:
    return {
        "n": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "pstdev": statistics.pstdev(values),
        "p95_linear": percentile(values, 95.0),
        "max": max(values),
    }


def timed_repeats(
    function: Callable[[], Any], warmups: int, repetitions: int, inner_loops: int
) -> list[float]:
    for _ in range(warmups):
        for _ in range(inner_loops):
            function()
    samples_ms: list[float] = []
    for _ in range(repetitions):
        start = time.perf_counter_ns()
        for _ in range(inner_loops):
            function()
        elapsed = time.perf_counter_ns() - start
        samples_ms.append(elapsed / inner_loops / 1_000_000.0)
    return samples_ms


def entry_profile(
    fixtures: list[Fixture],
    name: str,
    function_for: Callable[[Fixture], Callable[[], Any]],
    warmups: int,
    repetitions: int,
    inner_loops: int,
) -> dict[str, Any]:
    samples_by_entry: dict[str, list[float]] = {}
    for fixture in fixtures:
        samples_by_entry[fixture.entry_id] = timed_repeats(
            function_for(fixture), warmups, repetitions, inner_loops
        )
    return entry_result(
        fixtures,
        name,
        samples_by_entry,
        warmups,
        repetitions,
        inner_loops,
    )


def entry_result(
    fixtures: list[Fixture],
    name: str,
    samples_by_entry: dict[str, list[float]],
    warmups: int,
    repetitions: int,
    inner_loops: int,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    repeat_totals = [0.0] * repetitions
    for fixture in fixtures:
        samples = samples_by_entry[fixture.entry_id]
        for index, sample in enumerate(samples):
            repeat_totals[index] += sample
        entries.append(
            {
                "entry_id": fixture.entry_id,
                "pack": fixture.pack,
                "samples_ms_per_call": samples,
                "summary_ms_per_call": summary(samples),
            }
        )
    entry_medians = [entry["summary_ms_per_call"]["median"] for entry in entries]
    repeat_per_decision = [total / len(fixtures) for total in repeat_totals]
    return {
        "name": name,
        "entry_count": len(entries),
        "warmups_per_entry": warmups,
        "repetitions_per_entry": repetitions,
        "inner_loops_per_sample": inner_loops,
        "corpus_repeat_total_ms": repeat_totals,
        "corpus_repeat_ms_per_decision": repeat_per_decision,
        "corpus_repeat_total_summary_ms": summary(repeat_totals),
        "corpus_repeat_per_decision_summary_ms": summary(repeat_per_decision),
        "spread_of_124_entry_medians_ms": summary(entry_medians),
        "fastest_entry_by_median": entries[min(range(len(entries)), key=entry_medians.__getitem__)][
            "entry_id"
        ],
        "slowest_entry_by_median": entries[max(range(len(entries)), key=entry_medians.__getitem__)][
            "entry_id"
        ],
        "entries": entries,
    }


def profile_in_process_pair(
    fixtures: list[Fixture], warmups: int, repetitions: int, inner_loops: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Interleave decide and decide_audited to reduce time-of-run bias.

    The call order alternates by reported repetition.  The workload remains
    deterministic while neither path receives a systematic first/second-call
    advantage across the complete run.
    """
    decide_samples: dict[str, list[float]] = {}
    audited_samples: dict[str, list[float]] = {}

    def one_sample(function: Callable[[], Any]) -> float:
        start = time.perf_counter_ns()
        for _ in range(inner_loops):
            function()
        return (time.perf_counter_ns() - start) / inner_loops / 1_000_000.0

    for fixture in fixtures:
        decide_call = lambda fixture=fixture: rr_api.decide(fixture.raw)
        audited_call = lambda fixture=fixture: rr_api.decide_audited(fixture.raw)
        for warmup in range(warmups):
            ordered = (
                (decide_call, audited_call)
                if warmup % 2 == 0
                else (audited_call, decide_call)
            )
            for function in ordered:
                for _ in range(inner_loops):
                    function()
        decide_values: list[float] = []
        audited_values: list[float] = []
        for repetition in range(repetitions):
            if repetition % 2 == 0:
                decide_values.append(one_sample(decide_call))
                audited_values.append(one_sample(audited_call))
            else:
                audited_values.append(one_sample(audited_call))
                decide_values.append(one_sample(decide_call))
        decide_samples[fixture.entry_id] = decide_values
        audited_samples[fixture.entry_id] = audited_values

    return (
        entry_result(
            fixtures,
            "decide_in_process",
            decide_samples,
            warmups,
            repetitions,
            inner_loops,
        ),
        entry_result(
            fixtures,
            "decide_audited_in_process",
            audited_samples,
            warmups,
            repetitions,
            inner_loops,
        ),
    )


def validate_paths(fixtures: list[Fixture], child_timeout: int) -> None:
    """Untimed parity check before observing costs."""
    for fixture in fixtures:
        response, exit_code = rr_api.decide(fixture.raw)
        got = b1.jcs_bytes(response) + b"\n"
        if got != fixture.expected or exit_code != fixture.expected_exit:
            raise RuntimeError(f"in-process parity failed for {fixture.entry_id}")
        audited = rr_api.decide_audited(fixture.raw)
        sealed = b1.jcs_bytes(audited["sealed_response"]) + b"\n"
        if sealed != fixture.expected or audited["exit_code"] != fixture.expected_exit:
            raise RuntimeError(f"audited parity failed for {fixture.entry_id}")
    # One untimed child proves the stdio command is usable before the full run.
    run_stdio(fixtures[0], child_timeout)


def child_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONHASHSEED"] = "0"
    return environment


def run_child(command: list[str], timeout: int, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        cwd=REPO,
        env=child_environment(),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def run_stdio(fixture: Fixture, timeout: int) -> None:
    result = run_child(
        [sys.executable, "-B", str(RUNNER), "execute"], timeout, fixture.raw
    )
    if result.stdout != fixture.expected:
        raise RuntimeError(f"stdio byte parity failed for {fixture.entry_id}")
    if result.returncode != fixture.expected_exit:
        raise RuntimeError(
            f"stdio exit mismatch for {fixture.entry_id}: "
            f"{result.returncode} != {fixture.expected_exit}"
        )
    if result.stderr:
        raise RuntimeError(f"stdio stderr was nonempty for {fixture.entry_id}")


def startup_probe(
    name: str,
    command: list[str],
    warmups: int,
    repetitions: int,
    timeout: int,
) -> dict[str, Any]:
    def once() -> None:
        result = run_child(command, timeout)
        if result.returncode != 0 or result.stdout or result.stderr:
            raise RuntimeError(
                f"startup probe {name!r} failed: returncode={result.returncode}, "
                f"stdout={result.stdout!r}, stderr={result.stderr!r}"
            )

    samples = timed_repeats(once, warmups, repetitions, 1)
    return {
        "name": name,
        "command_shape": command[1:],
        "warmups": warmups,
        "repetitions": repetitions,
        "samples_ms": samples,
        "summary_ms": summary(samples),
    }


def profile_startup(warmups: int, repetitions: int, timeout: int) -> dict[str, Any]:
    impl_literal = repr(str(IMPL))
    import_source = f"import sys;sys.path.insert(0,{impl_literal});import pcb_runner"
    authority_source = import_source + ";pcb_runner.b1.authority_documents()"
    probes = [
        startup_probe(
            "interpreter_process_noop",
            [sys.executable, "-B", "-c", "pass"],
            warmups,
            repetitions,
            timeout,
        ),
        startup_probe(
            "interpreter_plus_engine_import",
            [sys.executable, "-B", "-c", import_source],
            warmups,
            repetitions,
            timeout,
        ),
        startup_probe(
            "interpreter_plus_engine_import_plus_authority_load_verify",
            [sys.executable, "-B", "-c", authority_source],
            warmups,
            repetitions,
            timeout,
        ),
    ]
    medians = {probe["name"]: probe["summary_ms"]["median"] for probe in probes}
    return {
        "probes": probes,
        "median_differences_ms_noncausal": {
            "engine_import_minus_noop": (
                medians["interpreter_plus_engine_import"]
                - medians["interpreter_process_noop"]
            ),
            "authority_load_verify_minus_import": (
                medians["interpreter_plus_engine_import_plus_authority_load_verify"]
                - medians["interpreter_plus_engine_import"]
            ),
        },
        "interpretation": (
            "Fresh-process wall probes overlap and are not additive. Median subtraction is "
            "reported only as a rough residual, not a causal phase time."
        ),
    }


def profile_authority_load(warmups: int, repetitions: int) -> dict[str, Any]:
    def load_uncached() -> None:
        b1.authority_documents.cache_clear()
        b1.authority_documents()

    samples = timed_repeats(load_uncached, warmups, repetitions, 1)
    return {
        "name": "authority_load_verify_application_cache_cold",
        "warmups": warmups,
        "repetitions": repetitions,
        "inner_loops_per_sample": 1,
        "samples_ms": samples,
        "summary_ms": summary(samples),
        "interpretation": (
            "Direct time inside authority_documents() after clearing its lru_cache. "
            "Filesystem/OS caches are intentionally uncontrolled."
        ),
    }


def profile_components(
    fixtures: list[Fixture], warmups: int, repetitions: int, inner_loops: int
) -> dict[str, Any]:
    responses = {
        fixture.entry_id: b1.build_core_response(fixture.request) for fixture in fixtures
    }

    def schema_for(fixture: Fixture) -> Callable[[], Any]:
        response = responses[fixture.entry_id]

        def call() -> tuple[list[str], list[str]]:
            return (
                pcb_runner._core_schema_error_pool(fixture.request),
                b1.validate_core_response(response),
            )

        return call

    def classify_for(fixture: Fixture) -> Callable[[], Any]:
        return lambda: b1.classify(
            fixture.request["operation_handle"], fixture.request["decision_input"]
        )

    def seal_for(fixture: Fixture) -> Callable[[], Any]:
        response = responses[fixture.entry_id]
        return lambda: b1.self_zero_sha256(response, "receipt_sha256")

    return {
        "schema_walk_valid_path": entry_profile(
            fixtures,
            "schema_walk_valid_path",
            schema_for,
            warmups,
            repetitions,
            inner_loops,
        ),
        "classify": entry_profile(
            fixtures,
            "classify",
            classify_for,
            warmups,
            repetitions,
            inner_loops,
        ),
        "seal_primitive": entry_profile(
            fixtures,
            "seal_primitive",
            seal_for,
            warmups,
            repetitions,
            inner_loops,
        ),
        "interpretation": (
            "Direct probes are non-additive. Schema measures the valid semantic path's "
            "binding/request pool plus response schema walk over a prebuilt response; "
            "classify measures the frozen predicate classifier; seal measures the exact "
            "self-zero JCS+SHA-256 primitive over a prebuilt response, not response assembly."
        ),
    }


def peak_samples(
    function: Callable[[], Any], warmups: int, repetitions: int
) -> list[float]:
    for _ in range(warmups):
        function()
    peaks: list[float] = []
    for _ in range(repetitions):
        gc.collect()
        tracemalloc.start()
        try:
            function()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        peaks.append(float(peak))
    return peaks


def profile_memory(
    fixtures: list[Fixture], warmups: int, repetitions: int, memory_loops: int
) -> dict[str, Any]:
    def authority() -> None:
        b1.authority_documents.cache_clear()
        b1.authority_documents()

    def decide_corpus() -> None:
        for _ in range(memory_loops):
            for fixture in fixtures:
                rr_api.decide(fixture.raw)

    def audited_corpus() -> None:
        for _ in range(memory_loops):
            for fixture in fixtures:
                rr_api.decide_audited(fixture.raw)

    result: dict[str, Any] = {}
    for name, function in (
        ("authority_load_verify_application_cache_cold", authority),
        ("decide_full_corpus_steady", decide_corpus),
        ("decide_audited_full_corpus_steady", audited_corpus),
    ):
        samples = peak_samples(function, warmups, repetitions)
        result[name] = {
            "samples_peak_traced_bytes": [int(value) for value in samples],
            "summary_peak_traced_bytes": summary(samples),
        }
    result["warmups"] = warmups
    result["repetitions"] = repetitions
    result["corpus_loops_per_sample"] = memory_loops
    result["interpretation"] = (
        "tracemalloc reports peak traced Python allocations after setup. It is not RSS, "
        "does not include native/interpreter baseline memory, and cannot observe child "
        "process allocations. Timing and memory runs are separate."
    )
    return result


def ratio_samples(numerator: list[float], denominator: list[float]) -> list[float]:
    if len(numerator) != len(denominator):
        raise ValueError("ratio sample vectors differ in length")
    return [left / right for left, right in zip(numerator, denominator, strict=True)]


def git_head() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def main() -> int:
    args = parse_args()
    fixtures = load_fixtures()
    validate_paths(fixtures, args.child_timeout)

    startup = profile_startup(
        args.warmups, args.repetitions, args.child_timeout
    )
    authority = profile_authority_load(args.warmups, args.repetitions)

    decide, audited = profile_in_process_pair(
        fixtures, args.warmups, args.repetitions, args.inner_loops
    )
    stdio = entry_profile(
        fixtures,
        "stdio_fresh_process",
        lambda fixture: lambda: run_stdio(fixture, args.child_timeout),
        args.stdio_warmups,
        args.repetitions,
        1,
    )
    components = profile_components(
        fixtures, args.warmups, args.repetitions, args.inner_loops
    )
    memory = profile_memory(
        fixtures, args.warmups, args.repetitions, args.memory_loops
    )

    stdio_vs_decide = ratio_samples(
        stdio["corpus_repeat_ms_per_decision"],
        decide["corpus_repeat_ms_per_decision"],
    )
    audited_vs_decide = ratio_samples(
        audited["corpus_repeat_ms_per_decision"],
        decide["corpus_repeat_ms_per_decision"],
    )
    result = {
        "profile_format": "receiver-reliance-profile-0.1",
        "measurement_units": {
            "time": "milliseconds",
            "memory": "tracemalloc peak traced bytes",
        },
        "system": {
            "python": sys.version.replace("\n", " "),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "perf_counter": vars(time.get_clock_info("perf_counter")),
            "git_head": git_head(),
        },
        "configuration": {
            "fixture_count": len(fixtures),
            "fixture_packs": [path.relative_to(REPO).as_posix() for path in PACK_PATHS],
            "warmups": args.warmups,
            "stdio_warmups": args.stdio_warmups,
            "repetitions": args.repetitions,
            "inner_loops": args.inner_loops,
            "memory_loops": args.memory_loops,
            "child_timeout_seconds": args.child_timeout,
            "child_environment_overrides": {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
            },
        },
        "parity_precheck": {
            "status": "pass",
            "paths": ["decide", "decide_audited sealed_response", "fresh-process stdio"],
            "fixture_entries_checked": len(fixtures),
        },
        "startup": startup,
        "authority_direct": authority,
        "integration_paths": {
            "decide_in_process": decide,
            "decide_audited_in_process": audited,
            "stdio_fresh_process": stdio,
        },
        "comparisons": {
            "stdio_over_decide_ratio_samples": stdio_vs_decide,
            "stdio_over_decide_ratio_summary": summary(stdio_vs_decide),
            "decide_audited_over_decide_ratio_samples": audited_vs_decide,
            "decide_audited_over_decide_ratio_summary": summary(audited_vs_decide),
            "in_process_pairing": (
                "decide and decide_audited samples are interleaved per fixture; "
                "reported repetition order alternates which path runs first"
            ),
        },
        "direct_component_probes": components,
        "peak_memory": memory,
        "limitations": [
            "Wall-clock results include scheduler, power-state, antivirus, and filesystem-cache noise.",
            "Fresh-process probes overlap; their median differences are residuals, not causal phase isolation.",
            "Direct component probes use valid semantic fixtures and are deliberately non-additive.",
            "The stdio path includes process creation, interpreter startup, imports, engine work, and pipe I/O.",
            "tracemalloc observes Python allocations only and excludes child-process and native RSS.",
            "Results describe this Python build and platform; rerun before using them for another host.",
        ],
    }
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(encoded)
    else:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8", newline="\n")
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
