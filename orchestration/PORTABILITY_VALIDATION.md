# Receiver-reliance portability validation — separated evidence report

Date: 2026-08-11

Branch: `sol/rr-portability-modelcheck-20260810` from baseline
`4e788d21e882a30bdda2aec3f780537161f81644`

Corrected clean source receipt HEAD:
`8a525b167b95a3b6b512282938199eba09594a24`

Authority: `MASTER_PROMPT_RR_PORTABILITY_20260810.md`
(SHA-256 `154A9E5397D5D5B5422FD5D7053E7D1E6C6544C5D0152866598E6DC990F9C478`),
executed to the adjudication freeze by Sol root, then finished under Fable
custody at James's direction of 2026-08-11 ("take it from here"), with the
adjudication handoff recorded in `PORTABILITY_FABLE_RETURN_20260810.md`. Codex
root then performed the 2026-08-11 corrective release audit documented below;
that historical handoff file is not a current-state authority.

Hosted evidence HEAD: `7facfa34bb7b841fd0a7d911f15b4da71efde95b`
(green run `31562391384`; receipts committed under
`portability/receipts/hosted/`)

Status: **LOCAL AND HOSTED EVIDENCE COMPLETE; CLOSE PUSH PENDING.** James
authorized and performed the first branch push on 2026-08-11/12. Four hosted
runs failed and drove harness repairs (F-MATRIX-013, F-SANDBOX-026/027,
F-LIVE-009/010/011 — all harness/validator defects, no
accepted-implementation divergence); the fifth run, on
`7facfa3`, passed every job. Section 12 records the hosted reconciliation.
Every category below is local evidence unless marked otherwise, and no
category is ever merged into a single pass count. The prose of sections 1–11
describes the corrective-release-audit state (`8a525b1`/`4c9250a`) and is
retained unedited except where marked "updated 2026-08-12"; hosted-pending
statements inside historical sections are superseded by section 12.

## Adjudication and decision record (Fable)

- **Bounded-state lane — Path A executed and ADMITTED.** The two prior
  complete receipts remain rejected (`081180E9...2B14`, pre-F-MODEL-001
  quotient unsoundness; `C27DEB15...D69E9`, F-MODEL-002 symbolic alias
  double-counting). The packet's eight preconditions were independently
  executed and passed — including alias exclusivity proven exhaustively to
  N=32 and retained-versus-streaming equivalence at every bound N=18..28 —
  before one post-F-MODEL-003 N=48 enumeration ran to exit 0 under durable
  file custody. Fresh refuter R-MODEL-3 attacked it across eight vectors;
  its full re-enumeration reproduced the canonical receipt body exactly.
  The historical pre/post receipt delta moved exactly 16,260,520 edges from
  admitted transitions to the excluded frontier. Verdict NO-NEW-EVIDENCE;
  receipt `CD6210F8...732E` admitted. This was the third complete N=48 receipt
  overall—and the first post-F-MODEL-003 attempt—under a three-strike
  stand-down rule; a third rejection would have closed the lane as
  quarantined-unresolved.
- **Live lane — F-LIVE-005 through F-LIVE-008 corrected and cleared.** The
  monitor's transport normalization is scoped to the physical read; every
  other loop-body exception is durably classified under the new
  `HarnessFaultError` (`HARNESS_FAULT`, replay exit 4). Four adversarial
  refutation rounds (R-LIVE-5) found three successively deeper renderer
  escapes and a two-axis stop-receipt evidence-overwrite defect
  (F-LIVE-006, also inherited by the frozen infrastructure writer); all
  repaired and regression-pinned. The corrective audit then reproduced two
  further defects: background-thread `BaseException` was lost and relabeled
  as transport failure (F-LIVE-007), and an OS-dependent ordinary short-write
  counter made otherwise identical replays disagree (F-LIVE-008). Both are
  repaired and pinned; the suite is 29/29.
