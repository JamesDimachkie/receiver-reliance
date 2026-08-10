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

import pathlib
import sys
from typing import BinaryIO

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import rr_api


def response_bytes(raw_line: bytes) -> bytes:
    """Return the existing one-shot audited response bytes for ``raw_line``."""
    return rr_api.b1.jcs_bytes(rr_api.decide_audited(raw_line)) + b"\n"


def serve(source: BinaryIO, sink: BinaryIO) -> int:
    """Consume one request per physical line until EOF.

    No state derived from a request is retained between iterations.  Flushing
    each response makes the same process usable by request/response clients,
    not only by clients that close stdin after sending a complete batch.
    """
    while True:
        raw_line = source.readline()
        if raw_line == b"":
            return 0
        sink.write(response_bytes(raw_line))
        sink.flush()


def main() -> int:
    return serve(sys.stdin.buffer, sys.stdout.buffer)


if __name__ == "__main__":
    raise SystemExit(main())
