# RSPEC generation-0.5 proposal consistency refutation

## Verdict

**REJECT-WITH-FINDINGS.** The two drafts are correctly marked proposed, are
additive, and leave the frozen 0.2/0.3 artifacts untouched. Their principal
E1/E2/E3, OBL-24, and OBL-30 choices are otherwise traceable to the recorded
defects and pinned tables. They are not yet one implementable deterministic
0.5 contract, however. Three blocking contradictions or omissions must be
resolved in new proposal bytes before schema/fixture authors could derive one
unambiguous expected result.

This verdict does **not** reject the drafts because adoption artifacts are
intentionally absent. It rejects exact normative rules that conflict or fail
to define an observable result.

## Review base and scope

- Required integration base: `6f3dcceb208e1159686782e5550040802be7af9a`.
- P7 source commit, replayed unchanged: `75de333c8429a5502f20597339c25ce073fac8a5`
  as local commit `f9cf14a`.
- P8 source commit, replayed unchanged: `ba45778e2821dfce9b295f994fc3844c4eaaf90e`
  as local commit `301770a`.
- Reviewed proposal paths:
  `continuation-specs/GEN_0_5_CORE.md` and
  `continuation-specs/GEN_0_5_SEMANTICS.md`.
- Frozen authorities and additive evidence consulted: `ERRATA.md`,
  `HOST_OBLIGATIONS.md`, the accepted and supplemental contract JSON,
  frozen OBL-24/OBL-30 fixtures and decision tables,
  `grounded-0_4/authority_register_0_4.json`,
  `grounded-0_4/closures_0_4.json`, `grounded-0_4/rr_api.py`, and
  `proof/RESULTS.md` / `proof/results.json`.

## Blocking findings

### B1 — INAPPLICABLE record-reference output has two incompatible sources

The core makes `record_references` a facts-only derivation:

- `GEN_0_5_CORE.md:354-377` says traversal is evaluated **only** over
  `decision_input.facts`, and no matching fact identifier produces `[]`.
- `GEN_0_5_SEMANTICS.md:330-360` says the INAPPLICABLE branch **must not
  contain `facts`**. Its record-bearing material instead lives at
  `applicability.subject_record_id` and `applicability.basis_record_refs`.
- Nevertheless, `GEN_0_5_SEMANTICS.md:389-394` requires the INAPPLICABLE
  response to bind the declaration's record references **through the core
  sealed reference field**.

These rules cannot all hold. Under the core algorithm, every schema-valid
INAPPLICABLE request has no `facts` object to traverse, so neither the subject
record nor basis references can enter `output.record_references`. The complete
request seal and response receipt still bind their bytes indirectly, but that
is not the semantic draft's promised reference-field behavior.

Primary counterevidence confirms this is not inherited behavior that silently
fills the gap: `grounded-0_4/rr_api.py:175-197` traverses only the supplied
facts object, and `decide_audited` calls it with
`decision_input.get("facts")` at `rr_api.py:236`. The 0.5 core explicitly says
it mirrors that surface.

**Required resolution choice:** either (preferred) define the 0.5 reference
candidate set as the union of the facts-derived candidates plus
`applicability.subject_record_id` and every
`applicability.basis_record_refs` item, then apply one specified
dedupe/order/cap/truncation law; or explicitly specify that INAPPLICABLE emits
`record_references:[]` and remove the claim that the declaration references
appear in that field. Add fixtures for empty, duplicate, 64-item, and
greater-than-64 combined candidate sets.

### B2 — exit code 3 aliases abstention and `ERR_INTERNAL` while being claimed distinct

The exact mappings agree that semantic INAPPLICABLE exits 3
(`GEN_0_5_CORE.md:240-247`, `:276-284` and
`GEN_0_5_SEMANTICS.md:383-418`). The core also assigns exit 3 to the protocol
`ERR_INTERNAL` branch (`GEN_0_5_CORE.md:245-247`). The semantic draft then
states that 3 is chosen so command-line callers cannot confuse abstention with
"wire/runtime error (2)" and says adoption must reserve that code
(`GEN_0_5_SEMANTICS.md:414-418`).