- **Sandbox lane — F-SANDBOX-022 through F-SANDBOX-025 corrected and
  cleared.** Path dialect is
  validated before rendering with component-level UNC anatomy (including
  the `\\?\UNC\` namespace), and the mount source fails closed on
  surrogate-escaped text, NUL, quotes, commas, line feeds, and edge
  whitespace matched to Docker's actual Go grammar rather than Python's
  broader whitespace policy. Five refutation rounds (R-SANDBOX-22),
  including a proven CPython 3.12/3.14 `is_absolute()` divergence. The release
  audit additionally found first-match duplicate-summary authorization
  (F-SANDBOX-023), then stopped two clean local gate runs on real prefixed and
  CRLF transcript shapes (F-SANDBOX-024/025). All are repaired and pinned;
  the focused suite is 76/76 on both CPython 3.12.10 and 3.14.5.
- **Concurrency — admitted with its standing qualification** (below).
- **Oracle — admitted** within its fixture-closed scope (below).
- **Author separation held for the adjudicated lanes:** enumeration by one fresh agent,
  collection by the custodian, refutation by fresh-context Codex sessions
  that never authored the artifacts they attacked; refuter-blocked
  executions were resolved by running the refuters' probe scripts verbatim
  and reporting results back for their verdicts. The corrective release audit
  was a separate root pass acting on four independent child reviews and then
  on failures produced by the real clean gate; it is not represented as a new
  author-separated adjudication cycle.

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
  median batch/in-process ratio 1.181 in the final receipt)
- single-pass audit: 1,142 checks / 0 failures (benchmark mode)

These eleven commands are the charter §1 expanded gate. The final clean-source
run is durably recorded at
`portability/receipts/local-expanded-gate-release-audit.json`: status `PASS`,
11/11 commands, clean source HEAD `8a525b1`, raw SHA-256
`4039ED94D885B9001C4B18B70C76BD7D70F6158A43946556C9062D66E7B361A3`,
and embedded receipt SHA-256
`F50D05B07985D21F37F4A8B1ACBDCCDED4D7CEF370343C9039F0D90AF34F0309`.
Every stdout/stderr transcript is retained in canonical base64 and bound to
its byte count and SHA-256.

Two earlier clean-source attempts are retained as rejected validator history,
not gate failures: rejected1 stopped at command 3 on a valid prefixed count
summary (raw SHA-256
`31F9C49E8D7E808372A399C9E868D624533D2171D99FB4CBC37EDDDB2E42AA73`);
rejected2 stopped at command 8 on a valid CRLF unittest PASS transcript (raw
SHA-256
`B82AF20209165F3EBBDAD61C42F5454266693109EA2AE3BE0343EB1E4ADCDE53`).
Their findings are F-SANDBOX-024 and F-SANDBOX-025.

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
- durable independent traversal:
  `portability/model/receipts/N48-independent-refuter-20260811.json`, raw
  SHA-256 `3A8D4BF8FC862818A87F7B16B76D4565F32DBCF1507EB800490B193225BF9FF8`;
  status `PASS`, 2,031.969 s, canonical receipt body identical, both embedded
  receipt hashes `CD6210F8...732E`. It checked all 20,531,838 currently
  rejected alias-label opportunities. That broader opportunity count includes
  edges the old key-consumption rule already rejected and is distinct from
  the 16,260,520 historical migration delta.

## 6. Live transport schedules

- eight committed schedules replayed twice on both real pipe and
  socketpair transports, byte-identical PASS results; complete 812-partition
  W coverage with zero unplanned OS short writes
- focused suite 29/29 after F-LIVE-005 through F-LIVE-008
- stop classes: DIVERGENCE (exit 1), INFRASTRUCTURE_ERROR (exit 2),
  HARNESS_FAULT (exit 4) — a harness fault is never transport or
  divergence evidence. Stop-receipt identity is a full SHA-256 over schedule,
  transport, replay number, and completed-replay content; overwriting another
  stop would require a full-digest collision rather than the former 64-bit
  prefix collision. Monitor `KeyboardInterrupt` and `SystemExit` are re-raised
  exactly across the background-thread boundary after child cleanup.

## 7. Concurrency schedules

- clean-source v3 normative receipt
  `normative-release-audit-head-8a525b1-attempt3.json`, raw SHA-256
  `B1782A43E4E4615569948953FFC45659BF0A820BEB67136F73FEDFDEAFE29998`;
  clean-source smoke receipt
  `smoke-release-audit-head-8a525b1-attempt3.json`, raw SHA-256
  `8CBA926DFB61B2C729C5CEAB95FF89350B99AFAF03809CBDDEAF6B8AC7719030`;
  both bind clean HEAD `8a525b1`; focused suite separately 15/15
- P ∈ {1,2,4,8,16,32} at 200 requests per caller, paired identical-seed
  runs byte-matching; P=16,32 soaks at 1,000 requests per caller; library
  and process modes; 242,400 independently projected audited envelopes;
  fresh refuter independently recomputed every declared aggregate
- the old dirty attempt-3 receipts remain historical only. The current
  normative run was clean-source-bound and did not overlap another audit
  workload; its resource fields are still local observations, not a universal
  performance baseline. The
  semantic projection does not independently oracle every nested audit
  metadata field (e.g. `engine_generation`).
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
- Hosted (updated 2026-08-12): **run and green.** Normative CPython
  3.12/3.13/3.14 across ubuntu-latest x64, ubuntu-24.04-arm arm64,
  macos-latest arm64, windows-latest x64, and windows-11-arm arm64 — all 15
  runnable rows PASS at plan-bound counts; the three predeclared `macos-13`
  x64 rows are evidenced `INFRA_UNAVAILABLE` exactly as forecast. The
  hosted expanded gate (CPython 3.12.13, ubuntu) and the hardened Linux
  container sandbox gate also PASS. Full record: section 12. (This bullet's
  historical local counts above — matrix 44, live 29, sandbox 76 — describe
  the `8a525b1` audit state; the hosted-repair commits settled the plan at
  matrix 48, live 33, sandbox 77, and the reconciliation commit rebinds
  `verify-committed-receipts` at 154 checks.)

## 10. Alternative-runtime observations

Stress-only and off-contract entries (CPython 3.14t with GIL receipt,
dev-mode, pydebug, PyPy, GraalPy below the 3.12 floor) are defined and
labeled in the plan; no local evidence exists and none is claimed.

Hosted observations (updated 2026-08-12, none normative): CPython 3.14t
free-threaded PASS including the bounded concurrency ladder at
`P = 1, 2, 4, 8` × 200 requests; CPython 3.14 dev-mode PASS; pydebug
`INFRA_UNAVAILABLE` (no `Py_DEBUG=1` build); the three `macos-15-intel`
rows `INFRA_UNAVAILABLE` (native-execution probe lacked negative Rosetta
evidence); PyPy 3.11 `OBSERVED_DIVERGENCE` (first failing command
`matrix-receipt-tests`; PyPy 3.11 is below the 3.12 floor); PyPy 3.12
`INFRA_UNAVAILABLE` (setup could not provide the build); GraalPy 24.0
`RECEIPT_MISSING` — its receipt was rejected by the fail-closed validator
because GraalPy's `full_version` disagrees with its `version_info` release
metadata, and the row closed as no-valid-durable-receipt rather than
adopting the file's self-reported outcome.

## 11. Hygiene and custody

- `portability/verify_hygiene.py` reports `HYGIENE_PASS`: exactly 138
  intentional CR-at-EOL diagnostics in four raw custody captures, all four
  protected by exact file hashes, and zero unexpected diagnostics.
- The corrective diff itself passes `git diff --check`. Raw baseline-to-HEAD
  `git diff --check` remains nonzero only because `.gitattributes` intentionally
  preserves those four captured byte streams; rewriting them would destroy
  their published custody hashes.
- The prior ledger's future-dated 12:44/12:55 entries are explicitly rejected,
  not silently edited into plausibility. Current timestamps come from actual
  commits and machine-readable receipts.
- Current finding dispositions were swept for pending/refutation boilerplate;
  no stale current-status match remains. Historical discovery prose remains
  only where the file explicitly labels it as history.

## 12. Hosted execution and reconciliation (2026-08-12)

James authorized the first branch push. Five hosted runs of the
`portability` workflow followed on this branch:

| Run | Head | Conclusion | Adjudication |
|---|---|---|---|
| `31548278804` | `4c9250a` | failure | hosted sandbox preflight and observation validation defects → F-MATRIX-013, F-SANDBOX-026, fixed in `00479e6` |
| `31549925307` | `00479e6` | failure | replay identity and sandbox comparator not daemon-real → F-LIVE-009, F-SANDBOX-027, fixed in `baa7b20` |
| `31552953993` | `baa7b20` | failure | residual defects; author-separated review returned four corrections, applied in `254b248` |
| `31553920699` | `254b248` | failure | controller liveness and fault-schedule replay identity → F-LIVE-010, F-LIVE-011, fixed in `7facfa3` |
| `31562391384` | `7facfa3` | **success** | all 28 jobs green; receipts collected below |

Every failure was a harness, workflow, or validator defect with its own
pinned finding and regression; none established an accepted-implementation
divergence. The plan settled at matrix 48, live 33, sandbox 77 during these
repairs (model 17, oracle 35, concurrency 15 unchanged).

Green-run evidence, validated by the runner's fail-closed summary and
re-derived locally:

- **Normative:** 16 PASS — 15 matrix rows (CPython 3.12/3.13/3.14 ×
  ubuntu-latest x64, ubuntu-24.04-arm arm64, macos-latest arm64,
  windows-latest x64, windows-11-arm arm64, at plan-bound suite counts) plus
  the hosted expanded gate (11/11 commands, totals identical to the local
  gate: 800; 800+107; 504; lint 0; meta 7; 2,296; 6,497; proof 7; 31/31;
  2,160; 1,142). The three predeclared `macos-13` x64 rows are evidenced
  `INFRA_UNAVAILABLE`. Zero normative failures, zero gating errors.
- **Hardened Linux sandbox:** daemon-real Docker 28.0.4 build from the
  committed Dockerfile (hash-bound), read-only rootfs, all capabilities
  dropped, no network, private namespaces, non-root UID; inner 11-command
  gate PASS; outer host receipt PASS; container removed cleanly.
- **Stress/off-contract observations:** recorded in section 10; the PyPy
  3.11 divergence and the GraalPy invalid receipt are observations, not
  normative failures, exactly as the plan's evidence classes define.
- **Conformance workflow** (pre-existing) also green on `7facfa3`
  (run `31562391410`, three OS jobs).

Custody: all 27 durable artifacts (25 row/gate receipts, the matrix
summary, the sandbox host receipt) plus 17 secondary concurrency smoke
receipts are committed under `portability/receipts/hosted/` with a
hash-bound manifest (`MANIFEST.json`, raw SHA-256
`9DC261CA316C4F8E83342FE6AD24EBF15C3A21F3FD38AE6565EE28651569D5E6`) and a
provenance record (`PROVENANCE.md`). `portability/verify_receipts.py` now
re-verifies the manifest hash, enumerates the directory fail-closed,
re-hashes every listed file, and re-checks the summary's 28-row outcome
vector, counts, source bindings, the sandbox receipt's status and
Dockerfile binding, and the hosted gate's exits and load-bearing totals —
154 checks, 0 failures (tamper-tested against a mutated receipt and a
mutated manifest; both fail closed). `verify-committed-receipts` in
`plan.json` is rebound from 62 to 154 so the next hosted run gates on the
extended verifier.

Independent local revalidation: the committed summary validator, re-run
locally over the downloaded row receipts with the same inputs, reproduced
the runner's `matrix-summary.json` in every field except the absolute
receipt path inside the single invalid-receipt error string (environment
detail), independently re-deriving the GraalPy metadata rejection.

At the reconciliation state all focused suites are green locally —
model 17 (one platform-specific skip), oracle 35, live 33, concurrency 15,
sandbox 77, matrix 48 — with `verify_receipts` 154/0 and `HYGIENE_PASS`
(138 allowed raw-capture diagnostics, zero unexpected). The full
11-command expanded gate passed with every command green; the clean-tree
close receipt is bound after the reconciliation commit and recorded in the
ledger.

## Dogfooding audit: the validation system tested itself

The input to the 2026-08-11 release audit was commit `e42c635`, presented as
complete and ready to publish. The audit did not accept that assertion. It
used the same adversarial practices required of the portability lanes against
the harness, validators, receipts, documentation, and task-control record.
The release audit and this catalog's own falsification produced six new stable
finding IDs, a strengthening of one earlier finding, and nine
evidence, custody, or documentation catches in the corrective release audit.
The final publication-prose pass added six editorial corrections, recorded
separately below. The source corrections are
`a6c60d4`, `7f81dc7`, and `8a525b1`; machine-readable evidence closeout is
`4ea69dc`, followed by this documentation-only catalog. No
accepted-implementation source was changed.

Product boundary: none of the DG entries is a product defect or evidence that
the accepted implementation's runtime behavior changed. DG-001 through DG-016
concern the portability validation harness, validators, evidence, custody, or
claims. DG-017 through DG-022 are six additional editorial-only publication
corrections.

This is the consolidated dogfooding record. A "propagation stopped" entry
describes the false downstream conclusion that remained possible at
`e42c635`; it is not a claim that the false conclusion had already escaped
this branch.

| ID | Catch and minimal witness | Propagation stopped | Correction and durable proof |
|---|---|---|---|
| DG-001 | [F-LIVE-007](../portability/live/findings/F-LIVE-007.md): injected `SystemExit` or `KeyboardInterrupt` died in the monitor thread and resurfaced as `TransportError`. | A harness abort could be published and debugged as infrastructure evidence. | Preserve and re-raise the identical `BaseException` after child cleanup; pinned in the 29/29 live suite. |
| DG-002 | [F-LIVE-008](../portability/live/findings/F-LIVE-008.md): identical 106,372-byte pipe replays varied only in `os_short_write_count` (including 10/5 and 5/30). | Host scheduling could create a false transport divergence or flaky receipt. | Ordinary writes now cross one declared backpressure boundary and complete without exposing incidental syscall partitions; paired replay regression requires a stable zero count. |
| DG-003 | [F-LIVE-006](../portability/live/findings/F-LIVE-006.md) strengthening: the corrected evidence identity still used only 16 digest hex characters while prose made a categorical no-overwrite claim. | Different stops retained a 64-bit collision surface inconsistent with the evidence-durability claim. | Directory identity now uses the complete SHA-256 over schedule, transport, replay, and completed-replay evidence; both overwrite axes remain regression-pinned. |
| DG-004 | [F-SANDBOX-023](../portability/sandbox/F-SANDBOX-023.md): a zero-exit command could print a valid summary and a contradictory summary and pass because validators used the first match. | Contradictory command evidence could self-authorize a green expanded gate. | Every validator now requires one unambiguous summary, strict UTF-8 and exact integer counts; admitted transcripts are retained in canonical base64 with byte counts and hashes. |
| DG-005 | [F-MATRIX-012](../portability/matrix/findings/F-MATRIX-012.md): a runnable target could report `INFRA_UNAVAILABLE` from a stale or dirty checkout without a matching workflow SHA. | Missing platform execution could be attributed to the wrong source revision and still satisfy the matrix summary. | Every runnable outcome, including absence, must bind a clean checkout and exact expected SHA; missing, dirty, and wrong-SHA mutations fail. |
| DG-006 | [Concurrency status](../portability/concurrency/receipts/STATUS.md): the published `test_ladder.py` hash did not match the current file, while the then-current receipts recorded a dirty baseline despite prose calling them admitted current evidence. | Superseded concurrency evidence could be reused after its own source-binding rule invalidated it. | Clean-source smoke and normative receipts bind `8a525b1`, the current four source hashes, 32 worker runs, and 242,400 projections; the dirty receipts are explicitly historical. |
| DG-007 | Model custody and count semantics: the claimed independent N=48 replay had no committed machine-readable result, and prose blurred the 16,260,520 historical migration delta with 20,531,838 current rejected alias opportunities. | A correct bounded result could be repeated with an incorrect interpretation or without inspectable independent custody. | [Independent receipt](../portability/model/receipts/N48-independent-refuter-20260811.json) preserves the full traversal and exact canonical-body comparison; the report now separates both counts. Raw SHA-256 `3A8D4BF8FC862818A87F7B16B76D4565F32DBCF1507EB800490B193225BF9FF8`. |
| DG-008 | Gate custody: the prior final-gate assertion existed only in report and ledger prose; no committed machine-readable local gate receipt retained what each validator consumed. | A later reviewer could not independently reconstruct the claimed 11/11 decision. | [Final gate receipt](../portability/receipts/local-expanded-gate-release-audit.json) retains all 22 streams and their bindings. Raw SHA-256 `4039ED94D885B9001C4B18B70C76BD7D70F6158A43946556C9062D66E7B361A3`; embedded self-hash `F50D05B07985D21F37F4A8B1ACBDCCDED4D7CEF370343C9039F0D90AF34F0309`. |
| DG-009 | Current-state prose was internally contradictory: 36 finding status lines still said refutation was pending, matrix prose still called N=48 pending, and model prose gave the wrong runtime. | Readers or automation could propagate stale disposition and count state despite the terminal report. | Every finding now has a resolved or explicitly historical current disposition in its record or authoritative lane index; stale-status, placeholder, and broken-local-link sweeps pass. |
| DG-010 | Oracle status stated cross-platform, cross-architecture, and cross-runtime success even though hosted execution had not occurred. | Local evidence could be promoted into an unsupported universal portability claim. | Oracle and terminal report now state that those clauses remain contingent on hosted receipts. |
| DG-011 | Ledger completion times of 12:44 and 12:55 appeared inside a 12:37 commit whose files were written earlier. | Impossible chronology could be treated as a valid custody timeline. | The two entries are preserved as `REJECTED AS CUSTODY TIMELINE`; the corrective interval ends at 14:40 before the 14:41 evidence commit. |
| DG-012 | The claimed raw `git diff --check` hygiene gate was red: 138 intentional CR-at-EOL diagnostics in four byte-custody captures plus one unexpected blank-at-EOF diagnostic. | A blanket hygiene-PASS statement could conceal both protected raw bytes and a real unrelated defect. | The unexpected diagnostic was removed. `verify_hygiene.py` hash-binds and permits exactly the 138 custody bytes and fails on anything else; current result is 138 allowed, zero unexpected, 4/4 hashes. |
| DG-013 | [F-SANDBOX-024](../portability/sandbox/F-SANDBOX-024.md): the first duplicate-summary correction rejected all six real human-prefixed grounded summaries. | A fail-closed hardening change could block valid releases and be mistaken for a product failure. | Prefix-aware exact parsing is regression-pinned; rejected attempt 1 remains quarantined at raw SHA-256 `31F9C49E8D7E808372A399C9E868D624533D2171D99FB4CBC37EDDDB2E42AA73`. |
| DG-014 | [F-SANDBOX-025](../portability/sandbox/F-SANDBOX-025.md): the hardened unittest validator accepted LF but rejected the real Windows `OK\r\n` transcript. | Platform-specific line endings could create a false negative in the portability gate. | Normalize lines once, then require exactly one `Ran 7 tests` and one `OK`; rejected attempt 2 remains quarantined at raw SHA-256 `B82AF20209165F3EBBDAD61C42F5454266693109EA2AE3BE0343EB1E4ADCDE53`. |
| DG-015 | The authoritative external task claim still described `e42c635` as the current validated state after corrective source and evidence commits existed. | The control-plane record could direct later work to superseded evidence or imply terminal completion. | The claim now binds the corrective source/evidence state, remains `in_progress` and `needs_user=true`, and lists hosted reconciliation and closeout as pending. |
| DG-016 | Catalog falsification found that this report claimed every finding file carried its own current disposition, but ten Oracle files deliberately preserve discovery-time state and defer current disposition to the lane status index. | A reader could mistake historical Oracle correction instructions for unresolved current work or trust an inaccurate completeness claim. | The report now identifies [Oracle status](../portability/oracle/STATUS.md) as the authoritative disposition index and states accurately that each finding has a witness while final disposition may live in the record or its lane index. |

### Publication prose corrections (editorial only)

These six entries improve the publication record. They did not change
executable behavior, model counts, receipts, or the accepted product and must
not be cited as product defects or product-outcome improvements.

| ID | Editorial catch | Misreading prevented | Correction |
|---|---|---|---|
| DG-017 | [F-CONC-003](../portability/concurrency/findings/F-CONC-003.md) said only `adjudicated harness defect` and gave a path ambiguous from its directory, without identifying the current v3 evidence. | The stopped v2 receipt could be mistaken for unresolved current state, and readers lacked a direct authority path. | The finding now says `RESOLVED locally`, distinguishes the stopped v2 receipt from clean v3 evidence, and links the receipt and authoritative status index. |
| DG-018 | [F-LIVE-004](../portability/live/findings/F-LIVE-004.md) described its older `BaseException` boundary as the current correction, contradicting F-LIVE-005 and F-LIVE-007. | A maintainer could restore or document superseded exception classification. | The correction now states the current three-way boundary: expected physical-read `OSError` and closed-stream `ValueError` become transport evidence, ordinary loop-body `Exception` values become harness faults, and `KeyboardInterrupt`/`SystemExit` are re-raised in the caller. |
| DG-019 | [F-ORACLE-006](../portability/oracle/findings/F-ORACLE-006.md) and [F-ORACLE-008](../portability/oracle/findings/F-ORACLE-008.md) had resolved headers but live `must add` and `remain unexecuted` instructions. | Historical stop instructions could be propagated as unfinished current work. | Both records now state the implemented correction, place the stopped closures in discovery-time past tense, and link the completed clean refutations in Oracle status. |
| DG-020 | [F-SANDBOX-003](../portability/sandbox/F-SANDBOX-003.md) described its pre-correction evidence-free PASS path in present tense beneath a resolved status. | A reader could conclude that the current sandbox still accepted an evidence-free PASS. | The witness is now explicitly scoped as pre-correction, and the required correction is in past tense; the following paragraph remains the current corrected behavior. |
| DG-021 | The admitted N=48 run was called `attempt three` while its receipt summary called it `attempt 1`. | Two valid numbering schemes looked like contradictory custody records. | The report now states that it was the third complete N=48 receipt overall and the first post-F-MODEL-003 attempt. |
| DG-022 | Oracle status imported `bounded-state` and `transport-scheduling` success from other lanes into its Oracle-local conclusion. | A lane-local status could be cited for evidence that it did not own. | The statement is narrowed to independent fixture-closed and bounded hostile-boundary Oracle validation; hosted portability remains contingent. |

The six new finding IDs map to DG-001, DG-002, DG-004, DG-005, DG-013, and
DG-014. DG-003 strengthened F-LIVE-006. DG-006 through DG-012 plus DG-015 are
the original eight evidence, custody, or documentation catches; DG-016 is the
ninth, found while falsifying this catalog. Those 16 entries form the earlier
validation audit catalog, spanning harness and validator defects plus evidence,
custody, and claim corrections. DG-017 through DG-022 are six additional
publication-only editorial records. The combined 22-row audit log is not a
severity ranking or a count of product defects.

### Tracked finding inventory

The portability corpus currently contains 60 stable `F-*` records. This count
is an inventory, not a claim of 60 accepted-implementation bugs: the records
cover defects or invalid evidence in models, oracles, harnesses, workflows,
validators, and custody. Each record retains its own witness. Current
disposition is recorded either in that file or in an authoritative lane index;
notably, `portability/oracle/STATUS.md` indexes the 13 discovery-time Oracle
records.

| Lane | Stable records | Count |
|---|---:|---:|
| Model | F-MODEL-001 through F-MODEL-003 | 3 |
| Oracle | F-ORACLE-001 through F-ORACLE-013 | 13 |
| Live | F-LIVE-001 through F-LIVE-008 | 8 |
| Concurrency | F-CONC-003 | 1 |
| Matrix | F-MATRIX-001 through F-MATRIX-012 | 12 |
| Sandbox | F-SANDBOX-003 through F-SANDBOX-025 | 23 |
| **Total** |  | **60** |

### What the dogfood result establishes

The observed sequence was concrete: a candidate labeled ready was rejected;
minimized witnesses were retained; code-level defects became
regressions; evidence gaps became source-bound receipts; invalid receipts were
quarantined rather than rewritten; and a fresh final falsifier found no
remaining local publication blocker. Executable regressions now stop
recurrences of the code-level classes when the required gates run. Chronology,
scope wording, and external task-record consistency remain explicit review
obligations rather than falsely claimed automated protections.

This does not prove the absence of unknown defects, validate anything outside
the declared finite model, or substitute for the pending hosted platforms and
Linux daemon. It improves the reliability of release decisions and future
changes; it does not claim that the accepted implementation itself changed.

## Findings inventory

Every finding under `portability/*/findings/` (and the sandbox lane's flat
`F-SANDBOX-*.md`) has a current disposition in its own file or an authoritative
lane index. The Oracle discovery records intentionally remain historical;
`portability/oracle/STATUS.md` carries their current dispositions. Adjudicated
before the release audit: F-MODEL-003 (resolved; receipt admitted), F-LIVE-005/F-LIVE-006
(corrected; four-round refutation to no-new-evidence), and F-SANDBOX-022
(corrected; five-round refutation to no-new-evidence). Corrective release-audit
findings F-LIVE-007, F-LIVE-008, F-MATRIX-012, and F-SANDBOX-023 through
F-SANDBOX-025 are resolved locally and regression-pinned. No
accepted-implementation divergence was established anywhere in the
portability effort; each finding concerns a model, oracle, harness, workflow,
validator, sandbox, or evidence-custody defect. The hosted-repair cycle
added F-MATRIX-013, F-SANDBOX-026, F-SANDBOX-027, F-LIVE-009, F-LIVE-010,
and F-LIVE-011, all resolved and regression-pinned (section 12). Local
Docker remains an honest `INFRA_UNAVAILABLE`; the sandbox correction is now
additionally confirmed by the daemon-real hosted Linux container run
(updated 2026-08-12).

## Open items (all James-gated or downstream of his gate)

1. ~~First push of this branch~~ — done: James authorized and performed it;
   five hosted runs followed (section 12).
2. ~~Collection and reconciliation of hosted receipts~~ — done: committed
   under `portability/receipts/hosted/`, bound by the extended
   `verify_receipts.py`, recorded in section 12.
3. Second (close) push of the reconciliation and close-evidence commits —
   staged; requires James's explicit current-turn authorization.
4. Task-claim closure after the close push is verified on the remote.

## Nonclaims

No efficacy, novelty, security, fuzzing-completeness, external-standard,
or universal-portability claim. The proof tier stays `internal held-out`.
The charter's full success statement — independent cross-platform,
cross-architecture, cross-runtime, bounded-state, and transport-scheduling
validation finding no divergence within the stated environments and bounds
— is **asserted within, and only within, the executed evidence** (updated
2026-08-12): bounded-state and transport-scheduling validation found no
divergence locally (CPython 3.12.10 Windows x64; 3.14.5 for the sandbox
suite) or on any of the 15 executed hosted normative rows — CPython 3.12,
3.13, and 3.14 across Ubuntu x64/arm64, macOS arm64, and Windows
x64/arm64 — nor in the hosted expanded gate or the hardened Linux
container gate, with everything outside the model reported as outside the
model. "Cross-runtime" here means across those CPython versions and
builds; alternative implementations (PyPy, GraalPy) remain off-contract
observations, the three predeclared `macos-13` x64 rows remain evidenced
`INFRA_UNAVAILABLE`, and no claim extends to any environment, schedule, or
input outside the declared finite bounds.
