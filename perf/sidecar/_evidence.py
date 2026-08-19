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
PORTABILITY = REPO / "portability"
if str(PORTABILITY) not in sys.path:
    sys.path.insert(0, str(PORTABILITY))

# ADOPTION A5 and ERRATA E15.  Two shared controls this file needs -- pinned
# tool resolution and home-directory redaction -- live under ``portability/``,
# and this file is a declared RUNTIME member of the ``portable/`` offline bundle
# whose file set is ``portable/inventory.json``.  Importing them at module scope
# would make the bundle's own gate (which imports this module for ``canonical``
# and ``sha256``) depend on two files the bundle does not declare, so the
# imports are made where they are used.  Neither call site runs inside the
# bundle: nothing there resolves ``git`` or writes a receipt.  The alternative
# -- declaring both modules in the inventory -- would move the manifest, its
# published file count and every count pinned to it for two functions the
# bundle never reaches.


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


def _trace_rows(trace_dir: pathlib.Path) -> list[dict[str, Any]]:
    """Every audit-trace row, in file-name then file order."""
    rows: list[dict[str, Any]] = []
    for path in sorted(trace_dir.glob("opens-*.jsonl"), key=lambda item: item.name):
        for line in path.read_bytes().splitlines():
            row = json.loads(line.decode("ascii"))
            if not isinstance(row, dict) or not isinstance(row.get("path"), str):
                raise RuntimeError(f"malformed audit trace row in {path}")
            rows.append(row)
    return rows


