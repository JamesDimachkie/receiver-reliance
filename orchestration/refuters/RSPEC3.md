# RSPEC3 twice-corrected generation-0.5 proposal consistency refutation

## Verdict

**REJECT-WITH-FINDINGS.** The second corrections close all five RSPEC2
blockers. The reference-union sources and feasible fixtures now agree, direct
and compact selectors use the same four-way taxonomy, compact pointer overflow
has an exact 4095/4096/4097 boundary, successful expansion has a complete CLI
shell, and direct errors have a phase-exact request-ID law. Exit codes 0 through
4, negotiation, receipts, and frozen-path preservation also cross-check.

Two new blocking omissions remain in rules the drafts claim are closed and
implementable: the applicability profile identifier has no exact admitted
string language, and the compact error algorithm alternates between a joint
common/target candidate pool and phase-local selection. Each permits two
different byte-exact responses for one request. Neither is one of the honestly
listed adoption choices.

This verdict does **not** reject the drafts because their 0.5 schemas,
registries, fixture packs, implementations, and receipts do not exist yet.
Those artifacts are correctly presented as future adoption work. It rejects
only present normative text that does not determine the bytes those artifacts
must implement.

## Review base and replayed commits

- Required integration base, resolved exactly:
  `8a30d1aaa13e5bfddb84df9cc6db2731fd8e0d8b`.
- P7 `75de333c8429a5502f20597339c25ce073fac8a5`, replayed as
  `88dbf18d309e07177c74ed3a2dae93130c0529b8`.
- P8 `ba45778e2821dfce9b295f994fc3844c4eaaf90e`, replayed as
  `29df20875c903d04c5152139e8823343179ffc2a`.
- P7 correction 1 `9b26bb0ba0c0c33b0b0c3c467cca3dca3af3ace1`,
  replayed as `14bd5b501fb10287cf3ab6c406f2e65ebdb61fe1`.
- P8 correction 1 `07331b59323951fa518db5257143953229eb039d`,
  replayed as `4ee290824f82f610b528e6b7b9f281e7eec00f68`.
- P7 correction 2 `314a9dd948a202800ff01082efeb982b1cdbc037`,
  replayed as `44dac3605812aa5f185bade01497f933d462446f`.
- P8 correction 2 `5b137ca480acc3a046bc7ad1ae6ac18efe9002e3`,
  replayed as `1f88ee0663fdb54cc2f99a3b44d4d4f3eaeeff23`.
- The final core and semantic blobs exactly match their respective correction-2
  source commits (`c05b7945...` and `4e1d6bb1...`).

Primary authorities consulted were both proposal files, both prior RSPEC
reports, `README.md`, `ERRATA.md`, `HOST_OBLIGATIONS.md`, `ACCEPTANCE.md`, the
accepted and supplemental control/fixture bytes, the accepted runner,
`grounded-0_4/rr_api.py`, the authority/closure artifacts, and the committed
proof protocol/results.

## Reproduction of every RSPEC2 blocker

| RSPEC2 blocker | Second-correction evidence | Disposition |
|---|---|---|
| R1, impossible empty INAPPLICABLE reference fixture and absent-source ambiguity | Core section 4.5 now makes each absent branch source contribute zero, rejects invalid present/required sources before derivation, and section 7 assigns empty only to APPLICABLE and duplicate/64/65 to INAPPLICABLE (`CORE:432-480`, `:627-640`). The semantic draft repeats the branch table and exact split (`SEMANTICS:318-500`). | **Closed.** Empty INAPPLICABLE is expressly forbidden, while all four required boundaries are constructible. |
| G1, malformed direct generation string had two classes | Both drafts use the exact syntax `^[A-Z0-9][A-Z0-9._-]{0,159}$`; missing is 75, non-string or malformed is 80, syntactically valid unknown/disabled/unavailable is 76, and recognized tuple contradiction is 80 (`CORE:90-119`; `SEMANTICS:42-54`, `:1144-1172`). | **Closed.** Direct `"?"` is unambiguously `ERR_SCHEMA`, not UNSUPPORTED. |
| C1, compact exact pointer could exceed its closed schema | The compact contract now performs common and target diagnostic-pointer budget passes before the corresponding candidates, admits length 4096, and maps greater lengths to sole root `ERR_LIMIT`; fixtures pin key lengths 4094/4095/4096 as pointer lengths 4095/4096/4097 (`SEMANTICS:1093-1095`, `:1197-1221`, `:1255-1261`; `CORE:144-150`). | **Closed for a standalone phase.** Mixed phase behavior is separately blocked by C3 below. |
| C2, successful compact process shell absent | Canonical expansion now writes exactly one direct-request JCS+LF value, writes empty stderr, exits 0, and invokes no engine. The parity list observes each property (`SEMANTICS:960-1003`, `:1273-1304`; `CORE:144-146`, `:659-662`). | **Closed.** Expander success and downstream-engine execution are distinct steps. |
| D1, direct-error request-ID echo undefined | Core section 4.1.1 defines the sentinel, a decoded single-key extraction boundary, every pre-tree failure, pre/post resource limits, duplicate-key treatment, valid-ID retention, and pre/post internal failures; byte-exact fixtures are mandatory (`CORE:287-328`, `:643-649`). | **Closed.** The response ID and therefore error receipt are derivable in every named phase. |

