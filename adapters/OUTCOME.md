# WP1 portable fallback outcome — all-408 replay

This file is deterministic generator output from `adapters/outcome_receipt.py`.
Do not edit it independently; `--write` regenerates it together with
`adapters/receipts/WP1_OUTCOME_RECEIPT.json`, and `--check` requires both byte
sequences to match the current generator and pinned inputs.

The fallback preflight classified all 408 raw-SHA-pinned native records before
the offline scorer joined truth. `REJECTED_INVALID` is detection;
`INSUFFICIENT_EVIDENCE` is abstention. Neither is a pass. `READY` only permits
the receipt's bounded, measurement-only engine replay and is not itself a pass.

| arm | ready clean pass | new false holds | insufficient clean | rejected-invalid detection | ready engine detection | total detection | clean false-hold rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| historical forced arm | 257/390 | 133 | 0 | 0/18 | 18/18 | 18/18 | 34.1% |
| portable fallback | 182/390 | 0 | 208 | 8/18 | 10/18 | 18/18 | 0.0% |

The portable taxonomy is exact: 192 `READY`, 8 `REJECTED_INVALID`, and 208
`INSUFFICIENT_EVIDENCE`. Five stale REF alias/path contradictions and three
equal/non-increasing lifecycle timestamp contradictions are rejected before
applicability. The 208 untyped, noncontradictory lifecycle rows abstain because
timestamps do not establish acknowledgment semantics. No defective row is in
the insufficient-evidence bucket.

The accepted-core runner and pinned proof adapter used after `READY` are
mutable local measurement machinery. They are non-shipping, absent from the
exported fallback API, and not claimable as integration capability.

The paired outcome bar is met at 0 new false holds and 18/18 detection. The
runtime evidence bar is met: local CPython 3.12/3.13/3.14 suite evidence for
these bytes is recorded in `RUNTIME_EVIDENCE.md` (2026-08-13 re-pin). Existing
hosted receipts still do not cover these bytes.

- Receipt raw SHA-256: `57763213B272DA4B363281D55FFC0881405E7086844EFCFFDCBBF935C9D1FFBD`
- Parent corpus raw SHA-256: `09B4B05FE26CF46F063EC637C1A4D27B4D5190961756888099F96254C49B334E`
- Parent truth raw SHA-256: `4FEEF9BE65DD7523849CEE71B5A43EA6F7667710745E71D79C0EE5B054E3E2C7`
- Row-binding SHA-256: `27B7837AFF5595C111C2622C1A2258548BF62424B5B184E3C471C47A1BE07DFA`

Reproduce with `python -B adapters/fixture_extract.py --check` and
`python -B adapters/outcome_receipt.py --check`. Regeneration is explicit:
`python -B adapters/outcome_receipt.py --write`.
