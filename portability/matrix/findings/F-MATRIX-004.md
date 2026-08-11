# F-MATRIX-004 — execution environment metadata was not plan-bound

Status: corrected locally by fresh F-MATRIX-4 before the first authorized
push; awaiting author-separated refutation. No hosted run has occurred.

## Minimized evidence

Start with a structurally valid normative `PASS` receipt and change only:

```json
{
  "environment": {
    "os": {"system": "Plan9"},
    "runtime": {"implementation": "ForgedPython"}
  }
}
```

Before correction, the summary accepted either mutation. Environment
validation checked field presence and primitive types, but did not compare the
reported execution environment with the checked-in matrix entry. The same gap
covered runtime version, native architecture/emulation, ABI, encodings, and
stress capability evidence.

## Why this is invalid

A canonical command manifest does not prove that it ran in the requested
environment. Without an independent summary-side comparison, a normative row
could remain green after its defining OS, architecture, or CPython identity was
lost. Runner-only preflight checks were insufficient because the receipt is the
artifact consumed by the separate summary job.

## Local correction

- The checked-in plan now names each runtime implementation and its shared
  64-bit, little-endian, UTF-8 execution requirements.
- The summary independently binds executed outcomes to the requested OS family,
  machine, native/non-emulated evidence, runtime implementation, and CPython or
  PyPy language-version pair.
- Free-threaded, pydebug, and Development Mode rows must carry their requested
  build/runtime evidence. Alternative runtimes must retain their plan identity.
- Executed receipts must be captured from a clean checkout and bind their
  40-hex checkout SHA to `GITHUB_SHA`; when the summary itself has
  `GITHUB_SHA`, it also compares against that workflow value.
- Adversarial regressions mutate every bound field, including the original
  `Plan9` and `ForgedPython` witnesses, and require fail-closed validation.

## Evidence boundary

The summary recomputes equality and consistency from checked-in expectations;
it does not turn self-reported JSON into independent attestation. Hosted
artifact provenance and job conclusions remain necessary parts of the workflow
evidence.
