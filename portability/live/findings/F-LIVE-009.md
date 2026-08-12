# F-LIVE-009 — peer-close race broke byte-identical replay on a hosted runner

Status: **RESOLVED locally; hosted rerun pending at the corrective SHA.**

In hosted run 31549925307 (SHA `00479e6`), the normative
`cpython-3.12-windows-latest-x64` job failed
`test_two_replays_are_byte_identical` for `broken_pipe.ndjson` on the
socketpair transport. The two replays' stable bytes differed only inside the
worker's captured stderr: each embedded the accepted server's unhandled
traceback, and the peer-initiated close surfaced at a different
`rr_batch.serve` frame per replay (the physical-read line in one, the
`_write_all` line in the other). The same case passed on windows-latest
3.13/3.14, windows-11-arm 3.12/3.13/3.14, ubuntu, macos, and locally —
the race window is real but narrow.

Root cause: which accepted-server syscall first observes a peer-initiated
connection abort is kernel-scheduled, not schedule-determined. Embedding the
resulting traceback (frames, line numbers, exception subclass) in the
worker's stderr placed a kernel-race artifact inside replay identity. This is
the same doctrine as F-LIVE-008, which removed incidental
`os_short_write_count` partitions from replay identity.

Correction: the worker wraps the accepted server with a peer-close abort
boundary catching exactly `BrokenPipeError`, `ConnectionResetError`, and
`ConnectionAbortedError`. It emits one deliberately field-free
`transport_abort` control event and exits with the fixed code 5, so both
replays produce identical deterministic evidence. Every other exception —
including any other `OSError` — propagates unchanged: a harness defect is
never laundered into transport-abort evidence (F-LIVE-005/F-LIVE-007
doctrine). The controller validates the new event as field-free.

Regression pin: `live/test_live.py`
`WorkerPeerCloseAbortTests.test_peer_close_abort_is_deterministic_and_never_launders_faults`
covers all three abort classes, the fixed exit code, the bare control event,
and non-laundering for `ValueError` and plain `OSError`. The suite is 30/30.

The accepted implementation is unchanged; the defect was in the harness's
replay-identity projection.
