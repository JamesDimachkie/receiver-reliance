# F-MATRIX-009 — deeply nested receipt JSON escaped the fail-closed summary

Status: corrected locally on attempt 1/3 by fresh F-MATRIX-9 before the first
authorized push; awaiting author-separated refutation. No hosted run has
occurred.

## Minimized boundary evidence

The hostile receipt is the following 6,002-byte structural form, with 2,994
opening array delimiters followed by `0` and 2,994 closing delimiters:

```text
{"entry_id": + "[" * 2994 + "0" + "]" * 2994 + "}"
```

Its SHA-256 is
`87692f2a880ebda740fc10ff0ba1fe3135b1e198c939e0d7edbc1d1411845a12`.
Depth 2,993 was decoded and classified red, while depth 2,994 raised an
uncaught `RecursionError` from `_json_load`. The `summarize` CLI therefore
exited 1 with no stdout and wrote no `matrix-summary.json`.

## Why this is invalid

Downloaded receipt artifacts are hostile input. A syntactically valid JSON
shape must not be able to terminate summary production before the durable red
artifact is written. The old decoder and deterministic writer both traversed
containers recursively, so merely moving a deeply nested value to an output
path would retain the same failure class.

## Local correction

- Input is read through a 16 MiB finite byte boundary and scanned by an
  iterative string/escape/delimiter state machine before `json.loads` runs.
  Structural nesting is capped at 64, including the root container.
- Mismatched, unclosed, and unterminated structural neighbors fail before the
  decoder. Delimiters inside escaped JSON strings do not affect the bound.
- Decoder `RecursionError` and `MemoryError` are normalized to deterministic
  invalid-input errors; the summary's artifact-load boundary also catches
  both classes defensively.
- Canonical JSON output now walks containers with an explicit stack, detects
  cycles, enforces the same depth limit, and streams atomically through a
  64 MiB output boundary. Deep hostile Python values fail with `ValueError`,
  not call-stack exhaustion, and leave no partial output.
- The exact 2,994-depth witness now makes the CLI exit 1, emit a receipt path,
  and persist a parseable red summary whose errors identify the structural
  limit. Regressions pin depth 64/65, deep arrays and objects, malformed
  delimiter neighbors, escaped-string delimiters, oversized input, synthetic
  decoder resource exceptions, and writer depth/cycle behavior.

## Evidence boundary

The limits make parsing and canonical output total over the declared finite
document domain; they do not establish authenticity of any self-reported
receipt field. Documents above 16 MiB, outputs above 64 MiB, and structural
depth above 64 are deliberately rejected as outside the matrix artifact
format rather than interpreted.
