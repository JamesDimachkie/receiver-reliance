# Receiver-reliance criticism adjudication

Status: **PHASE 0 COMPLETE — work-package implementation may begin only after
this file is committed.**

Authority: `MASTER_PROMPT_RR_ROBUSTNESS_20260811.md`, raw SHA-256
`49A1A9799B73EA3EF1343F8B1CD9D608B166C48824162E4683CDBE0D2A983C79`.
The evidence tree is repository commit
`9bbf687398aeea60c5bbe65c77d51b1c43197b28`. Every citation below means the
bytes at that commit, not a moving working-tree path.

## Decision rule

Each seeded criticism receives exactly one charter class. Where a criticism
combines an already-disclosed design boundary with a remaining usability gap,
the entry is classified by the response still owed; the disclosed boundary is
recorded as evidence, not as a second classification. A criticism is not
`INVALID` merely because the repository already admits it.

The Phase 0 evidence set is raw-SHA-256 bound as follows:

| Evidence | Raw SHA-256 |
|---|---|
| `README.md` | `B97C8A408E48E8AF0907FA8AAF5661800BAFD53C0B0A0526AB477B73A7780EBB` |
| `HOST_OBLIGATIONS.md` | `F536254D3C6D09379D40EBB2CB744C6109489146BEEF20B539BA1B70FCD0F222` |
| `ERRATA.md` | `910498AD7CC3C960299F5B60EEA97D1367E9C9499C76298A52BBDCFCEE8B1B7F` |
| `ACCEPTANCE.md` | `ABC6C7793A8F837D41952D9B894B569EE76AE9CA4FEA5CA90701B10359CF99D0` |
| `grounded-0_4/authority_register_0_4.json` | `35BCE854A0F502B04E74FCAB6F1AD3159DA5BDFA014C8ABCB4709022C25098E3` |
| `grounded-0_4/lint_contract.py` | `1B5A14E38A1BD3060B192F185493DEDE9C1F93C9D895640D4B3AD31A7D2249FA` |
| `proof/README.md` | `77595F0CD2E4FC923ED4F020FC880A0DA6B29C3C78116DEDE51A57C8176F6E68` |
| `proof/RESULTS.md` | `BBA637F1109268EA36D11EFF98F9D1B22D7A9BD1685C504B67B438BA5EC1F9A9` |
| `proof/results.json` | `3883F504C349D8884701586DB0B8B29744D094EBB6B7C6A5DB69456FAEC9C032` |
| `perf/PROFILE_BASELINE.md` | `7371C1E5A209B1E4B41A3150D26160ADD6E1DB7CEED70D745E791F4D8C4A35D7` |
| `perf/BATCH_O1.md` | `D50D1DEA1CBB326D7DF08089BD0D5BFADA386A9773912BCDD27647C3D4DA96AF` |
| `orchestration/FUZZ_CAMPAIGN.md` | `36E8D78A35159996A7CF3416CAA909123DE992A65B09ED2A903D5150E08EE508` |
| `orchestration/refuters/RI1.md` | `001D0448BECE4A5769FCFA73AB5B739D75B9692B329A520DC72A1AAFC81B1C53` |
| `orchestration/refuters/RI2.md` | `12DFC861983A4146C4C0B2ED2451C564F89AC35AFE24B4F8C8F68999E59D0FEF` |
| `orchestration/refuters/RI3.md` | `6AF1D2B4DC7467CA1F2AC85DAE279B35DFF6EBC61ACD229E50E839D422DCB735` |
| `orchestration/refuters/RI4.md` | `19A0C244D88FD6CE49CFE8AEB646091DDC12DA89CECA92B7F3E05DF274A95FFE` |
| `orchestration/refuters/RSPEC3.md` | `D2810E8AFC8386A2C342D787FD1DB2B0326B2B9961E5DCC95A5B3C8DE492A782` |

The authority lint was also executed at launch and reported 199 required fact
fields (`semantic=111`, `presence_only=64`, `inert_disclosed=10`,
`inert_registered_debt=14`) with zero findings.

## Seeded criticism 1 — high host integration burden

**Classification: ADDRESSABLE-ADDITIVE. Pre-adjudication confirmed and
normalized to one class.**

