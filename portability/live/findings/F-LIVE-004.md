# F-LIVE-004 — monitor read failures escaped after valid control events

Status: **corrected; fresh refutation required**. This was a live-harness
failure-classification and evidence-durability defect, not an
accepted-implementation divergence. Found by fresh R-LIVE-4 on 2026-08-10.

## Minimized evidence

The deterministic stream first returns this 43-byte valid control record
(SHA-256
`D6B44EE0CF6733FAA8A8065B83B3BDEFF77BF2554C934B80DDF354A1643C53FD`):

```text
RRCTL {"event":"ready","transport":"pipe"}\n
```

Its second `readline()` raises
`OSError("deterministic control read failure after valid event")`. Before the
correction, `wait_for("ready")` returned the valid event and `finish()` also
returned. The exception existed only as an unbound `rr-live-control` thread
traceback. The same boundary laundered a read failure before the first event:
the consumer became `finished`, so a caller received the misleading
`child exited before event` reason instead of the causal stream failure.

## Correction

- `_ControlMonitor` catches the expected binary-control-stream failures:
  `OSError` for pipe/socket I/O and `ValueError` for an already-closed Python
  binary stream. Host-specific `OSError` subclasses normalize to the stable
  text `OSError`.
- The first protocol or stream failure becomes one condition-protected,
  sticky `TransportError`. A later read or close failure cannot overwrite a
  prior malformed-record reason.
- `wait_for()`, `count()`, and `finish()` consult the sticky failure before
  returning evidence. `finish()` also normalizes an expected stream-close
  failure; spawn cleanup preserves the original causal failure.
- The boundary deliberately does not catch `BaseException` generally.
  `KeyboardInterrupt`, `SystemExit`, and unexpected programmer defects are not
  recast as transport evidence.
- `replay.py` needs no new stop schema: the corrected failure reaches the
  F-LIVE-002 canonical `INFRASTRUCTURE_ERROR` receipt and exit 2. PASS and
  divergence paths are unchanged.

## Validation

Direct regressions cover a valid event followed by a gated read failure, a
failure before any event, first-error preservation after a malformed record,
and an `OSError` during close. They assert no call to `threading.excepthook`.
Both read-failure orders are also routed through the replay CLI. For
`half_close.ndjson`, pipe transport, replay 1, the canonical read-failure
receipt has SHA-256
`85714A2FF02A7394076C21EAE6B3AE2E33EB982A6A7904D5EA59C65B21474B57`
and records `classification=INFRASTRUCTURE`,
`status=INFRASTRUCTURE_ERROR`, `error.type=TransportError`, and
`error.message="control-channel read failure: OSError"`.

The focused suite passes 21/21. Its setup still replays all eight schedules
twice on both real pipe and socketpair transports, retains byte-identical PASS
results, and retains the complete 812-partition W assertions. This correction
does not claim arbitrary hostile-stream containment, timing independence
beyond the existing barrier protocol, or implementation behavior beyond the
declared live schedules.
