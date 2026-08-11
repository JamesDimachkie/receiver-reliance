# F-MATRIX-008 — negative numeric underflow erased the sign before validation

Status: corrected locally by fresh F-MATRIX-8 before the first authorized
push; awaiting author-separated refutation. No hosted run has occurred.

## Minimized evidence

Start with a canonical normative `PASS` receipt and replace the first command's
elapsed time with the JSON number `-1e-324`. Python's default JSON decoder
rounded that number to the binary float `-0.0`. Before correction,
`_is_nonnegative_number` then accepted it because `0.0 <= -0.0` is true. The
same path affected `children_user_seconds` and `children_system_seconds`.
Explicit `-0` and `-0.0` spellings had the same sign-erasure problem.

## Why this is invalid

A negative measurement cannot be evidence for a nonnegative field. Artifact
validation must be a total function of the JSON text, not of a lossy binary64
projection that can turn an invalid negative value into an accepted zero.
Extreme exponent spellings must also fail closed rather than overflow, round,
or allocate without a finite parser bound.

## Local correction

- Receipt JSON fractional/exponent numbers are decoded to stdlib `Decimal`,
  retaining sign and exact magnitude. Integer parsing separately rejects the
  otherwise sign-erasing `-0` spelling.
- Numeric lexemes and exponents have explicit finite parser bounds. Nonstandard
  constants, negative zero, non-finite values, and out-of-domain exponents are
  rejected before schema validation.
- Numeric predicates accept exact nonnegative Decimal evidence, including tiny
  positive neighbors, while rejecting Decimal and binary-float negative zero.
- The deterministic stdlib JSON writer has an exact Decimal path and refuses
  negative zero/non-finite output. Valid tiny positive evidence remains a JSON
  number in the durable summary instead of being rounded to zero.
- Direct and summary regressions cover both elapsed time and child CPU time,
  negative underflow, integer/fractional negative zero, extreme exponents,
  valid zero, and valid tiny positive neighbors.

## Evidence boundary

This closes a lexical numeric-validation gap. It does not make self-reported
timing or resource metrics independent attestation; hosted artifact provenance
and job conclusions remain necessary.