That distinction is false for the exact proposed response contract: a caller
using process status alone cannot distinguish INAPPLICABLE from
`ERR_INTERNAL`. This is not merely hypothetical inherited wording. The frozen
runner also maps `ERR_INTERNAL` to 3
(`baseline-run/implementation-output-0.3/b1_capabilities.py:1077-1087`), and
the core deliberately retains that mapping for 0.5.

**Required resolution choice:** preferably assign INAPPLICABLE a distinct
unused exit code (for example 4) and regenerate its response schema, fixtures,
wrapper expectations, transcripts, manifests, and receipts. Alternatively,
move 0.5 `ERR_INTERNAL` to 2 and explicitly state that this is new-generation
behavior while frozen exits remain unchanged. If code sharing is intentional,
remove the non-confusion/reservation claim and state that JSON response parsing
is mandatory; that is a materially different CLI contract.

### B3 — the compact expander's failure surface is not deterministic or wire-complete

The compact expansion is called a "total deterministic function"
(`GEN_0_5_SEMANTICS.md:875-909`) and section 5.6 assigns compact-only failures
the shared codes 75, 76, 80, and 100 (`:952-975`). It does not define:

- an error response/return schema or format identifier;
- whether an error is JCS+LF stdout, a typed local return, or an exception;
- request-id sentinel/echo behavior, receipt/self-zero behavior, stderr, or
  process exit code;
- the RFC 6901 pointer for each tuple/profile failure or how multiple bad
  selector fields enter the precedence/pointer pool; or
- one consistent distinction between absent, unknown, and unavailable.

The last point also conflicts with the core scanner. The core assigns
`ERR_GENERATION_UNDECLARED` only to a missing declaration and assigns an
unrecognized string `ERR_GENERATION_UNSUPPORTED`
(`GEN_0_5_CORE.md:88-105`). Compact section 5.6 instead assigns **unknown**
tuples/profiles `ERR_GENERATION_UNDECLARED` and "declared ... unavailable"
`ERR_GENERATION_UNSUPPORTED` without defining what registry/build state makes
the same received identifier unknown versus declared (`GEN_0_5_SEMANTICS.md:
954-965`). Multiple selector fields can disagree simultaneously, but no
pointer law selects the observable error.

The core expressly says a front dispatcher needs a separately versioned error
wire and does not define one (`GEN_0_5_CORE.md:111-114`). The compact expander
is outside the sealed parser and may target either 0.5 or frozen composed 0.3,
so silently borrowing the 0.5 engine error response is not justified; the
frozen 0.3 response schema cannot carry the new generation errors.

**Required resolution choice:** define a unique compact-expander error
contract (or an exact typed local API result) with format, fields, receipt if
any, exits, stderr/stdout behavior, request-id handling, and per-field
pointer/pooling rules. Align the scanner matrix with core section 2.2:
missing selector -> undeclared; non-string -> schema; syntactically valid but
unrecognized/disabled selector -> unsupported; recognized tuple contradiction
after selection -> schema; admitted-registry corruption -> internal. If a
different compact-specific taxonomy is desired, give it distinct codes and
messages rather than reusing the core codes with different meanings.

## Nonblocking findings and open choices

No additional blocking defect was found in the following explicitly open
choices. They must be resolved before adoption, but the drafts identify them
as choices rather than pretending they are settled:

- OBL-24 non-default competence profile and required-versus-allowed set law
  (`GEN_0_5_SEMANTICS.md:280-288`);
- whether profile arrays themselves are canonically sorted (`:284-285`);
- applicability-profile registry status, empty basis references, and whether
  every operation admits INAPPLICABLE (`:486-497`);
- OBL-30 select-all-compatible policy, canonical projection order, and removal
  of the two redundant 0.3 fields (`:778-787`); and
