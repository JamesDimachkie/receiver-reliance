# RSPEC2 corrected generation-0.5 proposal consistency refutation

## Verdict

**REJECT-WITH-FINDINGS.** The corrected drafts close the former exit-code
alias and supply a genuinely separate compact-expander error wire. The main
facts/applicability reference union is also now explicit enough to establish
one shared dedupe, ordering, cap, and truncation rule. The combined proposal
still cannot produce one unambiguous conforming implementation and fixture
set, however. Five minimized blocking inconsistencies or missing observable
rules remain.

This verdict does **not** reject the drafts for being proposed rather than
adopted. They remain honestly marked **PROPOSED / NOT ADOPTED**, and the
absence of future 0.5 schema, registry, implementation, fixture, receipt, and
manifest bytes is not itself a finding. The blockers below concern rules the
drafts already claim to settle.

## Review base and replayed commits

- Required integration base, resolved exactly:
  `ab863d93b9ad672689f18e14511ce7cedbff96bf`.
- Original P7 commit `75de333c8429a5502f20597339c25ce073fac8a5`,
  replayed as `8256a7b79530b60a980f60638e9fe13d14a9c874`.
- Original P8 commit `ba45778e2821dfce9b295f994fc3844c4eaaf90e`,
  replayed as `43aa0b85a07ade667ea3a0a3fb5be2df4e264953`.
- P7 correction `9b26bb0ba0c0c33b0b0c3c467cca3dca3af3ace1`,
  replayed as `f0f1b47a707c5a809bd505bf1dec55c97cf331a9`.
- P8 correction `07331b59323951fa518db5257143953229eb039d`,
  replayed as `9d75d31fa2eabb017d700586a9857a490720091c`.
- Reviewed proposal paths:
  `continuation-specs/GEN_0_5_CORE.md` and
  `continuation-specs/GEN_0_5_SEMANTICS.md`.
- Frozen and additive authorities consulted: `README.md`, `ERRATA.md`,
  `HOST_OBLIGATIONS.md`, the accepted and supplemental control contracts,
  the frozen OBL-24 and OBL-30 fixture/table bytes, the accepted 0.3 runner,
  the grounded 0.4 authority/closure surfaces, and the committed proof
  results.

## Disposition of the three prior blockers

| Prior blocker | Corrected disposition | Assessment |
|---|---|---|
| B1, INAPPLICABLE references had no source | The facts, subject, and basis candidates now enter one JCS-byte dedupe, unsigned-UTF-16 order, 64-cap, and truncation law in both drafts (`CORE:366-407`; `SEMANTICS:423-470`). | **Partially closed.** The semantic result is now derivable for the intended examples, but the cross-file fixture mandate is impossible and absent-source treatment should be made total; see R1. |
| B2, exit 3 aliased INAPPLICABLE and internal error | Both drafts assign semantic INAPPLICABLE exit 4, direct/compact internal error exit 3, ordinary protocol error exit 2, semantic defect exit 1, and VALID exit 0 (`CORE:252-259`, `:288-296`, `:458`, `:516-521`; `SEMANTICS:385-421`, `:1041-1074`). | **Closed.** I found no remaining 3/4 alias or incompatible class/schema obligation. |
| B3, compact failure surface absent | Section 5.7 now defines a unique closed error wire, self-zero seal, exact error rows, request-ID rule, selector taxonomy, candidate pooling, pointer selection, stdout/error exits, and fixtures (`SEMANTICS:1029-1191`); core expressly delegates compact failures to it (`CORE:116-126`). | **Partially closed.** Error ownership is now distinct, but the claimed total surface cannot encode a permitted long-property error and does not close the successful CLI ABI; see C1 and C2. |

## Blocking findings

### R1 — the reference-union fixture mandate requires an impossible empty INAPPLICABLE request