## Blocking findings

### A1 — `applicability_profile_id` is called bounded without any bound or pattern

The semantic draft calls the applicability object a closed schema, then defines
`applicability_profile_id` only as a “bounded non-empty string”
(`GEN_0_5_SEMANTICS.md:353-363`). No maximum length, CR/LF law, character
language, or named inherited schema is supplied anywhere else. The later
240-scalar rule applies only to strings that contribute to
`record_references` (`:442-466`); `applicability_profile_id` is not one of the
three candidate sources.

This is observable, not editorial. Consider an otherwise valid, correctly
sealed APPLICABLE request whose opaque host profile ID is 200 ASCII `A`
characters. An implementation using the repository's ordinary 160-character
ID bound emits `ERR_SCHEMA`/2. An implementation using the proposal's explicit
240-scalar reference-string bound as its nearest new-generation convention
accepts the field and reaches semantic classification. Both selected a finite
bound and therefore satisfy the literal phrase “bounded non-empty string.”
The response family, exit, output, and receipt all differ.

Counterevidence does not close the gap. OBL-24 expressly says its request arrays
use the **existing bounded string item schema** (`SEMANTICS:184-187`), and
OBL-30 expressly says its **existing bounds remain** (`:644-646`). The new
applicability field uses neither cross-reference. The open question about
whether profile IDs are opaque or registry-backed (`:573-575`) does not choose
a string language for the currently proposed opaque-ID branch, and the
adoption-question summary does not disclose the missing bound.

**Required resolution:** specify an exact schema (recommended: name a single
existing bounded-ID schema or give exact type, minimum, maximum, NFC, and CR/LF
rules), then add boundary fixtures at max-1/max/max+1 on both APPLICABLE and
INAPPLICABLE branches. If registry membership will replace opaque IDs, make
that the normative candidate rather than leaving the current opaque branch
under-specified.

### C3 — compact common/target errors have incompatible pooling phase laws

The compact draft describes one joint candidate set:

- common and selector candidates are constructed; and
- when the selector tuple and profile pins are available, target-specific
  candidates are **also added** (`GEN_0_5_SEMANTICS.md:1174-1184`).

Its phase text describes a different algorithm:

- after each pointer-budget pass, “construct the phase's candidates and select
  the one” (`:1223-1230`);
- registry and target validation occur only after a “common compact-schema
  pass” (`:1232-1236`); and
- an overlong target-phase pointer emits sole root `ERR_LIMIT` while claiming
  that no partial pool exists because candidate construction has not begun
  (`:1208-1217`), even though the common phase has already constructed its
  candidates under the preceding clauses.

A minimized ordinary-pointer counterexample uses an exact enabled tuple and a
valid pinned registry entry, but has both a malformed outer `request_id` and a
target decision input missing `/decision_input/facts`. Under the joint-pool
clause, both `ERR_SCHEMA`/80 candidates enter and the target pointer wins because
`/decision_input/facts` sorts before `/request_id`. Under phase-local selection,
the common phase emits `/request_id` and target validation never runs. The
sentinel is the same, but the selected pointer and self-zero error seal differ.

The 4097 interaction makes the split even sharper. Add a target-specific
overlong property path to the same common-schema-invalid request. A phase-local
implementation returns the common `ERR_SCHEMA`; an implementation that runs
the target budget pass follows `:1215-1221` and emits sole root `ERR_LIMIT`.
The required 4095/4096/4097 fixtures are expressly otherwise-valid compact
objects (`:1255-1259`), so they do not decide either mixed case. The general
“simultaneous ... candidates” fixture requirement does not say whether target
validation runs with a nonempty common pool.

**Required resolution:** choose one phase law and state it directly. Either
(a) fail closed after each phase—target pointer construction/validation occurs
only when the common/selector pool is empty—or (b) define a true combined pool,
including whether a later pointer-budget `ERR_LIMIT` discards earlier
candidates. Add byte-exact fixtures for common-schema plus target-schema,
common-schema plus target 4097-pointer, and common-schema plus selected-registry
corruption. Receipt bytes, request-ID choice, stderr, and exit must be pinned.

