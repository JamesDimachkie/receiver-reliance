# F-MATRIX-001 — missing normative receipts fail open as infrastructure

Status: **RESOLVED locally.** Correction retained and covered by two
consecutive 44/44 focused passes. No hosted run has occurred.

## Reachable path

- `.github/workflows/portability.yml` marks the whole normative matrix job
  `continue-on-error: true`.
- The receipt step may crash or be killed before producing a file.
- Artifact upload runs with `if: always()` and only warns when the receipt is
  missing; summary artifact download failure is also tolerated.
- `portability/matrix/receipt.py` synthesizes every missing runnable normative
  receipt as `INFRA_UNAVAILABLE` and excludes it from normative failures.

The focused missing-receipt unit test codifies that behavior and exits zero.

## Why this is invalid

An explicitly observed missing runner or unavailable runtime build is
`INFRA_UNAVAILABLE`. A missing receipt from a scheduled/executed job is
ambiguous: it also includes harness crashes, kills, upload loss, and download
failure. Without job-result and setup-outcome evidence, classifying it as
infrastructure can swallow a real normative divergence and leave the workflow
green.

## Required correction

Normative absence may be green only when a durable receipt explicitly proves
runner/build unavailability. Every other missing/ambiguous normative receipt,
failed upload/download, or executed harness failure must fail closed. A fresh
author owns the correction; a fresh refuter must verify it before push.

## Local correction

- Scheduled runnable rows without receipts now produce `RECEIPT_MISSING`, not
  synthetic infrastructure evidence; normative instances fail the summary.
- `INFRA_UNAVAILABLE` receipts carry validated proof kind, producer, and
  evidence. The three unscheduled `macos-13` rows retain their checked-in
  runner evidence.
- Normative and expanded-gate jobs preserve failure conclusions, pass those
  conclusions to the summary, and make receipt upload/download loss fatal.
- Adversarial tests cover missing and ambiguous receipts, an explicit setup
  failure receipt, failed job/result propagation, artifact loss, a failed
  harness result mislabelled `PASS`, and a real `DIVERGENCE` outcome.
