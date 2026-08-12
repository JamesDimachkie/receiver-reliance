# WP1 portable fallback runtime evidence

INTERIM STATE (2026-08-12, Intake 10 increment): the fail-closed boundary
law (F-WP1-010..013) changed the preflight bytes after the table below was
produced. The rows record the pre-increment runs and stand as historical
evidence only; the final three-runtime matrix (CPython 3.12/3.13/3.14 —
3.13.15 is now installed locally) re-runs after the fresh-context refuter
pass on the increment, and this block is re-pinned then.

Bytes under test (current):

- `portable_preflight.py`: re-pinned at the final matrix run
- `test_portable_preflight.py`: re-pinned at the final matrix run
- `outcome_receipt.py`: `A6A4FEB4DE5D519EC770DCDE8D7F5916A9AB6332FD899746040384691973F2E5`
- `WP1_OUTCOME_RECEIPT.json`: `ED3F67D6AA103917CC9CC6B3E9B75A841C55F52200FB60B3816A8D6809C318B8`

| runtime | command | result |
|---|---|---|
| CPython 3.12.10 | `py -3.12 -B adapters/test_portable_preflight.py` | 14 fallback-only tests passed |
| CPython 3.12.10 | `py -3.12 -B adapters/test_outcome_receipt.py` | 2 measurement tests passed |
| CPython 3.12.10 | `py -3.12 -B adapters/outcome_receipt.py --check` | all-408 deterministic check passed |
| CPython 3.12.10 | `py -3.12 -B adapters/fixture_extract.py --check` | 408 parent rows / 211 E7 rows; row binding verified |
| CPython 3.12.10 | `py -3.12 -B adapters/test_reference_host.py` | 47 non-shipping historical regressions passed |
| CPython 3.14.5 | `py -3.14 -B adapters/test_portable_preflight.py` | 14 fallback-only tests passed |
| CPython 3.14.5 | `py -3.14 -B adapters/test_outcome_receipt.py` | 2 measurement tests passed |
| CPython 3.14.5 | `py -3.14 -B adapters/outcome_receipt.py --check` | all-408 deterministic check passed |
| CPython 3.14.5 | `py -3.14 -B adapters/fixture_extract.py --check` | 408 parent rows / 211 E7 rows; row binding verified |
| CPython 3.14.5 | `py -3.14 -B adapters/test_reference_host.py` | 47 non-shipping historical regressions passed |
| CPython 3.13 | same portable, measurement, provenance, and receipt commands | **PENDING — runtime unavailable locally** |

The fallback-only test entrypoint imports neither the stood-down reference
host nor its H5/H6 experiments. The historical suite is recorded separately
and is not part of the shipping fallback boundary.

Hosted evidence was inspected, not borrowed. Hosted manifest raw SHA-256 is
`9DC261CA316C4F8E83342FE6AD24EBF15C3A21F3FD38AE6565EE28651569D5E6`
at head `7facfa34bb7b841fd0a7d911f15b4da71efde95b`; neither the current fallback
test command nor current portable-preflight hash appears in hosted receipts.
Those CPython 3.13 rows do not exercise these bytes.

Conclusion: current local evidence covers 3.12 and 3.14. The paired outcome
bar is met, but the requested CPython 3.12–3.14 runtime evidence bar and
package completion remain unmet until an actual 3.13 run is produced.
