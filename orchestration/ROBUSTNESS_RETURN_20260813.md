# Robustness program return — 2026-08-13 (Fable custody)

## Where the program stands

WP4 is decided: the decisive fresh-context refuter confirmed 592 divergences
across five mechanisms on attempt 4 (`orchestration/refuters/RI5.md`), the
third strike, and the package has taken its chartered fallback — the
attempt-4 candidate remains committed as a nonconforming receipt-bound
record, the reimplementer guidance now carries the newly pinned law surfaces,
and the README keeps its "does not exist" wording (claims edit staged for the
James gate). The hosted 50k campaign is no longer an admission gate; the
hosted evidence of record is run `31661587861` (campaign FAIL at identity 588
on pre-fix bytes = F-WP4-007, all nine suites cells 21/21 on program steps).

All four pending increment refutations are delivered (ledger row 2026-08-13):
A valid MEDIUM (unsealed evaluator; disposition James-gated), B valid LOW
(fixed as F-WP1-014, commit `15faca2`), C clean, D valid MEDIUM (manifest
re-pinned, commit `a4dbfe5`; hygiene re-bound, commit `c8476b7`).

## Verified green at this return (local, `py -3.12` unless noted)

- WP1 matrix on CPython 3.12/3.13/3.14: portable preflight suite,
  outcome-measurement suite, `outcome_receipt.py --check`,
  `fixture_extract.py --check`, reference-host historical regressions — all
  green on all three runtimes over the F-WP1-014 bytes.
- WP1 outcome receipt regenerated: 0 new false holds, 208 insufficient,
  18/18 detection; `FALLBACK_DELIVERED_CPYTHON_3_13_PENDING` retained
  pending the James-gated claim re-pin.
- Portable offline gate 9/9 over the re-pinned manifest (60 files).
- Custody: `verify_receipts` 193/0; `verify_hygiene` HYGIENE_PASS
  allowed_raw_receipt_warnings=980 admitted_diagnostics=2
  custody_hashes=12/12.
- WP4 cross gate re-verified on `2306f73` bytes by the custodian:
  test_cross failures=0; DIV-001-min independently re-executed (exit 2/2,
  stdout SHA-256 BAA52EC9… / 120BD0E7…).

## Open at this return (all staged for one James gate)

1. README fallback claims edit (diff staged in the operator workspace,
   round accounting: seven refutation rounds, one campaign run).
2. Increment-A disposition: amend TRUST_MODEL/ERRATA E8 wording (data
   authorities vs evaluator, recommended) or add `grounded_layer_sha256` to
   `GOVERNING_AUTHORITIES` (format bump + fresh refuter round).
3. WP1 3.13 claim re-pin: RUNTIME_EVIDENCE re-pin and the
   `evidence_bar_met` flip in `outcome_receipt.py` (+ the paired
   `test_313_is_explicitly_pending_and_bar_unmet` regression update).
4. Workflow patch (guarded file, James applies): `fetch-depth: 0` for the
   suites-job checkout (custody hygiene needs the base object), and the
   campaign jobs' disposition under fallback (dispatch-only recommended).
5. The carrying push and terminal close.

## Remote state

Unchanged this session: no push, tag, release, workflow, settings,
deployment, or secret mutation. Branch is ahead of origin by local commits
only; every push remains separately James-gated.
