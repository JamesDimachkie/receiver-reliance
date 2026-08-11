# F-MATRIX-003 — canonical command IDs can carry forged execution evidence

Status: **RESOLVED locally.** Correction retained and covered by two
consecutive 44/44 focused passes. No hosted run has occurred.

## Minimized evidence

Start with a runnable normative `PASS` receipt whose `commands_planned` and
executed command IDs exactly match `plan.json`. Before correction, any executed
record could then substitute fields such as:

```json
{
  "id": "matrix-receipt-tests",
  "argv": ["/substituted/python", "-c", "pass"],
  "cwd": "baseline-run",
  "timeout_seconds": 1,
  "timed_out": false,
  "exit": 0,
  "elapsed_seconds": -1,
  "stdout_sha256": "not-a-hash",
  "stdout_bytes": -1,
  "suite_counts": {"checks": [-1]},
  "expected_counts": {},
  "expectation_mismatches": [],
  "resources": {"children_user_seconds": -1}
}
```

The old summary validator inspected only the ID, timeout flag, exit, and empty
mismatch list. With canonical IDs in order, it accepted the receipt as `PASS`.
The top-level `suite_counts` projection was also unchecked.

## Why this is invalid

Binding only command IDs does not bind the recorded result to the checked-in
command template. Corrupt or substituted artifact data could claim that a
different command, directory, or timeout ran, and malformed or negative
evidence could still keep the normative summary green.

## Local correction

- Every executed command now has an exact fail-closed schema. Its argv is
  matched to the checked-in template: literals and entry IDs are exact, the
  interpreter matches the environment record, and every `{temp}` expansion
  uses one absolute root while retaining the exact planned suffix.
- `cwd` and `timeout_seconds` must equal the plan. Elapsed time, byte counts,
  hashes, suite counts, exits, and resource observations have explicit types
  and nonnegative/finite ranges.
- `expected_counts` is plan-owned. `expectation_mismatches` is recomputed from
  the recorded suite counts, and top-level `suite_counts` is recomputed from
  the command records.
- Git, requested-environment, and executed-environment field groups now have
  closed schemas and basic internal consistency checks. PASS/divergence reason,
  proof, prefix, and stop-at-first-failure relationships are also checked.
- Adversarial regressions cover substituted argv/interpreter/temp paths, cwd,
  timeout, negative or malformed evidence, forged count expectations,
  resources, and top-level aggregation.

## Evidence boundary

These checks make a receipt structurally bound to the checked-in plan and
internally self-consistent. They do not make the JSON artifact an independent
attestation that the process ran. Stream hashes are metadata for comparing
recorded byte streams; because the streams are not embedded in the receipt,
hash syntax and byte counts cannot prove their contents.