The core requires each of the empty, duplicate, exactly-64, and greater-than-64
combined-source cases to pin the result on **both** applicable and inapplicable
branches (`GEN_0_5_CORE.md:544-548`). The semantic schema makes an empty
INAPPLICABLE union impossible:

- the inapplicable branch forbids `facts` (`GEN_0_5_SEMANTICS.md:332-349`);
- `subject_record_id` is a required non-empty string for that branch
  (`:351-359`); and
- the corrected fixture list consequently assigns the empty boundary only to
  APPLICABLE, while its INAPPLICABLE fixtures contain a subject and optionally
  basis references (`:456-470`).

Every schema-valid INAPPLICABLE request therefore contributes at least its
subject, so no fixture author can satisfy the core's empty-INAPPLICABLE
requirement. The shared algorithm also should state explicitly that an absent
branch-only source contributes the empty sequence: core step 1 walks `facts`
without a presence qualification and step 3 reads `basis_record_refs`
unconditionally (`CORE:372-386`), while the two decision-input branches make
one or the other absent. The semantic restatement qualifies absent `facts` but
not absent basis (`SEMANTICS:429-438`).

**Required resolution choice:** preferably state that every absent source
contributes zero candidates, keep `subject_record_id` required for
INAPPLICABLE, and replace the core's “each case ... on both” mandate with the
exact feasible split already described by the semantic draft: empty on
APPLICABLE; cross-source duplicate, 64, and 65 on INAPPLICABLE; plus any
additional branch-parity cases desired. Alternatively, make the inapplicable
subject optional and define what an empty declaration means, but that is a
materially different applicability schema and attestation contract.

### G1 — a malformed direct generation string selects two different error classes

The direct core makes no syntax subclass for a present string. Any request
`format_version` string other than an exact enabled value is
`ERR_GENERATION_UNSUPPORTED` at precedence 76 (`GEN_0_5_CORE.md:94-105`). The
semantic draft's unqualified common generation rule instead assigns a
“malformed” declaration `ERR_SCHEMA` at precedence 80, reserving UNSUPPORTED
for syntactically valid but unrecognized/disabled/unavailable values
(`GEN_0_5_SEMANTICS.md:43-50`). Section 5.7 later defines the syntax distinction
for the **compact** selectors (`:1101-1128`), but section 1 does not limit its
statement to that surface.

A direct-core request with `format_version:"?"` therefore has two normative
answers: UNSUPPORTED/76 under the core and SCHEMA/80 under the semantic draft.
The same conflict applies to a malformed string response offer after a valid
request format. Different precedence, code, message, and receipt bytes result.

**Required resolution choice:** preferably qualify the semantic section-1
summary: direct-core non-string declarations are SCHEMA and every other
non-exact string is UNSUPPORTED, while compact selectors alone use the
section-5.7 syntax/tuple taxonomy. Alternatively, add the same selector syntax
law to core section 2.2 and deliberately change its present-string rule and
direct fixtures. One rule must own each wire.

### C1 — a permitted compact additional-property error cannot fit the closed error schema

The compact error schema caps `errors[0].pointer` at 4096 Unicode scalar values
(`GEN_0_5_SEMANTICS.md:1052-1055`). The candidate law requires an additional
property to point to that property and preserves the complete RFC 6901 pointer
(`:1130-1159`). The compact schema is closed, but no property-name or
constructed-pointer limit below 4096 is stated.

A canonical compact object under the 16 MiB input cap can therefore contain an
otherwise ordinary additional top-level property whose ASCII name is 5,000
characters. It deterministically creates an `ERR_SCHEMA` candidate with a
5,001-character pointer. The required selected error cannot validate against
the error schema, and no truncation, parent-pointer substitution, or pre-pool
resource-limit rule handles it. This is the same shape of conflict disclosed
for a frozen wrapper in `README.md:129-133`; a new wire described as total
cannot silently reproduce it.

