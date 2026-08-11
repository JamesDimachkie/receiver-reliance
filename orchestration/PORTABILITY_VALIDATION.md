# Receiver-reliance portability validation — separated evidence report

Date: 2026-08-11

Branch: `sol/rr-portability-modelcheck-20260810` from baseline
`4e788d21e882a30bdda2aec3f780537161f81644`

Authority: `MASTER_PROMPT_RR_PORTABILITY_20260810.md`
(SHA-256 `154A9E5397D5D5B5422FD5D7053E7D1E6C6544C5D0152866598E6DC990F9C478`),
executed to the adjudication freeze by Sol root, then finished under Fable
custody at James's direction of 2026-08-11 ("take it from here"), with the
adjudication handoff recorded in `PORTABILITY_FABLE_RETURN_20260810.md`.

Status: **LOCAL EVIDENCE COMPLETE.** The hosted matrix, hosted sandbox, and
hosted expanded-gate receipts have not run because the first branch push —
which triggers them — is gated on James's explicit authorization. Every
category below is local evidence unless marked otherwise, and no category is
ever merged into a single pass count.

## Adjudication and decision record (Fable)

- **Bounded-state lane — Path A executed and ADMITTED.** The two prior
  complete receipts remain rejected (`081180E9...2B14`, pre-F-MODEL-001
  quotient unsoundness; `C27DEB15...D69E9`, F-MODEL-002 symbolic alias
  double-counting). The packet's eight preconditions were independently
  executed and passed — including alias exclusivity proven exhaustively to
  N=32 and retained-versus-streaming equivalence at every bound N=18..28 —
  before one post-F-MODEL-003 N=48 enumeration ran to exit 0 under durable
  file custody. Fresh refuter R-MODEL-3 attacked it across eight vectors;
  its independent full re-enumeration reproduced the receipt byte-for-byte
  and counted the alias-edge migration at exactly 16,260,520. Verdict
  NO-NEW-EVIDENCE; receipt `CD6210F8...732E` admitted. This was receipt
  attempt three of a three-strike stand-down rule; a third rejection would
  have closed the lane as quarantined-unresolved.
- **Live lane — F-LIVE-005 and F-LIVE-006 corrected and cleared.** The
  monitor's transport normalization is scoped to the physical read; every
  other loop-body exception is durably classified under the new
  `HarnessFaultError` (`HARNESS_FAULT`, replay exit 4). Four adversarial
  refutation rounds (R-LIVE-5) found three successively deeper renderer
  escapes and a two-axis stop-receipt evidence-overwrite defect
  (F-LIVE-006, also inherited by the frozen infrastructure writer); all
  repaired and regression-pinned. Final verdict NO-NEW-EVIDENCE.
