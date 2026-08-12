"""Small stdlib-only helpers shared by the WP5 evidence scripts."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import tempfile
import uuid
from collections import Counter
from typing import Any, Iterable


REPO = pathlib.Path(__file__).resolve().parents[2]
TRACE_EXEC = pathlib.Path(__file__).resolve().parent / "_trace_exec.py"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "ascii"
    )


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_label(path: pathlib.Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO).as_posix()
    except ValueError:
        return resolved.as_posix()


def source_pins(paths: Iterable[pathlib.Path]) -> dict[str, str]:
    pins: dict[str, str] = {}
    for path in paths:
        resolved = path.resolve()
        pins[repo_label(resolved)] = sha256(resolved.read_bytes())
    return dict(sorted(pins.items()))


def traced_python_command(target: pathlib.Path, *args: str) -> list[str]:
    """Return a fresh-source command sharing this execution's audit trace."""
    trace_dir_text = os.environ.get("RR_WP5_TRACE_DIR")
    if not trace_dir_text:
        raise RuntimeError("RR_WP5_TRACE_DIR is absent; evidence worker was not traced")
    trace_dir = pathlib.Path(trace_dir_text).resolve()
    cache = pathlib.Path(tempfile.mkdtemp(prefix="empty-pycache-", dir=trace_dir))
    if any(cache.iterdir()):
        raise RuntimeError("new pycache directory was not empty")
    return [
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
        str(target.resolve()),
        *args,
    ]


def reexec_traced_worker(script: pathlib.Path, marker: str = "--wp5-traced-worker") -> None:
    """Re-exec an evidence script before any repository imports occur."""
    if marker in sys.argv:
        sys.argv.remove(marker)
        return
    with tempfile.TemporaryDirectory(prefix="rr-wp5-trace-") as temporary:
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
            str(script.resolve()),
            marker,
            *sys.argv[1:],
        ]
        result = subprocess.run(command, cwd=pathlib.Path.cwd(), check=False)
        raise SystemExit(result.returncode)


def execution_input_manifest() -> tuple[dict[str, Any], dict[str, str]]:
    """Collect the complete repo-read trace and raw-pin every unique input."""
    trace_dir_text = os.environ.get("RR_WP5_TRACE_DIR")
    if not trace_dir_text:
        raise RuntimeError("RR_WP5_TRACE_DIR is absent")
    trace_dir = pathlib.Path(trace_dir_text).resolve()
    events: list[dict[str, Any]] = []
    for path in sorted(trace_dir.glob("opens-*.jsonl"), key=lambda item: item.name):
        raw = path.read_bytes()
        for line in raw.splitlines():
            row = json.loads(line.decode("ascii"))
            if not isinstance(row, dict) or not isinstance(row.get("path"), str):
                raise RuntimeError(f"malformed audit trace row in {path}")
            events.append(row)
    labels = sorted({row["path"] for row in events})
    paths = [REPO / pathlib.PurePosixPath(label) for label in labels]
    pins = source_pins(paths)
    # Pinning reopens exactly the already traced paths. A new label here means
    # collection was not closed over its own declared manifest.
    closed_labels: set[str] = set()
    for path in sorted(trace_dir.glob("opens-*.jsonl"), key=lambda item: item.name):
        for line in path.read_bytes().splitlines():
            closed_labels.add(json.loads(line.decode("ascii"))["path"])
    if closed_labels != set(labels) or set(pins) != set(labels):
        raise RuntimeError("audit trace and complete execution-input manifest differ")
    # Source pinning adds duplicate read events for the same closed set. Record
    # the final trace bytes only after that closure pass.
    final_events: list[dict[str, Any]] = []
    trace_files: list[dict[str, Any]] = []
    for path in sorted(trace_dir.glob("opens-*.jsonl"), key=lambda item: item.name):
        raw = path.read_bytes()
        trace_files.append({"name": path.name, "raw_sha256": sha256(raw), "bytes": len(raw)})
        final_events.extend(json.loads(line.decode("ascii")) for line in raw.splitlines())
    metas: list[dict[str, Any]] = []
    for path in sorted(trace_dir.glob("meta-*.json"), key=lambda item: item.name):
        value = json.loads(path.read_text(encoding="ascii"))
        metas.append(value)
    meta_root = hashlib.sha256()
    for value in metas:
        meta_root.update(canonical(value) + b"\n")
    trace_root = hashlib.sha256()
    for value in trace_files:
        trace_root.update(canonical(value) + b"\n")
    current_prefix = pathlib.Path(sys.pycache_prefix or "")
    current_empty = current_prefix.is_dir() and not any(current_prefix.rglob("*"))
    return (
        {
            "schema": "receiver-reliance/wp5-complete-execution-input-manifest-1",
            "complete": True,
            "audit_hook": "sys.addaudithook(open); repository regular-file reads only",
            "repo_open_events": len(final_events),
            "repo_paths": labels,
            "trace_files": {
                "count": len(trace_files),
                "identity_root_sha256": trace_root.hexdigest().upper(),
                "total_bytes": sum(value["bytes"] for value in trace_files),
            },
            "completed_child_processes": {
                "count": len(metas),
                "identity_root_sha256": meta_root.hexdigest().upper(),
                "target_counts": dict(sorted(Counter(value["target"] for value in metas).items())),
                "exit_code_counts": dict(
                    sorted(Counter(str(value.get("exit_code")) for value in metas).items())
                ),
                "all_dont_write_bytecode": all(value.get("dont_write_bytecode") is True for value in metas),
                "all_pycache_empty_at_start": all(value.get("pycache_empty_at_start") is True for value in metas),
                "all_pycache_empty_at_end": all(value.get("pycache_empty_at_end") is True for value in metas),
            },
            "current_process": {
                "pid": os.getpid(),
                "pycache_prefix": str(current_prefix),
                "pycache_empty_at_manifest": current_empty,
                "dont_write_bytecode": sys.dont_write_bytecode,
                "executed_argv": list(sys.orig_argv),
            },
            "pycache_policy": (
                "Every traced process uses -B and a unique, existing, empty temporary "
                "-X pycache_prefix, preventing repository .pyc reads and writes."
            ),
        },
        pins,
    )