- exact compact template bytes/registry placement and optional compact-input
  digest (`:1072-1081`).

The proposals consistently label normative language **PROPOSED / NOT
ADOPTED** (`GEN_0_5_CORE.md:3-8`, `GEN_0_5_SEMANTICS.md:3-14`) and include an
adequate non-claims boundary. I found no claim that the digests authenticate
facts, that the proof snapshot establishes general efficacy, or that any
external system conforms.

## Field, error, and format crosswalk

| Surface | Frozen/additive authority re-derived | Proposed mapping across P7/P8 | Assessment |
|---|---|---|---|
| E1 request identity | Accepted 0.2 and composed 0.3 both use `B1-SEMANTIC-DECISION-REQUEST-0.2`; `ERRATA.md` E1 records the collision and lint L2 grandfathers only it. | Both drafts use unique `B1-SEMANTIC-DECISION-REQUEST-0.5`, exact response offer `PCB-RUNNER-RESPONSE-0.5`, and forbid inferred downgrade (`CORE:44-128`; `SEMANTICS:18-48`). | Consistent for the direct engine. Compact error selection remains blocked by B3. |
| Outer generation fields | Frozen schemas have no response-offer field. | Direct request requires `format_version` and `accept_response_format_version`; both are covered by the complete request seal (`CORE:63-105`, `:183-205`). | Consistent. |
| Legacy dispatch | Same outer 0.2 format cannot distinguish accepted 0.2 from composed 0.3. | Explicit deployment boundary for frozen modes; distinct 0.5 routing; no implicit upgrade (`CORE:116-128`). Compact legacy profile pins composed-0.3 contract/generation (`SEMANTICS:911-950`). | Consistent with E1 and frozen bytes. |
| `inner_request` | Frozen envelope validates and hashes the complete packet request, but classification ignores it. | Direct 0.5 retains it as auxiliary, removes the two old digest fields, and covers it only through the request seal (`CORE:130-166`; `SEMANTICS:821-825`, `:853-873`). | Consistent with E3 and the frozen authority boundary. |
| `decision_input_sha256` | H5/grounded 0.4 bind `SHA256_UPPER(JCS(decision_input))`; frozen ordinary responses do not carry it. | Same LF-excluded formula in both drafts; request schema requires it and response echoes it inside the receipt (`CORE:168-181`, `:252-274`; `SEMANTICS:29-41`). | Consistent with E2/E3. |
| Request seal | No frozen equivalent; legacy has inner-only digests. | Self-zero only `request_envelope_sha256`; JCS preimage excludes LF; final wire JCS+LF (`CORE:183-205`; `SEMANTICS:29-41`). | Consistent and nonrecursive. |
| Response seal | Frozen response self-zero seal covers its closed response but not decision input on ordinary branches. | New receipt covers all output, including input digest, request seal, trace, references, truncation, class, and effect receipt (`CORE:384-415`). | Consistent with E2. |
| Applicable class order | Frozen order is MALFORMED, BINDING, OMISSION, else VALID. | Applicability is evaluated before the table; APPLICABLE retains the frozen order (`CORE:293-315`; `SEMANTICS:71-76`, `:373-406`). | Consistent. |
| `first_match_predicates` | Grounded API records the three-class short-circuit map. | Fixed three booleans; later false after a match means not evaluated; all false for VALID or INAPPLICABLE, disambiguated by class/trace (`CORE:293-315`; `SEMANTICS:402-412`). | Deterministic. |
| Witness | Grounded trace uses atomic pointer extraction, first-true `any`, all children for true `all`, and a compact `not` marker. | P7 specifies the same algorithms, Unicode-scalar pointer sorting, hard admission caps, and no truncation (`CORE:317-352`). P8 pins the INAPPLICABLE witness. | Consistent. |
| Record references | Grounded 0.4 scans facts only, dedupes/sorts, and caps 64. | P7 retains facts-only derivation and adds explicit truncation. P8 requires applicability references in the field while forbidding facts. | **Blocking: B1.** |
| Error law | Frozen order 10..100 and `ERR_INTERNAL` exit 3. | Direct 0.5 inserts generation errors 75/76, then schema 80, one error by precedence/pointer (`CORE:446-492`). | Direct path is specified; exit alias is **B2** and compact error path is **B3**. |
| INAPPLICABLE representation | E7/H4 establish that frozen generations have no abstention; proof snapshot is 18/0/133 strict versus 18/0/0 calibrated. | Closed no-facts branch; `ok:true`; result/status/class/conclusion all INAPPLICABLE; empty unresolved reasons; null effect receipt (`SEMANTICS:290-472`; `CORE:236-291`). | Shape is consistent; references and exit are blocked by B1/B2. |
| OBL-24 schema/authority | Frozen OBL-24 requires `declared_fixture_class_ids` and inert `covered_modality_ids`; table hard-codes four classes; E4 records self-reference. | Contract-pinned active profile; request repeats profile ID as const; declared classes and modalities become semantic; duplicate/required/allowed laws compile to existing operators (`SEMANTICS:78-247`). | Consistent proposed closure. Actual profile bytes remain an explicit adoption task. |
| OBL-30 source authority | Frozen 0.3 marks intent tuple inert and trusts verdicts/projections; E5/0.4 closures catch projection disagreement but not coherent inversion. | Intent and five candidate dimensions become semantic; compatibility and ordered reasons are derived row-by-row (`SEMANTICS:499-637`). | Correctly addresses the residual E5 hole. |
| OBL-30 structure/order | Frozen table mostly uses set comparisons and caller bookkeeping; valid fixture selects all compatible candidates and excludes the lure. | Candidate order defines all projections; duplicates/order/pool membership are MALFORMED; derived disagreement is BINDING; missing selected/excluded derived rows is OMISSION; VALID is exact (`SEMANTICS:638-688`). | Deterministic; select-all is accurately disclosed as an adoption choice. |
| OBL-30 removed fields | Grounded closures derive `undispositioned_compatible_record_ids`; frozen schema also carries `misreasoned_excluded_record_ids`. | Both are forbidden/removed; their conditions are engine-derived (`SEMANTICS:534-558`, `:668-688`). | Consistent, with migration consequences listed. |
| Direct compact expansion | No frozen compact wire. | Unique compact format, pinned profile/template, two exact substitutions, direct digest/seal construction, schema revalidation, atomic JCS+LF (`SEMANTICS:789-910`). | Success path is deterministic subject to intentionally unpinned template bytes. |
| Frozen 0.3 compact adapter | Frozen composed request uses colliding 0.2 string and the two legacy digest formulas. | Separate compact format/profile pins `COMPOSED-0.3-FROZEN`, exact contract, old fields only, and old digest formulas (`SEMANTICS:911-950`). | Compatible in design; parity is required rather than claimed. |
| Regeneration/adoption | Frozen schemas, fixtures, receipts, examples, manifests, and implementations are protected. | Both drafts require new schemas, registries, fixtures, wrapper/transcript artifacts, receipts, manifests, authority rows, examples, gates, and frozen byte parity (`CORE:494-580`; `SEMANTICS:1083-1125`). | Complete at proposal level; no absent adoption artifact was treated as a defect. |

