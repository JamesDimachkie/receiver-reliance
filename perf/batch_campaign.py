#!/usr/bin/env python3
"""Resumable 50k differential campaign for the persistent audited batch path.

This harness regenerates (but never writes) the first reference 50k raw-input
identities, excludes their SHA-256 values, and deterministically selects 50k
additional unique requests that are exactly one NDJSON physical line.  Each
atomic 1,000-case chunk compares one persistent isolated subprocess with
independently computed ``rr_api.decide_audited`` JCS+LF bytes.

No corpus or checkpoint is committed.  ``--self-test`` and ``--plan-only``
are read-only smoke modes.  ``--run`` is the explicitly gated campaign mode.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import pathlib
import platform
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
FUZZ_DIR = REPO / "fuzz"
GROUNDED = REPO / "grounded-0_4"
for module_dir in (FUZZ_DIR, GROUNDED):
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))

import fuzz as oracle  # noqa: E402
import rr_api  # noqa: E402


FORMAT_VERSION = "RR-AUDITED-BATCH-CAMPAIGN-0.1"
TARGET_CASES = 50_000
CHUNK_SIZE = 1_000
CANDIDATE_BASE_SEED = 0xD150000000000000
SOURCE_CASES_PER_SEED = 1_000
MAX_SOURCE_CHUNKS = 512
FRESH_SAMPLE_COUNT = 128
P1_AUDITED_IN_PROCESS_MS = 5.288240
P1_FRESH_STDIO_MS = 154.984114
THREE_X_P1_MS = 3 * P1_AUDITED_IN_PROCESS_MS
BATCH_TIMEOUT_SECONDS = 300.0

REFERENCE_STREAMS = (
    ("pilot", 0x5252465A00000000, 20),
    ("A", 0xA100000000000000, 14),
    ("B", 0xB100000000000000, 8),
    ("C", 0xC100000000000000, 8),
)

# Filled from the deterministic plan before admission; self-test makes source
# or schedule drift explicit instead of silently changing campaign identity.
EXPECTED_REFERENCE_IDENTITY_ROOT = "0B40CC2963B56770909650D006CCE89EBC5DBF4534942E62FD91797820BA2090"
EXPECTED_CANDIDATE_IDENTITY_ROOT = "9F46680E1D7D0006126ACB046F6CB0EC0CC3EA1CDA094FC8B1A484489B056B20"

BATCH_RUNNER = GROUNDED / "rr_batch.py"
RR_API = GROUNDED / "rr_api.py"
ORACLE = FUZZ_DIR / "fuzz.py"
DEFAULT_STATE_DIR = HERE / ".batch-campaign-work"


class CampaignError(RuntimeError):
    """The deterministic plan, checkpoint, or subprocess evidence is invalid."""


@dataclass(frozen=True)
class SelectedCase:
    selected_index: int
    source_seed: int
    source_index: int
    strategy: str
    raw_sha256: str
    raw: bytes


@dataclass
class CampaignPlan:
    selected: list[SelectedCase]
    reference_hash_count: int
    reference_identity_root: str
    candidate_identity_root: str
    source_chunks: int
    distributions: dict[str, dict[str, int]]
    exclusion_reasons: dict[str, int]


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def file_sha256(path: pathlib.Path) -> str:
    return sha256(path.read_bytes())


def one_physical_line(raw: bytes) -> bool:
    return raw.endswith(b"\n") and b"\n" not in raw[:-1]


def _counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items()))


def reference_hashes() -> tuple[set[str], str, Counter[str], int]:
    """Regenerate the exact pilot+A+B+C first-half schedule."""
    hashes: set[str] = set()
    identity = hashlib.sha256()
    strategies: Counter[str] = Counter()
    generated = 0
    for stream, base_seed, chunk_count in REFERENCE_STREAMS:
        for chunk_id in range(chunk_count):
            seed = base_seed + chunk_id
            cases = oracle.generate_cases(seed, CHUNK_SIZE, list(oracle.STRATEGIES))
            if len(cases) != CHUNK_SIZE:
                raise CampaignError(f"reference {stream}/{chunk_id} did not generate 1000 cases")
            for case in cases:
                raw_digest = sha256(case.raw)
                hashes.add(raw_digest)
                strategies[case.strategy] += 1
                identity.update(
                    (
                        f"{stream},{chunk_id},{seed:016X},{case.index},"
                        f"{case.strategy},{raw_digest}\n"
                    ).encode("ascii")
                )
                generated += 1
    if generated != TARGET_CASES:
        raise CampaignError(f"reference schedule generated {generated}, expected {TARGET_CASES}")
    return hashes, identity.hexdigest().upper(), strategies, generated


def build_plan(target_cases: int = TARGET_CASES) -> CampaignPlan:
    if target_cases <= 0 or target_cases % CHUNK_SIZE:
        raise CampaignError("target must be a positive multiple of 1000")
    reference, reference_root, reference_strategies, generated_reference = reference_hashes()
    selected: list[SelectedCase] = []
    selected_hashes: set[str] = set()
    candidate_identity = hashlib.sha256()
    generated_strategies: Counter[str] = Counter()
    selected_strategies: Counter[str] = Counter()
    excluded_by_strategy: dict[str, Counter[str]] = {
        "non_single_line": Counter(),
        "reference_overlap": Counter(),
        "candidate_duplicate": Counter(),
        "target_full": Counter(),
    }
    reasons: Counter[str] = Counter()
    source_chunk_id = 0
    while len(selected) < target_cases:
        if source_chunk_id >= MAX_SOURCE_CHUNKS:
            raise CampaignError(
                f"candidate schedule exhausted {MAX_SOURCE_CHUNKS} source chunks at "
                f"{len(selected)}/{target_cases} unique admissible requests"
            )
        seed = CANDIDATE_BASE_SEED + source_chunk_id
        cases = oracle.generate_cases(seed, SOURCE_CASES_PER_SEED, list(oracle.STRATEGIES))
        if len(cases) != SOURCE_CASES_PER_SEED:
            raise CampaignError(f"candidate source chunk {source_chunk_id} was short")
        for case in cases:
            generated_strategies[case.strategy] += 1
            raw_digest = sha256(case.raw)
            reason = None
            if not one_physical_line(case.raw):
                reason = "non_single_line"
            elif raw_digest in reference:
                reason = "reference_overlap"
            elif raw_digest in selected_hashes:
                reason = "candidate_duplicate"
            elif len(selected) >= target_cases:
                reason = "target_full"
            if reason is not None:
                excluded_by_strategy[reason][case.strategy] += 1
                reasons[reason] += 1
                continue
            selected_index = len(selected)
            selected_hashes.add(raw_digest)
            selected_strategies[case.strategy] += 1
            selected_case = SelectedCase(
                selected_index,
                seed,
                case.index,
                case.strategy,
                raw_digest,
                case.raw,
            )
            selected.append(selected_case)
            candidate_identity.update(
                (
                    f"{selected_index},{seed:016X},{case.index},"
                    f"{case.strategy},{raw_digest}\n"
                ).encode("ascii")
            )
        source_chunk_id += 1

    if len(selected_hashes) != target_cases:
        raise CampaignError("candidate selected hashes are not unique")
    if selected_hashes & reference:
        raise CampaignError("candidate plan overlaps the first reference 50k")
    if any(not one_physical_line(case.raw) for case in selected):
        raise CampaignError("candidate plan contains a non-admissible physical line")
    distributions = {
        "reference_generated": _counter(reference_strategies),
        "candidate_generated": _counter(generated_strategies),
        "selected": _counter(selected_strategies),
    }
    for reason, counts in excluded_by_strategy.items():
        distributions[f"excluded_{reason}"] = _counter(counts)
    if generated_reference != TARGET_CASES or sum(selected_strategies.values()) != target_cases:
        raise CampaignError("strategy accounting does not sum to the planned totals")
    return CampaignPlan(
        selected=selected,
        reference_hash_count=len(reference),
        reference_identity_root=reference_root,
        candidate_identity_root=candidate_identity.hexdigest().upper(),
        source_chunks=source_chunk_id,
        distributions=distributions,
        exclusion_reasons=_counter(reasons),
    )


def chunk_cases(plan: CampaignPlan, chunk_id: int) -> list[SelectedCase]:
    start = chunk_id * CHUNK_SIZE
    cases = plan.selected[start : start + CHUNK_SIZE]
    if len(cases) != CHUNK_SIZE:
        raise CampaignError(f"execution chunk {chunk_id} is not exactly 1000 cases")
    return cases


def chunk_identity(cases: list[SelectedCase]) -> str:
    digest = hashlib.sha256()
    for case in cases:
        digest.update(
            (
                f"{case.selected_index},{case.source_seed:016X},{case.source_index},"
                f"{case.strategy},{case.raw_sha256}\n"
            ).encode("ascii")
        )
    return digest.hexdigest().upper()


class ResourceProbe:
    """Best-effort stdlib child peak-working-set observation."""

    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.kind = "unavailable"
        self.peak_bytes: int | None = None
        self.samples = 0
        self._handle = None
        self._counter_type = None
        if os.name == "nt":
            from ctypes import wintypes

            class ProcessMemoryCountersEx(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t),
                ]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(ProcessMemoryCountersEx),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            handle = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
            if handle:
                self.kind = "windows-peak-working-set"
                self._handle = handle
                self._kernel32 = kernel32
                self._psapi = psapi
                self._counter_type = ProcessMemoryCountersEx
        elif pathlib.Path(f"/proc/{pid}/status").is_file():
            self.kind = "linux-proc-vmhwm"

    def sample(self) -> None:
        if self.kind == "windows-peak-working-set" and self._handle is not None:
            counters = self._counter_type()
            counters.cb = ctypes.sizeof(counters)
            if self._psapi.GetProcessMemoryInfo(
                self._handle, ctypes.byref(counters), counters.cb
            ):
                value = int(counters.PeakWorkingSetSize)
                self.peak_bytes = max(self.peak_bytes or 0, value)
                self.samples += 1
        elif self.kind == "linux-proc-vmhwm":
            try:
                lines = pathlib.Path(f"/proc/{self.pid}/status").read_text().splitlines()
                value = next(int(line.split()[1]) * 1024 for line in lines if line.startswith("VmHWM:"))
            except (OSError, StopIteration, ValueError):
                return
            self.peak_bytes = max(self.peak_bytes or 0, value)
            self.samples += 1

    def close(self) -> None:
        if self._handle is not None:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


def communicate_observed(payload: bytes) -> dict[str, Any]:
    command = [sys.executable, "-I", "-B", str(BATCH_RUNNER)]
    process = subprocess.Popen(
        command,
        cwd=REPO,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    probe = ResourceProbe(process.pid)
    holder: dict[str, Any] = {}

    def communicate() -> None:
        try:
            holder["stdout"], holder["stderr"] = process.communicate(
                payload, timeout=BATCH_TIMEOUT_SECONDS
            )
            holder["timed_out"] = False
        except subprocess.TimeoutExpired:
            process.kill()
            holder["stdout"], holder["stderr"] = process.communicate()
            holder["timed_out"] = True
        except Exception as error:  # noqa: BLE001 - preserve harness failure evidence
            process.kill()
            holder["stdout"], holder["stderr"] = process.communicate()
            holder["timed_out"] = False
            holder["communication_error"] = f"{type(error).__name__}: {error}"

    started = time.perf_counter_ns()
    thread = threading.Thread(target=communicate, name="batch-campaign-communicate")
    thread.start()
    while thread.is_alive():
        probe.sample()
        thread.join(0.01)
    probe.sample()
    elapsed_ns = time.perf_counter_ns() - started
    probe.close()
    return {
        "returncode": process.returncode,
        "stdout": holder.get("stdout", b""),
        "stderr": holder.get("stderr", b""),
        "timed_out": holder.get("timed_out", True),
        "communication_error": holder.get("communication_error"),
        "elapsed_seconds": elapsed_ns / 1_000_000_000,
        "resource_kind": probe.kind,
        "child_peak_bytes": probe.peak_bytes,
        "resource_samples": probe.samples,
    }


def independent_expectations(cases: list[SelectedCase]) -> tuple[list[bytes], dict[str, Any]]:
    started = time.perf_counter_ns()
    audited = [rr_api.decide_audited(case.raw) for case in cases]
    decided_ns = time.perf_counter_ns() - started
    started = time.perf_counter_ns()
    expected = [rr_api.b1.jcs_bytes(value) + b"\n" for value in audited]
    encoded_ns = time.perf_counter_ns() - started
    return expected, {
        "direct_decide_seconds": decided_ns / 1_000_000_000,
        "direct_encode_seconds": encoded_ns / 1_000_000_000,
        "direct_total_seconds": (decided_ns + encoded_ns) / 1_000_000_000,
        "expected_bytes": sum(map(len, expected)),
        "max_expected_response_bytes": max(map(len, expected)),
    }


def execute_chunk(cases: list[SelectedCase], chunk_id: int) -> dict[str, Any]:
    expected, direct = independent_expectations(cases)
    payload = b"".join(case.raw for case in cases)
    observed = communicate_observed(payload)
    stdout = observed.pop("stdout")
    stderr = observed.pop("stderr")
    lines = stdout.splitlines(keepends=True)
    first_mismatch = None
    for index, (actual, wanted) in enumerate(zip(lines, expected)):
        if actual != wanted:
            first_mismatch = {
                "offset": index,
                "selected_index": cases[index].selected_index,
                "raw_sha256": cases[index].raw_sha256,
                "actual_sha256": sha256(actual),
                "expected_sha256": sha256(wanted),
            }
            break
    parity = (
        observed["returncode"] == 0
        and not observed["timed_out"]
        and observed["communication_error"] is None
        and stderr == b""
        and len(lines) == len(cases)
        and first_mismatch is None
        and stdout == b"".join(expected)
    )
    return {
        "status": "pass" if parity else "failure",
        "chunk_id": chunk_id,
        "cases": len(cases),
        "identity_sha256": chunk_identity(cases),
        "selected_first": cases[0].selected_index,
        "selected_last": cases[-1].selected_index,
        "strategy_counts": _counter(Counter(case.strategy for case in cases)),
        "input_bytes": len(payload),
        "output_bytes": len(stdout),
        "response_count": len(lines),
        "ordered_byte_parity": parity,
        "first_mismatch": first_mismatch,
        "stderr_bytes": len(stderr),
        "stderr_sha256": sha256(stderr),
        "stdout_sha256": sha256(stdout),
        **direct,
        **observed,
    }


def fresh_sample_indices(count: int = FRESH_SAMPLE_COUNT) -> list[int]:
    if count < 2:
        raise CampaignError("fresh-process sample must contain at least two cases")
    return [index * (TARGET_CASES - 1) // (count - 1) for index in range(count)]


def execute_fresh_sample(plan: CampaignPlan, count: int = FRESH_SAMPLE_COUNT) -> dict[str, Any]:
    records = []
    identity = hashlib.sha256()
    for selected_index in fresh_sample_indices(count):
        case = plan.selected[selected_index]
        expected = rr_api.b1.jcs_bytes(rr_api.decide_audited(case.raw)) + b"\n"
        observed = communicate_observed(case.raw)
        stdout = observed.pop("stdout")
        stderr = observed.pop("stderr")
        parity = (
            observed["returncode"] == 0
            and not observed["timed_out"]
            and observed["communication_error"] is None
            and stderr == b""
            and stdout == expected
        )
        identity.update(f"{selected_index},{case.raw_sha256}\n".encode("ascii"))
        records.append(
            {
                "selected_index": selected_index,
                "raw_sha256": case.raw_sha256,
                "elapsed_ms": observed["elapsed_seconds"] * 1000,
                "parity": parity,
                "returncode": observed["returncode"],
                "stderr_bytes": len(stderr),
                "resource_kind": observed["resource_kind"],
                "child_peak_bytes": observed["child_peak_bytes"],
            }
        )
        if not parity:
            break
    latencies = [record["elapsed_ms"] for record in records]
    return {
        "status": "pass" if len(records) == count and all(r["parity"] for r in records) else "failure",
        "count": len(records),
        "planned_count": count,
        "identity_sha256": identity.hexdigest().upper(),
        "indices": [record["selected_index"] for record in records],
        "latency_ms": latencies,
        "median_ms": statistics.median(latencies),
        "p95_ms": percentile(latencies, 95),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "peak_child_bytes": max(
            (record["child_peak_bytes"] or 0 for record in records), default=0
        ),
        "records": records,
    }


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def plan_summary(plan: CampaignPlan) -> dict[str, Any]:
    chunk_roots = [chunk_identity(chunk_cases(plan, chunk)) for chunk in range(TARGET_CASES // CHUNK_SIZE)]
    execution_root = hashlib.sha256(
        b"".join(f"{index},{root}\n".encode("ascii") for index, root in enumerate(chunk_roots))
    ).hexdigest().upper()
    return {
        "target_cases": len(plan.selected),
        "chunk_size": CHUNK_SIZE,
        "execution_chunks": len(chunk_roots),
        "reference_generated": TARGET_CASES,
        "reference_unique_raw_hashes": plan.reference_hash_count,
        "reference_identity_root": plan.reference_identity_root,
        "candidate_base_seed": f"0x{CANDIDATE_BASE_SEED:016X}",
        "candidate_source_chunks": plan.source_chunks,
        "candidate_seed_first": f"0x{CANDIDATE_BASE_SEED:016X}",
        "candidate_seed_last": f"0x{CANDIDATE_BASE_SEED + plan.source_chunks - 1:016X}",
        "candidate_identity_root": plan.candidate_identity_root,
        "execution_chunk_root": execution_root,
        "exclusion_reasons": plan.exclusion_reasons,
        "distributions": plan.distributions,
    }


def runtime_config(plan: CampaignPlan) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "target_cases": TARGET_CASES,
        "chunk_size": CHUNK_SIZE,
        "fresh_sample_count": FRESH_SAMPLE_COUNT,
        "reference_streams": [list(item) for item in REFERENCE_STREAMS],
        "candidate_base_seed": CANDIDATE_BASE_SEED,
        "source_cases_per_seed": SOURCE_CASES_PER_SEED,
        "strategies": list(oracle.STRATEGIES),
        "plan": plan_summary(plan),
        "files": {
            "batch_campaign.py": file_sha256(pathlib.Path(__file__).resolve()),
            "fuzz.py": file_sha256(ORACLE),
            "rr_api.py": file_sha256(RR_API),
            "rr_batch.py": file_sha256(BATCH_RUNNER),
        },
        "python": sys.version.replace("\n", " "),
        "python_executable": str(pathlib.Path(sys.executable).resolve()),
    }


def atomic_write(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    payload = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_state(path: pathlib.Path, config: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        state = {
            "format_version": FORMAT_VERSION,
            "config": config,
            "machine": {
                "platform": platform.platform(),
                "machine": platform.machine(),
                "logical_cpu_count": os.cpu_count(),
            },
            "chunks": {},
            "fresh_process_sample": None,
            "runs": [],
        }
        atomic_write(path, state)
        return state
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CampaignError(f"cannot read checkpoint: {error}") from error
    if state.get("format_version") != FORMAT_VERSION or state.get("config") != config:
        raise CampaignError("checkpoint identity differs from the current deterministic plan/runtime")
    if not isinstance(state.get("chunks"), dict) or not isinstance(state.get("runs"), list):
        raise CampaignError("checkpoint collections are malformed")
    return state


def aggregate(state: dict[str, Any]) -> dict[str, Any]:
    chunks = [state["chunks"].get(str(index)) for index in range(TARGET_CASES // CHUNK_SIZE)]
    passed = [record for record in chunks if isinstance(record, dict) and record.get("status") == "pass"]
    cases = sum(record["cases"] for record in passed)
    batch_seconds = sum(record["elapsed_seconds"] for record in passed)
    direct_seconds = sum(record["direct_decide_seconds"] for record in passed)
    batch_ms = batch_seconds / cases * 1000 if cases else None
    direct_ms = direct_seconds / cases * 1000 if cases else None
    ratio = batch_ms / direct_ms if batch_ms is not None and direct_ms else None
    fresh = state.get("fresh_process_sample")
    return {
        "cases": cases,
        "chunks": len(passed),
        "parity_failures": sum(
            isinstance(record, dict) and record.get("status") == "failure" for record in chunks
        ),
        "batch_seconds": batch_seconds,
        "direct_decide_seconds": direct_seconds,
        "persistent_ms_per_request": batch_ms,
        "direct_decide_ms_per_request": direct_ms,
        "persistent_over_direct_ratio": ratio,
        "at_most_3x_local_direct": ratio is not None and ratio <= 3.0,
        "persistent_over_p1_ratio": batch_ms / P1_AUDITED_IN_PROCESS_MS if batch_ms is not None else None,
        "at_most_3x_p1": batch_ms is not None and batch_ms <= THREE_X_P1_MS,
        "chunk_median_ms_per_request": statistics.median(
            record["elapsed_seconds"] / record["cases"] * 1000 for record in passed
        ) if passed else None,
        "chunk_p95_ms_per_request": percentile(
            [record["elapsed_seconds"] / record["cases"] * 1000 for record in passed], 95
        ) if passed else None,
        "peak_child_bytes": max((record.get("child_peak_bytes") or 0 for record in passed), default=0),
        "fresh_process_status": fresh.get("status") if isinstance(fresh, dict) else None,
        "fresh_process_median_ms": fresh.get("median_ms") if isinstance(fresh, dict) else None,
        "persistent_speedup_vs_fresh_sample": (
            fresh["median_ms"] / batch_ms
            if isinstance(fresh, dict) and fresh.get("median_ms") and batch_ms
            else None
        ),
        "p1_fresh_stdio_ms_context_only": P1_FRESH_STDIO_MS,
    }


def run_campaign(plan: CampaignPlan, state_dir: pathlib.Path) -> int:
    state_path = state_dir / "batch_campaign.json"
    config = runtime_config(plan)
    state = read_state(state_path, config)
    run = {
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "starting_cases": aggregate(state)["cases"],
        "status": "running",
    }
    state["runs"].append(run)
    atomic_write(state_path, state)
    for chunk_id in range(TARGET_CASES // CHUNK_SIZE):
        existing = state["chunks"].get(str(chunk_id))
        expected_identity = chunk_identity(chunk_cases(plan, chunk_id))
        if isinstance(existing, dict) and existing.get("status") == "pass":
            if existing.get("identity_sha256") != expected_identity:
                raise CampaignError(f"completed chunk {chunk_id} identity drifted")
            continue
        record = execute_chunk(chunk_cases(plan, chunk_id), chunk_id)
        attempts = list(existing.get("attempts", [])) if isinstance(existing, dict) else []
        attempts.append(record)
        state["chunks"][str(chunk_id)] = {**record, "attempts": attempts}
        atomic_write(state_path, state)
        rate = record["cases"] / record["elapsed_seconds"]
        print(
            f"chunk={chunk_id + 1}/50 status={record['status']} "
            f"identity={record['identity_sha256']} elapsed={record['elapsed_seconds']:.6f}s "
            f"rate={rate:.3f} cases/s peak={record['child_peak_bytes']}",
            flush=True,
        )
        if record["status"] != "pass":
            run.update(status="failed", finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            atomic_write(state_path, state)
            return 1
    if not isinstance(state.get("fresh_process_sample"), dict) or state["fresh_process_sample"].get("status") != "pass":
        state["fresh_process_sample"] = execute_fresh_sample(plan)
        atomic_write(state_path, state)
        if state["fresh_process_sample"]["status"] != "pass":
            run.update(status="failed", finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            atomic_write(state_path, state)
            return 1
    summary = aggregate(state)
    success = (
        summary["cases"] == TARGET_CASES
        and summary["chunks"] == TARGET_CASES // CHUNK_SIZE
        and summary["parity_failures"] == 0
        and summary["fresh_process_status"] == "pass"
        and summary["at_most_3x_local_direct"]
        and summary["at_most_3x_p1"]
    )
    run.update(
        status="pass" if success else "failed",
        finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        final_summary=summary,
    )
    state["summary"] = summary
    atomic_write(state_path, state)
    print("batch-campaign=" + json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0 if success else 1


def self_test(plan: CampaignPlan) -> int:
    checks = 0

    def require(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            raise CampaignError(f"self-test failed: {message}")

    summary = plan_summary(plan)
    require(len(plan.selected) == TARGET_CASES, "selected count")
    require(len({case.raw_sha256 for case in plan.selected}) == TARGET_CASES, "unique hashes")
    require(all(one_physical_line(case.raw) for case in plan.selected), "physical-line filter")
    require(sum(plan.distributions["selected"].values()) == TARGET_CASES, "selected distribution")
    require(summary["execution_chunks"] == 50, "chunk count")
    require(
        plan.reference_identity_root == EXPECTED_REFERENCE_IDENTITY_ROOT,
        f"reference root {plan.reference_identity_root}",
    )
    require(
        plan.candidate_identity_root == EXPECTED_CANDIDATE_IDENTITY_ROOT,
        f"candidate root {plan.candidate_identity_root}",
    )
    first_chunk = chunk_cases(plan, 0)
    require(chunk_identity(first_chunk) == chunk_identity(list(first_chunk)), "chunk identity determinism")
    smoke_cases = first_chunk
    smoke = execute_chunk(smoke_cases, -1)
    require(smoke["status"] == "pass", "1000-case persistent parity smoke")
    fresh = execute_fresh_sample(plan, 4)
    require(fresh["status"] == "pass", "four-case fresh-process smoke")
    with tempfile.TemporaryDirectory() as temporary:
        path = pathlib.Path(temporary) / "atomic.json"
        value = {"format": FORMAT_VERSION, "identity": summary["execution_chunk_root"]}
        atomic_write(path, value)
        require(json.loads(path.read_text(encoding="utf-8")) == value, "atomic checkpoint round-trip")
    print(
        "batch-campaign-self-test: "
        f"checks={checks} failures=0 selected={len(plan.selected)} "
        f"reference_unique={plan.reference_hash_count} source_chunks={plan.source_chunks} "
        f"reference_root={plan.reference_identity_root} candidate_root={plan.candidate_identity_root} "
        f"smoke_batch_ms={smoke['elapsed_seconds'] * 1000:.6f} "
        f"smoke_direct_decide_ms={smoke['direct_decide_seconds'] * 1000:.6f} "
        f"smoke_direct_total_ms={smoke['direct_total_seconds'] * 1000:.6f} "
        f"smoke_peak_child_bytes={smoke['child_peak_bytes']} "
        f"fresh_median_ms={fresh['median_ms']:.6f} "
        f"exclusions={json.dumps(plan.exclusion_reasons, sort_keys=True, separators=(',', ':'))}"
    )
    return 0


def repo_local_path(value: str) -> pathlib.Path:
    path = pathlib.Path(value)
    if not path.is_absolute():
        path = pathlib.Path.cwd() / path
    path = path.resolve()
    try:
        path.relative_to(REPO)
    except ValueError as error:
        raise CampaignError(f"state directory must remain inside the repository: {path}") from error
    return path


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    mode = result.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true", help="regenerate and print identity/distributions")
    mode.add_argument("--self-test", action="store_true", help="run deterministic planning and one 1000-case smoke chunk")
    mode.add_argument("--run", action="store_true", help="execute/resume the authorized 50k campaign")
    result.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        plan = build_plan()
        if args.plan_only:
            print("batch-campaign-plan=" + json.dumps(plan_summary(plan), sort_keys=True, separators=(",", ":")))
            return 0
        if args.self_test:
            return self_test(plan)
        return run_campaign(plan, repo_local_path(args.state_dir))
    except (CampaignError, OSError, ValueError) as error:
        print(f"batch-campaign: ERROR {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
