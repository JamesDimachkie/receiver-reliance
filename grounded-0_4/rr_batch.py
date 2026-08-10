"""Persistent NDJSON transport for the grounded 0.4 audited API.

The transport is intentionally only framing.  Each physical input line is
passed, byte-for-byte (including its line ending, if present), to
``rr_api.decide_audited``.  Exactly one RFC 8785/JCS response followed by LF
is written and flushed for that line.  Consequently malformed input remains
a per-request protocol error with the same audited bytes as an isolated call;
it does not terminate or contaminate the stream.

EOF is a clean process shutdown.  The process exit status is therefore zero
after a normally consumed stream; each request's frozen-engine exit status is
carried in that request's audited response.  Stderr is unused.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
from typing import BinaryIO

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import rr_api

_READ_CHUNK_BYTES = 64 * 1024


def response_bytes(raw_line: bytes) -> bytes:
    """Return the existing one-shot audited response bytes for ``raw_line``."""
    return rr_api.b1.jcs_bytes(rr_api.decide_audited(raw_line)) + b"\n"


def _overlimit_response_bytes(request_raw_sha256: str) -> bytes:
    """Reproduce ``decide_audited`` after its pre-decode size rejection.

    The frozen parser rejects an oversized request before inspecting any
    content, so its sealed response is the constant core ``ERR_LIMIT`` shape.
    Only the audited raw-request digest varies.  Receiving that digest from an
    incremental hasher preserves exact one-shot bytes without retaining an
    untrusted physical line.
    """
    sealed_response, exit_code = rr_api.pcb_runner._protocol_error("ERR_LIMIT", "")
    audited = {
        "format_version": rr_api.AUDIT_FORMAT,
        "sealed_response": sealed_response,
        "exit_code": exit_code,
        "audit": {
            "request_raw_sha256": request_raw_sha256,
            "engine_generation": "composed-0.3-frozen",
            "decision_input_sha256": None,
            "errors": sealed_response.get("errors"),
        },
        "audited_behavior_class": "PROTOCOL_ERROR",
        "audit_sha256": rr_api.b1.ZERO64,
    }
    audited["audit_sha256"] = rr_api.b1.self_zero_sha256(audited, "audit_sha256")
    return rr_api.b1.jcs_bytes(audited) + b"\n"


def _read_request(source: BinaryIO) -> tuple[bytes | None, str | None]:
    """Read one physical line with memory bounded by ``MAX_INPUT_BYTES``.

    Returns ``(raw, None)`` for an in-bound request, ``(None, digest)`` for an
    oversized request, and ``(None, None)`` for clean EOF.  Once the line
    crosses the cap, retained chunks are released and the remainder is
    drained through LF or EOF into an incremental SHA-256 only.
    """
    chunks: list[bytes] = []
    retained = 0
    digest = None
    saw_input = False
    while True:
        chunk = source.readline(_READ_CHUNK_BYTES)
        if chunk == b"":
            if not saw_input:
                return None, None
            if digest is not None:
                return None, digest.hexdigest().upper()
            return b"".join(chunks), None
        if not isinstance(chunk, bytes):
            raise TypeError("binary source.readline() must return bytes")
        if len(chunk) > _READ_CHUNK_BYTES:
            raise OSError("binary source.readline(size) exceeded the requested bound")
        saw_input = True
        if digest is not None:
            digest.update(chunk)
        elif retained + len(chunk) <= rr_api.b1.MAX_INPUT_BYTES:
            chunks.append(chunk)
            retained += len(chunk)
        else:
            digest = hashlib.sha256()
            for retained_chunk in chunks:
                digest.update(retained_chunk)
            digest.update(chunk)
            chunks.clear()
        if chunk.endswith(b"\n"):
            if digest is not None:
                return None, digest.hexdigest().upper()
            return b"".join(chunks), None


def _write_all(sink: BinaryIO, data: bytes) -> None:
    """Write every byte or raise before flush; never accept silent truncation."""
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = sink.write(view[offset:])
        if written is None or written == 0:
            raise BlockingIOError("binary sink.write() made no progress")
        if type(written) is not int or written < 0 or written > len(view) - offset:
            raise OSError(f"binary sink.write() returned invalid byte count: {written!r}")
        offset += written


def serve(source: BinaryIO, sink: BinaryIO) -> int:
    """Consume one request per physical line until EOF.

    No state derived from a request is retained between iterations.  Flushing
    each response makes the same process usable by request/response clients,
    not only by clients that close stdin after sending a complete batch.
    """
    while True:
        raw_line, overlimit_sha256 = _read_request(source)
        if raw_line is None and overlimit_sha256 is None:
            return 0
        if overlimit_sha256 is not None:
            response = _overlimit_response_bytes(overlimit_sha256)
        else:
            assert raw_line is not None
            response = response_bytes(raw_line)
        _write_all(sink, response)
        sink.flush()


def main() -> int:
    return serve(sys.stdin.buffer, sys.stdout.buffer)


if __name__ == "__main__":
    raise SystemExit(main())
