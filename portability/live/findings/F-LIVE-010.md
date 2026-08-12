# F-LIVE-010 — fault-schedule replay identity bound death-racy fields

Status: **RESOLVED locally; hosted rerun pending at the corrective SHA.**

In hosted run 31553920699 (SHA `254b248`), the normative
`cpython-3.14-windows-latest-x64` job failed
`test_two_replays_are_byte_identical` for `child_kill.ndjson` on socketpair:
the two replays' stable bytes differed only in `flush_count` (8 versus 7).
The same case passed on the other fourteen normative targets and locally.

Root cause: `child_kill.ndjson` writes a batch, waits for the
backpressure barrier, then kills the child. Between that barrier and the
kill signal landing, the child may complete additional per-response `flush`
control events; how many is a race between signal delivery and child
progress — kernel-scheduled, not schedule-determined. The same class covers
the stop path itself: an aborting child may exit through the orderly
`transport_abort` path (exit 5) or be reaped, and its stderr control tail
truncates at the death instant. Binding any of these in replay identity
makes byte-identical replay claim determinism over a kill race — the same
doctrine violation corrected for `os_short_write_count` (F-LIVE-008) and
traceback frames (F-LIVE-009).

Correction: `RunResult` carries `fault_schedule`, true exactly when the
schedule's terminal action is asynchronous (kill, or full close during
observed backpressure — the runner's existing `disruptive` classification).
For fault schedules, `stable_bytes()` excludes `returncode`, `flush_count`,
and the stderr stream from replay identity; the flag itself is part of
identity so the two receipt shapes can never alias, every schedule-driven
surface (data bytes, acknowledgments, barrier-synced counters) stays bound,
and `summary()` retains the excluded values as durable evidence. Orderly
schedules keep the full binding.

Regression pin: `live/test_live.py`
`FaultScheduleIdentityTests.test_fault_schedule_identity_excludes_death_racy_fields`.
The suite is 33/33.
