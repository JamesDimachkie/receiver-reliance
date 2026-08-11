# F-MATRIX-005 — GraalPy release and Python language version were unbound

Status: **RESOLVED locally.** Correction retained and covered by two
consecutive 44/44 focused passes. No hosted run has occurred.

## Minimized evidence

Start with the otherwise valid receipt for
`off-contract-graalpy-24-0-ubuntu-latest-x64`. Before correction, each of these
mutations was accepted when `full_version` was changed to the same triple:

```text
version_info = [99, 99, 7, "final", 0]
version_info = [3, 8, 7, "final", 0]
version_info = [3, 14, 7, "final", 0]
```

`_receipt_validation_error(...)` returned `None` for the canonical row and all
three forged rows. The `GraalVM` implementation name bypassed both the CPython
and PyPy version branches.

## Why this is invalid

`graalpy-24.0` is a GraalPy distribution release selector, not a Python
language version. GraalPy 24.0 is a Python 3.10-compliant runtime. Treating the
two versions as one value would be incorrect, but leaving both unbound lets an
arbitrary language runtime retain a green off-contract observation.

The pinned `actions/setup-python` implementation emits its resolved GraalPy
release as the `python-version` output (for example `graalpy24.0.2`). That is
the honest hosted observation of which 24.0 patch the setup step installed;
`sys.version_info` independently reports the Python language level.

Primary evidence checked on 2026-08-10:

- `actions/setup-python` at the workflow-pinned SHA
  `ece7cb06caefa5fff74198d8649806c4678c61a1`,
  `src/find-graalpy.ts`, sets the output to
  `graalpy${resolvedGraalPyVersion}`.
- Oracle's official `graal-24.0.2` GitHub release describes GraalPy 24.0.2 as a
  Python 3.10-compliant runtime.
- Counterevidence sought: Oracle's GraalPy 24.0.2 `SysModuleBuiltins.java`
  builds `sys.implementation.version` from the Python language
  `versionInfo`, not the GraalPy distribution release. The correction therefore
  does not mislabel that field as independent distribution evidence.

## Local correction

- The plan separately declares `distribution_release: "24.0"` and
  `python_language_version: "3.10"` while retaining
  `python_version: "graalpy-24.0"` as the setup input.
- The stress run steps pass the pinned setup action's resolved
  `python-version` output to the receipt writer. Executed receipts record it as
  `environment.runtime.setup_python_version`.
- Summary validation requires the checked-in setup selector and distribution
  family to agree, the resolved setup output to remain in the 24.0 family, and
  the runtime language major/minor to be 3.10. Patch updates within 24.0 remain
  allowed because the setup input intentionally selects that release family.
- Regressions cover the three minimized language-version forgeries, adjacent
  GraalPy release families, absent/malformed setup output, and an allowed 24.0
  patch neighbor.

## Evidence boundary

This remains a stress-only, off-contract observation below the Python 3.12
language floor. The setup output and runtime fields are receipt evidence, not
independent attestation. Hosted artifact provenance and job conclusions remain
necessary, and the row cannot substitute for any normative CPython result.
