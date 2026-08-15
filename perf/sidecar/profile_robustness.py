#!/usr/bin/env python3
"""WP5 canonicalization/digest/audit and integration-mode profiler.

Wall timings use fixed committed fixtures, paired observations, alternating
order, medians, and raw sample vectors.  cProfile is attribution-only because
instrumentation overhead changes absolute timings.  No timing is a gate.
"""
from __future__ import annotations

import argparse
import base64
import cProfile
import gc
import hashlib
import importlib.util
import io
import json
import pathlib
import pstats
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Any, Callable, Iterable


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
GROUNDED = REPO / "grounded-0_4"
IMPL = REPO / "baseline-run/implementation-output-0.3"
RUNNER = IMPL / "pcb_runner.py"
ORACLE_PATH = GROUNDED / "test_single_pass_audit.py"
LAUNCHER = HERE / "rr_sidecar.py"
TRACE_EXEC = HERE / "_trace_exec.py"
WORKER_MARKER = "--wp5-traced-worker"
if WORKER_MARKER not in sys.argv:
    with tempfile.TemporaryDirectory(prefix="rr-wp5-profile-trace-") as temporary:
        trace_dir = pathlib.Path(temporary).resolve()
        cache = trace_dir / "empty-pycache-root"
        cache.mkdir()
        command = [
            sys.executable,
            "-I",
            "-B",
            "-X",
            f"pycache_prefix={cache}",
            str(TRACE_EXEC),
            "--trace-dir",
            str(trace_dir),
            "--trace-id",
            uuid.uuid4().hex,
            str(pathlib.Path(__file__).resolve()),
            WORKER_MARKER,
            *sys.argv[1:],
        ]
        raise SystemExit(subprocess.run(command, cwd=pathlib.Path.cwd(), check=False).returncode)
sys.argv.remove(WORKER_MARKER)
if str(GROUNDED) not in sys.path:
    sys.path.insert(0, str(GROUNDED))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import rr_api  # noqa: E402
from _evidence import (  # noqa: E402
    execution_input_manifest,
    git_record,
    python_process_observation,
    repo_label,
    runtime_record,
    traced_python_command,
    utc_now,
    write_new_receipt,
)
from transport_envelope import encode_request_frame, read_response_frame, sha256  # noqa: E402


b1 = rr_api.b1
PACKS = (
    REPO / "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json",
    REPO / "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
)
PAIR_REPETITIONS = 11
PAIR_INNER_LOOPS = 3
INTEGRATION_REPETITIONS = 3
CPROFILE_CORPUS_LOOPS = 3


def load_fixtures() -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    for path in PACKS:
        pack = json.loads(path.read_text(encoding="utf-8"))
        for entry in pack["entries"]:
            fixtures.append(
                {
                    "entry_id": entry["entry_id"],
                    "raw": base64.b64decode(entry["semantic_request_jcs_lf_base64"], validate=True),
                    "expected": base64.b64decode(entry["expected_response_jcs_lf_base64"], validate=True),
                    "request": entry["semantic_request"],
                }
            )
    fixtures.sort(key=lambda item: item["entry_id"].encode("utf-8"))
    if len(fixtures) != 124:
        raise RuntimeError(f"expected 124 semantic fixtures, got {len(fixtures)}")
    return fixtures


