# F-MATRIX-007 — oversized JSON numbers could crash receipt validation

Status: corrected locally by fresh F-MATRIX-7 before the first authorized
push; awaiting author-separated refutation. No hosted run has occurred.

## Minimized evidence

Start with a canonical normative `PASS` receipt and replace only
`commands[0].elapsed_seconds` with the JSON integer `1` followed by 309 zeros.
Python's JSON decoder accepts that exact integer. Before correction,
`_is_nonnegative_number` called `float(value)`, which raised `OverflowError`.
Both direct receipt validation and the summary command could therefore crash
instead of producing a fail-closed result.

The same trust boundary admitted unbounded integers in byte counts, parsed
suite counts, resource observations, git status counts, ABI metadata, and
`sys.version_info`. Nonstandard `NaN`/`Infinity` constants were also accepted
by Python's default JSON decoder, while very large numeric substrings in
runtime release metadata could reach unsafe integer conversion.

## Why this is invalid

Downloaded receipt artifacts are hostile input. No syntactically accepted JSON
number may terminate the summary before it writes its durable red result.
Boolean values must not pass as integers, non-finite floats are not evidence,
and fields produced by bounded processes need explicit finite domains.

## Local correction

- Numeric predicates branch on exact integer/float types and never coerce an
  unbounded integer to float. Booleans, non-finite floats, negative values, and
  values above field-specific ceilings fail closed.
- General counts, byte/resource sizes, and status counts use a signed-64-bit
  ceiling. Timings, version components, logical CPU count, and word size use
  narrower domains justified by the producing command or platform field;
  process exits use the finite cross-platform subprocess return-code domain.
- Unsigned decimal release strings are length/range checked before conversion;
  build-flag numeric scalars must also be finite and bounded.
- JSON `NaN` and `Infinity` constants are rejected at load time. The summary
  validates artifacts inside a final exception boundary, omits invalid rows
  from trusted aggregation, and still writes a failing summary.
- Subprocess count parsing also length/range-checks decimal output before
  conversion, and JSON writers refuse non-finite numeric extensions.
- Regressions cover the minimized 310-digit integer through direct validation
  and summary, overflowing exponent notation, `NaN`, booleans, bytes, counts,
  resources, ABI/version serial fields, and accepted/rejected finite boundary
  neighbors.

## Evidence boundary

This makes artifact parsing and validation total over the tested hostile
numeric domain. It does not make self-reported receipt metrics independent
attestation; hosted artifact provenance and job conclusions remain necessary.
