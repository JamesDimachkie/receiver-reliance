# F-LIVE-005 — monitor body defects were laundered as transport evidence

Status: **RESOLVED locally after F-LIVE-007.** The terminal 29/29 suite binds
both ordinary exceptions and cross-thread `BaseException` propagation. This was
a live-harness failure-classification defect, not an accepted-implementation
divergence. Found by fresh refutation of the F-LIVE-004 author state on
2026-08-10; corrected by a fresh author after the Fable adjudication of the
same date. The first corrected state was itself REFUTED by fresh refuter
R-LIVE-5 (an exception whose own `__str__` raises escaped `_fail_harness`,
reproducing silent thread death and a misleading transport label), and
R-LIVE-5 then refuted the first hardening as well: a metaclass raising on
the `__name__` lookup escaped the fallback's repeated lookup. The current
renderer guards each lookup exactly once. R-LIVE-5's evidence-durability
findings are recorded separately as F-LIVE-006.

## Minimized evidence

The F-LIVE-004 catch wrapped the entire monitor consume loop, not just its
OS reads. Injecting `ValueError("injected monitor defect")` into
`_decode_control_record` while the stream held one valid 43-byte control
record produced a sticky `TransportError` with
`status=INFRASTRUCTURE_ERROR`: a controller programmer defect became
transport infrastructure evidence, reaching the canonical
infrastructure receipt and exit 2.

A second laundering path existed for every other exception type: an
injected `TypeError` in `_validate_control_event` escaped the
`(OSError, ValueError)` catch entirely, killed the `rr-live-control`
thread through `threading.excepthook`, and later waits surfaced the
misleading transport reason `child exited before event` instead of the
causal defect. F-LIVE-004's claim that programmer defects are not recast
as transport evidence therefore held only for exception types outside
`(OSError, ValueError)`, and those died without durable classification.

## Correction

- Transport normalization is scoped to the sole physical read:
  `_ControlMonitor._read_physical()` wraps only
  `stream.readline(MAX_CONTROL_RECORD_BYTES + 1)` and maps `OSError` and
  the deterministic closed-stream `ValueError` to the sticky
  `TransportError`, with the same normalized reason text as before.
- Every other `Exception` the loop body raises is recorded as a sticky
  `HarnessFaultError` (`status=HARNESS_FAULT`), a new class distinct from
  both divergence and infrastructure. `BaseException` is stored verbatim at
  the thread boundary and re-raised from the caller's next consultation:
  `KeyboardInterrupt` and `SystemExit` are neither transport nor harness
  evidence (F-LIVE-007).
- The fault detail is rendered before the condition lock is taken behind
  layered guards whose last resort is a constant that formats no foreign
  object: a failing type-`__name__` lookup renders as
  `<unprintable exception type>`, a failing `__str__` as
  `<unprintable fault detail>`, and a `__name__` that is itself a hostile
  `str` subclass raising on formatting as `<unprintable fault>` (R-LIVE-5
  witnesses). A successful f-string yields an exact `str`, so the recorded
  detail is inert, and exception matching dispatches on the real type, so a
  hostile metaclass cannot reach the guard clauses.
- A recorded harness fault outranks transport labeling at every consult
  point (`wait_for`, `count`, `finish`): once the monitor is defective,
  its transport claims are unreliable.
- Spawn cleanup reaps the child on a harness fault exactly as it does on
  a transport failure.
- `replay.py` writes a canonical
  `receiver-reliance-live-harness-fault-v1` receipt under
  `portability/live/harness-faults/` and exits 4 with
  `status=HARNESS_FAULT`, `classification=HARNESS`. The
  F-LIVE-002/F-LIVE-004 infrastructure receipt, divergence, and PASS
  paths are byte-unchanged.

## Validation

Direct regressions cover: the injected-`ValueError` witness (harness
fault, not transport; no `threading.excepthook` call), the
injected-`TypeError` witness (durably recorded instead of silent thread
death), the raising-`__str__` renderer witness (recorded as
`<unprintable fault detail>`, no `threading.excepthook` call), the
metaclass `__name__`-trap witness (recorded as
`<unprintable exception type>`, no `threading.excepthook` call), the
hostile-`str`-subclass `__name__` witness (recorded as
`<unprintable fault>`, no `threading.excepthook` call), the
closed-stream read (still transport-normalized to
`control-channel read failure: ValueError`), and the replay CLI
harness-fault receipt. For `half_close.ndjson`, pipe transport,
replay 1, the canonical harness-fault receipt has SHA-256
`FA63452507E8C7F6D7CD2DE3F9C3E3F2CBF5F99ED5DDAE860185D8F91D790614`
and records `classification=HARNESS`, `status=HARNESS_FAULT`,
`error.type=HarnessFaultError`. Cross-thread regressions inject the exact
`KeyboardInterrupt` and `SystemExit` objects and require `wait_for`, `count`,
and `finish` to re-raise those same objects without a thread-exception hook or
transport/harness classification. Receipt bytes exclude the evidence
directory name, so the F-LIVE-006 identity widening does not move this
hash.

The focused suite passes 29/29 (the prior 21, these seven, and the
F-LIVE-006 distinctness regression). Its setup
still replays all eight schedules twice on both real pipe and socketpair
transports with byte-identical PASS results and the complete
812-partition W assertions. This correction does not claim arbitrary
hostile-stream containment, timing independence beyond the existing
barrier protocol, or implementation behavior beyond the declared live
schedules.
