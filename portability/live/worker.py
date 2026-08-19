"""Child-side adapter for the live transport controller.

The accepted batch server is run unchanged.  This adapter only supplies real
OS byte streams and reports deterministic transport events on a separate
control channel (stderr).  Response bytes never traverse that channel.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import socket
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
GROUNDED = REPO / "grounded-0_4"
if str(GROUNDED) not in sys.path:
    sys.path.insert(0, str(GROUNDED))
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

import rr_batch  # noqa: E402
import strict_ingest  # noqa: E402  (ADOPTION A4: the one shared ingest law)

CONTROL_PREFIX = b"RRCTL "

# F-LIVE-009: exactly the peer-initiated connection-abort classes.  Which
# accepted-server syscall first observes a peer close is kernel-scheduled, not
# schedule-determined, so the raising frame and exception subclass are
# incidental race artifacts that must not enter replay identity.  The classes
# are translated into the internal sentinel ONLY at the physical data
# endpoints (the data sink's OS write and the data source's OS read):
# exception class alone cannot establish which endpoint raised, so a
# boundary-control or stderr-control failure keeps its own classification and
# is never laundered into transport-abort evidence (F-LIVE-005/F-LIVE-007
# doctrine).
PEER_CLOSE_ABORTS = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)
PEER_CLOSE_EXIT = 5


class _PeerCloseAbort(Exception):
    """Sentinel: a peer-initiated close observed at a physical data endpoint."""


def _serve(source: Any, sink: Any) -> int:
    try:
        return rr_batch.serve(source, sink)
    except _PeerCloseAbort:
        _control("transport_abort")
        return PEER_CLOSE_EXIT


def _control(event: str, **fields: Any) -> None:
    payload = json.dumps(
        {"event": event, **fields}, sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    os.write(2, CONTROL_PREFIX + payload + b"\n")


class NonBlockingSink:
    """A raw sink that makes real OS backpressure directly observable.

    Each write first uses nonblocking mode.  EAGAIN is acknowledged on the
    control channel, after which the same OS endpoint is put into blocking
    mode for the retry.  Progress therefore resumes only when the controller
    performs a scheduled read; no clock or polling interval participates.
    """

    def __init__(
        self,
        endpoint: int | socket.socket,
        boundary_control: socket.socket | None = None,
    ) -> None:
        self.endpoint = endpoint
        self._is_socket = isinstance(endpoint, socket.socket)
        self.boundary_control = boundary_control
        self._control_reader = (
            boundary_control.makefile("rb", buffering=0)
            if boundary_control is not None
            else None
        )
        self._response_index = 0
        self._boundary_complete = False
        self._set_blocking(False)

    def _set_blocking(self, value: bool) -> None:
        if self._is_socket:
            assert isinstance(self.endpoint, socket.socket)
            self.endpoint.setblocking(value)
        else:
            assert isinstance(self.endpoint, int)
            os.set_blocking(self.endpoint, value)

    def _write_once(self, data: memoryview) -> int:
        try:
            if self._is_socket:
                assert isinstance(self.endpoint, socket.socket)
                return self.endpoint.send(data)
            assert isinstance(self.endpoint, int)
            return os.write(self.endpoint, data)
        except PEER_CLOSE_ABORTS as error:
            raise _PeerCloseAbort("data sink peer close") from error

    def _receive_command(self, expected: str) -> dict[str, Any]:
        assert self._control_reader is not None
        line = self._control_reader.readline()
        if not line:
            raise OSError("boundary-control EOF")
        try:
            command = strict_ingest.load_safe(line, label="boundary-control")
        except strict_ingest.IngestError as error:
            raise OSError("invalid boundary-control command") from error
        if type(command) is not dict or command.get("command") != expected:
            raise OSError(f"expected boundary-control command {expected!r}")
        return command

    def _write_at_forced_boundary(self, view: memoryview) -> int:
        arm = self._receive_command("arm_write_boundary")
        response_index = arm.get("response_index")
        split = arm.get("split")
        response_bytes = arm.get("response_bytes")
        if (
            type(response_index) is not int
            or response_index != self._response_index
            or type(split) is not int
            or type(response_bytes) is not int
            or response_bytes != len(view)
            or not 0 < split <= len(view)
        ):
            raise OSError("invalid armed write boundary")

        # This is an actual write to the real data endpoint.  Limiting the OS
        # call to ``split`` forces rr_batch._write_all to observe a short
        # sink.write return for every two-part W case.
        self._set_blocking(True)
        written = self._write_once(view[:split])
        if written != split:
            _control(
                "unexpected_os_short_write",
                response_index=response_index,
                requested=split,
                written=written,
            )
            raise OSError("OS did not write the armed boundary atomically")
        _control(
            "write_boundary",
            response_index=response_index,
            offered=len(view),
            os_offered=split,
            split=split,
            written=written,
            forced_short_write=split < len(view),
        )

        resume = self._receive_command("resume_write")
        if (
            resume.get("response_index") != response_index
            or resume.get("split") != split
        ):
            raise OSError("resume does not match armed write boundary")
        _control("write_resumed", response_index=response_index, split=split)
        self._boundary_complete = True
        self._set_blocking(False)
        return written

    def write(self, data: bytes | bytearray | memoryview) -> int:
        view = memoryview(data)
        if self.boundary_control is not None and not self._boundary_complete:
            return self._write_at_forced_boundary(view)
        # A full-duplex socket source reasserts blocking mode before reads.
        # Reassert the probe mode at every write call, not only at startup.
        self._set_blocking(False)
        try:
            written = self._write_once(view)
        except (BlockingIOError, InterruptedError):
            written = 0
        if written < len(view):
            # A nonblocking partial write and EAGAIN are both genuine OS
            # backpressure.  Publish one scheduled barrier, then finish this
            # adapter call in blocking mode.  Returning the transient partial
            # count to rr_batch made the number of ordinary bulk-write calls
            # host-scheduling-dependent, so two otherwise identical replays
            # could disagree only in os_short_write_count (F-LIVE-008).  The W
            # branch above remains the sole deliberate short-return surface.
            _control("backpressure", offered=len(view))
            self._set_blocking(True)
            try:
                while written < len(view):
                    advanced = self._write_once(view[written:])
                    if advanced <= 0:
                        raise OSError("blocking output write made no progress")
                    written += advanced
            finally:
                self._set_blocking(False)
        return written

    def flush(self) -> None:
        # Writes are unbuffered at this adapter boundary.  The event pins that
        # rr_batch nevertheless issued its per-response flush call.
        _control("flush")
        self._response_index += 1
        self._boundary_complete = False


class BlockingSocketSource:
    """Restore blocking mode before each read on a full-duplex socket.

    Socket blocking mode belongs to the endpoint shared by source and sink.
    The sink intentionally leaves it nonblocking after each write probe, so
    the source must reassert blocking mode before rr_batch asks for a line.
    """

    def __init__(self, endpoint: socket.socket) -> None:
        self.endpoint = endpoint
        self.raw = endpoint.makefile("rb", buffering=0)

    def readline(self, size: int = -1) -> bytes:
        try:
            self.endpoint.setblocking(True)
            return self.raw.readline(size)
        except PEER_CLOSE_ABORTS as error:
            raise _PeerCloseAbort("data source peer close") from error

    def close(self) -> None:
        self.raw.close()


def _shared_socket_from_stdin() -> socket.socket:
    shared = base64.b64decode(sys.stdin.buffer.readline().strip(), validate=True)
    return socket.fromshare(shared)


def _socket_from_parent(fd: int | None) -> socket.socket:
    if os.name == "nt":
        return _shared_socket_from_stdin()
    if fd is None:
        raise ValueError("--fd is required outside Windows")
    return socket.socket(fileno=fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=("pipe", "socketpair"), required=True)
    parser.add_argument("--fd", type=int)
    parser.add_argument("--boundary-control-fd", type=int)
    parser.add_argument("--boundary-control-bootstrap", action="store_true")
    args = parser.parse_args()

    boundary_control = None
    if args.boundary_control_bootstrap:
        if os.name != "nt":
            raise ValueError("--boundary-control-bootstrap is Windows-only")
        # For socketpair transport, the data socket share is the first line;
        # the control share is therefore read after _socket_from_parent below.
        if args.transport == "pipe":
            boundary_control = _shared_socket_from_stdin()
    elif args.boundary_control_fd is not None:
        boundary_control = socket.socket(fileno=args.boundary_control_fd)

    if args.transport == "pipe":
        source = sys.stdin.buffer
        sink = NonBlockingSink(sys.stdout.fileno(), boundary_control)
        _control("ready", transport="pipe")
        try:
            return _serve(source, sink)
        finally:
            if boundary_control is not None:
                boundary_control.close()

    endpoint = _socket_from_parent(args.fd)
    if args.boundary_control_bootstrap:
        boundary_control = _shared_socket_from_stdin()
    endpoint.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    source = BlockingSocketSource(endpoint)
    sink = NonBlockingSink(endpoint, boundary_control)
    _control(
        "ready",
        transport="socketpair",
        send_buffer=endpoint.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF),
    )
    try:
        return _serve(source, sink)
    finally:
        source.close()
        endpoint.close()
        if boundary_control is not None:
            boundary_control.close()


if __name__ == "__main__":
    raise SystemExit(main())
