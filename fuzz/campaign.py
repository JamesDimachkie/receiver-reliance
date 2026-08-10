#!/usr/bin/env python3
"""Resumable deterministic campaign wrapper for the integrated fuzz oracle.

Each chunk invokes ``fuzz.py`` as an unchanged subprocess.  The wrapper only
schedules chunks, verifies their summaries, and persists campaign evidence; it
does not validate runner output itself or replace any oracle invariant.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

import fuzz as oracle


FORMAT_VERSION = "RR-FUZZ-CAMPAIGN-0.1"
DEFAULT_BASE_SEED = 0x5252465A00000000
DEFAULT_CHUNK_SIZE = 1_000
DEFAULT_CHUNK_BUDGET_SECONDS = 900.0
MAX_CAMPAIGN_WORKERS = 16
MAX_FULL_WALL_SECONDS = 6 * 60 * 60
SUMMARY_RE = re.compile(
    r"^rr-fuzz: verdict=(?P<verdict>PASS|FAIL) "
    r"cases=(?P<completed>[0-9]+)/(?P<requested>[0-9]+) "
    r"seed=(?P<seed>\S+) source=(?P<source>\S+) "
    r"failures=(?P<failures>[0-9]+) "
    r"budget_exhausted=(?P<budget_exhausted>true|false)$"
)

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
ORACLE = HERE / "fuzz.py"
RUNNER = REPO / "baseline-run" / "implementation-output-0.3" / "pcb_runner.py"
DEFAULT_STATE_DIR = HERE / "regressions" / ".campaign-work"


class CampaignConfigurationError(ValueError):
    """The campaign configuration or checkpoint is invalid."""


@dataclass(frozen=True)
class ChunkPlan:
    chunk_id: int
    seed: int
    cases: int


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _seed(value: str) -> int:
    try:
        parsed = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a decimal or 0x-prefixed integer") from exc
    if not 0 <= parsed <= (1 << 64) - 1:
        raise argparse.ArgumentTypeError("must fit in an unsigned 64-bit integer")
    return parsed


def _repo_path(value: str) -> pathlib.Path:
    path = pathlib.Path(value)
    if not path.is_absolute():
        path = pathlib.Path.cwd() / path
    path = path.resolve()
    try:
        path.relative_to(REPO)
    except ValueError as exc:
        raise CampaignConfigurationError(
            f"campaign state must stay inside the repository: {path}"
        ) from exc
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic, resumable chunks through the unchanged fuzz oracle."
    )
    parser.add_argument("--target-cases", required=True, type=_positive_int)
    parser.add_argument("--chunk-size", type=_positive_int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--workers", type=_positive_int, default=1)
    parser.add_argument("--base-seed", type=_seed, default=DEFAULT_BASE_SEED)
    parser.add_argument(
        "--state-dir",
        default=str(DEFAULT_STATE_DIR),
        help="repo-local checkpoint directory (default: fuzz/regressions/.campaign-work)",
    )
    parser.add_argument(
        "--phase",
        choices=("pilot", "tuning", "full", "resume"),
        default="pilot",
        help="phase label recorded in the checkpoint; full starts the six-hour cap",
    )
    parser.add_argument(
        "--chunk-budget-seconds",
        type=float,
        default=DEFAULT_CHUNK_BUDGET_SECONDS,
    )
    parser.add_argument("--case-timeout-seconds", type=float, default=5.0)
    parser.add_argument("--max-retries", type=int, default=1)
    return parser


def _validate_args(args: argparse.Namespace) -> pathlib.Path:
    if args.chunk_size > oracle.MAX_CASES:
        raise CampaignConfigurationError(
            f"chunk size exceeds oracle cap of {oracle.MAX_CASES}"
        )
    if not 1 <= args.workers <= MAX_CAMPAIGN_WORKERS:
        raise CampaignConfigurationError(
            f"workers must be between 1 and {MAX_CAMPAIGN_WORKERS}"
        )
    if not 0.0 < args.chunk_budget_seconds <= 86_400.0:
        raise CampaignConfigurationError("chunk budget must be in (0, 86400]")
    if not 0.0 < args.case_timeout_seconds <= 86_400.0:
        raise CampaignConfigurationError("case timeout must be in (0, 86400]")
    if not 0 <= args.max_retries <= 3:
        raise CampaignConfigurationError("max retries must be between 0 and 3")
    chunk_count = (args.target_cases + args.chunk_size - 1) // args.chunk_size
    if args.base_seed + chunk_count - 1 > (1 << 64) - 1:
        raise CampaignConfigurationError("seed schedule would overflow unsigned 64-bit range")
    if not ORACLE.is_file() or not RUNNER.is_file():
        raise CampaignConfigurationError("integrated oracle or runner is missing")
    return _repo_path(args.state_dir)


def _machine_record() -> dict[str, Any]:
    return {
        "logical_cpu_count": os.cpu_count(),
        "machine": platform.machine(),
        "node": platform.node(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": sys.version.replace("\n", " "),
        "python_executable": sys.executable,
    }


def _config(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "base_seed": args.base_seed,
        "chunk_size": args.chunk_size,
        "identity_fields": ["seed", "index", "strategy", "input_sha256"],
        "oracle_sha256": _sha256(ORACLE.read_bytes()),
        "runner_sha256": _sha256(RUNNER.read_bytes()),
        "seed_schedule": "seed = base_seed + zero_based_chunk_id",
        "strategies": list(oracle.STRATEGIES),
        "two_fresh_runner_executions_per_completed_case": True,
    }


def _new_state(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "created_utc": _utc_now(),
        "machine": _machine_record(),
        "config": _config(args),
        "campaign_launch_epoch": None,
        "campaign_launch_utc": None,
        "chunks": {},
        "runs": [],
        "events": [],
    }


def _read_state(path: pathlib.Path, args: argparse.Namespace) -> dict[str, Any]:
    if not path.exists():
        return _new_state(args)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CampaignConfigurationError(f"cannot read checkpoint: {exc}") from exc
    if not isinstance(state, dict) or state.get("format_version") != FORMAT_VERSION:
        raise CampaignConfigurationError("checkpoint format is not supported")
    if state.get("config") != _config(args):
        raise CampaignConfigurationError(
            "checkpoint configuration differs from the requested seed schedule, chunk size, "
            "strategies, oracle, or runner"
        )
    if not isinstance(state.get("chunks"), dict) or not isinstance(state.get("runs"), list):
        raise CampaignConfigurationError("checkpoint collections are malformed")
    recorded_machine = state.get("machine")
    current_machine = _machine_record()
    if not isinstance(recorded_machine, dict) or (
        recorded_machine.get("python") != current_machine["python"]
        or pathlib.Path(str(recorded_machine.get("python_executable", ""))).resolve()
        != pathlib.Path(current_machine["python_executable"]).resolve()
    ):
        raise CampaignConfigurationError(
            "checkpoint Python runtime differs from the current interpreter"
        )
    return state


def _atomic_checkpoint(path: pathlib.Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    payload = json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _plans(target_cases: int, chunk_size: int, base_seed: int) -> list[ChunkPlan]:
    plans: list[ChunkPlan] = []
    remaining = target_cases
    chunk_id = 0
    while remaining:
        count = min(chunk_size, remaining)
        plans.append(ChunkPlan(chunk_id, base_seed + chunk_id, count))
        remaining -= count
        chunk_id += 1
    return plans


def _identity_digest(plan: ChunkPlan) -> tuple[str, dict[str, int]]:
    cases = oracle.generate_cases(plan.seed, plan.cases, list(oracle.STRATEGIES))
    seen: set[tuple[int | None, int, str, str]] = set()
    digest = hashlib.sha256()
    counts: Counter[str] = Counter()
    for case in cases:
        input_digest = _sha256(case.raw)
        identity = (case.seed, case.index, case.strategy, input_digest)
        if identity in seen:
            raise CampaignConfigurationError(
                f"duplicate input identity inside chunk {plan.chunk_id}: {identity}"
            )
        seen.add(identity)
        counts[case.strategy] += 1
        digest.update(
            f"{case.seed:016X},{case.index},{case.strategy},{input_digest}\n".encode("ascii")
        )
    if len(seen) != plan.cases:
        raise CampaignConfigurationError(
            f"chunk {plan.chunk_id} generated {len(seen)} identities, expected {plan.cases}"
        )
    return digest.hexdigest().upper(), dict(sorted(counts.items()))


def _json_line(lines: list[str], prefix: str) -> dict[str, int] | None:
    matches = [line for line in lines if line.startswith(prefix)]
    if len(matches) != 1:
        return None
    try:
        value = json.loads(matches[0][len(prefix) :])
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    if any(not isinstance(key, str) or not isinstance(count, int) for key, count in value.items()):
        return None
    return value


def _parse_summary(stdout: str) -> dict[str, Any] | None:
    lines = stdout.splitlines()
    summary_lines = [line for line in lines if line.startswith("rr-fuzz: ")]
    if len(summary_lines) != 1:
        return None
    match = SUMMARY_RE.fullmatch(summary_lines[0])
    strategy_counts = _json_line(lines, "strategy_counts=")
    exit_counts = _json_line(lines, "exit_counts=")
    if match is None or strategy_counts is None or exit_counts is None:
        return None
    parsed: dict[str, Any] = match.groupdict()
    for key in ("completed", "requested", "failures"):
        parsed[key] = int(parsed[key])
    parsed["budget_exhausted"] = parsed["budget_exhausted"] == "true"
    parsed["strategy_counts"] = strategy_counts
    parsed["exit_counts"] = exit_counts
    return parsed


def _tail(value: str, limit: int = 2_000) -> str:
    return value if len(value) <= limit else value[-limit:]


def _run_chunk(
    plan: ChunkPlan,
    *,
    attempt: int,
    state_dir: pathlib.Path,
    chunk_budget_seconds: float,
    case_timeout_seconds: float,
    deadline_epoch: float | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    identity_digest, expected_strategy_counts = _identity_digest(plan)
    failures_dir = state_dir / "failures"
    failures_dir.mkdir(parents=True, exist_ok=True)
    failure_path = failures_dir / f"chunk-{plan.chunk_id:06d}-attempt-{attempt}.jsonl"

    effective_budget = chunk_budget_seconds
    if deadline_epoch is not None:
        effective_budget = min(effective_budget, max(0.001, deadline_epoch - time.time()))
    command = [
        sys.executable,
        "-B",
        str(ORACLE),
        "--seed",
        f"0x{plan.seed:016X}",
        "--cases",
        str(plan.cases),
        "--budget-seconds",
        f"{effective_budget:.6f}",
        "--case-timeout-seconds",
        f"{case_timeout_seconds:.6f}",
        "--failures-out",
        str(failure_path),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=REPO,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=effective_budget + 30.0,
        )
        returncode: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        wrapper_timeout = False
    except subprocess.TimeoutExpired as exc:
        returncode = None
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        wrapper_timeout = True

    elapsed = time.perf_counter() - started
    summary = _parse_summary(stdout)
    oracle_validator_failed = any(
        line.startswith("FAIL ") and "harness response validator raised" in line
        for line in stdout.splitlines()
    )
    status = "harness_error"
    classification = "harness_or_configuration_failure"
    completed_cases = 0
    runner_executions: int | None = None
    errors: list[str] = []

    if wrapper_timeout:
        errors.append("campaign wrapper timed out waiting for the oracle subprocess")
    elif summary is None:
        errors.append("oracle output did not contain one parseable summary and count pair")
    else:
        completed_cases = summary["completed"]
        expected_seed = f"0x{plan.seed:016X}"
        structural_errors = []
        if summary["requested"] != plan.cases:
            structural_errors.append("oracle requested-case count differs from the chunk plan")
        if summary["seed"] != expected_seed or summary["source"] != "generated":
            structural_errors.append("oracle seed/source differs from the chunk plan")
        if summary["strategy_counts"] != expected_strategy_counts:
            structural_errors.append("oracle strategy counts differ from deterministic generation")
        if sum(summary["exit_counts"].values()) + summary["failures"] != completed_cases:
            structural_errors.append("oracle exit/failure counts do not sum to completed cases")
        errors.extend(structural_errors)

        clean_pass = (
            not structural_errors
            and returncode == 0
            and summary["verdict"] == "PASS"
            and summary["completed"] == plan.cases
            and summary["failures"] == 0
            and not summary["budget_exhausted"]
            and not stderr
        )
        if clean_pass:
            status = "pass"
            classification = "no_invariant_breach"
            runner_executions = plan.cases * 2
        elif not structural_errors and summary["budget_exhausted"]:
            status = "incomplete"
            classification = "campaign_or_harness_budget_exhaustion"
            errors.append("oracle budget exhausted; this is not classified as a runner finding")
        elif (
            not structural_errors
            and returncode == 1
            and summary["verdict"] == "FAIL"
            and summary["completed"] == plan.cases
            and summary["failures"] > 0
            and not summary["budget_exhausted"]
        ):
            if oracle_validator_failed:
                status = "harness_error"
                classification = "oracle_validator_failure_not_runner_finding"
                errors.append(
                    "oracle response validator raised; this is not classified as a runner finding"
                )
            else:
                status = "breach"
                classification = "candidate_runner_invariant_breach"
        else:
            errors.append("oracle exit/verdict/stderr combination is not a valid completed result")

    durable_failure_path: str | None = None
    if status == "breach":
        if failure_path.is_file():
            durable = HERE / "regressions" / f"chunk-{plan.chunk_id:06d}.jsonl"
            shutil.copyfile(failure_path, durable)
            durable_failure_path = durable.relative_to(REPO).as_posix()
        else:
            status = "harness_error"
            classification = "harness_or_configuration_failure"
            errors.append("oracle reported failures but did not write the requested exact corpus")

    return {
        "attempt": attempt,
        "cases": plan.cases,
        "chunk_id": plan.chunk_id,
        "classification": classification,
        "completed_cases": completed_cases,
        "effective_budget_seconds": effective_budget,
        "elapsed_seconds": elapsed,
        "errors": errors,
        "failure_corpus": durable_failure_path,
        "identity_digest": identity_digest,
        "oracle_returncode": returncode,
        "runner_executions": runner_executions,
        "seed": plan.seed,
        "status": status,
        "stderr_sha256": _sha256(stderr.encode("utf-8")),
        "stderr_tail": _tail(stderr),
        "stdout_sha256": _sha256(stdout.encode("utf-8")),
        "stdout_tail": _tail(stdout),
        "summary": summary,
    }


def _is_completed(record: dict[str, Any]) -> bool:
    return record.get("status") in {"pass", "breach"}


def _aggregate(state: dict[str, Any], plans: list[ChunkPlan]) -> dict[str, Any]:
    plan_ids = {str(plan.chunk_id) for plan in plans}
    records = [
        record
        for chunk_id, record in state["chunks"].items()
        if chunk_id in plan_ids and _is_completed(record)
    ]
    records.sort(key=lambda item: item["chunk_id"])
    strategy_counts: Counter[str] = Counter()
    exit_counts: Counter[str] = Counter()
    cases = 0
    runner_executions = 0
    runner_executions_exact = True
    digest = hashlib.sha256()
    for record in records:
        summary = record["summary"]
        cases += record["cases"]
        strategy_counts.update(summary["strategy_counts"])
        exit_counts.update(summary["exit_counts"])
        if record["runner_executions"] is None:
            runner_executions_exact = False
        else:
            runner_executions += record["runner_executions"]
        digest.update(
            (
                f"{record['chunk_id']},{record['seed']:016X},{record['cases']},"
                f"{record['identity_digest']}\n"
            ).encode("ascii")
        )
    seeds = [record["seed"] for record in records]
    return {
        "candidate_breach_chunks": sum(record["status"] == "breach" for record in records),
        "cases": cases,
        "chunk_count": len(records),
        "identity_root_sha256": digest.hexdigest().upper(),
        "runner_executions": runner_executions if runner_executions_exact else None,
        "runner_executions_exact": runner_executions_exact,
        "seed_first": min(seeds) if seeds else None,
        "seed_last": max(seeds) if seeds else None,
        "strategy_counts": dict(sorted(strategy_counts.items())),
        "exit_counts": dict(sorted(exit_counts.items())),
    }


def _print_progress(record: dict[str, Any], total_chunks: int) -> None:
    rate = record["completed_cases"] / record["elapsed_seconds"] if record["elapsed_seconds"] else 0.0
    print(
        f"chunk={record['chunk_id'] + 1}/{total_chunks} "
        f"seed=0x{record['seed']:016X} status={record['status']} "
        f"cases={record['completed_cases']}/{record['cases']} "
        f"elapsed={record['elapsed_seconds']:.3f}s rate={rate:.2f} cases/s",
        flush=True,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        state_dir = _validate_args(args)
        state_path = state_dir / "campaign.json"
        state = _read_state(state_path, args)
    except CampaignConfigurationError as exc:
        print(f"rr-campaign: configuration error: {exc}", file=sys.stderr)
        return 2

    plans = _plans(args.target_cases, args.chunk_size, args.base_seed)
    plan_ids = {str(plan.chunk_id) for plan in plans}
    existing_completed = sum(
        record.get("cases", 0)
        for chunk_id, record in state["chunks"].items()
        if chunk_id in plan_ids and _is_completed(record)
    )
    if args.phase == "pilot" and existing_completed == 0 and args.target_cases < 20_000:
        print("rr-campaign: configuration error: initial pilot must target at least 20000 cases", file=sys.stderr)
        return 2
    if args.phase == "full" and state["campaign_launch_epoch"] is None:
        state["campaign_launch_epoch"] = time.time()
        state["campaign_launch_utc"] = _utc_now()
        state["events"].append(
            {"event": "full_campaign_launched", "utc": state["campaign_launch_utc"]}
        )
    deadline_epoch = None
    if state["campaign_launch_epoch"] is not None:
        deadline_epoch = state["campaign_launch_epoch"] + MAX_FULL_WALL_SECONDS

    resume_utc = _utc_now()
    for prior_run in state["runs"]:
        if prior_run.get("status") == "running":
            prior_run.update(
                {
                    "added_cases_durable": max(
                        0, existing_completed - prior_run.get("starting_completed_cases", 0)
                    ),
                    "finished_utc": resume_utc,
                    "status": "interrupted",
                    "stop_reason": "inferred_external_process_termination_before_resume",
                }
            )
            state["events"].append(
                {
                    "event": "inferred_interruption",
                    "run_id": prior_run.get("run_id"),
                    "utc": resume_utc,
                }
            )

    pending = [plan for plan in plans if not _is_completed(state["chunks"].get(str(plan.chunk_id), {}))]
    run_id = len(state["runs"])
    run_record: dict[str, Any] = {
        "run_id": run_id,
        "phase": args.phase,
        "started_utc": _utc_now(),
        "workers": args.workers,
        "target_cases": args.target_cases,
        "starting_completed_cases": existing_completed,
        "chunk_budget_seconds": args.chunk_budget_seconds,
        "case_timeout_seconds": args.case_timeout_seconds,
        "max_retries": args.max_retries,
        "runtime": _machine_record(),
        "retries": 0,
        "status": "running",
    }
    if existing_completed:
        state["events"].append(
            {
                "event": "resume",
                "run_id": run_id,
                "completed_cases_before_resume": existing_completed,
                "utc": run_record["started_utc"],
            }
        )
    state["runs"].append(run_record)
    _atomic_checkpoint(state_path, state)

    started = time.perf_counter()
    attempts: Counter[int] = Counter()
    pending_iter = iter(pending)
    futures: dict[concurrent.futures.Future[dict[str, Any]], ChunkPlan] = {}
    stop_reason: str | None = None
    interrupted = False

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=args.workers)

    def submit(plan: ChunkPlan) -> bool:
        nonlocal stop_reason
        if deadline_epoch is not None and time.time() >= deadline_epoch:
            stop_reason = "six_hour_campaign_cap_reached"
            return False
        attempts[plan.chunk_id] += 1
        future = executor.submit(
            _run_chunk,
            plan,
            attempt=attempts[plan.chunk_id],
            state_dir=state_dir,
            chunk_budget_seconds=args.chunk_budget_seconds,
            case_timeout_seconds=args.case_timeout_seconds,
            deadline_epoch=deadline_epoch,
        )
        futures[future] = plan
        return True

    try:
        for _ in range(args.workers):
            try:
                plan = next(pending_iter)
            except StopIteration:
                break
            if not submit(plan):
                break

        while futures:
            done, _ = concurrent.futures.wait(
                futures, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in done:
                plan = futures.pop(future)
                try:
                    record = future.result()
                except Exception as exc:  # noqa: BLE001 - worker failure is campaign evidence
                    record = {
                        "attempt": attempts[plan.chunk_id],
                        "cases": plan.cases,
                        "chunk_id": plan.chunk_id,
                        "classification": "campaign_wrapper_failure",
                        "completed_cases": 0,
                        "effective_budget_seconds": args.chunk_budget_seconds,
                        "elapsed_seconds": 0.0,
                        "errors": [f"worker raised {type(exc).__name__}: {exc}"],
                        "failure_corpus": None,
                        "identity_digest": "",
                        "oracle_returncode": None,
                        "runner_executions": None,
                        "seed": plan.seed,
                        "status": "harness_error",
                        "stderr_sha256": "",
                        "stderr_tail": "",
                        "stdout_sha256": "",
                        "stdout_tail": "",
                        "summary": None,
                    }
                _print_progress(record, len(plans))
                state["chunks"][str(plan.chunk_id)] = record
                if record["attempt"] > 1:
                    run_record["retries"] += 1
                _atomic_checkpoint(state_path, state)

                retryable = record["status"] in {"harness_error", "incomplete"}
                if retryable and attempts[plan.chunk_id] <= args.max_retries:
                    submit(plan)
                    continue
                if retryable:
                    stop_reason = (
                        "safety_or_harness_failure_after_retry_ceiling; not a runner finding"
                    )
                    continue
                if stop_reason is not None:
                    continue
                try:
                    next_plan = next(pending_iter)
                except StopIteration:
                    continue
                submit(next_plan)
    except KeyboardInterrupt:
        interrupted = True
        stop_reason = "operator_interruption"
        state["events"].append(
            {"event": "interruption", "run_id": run_id, "utc": _utc_now()}
        )
    finally:
        executor.shutdown(wait=not interrupted, cancel_futures=interrupted)

    elapsed = time.perf_counter() - started
    aggregate = _aggregate(state, plans)
    added_cases = aggregate["cases"] - existing_completed
    run_record.update(
        {
            "added_cases": added_cases,
            "elapsed_seconds": elapsed,
            "finished_utc": _utc_now(),
            "status": "interrupted" if interrupted else "finished",
            "stop_reason": stop_reason,
            "throughput_cases_per_second": added_cases / elapsed if elapsed else 0.0,
        }
    )
    _atomic_checkpoint(state_path, state)
    checkpoint_digest = _sha256(state_path.read_bytes())

    target_reached = aggregate["cases"] >= args.target_cases
    if target_reached and aggregate["candidate_breach_chunks"] == 0:
        verdict = "PASS"
    elif target_reached:
        verdict = "CANDIDATE BREACHES REQUIRE ADJUDICATION"
    else:
        verdict = "TARGET NOT REACHED"
    print(
        "rr-campaign: "
        f"verdict={verdict} cases={aggregate['cases']}/{args.target_cases} "
        f"runner_executions={aggregate['runner_executions']} "
        f"chunks={aggregate['chunk_count']}/{len(plans)} "
        f"breach_chunks={aggregate['candidate_breach_chunks']} "
        f"identity_root_sha256={aggregate['identity_root_sha256']} "
        f"checkpoint_sha256={checkpoint_digest}",
        flush=True,
    )
    print(
        "aggregate=" + json.dumps(aggregate, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        flush=True,
    )
    if verdict == "PASS":
        return 0
    if verdict == "TARGET NOT REACHED":
        return 3
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