**Required resolution choice:** define an explicit pointer-construction
resource phase before candidate pooling (for example, an over-limit candidate
emits only root `ERR_LIMIT`, as the phase-boundary law already permits) and pin
the 4095/4096/4097 boundaries, or widen the error schema and define output-cap
containment for the maximum permitted input path. Exact-pointer truncation is
not an acceptable implicit choice.

### C2 — successful compact expansion has no process exit or stderr contract

Canonical expansion is called a total deterministic function and ends by
atomically emitting the direct request bytes (`GEN_0_5_SEMANTICS.md:926-963`).
Failure behavior is fully process-shaped: exact stdout, empty stderr, and
sealed exit 2 or 3 (`:1031-1088`). No clause assigns the successful expander
process an exit code or requires empty stderr, and the compact parity list
checks successful request/response bytes without checking that process shell
(`:1193-1226`).

Thus two executables can emit identical correct direct-request bytes but exit
0 versus 1, or differ on stderr, while satisfying every stated successful
parity assertion. That leaves the requested 0/1/2/3/4 process contract
incomplete even though the downstream engine's exits are closed.

**Required resolution choice:** state that a successful expansion writes
exactly one direct-request JCS+LF value to stdout, writes nothing to stderr,
invokes no engine in expander-only mode, and exits 0; add those observations to
the expansion and cross-platform fixtures. If the expander is instead a typed
library-only API, remove the CLI emission/process language and define the exact
success/error return union; the current mixed surface cannot remain.

### D1 — direct-core error receipts do not have an exact request-ID echo law

The direct response clause says only that `request_id` echoes “a schema-valid
identifier when safely available” and otherwise uses the existing sentinel
(`GEN_0_5_CORE.md:261-262`). It does not define which raw-error phases produce
a safely available tree, how duplicate request-ID keys are handled, or whether
a valid identifier is echoed when another string/number/limit check fails.
Those choices change every error receipt byte.

This is not filled by the compact clause: compact deliberately gives its own
specific sentinel/echo law (`GEN_0_5_SEMANTICS.md:1090-1099`). The accepted 0.3
runner is counterevidence to assuming only one obvious behavior: it validates
the value from the parsed object in `_valid_request_id` and passes it to the
error builder (`baseline-run/implementation-output-0.3/pcb_runner.py:43-62`),
while its scanner can detect duplicate/NFC/number findings before dispatch.
The proposal neither normatively imports that precise parsed-tree behavior nor
chooses the compact rule. For a direct request with two different individually
valid `request_id` values under duplicate keys, sentinel versus parser-selected
echo are both plausible readings of “safely available.”

**Required resolution choice:** give the direct wire an explicit phase-by-
phase echo/sentinel law, including empty/oversize/UTF-8/BOM, duplicate-key,
JSON/framing, NFC, number, root type, generation, schema, limit, and internal
failures, and add byte-exact receipt fixtures. Either deliberately preserve
the accepted parsed-tree behavior or deliberately adopt the compact single-key
law for 0.5; do not leave “safely available” as the selector.

## Cross-surface assessment beyond the blockers