## Cross-surface assessment beyond the blockers

| Surface | Evidence and adversary | Assessment |
|---|---|---|
| Direct generation and no downgrade | Request selector is inspected first; only an exact supported request format permits response-offer interpretation; legacy bytes are never upgraded (`CORE:90-166`). Missing/non-string/malformed/unknown/disabled/unavailable/tuple cases are all fixture obligations. | Coherent. |
| Compact generation and no downgrade | Five positional selectors, unique profile-row selection, distinct legacy adapter format, and no fallback are exact (`SEMANTICS:875-958`, `:1005-1070`, `:1144-1172`). | Coherent apart from C3's mixed validation phases. |
| Direct request-ID and receipt | Single decoded top-level key after the safe-tree boundary owns every later echo; error receipt seals that exact choice (`CORE:287-328`, `:489-500`, `:590-592`). | Coherent; former D1 closed. |
| Compact request-ID and error seal | Raw/duplicate/root/invalid-ID failures use the sentinel; later selector/schema/registry errors echo a retained valid ID. The distinct error object self-zero-seals every field and exits 2/3 only (`SEMANTICS:1074-1141`). | Coherent once C3 chooses which later error wins. |
| Exit/schema closure | Direct VALID/defect/protocol/internal/INAPPLICABLE are 0/1/2/3/4 with closed mutually exclusive shapes; compact success is 0 and compact errors only 2/3 (`CORE:268-367`, `:599-604`; `SEMANTICS:994-1003`, `:1081-1129`). | Closed. No residual 3/4 alias. |
| Request/response seals | Direct input digest, complete self-zero envelope seal, output-sealing receipt, and compact-error seal all exclude LF and zero one named field only (`CORE:204-244`, `:489-500`; `SEMANTICS:29-41`, `:1117-1129`). | Coherent and nonrecursive. |
| Applicability branches | Facts/subject/basis presence is mutually exclusive and total; feasible empty/duplicate/64/65 reference fixtures agree across both drafts. | Reference union is closed. A1 prevents an exact schema for the shared profile ID. |
| Facts-derived references | Core admits only string leaves/items after schema validation; semantic text additionally makes non-string source values schema errors. The accepted OBL-02 schema admits `exact_reference:null`, and frozen fixture `SEMFX-OBL-02-CTRL-40AA7A46632A77A9` uses it. | Not a contradiction if the semantic draft deliberately versions null out before derivation, but it is a real 0.5 migration consequence. Adoption fixtures must pin `exact_reference:null -> ERR_SCHEMA`; silently inheriting the nullable OBL-02 branch would conflict with the semantic rule. |
| Standalone compact pointer boundaries | Escaping occurs before scalar-length measurement; exact 4096 is admitted; 4097 becomes root limit; no truncation or parent substitution (`SEMANTICS:1197-1221`, `:1255-1261`). | Closed for otherwise-valid common or target phases; cross-phase composition is C3. Direct E6 remains explicitly out of scope. |
| OBL-24 | Active digest-bound profile, required/allowed class and modality sets, duplicate/containment/subset predicates, fifth class, and a non-default compiler competence case agree (`SEMANTICS:84-290`). | Deterministic under the proposed default. Array byte-order and required-vs-allowed policy are honestly open adoption choices. |
| OBL-30 cardinality/order | One derived verdict per candidate, five ordered reasons, source-order projections, all-compatible selection, structural duplicate/order/pool checks, contradiction checks, omission checks, and exact VALID projections compose without a cardinality hole (`SEMANTICS:585-872`). Empty pools derive all-empty VALID; 64-row pools remain bounded. | Deterministic. Select-all, canonical order, and removed-field policy are honestly open choices rather than hidden ambiguities. |
| Fixtures and regeneration | Both drafts require new schemas, controls, semantic/error/wrapper/transcript fixtures, receipts, manifests, authority rows, and parity gates. No future count or digest is presented as if generated (`CORE:610-710`; `SEMANTICS:1382-1445`). | Complete at proposal level except the fixtures required by A1/C3. |
| Protected frozen surfaces | Candidate diff adds only the two proposal Markdown files. The final blobs match source commits; no baseline, supplemental, access, workflow, acceptance, example, attributes, license, fixture, receipt, proof, or implementation byte changed. | Preserved. |

## Counterevidence sought

1. **All RSPEC2 reproducers.** I rebuilt each former counterexample—empty
   INAPPLICABLE, malformed direct selector, 4097 compact property pointer,
   successful expander exit/stderr, and duplicate direct request IDs. Each now
   has one cross-file answer.
