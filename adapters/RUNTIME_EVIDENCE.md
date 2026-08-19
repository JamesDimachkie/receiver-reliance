# WP1 portable fallback runtime evidence

Re-pinned 2026-08-18; the correction notice below records the 2026-08-13 pass on
`a107081` and the F-WP1-014 repair (`15faca2`): the matrix below records
local runs of the shipping fallback suites on CPython 3.12, 3.13, and 3.14
over the current bytes. The pre-increment table this block replaces is
preserved in git history (`a107081`..`15faca2`) as chronology.

Bytes under test (current):

- `portable_preflight.py`: `B1F4F7C20E96AD88DE54402771CC71BEB3BE79BC37A7516EA9547790B5418F07`
- `test_portable_preflight.py`: `4CB01B0950242875A1AE76A690C14F762F887AC08CC5AFAFFB6C8A8E2EC7843E`
- `outcome_receipt.py`: `A1CC25FF550F6795FB3E35E1EB34D9B0BBE20611430DA16457F63827FF0102E1`
- `receipts/WP1_OUTCOME_RECEIPT.json`: `57763213B272DA4B363281D55FFC0881405E7086844EFCFFDCBBF935C9D1FFBD`

> **Re-pinned 2026-08-18.** The four digests above previously named the
> pre-W3 bytes and matched nothing on disk, so this file claimed multi-runtime
> evidence for code that no longer existed — the W3 adapters wave rewrote all
> four without re-pinning here. The commands below were re-executed against the
> current bytes on all three runtimes before these digests were written.

| runtime | command | result |
|---|---|---|
| CPython 3.12.10 | `py -3.12 -B adapters/test_portable_preflight.py` | OK (fallback-only tests incl. TransportDecodeTests) |
| CPython 3.12.10 | `py -3.12 -B adapters/test_outcome_receipt.py` | OK |
| CPython 3.12.10 | `py -3.12 -B adapters/outcome_receipt.py --check` | all-408 deterministic check passed |
| CPython 3.12.10 | `py -3.12 -B adapters/fixture_extract.py --check` | 408 parent rows / 211 E7 rows; row binding verified |
| CPython 3.12.10 | `py -3.12 -B adapters/test_reference_host.py` | OK (non-shipping historical regressions) |
| CPython 3.13.15 | same five commands under `py -3.13` | all green, same counts |
| CPython 3.14.5 | same five commands under `py -3.14` | all green, same counts |

The fallback-only test entrypoint imports neither the stood-down reference
host nor its H5/H6 experiments. The historical suite is recorded separately
and is not part of the shipping fallback boundary.

Hosted evidence was inspected, not borrowed: the receipt's
`hosted_evidence_inspection` block pins the hosted manifest and records that
no hosted row exercises these bytes. The runtime evidence bar is met on
local evidence alone; the paired outcome bar (0 new false holds, 18/18
detection) is recorded in `receipts/WP1_OUTCOME_RECEIPT.json` and
`OUTCOME.md`.

Conclusion: local evidence covers CPython 3.12.10, 3.13.15, and 3.14.5 for the
current bytes, re-verified 2026-08-18. The requested CPython 3.12–3.14 runtime evidence bar is met;
`evidence_bar_met` and `package_complete` are recorded accordingly in the
regenerated receipt (2026-08-13).
