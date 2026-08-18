# F-CONC-004 — the published ladder source pin is stale, and the receipt verifier never checked it

Status: **DISPOSED, NOT REPAIRED.** The pin stays as published; `ERRATA.md` E12
carries the disposition and `portability/verify_receipts.py` now enforces the
whole table so the class cannot recur silently. Recorded from the 2026-08-12
deep-scan finding `csf_29f06dd2`.

## What was wrong

`../receipts/STATUS.md` publishes four raw SHA-256 digests under "Raw source
binding for the current clean v3 receipts" and states that any change to one of
those files invalidates the binding and requires a new receipt. Nothing in the
repository enforced that sentence. `verify_receipts.py::_verify_concurrency`
binds the two receipt files by raw digest, checks their recorded
`status`/`git.clean`/`git.head`, and recomputes the worker-run and
audited-envelope totals from the receipt bodies — all of which pass — but it
never hashed a single source file the receipts name.

The gap was not hypothetical. Measured at this revision:

| Role | Source | Published | Current |
|---|---|---|---|
| harness | `../ladder.py` | `B5436C85…` | `D40F692A…` |
| focused tests | `../test_ladder.py` | `926D75C5…` | `926D75C5…` |
| clean oracle implementation | `../../oracle/oracle.py` | `2148F0C9…` | `2148F0C9…` |
| clean oracle public API | `../../oracle/__init__.py` | `747CF137…` | `747CF137…` |

`4ea69dc` bound the receipts. `ca1ccfe` — the only commit to touch `ladder.py`
since — changed one line, `AUDITED_FORMAT_VERSION` `0.4` to `0.4.1`, as the
F-MATRIX-016 response-era migration. `verify_receipts` continued to report
`checks=193 failures=0` throughout, truthfully, because none of its 193 checks
covered the source table.

## Why the pin is not refreshed

Refreshing it is the cheap repair and it is the wrong one. The digest's only
function is to say which bytes produced the recorded run. Rewriting it to
`D40F692A…` would assert that the current bytes produced the 242,400-envelope,
213.937-second normative run, which they did not: no ladder re-run receipt
exists at these bytes. F-MATRIX-016 argues the 0.4.1 envelope keeps the frozen
six-field surface so the seal recompute and oracle projection hold unchanged,
and that argument is sound — but it is an equivalence argument, not evidence of
re-execution, and a provenance pin is exactly the field that must not absorb an
equivalence argument.

## Scope of the invalidation

Unaffected: both receipt files are byte-unchanged and still bind their published
raw digests (`B1782A43…`, `8CBA926D…`); the recorded clean-source HEAD
`8a525b16` is unchanged; the worker-run total (32) and audited-envelope total
(242,400) still recompute from the receipt bodies; the physical-cache and oracle
bindings and the R-CONC-4 refutation all rest on the three unmoved pins.

Affected: the claim that the ladder source *at this revision* is the source that
produced those receipts. It is not. Anyone re-running the ladder here runs the
0.4.1 auditor.

## Enforcement

`verify_receipts.py` gains `CONCURRENCY_SOURCE_PINS` and `SOURCE_PIN_ERRATA`.
Three pins must equal the current bytes exactly. `ladder.py` is bound to the
post-erratum digest, and a further check requires `STATUS.md` to still publish
the historical digest and to carry the E12 cross-reference — so neither the pin
nor its disclosure can be quietly dropped, and a second undisclosed byte move
fails the gate instead of hiding behind the first.

Same class as F-MATRIX-013/014/015/016/017: bindings to program-era truths must
migrate in the same change that moves the truths. This one could not migrate,
because the truth it binds is a past execution. Where migration is impossible,
the binding gets a disposition and a guard.
