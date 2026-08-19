#!/usr/bin/env python3
"""Negative-armed proofs for the four supervision bounds F-WP5-006 disclosed.

    python -B perf/sidecar/test_supervision_bounds.py

One case per bound is not enough for any of these, because every one of them is
a claim that something now happens which did not happen before.  A case that
only shows the good outcome cannot tell "the guard fired" from "the situation
never arose", so each bound here carries an arm that fails without the repair:

* the write deadline fires on a child that never reads, and does NOT fire when
  the same child accepts a request that fits the pipe buffer;
* a grandchild dies with the supervised tree, and demonstrably survives the
  ``Popen.kill()`` that supervision used to do instead;
* stderr produced after interaction N's response was admitted is charged to N,
  and stderr produced during N is charged to N as in-flight, so the retroactive
  flag distinguishes two situations rather than being decoration;
* an execution input whose read-time bytes disagree with its manifest-time bytes
  stops collection, as do two reads that disagree and a read with no pin at all.

Timing is synchronised through files and observable supervisor state, never
through a sleep long enough to "probably" be sufficient.  The one place a bound
wait exists it waits for a condition and fails on the deadline, so a slow host
is slow rather than green by luck.
"""
from __future__ import annotations

import sys

if "--trace-child" in sys.argv:
    # Executed under perf/sidecar/_trace_exec.py by the bound-5 end-to-end arm.
    # It runs before every other import in this file so the trace it produces is
    # the smallest one that still proves the audit hook pins at the read.
    import pathlib as _pathlib

    _target = _pathlib.Path(sys.argv[sys.argv.index("--trace-child") + 1])
    _target.read_bytes()
    raise SystemExit(0)

import json
import os
import pathlib
import subprocess
import tempfile
import time
import uuid
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _evidence  # noqa: E402
from supervised_client import (  # noqa: E402
    ContainmentError,
    ProcessTree,
    SidecarFailure,
    SidecarProcess,
)

WINDOWS = sys.platform == "win32"
POLL_SECONDS = 0.005
CONDITION_TIMEOUT_SECONDS = 30.0
SLEEPER = "import time; time.sleep(600)"


def _alive(pid: int) -> bool:
    """Whether a process id still names a running process.

    Windows keeps a process object alive while any handle to it is open, so
    ``OpenProcess`` succeeding is not liveness; the exit code is.  POSIX uses
    the standard zero-signal probe.
    """
    if not WINDOWS:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    import ctypes
    import ctypes.wintypes as wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _await(condition, description: str, timeout: float = CONDITION_TIMEOUT_SECONDS) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(POLL_SECONDS)
    return False


def _spawner_source(pid_file: pathlib.Path) -> str:
    """A child that spawns one grandchild, publishes its pid, then goes deaf."""
    return (
        "import pathlib, subprocess, sys, time\n"
        f"grandchild = subprocess.Popen([sys.executable, '-I', '-B', '-c', {SLEEPER!r}])\n"
        f"pathlib.Path({str(pid_file)!r}).write_text(str(grandchild.pid), encoding='ascii')\n"
        "time.sleep(600)\n"
    )


def _peer_source(tail: str) -> str:
    """A minimal but real transport peer, so stderr timing is the only variable."""
    return (
        "import os, pathlib, sys, time\n"
        f"sys.path.insert(0, {str(HERE)!r})\n"
        "from transport_envelope import (\n"
        "    encode_response_frame, read_exact, read_request_header, write_all)\n"
        "def serve_one():\n"
        "    header = read_request_header(sys.stdin.buffer)\n"
        "    payload, digest = read_exact(sys.stdin.buffer, header.payload_bytes)\n"
        "    frame = encode_response_frame(header.sequence, digest, b'OK\\n')\n"
        "    write_all(sys.stdout.buffer, frame)\n"
        "    sys.stdout.buffer.flush()\n"
        "    return header.sequence\n"
        + tail
    )


def main() -> int:
    checks = 0
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(f"{name}: {detail}" if detail else name)

    with tempfile.TemporaryDirectory(prefix="rr-supervision-") as workspace:
        work = pathlib.Path(workspace)
        _write_phase_deadline(check, work)
        _process_tree_containment(check, work)
        _retroactive_stderr(check, work)
        _read_time_input_pinning(check, work)

    for failure in failures:
        print(f"FAIL {failure}")
    print(f"supervision bounds: checks={checks} failures={len(failures)}")
    return 0 if not failures else 1


