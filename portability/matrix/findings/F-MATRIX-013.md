# F-MATRIX-013 — honest empty compiler invalidated off-contract observation receipts

Status: **RESOLVED locally; hosted rerun pending at the corrective SHA.**

In hosted run 31548278804 (pushed SHA
`4c9250a75e29e46275aa0d99902d49023e97ef15`), the off-contract jobs for
GraalPy 24.0 and PyPy 3.11 produced receipts that the summarizer rejected
with `environment runtime compiler must be nonempty`, downgrading both rows
to `RECEIPT_MISSING` in `matrix-summary.json`:

- `off-contract-graalpy-24-0-ubuntu-latest-x64` recorded an honest
  `INFRA_UNAVAILABLE`;
- `off-contract-pypy-3-11-ubuntu-latest-x64` recorded a labeled below-floor
  `OBSERVED_DIVERGENCE` observation.

Root cause: those runtimes legitimately return an empty string from
`platform.python_compiler()`. `_environment_validation_error` required a
nonempty `compiler` for every receipt, so a truthful recorded value
invalidated otherwise well-formed observation evidence. The observation
outcomes themselves were preserved in the artifacts; only their validation
and summary classification were wrong.

The correction keeps `compiler` type-checked as a string everywhere, keeps
the nonempty requirement for `normative` receipts, and accepts the empty
string as the honest recorded value for observation classifications
(`off_contract`, `stress`).

Regression pin: `matrix/test_receipt.py`
`SummaryTests.test_off_contract_compiler_may_be_empty_normative_must_not`
covers the off-contract empty-compiler acceptance, the normative rejection,
and the non-string rejection.

This is observation-lane machinery only: no normative gate consumed the
affected receipts, and `normative_failures` stayed empty in the run-1
summary.
