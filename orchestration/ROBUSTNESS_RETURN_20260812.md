# Robustness program — session checkpoint 2026-08-12 (Fable custody)

**Status: CHECKPOINT — IN PROGRESS. This is a resumable handoff, not the
terminal return.** The charter's terminal definition of done
(`MASTER_PROMPT_RR_ROBUSTNESS_20260811.md` §11) is not yet satisfied: WP4 is
unresolved and the full local gate + hosted matrix have not been run at a
terminal commit. Nothing here is pushed; every remote action remains
James-gated.

## Custody

Integration custody passed from Sol root to Claude (Fable 5) by James's
explicit current-turn direction on 2026-08-12, after Sol's budget was
exhausted mid-flight. Single-writer, same charter, same red lines, same
gates. Recorded in the task claim `owner`/`custody_note`.

The host power-cycled once mid-session (plug ajar); the worktree survived
intact (`git fsck` clean) and all in-flight work was on disk. No corruption.

## What this session did (all additive, all local)

The 2026-08-12 Deep Security Scan (99 findings) was adjudicated as **Intake
10** against a newly written canonical trust model, and the load-bearing
findings were fixed with regressions. Four commits on
`sol/rr-robustness-20260811`:

| Commit | Content |
|---|---|
| `f08fa34` | Grounded audit format `B1-AUDITED-DECISION-0.4.1`: `governing_authorities` policy digests sealed into every audit (ERRATA E8), closure-evaluator errors fail closed to `AUDIT_INCOMPLETE` (E9), record-reference truncation disclosed (GEN_0_5 §4.5 backport). Grounded 517/0, single-pass 1142/0, batch 2149/0, adversarial 6497/0. |
| `a107081` | WP1 fail-closed preflight boundary law (F-WP1-010..013): empty stream = exit 2, duplicate-member rejection with bounded acquisition, REJECTED-over-INSUFFICIENT precedence, injective scope digests. All-408 replay byte-identical (0 false holds, 18/18). |
| `ac2bbd5` | `TRUST_MODEL.md` (canonical), Intake 10 adjudication + `INTAKE_10_SCAN_DISPOSITIONS.md`. |
| `a87293e` | WP5 sidecar: admit valid early responses (F-WP5-007), full stderr drain (F-WP5-004 correction), bounded declared work + nonempty-frame law (F-WP5-006), deterministic timeout probe. Suite 728/0. |

**Uncommitted, green, ready to commit next (working tree):** WP5 receipt
convergence to the explicit `py -3.12` pair (profile attempt7 / sidecar
attempt10) with verifier + perf docs re-pinned (verify 126/0); WP1 3.14
test-portability fix; doc coherence (README, ERRATA, HOST_OBLIGATIONS,
portable/README, PROFILE date note); matrix `plan.json` re-pins
(grounded 504→517, lint-gate-meta 7→9) + Sol's `portable-bundle-gate`
matrix row; the whole `portable/` lane (inventory + manifest, 60 files,
gate wired); `second-implementation/` (WP4 attempt-3 candidate);
`orchestration/REIMPLEMENTERS_GUIDE.md`.

## The one uncertainty James asked to resolve — RESOLVED

Consumer census (2026-08-12, recorded in `TRUST_MODEL.md`): **zero external
or sibling code consumers** of `receiver_reliance`, preflight `READY`, or
audit seals across the workspace and adjacent trees (one unrelated
production repo excluded by standing policy). This is the fact ~70 of the 99
findings implicitly depended on. The artifact is a **research artifact**:
consumers re-verify from the commit root; receipts make that mechanical.
Re-adjudication trigger recorded: first external consumer or any adversarial
embedding promotes the deferred hardening set to blocking.

## Verified green this session (local, Windows)

- Frozen conformance 0.2 (800/0) and composed 0.3 (800+107/0); grounded
  517/0; single-pass 1142/0; batch 2149/0; adversarial 6497/0; properties
  2296/0; authority-legibility 452/0; lint 0; lint-gate-meta 9/0; authority
  table `--check` exact.
