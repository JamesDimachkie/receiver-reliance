# F-LIVE-006 — stop-receipt identity allowed completed-evidence overwrite

Status: **corrected; fresh refutation required**. This was an
evidence-durability defect in both replay stop-receipt writers, not an
accepted-implementation divergence. Found by fresh refuter R-LIVE-5 on
2026-08-10 while attacking the first F-LIVE-005 author state.

## Minimized evidence

Both `_write_transport_error` and the new `_write_harness_fault` derived
the evidence directory identity from
`{error_type, reason, replay, schedule, transport}` only, with `schedule`
contributing just its basename. Two axes of genuinely different stops
therefore resolved to the same target directory:

- identical reasons with different completed first replays (stdout
  `first-A` versus `first-B`); and
- different schedule bytes sharing one basename (`a/same.ndjson` versus
  `b/same.ndjson`).

```text
same_target= True
receipt_bytes_differ= True
first_receipt_overwritten= True
```

In each case the later invocation overwrote the earlier evidence and
invalidated the earlier CLI-reported receipt hash at that evidence path.
The defect predates F-LIVE-005 in the infrastructure writer; the harness
writer inherited it by mirroring. The schedule-content axis was found by
R-LIVE-5's second pass against the first correction of this finding.

## Correction

The canonical identity input for both writers now includes the full
declared evidence: `completed_stable_sha256` (the ordered list of
completed-replay `RunResult.stable_bytes()` SHA-256 hashes) and
`schedule_sha256` (the SHA-256 of the schedule bytes, which the receipt
already recorded). Stops that differ in any completed-replay content or
schedule content land in distinct directories; fully identical stops
still deduplicate to one deterministic path. Receipt bytes are
unchanged — the identity feeds only the directory name — so previously
recorded receipt hashes (F-LIVE-004's `85714A2F...`, F-LIVE-005's
`FA634525...`) remain valid.

## Validation

Direct regressions drive both writers twice per axis — identical reasons
with differing completed first replays, and same-basename schedules with
differing bytes — and assert distinct target directories with both
receipts intact on disk. The focused suite passes 29/29. No clock,
randomness, retry, or environment dependence is introduced; the identity
remains a pure function of declared evidence.