The division of responsibility is real and already disclosed. `README.md`
section “What this is” says the engine classifies caller-assembled fact
profiles and does not retrieve state, enforce policy, or execute effects.
`HOST_OBLIGATIONS.md` H1–H6 assigns truthfulness, atomicity, derivation,
applicability, input binding, and effects to the host and gives a conformance
check for each. That design boundary is part of the decision-only identity and
is not to be erased.

The construction burden is nevertheless verified. `proof/README.md` reports
768 fabricated field values across 384 of 408 decisions, and the strict
adapter false-held 133 of 390 clean records when it forced an inapplicable
obligation. Existing disclosure does not give an adopter a reusable,
preflighted construction path.

**Promised response:** WP1 will ship the stdlib-only reference adapter,
obligation-naming preflight, calibration playbook, and adversarial tests. The
adapter and preflight are the affordance that makes H1–H6 operational rather
than merely acknowledged. Its outcome table must show the 34.1% baseline and
the new false-hold, abstention/refusal, and detection counts together; the bar
is near-zero false holds with the recorded 18/18 detections unchanged.

## Seeded criticism 2 — inert fields can be mistaken for validated fields

**Classification: ADDRESSABLE-ADDITIVE. Pre-adjudication confirmed.**

The factual premise is verified, and the artifact already discloses it.
`README.md` sections “What this is” and “What this does not claim” name
classification-inert and presence-only surface. `ERRATA.md` gives the census,
and `grounded-0_4/authority_register_0_4.json` plus the gate lint define the
machine authority. The launch lint reproduced 111 semantic, 64 presence-only,
10 disclosed-inert, and 14 registered-debt fields, totaling 199 with zero
findings.

The remaining gap is legibility: a caller must interpret the register rather
than ask the API, and no generated one-glance operation table is linked from
the public entry point. That makes a wrong validation assumption reasonable
even though the raw disclosure is accurate.

**Promised response:** WP2 will derive a programmatic authority query and a
deterministically generated per-operation table from the register itself,
never from a second hand-maintained list. Tests and the local gate must fail on
any byte drift between the table/API result and the register. A concise README
mechanism paragraph will be prepared for James's claims-change gate before any
carrying push.

## Seeded criticism 3 — contract-design non-closures

**Classification: CONTRACT-REVISION. Pre-adjudication confirmed.**

All three reported non-closures are pinned by current bytes:

- `ACCEPTANCE.md` and `ERRATA.md` E6 record that an exact RFC 6901 error
  pointer can exceed the frozen wrapper response's 240-character cap;
- the same records state that the wrapper transcript evaluator checks schema,
  envelope, echo, and seals but does not re-derive semantic classification;
  and
- the OBL-30 contradictory-exclusion disjunct is unreachable while its reason
  enum has one member.

These are not implementation bugs in the accepted generation, and the sealed
0.2/0.3 bytes cannot be edited. Additive documentation alone cannot make the
existing frozen clauses mutually satisfiable.

**Promised response:** WP3 Path A must resolve the RSPEC3 blockers and carry
the complete errata-prescribed next generation through fixtures,
author-separated implementation acceptance, and refutation to
NO-NEW-EVIDENCE. Each of the three items, plus abstention, ends only as
`CLOSED` with committed receipts or `BOUNDED` with exact trigger conditions.
After three same-class Path A failures, Path B ships the strengthened wrapper
evaluator and exact boundary documentation without changing the contract.

## Seeded criticism 4 — reimplementation friction / not plug-and-play

**Classification: ADDRESSABLE-ADDITIVE. Pre-adjudication confirmed and
normalized to one class.**

The “not an SDK” portion describes the disclosed decision-only boundary, not a
false promise: `README.md` presents a comparator/reference implementation and
`HOST_OBLIGATIONS.md` leaves operational integration to the host. The absence
of a conforming second implementation, however, is verified negative evidence.
`RI1.md` through `RI4.md` record four successive byte-observable divergences:
UTF-16 member ordering, escaped lone-surrogate handling, missing-LF
duplicate-key precedence, and ordinary duplicate-key pointer selection. The
fourth report explicitly rejects the treatment-exposed patched candidate as a
fresh independent implementation.

**Promised response:** WP4 will start from contract/schemas/fixtures under new
author separation, replay all four minimized failures as its opening
regression set, publish a reimplementer's guide, and run deterministic
coverage-guided differential evidence at no fewer than 50,000 identities. It
earns admission only at zero divergence after a full refuter pass returns
NO-NEW-EVIDENCE. After three same-class failures, the guide and newest
minimized divergence set ship as the named fallback. WP1 and WP5 separately
make host integration and the long-lived execution shape concrete without
claiming an SDK.

