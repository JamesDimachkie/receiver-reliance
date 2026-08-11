# F-LIVE-003 — decoded non-object control records escaped the stop protocol

Status: **RESOLVED locally.** Correction retained in the terminal 29/29
focused suite. This was a live-harness
control-boundary and evidence-durability defect, not an
accepted-implementation divergence. Found by fresh R-LIVE-3 on 2026-08-10.

## Minimized evidence

The exact nine-byte record below has SHA-256
`1A6E0C12703BFD27ABF28E8F76820E3EFD426ABC998483885FAC5FE04CA0B115`:

```text
RRCTL []\n
```

Before correction, `_ControlMonitor._consume()` accepted every successfully
decoded JSON value and appended the list to `events`. `wait_for("ready")`
then evaluated `event.get(...)` and escaped with:

```text
events= [[]]
AttributeError: 'list' object has no attribute 'get'
```

Because `replay.py` classifies only `DivergenceError` and `TransportError`, the
bare `AttributeError` produced neither divergence evidence nor the canonical
F-LIVE-002 infrastructure-stop receipt. JSON object duplicate members,
non-finite values, recursive shapes, oversized records, unknown events, extra
fields, and event-field type confusion were adjacent forms of the same
unvalidated trust boundary.

## Correction

- A child control record is limited to 4,096 bytes including its required LF.
  Oversized records are drained in bounded reads so the producer cannot remain
  blocked on stderr.
- JSON decoding rejects duplicate members, non-finite constants, invalid UTF-8
  or JSON, recursion failures, and non-object roots.
- The decoded object must match exactly one event schema emitted by
  `worker.py`: `ready`, `flush`, `backpressure`, `short_write`,
  `unexpected_os_short_write`, `write_boundary`, or `write_resumed`. Required
  fields, exact Python value types, bounded integers, and the write-boundary
  relationships are checked before the event enters monitor state.
- The first invalid record is sticky. `wait_for()`, `count()`, and `finish()`
  raise `TransportError` with deterministic text. A replay therefore exits 2
  as `INFRASTRUCTURE_ERROR` and writes the existing canonical
  `receiver-reliance-live-infrastructure-error-v1` receipt.
- Non-control stderr is unchanged. Schedule syntax, implementation-divergence
  classification, PASS comparisons, W-domain meaning, and worker data bytes
  are unchanged.

## Validation

The exact witness now yields:

```text
TransportError: invalid child control record: object required
```

The canonical replay regression uses `half_close.ndjson` (SHA-256
`857D5B2B11914F5E836B4E40667EFC405C5B627375E9BCDEFA11A1489D1CA476`)
and produces receipt SHA-256
`6ED489E9082027197F876C7378A8E3A7AD2482BEAF17E8191D2362E5CAB857EA`.
It records `classification=INFRASTRUCTURE`,
`status=INFRASTRUCTURE_ERROR`, `error.type=TransportError`, and the exact
deterministic reason above.

The focused suite passes 29/29. It covers the minimized monitor witness, the
hostile adjacent record classes, every accepted event schema, and canonical
CLI evidence. F-LIVE-004 adds the adjacent monitor-stream exception boundary.
The class setup also replays all eight committed schedules twice on both real
transports and retains the complete 812-partition W assertions. This is bounded
child-control validation, not a general JSON protocol or hostile-child security
claim.
