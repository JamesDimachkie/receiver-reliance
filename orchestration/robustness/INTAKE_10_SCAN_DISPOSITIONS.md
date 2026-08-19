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

## Closed after the cluster table — the W3-grounded seven

The cluster table above was written on 2026-08-12. Commit `5946e4c`
(2026-08-13) then closed seven individual findings with code across
`grounded-0_4/authority_surface.py`, `rr_api.py`, `rr_batch.py` and
`test_public_surface.py`. Their ids were recorded only in that commit's
subject line, so this section is the missing disposition. Severity and
category are the scan's own; each verdict names the mechanism and the check
that pins it. `python -B grounded-0_4/test_public_surface.py` returns
`PUBLIC-SURFACE PASS: 38 checks` at the current bytes.

| Finding | Severity / category | Verdict |
|---|---|---|
| `csf_2b00e6b7` normal runtime paths trust adjacent policy-root files without independent authentication | low / file-safety | **FIXED** — the runtime authority query and the closure-policy loader authenticate the adjacent register and policy bytes against pinned digests before use. Pinned by `runtime authority query authenticates adjacent register bytes` and `closure policy substitution fails authentication`, which substitute `{}` for each file in a temporary root and require failure. |
| `csf_68032a42` runtime authority validation accepts unsupported register versions and arbitrary nonempty status values | low / integrity-verification | **FIXED** — register `format_version` and per-field `status` are closed enumerations rather than nonempty-string checks. Pinned by `authority rejects unsupported format_version` and `authority rejects unsupported status`, using `B1-AUTHORITY-REGISTER-999` and `synthetic_open_status`. |
| `csf_5cb40479` a deeply nested authority register escapes validation as an uncaught RecursionError | low / path-traversal | **FIXED** — register parsing is depth-bounded and fails closed instead of raising. Pinned by `deep authority register fails closed` against a 128-deep array. |
| `csf_752f72c3` public object APIs canonicalize caller-controlled Python objects before the bounded total wire parser, breaking API/CLI parity | medium / cross-surface-consistency | **FIXED** — object requests are converted by `_bounded_object_wire` and enter the same bounded total parser as CLI bytes, so cyclic, non-string-key, non-finite, lone-surrogate, over-nested and over-member inputs return `ERR_JSON`, `ERR_NUMBER` or `ERR_LIMIT` instead of raising. Pinned by seven checks including `valid object and bytes calls remain byte-identical` and `conformance object path is total too`. |
| `csf_871e62f4` stable library API can bind ambient same-name modules instead of the intended frozen implementation | low / input-validation | **FIXED** — package import resolves `authority_surface`, `b1_capabilities` and `pcb_runner` by repository path regardless of same-name modules already present. Pinned by three `ambient collision cannot replace ...` checks that pre-poison `sys.modules` with empty stand-ins and then compare resolved `__file__` paths. |
| `csf_ec4c5438` OBL-30 trusts caller-controlled row and bookkeeping projections that are not bound to the candidate pool | medium / integrity-verification | **FIXED IN THE AUDITED TIER** — three projection closures (R1 candidate/pool record ids, R2 verdict record ids, R3 exclusion record ids) fire `MALFORMED_OR_BOUNDARY` on the audited surface. The sealed 0.4 response still returns `VALID`, which is E5's recorded frozen gap and may not change by charter; each case asserts BOTH halves, `frozen-gap-reproduced` and `audited-fail-closed`, so the gap is now closure-detected rather than only disclosed. |
| `csf_6dc196be` a never-terminated oversized batch request can monopolize the sidecar indefinitely | medium / denial-of-service | **FIXED** — `rr_batch.serve` gives an unterminated overlimit line a finite work ceiling and fails deterministically with `ERR_BATCH_RECORD_LIMIT`. Pinned by `unterminated overlimit batch work is bounded`, which asserts the exact read count. The sidecar half of the same class is `MAX_DECLARED_REQUEST_BYTES` in F-WP5-006; that finding's bound 4 (an LF-less flood costing bounded memory but unbounded work) is the deliberately-kept limb. |

Effect on the deferred set below: C2's remainder narrows to the peripheral
loaders — the public decision surface is now behind the one bounded total
parser, which was C2's stated shape. C1's runtime-authentication limb is
closed. C6's remainder is unchanged apart from the batch ceiling. No row
here retires the re-adjudication trigger.

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
- ~~CI hardening items (mutable action tags, credential persistence) at the
  next workflow edit, which is James-gated.~~ **Landed 2026-08-15 (`4be4691`,
  owner-authorized, ManagedCodex lane).** All three workflows pin every action
  to a 40-hex SHA and set `persist-credentials: false`; scan finding
  `csf_676003e1` is named in that commit. Struck rather than deleted so the
  deferred set stays a record of what was deferred and what became of it.

## Findings the scan itself scoped down

The scan's severity rationale template concedes "exposure is narrower than
a public internet service" and conditions escalation on "proof of broad
unauthenticated deployment or privileged downstream effects" — neither
exists (census). That calibration note is why the deferred set is safe to
defer, and it expires with the trigger above.