def load_legacy_oracle() -> Any:
    spec = importlib.util.spec_from_file_location("rr_wp5_legacy_audit", ORACLE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load single-pass audit oracle")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def atomic_call_count(function: Callable[[], Any]) -> int:
    original = b1._eval_atomic
    count = 0

    def counted(node: dict[str, Any], doc: Any) -> bool:
        nonlocal count
        count += 1
        return original(node, doc)

    b1._eval_atomic = counted
    try:
        function()
    finally:
        b1._eval_atomic = original
    return count


def summarize(values: list[float]) -> dict[str, float | int]:
    return {
        "n": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "pstdev": statistics.pstdev(values),
        "max": max(values),
    }


def paired_interleaved(
    name: str,
    items: Iterable[Any],
    left_name: str,
    left: Callable[[Any], Any],
    right_name: str,
    right: Callable[[Any], Any],
    *,
    repetitions: int = PAIR_REPETITIONS,
    inner_loops: int = PAIR_INNER_LOOPS,
) -> dict[str, Any]:
    material = list(items)
    for item in material:
        left(item)
        right(item)
    left_samples: list[float] = []
    right_samples: list[float] = []
    ratios: list[float] = []
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        for repetition in range(repetitions):
            gc.collect()
            left_ns = 0
            right_ns = 0
            for index, item in enumerate(material):
                for inner in range(inner_loops):
                    order = ((left_name, left), (right_name, right))
                    if (repetition + index + inner) % 2:
                        order = tuple(reversed(order))
                    for label, function in order:
                        before = time.perf_counter_ns()
                        function(item)
                        elapsed = time.perf_counter_ns() - before
                        if label == left_name:
                            left_ns += elapsed
                        else:
                            right_ns += elapsed
            divisor = len(material) * inner_loops * 1_000_000
            left_ms = left_ns / divisor
            right_ms = right_ns / divisor
            left_samples.append(left_ms)
            right_samples.append(right_ms)
            ratios.append(right_ms / left_ms)
    finally:
        if was_enabled:
            gc.enable()
    return {
        "name": name,
        "method": "paired per item; call order alternates by repetition + item + inner loop",
        "items": len(material),
        "repetitions": repetitions,
        "inner_loops": inner_loops,
        "left": {"name": left_name, "samples_ms_per_item": left_samples, "summary": summarize(left_samples)},
        "right": {
            "name": right_name,
            "samples_ms_per_item": right_samples,
            "summary": summarize(right_samples),
        },
        "right_over_left_ratio": {"samples": ratios, "summary": summarize(ratios)},
    }


def corpus_pair(
    name: str,
    left_name: str,
    left: Callable[[], None],
    right_name: str,
    right: Callable[[], None],
    item_count: int,
) -> dict[str, Any]:
    left()
    right()
    left_samples: list[float] = []
    right_samples: list[float] = []
    ratios: list[float] = []
    for repetition in range(INTEGRATION_REPETITIONS):
        order = ((left_name, left), (right_name, right))
        if repetition % 2:
            order = tuple(reversed(order))
        elapsed_by_name: dict[str, int] = {}
        for label, function in order:
            before = time.perf_counter_ns()
            function()
            elapsed_by_name[label] = time.perf_counter_ns() - before
        left_ms = elapsed_by_name[left_name] / item_count / 1_000_000
        right_ms = elapsed_by_name[right_name] / item_count / 1_000_000
        left_samples.append(left_ms)
        right_samples.append(right_ms)
        ratios.append(right_ms / left_ms)
    return {
        "name": name,
        "method": "paired whole-corpus observations; first/second order alternates by repetition",
        "items": item_count,
        "repetitions": INTEGRATION_REPETITIONS,
        "left": {"name": left_name, "samples_ms_per_item": left_samples, "summary": summarize(left_samples)},
        "right": {
            "name": right_name,
            "samples_ms_per_item": right_samples,
            "summary": summarize(right_samples),
        },
        "right_over_left_ratio": {"samples": ratios, "summary": summarize(ratios)},
    }


def profile_rows(profile: cProfile.Profile, limit: int = 30) -> list[dict[str, Any]]:
    stats = pstats.Stats(profile)
    rows: list[dict[str, Any]] = []
    for (filename, line, function), (primitive, total, own, cumulative, _callers) in sorted(
        stats.stats.items(), key=lambda item: item[1][3], reverse=True
    )[:limit]:
        path = pathlib.Path(filename)
        label = repo_label(path) if path.is_absolute() else filename
        rows.append(
            {
                "function": f"{label}:{line}:{function}",
                "primitive_calls": primitive,
                "total_calls": total,
                "own_seconds": own,
                "cumulative_seconds": cumulative,
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    started = utc_now()
    process_observation_before = python_process_observation()
    fixtures = load_fixtures()
    audit_oracle = load_legacy_oracle()
    audit_oracle.run_equivalence()
    legacy = audit_oracle.legacy_decide_audited
    raws = [item["raw"] for item in fixtures]
    decision_inputs = [item["request"]["decision_input"] for item in fixtures]
    canonical_inputs = [b1.jcs_bytes(value) for value in decision_inputs]
    audited_values = [rr_api.decide_audited(raw) for raw in raws]
    audited_bytes = [b1.jcs_bytes(value) + b"\n" for value in audited_values]

    reduced_fixtures = 0
    atomic_calls_saved = 0
    work_failures: list[str] = []
    for fixture in fixtures:
        raw = fixture["raw"]
        legacy_calls = atomic_call_count(lambda raw=raw: legacy(raw))
        accepted_calls = atomic_call_count(lambda raw=raw: rr_api.decide_audited(raw))
        if accepted_calls > legacy_calls:
            work_failures.append(fixture["entry_id"])
        if accepted_calls < legacy_calls:
            reduced_fixtures += 1
            atomic_calls_saved += legacy_calls - accepted_calls

    parity_failures: list[str] = []
    identity = hashlib.sha256()
    for fixture, audited, encoded in zip(fixtures, audited_values, audited_bytes, strict=True):
        legacy_encoded = b1.jcs_bytes(legacy(fixture["raw"])) + b"\n"
        if legacy_encoded != encoded:
            parity_failures.append(f"legacy:{fixture['entry_id']}")
        sealed = b1.jcs_bytes(audited["sealed_response"]) + b"\n"
        if sealed != fixture["expected"]:
            parity_failures.append(f"sealed:{fixture['entry_id']}")
        identity.update(fixture["entry_id"].encode("utf-8") + b"\0")
        identity.update(hashlib.sha256(fixture["raw"]).digest())
        identity.update(hashlib.sha256(fixture["expected"]).digest())

    hotpaths = {
        "digest_vs_canonicalize_digest": paired_interleaved(
            "digest_vs_canonicalize_digest",
            list(zip(decision_inputs, canonical_inputs, strict=True)),
            "sha256_precanonical",
            lambda item: b1.sha256_upper(item[1]),
            "jcs_plus_sha256",
            lambda item: b1.sha256_upper(b1.jcs_bytes(item[0])),
        ),
        "raw_digest_vs_audit_seal": paired_interleaved(
            "raw_digest_vs_audit_seal",
            list(zip(raws, audited_values, strict=True)),
            "request_raw_sha256",
            lambda item: b1.sha256_upper(item[0]),
            "audit_self_zero_jcs_sha256",
            lambda item: b1.self_zero_sha256(item[1], "audit_sha256"),
        ),
        "legacy_vs_single_pass_audit": paired_interleaved(
            "legacy_vs_single_pass_audit",
            raws,
            "legacy_two_pass_decide_audited",
            legacy,
            "accepted_single_pass_decide_audited",
            rr_api.decide_audited,
        ),
    }

    profile = cProfile.Profile()
    profile.enable()
    for _ in range(CPROFILE_CORPUS_LOOPS):
        for raw in raws:
            rr_api.decide_audited(raw)
    profile.disable()

    def audited_corpus() -> None:
        for raw in raws:
            rr_api.decide_audited(raw)

    def sidecar_corpus() -> None:
        request_frames = b"".join(
            encode_request_frame(sequence, raw)
            for sequence, raw in enumerate(raws, 1)
        )
        result = subprocess.run(
            traced_python_command(LAUNCHER),
            cwd=REPO,
            input=request_frames,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=60,
        )
        response_stream = io.BytesIO(result.stdout)
        observed_payloads: list[bytes] = []
        correlation_failed = False
        for sequence, (raw, expected_payload) in enumerate(zip(raws, audited_bytes, strict=True), 1):
            try:
                frame = read_response_frame(response_stream, 32 * 1024 * 1024)
            except Exception:
                correlation_failed = True
                break
            if (
                frame is None
                or frame.sequence != sequence
                or frame.request_sha256 != sha256(raw)
                or frame.payload != expected_payload
            ):
                correlation_failed = True
                break
            observed_payloads.append(frame.payload)
        if read_response_frame(response_stream, 32 * 1024 * 1024) is not None:
            correlation_failed = True
        if (
            result.returncode != 0
            or result.stderr
            or correlation_failed
            or observed_payloads != audited_bytes
        ):
            raise RuntimeError("sidecar parity failed during timing")

    audited_vs_sidecar = corpus_pair(
        "audited_library_vs_persistent_sidecar",
        "decide_audited_in_process",
        audited_corpus,
        "sidecar_stdio_startup_amortized_124",
        sidecar_corpus,
        len(raws),
    )

    direct_vs_audited = paired_interleaved(
        "decide_vs_decide_audited",
        raws,
        "decide_in_process",
        rr_api.conformance_execute,
        "decide_audited_in_process",
        rr_api.decide_audited,
    )

    fresh_failures: list[str] = []

    def fresh_one(item: tuple[bytes, bytes]) -> bytes:
        raw, expected = item
        result = subprocess.run(
            traced_python_command(RUNNER, "execute"),
            cwd=REPO,
            input=raw,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
        if result.stdout != expected or result.stderr or result.returncode not in (0, 1):
            fresh_failures.append(hashlib.sha256(raw).hexdigest().upper())
        return result.stdout

    direct_vs_fresh = paired_interleaved(
        "decide_library_vs_fresh_isolated_stdio",
        [(item["raw"], item["expected"]) for item in fixtures],
        "decide_in_process",
        lambda item: rr_api.conformance_execute(item[0]),
        "fresh_process_stdio_-I_-B",
        fresh_one,
        repetitions=INTEGRATION_REPETITIONS,
        inner_loops=1,
    )

    process_observation_after = python_process_observation()
    execution_manifest, complete_source_pins = execution_input_manifest()
    equivalence_evidence = {
        "checks": audit_oracle.checks,
        "failures": audit_oracle.failure_count,
        "fixture_entries": len(fixtures),
        "reduced_fixtures": reduced_fixtures,
        "atomic_calls_saved": atomic_calls_saved,
        "work_nonincrease_failures": work_failures,
    }
    status = (
        "PASS"
        if (
            not parity_failures
            and not fresh_failures
            and not work_failures
            and audit_oracle.failure_count == 0
            and audit_oracle.checks == 1142
            and reduced_fixtures == 93
            and atomic_calls_saved == 116
        )
        else "FAIL"
    )
    receipt: dict[str, Any] = {
        "schema": "receiver-reliance/wp5-profile-receipt-3",
        "status": status,
        "started_utc": started,
        "finished_utc": utc_now(),
        "command": list(sys.orig_argv),
        "requested_argv": [repo_label(pathlib.Path(__file__)), *sys.argv[1:]],
        "runtime": runtime_record(),
        "git": git_record(),
        "contention_observation": {
            "before": process_observation_before,
            "after": process_observation_after,
            "interpretation": (
                "Optional platform-specific executable-name snapshots only; not a universal process census. "
                "Scheduler, power, antivirus, and other load remain uncontrolled."
            ),
        },
        "execution_input_manifest": execution_manifest,
        "source_sha256": complete_source_pins,
        "workload": {
            "semantic_fixture_entries": len(fixtures),
            "ordering": "entry_id sorted by UTF-8 bytes",
            "identity_root_sha256": identity.hexdigest().upper(),
            "child_flags": ["-I", "-B"],
        },
        "parity": {
            "legacy_vs_single_pass_entries": len(fixtures),
            "sealed_response_vs_committed_entries": len(fixtures),
            "failures": parity_failures,
            "fresh_stdio_failures": fresh_failures,
        },
        "accepted_single_pass_equivalence": equivalence_evidence,
        "hotpath_timing": hotpaths,
        "accepted_audit_cprofile": {
            "corpus_loops": CPROFILE_CORPUS_LOOPS,
            "calls": CPROFILE_CORPUS_LOOPS * len(fixtures),
            "top_by_cumulative_seconds": profile_rows(profile),
            "interpretation": "Attribution only. cProfile instrumentation changes absolute timings and rows are cumulative, not additive.",
        },
        "integration_modes": {
            "decide_vs_audited": direct_vs_audited,
            "audited_vs_sidecar": audited_vs_sidecar,
            "decide_vs_fresh_stdio": direct_vs_fresh,
        },
        "optimization_admission": {
            "new_optimization_admitted": False,
            "outcome": "charter_fallback_cost_model_and_sidecar_packaging",
            "reason": (
                "The accepted single-pass audit path is byte-identical and reduces predicate work, "
                "but this paired run is observational and does not establish a stable wall-clock speedup. "
                "No additional engine mutation was attempted."
            ),
        },
        "limits": [
            "Numbers are observations for this host, runtime, checkout, workload, and concurrent desktop state.",
            "Fresh stdio includes process creation, interpreter startup, imports, engine work, and pipes.",
            "Sidecar timing includes one process startup and shutdown amortized across exactly 124 requests.",
            "Direct hotpath probes are non-additive and do not allocate causal shares of end-to-end latency.",
            "Re-run on the target deployment host before setting budgets or thresholds.",
        ],
    }
    embedded, raw_digest = write_new_receipt(args.receipt, receipt)
    print(
        f"wp5 profile: status={status} fixtures={len(fixtures)} "
        f"receipt={repo_label(args.receipt)} embedded_sha256={embedded} raw_sha256={raw_digest}"
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