def runtime_record() -> dict[str, Any]:
    return {
        "implementation": platform.python_implementation(),
        "version": platform.python_version(),
        "full_version": sys.version.replace("\n", " "),
        "executable": sys.executable,
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "perf_counter": vars(__import__("time").get_clock_info("perf_counter")),
    }


def _git(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git_record() -> dict[str, Any]:
    head = _git(["rev-parse", "HEAD"])
    status = _git(["status", "--porcelain=v1", "--untracked-files=all"])
    return {
        "head": head.stdout.decode("ascii", "replace").strip() if head.returncode == 0 else None,
        "head_query_exit_code": head.returncode,
        "clean": status.returncode == 0 and status.stdout == b"",
        "status_exit_code": status.returncode,
        "status_bytes": len(status.stdout),
        "status_sha256": sha256(status.stdout),
    }


def python_process_observation() -> dict[str, Any]:
    """Return one optional, platform-labelled process-name snapshot.

    This is intentionally not a process census.  The available native command,
    matching rules, permissions, and races differ by operating system.
    """
    system = platform.system()
    unavailable = {
        "platform": system,
        "available": False,
        "count": None,
        "probe": None,
        "scope": "optional platform-specific executable-name snapshot; not a universal process census",
    }
    try:
        if system == "Windows":
            command = ["tasklist", "/FO", "CSV", "/NH"]
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
            if result.returncode:
                return {**unavailable, "probe": {"argv": command, "exit_code": result.returncode}}
            rows = result.stdout.decode("utf-8", "replace").splitlines()
            count = sum(
                1
                for row in rows
                if row.lstrip().lower().startswith(('"python', '"pypy', '"graalpy'))
            )
            return {
                "platform": system,
                "available": True,
                "count": count,
                "probe": {"argv": command, "exit_code": 0},
                "scope": (
                    "Windows tasklist image-name prefix snapshot for python/pypy/graalpy; "
                    "racy and permission-dependent, not a universal process census"
                ),
            }
        if system not in {"Linux", "Darwin"}:
            return unavailable
        command = ["ps", "-eo", "comm="]
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
        if result.returncode:
            return {**unavailable, "probe": {"argv": command, "exit_code": result.returncode}}
        count = sum(
            pathlib.Path(line.strip()).name.lower().startswith(("python", "pypy", "graalpy"))
            for line in result.stdout.decode("utf-8", "replace").splitlines()
            if line.strip()
        )
        return {
            "platform": system,
            "available": True,
            "count": count,
            "probe": {"argv": command, "exit_code": 0},
            "scope": (
                f"{system} ps command-name prefix snapshot for python/pypy/graalpy; "
                "racy and permission-dependent, not a universal process census"
            ),
        }
    except (OSError, subprocess.SubprocessError):
        return unavailable


def write_new_receipt(path: pathlib.Path, receipt: dict[str, Any]) -> tuple[str, str]:
    """Write one immutable receipt and return (embedded digest, raw-file digest)."""
    resolved = path.resolve()
    try:
        resolved.relative_to((REPO / "perf" / "receipts" / "robustness").resolve())
    except ValueError as error:
        raise ValueError("receipt must stay under perf/receipts/robustness") from error
    if resolved.exists():
        raise FileExistsError(f"refusing to overwrite receipt: {resolved}")
    if "receipt_sha256" in receipt:
        raise ValueError("receipt_sha256 is reserved")
    embedded = sha256(canonical(receipt))
    complete = dict(receipt)
    complete["receipt_sha256"] = embedded
    payload = canonical(complete) + b"\n"
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return embedded, sha256(payload)
