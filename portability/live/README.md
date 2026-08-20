# Live transport schedules

This lane runs the accepted `grounded-0_4/rr_batch.py` server unchanged in a
child process. The data path is either two real anonymous OS pipes or one real
full-duplex `socket.socketpair()`. `BytesIO` and other in-memory transport
substitutes are not used.

## Replay

```text
python -B portability/live/replay.py portability/live/schedules/half_close.ndjson
python -B portability/live/test_live.py
```

`replay.py` executes the named schedule twice on each transport and compares
the complete stdout bytes, stderr bytes, exit status, and normalized barrier
transcript. Its stdout is a compact deterministic JSON receipt with byte
lengths and SHA-256 hashes. On any mismatch with the isolated physical-line
result, or between replay 1 and replay 2, it stops and writes the smallest
available evidence beneath `portability/live/divergences/`.

Implementation divergence and transport infrastructure failure are separate
stop classes. A `DivergenceError` writes divergence evidence and exits 1 with
`status=DIVERGENCE`. A controller `TransportError` (including an error-only
watchdog, premature control-channel EOF, or control acknowledgement mismatch)
exits 2 with `status=INFRASTRUCTURE_ERROR` and
`classification=INFRASTRUCTURE`; it is never promoted to an implementation
divergence or a pass. Monitor-side pipe/socket read failures and binary-stream
close failures are normalized to the same stop class. Its canonical
`receiver-reliance-live-infrastructure-error-v1` receipt is stored under a
reason-addressed directory in `portability/live/infrastructure-errors/` with
the exact schedule and any fully completed earlier replay. The receipt
contains no time measurement, timestamp, retry, or timing-derived schedule
decision. Invalid schedule syntax remains a caller input error, not transport
or accepted-implementation evidence.

A third stop class covers the harness itself (F-LIVE-005). Transport
normalization is scoped to the monitor's physical `readline()`; any other
exception the monitor loop body raises is a programmer defect in this
controller, recorded durably as a sticky `HarnessFaultError` that outranks
transport labeling. `replay.py` exits 4 with `status=HARNESS_FAULT` and
`classification=HARNESS`, writing a canonical
`receiver-reliance-live-harness-fault-v1` receipt under
`portability/live/harness-faults/`. A harness fault is never infrastructure,
divergence, or pass evidence; it invalidates the run and demands a controller
correction. `KeyboardInterrupt` and `SystemExit` are stored verbatim at the
monitor thread boundary and re-raised from the caller's next consultation;
they remain unrecorded and are never relabeled as harness or transport
evidence (F-LIVE-007).

The child control channel is a separate, bounded protocol boundary. A control
record is at most 4,096 bytes including LF, must decode to an exact JSON object
with one of the worker's declared event schemas, and may not contain duplicate
members, non-finite numbers, unknown events, extra fields, or type-confused
field values. The first invalid control record or expected control-stream I/O
failure is sticky: event waits, counts, and finalization raise `TransportError`,
so `replay.py` preserves the same canonical infrastructure-stop evidence
instead of treating malformed control data as stderr or allowing a
monitor-thread traceback to escape. The I/O boundary catches only `OSError`
(normalized across host-specific subclasses) and the closed-stream
`ValueError`; it does not relabel `KeyboardInterrupt`, `SystemExit`, or
programmer defects. Ordinary non-control stderr remains ordinary stderr.

## Barrier law

Schedule actions never sleep, poll, or select behavior from elapsed time.
Each action acknowledges its unique `barrier` only after the corresponding OS
operation completes. `backpressure-observed` is stronger: the child first
attempts a nonblocking write on the real endpoint, emits an acknowledgement
only after the OS returns EAGAIN, then performs a blocking retry that can make
progress only when the schedule reads or closes the endpoint. The 30-second
limit in the controller is an error-only deadlock watchdog, not a schedule
transition or pass criterion.

`pause_every_byte.ndjson` is a compact, deterministically expanded
representation of the complete `W <= 2` domain for the first 1,212-byte
response. The expansion executes 1,212 request/response trials in one child:
one unsplit write and every two-write partition `[0,k),[k,1212)` for
`1 <= k < 1212`.

For each trial, the adapter limits its first real pipe/socket write to `k`
bytes and reports the completed OS write on the control channel. The reader is
paused until that `write_boundary` acknowledgement arrives. It then resumes,
reads exactly the acknowledged prefix from the real data endpoint, and sends a
matching `resume_write` acknowledgement. Only then may the child issue the
suffix. Thus the accepted server observes 1,211 actual short `sink.write`
returns, rather than the controller inferring sender partitions from one-byte
reads of already-buffered output. The unsplit case is also gated and
acknowledged, giving 1,212 W partitions, pauses, resumes, write-boundary
events, and writer-resume events per transport run.

The W control gate is deliberately not reported as OS `EAGAIN` backpressure:
its receipt has `backpressure_observed: false` and separate
`write_boundary_count`, `forced_short_write_count`, and
`write_resume_ack_count` fields. `os_short_write_count` must remain zero in W,
which proves no unplanned third segment expanded a declared two-write case.
The three adversarial bulk-output schedules continue to require and report
genuine nonblocking OS backpressure. In those ordinary bulk schedules, EAGAIN
and a nonblocking partial write both acknowledge that barrier; the adapter then
finishes the current call in blocking mode. This keeps incidental kernel
syscall partition counts out of the declared replay transcript while the W
path remains the only deliberate short-return surface (F-LIVE-008).

## Schedule inventory

| File | Fault / invariant exercised |
|---|---|
| `pause_every_byte.ndjson` | Complete `W <= 2`: one unsplit write plus every first-response two-write split, with an acknowledged reader pause/resume at each boundary |
| `half_close.ndjson` | Client input half-close while retaining the response direction |
| `full_close.ndjson` | Orderly full close after one flushed response |
| `broken_pipe.ndjson` | Verified OS backpressure followed by output-peer closure |
| `child_kill.ndjson` | Verified OS backpressure followed by child termination |
| `delayed_flush.ndjson` | Record completion delayed across a barrier; response read before EOF |
| `partial_final_eof.ndjson` | Non-LF-terminated final request processed at EOF |
| `multi_response_buffering.ndjson` | 131 responses, verified OS backpressure, exact ordered drain |

The controller's expected bytes are isolated invocations of the same accepted
physical-line surface. Independent semantic expectations and cross-platform
relations belong to `portability/oracle/`; this lane makes no independence
claim for that local transport-parity comparison.

The focused lane suite currently passes 33/33 tests. In addition to replaying
all eight committed schedules twice on both real transports, it directly
forces the watchdog, premature control EOF, and mismatched-control-event error
paths and verifies their deterministic CLI receipts and exit classification,
plus the F-LIVE-005 harness-fault classification witnesses, F-LIVE-006
full-digest evidence-identity distinctness, F-LIVE-007 exact cross-thread
`BaseException` propagation, and F-LIVE-008 stable bulk-write replay boundary.
It also pins the exact non-object witness; forces read failure both before and
after a valid event; checks first-failure stickiness and close failure; and
rejects duplicate-member, non-finite, malformed, deeply nested, oversized,
unknown-event, extra-field, and field-type-confusion control records without
widening the live lane into a general JSON-protocol claim.