| Surface | Evidence re-derived | Assessment |
|---|---|---|
| Direct versus compact ownership | Compact-only failures use `B1-COMPACT-EXPANDER-ERROR-0.5`; only a successfully emitted sealed direct request reaches the target engine. Compact errors never fabricate a core receipt (`CORE:116-126`, `:581-584`; `SEMANTICS:1006-1088`). | Ownership is coherent apart from C2's missing success shell. |
| Exit/schema closure | Direct response branches uniquely bind 0 VALID, 1 semantic defect, 2 client/protocol error, 3 internal error, and 4 INAPPLICABLE; compact errors admit only 2/3 and forbid 4. Schema-negative swaps are required (`CORE:252-259`, `:288-296`, `:516-521`, `:549-551`; `SEMANTICS:1041-1074`). | Former B2 is closed. |
| Request and response seals | `decision_input_sha256`, complete self-zero request seal, semantic output, and self-zero response receipt have LF-excluded preimages and no recursive field ambiguity (`CORE:180-220`, `:409-424`; `SEMANTICS:29-41`). | Coherent. Core `:189-191` should editorially say the complete branch object includes `facts` only when present; the formula itself is unambiguous. |
| Reference union | Combined facts, subject, and basis candidates dedupe by JCS string bytes, sort by unsigned UTF-16 code units, cap after the union at 64, and set truncation iff distinct count exceeds 64 (`CORE:366-407`; `SEMANTICS:423-470`). A subject plus 64 unique basis refs makes the 65 case schema-feasible. | Algorithmic intent is coherent; R1 blocks the exact source/fixture contract. |
| OBL-24 | The active digest-bound profile, required/allowed class and modality sets, duplicate/containment/subset predicates, default five-class profile, and compiler competence case are mutually consistent (`SEMANTICS:80-290`). | No new blocker. Non-default profile bytes, profile-array canonical order, and required-versus-allowed equality remain honestly open. |
| Applicability | Mutually exclusive APPLICABLE-with-facts and INAPPLICABLE-with-attestation branches, pre-table selection, no effect receipt, empty unresolved reasons, fifth fixture class, and migration non-inference agree (`SEMANTICS:308-548`; `CORE:318-338`, `:428-436`). | Coherent except R1. Host truth remains expressly unattested by the engine. |
| OBL-30 | Five intent/candidate dimensions derive ordered reasons and one verdict row per candidate. Candidate order owns every projection; select-all-compatible fixes `D_selected`; all incompatible rows are excluded; duplicates/order/pool violations precede derived contradiction and omission checks (`SEMANTICS:550-838`). | Deterministic cardinality and order. Select-all policy, order treatment, and removed-field choice are disclosed adoption choices, not hidden ambiguities. |
| Negotiation | No downgrade/inference, distinct compact formats, a digest-pinned legacy 0.3 adapter, and exact enabled tuples are specified (`CORE:63-140`; `SEMANTICS:853-1027`). | Coherent except G1. Frozen 0.2/0.3 collision remains an explicit out-of-band deployment choice. |
| Regeneration/adoption | Both drafts require new schemas, controls, fixtures, receipts, manifests, wrappers, transcripts, authority entries, and gates; no proposed digest/count substitutes for generated artifacts (`CORE:527-609`; `SEMANTICS:1304-1354`). | Honest proposal status. R1 makes one current fixture mandate unsatisfiable. |
| Frozen preservation | The protected-surface table forbids legacy edits and keeps legacy errors, outputs, digests, effects, and dispatch unchanged (`CORE:611-627`; `SEMANTICS:18-20`, `:965-1004`, `:1351-1354`). | Confirmed by the actual candidate diff and green frozen gates. |

## Counterevidence sought

1. **Former B1 across every branch.** I tried to construct empty, duplicate,
   64, and 65 candidate unions under both branch schemas. Subject plus 64 basis
   refs proves the corrected cap is reachable and applied after union. It also
   proves the empty-INAPPLICABLE fixture cannot exist while subject is required.
2. **Former B2 across every exit mention.** I searched both drafts' response
   families, mapping tables, resource profile, error rows, schema obligations,
   fixture lists, migration list, and adoption gate. Every semantic
   INAPPLICABLE occurrence now uses 4 and every direct/compact internal error
   uses 3; no counterexample survived.
3. **Former B3 ownership and error shape.** I traced failures before profile
   selection, after selection, on registry corruption, after emitted-request
   mutation, and after engine invocation. The new distinct error format owns
   the first three categories correctly. C1 and C2 remained after looking for
   pointer overflow, success exit, success stderr, and success-shell fixtures.
