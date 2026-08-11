# F-SANDBOX-003 — evidence-free inner PASS is accepted

Status: **RESOLVED locally.** Correction retained; final focused suite green.

Before correction, the exact host flow accepted container exit 0 plus inner
stdout:

```json
{"status":"PASS"}
```

and emitted host `PASS`/exit 0. It did not require the inner receipt schema,
treatment-exposed flag, effective-boundary proof, all eleven gate
commands/counts, or a recomputable deterministic projection. Thus a malformed,
truncated, or dishonest inner process could promote an evidence-free PASS.

The local daemon-unavailable path was already honestly bound and classified.
The defect was in parsing a future live container result. The required
correction was to make PASS fail closed unless the complete inner receipt
validated, with negative coverage for missing fields, wrong counts/commands,
boundary failure, wrong projection, and nonzero exit.

The correction validates one canonical JSON record against exact nested keys
and types, requires the treatment flag and effective boundary values, matches
all eleven ordered command identities and their declared count evidence,
requires zero command exits/timeouts plus stream hashes, byte counts, and
resource observations, and recomputes the deterministic projection on the
host. Any discrepancy, including container nonzero exit, now yields host
`INVALID_CONTAINER_RECEIPT`/exit 1. Static adversarial tests cover each class
and include one complete synthetic PASS receipt as a positive control.
