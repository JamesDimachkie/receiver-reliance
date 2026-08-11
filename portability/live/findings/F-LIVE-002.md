# F-LIVE-002 — transport failures escaped without durable stop evidence

Status: **RESOLVED locally.** Correction retained in the terminal 29/29
focused suite. This was a live-harness
evidence-durability defect, not an accepted-implementation divergence.

## Minimized evidence

`controller.py` deliberately raises `TransportError` for error-only watchdogs,
premature child/control-channel EOF, unavailable control endpoints, transport
write/read failure, and mismatched W acknowledgements. Before this correction,
`replay.py` caught only `DivergenceError`. Replacing `run_schedule` with the
following deterministic failure therefore let the exception escape and wrote
no receipt or preserved schedule:

```text
TransportError: watchdog waiting for child event
```

The same unsupported path applied to a child exiting before an expected
control event and to a control acknowledgement whose response index, split,
or byte fields did not match the armed W boundary. The controller prose called
the watchdog an infrastructure error, but the executable replay surface had no
durable infrastructure classification.

## Correction

- `TransportError.status` is explicitly `INFRASTRUCTURE_ERROR`, distinct from
  `DIVERGENCE`.
- `replay.py` catches that class on either replay, writes a canonical
  `receiver-reliance-live-infrastructure-error-v1` receipt, preserves the exact
  schedule and any fully completed first replay, emits the receipt hash, and
  exits 2 without retry.
- Evidence directories are addressed by schedule, transport, replay number,
  and the deterministic error identity. The receipt contains no clock,
  timestamp, duration, or timing-derived transition.
- The success/divergence path is unchanged. Invalid schedule syntax is still a
  caller input error and cannot be misclassified as transport evidence.

The focused suite now passes 29/29 tests. Direct and CLI regressions cover the
mocked watchdog, premature control EOF, and mismatched W acknowledgement, plus
failure on replay two with the first replay's bytes and stable hash retained.
All eight schedules still replay twice on both real pipes and socketpairs, and
the complete 812-partition W assertions remain green. F-LIVE-003 separately
corrects malformed child-control records and F-LIVE-004 corrects monitor-side
I/O exceptions at the same trust boundary. Both use this finding's existing
canonical infrastructure receipt path rather than introducing another stop
class.

The current local disposition is closed; hosted execution remains separate.