- **Sandbox lane — F-SANDBOX-022 corrected and cleared.** Path dialect is
  validated before rendering with component-level UNC anatomy (including
  the `\\?\UNC\` namespace), and the mount source fails closed on
  surrogate-escaped text, NUL, quotes, commas, line feeds, and edge
  whitespace matched to Docker's actual Go grammar rather than Python's
  broader whitespace policy. Five refutation rounds (R-SANDBOX-22),
  including a proven CPython 3.12/3.14 `is_absolute()` divergence; all
  repaired and regression-pinned. Final verdict NO-NEW-EVIDENCE.
- **Concurrency — admitted with its standing qualification** (below).
- **Oracle — admitted** within its fixture-closed scope (below).
- **Author separation held throughout:** enumeration by one fresh agent,
  collection by the custodian, refutation by fresh-context Codex sessions
  that never authored the artifacts they attacked; refuter-blocked
  executions were resolved by running the refuters' probe scripts verbatim
  and reporting results back for their verdicts.

## 1. Frozen 0.2 parity

`baseline-run/implementation-output-0.2/run_conformance_0_2.py`: 800
checks, 0 failures (semantic 112, competence 370, wrapper arms 224,
negative 10, metamorphic 4, error law 80).

## 2. Composed 0.3 parity

`run_conformance_0_3.py --suite all`: 800/0 on the 0.2 suite plus 107/0 on
the 0.3 suite (competence 53, metamorphic 8, negative 10, semantic 12,
wrapper arms 24).

## 3. Grounded 0.4 behavior

- regression: 504 checks / 0 failures
- contract lint: 0 findings (authority ledger 199 required fields:
  semantic 111, presence-only 64, inert disclosed 10, inert registered
  debt 14)
- lint meta-gate: 7 checks / 0 failures (each controlled mutation rejected)
- seeded properties: 2,296 checks / 0 failures (seed 0x5EED8785)
- audited adversarial: 6,497 checks / 0 failures
- internal held-out synthetic proof: 7 tests pass
- seeded fuzz smoke: 31/31 strategies (seed 0x000000000B10F042)
- batch: 2,160 checks / 0 failures (perf on; peak 16,853,617 bytes;
  median batch/in-process ratio 1.263)
- single-pass audit: 1,142 checks / 0 failures (benchmark mode)

These eleven commands are the charter §1 expanded gate, re-run complete and
green on the final integrated tree (2026-08-11). The identical gate was
green at the pre-handoff freeze.

## 4. Raw JSON / UTF-8 / JCS finite exploration (independent oracle)

- focused tests: 35/35
- four frozen fixture packs: 124 semantic + 248 wrapper = 372 unique
  bindings; fixture binding
  `78FC43470C9AD4C41932CD38926F8430A004D02FE18E065D3DD6BE59A5A4B80B`
- two distinct no-new-evidence refutation passes (57 frozen closures + 24
  hostile boundary cases; then 122 additional seeded cases against both
  accepted ABIs)
- scope: semantic success is closed to the fixture packs; raw schema
  routing is bounded; JCS number emission is integer-only. Source-reading
  boundary declared in `portability/oracle/PROVENANCE.md`.

## 5. Bounded state model M (admitted receipt)

Receipt `CD6210F8706C7B37B6CD25A9EF67B53696207EAFED716284151D67B20444732E`
(custody: `portability/model/receipts/N48-POST-F-MODEL-003-SUMMARY.md`):

- quotient states 37,432,306; admissible transitions 294,190,481; terminal
  transitions 68,157,505
- symbolic terminal traces
  34,269,567,869,926,335,890,219,352,245,333,204,780,922,262
- excluded frontier edges 192,429,497; excluded trace prefixes
  365,700,154,247,143,020,084,708,553,153,258,324,529,440,021
- terminal classes: ERR_DUPLICATE_KEY 42,834,308; ERR_JSON 25,322,938;
  ERR_UTF8 170; PARSE_OK 47; ERR_NFC 41; ERR_EMPTY_INPUT 1 (quotient
  terminals; per-class symbolic multiplicities in `EXPECTED_COUNTS.json`)
- complete scheduler products P≤2/R≤2 and declared C/W partition
  multiplicities as published in the receipt; R=3 is recorded adversarial
  schedules only, never a completeness claim
- focused suite 17 tests (16 pass + 1 intentional full-enumeration skip);
  the `--full` constants now bind these admitted values
- assumptions, symmetry reductions, and exclusions are published verbatim
  from `domain.py` inside the receipt; everything outside M is reported as
  outside M

## 6. Live transport schedules

- eight committed schedules replayed twice on both real pipe and
  socketpair transports, byte-identical PASS results; complete 812-partition
  W coverage with zero unplanned OS short writes
- focused suite 29/29 after F-LIVE-005/F-LIVE-006
- stop classes: DIVERGENCE (exit 1), INFRASTRUCTURE_ERROR (exit 2),
  HARNESS_FAULT (exit 4) — a harness fault is never transport or
  divergence evidence, and stop-receipt evidence directories bind schedule
  bytes and completed-replay content so no stop can overwrite another's
  evidence

## 7. Concurrency schedules

- v3 receipt
  `98786009478343F4A7D84FC594A67C7E09BE64483865123AC1C73E4144525699`;
  focused suite 15/15
- P ∈ {1,2,4,8,16,32} at 200 requests per caller, paired identical-seed
  runs byte-matching; P=16,32 soaks at 1,000 requests per caller; library
  and process modes; 242,400 independently projected audited envelopes;
  fresh refuter independently recomputed every declared aggregate
- **standing qualification:** the receipt records `git.clean=false` at its
  baseline and coexecution resource observations; it is not
  clean-commit-bound and not an isolated performance baseline, and the
  semantic projection does not independently oracle every nested audit
  metadata field (e.g. `engine_generation`)
- CPython 3.14t free-threaded evidence is an honest local
  `INFRA_UNAVAILABLE` receipt; the hosted stress lane owns it

## 8. Resource probes

- N=48 enumeration: peak working set 1,366,290,432 bytes, 2,153 s wall,
  30 s interval samples on record
- batch transport: peak 16,853,617 bytes over the overlimit set
- ladder receipts record FD/handle/thread counts and before/peak/after
  memory per level

## 9. Supported CPython matrix

- Local: every suite green on CPython 3.12.10 (Windows x64); the sandbox
  suite additionally green on CPython 3.14.5. Matrix plan fully settled —
  every profile entry now binds its expected count (matrix 44, model 17,
  oracle 35, live 29, concurrency 15, sandbox 76) — and the matrix suite
  passed twice consecutively with no new evidence after final settlement.
- Hosted: **not run.** The workflow (`.github/workflows/portability.yml`,
  read-only permissions, branch-limited triggers, SHA-pinned actions) fires
  on the first authorized push. Normative CPython 3.12/3.13/3.14 across
  ubuntu/macos/windows on x64 and arm64 remains PENDING with
  `INFRA_UNAVAILABLE` as the only admissible absence record.

## 10. Alternative-runtime observations

Stress-only and off-contract entries (CPython 3.14t with GIL receipt,
dev-mode, pydebug, PyPy, GraalPy below the 3.12 floor) are defined and
labeled in the plan; no local evidence exists and none is claimed. Hosted
observations remain pending with the matrix.

## Findings inventory

Every finding file under `portability/*/findings/` (and the sandbox lane's
flat `F-SANDBOX-*.md`) carries its own disposition. Adjudicated in this
finishing pass: F-MODEL-003 (resolved; receipt admitted), F-LIVE-005 and
F-LIVE-006 (corrected; four-round refutation to no-new-evidence),
F-SANDBOX-022 (corrected; five-round refutation to no-new-evidence). No
accepted-implementation divergence was established anywhere in the
portability effort: every finding is a defect in a model, oracle, harness,
workflow, receipt validator, or sandbox validator. Local Docker remains an
honest `INFRA_UNAVAILABLE`; the sandbox correction rests on static checks
pending the hosted Linux daemon.

## Open items (all James-gated or downstream of his gate)

1. First push of this branch — triggers the hosted matrix; requires
   explicit current-turn authorization.
2. Collection and reconciliation of hosted normative, stress,
   expanded-gate, and Linux sandbox receipts into this report.
3. Ledger close, terminal return, and the second (close) push.
4. Task-claim closure after (1)–(3).

## Nonclaims

No efficacy, novelty, security, fuzzing-completeness, external-standard,
or universal-portability claim. The proof tier stays `internal held-out`.
The charter's full success statement — independent cross-platform,
cross-architecture, cross-runtime, bounded-state, and transport-scheduling
validation finding no divergence within the stated environments and bounds
— is **asserted here only in its local scope**: bounded-state and
transport-scheduling validation on local CPython 3.12.10 (plus 3.14.5 for
the sandbox suite) found no divergence within the stated bounds, with
everything outside the model reported as outside the model. The
cross-platform, cross-architecture, and cross-runtime clauses remain
contingent on the hosted receipts.
