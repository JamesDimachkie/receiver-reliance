# Intake 10 — Deep Security Scan dispositions

Scan id `6e9e61a6-a1f0-46c9-92d7-19f102f43170` against worktree revision
`e6c2856979410e8431640234f0bc6051fc6db1d1` plus uncommitted lane bytes;
artifact digests pinned in the Intake 10 entry of
`orchestration/CRITICISM_ADJUDICATION.md`. Findings are dispositioned
against the canonical trust declaration (`TRUST_MODEL.md`). Finding ids are
the scan's `findingId` values. Severity labels are the scan's own; this
record does not re-grade them, it dispositions them.

## Architectural clusters (99 findings → 6 causes)

| # | Cluster | ~Count | Disposition |
|---|---|---|---|
| C1 | Evidence identifies itself, not its governor (unpinned governing policy, receipts describing rather than proving) | 25 | Core fixed now (E8/E9, 0.4.1 governance binding); harness-receipt limbs recorded as scope caveats under TRUST_MODEL's harness row |
| C2 | Per-lane parser/canonicalization divergence from the core's one strict law | 20 | Shipping decision surfaces fixed now (preflight, F-WP1-011); remainder DEFERRED-WITH-TRIGGER: a shared canonical ingest module becomes blocking at the first external consumer |
| C3 | Preflight three-state semantics leaned READY on absent/ambiguous evidence | 8 | Fixed now (F-WP1-010/012), regression-pinned, outcome replay unchanged |
| C4 | Two-tier decision surface with the weak tier presented as a peer | 6 | DESIGN-DISCLOSED, strengthened: tier language now explicit in `receiver_reliance/__init__.py`, HOST_OBLIGATIONS H5, TRUST_MODEL evidence table; sealed bytes unchanged by law |
| C5 | Ambient host authority inside evidence harnesses (bare git/docker resolution, env passthrough, optimistic sandbox fields) | 23 | Recorded as harness scope caveats (trusted-OS assumption, TRUST_MODEL boundary table); DEFERRED-WITH-TRIGGER for any adversarial embedding |
| C6 | Subprocess lifecycle/resource totality treated as local detail | 17 | Sidecar lifecycle items adjudicated inside WP5's loop; local test-rig items DEFERRED-WITH-TRIGGER |

## The eleven highs

| Finding | Verdict |
|---|---|
| `csf_e5e9b8cdec13c18cf70c88eb` grounded audits don't identify governing authority/closure bytes | **FIXED** — ERRATA E8; `governing_authorities` sealed into every 0.4.1 audit; `governance:*` regressions |
| `csf_2e9e3a58b7bde4789bf783ba` closure authority unauthenticated; evaluator errors fail open to VALID | **FIXED** (fail-open half) — ERRATA E9, `AUDIT_INCOMPLETE`; authentication half is governed by the commit-root law: in-repo pinning is drift detection, and the audit now names its governing bytes so a verifier can check them against the root |
| `csf_9e86e5fae76792ca7c754b26` preflight success on empty/blank evidence stream | **FIXED** — F-WP1-010, `PREFLIGHT_STREAM_EMPTY`, exit 2; same-path truncation limb closed |
| `csf_048c221833a3d6e63e8825a1` preflight accepts duplicate JSONL members | **FIXED** — F-WP1-011, duplicate-rejecting pairs hook, bounded acquisition |
| `csf_6f35c3d2731af848eec8bdd4` INSUFFICIENT returned before validating contradictions | **FIXED** — F-WP1-012, all-layers precedence law |
| `csf_5f7b1451b3f0e17bb08d15f6` non-injective newline scope digests | **FIXED** — F-WP1-013, canonical-array digest on both adapter surfaces; historical `proof/arm_b1.py` sealed as-is |
| `csf_e6f27f6587b775706a1e076c` audit records silently omit references beyond 64 | **FIXED** — `record_references_truncated` backported from GEN_0_5 §4.5 (the cap was already specced there; the gap was disclosure, not design) |
| `csf_abbd6848057db9fcb967fc89` bare decide seals responses that don't bind decision facts | **RESTATED ERRATUM** — this is E2, recorded and fixed-by-tier since 2026-08-10; incremental response: explicit tier language at the package export (C4). No sealed byte may change by charter |
| `csf_0479d1a9cc58022cab8ed392` bare decide bypasses OBL-30 closures | **RESTATED DISCLOSURE** — E5's closures are 0.4-layer by construction; same C4 tier response. The audited surface is the governed surface |
| `csf_4dac9670c3eb1356499b8969` rr2 wrapper transcript validation bypasses strict parser | **WP4 LANE** — routed into the WP4 fresh-context refuter pass over the attempt-3 candidate; dispositioned by that loop's verdict in the ledger |
| `csf_99b169a9402543b529bffc96` execute_wrapper seals without validating outer request | **WP4 LANE** — same routing |

## The scan's two deferred candidates — answered

Both reduced to "what in-scope consumer relies on this?". The census
(TRUST_MODEL.md, 2026-08-12) found zero external or sibling code consumers;
the answers are therefore:

- `candidate-a41ddc43c8256a3e` (OBL-08 identity/policy values have
  presence-only authority): the presence-only status is REGISTERED,
  machine-checked, and publicly generated (`AUTHORITY_TABLE.md`); no
  consumer exists that treats presence-only fields as validated. Recorded
  disclosure, not a defect.
- `candidate-9cf53c80e425c536` (audited-decision seal is recomputable, does
  not authenticate provenance): correct by design and now stated canonically
  in TRUST_MODEL.md — seals prove integrity/reproducibility under the
  commit root, never provenance. The 0.4.1 governance binding gives the
  seal the missing referent (WHICH policy governed), which is the checkable
  half of the concern.

## Deferred set — recorded, with trigger

Deferred, not dropped. **Trigger:** the first external consumer, or any
embedding where handoff senders are adversarial to the receiver's tooling,
promotes this set to blocking (TRUST_MODEL.md, "Re-adjudication trigger").

- C2 remainder: one shared canonical bounded-ingest module adopted by every
  peripheral loader (portability matrix/receipt loaders, portable verifier,
  second-implementation CLI, live/schedule parsers).
- C5: harness ambient-authority elimination (pinned tool resolution,
  environment scrubbing, sandbox field verification instead of optimistic
  reporting) or receipt-language reduction to what was actually verified.
- C6 remainder: process-tree containment, deadline totality, and buffer
  bounds as protocol obligations for every long-lived harness.
- CI hardening items (mutable action tags, credential persistence) at the
  next workflow edit, which is James-gated.

## Findings the scan itself scoped down

The scan's severity rationale template concedes "exposure is narrower than
a public internet service" and conditions escalation on "proof of broad
unauthenticated deployment or privileged downstream effects" — neither
exists (census). That calibration note is why the deferred set is safe to
defer, and it expires with the trigger above.