# ---------------------------------------------------------------------------
# Bound 1 -- the deadline covers the write phase.
# ---------------------------------------------------------------------------


def _write_phase_deadline(check, work: pathlib.Path) -> None:
    # A child that never reads.  The request is far larger than any pipe buffer,
    # so the write cannot complete and the old code blocked in it indefinitely:
    # timeout_seconds bounded the wait for a response, which this call never
    # reaches.
    oversized = b"x" * (4 * 1024 * 1024) + b"\n"
    client = SidecarProcess(
        [sys.executable, "-I", "-B", "-c", SLEEPER],
        timeout_seconds=2.0,
    )
    started = time.monotonic()
    try:
        client.start()
        try:
            client.request(oversized)
            check("bound1:blocking-write-is-refused", False, "request returned a payload")
        except SidecarFailure as error:
            message = str(error)
            check(
                "bound1:blocking-write-is-refused",
                "write did not complete within the deadline" in message,
                message,
            )
        elapsed = time.monotonic() - started
        check("bound1:bounded-by-the-deadline", elapsed < 25.0, f"elapsed={elapsed:.3f}s")
        check("bound1:deadline-counted", client.write_deadline_count == 1, repr(client.write_deadline_count))
        check(
            "bound1:no-write-was-completed",
            client.request_write_count == 0 and client.response_count == 0,
            repr(client.state_evidence()),
        )
        check(
            "bound1:no-automatic-replay",
            client.automatic_replay_count == 0 and client.request_attempt_count == 1,
            repr(client.state_evidence()),
        )
        check(
            "bound1:child-stopped",
            _await(lambda: client.returncode is not None, "child exit"),
            repr(client.returncode),
        )
    finally:
        client.stop(check=False)

    # Negative arm.  The same deaf child, a request that fits the pipe buffer.
    # The write completes, so the write deadline must NOT fire and the failure
    # must be the await-phase timeout that already existed.  Without this arm a
    # write watchdog that fired on every request would look identical above.
    small = SidecarProcess(
        [sys.executable, "-I", "-B", "-c", SLEEPER],
        timeout_seconds=2.0,
    )
    try:
        small.start()
        try:
            small.request(b'{"probe":"small"}\n')
            check("bound1:small-request-still-times-out", False, "request returned a payload")
        except SidecarFailure as error:
            message = str(error)
            check(
                "bound1:small-request-still-times-out",
                "sidecar response timed out" in message,
                message,
            )
        check(
            "bound1:write-deadline-did-not-fire",
            small.write_deadline_count == 0 and small.request_write_count == 1,
            repr(small.state_evidence()),
        )
    finally:
        small.stop(check=False)


# ---------------------------------------------------------------------------
# Bound 2 -- cleanup contains the process tree, not just the direct child.
# ---------------------------------------------------------------------------


