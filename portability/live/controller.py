"""Deterministic live controller for real pipe and socketpair transports.

Schedule progress is driven only by ordered actions and child acknowledgments.
The sole time limits are watchdogs that turn a hang into an infrastructure
error; they are not used to select, pace, or pass a schedule transition.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import select
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Any, BinaryIO, Iterable

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
GROUNDED = REPO / "grounded-0_4"
WORKER = HERE / "worker.py"
if str(GROUNDED) not in sys.path:
    sys.path.insert(0, str(GROUNDED))

import rr_batch  # noqa: E402

TRANSPORTS = ("pipe", "socketpair")
ACTIONS = {
    "write",
    "pause",
    "resume",
    "read",
    "close_half",
    "close_full",
    "kill",
}
CONTROL_PREFIX = b"RRCTL "
WATCHDOG_SECONDS = 30
MAX_CONTROL_RECORD_BYTES = 4096
MAX_CONTROL_INTEGER = (1 << 63) - 1


class ScheduleError(ValueError):
    pass


class TransportError(RuntimeError):
    """A harness/OS transport failure, never an implementation divergence."""

    status = "INFRASTRUCTURE_ERROR"


class HarnessFaultError(RuntimeError):
    """An internal controller/monitor defect, durably classified.

    Distinct from ``TransportError`` so a programmer fault inside the monitor
    can never be laundered as transport ``INFRASTRUCTURE_ERROR`` evidence and
    never dies silently with the monitor thread (F-LIVE-005).
    """

    status = "HARNESS_FAULT"


class DivergenceError(AssertionError):
    def __init__(self, message: str, result: "RunResult", expected: bytes) -> None:
        super().__init__(message)
        self.result = result
        self.expected = expected


class _ControlRecordError(ValueError):
    """A deterministic child-control protocol rejection."""


def _reject_duplicate_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, member in pairs:
        if key in value:
            raise _ControlRecordError("duplicate member")
        value[key] = member
    return value


def _reject_nonfinite_number(unused_token: str) -> None:
    raise _ControlRecordError("non-finite number")


def _control_integer(
    event: dict[str, Any], name: str, *, minimum: int = 0
) -> int:
    value = event.get(name)
    if type(value) is not int or not minimum <= value <= MAX_CONTROL_INTEGER:
        raise _ControlRecordError("field schema mismatch")
    return value


def _require_control_fields(event: dict[str, Any], fields: set[str]) -> None:
    if set(event) != fields:
        raise _ControlRecordError("field schema mismatch")


def _validate_control_event(value: Any) -> dict[str, Any]:
    if type(value) is not dict:
        raise _ControlRecordError("object required")
    event_name = value.get("event")
    if type(event_name) is not str:
        raise _ControlRecordError("event must be text")

    if event_name == "flush":
        _require_control_fields(value, {"event"})
    elif event_name == "ready":
        transport = value.get("transport")
        if transport == "pipe":
            _require_control_fields(value, {"event", "transport"})
        elif transport == "socketpair":
            _require_control_fields(value, {"event", "transport", "send_buffer"})
            _control_integer(value, "send_buffer", minimum=1)
        else:
            raise _ControlRecordError("field schema mismatch")
    elif event_name == "backpressure":
        _require_control_fields(value, {"event", "offered"})
        _control_integer(value, "offered", minimum=1)
    elif event_name == "short_write":
        _require_control_fields(value, {"event", "offered", "written"})
        offered = _control_integer(value, "offered", minimum=1)
        written = _control_integer(value, "written")
        if written >= offered:
            raise _ControlRecordError("field schema mismatch")
    elif event_name == "unexpected_os_short_write":
        _require_control_fields(
            value, {"event", "requested", "response_index", "written"}
        )
        requested = _control_integer(value, "requested", minimum=1)
        _control_integer(value, "response_index")
        written = _control_integer(value, "written")
        if written > requested or written == requested:
            raise _ControlRecordError("field schema mismatch")
    elif event_name == "write_boundary":
        _require_control_fields(
            value,
            {
                "event",
                "forced_short_write",
                "offered",
                "os_offered",
                "response_index",
                "split",
                "written",
            },
        )
        offered = _control_integer(value, "offered", minimum=1)
        os_offered = _control_integer(value, "os_offered", minimum=1)
        _control_integer(value, "response_index")
        split = _control_integer(value, "split", minimum=1)
        written = _control_integer(value, "written", minimum=1)
        forced = value.get("forced_short_write")
        if (
            type(forced) is not bool
            or os_offered != split
            or written != split
            or split > offered
            or forced is not (split < offered)
        ):
            raise _ControlRecordError("field schema mismatch")
    elif event_name == "write_resumed":
        _require_control_fields(value, {"event", "response_index", "split"})
        _control_integer(value, "response_index")
        _control_integer(value, "split", minimum=1)
    elif event_name == "transport_abort":
        # F-LIVE-009: a peer-initiated connection abort inside the accepted
        # server.  Deliberately field-free: which syscall observed the close
        # (and therefore the exception subclass and raising frame) is a
        # kernel-race artifact excluded from replay identity.
        _require_control_fields(value, {"event"})
    else:
        raise _ControlRecordError("unsupported event")
    return value


def _decode_control_record(line: bytes) -> dict[str, Any]:
    try:
        payload = line[len(CONTROL_PREFIX) : -1].decode("utf-8")
        value = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_members,
            parse_constant=_reject_nonfinite_number,
        )
    except _ControlRecordError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        raise _ControlRecordError("valid bounded JSON required") from error
    return _validate_control_event(value)


@dataclass(frozen=True)
class Step:
    step: int
    action: str
    barrier: str
    payload: bytes = b""
    byte_range: tuple[int, int] | None = None


@dataclass(frozen=True)
class RunResult:
    schedule: str
    transport: str
    stdout: bytes
    stderr: bytes
    returncode: int
    acknowledgments: tuple[dict[str, Any], ...]
    backpressure_observed: bool
    flush_count: int
    w_partition_count: int
    pause_count: int
    resume_count: int
    write_boundary_count: int
    forced_short_write_count: int
    os_short_write_count: int
    write_resume_ack_count: int
    fault_schedule: bool = False

    def stable_bytes(self) -> bytes:
        metadata = {
            "schedule": self.schedule,
            "transport": self.transport,
            "fault_schedule": self.fault_schedule,
            "acknowledgments": self.acknowledgments,
            "backpressure_observed": self.backpressure_observed,
            "w_partition_count": self.w_partition_count,
            "pause_count": self.pause_count,
            "resume_count": self.resume_count,
            "write_boundary_count": self.write_boundary_count,
            "forced_short_write_count": self.forced_short_write_count,
            "os_short_write_count": self.os_short_write_count,
            "write_resume_ack_count": self.write_resume_ack_count,
            "stdout_b64": base64.b64encode(self.stdout).decode("ascii"),
        }
        if not self.fault_schedule:
            # F-LIVE-010: a schedule whose terminal action is an asynchronous
            # fault (kill, or full close during observed backpressure) cuts
            # the child at a kernel-scheduled instant.  How far the child's
            # control-event tail progressed (flush_count), which stop path it
            # took (returncode 5 orderly abort versus a forced reap), and its
            # stderr tail are race artifacts of that instant.  They stay in
            # summary() as durable evidence but are excluded from replay
            # identity; the schedule-driven data plane and barrier-synced
            # counters above remain bound for every schedule.
            metadata["returncode"] = self.returncode
            metadata["flush_count"] = self.flush_count
            metadata["stderr_b64"] = base64.b64encode(self.stderr).decode("ascii")
        return json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("ascii")

    def summary(self) -> dict[str, Any]:
        return {
            "schedule": self.schedule,
            "transport": self.transport,
            "returncode": self.returncode,
            "stdout_bytes": len(self.stdout),
            "stdout_sha256": hashlib.sha256(self.stdout).hexdigest().upper(),
            "stderr_bytes": len(self.stderr),
            "stderr_sha256": hashlib.sha256(self.stderr).hexdigest().upper(),
            "ack_sha256": hashlib.sha256(
                json.dumps(
                    self.acknowledgments, sort_keys=True, separators=(",", ":")
                ).encode("ascii")
            ).hexdigest().upper(),
            "backpressure_observed": self.backpressure_observed,
            "flush_count": self.flush_count,
            "w_partition_count": self.w_partition_count,
            "pause_count": self.pause_count,
            "resume_count": self.resume_count,
            "write_boundary_count": self.write_boundary_count,
            "forced_short_write_count": self.forced_short_write_count,
            "os_short_write_count": self.os_short_write_count,
            "write_resume_ack_count": self.write_resume_ack_count,
        }


def load_schedule(path: pathlib.Path | str) -> tuple[Step, ...]:
    schedule_path = pathlib.Path(path)
    steps: list[Step] = []
    barriers: set[str] = set()
    with schedule_path.open("r", encoding="utf-8", newline="") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.endswith("\n"):
                raise ScheduleError(f"line {line_number}: NDJSON line must end with LF")
            try:
                item = json.loads(line)
            except json.JSONDecodeError as error:
                raise ScheduleError(f"line {line_number}: {error}") from error
            if type(item) is not dict:
                raise ScheduleError(f"line {line_number}: object required")
            required = {"step", "action", "barrier"}
            if not required.issubset(item):
                raise ScheduleError(f"line {line_number}: missing {sorted(required - set(item))}")
            if item["step"] != len(steps):
                raise ScheduleError(f"line {line_number}: expected step {len(steps)}")
            if item["action"] not in ACTIONS:
                raise ScheduleError(f"line {line_number}: unknown action {item['action']!r}")
            barrier = item["barrier"]
            if type(barrier) is not str or not barrier or barrier in barriers:
                raise ScheduleError(f"line {line_number}: barrier must be unique nonempty text")
            barriers.add(barrier)
            payload = b""
            if "bytes_b64" in item:
                if item["action"] != "write" or type(item["bytes_b64"]) is not str:
                    raise ScheduleError(f"line {line_number}: bytes_b64 is write-only text")
                try:
                    payload = base64.b64decode(item["bytes_b64"], validate=True)
                except Exception as error:
                    raise ScheduleError(f"line {line_number}: invalid base64") from error
            elif item["action"] == "write":
                raise ScheduleError(f"line {line_number}: write requires bytes_b64")
            byte_range = None
            if "range" in item:
                value = item["range"]
                if (
                    item["action"] != "read"
                    or type(value) is not list
                    or len(value) != 2
                    or any(type(part) is not int or part < 0 for part in value)
                    or value[1] < value[0]
                ):
                    raise ScheduleError(f"line {line_number}: invalid read range")
                byte_range = (value[0], value[1])
            elif item["action"] == "read":
                raise ScheduleError(f"line {line_number}: read requires range")
            unknown = set(item) - {"step", "action", "barrier", "bytes_b64", "range"}
            if unknown:
                raise ScheduleError(f"line {line_number}: unknown fields {sorted(unknown)}")
            steps.append(Step(item["step"], item["action"], barrier, payload, byte_range))
    if not steps:
        raise ScheduleError("schedule is empty")
    if not any(step.action in {"close_half", "close_full", "kill"} for step in steps):
        raise ScheduleError("schedule requires an explicit terminal transport action")
    return tuple(steps)


class _ControlMonitor:
    def __init__(self, stream: BinaryIO) -> None:
        self.stream = stream
        self.events: list[dict[str, Any]] = []
        self.stderr = bytearray()
        self.finished = False
        self.transport_error: TransportError | None = None
        self.harness_fault: HarnessFaultError | None = None
        self.control_abort: BaseException | None = None
        self.condition = threading.Condition()
        self.thread = threading.Thread(target=self._consume, name="rr-live-control", daemon=True)
        self.thread.start()

    def _read_physical(self) -> bytes:
        """Perform the one OS read; the sole transport-normalization site.

        OSError covers failed OS reads (including its I/O subclasses);
        ValueError is the deterministic closed-stream failure from Python's
        binary I/O wrappers.  Only exceptions escaping this physical read may
        become transport ``INFRASTRUCTURE_ERROR`` evidence (F-LIVE-005).
        """
        try:
            return self.stream.readline(MAX_CONTROL_RECORD_BYTES + 1)
        except (OSError, ValueError) as error:
            raise TransportError(
                "control-channel read failure: " + self._io_error_kind(error)
            ) from error

    def _consume(self) -> None:
        try:
            while True:
                line = self._read_physical()
                if not line:
                    break
                is_control = line.startswith(CONTROL_PREFIX)
                if not line.endswith(b"\n"):
                    if is_control:
                        reason = (
                            "record exceeds byte limit"
                            if len(line) > MAX_CONTROL_RECORD_BYTES
                            else "record must end with LF"
                        )
                        self._fail_control(reason)
                    else:
                        self.stderr.extend(line)
                    # Drain one physical record in bounded reads so an
                    # oversized producer cannot block forever on stderr.
                    while line and not line.endswith(b"\n"):
                        line = self._read_physical()
                        if not is_control:
                            self.stderr.extend(line)
                    continue
                if len(line) > MAX_CONTROL_RECORD_BYTES:
                    if is_control:
                        self._fail_control("record exceeds byte limit")
                    else:
                        self.stderr.extend(line)
                    continue
                if not is_control:
                    self.stderr.extend(line)
                    continue
                try:
                    event = _decode_control_record(line)
                except _ControlRecordError as error:
                    self._fail_control(str(error))
                    continue
                with self.condition:
                    self.events.append(event)
                    self.condition.notify_all()
        except TransportError as error:
            self._fail_transport(str(error))
        except Exception as error:  # noqa: BLE001 -- deliberate fault boundary
            # Anything the loop body itself raises is a programmer defect in
            # this harness, never transport evidence: record it durably under
            # its own class instead of relabeling it INFRASTRUCTURE_ERROR or
            # letting the thread die silently (F-LIVE-005).
            self._fail_harness(error)
        except BaseException as error:
            # A BaseException cannot propagate across a thread boundary by
            # itself.  Preserve it verbatim and re-raise it from the caller's
            # next monitor consultation; otherwise a silent monitor exit is
            # later laundered into ``child exited`` transport evidence.
            # KeyboardInterrupt and SystemExit remain neither transport nor
            # harness evidence.
            self._fail_control_abort(error)
        finally:
            with self.condition:
                self.finished = True
                self.condition.notify_all()

    @staticmethod
    def _io_error_kind(error: OSError | ValueError) -> str:
        # Normalize OSError subclasses so the receipt does not vary with the
        # host's concrete pipe/socket exception class.
        return "OSError" if isinstance(error, OSError) else "ValueError"

    def _fail_transport(self, reason: str) -> None:
        with self.condition:
            if self.transport_error is None:
                self.transport_error = TransportError(reason)
            self.condition.notify_all()

    def _fail_control(self, reason: str) -> None:
        self._fail_transport(f"invalid child control record: {reason}")

    def _fail_harness(self, error: BaseException) -> None:
        # Render before taking the lock, and never let the renderer itself
        # raise: a fault whose metaclass __name__ lookup fails, whose
        # __str__ raises, or whose __name__ is a hostile str subclass that
        # raises on formatting must still be recorded, not escape this
        # handler and die through threading.excepthook (R-LIVE-5
        # refutations of the first three F-LIVE-005 author states).  The
        # last resort is a constant that formats no foreign object; a
        # successful f-string always yields an exact str, so `detail` is
        # inert once assigned.  Exception matching itself dispatches on the
        # real type, so a hostile metaclass cannot reach these clauses.
        try:
            name = type(error).__name__
        except Exception:
            name = "<unprintable exception type>"
        try:
            detail = f"{name}: {error}"
        except Exception:
            try:
                detail = f"{name}: <unprintable fault detail>"
            except Exception:
                detail = "<unprintable fault>"
        with self.condition:
            if self.harness_fault is None:
                self.harness_fault = HarnessFaultError(
                    f"monitor harness fault: {detail}"
                )
                self.harness_fault.__cause__ = error
            self.condition.notify_all()

    def _fail_control_abort(self, error: BaseException) -> None:
        with self.condition:
            if self.control_abort is None:
                self.control_abort = error
            self.condition.notify_all()

    def _raise_transport_error(self) -> None:
        abort = getattr(self, "control_abort", None)
        if abort is not None:
            raise abort
        # A recorded harness fault outranks transport labeling: once the
        # monitor itself is defective, its transport claims are unreliable.
        fault = getattr(self, "harness_fault", None)
        if fault is not None:
            raise fault
        error = getattr(self, "transport_error", None)
        if error is not None:
            raise error

    def wait_for(self, event_name: str, occurrence: int = 1) -> dict[str, Any]:
        with self.condition:
            self._raise_transport_error()
            matched = [event for event in self.events if event.get("event") == event_name]
            while len(matched) < occurrence and not self.finished:
                # Watchdog only: a successful transition is event-driven.
                notified = self.condition.wait(WATCHDOG_SECONDS)
                if not notified:
                    raise TransportError(f"watchdog waiting for child event {event_name!r}")
                self._raise_transport_error()
                matched = [event for event in self.events if event.get("event") == event_name]
            self._raise_transport_error()
            if len(matched) < occurrence:
                raise TransportError(f"child exited before event {event_name!r}")
            return matched[occurrence - 1]

    def finish(self) -> None:
        self.thread.join(WATCHDOG_SECONDS)
        if self.thread.is_alive():
            raise TransportError("watchdog waiting for control-channel EOF")
        self._close_stream()
        self._raise_transport_error()

    def _close_stream(self) -> None:
        try:
            self.stream.close()
        except (OSError, ValueError) as error:
            self._fail_transport(
                "control-channel close failure: " + self._io_error_kind(error)
            )

    def count(self, event_name: str) -> int:
        with self.condition:
            self._raise_transport_error()
            return sum(event.get("event") == event_name for event in self.events)


class _Connection:
    def __init__(
        self,
        transport: str,
        process: subprocess.Popen[bytes],
        monitor: _ControlMonitor,
        endpoint: socket.socket | None = None,
        control_endpoint: socket.socket | None = None,
    ) -> None:
        self.transport = transport
        self.process = process
        self.monitor = monitor
        self.endpoint = endpoint
        self.control_endpoint = control_endpoint
        self.input_closed = False
        self.output_closed = False

    def _await_pipe(self, fd: int, mode: str) -> None:
        # F-LIVE-011: every controller data-plane OS call carries the same
        # watchdog bound the event waits already have, so an unresponsive
        # child produces a minimized TransportError witness instead of an
        # unbounded stall.  select() bounds POSIX pipes; Windows pipes cannot
        # be select()ed and retain the schedule-level reap watchdog only.
        if os.name == "nt":
            return
        readable = [fd] if mode == "read" else []
        writable = [fd] if mode == "write" else []
        ready = select.select(readable, writable, [], WATCHDOG_SECONDS)
        if not any(ready):
            raise TransportError(f"watchdog: parent pipe {mode} stalled")

    def write_all(self, data: bytes) -> None:
        view = memoryview(data)
        offset = 0
        while offset < len(view):
            if self.transport == "pipe":
                assert self.process.stdin is not None
                self._await_pipe(self.process.stdin.fileno(), "write")
                written = os.write(self.process.stdin.fileno(), view[offset:])
            else:
                assert self.endpoint is not None
                try:
                    written = self.endpoint.send(view[offset:])
                except socket.timeout as error:
                    raise TransportError(
                        "watchdog: parent socket write stalled"
                    ) from error
            if written <= 0:
                raise TransportError("parent transport write made no progress")
            offset += written

    def read_exact(self, size: int, each_byte: bool = False) -> bytes:
        chunks: list[bytes] = []
        remaining = size
        while remaining:
            offered = 1 if each_byte else min(remaining, 64 * 1024)
            if self.transport == "pipe":
                assert self.process.stdout is not None
                self._await_pipe(self.process.stdout.fileno(), "read")
                chunk = os.read(self.process.stdout.fileno(), offered)
            else:
                assert self.endpoint is not None
                try:
                    chunk = self.endpoint.recv(offered)
                except socket.timeout as error:
                    raise TransportError(
                        "watchdog: parent socket read stalled"
                    ) from error
            if not chunk:
                raise TransportError(f"EOF with {remaining} scheduled response bytes missing")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def send_control(self, command: dict[str, Any]) -> None:
        if self.control_endpoint is None:
            raise TransportError("schedule requires an unavailable control endpoint")
        payload = json.dumps(command, sort_keys=True, separators=(",", ":")).encode(
            "ascii"
        )
        try:
            self.control_endpoint.sendall(payload + b"\n")
        except socket.timeout as error:
            raise TransportError(
                "watchdog: boundary-control write stalled"
            ) from error

    def close_half(self) -> None:
        if self.input_closed:
            return
        if self.transport == "pipe":
            assert self.process.stdin is not None
            self.process.stdin.close()
        else:
            assert self.endpoint is not None
            self.endpoint.shutdown(socket.SHUT_WR)
        self.input_closed = True

    def close_full(self) -> None:
        if self.transport == "pipe":
            if not self.input_closed and self.process.stdin is not None:
                self.process.stdin.close()
            if not self.output_closed and self.process.stdout is not None:
                self.process.stdout.close()
        elif self.endpoint is not None:
            self.endpoint.close()
        if self.control_endpoint is not None:
            self.control_endpoint.close()
            self.control_endpoint = None
        self.input_closed = True
        self.output_closed = True

    def kill(self) -> None:
        self.process.kill()
        self.close_full()


def _await_ready(connection: _Connection) -> _Connection:
    try:
        connection.monitor.wait_for("ready")
    except BaseException:
        # Any failure can precede the ready event.  At that point the caller
        # has no returned connection whose normal finally block could reap the
        # child, so cleanup belongs to this spawn boundary.  In particular,
        # preserve and re-raise a monitor BaseException after cleanup rather
        # than either leaking the child or relabeling the abort as evidence.
        if connection.process.poll() is None:
            connection.process.kill()
        connection.close_full()
        try:
            connection.process.wait(timeout=WATCHDOG_SECONDS)
        except subprocess.TimeoutExpired:
            pass
        connection.monitor.thread.join(WATCHDOG_SECONDS)
        if not connection.monitor.thread.is_alive():
            # Preserve the wait failure as the causal stop while still routing
            # an adjacent close failure into the monitor's sticky state.
            connection.monitor._close_stream()
        raise
    return connection


def _spawn(transport: str, *, boundary_control: bool = False) -> _Connection:
    command = [sys.executable, "-B", str(WORKER), "--transport", transport]
    control_parent = None
    control_child = None
    pass_fds: list[int] = []
    if boundary_control:
        control_parent, control_child = socket.socketpair()
        control_parent.settimeout(WATCHDOG_SECONDS)
        if os.name == "nt":
            command.append("--boundary-control-bootstrap")
        else:
            command.extend(("--boundary-control-fd", str(control_child.fileno())))
            pass_fds.append(control_child.fileno())
    if transport == "pipe":
        popen_options: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "pipesize": 4096,
        }
        if pass_fds:
            popen_options["pass_fds"] = tuple(pass_fds)
        process = subprocess.Popen(command, **popen_options)
        if os.name == "nt" and control_child is not None:
            assert process.stdin is not None
            process.stdin.write(base64.b64encode(control_child.share(process.pid)) + b"\n")
            process.stdin.flush()
        if control_child is not None:
            control_child.close()
        assert process.stdout is not None and process.stderr is not None
        if os.name != "nt":
            try:
                import fcntl

                fcntl.fcntl(process.stdout.fileno(), fcntl.F_SETPIPE_SZ, 4096)
            except (AttributeError, OSError):
                pass
        monitor = _ControlMonitor(process.stderr)
        return _await_ready(
            _Connection(
                transport, process, monitor, control_endpoint=control_parent
            )
        )

    parent, child = socket.socketpair()
    # F-LIVE-011: the same watchdog bound as every event wait, applied at the
    # socket layer so no controller data-plane call can stall unboundedly.
    parent.settimeout(WATCHDOG_SECONDS)
    parent.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    child.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    if os.name == "nt":
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        assert process.stdin is not None
        process.stdin.write(base64.b64encode(child.share(process.pid)) + b"\n")
        if control_child is not None:
            process.stdin.write(base64.b64encode(control_child.share(process.pid)) + b"\n")
            control_child.close()
        process.stdin.close()
    else:
        command.extend(("--fd", str(child.fileno())))
        pass_fds.append(child.fileno())
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            pass_fds=tuple(pass_fds),
        )
    child.close()
    if control_child is not None and os.name != "nt":
        control_child.close()
    assert process.stderr is not None
    monitor = _ControlMonitor(process.stderr)
    return _await_ready(
        _Connection(
            transport, process, monitor, parent, control_endpoint=control_parent
        )
    )


def _physical_lines(raw: bytes) -> Iterable[bytes]:
    offset = 0
    while offset < len(raw):
        newline = raw.find(b"\n", offset)
        if newline < 0:
            yield raw[offset:]
            return
        yield raw[offset : newline + 1]
        offset = newline + 1


def isolated_expected(raw: bytes) -> bytes:
    return b"".join(rr_batch.response_bytes(line) for line in _physical_lines(raw))


W_PAUSE_BARRIER = "w-partition-writer-blocked-reader-paused"
W_RESUME_BARRIER = "w-partition-reader-resumed-writer-released"
W_READ_BARRIER = "w-partition-response-read"


def _is_w_schedule(steps: tuple[Step, ...]) -> bool:
    return (
        tuple(step.action for step in steps)
        == ("write", "pause", "resume", "read", "close_half")
        and steps[1].barrier == W_PAUSE_BARRIER
        and steps[2].barrier == W_RESUME_BARRIER
        and steps[3].barrier == W_READ_BARRIER
    )


def _run_w_schedule(
    schedule_path: pathlib.Path,
    transport: str,
    steps: tuple[Step, ...],
) -> RunResult:
    request = steps[0].payload
    expected_response = isolated_expected(request)
    if not request or request.count(b"\n") != 1 or not request.endswith(b"\n"):
        raise ScheduleError("W expansion requires exactly one LF-terminated request")
    if steps[3].byte_range != (0, len(expected_response)):
        raise ScheduleError("W read range must equal the isolated first response")

    # W <= 2: k == response_bytes is the one-write partition; every
    # 1 <= k < response_bytes is the complete two-write split [0,k),[k,n).
    split_positions = range(1, len(expected_response) + 1)
    connection = _spawn(transport, boundary_control=True)
    raw_input = bytearray()
    actual = bytearray()
    acknowledgments: list[dict[str, Any]] = []

    try:
        for response_index, split in enumerate(split_positions):
            partition = (
                [0, len(expected_response)]
                if split == len(expected_response)
                else [0, split, len(expected_response)]
            )
            connection.send_control(
                {
                    "command": "arm_write_boundary",
                    "response_bytes": len(expected_response),
                    "response_index": response_index,
                    "split": split,
                }
            )
            connection.write_all(request)
            raw_input.extend(request)
            acknowledgments.append(
                {
                    "step": steps[0].step,
                    "action": "write",
                    "barrier": steps[0].barrier,
                    "bytes": len(request),
                    "response_index": response_index,
                    "w_partition": partition,
                }
            )

            boundary = connection.monitor.wait_for(
                "write_boundary", response_index + 1
            )
            expected_boundary = {
                "response_index": response_index,
                "offered": len(expected_response),
                "os_offered": split,
                "split": split,
                "written": split,
                "forced_short_write": split < len(expected_response),
            }
            if any(boundary.get(key) != value for key, value in expected_boundary.items()):
                raise TransportError(
                    f"write-boundary acknowledgment mismatch at W split {split}"
                )
            acknowledgments.append(
                {
                    "step": steps[1].step,
                    "action": "pause",
                    "barrier": steps[1].barrier,
                    "response_index": response_index,
                    "w_partition": partition,
                    "writer_event": boundary["event"],
                    "forced_short_write": boundary["forced_short_write"],
                }
            )

            # The writer cannot issue the suffix before this exact prefix has
            # crossed the real pipe/socket endpoint: it is blocked waiting for
            # the following resume command on the independent control channel.
            prefix = connection.read_exact(split)
            connection.send_control(
                {
                    "command": "resume_write",
                    "response_index": response_index,
                    "split": split,
                }
            )
            resumed = connection.monitor.wait_for(
                "write_resumed", response_index + 1
            )
            if (
                resumed.get("response_index") != response_index
                or resumed.get("split") != split
            ):
                raise TransportError(
                    f"write-resume acknowledgment mismatch at W split {split}"
                )
            acknowledgments.append(
                {
                    "step": steps[2].step,
                    "action": "resume",
                    "barrier": steps[2].barrier,
                    "prefix_bytes_read": len(prefix),
                    "response_index": response_index,
                    "w_partition": partition,
                    "writer_event": resumed["event"],
                }
            )

            suffix = connection.read_exact(len(expected_response) - split)
            connection.monitor.wait_for("flush", response_index + 1)
            response = prefix + suffix
            actual.extend(response)
            acknowledgments.append(
                {
                    "step": steps[3].step,
                    "action": "read",
                    "barrier": steps[3].barrier,
                    "bytes": len(response),
                    "range": [0, len(response)],
                    "response_index": response_index,
                    "w_partition": partition,
                }
            )

        connection.close_half()
        acknowledgments.append(
            {
                "step": steps[4].step,
                "action": "close_half",
                "barrier": steps[4].barrier,
            }
        )
        try:
            returncode = connection.process.wait(timeout=WATCHDOG_SECONDS)
        except subprocess.TimeoutExpired as error:
            connection.kill()
            raise TransportError("watchdog: child did not terminate after W schedule") from error
        connection.monitor.finish()
        if connection.monitor.count("short_write"):
            raise TransportError("unplanned OS short write expanded a W partition")
        if connection.monitor.count("unexpected_os_short_write"):
            raise TransportError("OS write stopped before an armed W boundary")
        result = RunResult(
            schedule=schedule_path.name,
            transport=transport,
            stdout=bytes(actual),
            stderr=bytes(connection.monitor.stderr),
            returncode=returncode,
            acknowledgments=tuple(acknowledgments),
            backpressure_observed=connection.monitor.count("backpressure") > 0,
            flush_count=connection.monitor.count("flush"),
            w_partition_count=len(expected_response),
            pause_count=sum(ack["action"] == "pause" for ack in acknowledgments),
            resume_count=sum(ack["action"] == "resume" for ack in acknowledgments),
            write_boundary_count=connection.monitor.count("write_boundary"),
            forced_short_write_count=sum(
                event.get("event") == "write_boundary"
                and event.get("forced_short_write") is True
                for event in connection.monitor.events
            ),
            os_short_write_count=connection.monitor.count("short_write"),
            write_resume_ack_count=connection.monitor.count("write_resumed"),
        )
        expected = isolated_expected(bytes(raw_input))
        if returncode == 0 and result.stdout != expected:
            raise DivergenceError(
                f"{schedule_path.name}/{transport}: W live bytes differ from isolated bytes",
                result,
                expected,
            )
        return result
    finally:
        if connection.process.poll() is None:
            connection.process.kill()
            connection.process.wait(timeout=WATCHDOG_SECONDS)
        if not connection.input_closed or not connection.output_closed:
            connection.close_full()


def _run_schedule_once(
    path: pathlib.Path | str,
    transport: str,
    *,
    steps: tuple[Step, ...] | None = None,
) -> RunResult:
    if transport not in TRANSPORTS:
        raise ValueError(f"transport must be one of {TRANSPORTS}")
    schedule_path = pathlib.Path(path)
    loaded = steps if steps is not None else load_schedule(schedule_path)
    connection = _spawn(transport)
    raw_input = bytearray()
    actual = bytearray()
    acknowledgments: list[dict[str, Any]] = []
    paused = False
    offset = 0
    pause_count = 0
    resume_count = 0
    disruptive = False

    try:
        for step in loaded:
            detail: dict[str, Any] = {
                "step": step.step,
                "action": step.action,
                "barrier": step.barrier,
            }
            if step.action == "write":
                if connection.input_closed:
                    raise ScheduleError(f"step {step.step}: write after input close")
                connection.write_all(step.payload)
                raw_input.extend(step.payload)
                detail["bytes"] = len(step.payload)
            elif step.action == "pause":
                paused = True
                pause_count += 1
                if step.barrier == "backpressure-observed":
                    event = connection.monitor.wait_for("backpressure")
                    detail["event"] = event["event"]
            elif step.action == "resume":
                paused = False
                resume_count += 1
            elif step.action == "read":
                if paused:
                    raise ScheduleError(f"step {step.step}: read while paused")
                assert step.byte_range is not None
                start, end = step.byte_range
                if start != offset:
                    raise ScheduleError(
                        f"step {step.step}: range starts at {start}, current offset is {offset}"
                    )
                chunk = connection.read_exact(end - start)
                actual.extend(chunk)
                offset = end
                detail["bytes"] = len(chunk)
            elif step.action == "close_half":
                connection.close_half()
            elif step.action == "close_full":
                disruptive = connection.monitor.count("backpressure") > 0
                connection.close_full()
            elif step.action == "kill":
                disruptive = True
                connection.kill()
            acknowledgments.append(detail)

        try:
            returncode = connection.process.wait(timeout=WATCHDOG_SECONDS)
        except subprocess.TimeoutExpired as error:
            connection.kill()
            raise TransportError("watchdog: child did not terminate after schedule") from error
        connection.monitor.finish()
        result = RunResult(
            schedule=schedule_path.name,
            transport=transport,
            stdout=bytes(actual),
            stderr=bytes(connection.monitor.stderr),
            returncode=returncode,
            acknowledgments=tuple(acknowledgments),
            backpressure_observed=connection.monitor.count("backpressure") > 0,
            flush_count=connection.monitor.count("flush"),
            w_partition_count=0,
            pause_count=pause_count,
            resume_count=resume_count,
            write_boundary_count=connection.monitor.count("write_boundary"),
            forced_short_write_count=0,
            os_short_write_count=connection.monitor.count("short_write"),
            write_resume_ack_count=connection.monitor.count("write_resumed"),
            fault_schedule=disruptive,
        )
        if returncode == 0 and not disruptive:
            expected = isolated_expected(bytes(raw_input))
            if result.stdout != expected:
                raise DivergenceError(
                    f"{schedule_path.name}/{transport}: live bytes differ from isolated bytes",
                    result,
                    expected,
                )
        return result
    finally:
        if connection.process.poll() is None:
            connection.process.kill()
            connection.process.wait(timeout=WATCHDOG_SECONDS)
        if not connection.input_closed or not connection.output_closed:
            connection.close_full()


def run_schedule(
    path: pathlib.Path | str,
    transport: str,
    *,
    steps: tuple[Step, ...] | None = None,
) -> RunResult:
    if transport not in TRANSPORTS:
        raise ValueError(f"transport must be one of {TRANSPORTS}")
    schedule_path = pathlib.Path(path)
    loaded = steps if steps is not None else load_schedule(schedule_path)
    if _is_w_schedule(loaded):
        return _run_w_schedule(schedule_path, transport, loaded)
    return _run_schedule_once(schedule_path, transport, steps=loaded)


def run_both(path: pathlib.Path | str) -> dict[str, RunResult]:
    steps = load_schedule(path)
    return {
        transport: run_schedule(path, transport, steps=steps) for transport in TRANSPORTS
    }
