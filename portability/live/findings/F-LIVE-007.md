# F-LIVE-007 — BaseException vanished at the monitor thread boundary

Status: **RESOLVED locally.** The exact `KeyboardInterrupt` and `SystemExit`
objects now cross the background-thread boundary and are regression-pinned in
the terminal 29/29 focused suite.

## Minimized evidence

F-LIVE-005 stated that a loop-body `BaseException` propagated and remained
outside transport or harness evidence. In a background thread it could not
propagate to the caller. Injecting `SystemExit` or `KeyboardInterrupt` killed
`rr-live-control`; a later `wait_for("ready")` instead raised
`TransportError("child exited before event 'ready'")`. A replay could therefore
durably misclassify a deliberate non-`Exception` abort as infrastructure.

## Correction

`_ControlMonitor` stores the first loop-body `BaseException` verbatim under the
same condition lock used by its other sticky outcomes. Every public
consultation checks that slot first and re-raises the identical object in the
caller thread. The pre-ready spawn boundary reaps the child before re-raising,
so exact propagation cannot leak a process. The abort is never converted to
`TransportError`, `HarnessFaultError`, or a receipt. Ordinary `Exception`
values retain the F-LIVE-005 durable harness classification.

## Validation

The existing monitor-fault regression now covers `TypeError`,
`KeyboardInterrupt`, and `SystemExit` without increasing the suite count. For
each non-`Exception` case it asserts object identity on re-raise from
`wait_for`, `count`, and `finish`, empty transport/harness slots, and no call to
`threading.excepthook`. The same test requires the pre-ready boundary to kill
and wait for its child before re-raising the exact abort.