## Seeded criticism 5 — no native abstention for inapplicable contexts

**Classification: CONTRACT-REVISION. Pre-adjudication confirmed.**

`ERRATA.md` E7 and `HOST_OBLIGATIONS.md` H4 state that every current operation
demands a full fact profile and the sealed contract has no abstention state.
The proof makes the consequence numerical: forcing OBL-17 onto records with no
acknowledgment semantics produced 133 false holds among 390 clean records
(34.1%); calibrated host refusal produced zero false holds while retaining
18/18 defect detections. The calibrated result is an honest host-side
workaround, not native contract closure.

**Promised response:** WP1 first makes applicability preflight mechanical and
reports refusals separately. WP3 must then add the explicit `INAPPLICABLE`
declaration, its fixture class, and competence/metamorphic cases that reject
both overclaiming applicability and eager abstention on decidable records. The
published outcome table must move 34.1% near zero while keeping 18/18
detection; counting abstentions as passes is forbidden.

## Seeded criticism 6 — integration-path performance

**Classification: ADDRESSABLE-ADDITIVE. Pre-adjudication confirmed.**

The cost difference is measured, not speculative. `perf/PROFILE_BASELINE.md`
reports a 5.119 ms in-process median and 154.984 ms fresh `-I -B` stdio median
over 124 semantic fixtures, a paired 30.274x ratio on the recorded host. It
attributes the latter to process creation, interpreter startup, imports,
engine work, and pipes rather than claiming digest math is the cause.
`perf/BATCH_O1.md` proves the existing persistent NDJSON path at a measured
5.305 ms/request and 2,160 parity/transport checks, but also records sequential
blocking plus concurrency, cancellation, queue, and backpressure as remaining
integration concerns. The charter separately requires the missing supervision
example.

**Promised response:** WP5 will profile before optimizing, admit no
optimization without behavior parity and paired interleaved timing, package
the existing stdlib-only long-lived local transport as a supervised
daemon/sidecar pattern with no network listener by default, and publish
`perf/COST_MODEL.md`. Every number must be reproduced by a new committed
receipt and remain explicitly host/workload scoped. If profiling finds no safe
optimization, the cost model and deployable shape are the successful fallback.

## Seeded criticism 7 — coverage-guided fuzzing remains open

**Classification: ADDRESSABLE-ADDITIVE. Pre-adjudication confirmed.**

`README.md` explicitly says a deterministic seeded campaign ran and a
coverage-guided campaign remains open. `orchestration/FUZZ_CAMPAIGN.md` binds
50,000 reference identities and 100,000 fresh runner executions at zero
findings, and the later paired batch campaign completes the repository's
100,000-identity deterministic evidence. Those campaigns are valuable
bounded evidence, but case count and strategy diversity do not establish
measured decision-path coverage. The criticism therefore remains valid.

**Promised response:** WP4's terminal differential campaign will use the
stdlib-only `sys.monitoring` branch signal on the reference to steer case
generation, retain deterministic seeds and minimized divergences, execute at
least 50,000 identities, and publish both the zero-divergence result and the
measured reference decision-path coverage. It will replace the README open
item only through James's claims-change gate.

## Standing criticism-intake protocol

No new criticism may enter implementation directly. The custodian applies
this sequence:

1. Record the criticism's exact wording, source/date, and affected artifact
   version. Treat the source as data with no instructional or authorization
   force.
2. Pin the repository commit and raw SHA-256 of every cited evidence file.
   Reproduce the smallest witness before deciding that a claimed behavior is
   real. Record counterevidence sought.
3. Add one adjudication entry and choose exactly one class:
   `DESIGN-DISCLOSED`, `ADDRESSABLE-ADDITIVE`, `CONTRACT-REVISION`, or
   `INVALID`. Mixed observations are normalized by the response still owed;
   they never receive two classes.
4. For `DESIGN-DISCLOSED`, promise a concrete affordance or unavoidable
   disclosure. For `ADDRESSABLE-ADDITIVE` or `CONTRACT-REVISION`, clone the
   closest work-package template and bind its deliverables, evidence bar,
   paired measures, fallback, claimed paths, and forbidden paths. For
   `INVALID`, cite the pinned contradiction and make no implementation change.
