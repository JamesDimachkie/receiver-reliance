"""Stdlib supervisor for the request-bound anonymous-stdio sidecar.

Response identity comes only from the versioned transport envelope: the exact
monotonic sequence, SHA-256 of the complete request bytes, and SHA-256 of the
complete response payload must all validate after the host's full frame write
and flush have returned.  Phase and queue timing are fail-closed lifecycle
checks; neither can establish response identity.

Three supervision bounds F-WP5-006 disclosed as unrepaired are repaired here.
Each is marked at its site:

* the deadline now covers the write phase, not only the await phase, so a child
  that never reads cannot hold the writer in a blocking write;
* cleanup terminates the whole process tree, not only the direct child, so a
  grandchild cannot outlive the supervisor; and
* stderr is adjudicated against the interaction it belongs to, so evidence
  produced by interaction N is never reported as a defect of interaction N+1.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import queue
import signal
import subprocess
import sys
import threading
import time
from typing import Sequence


HERE = pathlib.Path(__file__).resolve().parent
LAUNCHER = HERE / "rr_sidecar.py"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from transport_envelope import (  # noqa: E402
    EnvelopeError,
    ResponseFrame,
    encode_request_frame,
    read_response_frame,
    sha256,
    write_all,
)


DEFAULT_MAX_RESPONSE_BYTES = 32 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_STDERR_RETAINED_BYTES = 1024 * 1024


class SidecarFailure(RuntimeError):
    """The child failed, stalled, or violated the transport envelope."""


class ContainmentError(SidecarFailure):
    """The child could not be bound to a killable process tree."""


# ---------------------------------------------------------------------------
# F-WP5-006 bound 2: process-tree containment.
#
# Failure cleanup used to be ``Popen.terminate()`` followed by ``Popen.kill()``.
# Both act on the direct child only, so a child that had spawned a grandchild
# left that grandchild running -- holding the inherited pipe ends and outliving
# the supervisor that was supposed to have stopped it.  The disclosed bound said
# "no job object / process group".  This is the job object and the process group.
#
# Windows is the host these receipts are produced on, so the Windows arm is the
# real one and ``test_supervision_bounds.py`` exercises it against an actual
# grandchild.  The child is created SUSPENDED, assigned to a job object carrying
# JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, and only then resumed, so there is no
# interval in which the child runs unassigned.  Creating first and assigning
# second would leave that interval open, and an interval too short to observe is
# still an interval.
#
# Resuming needs the child's initial thread, which ``subprocess.Popen`` closes
# before returning.  It is recovered from a Toolhelp thread snapshot; a
# suspended process has exactly one thread, so the lookup is unambiguous.
#
# POSIX gets ``start_new_session=True`` -- the child becomes a session and
# process-group leader -- and cleanup signals the whole group with ``killpg``.
#
# Containment failure is fatal by design.  A supervisor that reports containment
# it does not have is the control-outside-the-decision-path shape this
# repository already names twice, so an unassignable child is killed and the
# failure raised, never downgraded to an uncontained child.
# ---------------------------------------------------------------------------

_WINDOWS = sys.platform == "win32"

if _WINDOWS:  # pragma: no cover - platform-selected
    import ctypes
    import ctypes.wintypes as _wintypes

    _JobObjectExtendedLimitInformation = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _CREATE_SUSPENDED = 0x00000004
    _TH32CS_SNAPTHREAD = 0x00000004
    _THREAD_SUSPEND_RESUME = 0x0002
    _PROCESS_TERMINATE_AND_SET_QUOTA = 0x0001 | 0x0100
    _RESUME_THREAD_FAILED = 0xFFFFFFFF

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", _wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", _wintypes.DWORD),
            ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
            ("PriorityClass", _wintypes.DWORD),
            ("SchedulingClass", _wintypes.DWORD),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _THREADENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", _wintypes.DWORD),
            ("cntUsage", _wintypes.DWORD),
            ("th32ThreadID", _wintypes.DWORD),
            ("th32OwnerProcessID", _wintypes.DWORD),
            ("tpBasePri", ctypes.c_long),
            ("tpDeltaPri", ctypes.c_long),
            ("dwFlags", _wintypes.DWORD),
        ]

    def _kernel32():
        """kernel32 with every signature declared, so no handle is truncated."""
        library = ctypes.WinDLL("kernel32", use_last_error=True)
        library.CreateJobObjectW.restype = _wintypes.HANDLE
        library.CreateJobObjectW.argtypes = [ctypes.c_void_p, _wintypes.LPCWSTR]
        library.SetInformationJobObject.restype = _wintypes.BOOL
        library.SetInformationJobObject.argtypes = [
            _wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            _wintypes.DWORD,
        ]
        library.AssignProcessToJobObject.restype = _wintypes.BOOL
        library.AssignProcessToJobObject.argtypes = [_wintypes.HANDLE, _wintypes.HANDLE]
        library.TerminateJobObject.restype = _wintypes.BOOL
        library.TerminateJobObject.argtypes = [_wintypes.HANDLE, _wintypes.UINT]
        library.OpenProcess.restype = _wintypes.HANDLE
        library.OpenProcess.argtypes = [_wintypes.DWORD, _wintypes.BOOL, _wintypes.DWORD]
        library.OpenThread.restype = _wintypes.HANDLE
        library.OpenThread.argtypes = [_wintypes.DWORD, _wintypes.BOOL, _wintypes.DWORD]
        library.ResumeThread.restype = _wintypes.DWORD
        library.ResumeThread.argtypes = [_wintypes.HANDLE]
        library.CreateToolhelp32Snapshot.restype = _wintypes.HANDLE
        library.CreateToolhelp32Snapshot.argtypes = [_wintypes.DWORD, _wintypes.DWORD]
        library.Thread32First.restype = _wintypes.BOOL
        library.Thread32First.argtypes = [
            _wintypes.HANDLE,
            ctypes.POINTER(_THREADENTRY32),
        ]
        library.Thread32Next.restype = _wintypes.BOOL
        library.Thread32Next.argtypes = [
            _wintypes.HANDLE,
            ctypes.POINTER(_THREADENTRY32),
        ]
        library.CloseHandle.restype = _wintypes.BOOL
        library.CloseHandle.argtypes = [_wintypes.HANDLE]
        return library


class ProcessTree:
    """One child and every descendant it spawns, as a single killable unit."""

    def __init__(self) -> None:
        self.kind = "none"
        self._job = None
        self._library = None
        self._pgid: int | None = None
        self._closed = False

    def popen_kwargs(self) -> dict[str, object]:
        """Creation arguments that make the child containable from birth."""
        if not _WINDOWS:
            return {"start_new_session": True}
        self._library = _kernel32()
        self._job = self._library.CreateJobObjectW(None, None)
        if not self._job:
            raise ContainmentError(
                "CreateJobObject failed, so the child cannot be contained: "
                f"winerror={ctypes.get_last_error()}"
            )
        information = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        information.BasicLimitInformation.LimitFlags = (
            _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        if not self._library.SetInformationJobObject(
            self._job,
            _JobObjectExtendedLimitInformation,
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            winerror = ctypes.get_last_error()
            self.close()
            raise ContainmentError(
                "SetInformationJobObject(KILL_ON_JOB_CLOSE) failed, so the child "
                f"cannot be contained: winerror={winerror}"
            )
        return {"creationflags": _CREATE_SUSPENDED}

    def adopt(self, process: "subprocess.Popen[bytes]") -> None:
        """Bind the created child, then let it run.  Failure is fatal."""
        if not _WINDOWS:
            try:
                self._pgid = os.getpgid(process.pid)
            except OSError as error:
                raise ContainmentError(
                    f"the child has no reachable process group: {error}"
                ) from error
            self.kind = "posix-process-group"
            return
        library = self._library
        assert library is not None
        handle = library.OpenProcess(
            _PROCESS_TERMINATE_AND_SET_QUOTA, False, process.pid
        )
        if not handle:
            raise ContainmentError(
                f"OpenProcess failed for the child: winerror={ctypes.get_last_error()}"
            )
        try:
            if not library.AssignProcessToJobObject(self._job, handle):
                raise ContainmentError(
                    "AssignProcessToJobObject failed; the child is still suspended "
                    f"and will be killed: winerror={ctypes.get_last_error()}"
                )
        finally:
            library.CloseHandle(handle)
        self._resume(process.pid)
        self.kind = "windows-job-object"

    def _resume(self, pid: int) -> None:
        library = self._library
        assert library is not None
        snapshot = library.CreateToolhelp32Snapshot(_TH32CS_SNAPTHREAD, 0)
        if not snapshot or snapshot == ctypes.c_void_p(-1).value:
            raise ContainmentError(
                "CreateToolhelp32Snapshot failed, so the assigned child cannot be "
                f"resumed: winerror={ctypes.get_last_error()}"
            )
        resumed = 0
        try:
            entry = _THREADENTRY32()
            entry.dwSize = ctypes.sizeof(_THREADENTRY32)
            more = library.Thread32First(snapshot, ctypes.byref(entry))
            while more:
                if entry.th32OwnerProcessID == pid:
                    thread = library.OpenThread(
                        _THREAD_SUSPEND_RESUME, False, entry.th32ThreadID
                    )
                    if thread:
                        try:
                            if library.ResumeThread(thread) != _RESUME_THREAD_FAILED:
                                resumed += 1
                        finally:
                            library.CloseHandle(thread)
                more = library.Thread32Next(snapshot, ctypes.byref(entry))
        finally:
            library.CloseHandle(snapshot)
        if resumed == 0:
            raise ContainmentError(
                "no thread of the suspended child could be resumed; it is assigned "
                "to the job and will be killed"
            )

    def terminate_tree(self) -> None:
        """Stop the child and every descendant.  Safe to call repeatedly."""
        if _WINDOWS:
            if self._job is None or self._closed:
                return
            assert self._library is not None
            self._library.TerminateJobObject(self._job, 1)
            return
        if self._pgid is None:
            return
        for number in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(self._pgid, number)
            except (OSError, AttributeError):
                return

    def close(self) -> None:
        """Release the containment handle.

        On Windows the job carries KILL_ON_JOB_CLOSE, so releasing the last
        handle stops whatever is still inside it.  That is what stops a
        descendant outliving its supervisor even when nobody called ``stop()``:
        interpreter exit closes the handle.
        """
        if not _WINDOWS:
            self.terminate_tree()
            return
        if self._job is None or self._closed:
            return
        assert self._library is not None
        self._library.CloseHandle(self._job)
        self._closed = True

    def evidence(self) -> dict[str, object]:
        return {
            "containment": self.kind,
            "platform": sys.platform,
            "process_group": self._pgid,
        }


class SidecarProcess:
    """Own one long-lived sidecar process and one sequential framed stream."""

    def __init__(
        self,
        command: Sequence[str] | None = None,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        max_write_chunk_bytes: int | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        if max_write_chunk_bytes is not None and max_write_chunk_bytes <= 0:
            raise ValueError("max_write_chunk_bytes must be positive or None")
        self.command = list(command) if command is not None else [
            sys.executable,
            "-I",
            "-B",
            str(LAUNCHER),
        ]
        if not self.command:
            raise ValueError("command must not be empty")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.max_write_chunk_bytes = max_write_chunk_bytes
        self._process: subprocess.Popen[bytes] | None = None
        self._tree = ProcessTree()
        self._responses: queue.Queue[ResponseFrame | BaseException | None] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._stderr_reader: threading.Thread | None = None
        self._request_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._stderr_lock = threading.Lock()
        self._stderr_bytes = bytearray()
        self._stderr_total = 0
        self._stderr_adjudications: list[dict[str, object]] = []
        self._protocol_failure: str | None = None
        self._phase = "IDLE"
        self._active_sequence = 0
        self._active_request_sha256: str | None = None
        self._completed_write_sequence = 0
        self._enqueued_response_sequence = 0
        self._last_admitted_sequence = 0
        self._write_deadline_expired = False
        self.request_attempt_count = 0
        self.request_write_count = 0
        self.host_write_call_count = 0
        self.response_count = 0
        self.stdout_frame_count = 0
        self.automatic_replay_count = 0
        self.write_deadline_count = 0

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    @property
    def returncode(self) -> int | None:
        return self._process.poll() if self._process is not None else None

    @property
    def containment(self) -> str:
        """How this child's descendants are bound: never a claim without a mechanism."""
        return self._tree.kind

    def start(self) -> "SidecarProcess":
        if self._process is not None:
            if self._process.poll() is None:
                return self
            raise SidecarFailure(
                "cannot restart a stopped instance; construct a fresh SidecarProcess"
            )
        # F-WP5-006 bound 2: the child is born inside its containment.  On
        # Windows popen_kwargs() creates the job and returns CREATE_SUSPENDED;
        # adopt() assigns and only then resumes.
        creation = self._tree.popen_kwargs()
        self._process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            **creation,
        )
        try:
            self._tree.adopt(self._process)
        except BaseException:
            # An uncontained child is never allowed to run: it is stopped and
            # the failure is raised rather than downgraded.
            self._tree.terminate_tree()
            try:
                self._process.kill()
                self._process.wait(timeout=2.0)
            except (OSError, subprocess.TimeoutExpired):
                pass
            self._tree.close()
            raise
        assert self._process.stdout is not None and self._process.stderr is not None

        def read_responses() -> None:
            assert self._process is not None and self._process.stdout is not None
            try:
                while True:
                    frame = read_response_frame(
                        self._process.stdout,
                        self.max_response_bytes,
                    )
                    if frame is None:
                        with self._state_lock:
                            in_flight = self._phase in {"WRITING", "AWAITING_RESPONSE"}
                        if in_flight:
                            self._poison("sidecar closed stdout before a response")
                        else:
                            self._responses.put(None)
                        return
                    with self._state_lock:
                        self.stdout_frame_count += 1
                        phase = self._phase
                        sequence = self._active_sequence
                        request_digest = self._active_request_sha256
                        completed = self._completed_write_sequence
                        already_enqueued = self._enqueued_response_sequence
                        last_admitted = self._last_admitted_sequence
                    if phase == "WRITING":
                        # A complete frame arrived while the host was still
                        # inside its own write path.  Identity comes from the
                        # envelope digest, never from phase timing
                        # (F-WP5-002), so wait — bounded by the caller's own
                        # deadline — for the writer's lock-protected
                        # transition instead of failing a valid early
                        # response (F-WP5-007).  A child that emitted early
                        # and then stopped draining leaves the writer blocked
                        # in WRITING; the bounded wait expires and poisons,
                        # which terminates the child and unblocks the writer.
                        wait_deadline = time.monotonic() + self.timeout_seconds
                        while True:
                            with self._state_lock:
                                phase = self._phase
                                sequence = self._active_sequence
                                request_digest = self._active_request_sha256
                                completed = self._completed_write_sequence
                                already_enqueued = self._enqueued_response_sequence
                                last_admitted = self._last_admitted_sequence
                            if phase != "WRITING" or time.monotonic() >= wait_deadline:
                                break
                            time.sleep(0.001)
                        if phase == "WRITING":
                            self._poison(
                                "sidecar emitted output and the host frame write did not complete within the deadline"
                            )
                            return
                    if phase != "AWAITING_RESPONSE":
                        self._poison("sidecar emitted unsolicited response output")
                        return
                    if completed != sequence:
                        self._poison("response arrived without a completed host frame write and flush")
                        return
                    if frame.sequence != sequence or frame.sequence != last_admitted + 1:
                        self._poison("response sequence was stale, duplicate, or reordered")
                        return
                    if frame.request_sha256 != request_digest:
                        self._poison("response request SHA-256 did not match the complete request bytes")
                        return
                    if already_enqueued == sequence:
                        self._poison("sidecar emitted a duplicate response frame")
                        return
                    with self._state_lock:
                        self._enqueued_response_sequence = sequence
                    self._responses.put(frame)
            except BaseException as error:  # owner receives parser and reader failures
                self._poison(f"sidecar stdout envelope reader failed: {error}")

        def read_stderr() -> None:
            # Drain EVERY stderr byte (F-WP5-004 correction: the first
            # implementation returned after one chunk, so the recorded
            # digest covered a 64 KiB prefix of a longer stream).  Retention
            # is bounded; the total count is always exact.
            #
            # F-WP5-006 bound 3: every arrival is adjudicated against the
            # interaction it belongs to.  Bytes that arrive while a request is
            # in flight belong to that request; bytes that arrive after its
            # response was admitted still belong to it, because nothing else
            # has been sent, and they are recorded as a RETROACTIVE
            # adjudication of that sequence.  The failure this raises names
            # that sequence, so evidence produced by interaction N is never
            # reported as a defect of interaction N+1.
            assert self._process is not None and self._process.stderr is not None
            try:
                poisoned = False
                while True:
                    chunk = self._process.stderr.read(64 * 1024)
                    if chunk == b"":
                        return
                    with self._state_lock:
                        phase = self._phase
                        in_flight = phase in {"WRITING", "AWAITING_RESPONSE"}
                        sequence = (
                            self._active_sequence
                            if in_flight
                            else self._last_admitted_sequence
                        )
                    with self._stderr_lock:
                        self._stderr_total += len(chunk)
                        room = MAX_STDERR_RETAINED_BYTES - len(self._stderr_bytes)
                        if room > 0:
                            self._stderr_bytes.extend(chunk[:room])
                        self._stderr_adjudications.append(
                            {
                                "sequence": sequence,
                                "phase": phase,
                                "bytes": len(chunk),
                                "retroactive": not in_flight and sequence > 0,
                            }
                        )
                    if not poisoned:
                        self._poison(_stderr_failure_message(sequence, in_flight))
                        poisoned = True
            except BaseException as error:
                self._poison(f"sidecar stderr reader failed: {error}")

        self._reader = threading.Thread(
            target=read_responses,
            name="receiver-reliance-sidecar-reader",
            daemon=True,
        )
        self._reader.start()
        self._stderr_reader = threading.Thread(
            target=read_stderr,
            name="receiver-reliance-sidecar-stderr-reader",
            daemon=True,
        )
        self._stderr_reader.start()
        return self

    def _poison(self, message: str) -> None:
        first = False
        with self._state_lock:
            if self._protocol_failure is None:
                self._protocol_failure = message
                self._phase = "FAILED"
                first = True
        if first:
            self._responses.put(SidecarFailure(message))
        self._terminate_ambiguous()

    def stderr_evidence(self, edge_bytes: int = 64) -> dict[str, object]:
        with self._stderr_lock:
            raw = bytes(self._stderr_bytes)
            total = self._stderr_total
        return {
            "bytes": len(raw),
            "total_bytes": total,
            "retained_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest().upper(),
            "sha256_scope": "complete" if total == len(raw) else "retained prefix",
            "prefix_hex": raw[:edge_bytes].hex().upper(),
            "tail_hex": raw[-edge_bytes:].hex().upper() if raw else "",
        }

    def stderr_adjudications(self) -> list[dict[str, object]]:
        """Which interaction each stderr arrival was charged to.

        ``retroactive`` marks an arrival that reached the supervisor after its
        interaction's response had already been admitted.  Before this existed
        such bytes surfaced as a failure of the NEXT interaction, or -- if there
        was no next interaction -- only at ``stop(check=True)``, in both cases
        naming the wrong interaction or none at all (F-WP5-006 bound 3).

        The residue, stated rather than implied: a supervisor cannot adjudicate
        bytes it has not yet received.  What it can do is charge them to the
        right interaction once they arrive, and that is what this records.
        """
        with self._stderr_lock:
            return [dict(item) for item in self._stderr_adjudications]

    def state_evidence(self) -> dict[str, object]:
        with self._state_lock:
            evidence = {
                "phase": self._phase,
                "active_sequence": self._active_sequence,
                "active_request_sha256": self._active_request_sha256,
                "completed_write_sequence": self._completed_write_sequence,
                "enqueued_response_sequence": self._enqueued_response_sequence,
                "last_admitted_sequence": self._last_admitted_sequence,
                "request_attempt_count": self.request_attempt_count,
                "request_write_count": self.request_write_count,
                "host_write_call_count": self.host_write_call_count,
                "response_count": self.response_count,
                "stdout_frame_count": self.stdout_frame_count,
                "automatic_replay_count": self.automatic_replay_count,
                "write_deadline_count": self.write_deadline_count,
                "protocol_failure": self._protocol_failure,
            }
        # Recorded in the state evidence, not only in a failure message, so a
        # receipt carries the adjudication instead of the operator having to
        # reach stop(check=True) to learn of it.
        evidence["stderr_adjudications"] = self.stderr_adjudications()
        evidence["containment"] = self._tree.kind
        return evidence

    def _failure(self, message: str) -> SidecarFailure:
        process = self._process
        code = process.poll() if process is not None else None
        evidence = self.stderr_evidence()
        suffix = f"; returncode={code}"
        if evidence["bytes"]:
            suffix += f"; stderr={evidence!r}"
        adjudications = self.stderr_adjudications()
        if adjudications:
            suffix += f"; stderr_adjudications={adjudications!r}"
        return SidecarFailure(message + suffix)

    def _terminate_ambiguous(self) -> None:
        # F-WP5-006 bound 2: the tree goes first, and it goes even when the
        # direct child is already gone -- a dead parent is not evidence that its
        # children died with it.
        self._tree.terminate_tree()
        process = self._process
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)

    def request(self, raw_line: bytes) -> bytes:
        """Send one physical engine request and return its correlated response.

        Timeout, EOF, partial/zero-progress write failure, or any envelope
        violation stops the child.  No ambiguous request is automatically
        replayed.  Both phases are deadline-bounded: the write phase by the
        watchdog below, the await phase by the queue timeout.
        """
        if not isinstance(raw_line, bytes):
            raise TypeError("raw_line must be bytes")
        if not raw_line.endswith(b"\n") or raw_line.count(b"\n") != 1:
            raise ValueError("request must be exactly one LF-terminated physical line")
        with self._request_lock:
            if self._process is None:
                self.start()
            assert self._process is not None
            if self._protocol_failure is not None:
                self._terminate_ambiguous()
                raise self._failure(self._protocol_failure)
            try:
                queued = self._responses.get_nowait()
            except queue.Empty:
                queued = ...
            if queued is not ...:
                self._poison("sidecar queued output or EOF before request")
                raise self._failure("sidecar queued output or EOF before request")
            if self._process.poll() is not None:
                raise self._failure("sidecar exited before request")
            assert self._process.stdin is not None
            with self._state_lock:
                if self._phase != "IDLE":
                    raise self._failure(f"sidecar is not idle before request: {self._phase}")
                self.request_attempt_count += 1
                sequence = self.request_attempt_count
                request_digest = sha256(raw_line)
                self._active_sequence = sequence
                self._active_request_sha256 = request_digest
                self._phase = "WRITING"
            frame_bytes = encode_request_frame(sequence, raw_line)

            def count_write() -> None:
                with self._state_lock:
                    self.host_write_call_count += 1

            # F-WP5-006 bound 1: the write phase gets the same deadline the
            # await phase already had.  ``timeout_seconds`` used to bound only
            # the wait for a response, so a child that accepted the request and
            # then stopped reading held the writer in a blocking pipe write
            # until the child died or was stopped from outside -- unbounded, and
            # invisible to a caller that had asked for a bounded interaction.
            #
            # The watchdog terminates the tree FIRST and poisons second.  That
            # order matters twice: killing the child is what breaks the pipe and
            # returns the blocked write, and it takes no lock, so the poison
            # that follows can never contend with a writer that is still inside
            # its own lock-protected flush.
            write_finished = threading.Event()

            def write_deadline_watchdog() -> None:
                if write_finished.wait(self.timeout_seconds):
                    return
                self._write_deadline_expired = True
                with self._state_lock:
                    self.write_deadline_count += 1
                self._tree.terminate_tree()
                self._poison(
                    "sidecar request frame write did not complete within the deadline; "
                    "the child was stopped and the request was not replayed"
                )

            watchdog = threading.Thread(
                target=write_deadline_watchdog,
                name="receiver-reliance-sidecar-write-deadline",
                daemon=True,
            )
            watchdog.start()
            try:
                write_all(
                    self._process.stdin,
                    frame_bytes,
                    max_chunk_bytes=self.max_write_chunk_bytes,
                    after_write=count_write,
                )
                with self._state_lock:
                    failure = self._protocol_failure
                if failure is not None:
                    raise SidecarFailure(failure)
                # Serialize flush-return and response eligibility.  A reader
                # that already has bytes still cannot admit them until this
                # lock-protected transition occurs after flush returns.
                with self._state_lock:
                    self._process.stdin.flush()
                    if self._protocol_failure is None:
                        self.request_write_count += 1
                        self._completed_write_sequence = sequence
                        self._phase = "AWAITING_RESPONSE"
                    failure = self._protocol_failure
                if failure is not None:
                    raise SidecarFailure(failure)
            except (BlockingIOError, BrokenPipeError, OSError) as error:
                message = (
                    "sidecar request frame write did not complete within the deadline; "
                    f"the child was stopped and the request was not replayed: {error}"
                    if self._write_deadline_expired
                    else f"sidecar request frame write failed: {error}"
                )
                self._poison(message)
                raise self._failure(message) from error
            except SidecarFailure as error:
                self._terminate_ambiguous()
                raise self._failure(str(error)) from error
            finally:
                write_finished.set()
                watchdog.join(timeout=2.0)
            try:
                item = self._responses.get(timeout=self.timeout_seconds)
            except queue.Empty as error:
                self._poison("sidecar response timed out; request was not replayed")
                raise self._failure("sidecar response timed out; request was not replayed") from error
            if isinstance(item, BaseException):
                self._terminate_ambiguous()
                raise self._failure(f"sidecar response reader failed: {item}") from item
            if item is None:
                self._poison("sidecar closed stdout before a response")
                raise self._failure("sidecar closed stdout before a response")
            if (
                item.sequence != sequence
                or item.request_sha256 != request_digest
                or item.payload_sha256 != sha256(item.payload)
            ):
                self._poison("response envelope did not correlate to the exact request and payload")
                raise self._failure("response envelope did not correlate to the exact request and payload")
            with self._state_lock:
                if self._phase != "AWAITING_RESPONSE":
                    failure = self._protocol_failure or f"unexpected response phase: {self._phase}"
                elif self._completed_write_sequence != sequence:
                    failure = "response admission preceded host frame write and flush completion"
                elif self._enqueued_response_sequence != sequence:
                    failure = "response was not envelope-bound by the reader"
                elif sequence != self._last_admitted_sequence + 1:
                    failure = "response admission sequence was not monotonic"
                else:
                    self.response_count += 1
                    self._last_admitted_sequence = sequence
                    self._phase = "IDLE"
                    failure = None
            if failure is not None:
                self._poison(failure)
                raise self._failure(failure)
            return item.payload

    def stop(self, *, check: bool = True, timeout_seconds: float = 5.0) -> int:
        process = self._process
        if process is None:
            self._tree.close()
            return 0
        if process.stdin is not None and not process.stdin.closed:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            self._tree.terminate_tree()
            process.terminate()
            try:
                code = process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
                code = process.wait(timeout=2.0)
        if self._reader is not None:
            self._reader.join(timeout=1.0)
        if self._stderr_reader is not None:
            self._stderr_reader.join(timeout=1.0)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
        # F-WP5-006 bound 2: the containment outlives the direct child by
        # exactly this long.  A clean parent exit is not evidence that a
        # descendant exited, so the tree is released only here, and releasing it
        # stops anything still inside.
        self._tree.close()
        stderr = self.stderr_evidence()
        with self._state_lock:
            phase = self._phase
        if check and (
            code != 0
            or stderr["bytes"] != 0
            or self._protocol_failure is not None
            or phase not in {"IDLE", "FAILED"}
        ):
            raise SidecarFailure(
                "sidecar shutdown was not clean; "
                f"returncode={code}; stderr={stderr!r}; protocol={self._protocol_failure!r}; "
                f"phase={phase}; stderr_adjudications={self.stderr_adjudications()!r}"
            )
        return code

    def __enter__(self) -> "SidecarProcess":
        return self.start()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.stop(check=exc_type is None)


def _stderr_failure_message(sequence: int, in_flight: bool) -> str:
    """Name the interaction the stderr bytes are charged to (F-WP5-006 bound 3)."""
    if in_flight:
        return f"sidecar wrote raw stderr bytes during interaction {sequence}"
    if sequence == 0:
        return "sidecar wrote raw stderr bytes before any interaction"
    return (
        "sidecar wrote raw stderr bytes attributable to interaction "
        f"{sequence}, after that interaction's response was admitted"
    )
