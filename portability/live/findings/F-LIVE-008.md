# F-LIVE-008 — bulk-write syscall partition counts made replays flaky

Status: **RESOLVED locally.** The exact failure reproduced in consecutive
suite runs; the correction is pinned by stable paired replays and a zero
ordinary-short-count assertion.

## Minimized evidence

`multi_response_buffering.ndjson` produced identical 106,372 response bytes,
exit status, flush count, and schedule acknowledgements on two pipe replays,
but `os_short_write_count` varied (observed pairs included 10/5 and 5/30).
`RunResult.stable_bytes()` included that host-scheduling-dependent count, so
`test_two_replays_are_byte_identical` and the replay CLI intermittently
classified a correct transport result as a divergence.

## Correction

For ordinary bulk schedules, a nonblocking EAGAIN or partial write now emits
the same genuine `backpressure` barrier and the adapter completes that one
write call in blocking mode before returning its full length to `rr_batch`.
The real pipe/socket may still segment the bytes internally, but incidental OS
syscall partitions no longer alter the declared replay transcript. The
controlled W path is unchanged: it remains the only path that deliberately
returns a short count to `rr_batch`, and all 812 acknowledged W partitions
remain explicit.

## Validation

The multi-response regression now requires all 131 responses, the exact
106,372-byte ordered output, genuine backpressure, and zero ordinary
`os_short_write_count`. The lane still runs every schedule twice on pipes and
socketpairs and compares the complete stable result.
