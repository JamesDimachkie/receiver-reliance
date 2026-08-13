# WP1 portable fallback runtime evidence

Re-pinned 2026-08-13 after the fresh-context increment refuter pass on
`a107081` and the F-WP1-014 repair (`15faca2`): the matrix below records
local runs of the shipping fallback suites on CPython 3.12, 3.13, and 3.14
over the current bytes. The pre-increment table this block replaces is
preserved in git history (`a107081`..`15faca2`) as chronology.

Bytes under test (current):

- `portable_preflight.py`: `25DD05F5731FC142ADC4CDDDBCC294354E9119C063FCFF4E506E3098BE280384`
- `test_portable_preflight.py`: `9272B9D79E8E89FA99DEBED64E768E6E35FE8E62B2A23E92D457041EA4AD4741`
- `outcome_receipt.py`: `662C9F31E55097DC316DA5353DDC268E009BAC9B7E3D1340CF67EBD855A1A807`
- `receipts/WP1_OUTCOME_RECEIPT.json`: `86263477F1D1A3BEF6E85C362B1AEBBE58D74E6FD940EFC6C077297F95711804`

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

Conclusion: local evidence covers CPython 3.12, 3.13, and 3.14 for the
current bytes. The requested CPython 3.12–3.14 runtime evidence bar is met;
`evidence_bar_met` and `package_complete` are recorded accordingly in the
regenerated receipt (2026-08-13).