## Counterevidence sought

1. **Pinned schemas and tables.** I extracted the accepted OBL-24 decision-input
   branch and predicate row from
   `baseline-run/control/B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json`. It requires
   the two frozen arrays, treats only declared classes semantically, and uses
   `NOT_UNIQUE`, `NOT_CONTAINS_ALL`, and `NOT_SUBSET_VALUES` over the four
   fixed classes. This supports P8's E4 diagnosis and operator reuse.
2. **Pinned OBL-30 schema/table.** I extracted the composed OBL-30 branch and
   supplemental decision row from
   `supplemental-0_3/control/B1_SUPPLEMENTAL_COMPARATOR_CONTRACT_0_3.json`.
   They confirm all five intent fields exist but were non-authoritative, while
   verdict/projection/disposition fields drive classification.
3. **Pinned valid OBL-30 fixture.** The INPUT_OUTPUT entry in
   `supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json`
   has candidates `REC_A`, incompatible `REC_LURE`, and `REC_B`; the valid
   projection selects both compatible records and excludes the lure. That is
   affirmative evidence for the draft's stated legacy select-all-compatible
   parity, not evidence for a new ranking policy.
4. **Authority and closure evidence.** The 0.4 authority register marks the
   OBL-30 intent tuple `inert_disclosed`, candidate/verdict/projection fields
   semantic, OBL-24 declared classes semantic, and modalities registered debt.
   The closure table enforces verdict/projection agreement and derived
   disposition exhaustiveness but cannot defeat coherent inversion. P8's
   proposed authority changes are responsive to that evidence.
