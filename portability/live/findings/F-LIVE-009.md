# F-LIVE-009 — peer-close race broke byte-identical replay on a hosted runner

Status: **RESOLVED; confirmed by the green hosted runs** — portability
run 31562391384 (`7facfa3`) and the close-push run 31564942933
(`55297bb`) passed every job containing this regression.

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

Correction (as hardened by the author-separated review): exactly
`BrokenPipeError`, `ConnectionResetError`, and `ConnectionAbortedError` are
translated into an internal `_PeerCloseAbort` sentinel ONLY at the physical
data endpoints — the data sink's OS write and the data source's OS read —
because exception class alone cannot establish which endpoint raised. The
worker's serve boundary catches only the sentinel, emits one deliberately
field-free `transport_abort` control event, and exits with the fixed code 5,
so both replays produce identical deterministic evidence. A raw
connection-abort class arriving from anywhere else (boundary-control,
stderr-control, harness code), and every other exception including plain
`OSError`, propagates unchanged: a harness defect is never laundered into
transport-abort evidence (F-LIVE-005/F-LIVE-007 doctrine). The controller
validates the new event as field-free.

Regression pins: `live/test_live.py`
`WorkerPeerCloseAbortTests.test_peer_close_abort_is_deterministic_and_never_launders_faults`
(sentinel exit path; propagation of all three raw abort classes plus
`ValueError` and plain `OSError`) and
`test_only_physical_data_endpoints_translate_peer_close` (sink-write and
source-read translation). The suite is 31/31.

The accepted implementation is unchanged; the defect was in the harness's
replay-identity projection.