def _process_tree_containment(check, work: pathlib.Path) -> None:
    pid_file = work / "supervised-grandchild.pid"
    client = SidecarProcess(
        [sys.executable, "-I", "-B", "-c", _spawner_source(pid_file)],
        timeout_seconds=2.0,
    )
    grandchild: int | None = None
    try:
        client.start()
        check(
            "bound2:containment-is-real",
            client.containment == ("windows-job-object" if WINDOWS else "posix-process-group"),
            client.containment,
        )
        check(
            "bound2:grandchild-published",
            _await(lambda: pid_file.is_file() and pid_file.read_bytes().strip() != b"", "pid file"),
            "the spawner never published a grandchild pid",
        )
        if pid_file.is_file() and pid_file.read_bytes().strip():
            grandchild = int(pid_file.read_text(encoding="ascii").strip())
        check("bound2:grandchild-running", grandchild is not None and _alive(grandchild), repr(grandchild))
        # Any real supervision failure reaches the same cleanup path; the
        # await-phase timeout is the cheapest one to provoke deterministically.
        try:
            client.request(b'{"probe":"tree"}\n')
            check("bound2:interaction-failed", False, "request returned a payload")
        except SidecarFailure as error:
            check("bound2:interaction-failed", "timed out" in str(error), str(error))
        check(
            "bound2:grandchild-terminated",
            grandchild is not None and _await(lambda: not _alive(grandchild), "grandchild exit"),
            f"grandchild {grandchild} survived supervised cleanup",
        )
    finally:
        client.stop(check=False)
        if grandchild is not None and _alive(grandchild):
            _force_kill(grandchild)

    # Negative arm.  Exactly what supervision used to do -- terminate the direct
    # child -- against exactly the same tree.  The grandchild survives, which is
    # the defect F-WP5-006 bound 2 named and the proof that the case above is
    # measuring the job object rather than an accident of process lifetime.
    uncontained_pid_file = work / "uncontained-grandchild.pid"
    raw = subprocess.Popen(
        [sys.executable, "-I", "-B", "-c", _spawner_source(uncontained_pid_file)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    orphan: int | None = None
    try:
        check(
            "bound2:uncontained-grandchild-published",
            _await(
                lambda: uncontained_pid_file.is_file()
                and uncontained_pid_file.read_bytes().strip() != b"",
                "pid file",
            ),
            "the uncontained spawner never published a grandchild pid",
        )
        if uncontained_pid_file.is_file() and uncontained_pid_file.read_bytes().strip():
            orphan = int(uncontained_pid_file.read_text(encoding="ascii").strip())
        raw.kill()
        raw.wait(timeout=10)
        check("bound2:uncontained-parent-stopped", raw.poll() is not None, repr(raw.poll()))
        check(
            "bound2:uncontained-grandchild-survives",
            orphan is not None and _alive(orphan),
            f"grandchild {orphan} did not survive a direct-child kill, so this "
            "arm no longer discriminates",
        )
    finally:
        if orphan is not None and _alive(orphan):
            _force_kill(orphan)

    # Fail-closed arm: an unbindable child is an error, never an uncontained
    # child.  A pid that cannot be opened stands in for every reason assignment
    # can fail on a host this suite cannot arrange.
    tree = ProcessTree()
    tree.popen_kwargs()
    try:
        class _Absent:
            pid = 0x7FFFFFFF

        tree.adopt(_Absent())
        check("bound2:unbindable-child-is-fatal", False, "adopt() accepted an unreachable pid")
    except ContainmentError as error:
        check("bound2:unbindable-child-is-fatal", isinstance(error, SidecarFailure), str(error))
    except OSError as error:
        check("bound2:unbindable-child-is-fatal", False, f"raised a bare OSError: {error}")
    finally:
        tree.close()


def _force_kill(pid: int) -> None:
    if WINDOWS:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        os.kill(pid, 9)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Bound 3 -- stderr is adjudicated against the interaction it belongs to.
# ---------------------------------------------------------------------------


def _retroactive_stderr(check, work: pathlib.Path) -> None:
    go = work / "late-stderr.go"
    marker = work / "late-stderr.written"
    tail = (
        "serve_one()\n"
        f"go = pathlib.Path({str(go)!r})\n"
        "deadline = time.monotonic() + 60\n"
        "while not go.exists() and time.monotonic() < deadline:\n"
        "    time.sleep(0.005)\n"
        "os.write(2, b'LATE')\n"
        f"pathlib.Path({str(marker)!r}).write_bytes(b'1')\n"
        "time.sleep(60)\n"
    )
    client = SidecarProcess(
        [sys.executable, "-I", "-B", "-c", _peer_source(tail)],
        timeout_seconds=20.0,
    )
    try:
        client.start()
        payload = client.request(b'{"probe":"one"}\n')
        check("bound3:first-interaction-admitted", payload == b"OK\n", repr(payload))
        # The child writes stderr only after this file appears, so the bytes are
        # provably later than the admission of interaction 1 rather than racing
        # it.  Without the handshake this case would sometimes exercise the
        # in-flight path and pass for the wrong reason.
        go.write_bytes(b"1")
        check(
            "bound3:late-stderr-observed",
            _await(
                lambda: client.state_evidence()["protocol_failure"] is not None,
                "stderr poison",
            ),
            repr(client.state_evidence()),
        )
        adjudications = client.stderr_adjudications()
        check(
            "bound3:one-retroactive-adjudication",
            len(adjudications) == 1
            and adjudications[0]["sequence"] == 1
            and adjudications[0]["retroactive"] is True
            and adjudications[0]["phase"] == "IDLE",
            repr(adjudications),
        )
        check(
            "bound3:adjudication-in-state-evidence",
            client.state_evidence()["stderr_adjudications"] == adjudications,
            repr(client.state_evidence()["stderr_adjudications"]),
        )
        try:
            client.request(b'{"probe":"two"}\n')
            check("bound3:next-interaction-refused", False, "request returned a payload")
        except SidecarFailure as error:
            message = str(error)
            check(
                "bound3:next-interaction-refused",
                "attributable to interaction 1" in message,
                message,
            )
            check(
                "bound3:not-charged-to-the-next-interaction",
                "interaction 2" not in message,
                message,
            )
    finally:
        client.stop(check=False)

    # Negative arm: stderr produced while the interaction is in flight is
    # charged to it as in-flight.  If ``retroactive`` were always true, or the
    # sequence always the last admitted one, this case fails.
    inflight = SidecarProcess(
        [sys.executable, "-I", "-B", "-c", _peer_source(
            "header = read_request_header(sys.stdin.buffer)\n"
            "payload, digest = read_exact(sys.stdin.buffer, header.payload_bytes)\n"
            "os.write(2, b'EARLY')\n"
            "time.sleep(60)\n"
        )],
        timeout_seconds=20.0,
    )
    try:
        inflight.start()
        try:
            inflight.request(b'{"probe":"inflight"}\n')
            check("bound3:in-flight-stderr-fails-its-own-interaction", False, "request returned a payload")
        except SidecarFailure as error:
            message = str(error)
            check(
                "bound3:in-flight-stderr-fails-its-own-interaction",
                "during interaction 1" in message,
                message,
            )
        adjudications = inflight.stderr_adjudications()
        check(
            "bound3:in-flight-adjudication-is-not-retroactive",
            len(adjudications) == 1
            and adjudications[0]["sequence"] == 1
            and adjudications[0]["retroactive"] is False,
            repr(adjudications),
        )
    finally:
        inflight.stop(check=False)


# ---------------------------------------------------------------------------
# Bound 5 -- execution-input receipts pin file bytes at each read.
# ---------------------------------------------------------------------------


def _trace_row(label: str, index: int, digest: str, length: int) -> dict[str, Any]:
    return {
        "event": "open",
        "index": index,
        "path": label,
        "pid": os.getpid(),
        "sha256": digest,
        "bytes": length,
    }


def _write_trace(directory: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    payload = b"".join(_evidence.canonical(row) + b"\n" for row in rows)
    (directory / "opens-0123456789abcdef.jsonl").write_bytes(payload)
    (directory / "meta-0123456789abcdef.json").write_bytes(
        _evidence.canonical(
            {
                "schema": "receiver-reliance/wp5-audit-trace-process-2",
                "target": "perf/sidecar/test_supervision_bounds.py",
                "input_pin_time": "read",
                "exit_code": 0,
                "dont_write_bytecode": True,
                "pycache_empty_at_start": True,
                "pycache_empty_at_end": True,
            }
        )
        + b"\n"
    )


def _collect(directory: pathlib.Path):
    saved = os.environ.get("RR_WP5_TRACE_DIR")
    os.environ["RR_WP5_TRACE_DIR"] = str(directory)
    try:
        return _evidence.execution_input_manifest()
    finally:
        if saved is None:
            os.environ.pop("RR_WP5_TRACE_DIR", None)
        else:
            os.environ["RR_WP5_TRACE_DIR"] = saved


def _read_time_input_pinning(check, work: pathlib.Path) -> None:
    label = "perf/sidecar/rr_sidecar.py"
    raw = (REPO / label).read_bytes()
    digest = _evidence.sha256(raw)

    # Agreeing reads collapse to one pin and declare where the pin came from.
    agree = work / "trace-agree"
    agree.mkdir()
    _write_trace(agree, [_trace_row(label, 0, digest, len(raw)), _trace_row(label, 1, digest, len(raw))])
    manifest, pins = _collect(agree)
    check(
        "bound5:schema-declares-read-time-pinning",
        manifest["schema"] == "receiver-reliance/wp5-complete-execution-input-manifest-2"
        and manifest["input_pin_time"] == "read",
        repr((manifest["schema"], manifest.get("input_pin_time"))),
    )
    check("bound5:pin-is-the-read-time-digest", pins == {label: digest}, repr(pins))
    check(
        "bound5:every-event-carries-a-pin",
        manifest["read_pinned_events"] == manifest["repo_open_events"],
        repr((manifest["read_pinned_events"], manifest["repo_open_events"])),
    )

    # A read whose bytes disagree with the bytes present at manifest time is
    # exactly the mid-run mutation the disclosed bound said was invisible.
    drifted = work / "trace-drifted"
    drifted.mkdir()
    stale = "0" * 63 + "1"
    _write_trace(drifted, [_trace_row(label, 0, stale, len(raw))])
    try:
        _collect(drifted)
        check("bound5:mutation-after-the-read-is-detected", False, "collection accepted a stale pin")
    except RuntimeError as error:
        check(
            "bound5:mutation-after-the-read-is-detected",
            "changed after its last read" in str(error),
            str(error),
        )

    # Two reads that disagree cannot be collapsed into one pin at all.
    conflicting = work / "trace-conflicting"
    conflicting.mkdir()
    _write_trace(
        conflicting,
        [_trace_row(label, 0, digest, len(raw)), _trace_row(label, 1, stale, len(raw))],
    )
    try:
        _collect(conflicting)
        check("bound5:disagreeing-reads-are-detected", False, "collection collapsed two digests")
    except RuntimeError as error:
        check(
            "bound5:disagreeing-reads-are-detected",
            "changed between reads" in str(error),
            str(error),
        )

    # An unpinned read fails closed rather than shrinking a complete manifest.
    unpinned = work / "trace-unpinned"
    unpinned.mkdir()
    row = _trace_row(label, 0, digest, len(raw))
    row["sha256"] = None
    _write_trace(unpinned, [row])
    try:
        _collect(unpinned)
        check("bound5:unpinned-read-fails-closed", False, "collection accepted a null pin")
    except RuntimeError as error:
        check(
            "bound5:unpinned-read-fails-closed",
            "without a read-time pin" in str(error),
            str(error),
        )

    _trace_exec_end_to_end(check, work)


def _trace_exec_end_to_end(check, work: pathlib.Path) -> None:
    """The writer side: _trace_exec.py really pins at the read, not afterwards."""
    trace_dir = work / "trace-exec"
    trace_dir.mkdir()
    cache = trace_dir / "empty-pycache-root"
    cache.mkdir()
    read_label = "perf/sidecar/rr_sidecar.py"
    read_path = REPO / read_label
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-X",
            f"pycache_prefix={cache}",
            str(HERE / "_trace_exec.py"),
            "--trace-dir",
            str(trace_dir),
            "--trace-id",
            uuid.uuid4().hex,
            str(pathlib.Path(__file__).resolve()),
            "--trace-child",
            str(read_path),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=120,
    )
    check(
        "bound5:traced-child-succeeded",
        completed.returncode == 0,
        f"exit={completed.returncode} stderr={completed.stderr[:400]!r}",
    )
    rows: list[dict[str, Any]] = []
    for path in sorted(trace_dir.glob("opens-*.jsonl")):
        rows.extend(json.loads(line.decode("ascii")) for line in path.read_bytes().splitlines())
    metas = [
        json.loads(path.read_text(encoding="ascii"))
        for path in sorted(trace_dir.glob("meta-*.json"))
    ]
    check("bound5:trace-produced-rows", bool(rows) and len(metas) == 1, f"rows={len(rows)} metas={len(metas)}")
    if not rows or len(metas) != 1:
        return
    check(
        "bound5:meta-declares-read-time-pinning",
        metas[0]["schema"] == "receiver-reliance/wp5-audit-trace-process-2"
        and metas[0]["input_pin_time"] == "read"
        and metas[0]["event_count"] == len(rows),
        repr({key: metas[0].get(key) for key in ("schema", "input_pin_time", "event_count")}),
    )
    mismatched = [
        row["path"]
        for row in rows
        if row.get("sha256") != _evidence.sha256((REPO / row["path"]).read_bytes())
        or row.get("bytes") != (REPO / row["path"]).stat().st_size
    ]
    check("bound5:every-row-pins-the-real-bytes", mismatched == [], repr(sorted(set(mismatched))))
    check(
        "bound5:the-read-was-recorded",
        any(row["path"] == read_label for row in rows),
        repr(sorted({row["path"] for row in rows})),
    )
    # The pinning read is itself an open.  Exactly one row for a file opened
    # exactly once proves the audit hook does not record its own hashing read --
    # the reentrance that would otherwise recurse without bound.
    check(
        "bound5:pinning-read-is-not-itself-recorded",
        sum(1 for row in rows if row["path"] == read_label) == 1,
        repr([row for row in rows if row["path"] == read_label]),
    )


if __name__ == "__main__":
    raise SystemExit(main())