4. **Direct request-ID inheritance.** I inspected the accepted composed runner
   rather than assuming the sentinel rule. It has an implementation-specific
   parsed-object echo path, showing why the proposal must choose rather than
   use “safely available.” No proposal clause or required direct fixture makes
   that choice exact.
5. **OBL-24 frozen authority.** The frozen schema and decision row confirm the
   two existing arrays, four baked-in class constants, and set-style
   `NOT_UNIQUE`/`NOT_CONTAINS_ALL`/`NOT_SUBSET_VALUES` behavior. The proposed
   registry compilation preserves those operator semantics while making the
   requirement set control-bound.
6. **OBL-30 frozen authority and valid fixture.** The composed contract confirms
   the intent tuple was inert and caller verdict/projection/disposition fields
   drove classification. The frozen valid fixture selects all compatible rows
   in candidate order and excludes the lure. The proposed `D_*` relation makes
   that policy explicit, detects coherent inversion, and closes selection
   shrinkage without inventing a rank cutoff.
7. **Generation adversaries.** I tested missing, non-string, malformed-string,
   unknown, disabled/unavailable, and recognized-but-contradictory selectors in
   the text. Compact has one exact taxonomy; the direct malformed-string case
   still has the G1 split.
8. **Pointer adversary.** I sought a compact property-name cap, parent-pointer
   rule, truncation rule, or pointer-construction resource phase that could
   defeat C1. None is present. The input and pointer caps admit the minimized
   5,000-ASCII-name counterexample.
9. **Frozen-byte check.** Before this report, the diff from the exact base was
   only the two new proposal Markdown files, 2,077 inserted lines. No sealed,
   implementation, workflow, dependency, fixture, receipt, manifest, access,
   acceptance, example, or proof byte changed. `git diff --check` passed.

## Validation gate

All available non-timing integration gates were run from the required
directories under PATH CPython 3.12.10 with `-B`. The active fuzz campaign
increased some elapsed times relative to the recorded matrix, but no command
timed out, no retry or smaller workset was used, and no assertion was weakened.

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
| Patch hygiene | `git diff --check` passed |

These gates prove that the doc-only proposal and corrections did not alter
accepted executable behavior. They cannot choose between conflicting future
normative outcomes.

## Residual uncertainty and honestly open design choices

- No 0.5 schema, registry, fixture, implementation, or receipt bytes exist by
  design. Future schema-combinator pointer projection and artifact seals remain
  untestable until adoption artifacts are authored.
- The direct 0.5 error-pointer schema has not been issued. I did not elevate
  the frozen E6 pointer-cap non-closure into a separate finding because the
  drafts do not claim to close E6 and do not yet choose a direct pointer cap.
  It remains an adoption risk. C1 is different: the compact draft already
  asserts a closed 4096-scalar error schema and a total exact-pointer law.
- Open choices remain exactly those disclosed by the proposal: OBL-24's
  non-default competence profile and set/canonical-order choices;
  applicability-profile registration, empty basis refs, and operation
  admission; OBL-30 select-all/order/removed-field choices; and exact compact
  template, optional compact-input digest, and registry placement. Resolving
  one may require new proposed bytes but is not evidence of a hidden present
  contradiction.
- Validation covered one local Windows/CPython 3.12 environment. The current
  deterministic properties exercise JCS and UTF-16 ordering, but future 0.5
  cross-platform byte parity remains an adoption obligation.
- This review is treatment-exposed and did not author regenerated research
  worlds, an oracle, gold outputs, or a renderer.

## Exact diff summary

Before this report, the candidate diff from
`ab863d93b9ad672689f18e14511ce7cedbff96bf` was exactly:

- `continuation-specs/GEN_0_5_CORE.md`: new, 705 lines;
- `continuation-specs/GEN_0_5_SEMANTICS.md`: new, 1,372 lines.

This refuter adds only `orchestration/refuters/RSPEC2.md`. No candidate spec,
code, sealed artifact, workflow, or dependency byte was edited.
