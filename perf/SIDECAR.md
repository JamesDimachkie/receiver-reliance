# Local anonymous-stdio sidecar

## Package boundary

`perf/sidecar/rr_sidecar.py` is a stdlib-only child process for the existing
audited `grounded-0_4/rr_batch.py` decision surface. It inherits anonymous
stdin/stdout, opens no socket or listener, reads no network configuration, and
keeps no request-derived state between decisions. One host application owns
one child and permits one request in flight.

The launcher adds a transport envelope, not decision logic. The caller still
passes exactly one LF-terminated physical engine request and receives exactly
the corresponding JCS+LF audited response payload.

## Version-1 transport envelope

The transport is an ASCII LF-terminated canonical header followed by exactly
the declared number of opaque payload bytes. Payloads are length framed, not
line framed.

```text
RR-SIDECAR/1 REQUEST <sequence> <request-bytes> <request-sha256>\n
<complete engine request bytes>

RR-SIDECAR/1 RESPONSE <sequence> <request-sha256> <response-bytes> <response-sha256>\n
<complete audited response bytes>
```

Sequences begin at 1 and increase by exactly one for the lifetime of a child.
Lengths use canonical positive decimal. Digests use 64 uppercase hexadecimal
characters and cover every payload byte, including the engine request's LF and
the audited response's LF.

The child reads and hashes the complete request payload before deciding. It
rejects a malformed header, truncated payload, length/digest mismatch, or any
duplicate, stale, or reordered request sequence by exiting 2 without a
response for that frame. Valid oversized engine requests remain ordinary
audited `ERR_LIMIT` response payloads because the child streams their complete
digest without retaining the overlimit body.

## Run and supervise

From the repository root:

```powershell
python -I -B perf/sidecar/rr_sidecar.py
```

Direct users must implement the frame grammar above. Application code should
normally use the reference owner:

```python
from perf.sidecar.supervised_client import SidecarProcess

request_jcs_lf = b'{"...":"one physical request"}\n'
with SidecarProcess(timeout_seconds=30.0) as sidecar:
    response_jcs_lf = sidecar.request(request_jcs_lf)
```

The client starts `python -I -B perf/sidecar/rr_sidecar.py` without a shell,
serializes callers, constructs transport frames, bounds response payloads, and
returns only the audited payload bytes. No listener is created on Windows,
Linux, or macOS; the process shape is the same redirected anonymous stdio
contract on each.

## Admission and failure semantics

A response is admitted only when all of these hold:

1. the complete request frame write and host flush have returned;
2. the response is a canonical version-1 frame;
3. its sequence is the exact next monotonic sequence;
4. its request digest equals SHA-256 of the complete request bytes;
5. its response length is within the caller's positive bound; and
6. its response digest equals SHA-256 of the complete received payload.

Phase state and queue timing are never evidence of identity, in either
direction: a complete frame that arrives while the host is still inside its
own write path is held — bounded by the caller's deadline — until the
lock-protected write completion, then judged purely by correlation
(F-WP5-007), and output observed while idle or after failure is rejected.
Raw `POISON`, whitespace, a future/stale/duplicate frame, either digest
mismatch, partial response, EOF, nonzero death, timeout, response overlimit,
and any stderr byte all fail closed and stop the child. Valid short writes are
completed; zero-progress and invalid write counts fail. There is no automatic
replay. A timeout after a completed write is an ambiguous outcome, and the
caller owns any later retry decision and idempotency policy.

Stderr evidence drains every byte with a bounded 1 MiB retention buffer:
`stderr_evidence()` reports `total_bytes`, `retained_bytes`, and
`sha256_scope`, so a digest over a truncated stream can never present as
complete (F-WP5-007). On the launcher side, a request header may declare at
most 256 MiB (`MAX_DECLARED_REQUEST_BYTES`): within the ceiling an
oversized engine request still receives its correlated `ERR_LIMIT`
response; beyond it the declaration itself is an envelope violation, so a
header cannot commit the process to draining arbitrary declared bytes
(F-WP5-006).

The default 32 MiB response-payload bound is host policy, not an engine limit.
Already returned audited responses are self-contained. Pools, routing,
queueing, cancellation, retry safety, resource controls, logging, and effects
remain host responsibilities. Scale by using independent one-host/one-child
pairs; never share one child's stdout among readers.

## Verification

```powershell
python -B perf/sidecar/test_sidecar.py
python -B perf/sidecar/verify_receipts.py
```

The admitted attempt-9 receipt records 728 passing checks: byte parity for all
124 committed semantic fixtures under one stable PID; a 16 MiB+1 engine
overlimit request; pre-, mid-, and post-write unsolicited output; a child that
reads one byte of a 1 MiB request then emits `POISON`; a child that emits
the CORRECT correlated frame mid-write, which must be admitted once the
write completes; short and zero writes; future, stale, duplicate, and
digest-invalid frames; EOF, death, timeout, response overlimit, raw stderr,
no replay, and thread/process cleanup — with the counted-timeout probe
gated on a child readiness signal so interpreter cold start is never
charged against the request deadline.

The receipt pins every repository regular file observed through Python `open`
audit events in the traced Python process tree. That is Python-audit-visible
repository-read custody only. It is not native or OS-wide I/O provenance and
does not observe native or non-Python child reads.

## Nonclaims

This package creates no security, authentication, availability,
interoperability, throughput, efficacy, external-standard, or universal
portability claim. The host remains responsible for `HOST_OBLIGATIONS.md`,
including effects, state truthfulness, deployment isolation, and retry policy.
