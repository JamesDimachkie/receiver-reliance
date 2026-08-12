#!/usr/bin/env python3
"""Versioned request-bound stdio launcher for the audited decision transport.

The process owns anonymous stdin/stdout only.  It accepts monotonically
sequenced transport frames, verifies each complete request payload digest,
computes the existing audited response, and returns a response frame bound to
that exact sequence and request digest.  It opens no listener.
"""
from __future__ import annotations

import pathlib
import sys
from typing import BinaryIO


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
GROUNDED = REPO / "grounded-0_4"
if str(GROUNDED) not in sys.path:
    sys.path.insert(0, str(GROUNDED))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import rr_batch  # noqa: E402
from transport_envelope import (  # noqa: E402
    EnvelopeError,
    encode_response_frame,
    read_exact,
    read_request_header,
    write_all,
)

# Bounded-work ceiling on a request header's declared payload size.  Within
# the ceiling an oversized engine request still receives its correlated
# ERR_LIMIT response (which requires draining and digesting the payload);
# beyond it the declaration itself is an envelope violation, so a header
# cannot commit this process to draining up to 2^63-1 bytes (F-WP5-006).
MAX_DECLARED_REQUEST_BYTES = 256 * 1024 * 1024


def serve(source: BinaryIO, sink: BinaryIO) -> int:
    """Serve complete, digest-verified request frames until clean header EOF.

    A malformed, truncated, duplicate, stale, or reordered frame terminates the
    stream with status 2 and emits no response for that frame.  Valid engine
    protocol errors remain ordinary audited response payloads.
    """
    expected_sequence = 1
    try:
        while True:
            header = read_request_header(source)
            if header is None:
                return 0
            if header.sequence != expected_sequence:
                raise EnvelopeError("request sequence was not the next monotonic value")
            if header.payload_bytes > MAX_DECLARED_REQUEST_BYTES:
                raise EnvelopeError("request payload declaration exceeds the drain ceiling")
            payload, observed_digest = read_exact(
                source,
                header.payload_bytes,
                retain_limit=rr_batch.rr_api.b1.MAX_INPUT_BYTES,
            )
            if observed_digest != header.payload_sha256:
                raise EnvelopeError("request payload SHA-256 did not match its header")
            if payload is None:
                response = rr_batch._overlimit_response_bytes(observed_digest)
            else:
                response = rr_batch.response_bytes(payload)
            frame = encode_response_frame(header.sequence, observed_digest, response)
            write_all(sink, frame)
            sink.flush()
            expected_sequence += 1
    except (EnvelopeError, BlockingIOError, BrokenPipeError, OSError, ValueError):
        return 2


def main() -> int:
    return serve(sys.stdin.buffer, sys.stdout.buffer)


if __name__ == "__main__":
    raise SystemExit(main())
