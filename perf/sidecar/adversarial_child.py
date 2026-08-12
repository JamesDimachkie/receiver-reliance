#!/usr/bin/env python3
"""Small stdlib-only protocol adversary used by ``test_sidecar.py``."""
from __future__ import annotations

import hashlib
import os
import pathlib
import sys
import time


HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from transport_envelope import (  # noqa: E402
    encode_response_frame,
    read_exact,
    read_request_header,
    write_all,
)


def read_request() -> tuple[int, str, bytes]:
    header = read_request_header(sys.stdin.buffer)
    if header is None:
        raise EOFError
    payload, observed = read_exact(sys.stdin.buffer, header.payload_bytes)
    assert payload is not None
    if observed != header.payload_sha256:
        raise ValueError("bad test request digest")
    return header.sequence, observed, payload


def raw_response_header(sequence: int, request_digest: str, payload: bytes, payload_digest: str) -> bytes:
    return (
        f"RR-SIDECAR/1 RESPONSE {sequence} {request_digest} {len(payload)} {payload_digest}\n".encode("ascii")
        + payload
    )


def main() -> int:
    mode = sys.argv[1]
    if mode == "prewrite-poison":
        os.write(1, b"POISON\n")
        time.sleep(5)
        return 0
    if mode == "midwrite-poison":
        os.read(0, 1)
        os.write(1, b"POISON\n")
        while os.read(0, 64 * 1024):
            pass
        time.sleep(5)
        return 0

    if mode == "stall":
        marker = pathlib.Path(sys.argv[2])
        if len(sys.argv) >= 4:
            # Readiness signal: interpreter is up and about to read.  The
            # harness polls this before issuing its deliberately short
            # request, so the child's cold start is never charged against
            # the request deadline (F-WP5-007 test-race repair).
            pathlib.Path(sys.argv[3]).write_bytes(b"R")
        read_request()
        marker.write_bytes(marker.read_bytes() + b"1")
        time.sleep(5)
        return 0
    if mode == "midwrite-valid":
        # Emit the CORRECT correlated response after the first request byte
        # lands, while the host is still chunking its write, then drain the
        # remainder.  Identity comes from the envelope digest (the expected
        # request bytes are supplied out of band), never from consumption.
        expected_line = pathlib.Path(sys.argv[2]).read_bytes()
        digest = hashlib.sha256(expected_line).hexdigest().upper()
        os.read(0, 1)
        frame = encode_response_frame(1, digest, b"OK\n")
        write_all(sys.stdout.buffer, frame)
        sys.stdout.buffer.flush()
        while os.read(0, 64 * 1024):
            pass
        time.sleep(0.2)
        return 0

    sequence, request_digest, _payload = read_request()
    if mode == "postwrite-poison":
        os.write(1, b"POISON\n")
        time.sleep(5)
        return 0
    if mode == "valid":
        frame = encode_response_frame(sequence, request_digest, b"OK\n")
        write_all(sys.stdout.buffer, frame)
        sys.stdout.buffer.flush()
        time.sleep(0.2)
        return 0
    if mode == "duplicate":
        first = encode_response_frame(sequence, request_digest, b"ONE\n")
        second = encode_response_frame(sequence, request_digest, b"TWO\n")
        os.write(1, first + second)
        time.sleep(5)
        return 0
    if mode == "future-sequence":
        os.write(1, encode_response_frame(sequence + 1, request_digest, b"FUTURE\n"))
        time.sleep(5)
        return 0
    if mode == "wrong-request-digest":
        wrong = hashlib.sha256(b"different request").hexdigest().upper()
        os.write(1, encode_response_frame(sequence, wrong, b"WRONG\n"))
        time.sleep(5)
        return 0
    if mode == "wrong-response-digest":
        payload = b"CORRUPT\n"
        wrong = hashlib.sha256(b"different response").hexdigest().upper()
        os.write(1, raw_response_header(sequence, request_digest, payload, wrong))
        time.sleep(5)
        return 0
    if mode == "stale-second":
        first_request = (sequence, request_digest)
        os.write(1, encode_response_frame(sequence, request_digest, b"FIRST\n"))
        sequence2, _request_digest2, _payload2 = read_request()
        assert sequence2 == sequence + 1
        os.write(1, encode_response_frame(first_request[0], first_request[1], b"STALE\n"))
        time.sleep(5)
        return 0
    if mode == "eof-live":
        os.close(1)
        time.sleep(5)
        return 0
    if mode == "stderr-whitespace":
        os.write(2, b" \n\t")
        time.sleep(5)
        return 0
    if mode == "stderr-long":
        os.write(2, b"P" * 5000 + b"TAIL")
        time.sleep(5)
        return 0
    if mode == "overlimit-response":
        os.write(1, encode_response_frame(sequence, request_digest, b"12345"))
        time.sleep(5)
        return 0
    raise ValueError(f"unknown adversary mode: {mode}")


if __name__ == "__main__":
    raise SystemExit(main())