5. **Applicability evidence.** `ERRATA.md` E7, `HOST_OBLIGATIONS.md` H4, and
   `proof/results.json` agree on the bounded snapshot: strict b1 had 133 false
   holds while calibrated b1 had zero, with the same 18 detections and no
   misses. The draft repeats those numbers with explicit evidence limits.
6. **Frozen-byte and scope check.** Relative to the required integration SHA,
   P7/P8 add only two proposal Markdown files (1,802 inserted lines). No
   sealed, implementation, workflow, dependency, fixture, receipt, manifest,
   or proof byte changed. `git diff --check` passed.
7. **Adversarial alternatives.** I tested for downgrade inference, old-format
   aliasing, digest LF ambiguity, double-zero recursion, projection set/list
   ambiguity, OBL-30 duplicate/order gaps, Unicode/NFC leakage, silent witness
   truncation, effect-receipt scope drift, and legacy adapter field grafting.
   No additional blocking contradiction reproduced. The three findings above
   survived the confirmatory pass against the pinned code and tables.

## Validation gate

The current full integration gate was run after both unchanged cherry-picks,
under Python 3.12.10, with `-B`:

| Gate | Result |
|---|---|
| Frozen 0.2 conformance | 800 checks, 0 failures |
| Composed 0.2 + 0.3 conformance | 800 + 107 checks, 0 failures |
| Grounded regression | 504 checks, 0 failures |
| Contract lint | 199-field census, 0 findings |
| Audit adversarial | 6,497 checks, 0 failures |
| Deterministic properties | seed `0x5EED8785`, 2,296 checks, 0 failures |
| Lint-gate meta-test | 7 checks, 0 failures |
| Proof harness | 7 tests, all passed |

This proves doc-only neutrality for accepted executable behavior; it cannot
resolve contradictions inside the unimplemented proposal.

## Residual uncertainty

- No 0.5 schemas, registry bytes, fixture packs, implementation, or receipts
  exist by design. I therefore could not validate future JSON Schema
  combinator pointer output or recompute proposed artifact seals. Their absence
  was not treated as a defect.
- The compact template and the non-default OBL-24 competence profile are
  explicitly unchosen, so parity of those future bytes remains unproven.
- Validation executed on one admitted Python/Windows environment. The frozen
  property suite includes UTF-16 member ordering and deterministic JCS checks,
  but future 0.5 cross-platform parity remains an adoption obligation.

## Exact diff summary

Before this report, the candidate diff from
`6f3dcceb208e1159686782e5550040802be7af9a` was exactly:

- `continuation-specs/GEN_0_5_CORE.md`: new, 658 lines;
- `continuation-specs/GEN_0_5_SEMANTICS.md`: new, 1,144 lines.

This refuter adds only `orchestration/refuters/RSPEC.md`. No proposal or code
byte was edited.

## Report commit

Recorded after commit in the handoff message; the report commit is the only
RSPEC-authored change.
