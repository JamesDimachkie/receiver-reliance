# F-MATRIX-006 — runtime release metadata admitted forged values

Status: **RESOLVED locally.** Correction retained and covered by two
consecutive 44/44 focused passes. No hosted run has occurred.

## Minimized evidence

Start with the canonical GraalPy receipt for
`off-contract-graalpy-24-0-ubuntu-latest-x64`. Before correction, either
mutation retained a successful validation result:

```text
version_info[3] = "forged"
version_info[4] = -1
```

In each case `_receipt_validation_error(...)` returned `None`. The same open
schema applied to CPython and PyPy rows: the first three version numbers only
had to be integers, the release level could be any string, and the serial
could be any integer.

## Why this is invalid

`sys.version_info` has five typed fields. Its numeric fields cannot be
negative, `releaselevel` is one of `alpha`, `beta`, `candidate`, and `final`,
and a final release has serial zero. The receipt's `sys.version` string also
starts with the corresponding public version, including `aN`, `bN`, or `rcN`
for a prerelease. Accepting arbitrary release metadata allowed a malformed or
forged runtime identity to retain a green summary.

## Local correction

- All runtimes now share one closed `version_info` validator: exactly five
  JSON-array items; nonnegative, non-boolean major/minor/micro and serial;
  exact release-level vocabulary; and serial zero for `final`.
- The leading public version in `full_version` must agree with the complete
  version tuple, including the alpha, beta, or release-candidate marker and
  serial where applicable.
- Regressions cover both minimized witnesses, booleans, negative version
  numbers, wrong lengths/container type, final/serial disagreement, and
  mismatched display strings across CPython, PyPy, and GraalPy.
- Valid `a0`, `b2`, and `rc1` neighbors for every runtime prevent the check
  from collapsing the schema to final releases only.

## Evidence boundary

This is structural and internal-consistency validation of a hosted receipt,
not independent attestation of the process that produced it. Hosted artifact
provenance and job conclusions remain necessary.
