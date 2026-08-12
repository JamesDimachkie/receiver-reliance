# Hosted receipt custody

This directory holds the durable receipts downloaded from the first fully
green hosted run of the `portability` workflow, plus a hash-bound manifest.
`portability/verify_receipts.py` binds `MANIFEST.json` by raw SHA-256 and
re-verifies every listed file byte-for-byte, so any post-download edit to
this evidence fails the committed verifier.

## Source run

- Workflow: `portability` (`.github/workflows/portability.yml`)
- Run: <https://github.com/JimGHTB12/receiver-reliance/actions/runs/31562391384>
  (id `31562391384`), created `2026-08-12T04:10:21Z`, conclusion `success`,
  all 28 jobs green.
- Head commit: `7facfa34bb7b841fd0a7d911f15b4da71efde95b`
  (`sol/rr-portability-modelcheck-20260810`). Every executed receipt in this
  directory binds exactly this `GITHUB_SHA` and a clean checkout.
- Download: `gh run download 31562391384` on 2026-08-12; artifact payloads
  were copied unmodified. GitHub artifact retention is finite, so these
  committed copies are the durable record.
- The pre-existing `conformance` workflow also passed on the same commit:
  run `31562391410`, all three OS jobs green. It uploads no artifacts; its
  identity is recorded here and in `MANIFEST.json` only.

## Prior runs on this branch (context, no receipts retained)

Four earlier hosted runs failed and drove harness repairs before the green
run: `31548278804` (`4c9250a`), `31549925307` (`00479e6`), `31552953993`
(`baa7b20`), `31553920699` (`254b248`). Each failure is adjudicated in the
findings records F-MATRIX-013, F-SANDBOX-026, F-SANDBOX-027, F-LIVE-009,
F-LIVE-010, and F-LIVE-011; none established an accepted-implementation
divergence.

## Contents and evidence classes

- `matrix-summary.json` — the runner's fail-closed aggregation
  (`aggregate_summary`). Raw SHA-256
  `CFAD7E2DA9D90D10737AF8F262512CBBACC654A2A7F53F51C40A7D1ADBD84CC1`.
- `receipt-*.json` — 25 per-row durable receipts (`row_receipt`): 15
  executed normative rows, 3 predeclared `macos-13` `INFRA_UNAVAILABLE`
  rows are represented inside the summary (they produce no separate
  artifact), 6 stress rows, 3 off-contract rows, and the hosted expanded
  gate.
- `sandbox-receipt.json` — the hardened Linux container sandbox host
  receipt (`sandbox_host_receipt`), daemon-real, inner and outer status
  `PASS`.
- `concurrency-smoke/matrix-focused-*.json` — 17 per-row concurrency smoke
  receipts (`secondary_unbound_concurrency_smoke`). Row receipts bind only
  the smoke commands' stream hashes, not these files' bytes, so their
  custody rests on this manifest alone; they are documentary, not
  independently bound evidence.

## Independent local revalidation

On 2026-08-12 the committed summary validator was re-run locally over the
downloaded row receipts:

```text
GITHUB_SHA=7facfa34bb7b841fd0a7d911f15b4da71efde95b \
python -B portability/matrix/receipt.py summarize \
  --receipts-dir <downloaded receipts> --output-name matrix-summary \
  --normative-job-result success --expanded-gate-job-result success
```

The locally produced summary is identical to the runner's committed
`matrix-summary.json` in every field — rows, counts, outcomes,
`gating_errors`, `normative_failures`, `upstream_job_results` — except the
absolute receipt path prefix embedded in the single invalid-receipt error
string (runner temp path vs. local download path). The local rerun
independently re-derived the same GraalPy `full_version` /
`version_info` metadata disagreement from the receipt bytes.

## Outcome summary (validated, from `matrix-summary.json`)

- Normative: 16 `PASS` (15 matrix rows + hosted expanded gate), 3
  predeclared `macos-13` rows as evidenced `INFRA_UNAVAILABLE`, zero
  normative failures, zero gating errors.
- Stress: `3.14t` free-threaded (including the bounded concurrency ladder)
  and `3.14` dev-mode `PASS`; `3.14` pydebug and the three
  `macos-15-intel` rows evidenced `INFRA_UNAVAILABLE` (pydebug build
  absent; native-execution probe lacked negative Rosetta evidence).
- Off-contract observations (never normative substitutes): PyPy 3.11
  `OBSERVED_DIVERGENCE` (first failing command `matrix-receipt-tests`;
  PyPy 3.11 is below the `>=3.12` contract floor), PyPy 3.12
  `INFRA_UNAVAILABLE` (setup could not provide the build), GraalPy 24.0
  `RECEIPT_MISSING` (its receipt was rejected as invalid: runtime
  `full_version` disagrees with `version_info` release metadata; the
  invalid artifact is preserved here as
  `receipt-off-contract-graalpy-24-0-ubuntu-latest-x64.json`).

## Nonclaims

No efficacy, novelty, security, fuzzing-completeness, external-standard, or
universal-portability claim. The proof tier stays `internal held-out`.
Hosted evidence covers exactly the environments, bounds, and rows recorded
above; `INFRA_UNAVAILABLE` and off-contract rows assert nothing beyond
their recorded reasons.