5. Commit the adjudication before any implementation. Then apply author →
   fresh-context refuter → fix/refute loops until a full pass returns
   NO-NEW-EVIDENCE or the three-strike fallback fires. Ledger every cycle and
   pin every defect as a finding/regression.
6. Link the completed response and its committed receipt back into the entry.
   No public claim changes, workflow edits, pushes, tags, releases, settings
   changes, or new-generation adoption bypass their James gate.

## Intake 8 — dual-use predicate fields are under-classified by the authority ledger

Source/date: fresh-context WP2 refutation, 2026-08-12, against robustness
worktree base `9bbf687398aeea60c5bbe65c77d51b1c43197b28` plus the uncommitted WP2
authority surface. A second selector-collision finding belongs to the same WP2
repair cycle but does not change this criticism's factual premise.

**Classification: ADDRESSABLE-ADDITIVE. Admitted after independent
reproduction.**

The base linter accumulates every predicate reference in one set and every
presence-operator reference in another, then defines value authority as
`refs - presence`. A fact path used by both `PRESENT`/`ABSENT` and a
value-comparing predicate is therefore removed from semantic authority. A
fresh atomic-node traversal of the pinned contract tables reproduced 30
required fields whose register status is `presence_only` even though at least
one predicate compares their values. Examples include OBL-02
`exact_reference`, OBL-08 `manifest_effect_sha256`, and OBL-29
`affordable_covering_query_id`. The affected base evidence is already pinned
above: `grounded-0_4/lint_contract.py` raw SHA-256
`1B5A14E38A1BD3060B192F185493DEDE9C1F93C9D895640D4B3AD31A7D2249FA`
and `authority_register_0_4.json` raw SHA-256
`35BCE854A0F502B04E74FCAB6F1AD3159DA5BDFA014C8ABCB4709022C25098E3`.

Counterevidence sought: the launch lint still reports zero findings and the
register/table byte-match is exact, but both derive from or reproduce the same
registered classifications; they do not independently distinguish a path used
only for presence from one also used for value comparison. The accepted
engine bytes are not implicated and remain untouched.

**Promised response:** WP2 attempt 2 will separate per-atomic-node presence
and value uses, correct the 30 register rows and their rationales, add mutation
tests that fail on dual-use under-classification, regenerate the public table,
and record both this defect and the selector-namespace collision as finding
files. The programmatic API, table, corrected register, and corrected lint must
agree exactly before a fresh refuter pass. No sealed byte or existing receipt
changes.

## Phase 0 disposition and order

All seven seeded pre-adjudications are confirmed after normalization to one
class per entry. None is `INVALID`. Intake 8 is the first post-launch
criticism admitted through the standing protocol. Work remains in the charter
order:

`WP1 → WP2 → WP5 → WP4 → WP3`.

The research program's blinded outcome-value experiment remains explicitly
out of scope and unchanged.

## Intake 9 — machine-local success does not establish a transferable integration

Source/date: James, 2026-08-12, after the first robustness cycles exposed
machine- and runtime-coupled failures in WP1, WP4, and WP5. The accompanying
GitHub traffic screenshot (raw SHA-256
`931B96CE0B4FB62D0552E0F98FF05E9C6327B9898CDA7501E688F3301A606AD8`)
shows 179 clones and 34 unique cloners in the displayed 14-day window. That
is an attention signal only: it is not adoption, efficacy, readiness, or
demand evidence and creates no public claim.

**Classification: ADDRESSABLE-ADDITIVE. Admitted after independent blocker
reproduction.**

The failures share one premise: an implicit local boundary was treated as a
portable contract. WP1 collapsed invalid native evidence and unavailable
native semantics into one `REFUSED` result and attempted to generalize host
truth that only an integration can observe. WP4 inherited CPython recursion
and integer-conversion behavior and loaded content-addressed authorities
without enforcing their pins. WP5 inferred request/response identity from
pipe timing instead of a response envelope bound to the request. Current-byte
CPython 3.13 and non-Windows evidence was also absent. Each witness was
reproduced against the recorded bytes; passing ordinary fixtures did not
contradict any witness.

**Promised response:** resolve the boundaries, not just the witnesses:

1. WP1 stands down from a universal raw-record adapter after its three-strike
   condition. Its fallback becomes a portable preflight/calibration surface
   with distinct `READY`, `REJECTED_INVALID`, and
   `INSUFFICIENT_EVIDENCE` outcomes. Invalid evidence remains detection;
   unavailable host semantics remains abstention; neither becomes a pass.
