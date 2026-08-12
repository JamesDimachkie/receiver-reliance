# F-LIVE-011 — controller data-plane calls lacked the watchdog bound

Status: **RESOLVED locally (liveness bound); the hosted deadlock partner is
not yet established. Hosted rerun pending at the corrective SHA.**

In hosted run 31552953993 (SHA `baa7b20`), the normative
`cpython-3.13-macos-latest-arm64` job's live suite produced no output for
the full 900-second command timeout and was killed; the receipt records
exit `None` with no observed counts. The oracle suite had completed at
01:15:31 and nothing further printed, placing the stall inside the live
suite's schedule replays. The same suite passed on every other target in
that run and on all fifteen targets in the following run.

Established mechanism surface: every controller event wait, child reap, and
monitor join already carries `WATCHDOG_SECONDS`, but the data-plane OS calls
did not — socket `send`/`recv`/`sendall` and pipe `os.read`/`os.write`
could block without bound. A stall in any of them (for example a blocked
child send that a peer close fails to wake, which BSD-derived kernels have
historically exhibited) would present exactly as observed: silence until
the job-level timeout, with no witness.

What is deliberately NOT claimed: the single occurrence left no transcript,
so the exact deadlock partner on macos arm64 CPython 3.13 is not
established. This finding does not assert a root cause beyond the absence
of the bound.

Correction: the controller's socketpair endpoint and boundary-control
socket now carry `settimeout(WATCHDOG_SECONDS)` with `socket.timeout`
converted to a `TransportError` watchdog witness at every call site, and
POSIX pipe reads/writes are `select()`-gated with the same bound. A
recurrence therefore fails in at most 30 seconds with a minimized
`INFRASTRUCTURE_ERROR` witness naming the stalled call, instead of a
silent 900-second kill. Windows pipes cannot be `select()`-gated and retain
only the schedule-level reap watchdog; that residual is explicit.

Regression pin: `live/test_live.py`
`FaultScheduleIdentityTests.test_controller_transport_watchdog_bounds`.
The suite is 33/33.
