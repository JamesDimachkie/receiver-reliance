"""Stdlib supervisor for the request-bound anonymous-stdio sidecar.

Response identity comes only from the versioned transport envelope: the exact
monotonic sequence, SHA-256 of the complete request bytes, and SHA-256 of the
complete response payload must all validate after the host's full frame write
and flush have returned.  Phase and queue timing are fail-closed lifecycle
checks; neither can establish response identity.
"""
from __future__ import annotations

import hashlib
import pathlib
import queue
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
        self._responses: queue.Queue[ResponseFrame | BaseException | None] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._stderr_reader: threading.Thread | None = None
        self._request_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._stderr_lock = threading.Lock()
        self._stderr_bytes = bytearray()
        self._stderr_total = 0
        self._protocol_failure: str | None = None
        self._phase = "IDLE"
        self._active_sequence = 0
        self._active_request_sha256: str | None = None
        self._completed_write_sequence = 0
        self._enqueued_response_sequence = 0
        self._last_admitted_sequence = 0
        self.request_attempt_count = 0
        self.request_write_count = 0
        self.host_write_call_count = 0
        self.response_count = 0
        self.stdout_frame_count = 0
        self.automatic_replay_count = 0

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    @property
    def returncode(self) -> int | None:
        return self._process.poll() if self._process is not None else None

    def start(self) -> "SidecarProcess":
        if self._process is not None:
            if self._process.poll() is None:
                return self
            raise SidecarFailure(
                "cannot restart a stopped instance; construct a fresh SidecarProcess"
            )
        self._process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
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
            assert self._process is not None and self._process.stderr is not None
            try:
                poisoned = False
                while True:
                    chunk = self._process.stderr.read(64 * 1024)
                    if chunk == b"":
                        return
                    with self._stderr_lock:
                        self._stderr_total += len(chunk)
                        room = MAX_STDERR_RETAINED_BYTES - len(self._stderr_bytes)
                        if room > 0:
                            self._stderr_bytes.extend(chunk[:room])
                    if not poisoned:
                        self._poison("sidecar wrote raw stderr bytes")
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

    def state_evidence(self) -> dict[str, object]:
        with self._state_lock:
            return {
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
                "protocol_failure": self._protocol_failure,
            }

    def _failure(self, message: str) -> SidecarFailure:
        process = self._process
        code = process.poll() if process is not None else None
        evidence = self.stderr_evidence()
        suffix = f"; returncode={code}"
        if evidence["bytes"]:
            suffix += f"; stderr={evidence!r}"
        return SidecarFailure(message + suffix)

    def _terminate_ambiguous(self) -> None:
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
        replayed.
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
                self._poison(f"sidecar request frame write failed: {error}")
                raise self._failure(f"sidecar request frame write failed: {error}") from error
            except SidecarFailure as error:
                self._terminate_ambiguous()
                raise self._failure(str(error)) from error
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
            return 0
        if process.stdin is not None and not process.stdin.closed:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
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
                f"returncode={code}; stderr={stderr!r}; protocol={self._protocol_failure!r}; phase={phase}"
            )
        return code

    def __enter__(self) -> "SidecarProcess":
        return self.start()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.stop(check=exc_type is None)
