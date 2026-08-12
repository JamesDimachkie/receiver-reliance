"""Versioned, request-bound binary frames for the anonymous stdio sidecar.

The header is ASCII and LF terminated.  It is followed by exactly the declared
number of opaque payload bytes; payloads are never line delimited.  Digests are
SHA-256 over the complete payload bytes.

Request::

    RR-SIDECAR/1 REQUEST <sequence> <payload-bytes> <payload-sha256>\n
    <payload>

Response::

    RR-SIDECAR/1 RESPONSE <sequence> <request-sha256> <payload-bytes>
    <payload-sha256>\n
    <payload>

The exact single-space grammar is intentional.  It makes every accepted
header canonical without depending on JSON parsing, locale, or platform I/O
behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import BinaryIO, Callable


PROTOCOL = b"RR-SIDECAR/1"
REQUEST = b"REQUEST"
RESPONSE = b"RESPONSE"
MAX_HEADER_BYTES = 256
MAX_SEQUENCE = (1 << 63) - 1
_SHA256_RE = re.compile(rb"[0-9A-F]{64}\Z")


class EnvelopeError(ValueError):
    """A transport frame is incomplete, noncanonical, or digest-invalid."""


@dataclass(frozen=True)
class RequestHeader:
    sequence: int
    payload_bytes: int
    payload_sha256: str


@dataclass(frozen=True)
class ResponseFrame:
    sequence: int
    request_sha256: str
    payload: bytes
    payload_sha256: str


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def _decimal(raw: bytes, label: str, maximum: int) -> int:
    if not raw or not raw.isdigit() or (len(raw) > 1 and raw.startswith(b"0")):
        raise EnvelopeError(f"{label} is not canonical decimal")
    value = int(raw)
    if value < 1 or value > maximum:
        raise EnvelopeError(f"{label} is outside the supported range")
    return value


def _digest(raw: bytes, label: str) -> str:
    if _SHA256_RE.fullmatch(raw) is None:
        raise EnvelopeError(f"{label} is not canonical uppercase SHA-256")
    return raw.decode("ascii")


def _header_line(stream: BinaryIO) -> bytes | None:
    line = stream.readline(MAX_HEADER_BYTES + 1)
    if line == b"":
        return None
    if not isinstance(line, bytes):
        raise EnvelopeError("binary stream.readline() did not return bytes")
    if len(line) > MAX_HEADER_BYTES or not line.endswith(b"\n"):
        raise EnvelopeError("transport header is overlimit or unterminated")
    if b"\r" in line or b"\t" in line:
        raise EnvelopeError("transport header contains noncanonical whitespace")
    return line[:-1]


def encode_request_frame(sequence: int, payload: bytes) -> bytes:
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if not payload:
        raise ValueError("payload must not be empty")
    if sequence < 1 or sequence > MAX_SEQUENCE:
        raise ValueError("sequence is outside the supported range")
    digest = sha256(payload)
    header = b" ".join(
        (PROTOCOL, REQUEST, str(sequence).encode("ascii"), str(len(payload)).encode("ascii"), digest.encode("ascii"))
    ) + b"\n"
    return header + payload


def encode_response_frame(sequence: int, request_sha256: str, payload: bytes) -> bytes:
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if not payload:
        raise ValueError("payload must not be empty")
    if sequence < 1 or sequence > MAX_SEQUENCE:
        raise ValueError("sequence is outside the supported range")
    request_digest = _digest(request_sha256.encode("ascii"), "request_sha256")
    payload_digest = sha256(payload)
    header = b" ".join(
        (
            PROTOCOL,
            RESPONSE,
            str(sequence).encode("ascii"),
            request_digest.encode("ascii"),
            str(len(payload)).encode("ascii"),
            payload_digest.encode("ascii"),
        )
    ) + b"\n"
    return header + payload


def read_request_header(stream: BinaryIO) -> RequestHeader | None:
    line = _header_line(stream)
    if line is None:
        return None
    fields = line.split(b" ")
    if len(fields) != 5 or fields[:2] != [PROTOCOL, REQUEST]:
        raise EnvelopeError("expected a version-1 request header")
    sequence = _decimal(fields[2], "sequence", MAX_SEQUENCE)
    payload_bytes = _decimal(fields[3], "payload_bytes", MAX_SEQUENCE)
    return RequestHeader(sequence, payload_bytes, _digest(fields[4], "payload_sha256"))


def read_exact(
    stream: BinaryIO,
    size: int,
    *,
    retain_limit: int | None = None,
) -> tuple[bytes | None, str]:
    """Read and hash exactly ``size`` bytes, optionally retaining a prefix-bounded payload.

    If ``size`` exceeds ``retain_limit``, no payload bytes are retained and the
    first chunks are released as soon as the limit is crossed.  The returned
    digest always covers the complete declared payload.
    """
    if size < 1:
        raise EnvelopeError("payload_bytes must be positive")
    retain = retain_limit is None or size <= retain_limit
    chunks: list[bytes] = []
    remaining = size
    digest = hashlib.sha256()
    while remaining:
        chunk = stream.read(min(64 * 1024, remaining))
        if chunk == b"":
            raise EnvelopeError("EOF inside transport payload")
        if not isinstance(chunk, bytes):
            raise EnvelopeError("binary stream.read() did not return bytes")
        if len(chunk) > remaining:
            raise EnvelopeError("binary stream.read() exceeded the requested bound")
        digest.update(chunk)
        if retain:
            chunks.append(chunk)
        remaining -= len(chunk)
    return (b"".join(chunks) if retain else None), digest.hexdigest().upper()


def read_response_frame(stream: BinaryIO, max_payload_bytes: int) -> ResponseFrame | None:
    if max_payload_bytes < 1:
        raise ValueError("max_payload_bytes must be positive")
    line = _header_line(stream)
    if line is None:
        return None
    fields = line.split(b" ")
    if len(fields) != 6 or fields[:2] != [PROTOCOL, RESPONSE]:
        raise EnvelopeError("expected a version-1 response header")
    sequence = _decimal(fields[2], "sequence", MAX_SEQUENCE)
    request_digest = _digest(fields[3], "request_sha256")
    payload_bytes = _decimal(fields[4], "payload_bytes", max_payload_bytes)
    declared_payload_digest = _digest(fields[5], "payload_sha256")
    payload, observed_payload_digest = read_exact(stream, payload_bytes)
    assert payload is not None
    if observed_payload_digest != declared_payload_digest:
        raise EnvelopeError("response payload SHA-256 did not match its header")
    return ResponseFrame(sequence, request_digest, payload, observed_payload_digest)


def write_all(
    sink: BinaryIO,
    data: bytes,
    *,
    max_chunk_bytes: int | None = None,
    after_write: Callable[[], None] | None = None,
) -> int:
    """Write every byte, accepting short writes and rejecting zero progress."""
    if max_chunk_bytes is not None and max_chunk_bytes < 1:
        raise ValueError("max_chunk_bytes must be positive or None")
    view = memoryview(data)
    offset = 0
    calls = 0
    while offset < len(view):
        stop = len(view)
        if max_chunk_bytes is not None:
            stop = min(stop, offset + max_chunk_bytes)
        written = sink.write(view[offset:stop])
        calls += 1
        if after_write is not None:
            after_write()
        if written is None or written == 0:
            raise BlockingIOError("binary sink.write() made no progress")
        if type(written) is not int or written < 0 or written > stop - offset:
            raise OSError(f"binary sink.write() returned invalid byte count: {written!r}")
        offset += written
    return calls