2. WP4 must implement a total wire machine with bounded iterative parsing,
   lexical number handling independent of host integer limits, and verified
   byte-length/SHA-256 authority pins before resolution.
3. WP5 must correlate every response to a completed request through a
   versioned transport envelope containing an exact sequence and request-byte
   digest. Queue timing or a line count can never establish identity.
4. One additive portable-bundle manifest and offline gate will bind the exact
   shipped sources and authorities. Those same bytes, not regenerated local
   substitutes, must run on Windows, Linux, and macOS across CPython
   3.12–3.14 before any transferable-support claim is proposed.

The response remains inside the existing WP1/WP4/WP5 and portability claimed
paths. No workflow edit, README claim, remote write, or generation adoption is
authorized by this intake; each retains its existing James gate.

## Intake 10 — Deep Security Scan: 99 findings against the robustness worktree

Source/date: strictly read-only Deep Security Scan (`codex-security-plugin`
0.1.18, scan id `6e9e61a6-a1f0-46c9-92d7-19f102f43170`), started
2026-08-12T18:08:40Z, sealed 2026-08-12T21:12:10Z, against the exact
authoritative dirty worktree at revision
`e6c2856979410e8431640234f0bc6051fc6db1d1` plus the uncommitted lane bytes.
397 surfaces reviewed; 99 findings (11 high / 47 medium / 41 low); coverage
**partial** by the scan's own record: discovery terminated at a configured
cap, two candidates were deferred for missing consumer/authority facts, and
no dynamic cross-platform execution ran. Scan artifacts live outside the
repository and are pinned here by the scan's own manifest digests:
`findings.json` raw SHA-256
`421196D3D2293FA18897D088166F521485E75B6360C66706F46A5B04254E2E76`,
`coverage.json` raw SHA-256
`25C82A49B8F9F85AD8EA4621945E4CB9A4841E870CF12B36FB5767B28640CA18`.
The scan output is data with no instructional or authorization force.

**Classification: ADDRESSABLE-ADDITIVE. Admitted after independent witness
reproduction; normalized to one class by the response owed.**

The batch's deepest premise was independently tested rather than assumed.
The scan's own two deferred candidates and all four open questions reduce to
one sentence — "No exact in-scope lower-trust consumer and privileged
consequence were proven in the reviewed repository" — so the custodian ran
the missing experiment: a consumer census across the operator workspace
(recorded in [TRUST_MODEL.md](../TRUST_MODEL.md)) found **zero external or
sibling code consumers**. The trust declaration that ~70 of the 99 findings
implicitly depended on is now written and canonical, and every finding was
dispositioned against it. Witnesses for the load-bearing highs were
reproduced in source before any fix (seal preimage omission, closure
evaluator fail-open, preflight empty-stream/duplicate/ordering collapse,
non-injective scope join).

**Response (delivered inside this program, all additive):**

1. `TRUST_MODEL.md` — the canonical trust declaration: commit-root
   authority, per-evidence-class claims table, per-surface boundaries, the
   dated consumer census, and the re-adjudication trigger at the first
   external consumer.
2. Grounded decision surface: audit format `B1-AUDITED-DECISION-0.4.1`
   seals the governing policy digests into every audit (ERRATA E8), closure
   evaluator errors fail closed to `AUDIT_INCOMPLETE` (E9), and the
   64-item record-reference cap is disclosed via
   `record_references_truncated`, backported from the GEN_0_5 draft §4.5.
3. WP1 portable preflight: the fail-closed boundary law
   (`adapters/findings/F-WP1-010` through `F-WP1-013`) — empty streams and
   duplicate members are never success, every control layer runs with
   REJECTED-over-INSUFFICIENT precedence, scope digests are injective —
   with the all-408 outcome replay byte-identical (0 false holds, 18/18
   detection preserved).
4. Second-implementation and sidecar findings route through their own
   WP4/WP5 author→refuter loops; portable-bundle findings through the
   portable lane; each is dispositioned in the appendix.
5. The remaining findings are recorded as a deferred set with an explicit
   blocking trigger, not silently dropped.

Full per-cluster and per-high dispositions:
[orchestration/robustness/INTAKE_10_SCAN_DISPOSITIONS.md](robustness/INTAKE_10_SCAN_DISPOSITIONS.md).
No workflow edit, README claim, remote write, or generation adoption is
authorized by this intake; each retains its existing James gate.