- Adapters: preflight 25/0, reference host 48/0, outcome 2/0 —
  **on CPython 3.12, 3.13, and 3.14** (3.13.15 installed this session via
  `py install 3.13`; this closes the WP1 3.13 evidence gap that
  `RUNTIME_EVIDENCE.md` still records as PENDING — see "next session" item 3).
- WP5 sidecar 728/0; WP5 receipt verifier 126/0.
- Portable: manifest 60 files drift=0, verify_bundle 60/0, build_bundle
  deterministic, test_bundle 6/0, test_cli 4/0 (incl. under `-I`); full
  `portable/gate.py` 9/9 (final confirm running at checkpoint).
- Custody: `portability/verify_receipts.py` 193/0,
  `portability/verify_hygiene.py` HYGIENE_PASS. (Re-run at terminal;
  grounded/adapters byte changes and the two new WP5 receipts will need the
  documented rebind — see next session item 2.)

## What remains (next session, in order)

1. **WP4 disposition (the one real open lane).** A fresh-context refuter was
   launched over the `second-implementation/` attempt-3 candidate this
   session (agent still in flight at checkpoint; its transcript persists,
   resumable). WP4 is NOT admitted — attempt-3 is a committed-later
   candidate that passed its own `test_cross` (0 divergences) but has not
   completed a fresh-context zero-divergence refuter pass, and no ≥50,000
   coverage-guided campaign receipt exists. Options per charter §8: refuter
   returns NO-NEW-EVIDENCE → run the 50k campaign
   (`second-implementation/coverage_campaign.py`, in-process, seed-fixed;
   no committed campaign receipt yet); any valid defect → fix or fire the
   three-strike fallback (ship `REIMPLEMENTERS_GUIDE.md` + minimized
   divergence set). Scan highs `csf_4dac9670` and `csf_99b169a9` are routed
   here.
2. **Verifier rebind + hygiene.** After WP4 settles, rebuild the portable
   manifest over the terminal byte set, run the documented
   `verify_receipts.py`/`plan.json` rebind for the new WP5 receipts and any
   grounded/adapters count changes, and re-run hygiene. The matrix plan row
   `grounded-0.4-regression` is now 517 and `lint-gate-meta` is 9 — hosted
   runs have never seen these; they re-pin at the next hosted cycle.
3. **WP1 3.13 evidence.** `adapters/RUNTIME_EVIDENCE.md` still says 3.13
   PENDING and the outcome receipt's `runtime_evidence.cpython_3_13` still
   says PENDING, but 3.13.15 now runs all WP1 suites green locally. Decide:
   regenerate the outcome receipt to record 3.13 evidence (flips
   `evidence_bar_met`; a claims-adjacent change — James-gate the wording) or
   leave PENDING pending a hosted 3.13 row. Recommendation: record the local
   3.13 pass, keep hosted 3.13 as separately-scoped.
3. **Terminal close.** Full local gate at the terminal commit, both custody
   verifiers, hygiene, worktree clean, ledger + claim closed. Then the
   README claims-change diff (TRUST_MODEL link, 0.4.1 audit wording, and —
   only if WP4 admits — the "conforming second implementation exists"
   sentence) goes to James with the diff before any push. Push stays a
   James button.

## Deliberately NOT done (correct to defer)

The Intake 10 deferred set (INTAKE_10_SCAN_DISPOSITIONS.md §Deferred): the
shared canonical-ingest module for peripheral loaders (C2 remainder), harness
ambient-authority elimination (C5), long-lived-harness lifecycle limits as
protocol (C6), CI action-pinning. All gated on the first external consumer.
The blinded outcome-value experiment remains out of scope.

## Evidence pointer

The sealed scan artifacts (report.md, findings.json, coverage.json,
scan-manifest.json) are copied for durability to
`.agent-reviews/results/receiver-reliance-deep-scan-6e9e61a6-salvage/final/`
(workspace root, outside this worktree). findings.json raw SHA-256
`421196D3D2293FA18897D088166F521485E75B6360C66706F46A5B04254E2E76`.