def _read_time_pins(rows: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Collapse the read-time digests to one pin per input, or fail.

    F-WP5-006 bound 5.  Every recorded read carries the digest of the bytes it
    opened, so this is where a mid-run mutation stops being invisible: two reads
    of one path that disagree cannot be collapsed, and the run does not get to
    claim either digest was "the" execution input.  Before this, the manifest
    reopened each path once after the run and pinned whatever it found.
    """
    observed: dict[str, dict[str, int]] = {}
    for row in rows:
        label = row["path"]
        digest = row.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise RuntimeError(
                "an execution input was recorded without a read-time pin: "
                f"{label} (event {row.get('index')!r}, pid {row.get('pid')!r})"
            )
        observed.setdefault(label, {})
        observed[label][digest] = observed[label].get(digest, 0) + 1
    conflicts = {label: counts for label, counts in observed.items() if len(counts) > 1}
    if conflicts:
        raise RuntimeError(
            "an execution input changed between reads, so no single digest "
            f"describes what was executed: {conflicts!r}"
        )
    return {label: next(iter(counts)) for label, counts in sorted(observed.items())}


def execution_input_manifest() -> tuple[dict[str, Any], dict[str, str]]:
    """Collect the complete repo-read trace and pin every input at each read."""
    # ADOPTION A5 and ERRATA E15.  The two shared modules this file imports
    # lazily -- pinned_tools for git resolution, receipt_paths for redaction --
    # are loaded HERE, before collection, and not left to load at their call
    # sites further down the run.  Both are repository files; importing them
    # afterwards would read two inputs behind the back of a manifest that calls
    # itself complete, which is precisely the defect F-WP5-001 built this
    # machinery to end.  Loading them first makes their bytes ordinary traced
    # inputs, pinned at their read like every other.  Measured, not assumed: a
    # probe run before this line existed produced a receipt whose manifest
    # declared 21 inputs and omitted both.
    import pinned_tools  # noqa: F401
    import receipt_paths  # noqa: F401

    trace_dir_text = os.environ.get("RR_WP5_TRACE_DIR")
    if not trace_dir_text:
        raise RuntimeError("RR_WP5_TRACE_DIR is absent")
    trace_dir = pathlib.Path(trace_dir_text).resolve()
    events = _trace_rows(trace_dir)
    labels = sorted({row["path"] for row in events})
    pins = _read_time_pins(events)
    paths = [REPO / pathlib.PurePosixPath(label) for label in labels]
    # Reopening at manifest time is now a CHECK, not the pin.  A file that moved
    # after its last read still fails here, and a file that moved between two
    # reads already failed above; the receipt therefore records the bytes the
    # run executed rather than the bytes that survived it.
    manifest_time = source_pins(paths)
    drifted = {
        label: (pins[label], manifest_time[label])
        for label in labels
        if manifest_time.get(label) != pins.get(label)
    }
    if drifted:
        raise RuntimeError(
            "an execution input changed after its last read, so the manifest "
            f"cannot describe the run: {drifted!r}"
        )
    # Pinning reopens exactly the already traced paths. A new label here means
    # collection was not closed over its own declared manifest.
    closed_rows = _trace_rows(trace_dir)
    closed_labels = {row["path"] for row in closed_rows}
    if closed_labels != set(labels) or set(pins) != set(labels):
        raise RuntimeError("audit trace and complete execution-input manifest differ")
    # The closure pass added one further read per input.  Those reads carry
    # read-time pins too, so re-collapsing over the complete row set proves the
    # agreement held across every read the run performed, not only the ones
    # recorded before the manifest started.
    if _read_time_pins(closed_rows) != pins:
        raise RuntimeError("read-time input pins disagree across the closed trace")
    # Source pinning adds duplicate read events for the same closed set. Record
    # the final trace bytes only after that closure pass.
    final_events: list[dict[str, Any]] = []
    trace_files: list[dict[str, Any]] = []
    for path in sorted(trace_dir.glob("opens-*.jsonl"), key=lambda item: item.name):
        raw = path.read_bytes()
        trace_files.append({"name": path.name, "raw_sha256": sha256(raw), "bytes": len(raw)})
        final_events.extend(json.loads(line.decode("ascii")) for line in raw.splitlines())
    read_pinned_events = sum(
        1 for row in final_events if isinstance(row.get("sha256"), str)
    )
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
            "schema": "receiver-reliance/wp5-complete-execution-input-manifest-2",
            "complete": True,
            "audit_hook": "sys.addaudithook(open); repository regular-file reads only",
            "input_pin_time": "read",
            "input_pin_rule": (
                "Every recorded read carries the SHA-256 of the bytes it opened. "
                "Reads of one path that disagree, or a path whose bytes moved "
                "between its last read and this manifest, fail collection instead "
                "of being pinned at post-run content."
            ),
            "repo_open_events": len(final_events),
            "read_pinned_events": read_pinned_events,
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
                "all_read_time_pinned": all(
                    value.get("input_pin_time") == "read" for value in metas
                ),
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
    # ADOPTION A5, the last unmigrated harness.  This function writes the
    # head/clean/status_sha256 provenance block into both admitted WP5 receipts,
    # so the program answering "which commit is this, and is it clean?" must not
    # be whichever `git` the ambient PATH resolves first -- a verification lane
    # demonstrated a forged `git` moving a receipt gate from FAIL to PASS
    # (TRUST_MODEL.md).  With RR_TOOL_DIR unset the argv is byte-identical to
    # the bare name this used to build; with it set, `git` resolves inside an
    # administrator-write-only directory and never falls back to PATH.
    import pinned_tools

    return subprocess.run(
        [pinned_tools.git(), *args],
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
    # ERRATA E15.  The WP5 receipts recorded `runtime.executable`, the real
    # `command` argv, `execution_input_manifest.current_process.executed_argv`,
    # the temporary pycache root and every cProfile function label verbatim, so
    # a run from a home-directory checkout published the maintainer's account
    # name for no evidentiary purpose.  This is the one boundary every WP5
    # receipt passes through, and it is applied to the whole tree rather than to
    # an enumerated field list -- the cProfile labels are exactly the field an
    # enumerated list would have missed.  The redaction rewrites what is
    # RECORDED; every path this function reads was already read above it.
    import receipt_paths

    receipt = receipt_paths.redact_tree(receipt)
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