2. **Pointer/path boundaries.** I checked top-level ASCII key lengths
   4094/4095/4096, nested `/` and `~` expansion, missing children, additional
   properties, selector-unknown target skipping, and exact-tuple target
   validation. Only the mixed common/target phase order in C3 remained.
3. **Applicability bounds.** I searched both proposals for a definition or
   cross-reference for `applicability_profile_id`. The only occurrences call it
   bounded, show examples, state its attestation status, and ask opaque-versus-
   registry. No number or pattern exists. Candidate-source max 240 cannot apply
   because the profile ID is not a source.
4. **Reference-source compatibility.** The accepted OBL-02 schema path admits
   string or null at `exact_reference`; the cited frozen BINDING fixture uses
   null and grounded 0.4 ignores the null while deriving `REC_A`. The semantic
   0.5 text can intentionally reject it, but the future schema and migration
   suite must say so. I did not inflate this into a third blocker because
   semantic schema validation precedes core derivation.
5. **Exit and receipt search.** Every semantic INAPPLICABLE mention uses 4;
   every direct/compact internal error uses 3; compact error cannot use 1 or 4;
   expander-only success uses 0. No schema-family swap survived.
6. **OBL-24/30 edge profiles.** I exercised empty and maximum cardinalities,
   duplicate rows/IDs, reordered and shortened projections, wrong ordered
   reasons, compatible exclusions, incompatible selections, and all-empty
   OBL-30 input. Class precedence and canonical order remain derivable.
7. **Frozen diff and source fidelity.** `git diff --check` passed. The candidate
   is exactly 2,271 added lines in two new files; all protected path diffs are
   empty.

## Expanded validation gate

All commands ran from the required directories under CPython 3.12.10 with
`-B`. Every exit was 0.

| Gate | Result |
|---|---|
| Frozen 0.2 conformance | 800 checks, 0 failures |
| Composed 0.2 + 0.3 conformance | 800 + 107 checks, 0 failures |
| Grounded regression | 504 checks, 0 failures |
| Contract lint | 199-field census, 0 findings |
| Audit adversarial | 6,497 checks, 0 failures |
| Lint-gate meta-test | 7 checks, 0 failures |
| Deterministic properties | seed `0x5EED8785`, 2,296 checks, 0 failures |
| Proof harness | 7 tests, all passed |
| Deterministic fuzz smoke | seed `0x000000000B10F042`, 31/31 strategies, 0 failures, `budget_exhausted=false`; exits `0:2`, `1:2`, `2:27` |
| Patch hygiene and protected paths | `git diff --check` passed; no protected-path diff |

These results prove executable neutrality of the doc-only candidate. They
cannot select an applicability string schema or resolve contradictory future
compact candidate-pool phases.

## Honestly open adoption choices and residual uncertainty

The following remain open without constituting current blockers because the
drafts identify them as choices instead of asserting one settled answer:

- OBL-24's non-default competence profile, profile-array byte order, and
  required-versus-allowed equality;
- opaque versus registered applicability profile IDs, empty basis references,
  and whether every operation admits INAPPLICABLE;
- OBL-30 select-all policy, projection order policy, and removal of the two
  redundant legacy fields;
- exact compact template bytes, optional compact-input digest, and registry
  placement; and
- the core's future dispatcher, exact-wire digest, explicit reference-field
  registry, witness predicate ID, auxiliary-inner-request removal, and any
  keyed host protocol.

Direct-engine E6 diagnostic-pointer containment also remains an explicit
future contract-design item. The new 4096 rule belongs only to the compact
wire; the core correctly says it does not silently become a direct-response
rule. No 0.5 schema or implementation exists yet, so cross-platform proposed
bytes and seals remain untestable. This review is treatment-exposed and did
not author regenerated worlds, an oracle, gold outputs, or a renderer.

A1 is not excused by the opaque-versus-registry choice: the currently written
opaque branch still needs an exact admitted string language. C3 is not an
adoption policy choice: the draft already claims a total deterministic
expander and exact error wire.

## Exact diff summary

Before this report, the candidate diff from
`8a30d1aaa13e5bfddb84df9cc6db2731fd8e0d8b` was exactly:

- `continuation-specs/GEN_0_5_CORE.md`: new, 806 lines;
- `continuation-specs/GEN_0_5_SEMANTICS.md`: new, 1,465 lines.

This refuter adds only `orchestration/refuters/RSPEC3.md`. No candidate spec,
code, sealed artifact, workflow, dependency, fixture, receipt, manifest,
proof, acceptance, example, or protected byte was edited.
