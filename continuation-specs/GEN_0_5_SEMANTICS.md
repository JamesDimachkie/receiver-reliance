# Generation 0.5 semantic proposals

> **STATUS: PROPOSED / NOT ADOPTED.** This document is a design draft. It is
> not an accepted contract, does not alter any sealed 0.2 or 0.3 byte, and does
> not authorize regeneration, release, or conformance claims.

This draft specifies proposed generation-0.5 treatment of ERRATA E4, ERRATA
E7, OBL-30 compatibility derivation, and a compact request profile. Normative
words such as **MUST** describe the proposal only.

Research boundary: reading this repository makes an author treatment-exposed
for the research program's future blinded experiment. This document is not,
and must not be used to author, a regenerated world, oracle, gold answer, or
renderer.

## 1. Scope, authority, and non-claims

The accepted 0.2 and composed 0.3 contracts, fixtures, receipts, and
implementations remain byte-frozen. Generation 0.5, if adopted, MUST use new
files, new schema identifiers, and the exact negotiated pair:

- request: `B1-SEMANTIC-DECISION-REQUEST-0.5`;
- response: `PCB-RUNNER-RESPONSE-0.5`;
- required request field: `accept_response_format_version`, whose only 0.5
  value is `PCB-RUNNER-RESPONSE-0.5`;
- direct input digest field: `decision_input_sha256`;
- self-zero request seal field: `request_envelope_sha256`.

The request seal is:

```text
SHA256_UPPER(
  RFC8785_JCS(complete expanded request with only
              request_envelope_sha256 replaced by ZERO64)
)
```

The preimage excludes LF. `decision_input_sha256` is
`SHA256_UPPER(RFC8785_JCS(decision_input))`, also without LF. The final wire is
the JCS request plus one LF. These names and formulas are shared with the
proposed core 0.5 contract; this document does not define a competing envelope.

Direct protocol errors produced for these semantic requests inherit the exact
pointer-selection and representation law in the core proposal's section 4.1.2,
**Direct exact-pointer containment (E6)**. The direct engine constructs and
selects with the complete canonical RFC 6901 pointer first. It emits that full
pointer string when the ordinary zero-receipt JCS+LF response fits the
16,777,216-byte response cap and otherwise uses the core's closed
`DIGESTED_RFC6901_SHA256_96` object. This semantic proposal neither redefines
that object nor permits containment to change the selected code, message,
precedence, request ID, exit, or receipt law. The inherited direct rule is
separate from the compact expander's phase-local 4096-scalar budget in section
5.7.

Generation selection happens before ordinary target-specific schema
validation. The same four-way selector taxonomy applies to every generation,
request-format, response-format, and profile selector on both the direct and
compact wires. A missing selector property produces
`ERR_GENERATION_UNDECLARED` at precedence 75. A present non-string or a string
that fails `^[A-Z0-9][A-Z0-9._-]{0,159}$` produces `ERR_SCHEMA` at precedence
80. A syntactically valid value that is unrecognized in that selector
position, recognized only by a disabled entry, or recognized by an entry
unavailable in the invoked build produces `ERR_GENERATION_UNSUPPORTED` at
precedence 76. Individually recognized and enabled values that contradict the
selected admitted tuple produce `ERR_SCHEMA` at precedence 80. No direct or
compact request may infer a generation, downgrade, or retry another tuple.

This draft makes no claim of efficacy, novelty, security, external
conformance, production readiness, or applicability to records outside the
committed fixtures and proof snapshot. In particular:

- an applicability declaration is a bound host attestation, not an engine
  finding about the world;
- an OBL-30 result is conditional on the supplied intent and candidate pool;
- a fixture-profile result checks a pinned profile relation, not the quality
  or sufficiency of a test program; and
- compact expansion is a deterministic representation transform, not a new
  semantic authority.

### 1.1 Common notation

- Equality of strings and booleans is type-strict JSON equality.
- `ids(rows)` means the `record_id` projection in row order.
- `project(rows, predicate)` preserves row order.
- Arrays described as canonical projections MUST be in source row order; a
  reordered projection is not canonical even if it has the same members.
- `UNIQUE_BY(rows, key)` means that no two rows have the same strict JSON value
  at `key`.
- Parsing, envelope binding, operation/obligation mapping, generation
  negotiation, direct-input digest verification, and request-seal verification
  all occur before semantic classification.
- The semantic precedence for applicable decisions remains:
  `MALFORMED_OR_BOUNDARY`, `BINDING_OR_CONFLICT`,
  `OMISSION_OR_INCOMPLETE`, `VALID`.

## 2. E4: parameterize OBL-24's fixture-class set

### 2.1 Chosen design

Generation 0.5 SHOULD retain OBL-24 as a generic fixture-profile coverage
relation and parameterize it with a digest-bound profile registry. It SHOULD
NOT rename OBL-24 to an artifact-specific audit.

The reason is narrow: renaming would truthfully describe the frozen 0.3 row,
but it would preserve the row's inability to express a different fixture
taxonomy. A profile registry removes the baked-in four-class constant while
keeping the operation deterministic and preventing a caller from choosing its
own conveniently weak requirement set.

The contract MUST contain `fixture_class_profiles`, an array of objects with
the following closed schema:

```json
{
  "profile_id": "string, 1..160 chars, no CR/LF",
  "required_fixture_class_ids": ["unique strings, max 256"],
  "allowed_fixture_class_ids": ["unique strings, max 256"],
  "required_modality_ids": ["unique strings, max 256"],
  "allowed_modality_ids": ["unique strings, max 256"]
}
```

The same contract MUST contain one
`active_obl24_fixture_profile_id`. It MUST equal exactly one registered
`profile_id`. Profile choice is therefore a generation/control decision, not a
per-request caller option.

Registry admission MUST reject:

1. duplicate `profile_id` values;
2. an empty `required_fixture_class_ids` array;
3. a required fixture class absent from `allowed_fixture_class_ids`;
4. a required modality absent from `allowed_modality_ids`;
5. duplicate values in any of the four set-valued fields; or
6. the same `profile_id` bound to a different RFC8785-JCS digest in another
   admitted 0.5 control artifact; or
7. an absent, unknown, or multiply resolved
   `active_obl24_fixture_profile_id`.

The registry and active binding are contract authority. The request repeats the
active profile ID as a schema `const` but cannot select another profile and does
not supply the requirement arrays. This avoids replacing E4 with either a
self-attested `required_fixture_class_ids` field or a caller-selectable weak
profile.

The proposed default profile is:

```json
{
  "profile_id": "B1-SEMANTIC-FIVE-CLASS-0.5",
  "required_fixture_class_ids": [
    "INPUT_OUTPUT",
    "INVARIANT",
    "POLICY_PERMITTED_CONTROL",
    "FAILURE",
    "INAPPLICABLE"
  ],
  "allowed_fixture_class_ids": [
    "INPUT_OUTPUT",
    "INVARIANT",
    "POLICY_PERMITTED_CONTROL",
    "FAILURE",
    "INAPPLICABLE"
  ],
  "required_modality_ids": [],
  "allowed_modality_ids": [
    "REPLAY",
    "ADVERSARIAL",
    "BOUNDED_STATE",
    "HUMAN_VALIDATED"
  ]
}
```

The proposed 0.5 control binds
`active_obl24_fixture_profile_id = "B1-SEMANTIC-FIVE-CLASS-0.5"`.

`INAPPLICABLE` is present because section 3 proposes it as a distinct fixture
class, not as a control or failure alias. No modality is universally required
by this default profile. A domain-specific profile may require one or more
modalities, but only by placing them in the pinned registry.

### 2.2 OBL-24 fact schema

For an applicable OBL-24 request, `facts` is a closed object with exactly these
required fields:

```json
{
  "fixture_profile_id": "B1-SEMANTIC-FIVE-CLASS-0.5",
  "declared_fixture_class_ids": ["..."],
  "covered_modality_ids": ["..."]
}
```

- `fixture_profile_id` MUST be a `const` equal to
  `active_obl24_fixture_profile_id`.
- Both arrays use the existing bounded string item schema, have `maxItems: 256`,
  and remain arrays rather than unordered JSON objects.
- Any other profile ID fails schema validation. It does not fall back to the
  default or select another registered profile.
- The schema does not use JSON Schema `uniqueItems`; duplicate handling remains
  a semantic MALFORMED fixture as in 0.3.

Authority-register consequences are exact:

- `fixture_profile_id`: `presence_only`, with a rationale that its value is
  fixed by schema and its requirement set comes from the control binding;
- `declared_fixture_class_ids`: `semantic`;
- `covered_modality_ids`: changes from `inert_registered_debt` to `semantic`.

### 2.3 OBL-24 predicates

For the profile selected by the control artifact's active binding, let `RC`,
`AC`, `RM`, and `AM` be its required classes, allowed classes, required
modalities, and allowed modalities. The row MUST implement these predicates in
the ordinary class precedence:

| class | predicate |
|---|---|
| `MALFORMED_OR_BOUNDARY` | `declared_fixture_class_ids` is not unique, OR `covered_modality_ids` is not unique |
| `BINDING_OR_CONFLICT` | `declared_fixture_class_ids` does not contain every value in `RC`, OR `covered_modality_ids` does not contain every value in `RM` |
| `OMISSION_OR_INCOMPLETE` | `declared_fixture_class_ids` contains a value outside `AC`, OR `covered_modality_ids` contains a value outside `AM` |
| `VALID` | no earlier class matches |

The implementation MUST compile the active profile to the existing
`NOT_CONTAINS_ALL` and `NOT_SUBSET_VALUES` operators with the pinned values.
The schema `const` resolves the profile before classification, so no ambient
lookup, clock, network, or new runtime dependency is permitted.

The profile registry order has no semantic effect. Registry generation MUST
sort profiles by `profile_id` before computing the registry digest and
resolving the active binding so generated control bytes are deterministic.

### 2.4 Fixture and regeneration consequences

The 0.5 OBL-24 fixture family MUST be regenerated, not edited in place:

- INPUT_OUTPUT: the default five-class declaration, no modalities, `VALID`;
- INVARIANT: a duplicate declared class, `MALFORMED_OR_BOUNDARY`;
- POLICY_PERMITTED_CONTROL: one required class absent,
  `BINDING_OR_CONFLICT`;
- FAILURE: an unallowed class or modality present,
  `OMISSION_OR_INCOMPLETE`;
- INAPPLICABLE: the declaration branch from section 3, with no OBL-24 facts.

At least one compiler competence case MUST instantiate a synthetic test control
whose active profile has a required class set other than the five-class set.
Renaming that active profile consistently in registry, binding, and request
without changing its four arrays MUST leave the derived class unchanged;
changing a required class while holding the declaration fixed MUST change the
derived class when the relation changes. The synthetic test control is not an
additional production-selectable profile. This is the minimum proof that the
row is parameterized rather than five-class hard-coded under a new field name.

All new schema digests, fixture entry digests, pack seals, wrapper parity
entries, receipts, authority-register rows, and documentation references MUST
be regenerated under 0.5 identifiers. No 0.2/0.3 receipt or pinned example is
recomputed.

An OBL-24 migrator MUST add the active profile ID and the APPLICABLE branch but
MUST derive `declared_fixture_class_ids` from the actual regenerated 0.5 pack.
It may not append `INAPPLICABLE` merely to make the row pass. If the fifth
fixture does not exist, migration fails or produces the relation's non-VALID
class; it does not fabricate coverage.

### 2.5 Example

Given the default profile above:

```json
{
  "fixture_profile_id": "B1-SEMANTIC-FIVE-CLASS-0.5",
  "declared_fixture_class_ids": [
    "INPUT_OUTPUT",
    "INVARIANT",
    "POLICY_PERMITTED_CONTROL",
    "FAILURE",
    "INAPPLICABLE"
  ],
  "covered_modality_ids": ["REPLAY"]
}
```

is `VALID`. Removing `INAPPLICABLE` is `BINDING_OR_CONFLICT`; adding
`UNREGISTERED_CLASS` is `OMISSION_OR_INCOMPLETE`; repeating `REPLAY` is
`MALFORMED_OR_BOUNDARY`.

### 2.6 Alternative and unresolved E4 questions

The rejected primary alternative is to rename OBL-24 to
`ARTIFACT_FOUR_CLASS_FIXTURE_COVERAGE`, retain the four constants, and state
that it audits only this artifact's fixture pack. That is the smallest truthful
description of 0.3 and remains a viable fallback if no generic profile use is
wanted. It was not chosen because it cannot express the new INAPPLICABLE class
or another admitted taxonomy without another operation.

Open before adoption:

1. Which non-default synthetic profile supplies the mandatory compiler
   competence case?
2. Are profile arrays required to be lexicographically sorted in control
   bytes, or only unique with a deterministic generator sort?
3. Should an allowed-but-not-required fixture class be supported in 0.5, or
   should admission require `required_fixture_class_ids ==
   allowed_fixture_class_ids` for a simpler exact-set relation?

## 3. E7: first-class applicability and abstention

### 3.1 Motivation and evidence limit

The committed `proof/RESULTS.md` snapshot reports, for its 408-record run:

- strict `b1`: 18 detected, 0 missed, 133 false holds, detection rate 1.0,
  false-hold rate 0.341; and
- `b1_calibrated`: 18 detected, 0 missed, 0 false holds, detection rate 1.0,
  false-hold rate 0.0.

Those strict-versus-calibrated numbers motivate a contract representation for
abstention. They are not a general efficacy estimate, do not prove that the
proposed declaration is correct, and do not elevate the committed proof
snapshot to external conformance evidence.

### 3.2 Decision-input branches

Every 0.5 operation MUST have two mutually exclusive decision-input branches.
Both use `B1-SEMANTIC-FACTS-0.5`, the operation's registered handle, and its
obligation ID.

The applicable branch is:

```json
{
  "format_version": "B1-SEMANTIC-FACTS-0.5",
  "operation_handle": "OPR_...",
  "obligation_id": "OBL-...",
  "applicability": {
    "status": "APPLICABLE",
    "applicability_profile_id": "HOST-PROFILE-ID"
  },
  "facts": {}
}
```

`facts` is required and MUST validate against the complete operation-specific
fact schema.

The inapplicable branch is:

```json
{
  "format_version": "B1-SEMANTIC-FACTS-0.5",
  "operation_handle": "OPR_...",
  "obligation_id": "OBL-...",
  "applicability": {
    "status": "INAPPLICABLE",
    "applicability_profile_id": "HOST-PROFILE-ID",
    "subject_record_id": "RECORD-ID",
    "reason_code": "NATIVE_SEMANTICS_ABSENT",
    "basis_record_refs": ["OPAQUE-REF"]
  }
}
```

This branch MUST NOT contain `facts`. The closed `applicability` schema is:

- `status`: the branch constant;
- `applicability_profile_id`: required in both branches and exactly a string
  matching `^[A-Z0-9][A-Z0-9._-]{0,159}$`; its admitted length is 1 through
  160 ASCII characters;
- `subject_record_id`: bounded non-empty string, required only for
  INAPPLICABLE;
- `reason_code`: initially the single enum value
  `NATIVE_SEMANTICS_ABSENT`, required only for INAPPLICABLE; and
- `basis_record_refs`: unique bounded strings, `maxItems: 64`, required only
  for INAPPLICABLE and permitted to be empty.

The `applicability_profile_id` pattern and length are the complete admitted
opaque-ID language for this proposal. Every admitted character is ASCII, so an
admitted value is necessarily NFC and CR/LF-free. Opaque versus registry-backed
identity remains the adoption choice in section 3.7; registry adoption may add
membership validation but MUST NOT silently broaden or narrow this string
language without a different declared generation.

The applicable branch MUST reject the three inapplicable-only fields. The
inapplicable branch MUST reject `facts` and every unlisted property. A request
that mixes fabricated facts with an INAPPLICABLE declaration therefore fails
`ERR_SCHEMA`; it does not obtain semantic-class precedence.

Source presence and type handling are total and branch-specific:

| branch | `facts` | `subject_record_id` | `basis_record_refs` |
|---|---|---|---|
| APPLICABLE | required object; missing or any non-object, including `null` or a list, is `ERR_SCHEMA` | forbidden and therefore absent; any present value, including `null` or a list, is `ERR_SCHEMA` | forbidden and therefore absent; any present value, including `null` or a non-list, is `ERR_SCHEMA` |
| INAPPLICABLE | forbidden and therefore absent; any present value, including `null` or a list, is `ERR_SCHEMA` | required non-empty bounded string; missing or any non-string, including `null` or a list, and any invalid string is `ERR_SCHEMA` | required unique bounded-string list, which may be empty; missing, `null`, a non-list, or an invalid item is `ERR_SCHEMA` |

An absent branch-forbidden source contributes the empty candidate sequence; it
is not treated as `null`. A present forbidden source or an invalid required
source is rejected during schema validation and never reaches reference
derivation. Thus these contribution rules do not turn a schema-invalid source
into an empty source.

`applicability_profile_id`, `subject_record_id`, `reason_code`, and
`basis_record_refs` are bound attestations. The engine validates their shape
and seals their bytes but does not verify that the profile exists in an
external host, that the record lacks semantics, or that a basis reference is
truthful. The authority register MUST label `applicability.status` as
`semantic`; the three required scalar attestation fields as `presence_only`
with an explicit host-attestation rationale; and `basis_record_refs` as
`inert_disclosed`. None may be described as verified evidence.

### 3.3 Evaluation and response

After the request has passed generation selection, strict parsing, schema,
envelope mapping, `decision_input_sha256`, and `request_envelope_sha256`:

1. `applicability.status == "INAPPLICABLE"` derives the first-class evaluation
   class `INAPPLICABLE` without invoking the operation predicate table.
2. `applicability.status == "APPLICABLE"` invokes the ordinary four-class
   table with unchanged class precedence.

The proposed evaluation mapping is:

| evaluation class | response `result` | `output.status` | behavior class | conclusion | process exit |
|---|---|---|---|---|---|
| `INAPPLICABLE` | `INAPPLICABLE` | `INAPPLICABLE` | `INAPPLICABLE` | `INAPPLICABLE` | `4` |

The response remains `ok: true`: a valid declaration was processed. It MUST
have no effect receipt, no unresolved reason that implies missing evidence,
and no PASS/FAIL status. Its sealed trace MUST state that the applicability
branch short-circuited predicate evaluation and MUST bind the declaration's
record references through the core 0.5 sealed reference field. It MUST NOT
claim that the engine proved inapplicability.

Concretely, top-level `result`, `output.status`,
`output.result_object.behavior_class`, and
`output.result_object.conclusion` are all the string `INAPPLICABLE`;
`output.unresolved_reasons` is `[]` and `output.effect_receipt_sha256` is
`null`.

The existing three-boolean `first_match_predicates` object is preserved. For
INAPPLICABLE, all three booleans are false; this does not mean VALID because the
sealed trace records the applicability short-circuit and the four response
fields in the table above identify the fifth class. Applicable requests retain
the ordinary three booleans and VALID fallback.

The exact pre-table sealed witness is:

```json
{"matched_class_witness":[{"op":"EQ","pointers":["/applicability/status"]}]}
```

Exit code 4 is the distinct new-generation abstention code. Command-line
callers can distinguish it from PASS (0), semantic FAIL (1), protocol/client
error (2), and `ERR_INTERNAL` (3). Frozen `ERR_INTERNAL = 3` behavior remains
unchanged; proposed 0.5 internal failures also retain 3. Adoption MUST reserve
4 for INAPPLICABLE and regenerate its schema, fixtures, wrapper expectations,
transcripts, manifests, and receipts together.

### 3.4 Record-reference union and boundary fixtures

The shared 0.5 `output.record_references` derivation uses the same algorithm
for APPLICABLE and INAPPLICABLE requests. Its candidate multiset is the union
of three sources:

1. A recursive walk of `decision_input.facts`, when present; an absent `facts`
   source contributes zero candidates:
   - include a string leaf when its object key contains `record_id` or is
     exactly `exact_reference`;
   - include string items of an array whose object key ends with
     `_record_ids` or is exactly `pool_record_ids`; and
   - recurse through every other object value and array item.
2. Include the present
   `decision_input.applicability.subject_record_id`; an absent subject source
   contributes zero candidates.
3. Include every string in the present
   `decision_input.applicability.basis_record_refs` list; an absent basis source
   contributes zero candidates, and a present empty list also contributes zero.

A schema-valid contributing string is non-empty, NFC, and at most 240 Unicode
scalar values. Empty, non-NFC, oversized, or non-string source values are
`ERR_SCHEMA`; they are not silently filtered. Reference derivation starts only
after the mutually exclusive branch schema has passed. For every candidate
compute its RFC8785-JCS string bytes. Dedupe by exact JCS bytes. Order the
distinct strings lexicographically by unsigned UTF-16 code-unit sequence, the
RFC8785 member-name rule, with JCS bytes as a final tie-break. If `N` distinct
strings remain:

```text
output.record_references = first min(N, 64) ordered strings
output.record_references_truncated = (N > 64)
```

The union is material: an INAPPLICABLE request has no `facts`, but its subject
and basis references still enter the same dedupe/order/cap operation. They are
not appended after the cap.

The regenerated response fixtures MUST use this feasible branch split:

- **empty:** an APPLICABLE request with no fact-derived candidates produces
  `record_references: []` and `record_references_truncated: false`;
- **cross-source duplicate:** an INAPPLICABLE request whose subject also
  appears once in `basis_record_refs` emits that string once and reports
  `false`;
- **64 distinct:** one subject plus 63 distinct basis references emits all 64
  in the shared order and reports `false`; and
- **65 distinct:** one subject plus 64 distinct basis references emits the
  first 64 in the shared order and reports `true`.

An empty INAPPLICABLE fixture is forbidden: every schema-valid INAPPLICABLE
request has a required non-empty subject and therefore at least one candidate.
The cross-source-duplicate, 64-distinct, and 65-distinct fixtures MUST be
INAPPLICABLE and MUST omit `facts`; the empty fixture MUST be APPLICABLE and
MUST omit the inapplicable-only subject and basis fields. Schema-negative
fixtures MUST cover each required source missing and replaced by `null` and by
the wrong container/scalar type, and each forbidden source present as `null`, a
list, and an otherwise-valid value. These fixtures MUST show `ERR_SCHEMA`
rather than a reference contribution; valid absence of a forbidden source MUST
be pinned as a zero-candidate contribution.

The 65-distinct fixture MUST place at least one value on each side of a
BMP/astral UTF-16 ordering boundary so an implementation that sorts Unicode
scalar values instead of unsigned UTF-16 code units cannot pass accidentally.

### 3.5 Distinct fixture class

`INAPPLICABLE` is a fifth fixture class. It is not a subtype of
`POLICY_PERMITTED_CONTROL`, `FAILURE`, or `OMISSION_OR_INCOMPLETE`.

Every operation admitted to 0.5 MUST have one semantic fixture whose
`fixture_class_assertion` is exactly `INAPPLICABLE`, whose decision input uses
the inapplicable branch, and whose expected response uses the mapping above.
The fixture must contain no operation facts and must expect process exit 4.

The regenerated fixture and wrapper packs MUST also cover:

- INAPPLICABLE plus `facts` -> `ERR_SCHEMA`;
- APPLICABLE without `facts` -> `ERR_SCHEMA`;
- six otherwise-valid, correctly digest-bound and sealed
  `applicability_profile_id` boundary cases: APPLICABLE and INAPPLICABLE each
  with exactly 159 ASCII `A` characters, 160 ASCII `A` characters, and 161
  ASCII `A` characters. The 159- and 160-character cases MUST pass the
  applicability schema and retain the pinned base request's semantic result
  (with the INAPPLICABLE cases exiting 4); the 161-character cases MUST emit
  the byte-exact direct `ERR_SCHEMA` response at
  `/decision_input/applicability/applicability_profile_id`, exit 2, and never
  reach semantic classification. Every one of the six cases MUST pin the
  request-ID choice, complete direct response JCS+LF bytes, receipt, empty
  stderr, and process exit after all required request digests and seals are
  recomputed;
- an unknown `reason_code` -> `ERR_SCHEMA`;
- a declaration mutation with stale `decision_input_sha256` -> the ordinary
  digest mismatch error selected by the core 0.5 contract;
- a recomputed direct-input digest but stale `request_envelope_sha256` -> the
  ordinary request-seal mismatch error; and
- wrapper parity for the same INAPPLICABLE semantic request in each admitted
  wrapper configuration.

Changing only `basis_record_refs` and correctly resealing MUST change the
request digest/seal and the response receipt or sealed reference/trace content;
it MUST NOT change the derived evaluation class.

A legacy applicable decision may be used to construct a new 0.5 APPLICABLE
request only with its complete fact object and an explicit host profile ID.
Migration MUST NOT infer INAPPLICABLE from a legacy failure, missing field, or
OMISSION class. Historical requests and receipts remain unchanged.

### 3.6 Example

For a record whose host adapter has no acknowledgment semantics for OBL-17:

```json
{
  "format_version": "B1-SEMANTIC-FACTS-0.5",
  "operation_handle": "OPR_2314EEF867905DC3E5230227",
  "obligation_id": "OBL-17",
  "applicability": {
    "status": "INAPPLICABLE",
    "applicability_profile_id": "HOST-LIFECYCLE-CALIBRATION-1",
    "subject_record_id": "REC_NO_ACK_001",
    "reason_code": "NATIVE_SEMANTICS_ABSENT",
    "basis_record_refs": ["LIFECYCLE_REC_001"]
  }
}
```

The engine may seal an INAPPLICABLE response. It may not say that OBL-17 is
satisfied, violated, safe, or actually irrelevant; those propositions exceed
the supplied attestation. The response's process exit is 4.

### 3.7 Alternatives and unresolved E7 questions

Rejected alternatives:

- encoding abstention as `OMISSION_OR_INCOMPLETE` still reports a semantic
  failure and does not distinguish absent native semantics from missing
  authoritative facts;
- making operation facts nullable preserves fabrication pressure and permits
  partially invented profiles; and
- host-side silent skipping leaves no bound declaration in the decision
  transcript.

Open before adoption:

1. Decide whether `applicability_profile_id` values are host-defined opaque
   identifiers, as proposed, or members of a contract registry. A registry
   would validate identity but still could not validate world truth.
2. Decide whether an empty `basis_record_refs` array is acceptable. Requiring a
   reference increases audit material but does not make it verified evidence.
3. Decide whether every operation admits INAPPLICABLE or whether an explicit
   operation registry may forbid it. If any operation forbids it, the default
   OBL-24 profile must describe that exception rather than claiming universal
   five-class coverage.

## 4. OBL-30: deterministic compatibility derivation

### 4.1 Authority boundary

Generation 0.5 MUST derive compatibility from the supplied intent tuple and
candidate attributes. It MUST NOT trust caller-supplied compatibility booleans
or projections as conclusions.

The authoritative intent tuple, in comparison precedence, is:

```text
(intent_episode_id,
 intent_purpose_id,
 intent_scope_ref,
 intent_action_class,
 intent_version_sha256)
```

The corresponding candidate tuple is:

```text
(episode_id, purpose_id, scope_ref, action_class, version_sha256)
```

`record_id` identifies the candidate. `similarity_rank` is deliberately not a
compatibility dimension. It remains `inert_disclosed` unless a separate,
explicit selection policy is adopted later. This row proves only compatibility
before disposition; it does not validate how similarity was computed.

The 0.5 authority register MUST change each intent field, candidate `record_id`,
and the five compared candidate subfields to `semantic`; candidate
`similarity_rank` remains `inert_disclosed`. Caller projections remain
`semantic` because predicates compare them, but their rationale MUST say that
they are checked against derivation and do not create source authority.

### 4.2 Proposed facts schema

The 0.5 OBL-30 facts object retains the raw 0.3 intent and candidate pool and
retains checked projections for auditability. It removes the two redundant
caller conclusions `undispositioned_compatible_record_ids` and
`misreasoned_excluded_record_ids`; the engine derives those conditions
directly.

Required top-level fields are exactly:

```text
intent_episode_id
intent_purpose_id
intent_scope_ref
intent_action_class
intent_version_sha256
candidate_pool
pool_record_ids
compatibility_verdicts
compatible_record_ids
incompatible_record_ids
selected_record_ids
excluded_records
excluded_record_ids
```

The existing bounds remain: at most 64 candidates/projection rows; IDs are
bounded non-empty strings without CR/LF; version digests are nonzero uppercase
SHA-256 strings; `similarity_rank` is an integer from 1 through 100000.

Each `compatibility_verdicts` row becomes:

```json
{
  "record_id": "REC_A",
  "compatible": true,
  "rejection_reasons": []
}
```

Each `excluded_records` row becomes:

```json
{
  "record_id": "REC_LURE",
  "exclusion_reason": "INTENT_INCOMPATIBLE",
  "rejection_reasons": ["EPISODE_ID_MISMATCH"]
}
```

`rejection_reasons` is a unique array, `maxItems: 5`, whose item enum is:

```text
EPISODE_ID_MISMATCH
PURPOSE_ID_MISMATCH
SCOPE_REF_MISMATCH
ACTION_CLASS_MISMATCH
VERSION_SHA256_MISMATCH
```

A compatible verdict requires an empty reason array. An excluded incompatible
record requires one or more reasons. Schema handles the conditional empty/non-
empty requirement where expressible; the derivation comparison enforces it in
all cases.

### 4.3 Derivation relation

For each candidate, in `candidate_pool` order:

1. Start with an empty reason array.
2. If `candidate.episode_id != intent_episode_id`, append
   `EPISODE_ID_MISMATCH`.
3. If `candidate.purpose_id != intent_purpose_id`, append
   `PURPOSE_ID_MISMATCH`.
4. If `candidate.scope_ref != intent_scope_ref`, append
   `SCOPE_REF_MISMATCH`.
5. If `candidate.action_class != intent_action_class`, append
   `ACTION_CLASS_MISMATCH`.
6. If `candidate.version_sha256 != intent_version_sha256`, append
   `VERSION_SHA256_MISMATCH`.
7. Derive `compatible = (rejection_reasons is empty)`.

All mismatches are recorded in that fixed order. The engine does not stop at
the first mismatch; the list is a deterministic explanation of the supplied
tuple comparison.

From those rows derive, preserving candidate order:

```text
D_pool         = ids(candidate_pool)
D_verdicts     = one derived verdict row per candidate
D_compatible   = ids(project(D_verdicts, compatible == true))
D_incompatible = ids(project(D_verdicts, compatible == false))
D_selected     = D_compatible
D_excluded     = one excluded row per incompatible candidate, carrying
                 INTENT_INCOMPATIBLE and its exact rejection_reasons
D_excluded_ids = ids(D_excluded)
```

`D_selected = D_compatible` deliberately preserves the composed-0.3 valid
fixture's select-all-compatible semantics. This proposal does not invent a
ranking cutoff or policy for excluding a compatible candidate. A future policy
may add that relation only under another declared generation or operation.

### 4.4 Structural, projection, and disposition checks

After derivation, checks occur in ordinary class precedence.

`MALFORMED_OR_BOUNDARY` fires if any of the following is true:

1. `candidate_pool` is not unique by `record_id`;
2. any ID projection contains duplicates;
3. `compatibility_verdicts` or `excluded_records` is not unique by
   `record_id`;
4. a projected/selected/excluded ID is absent from `D_pool`;
5. `selected_record_ids` intersects `excluded_record_ids`;
6. `pool_record_ids` or the `record_id` projection of
   `compatibility_verdicts` does not have exactly one row, in candidate order,
   for every candidate;
7. any record-ID-bearing projection is not in the relative order established
   by `D_pool`; or
8. `excluded_record_ids != ids(excluded_records)`.

`BINDING_OR_CONFLICT` fires if structurally well-formed input has any of these
semantic contradictions:

1. `compatibility_verdicts != D_verdicts` row-for-row;
2. `compatible_record_ids != D_compatible`;
3. `incompatible_record_ids != D_incompatible`;
4. a selected record is derived incompatible;
5. an excluded record is derived compatible; or
6. an excluded record's `exclusion_reason` or `rejection_reasons` differs from
   its derived row.

`OMISSION_OR_INCOMPLETE` fires if, after the two earlier classes do not match:

1. any ID in `D_selected` is absent from `selected_record_ids`; or
2. any derived excluded row is absent from `excluded_records`.

`VALID` requires all of these exact canonical projections:

```text
pool_record_ids        == D_pool
compatibility_verdicts == D_verdicts
compatible_record_ids  == D_compatible
incompatible_record_ids== D_incompatible
selected_record_ids    == D_selected
excluded_records       == D_excluded
excluded_record_ids    == D_excluded_ids
```

These rules close both recorded E5 probes in the semantic generation itself:
inverting supplied booleans conflicts with `D_verdicts`; shrinking selection
omits a member of `D_selected`. The 0.4 tighten-only closures remain unchanged
for frozen 0.3 requests.

### 4.5 Example

For intent `(EPISODE_001, PURPOSE_A, SCOPE_A, ACTION_CLASS_A, C...C1)` and:

```json
[
  {
    "record_id": "REC_A",
    "episode_id": "EPISODE_001",
    "purpose_id": "PURPOSE_A",
    "scope_ref": "SCOPE_A",
    "action_class": "ACTION_CLASS_A",
    "version_sha256": "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC1",
    "similarity_rank": 2
  },
  {
    "record_id": "REC_LURE",
    "episode_id": "EPISODE_002",
    "purpose_id": "PURPOSE_B",
    "scope_ref": "SCOPE_B",
    "action_class": "ACTION_CLASS_A",
    "version_sha256": "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",
    "similarity_rank": 1
  }
]
```

the derived rows are:

```json
[
  {"record_id":"REC_A","compatible":true,"rejection_reasons":[]},
  {
    "record_id":"REC_LURE",
    "compatible":false,
    "rejection_reasons":[
      "EPISODE_ID_MISMATCH",
      "PURPOSE_ID_MISMATCH",
      "SCOPE_REF_MISMATCH",
      "VERSION_SHA256_MISMATCH"
    ]
  }
]
```

The lure's better similarity rank has no compatibility effect. A valid
disposition selects `REC_A` and excludes `REC_LURE` with exactly those four
ordered reasons.

### 4.6 Fixture and migration consequences

The regenerated 0.5 OBL-30 family MUST include:

- INPUT_OUTPUT: the current compatible records selected and incompatible lure
  excluded, with derived ordered reasons;
- INVARIANT: duplicate candidate or projection ID ->
  `MALFORMED_OR_BOUNDARY`;
- POLICY_PERMITTED_CONTROL: an incompatible lure selected ->
  `BINDING_OR_CONFLICT`;
- FAILURE: a compatible candidate omitted from selection ->
  `OMISSION_OR_INCOMPLETE`;
- INAPPLICABLE: the section-3 branch with no OBL-30 facts;
- mutation: invert every supplied compatible boolean and recompute its
  projections -> `BINDING_OR_CONFLICT` because the raw tuple relation wins;
- mutation: change each intent dimension separately and rederive all declared
  projections -> only the corresponding reason membership changes, subject to
  other mismatches; and
- metamorphic: changing only `similarity_rank` leaves every derived
  compatibility row and class unchanged.

A 0.3-to-0.5 migrator MUST re-derive every compatibility and disposition
surface from intent plus candidate pool. It MUST NOT copy 0.3 verdicts as
authority. It MUST drop the two removed redundant fields, add ordered reasons,
add the applicability branch, and recompute every 0.5 digest and seal. If a
0.3 request's declared projections disagree with derivation, migration MUST
fail with a diagnostic; it may not silently repair an audit record.

### 4.7 Alternatives and unresolved OBL-30 questions

Rejected alternatives:

- retaining the 0.3 caller-verdict authority with only projection closures
  cannot detect a coherently inverted verdict/projection set;
- recording only the first mismatch loses deterministic available explanation
  without reducing the comparison work materially; and
- choosing the lowest `similarity_rank` would create a new selection policy
  absent from the current relation.

Open before adoption:

1. Confirm select-all-compatible semantics. If callers need a compatible
   subset, 0.5 needs an additional pinned selection policy and a reason for
   each unselected compatible candidate; that is not specified here.
2. Decide whether projection order disagreement is MALFORMED, as proposed, or
   whether arrays should be compared as sets and normalized in the sealed
   trace.
3. Decide whether the two redundant 0.3 fields should be forbidden, as
   proposed, or retained as checked projections for easier migration.

## 5. Compact request profile

### 5.1 Purpose and boundary

The compact profile removes the roughly 1.8 KB inert `inner_request` material
from the caller-facing API. It does not remove or reinterpret fields from an
adopted sealed wire contract. A deterministic local expander reconstructs the
complete sealed request for a separate downstream engine invocation. The
expander-only command defined here never invokes that engine itself.

The compact request is therefore an API/transport representation, not an
engine request and not a second classification surface. Engines MUST reject it
if sent directly to the sealed request parser.

### 5.2 Compact schema

The proposed compact format is the unique string
`B1-SEMANTIC-DECISION-COMPACT-0.5`. Its closed schema requires exactly:

```json
{
  "format_version": "B1-SEMANTIC-DECISION-COMPACT-0.5",
  "expansion_profile_id": "B1-INNER-TEMPLATE-0.5",
  "target_generation_id": "B1-GENERATION-0.5",
  "target_request_format_version": "B1-SEMANTIC-DECISION-REQUEST-0.5",
  "accept_response_format_version": "PCB-RUNNER-RESPONSE-0.5",
  "request_id": "RUN_...",
  "operation_handle": "OPR_...",
  "obligation_id": "OBL-...",
  "decision_input": {}
}
```

The operation/obligation/decision-input exact-pair constraints are identical
to the direct 0.5 schema. The compact form does not accept caller-supplied
`inner_request`, `decision_input_sha256`, or `request_envelope_sha256`; all
three are expander outputs. Direct 0.5 has no `inner_request_raw_sha256` or
`inner_input_sha256` fields. It does not repurpose either frozen name.

### 5.3 Expansion-profile registry

Each admitted `expansion_profile_id` MUST resolve to one closed, digest-pinned
registry entry containing:

```text
profile_id
compact_format_version
target_generation_id
target_request_format_version
target_response_format_version
target_contract_raw_sha256
inner_request_template_jcs_base64
inner_request_template_byte_length
inner_request_template_raw_sha256
substitution_pointers
expansion_algorithm_id
```

`inner_request_template_jcs_base64` decodes to RFC8785-JCS object bytes with no
LF. `inner_request_template_raw_sha256` is the SHA-256 of those exact decoded
bytes. Decoding uses strict padded RFC 4648 standard base64 with no whitespace,
and the decoded length MUST equal `inner_request_template_byte_length`.
Admission rejects a template whose decoded bytes are not byte-identical to
RFC8785-JCS of the parsed object.

The direct 0.5 schema retains the packet-compatible inner request as auxiliary
composed legacy input. For that target,
`substitution_pointers` MUST be exactly:

```text
/request_id                  <- compact.request_id
/operation_handle            <- compact.operation_handle
```

The pinned inner template supplies every other inner field. Its
`observable_external_facts` marker MUST identify the expansion profile, not a
semantic fixture case, and MUST be constant. Classification MUST read only the
direct `decision_input`.

No substitution pointer may target `/input`, except through a future profile
with a new profile ID and digest. Duplicate, overlapping, non-RFC6901, missing,
or schema-invalid substitution pointers fail profile admission.

Direct 0.5 removes `inner_request_raw_sha256` and `inner_input_sha256`. The
whole expanded `inner_request` is covered by `request_envelope_sha256`, while
classification remains `decision_input`-only.

### 5.4 Canonical 0.5 expansion

0.5 expansion is the following total deterministic function:

1. Strict-parse one compact JCS-compatible JSON value under the ordinary byte,
   Unicode, number, duplicate-key, and resource-limit rules.
2. Apply the common-schema pointer-budget phase in section 5.7, then construct
   the complete common compact-schema and selector candidate pool. If that pool
   is nonempty, select and emit its one error under section 5.7 and stop before
   target registry-entry verification, target-schema construction, or target
   pointer enumeration.
3. Only when the common/selector pool is empty, use the exact declared tuple
   already established by selector validation to identify its one selected
   profile, then verify that profile's target contract and template byte-length
   and SHA-256 pins.
4. Only after that empty prior pool and successful registry verification, apply
   the target-schema pointer-budget phase in section 5.7, then validate the
   target-specific decision input and exact operation/obligation mapping. A
   target candidate is selected only from the fresh target-phase pool.
5. Decode the template's base64, verify it is exactly one JCS JSON object, and
   deep-copy it.
6. Replace only the two registered pointers with compact `request_id` and
   `operation_handle`.
7. Validate the expanded inner object against the target contract's pinned
   inner-request schema.
8. Compute:

   ```text
   decision_input_sha256 =
     SHA256_UPPER(RFC8785_JCS(compact.decision_input))
   ```

9. Construct the direct request with the exact target format,
   `accept_response_format_version`, copied IDs and decision input, expanded
   inner object, `decision_input_sha256`, and
   `request_envelope_sha256 = ZERO64`.
10. Set `request_envelope_sha256` to the LF-excluded self-zero digest defined
    in section 1.
11. Validate the complete direct request against the exact pinned 0.5 schema.
12. Emit exactly `RFC8785_JCS(direct_request) || LF` atomically to stdout,
    emit zero bytes to stderr, exit 0, and invoke no target engine.

There is no clock, randomness, network, ambient environment input, path search,
or caller-selected template. The expander uses only compact bytes and admitted
registry bytes. This is an expander-only CLI ABI: success returns only the
expanded direct-request wire. A caller or parity harness may subsequently pass
those bytes to the exact target engine as a separate process step; target
response bytes and target exits are never multiplexed into expander stdout or
substituted for expander exit 0.

### 5.5 Frozen composed-0.3 legacy profile

A separately versioned compact schema and profile MAY target the frozen
composed-0.3 engine solely as an additive adapter:

```text
compact format = B1-SEMANTIC-DECISION-COMPACT-COMPOSED-0.3-ADAPTER-0.1
expansion_profile_id = B1-INNER-TEMPLATE-COMPOSED-0.3-FROZEN
target_generation_id = COMPOSED-0.3-FROZEN
target request format = B1-SEMANTIC-DECISION-REQUEST-0.2
target response format = PCB-RUNNER-RESPONSE-0.2
```

That legacy compact schema has the same bounded ID fields as section 5.2 but
fixes the five identifiers above, fixes `accept_response_format_version` to
`PCB-RUNNER-RESPONSE-0.2` as adapter negotiation metadata, and validates
`decision_input` against the composed-0.3 schema. Its distinct compact format
prevents a 0.5 compact request from being reinterpreted as a legacy adapter
request.

That target request string is the recorded 0.2/0.3 grandfathered collision.
The legacy profile is unambiguous only because it pins the composed-0.3
contract digest and names that exact engine as its downstream target. The
expander-only command still invokes no engine. It MUST NOT infer 0.3 from the
colliding request format.

Legacy expansion emits the exact frozen fields only. In particular it MUST NOT
insert `accept_response_format_version`, `decision_input_sha256`, or
`request_envelope_sha256` into 0.3 bytes. It computes the two frozen inner
digests exactly as follows and produces a request accepted by the unchanged
composed-0.3 schema:

```text
inner_request_raw_sha256 =
  SHA256_UPPER(RFC8785_JCS(inner_request) || LF)

inner_input_sha256 =
  SHA256_UPPER(RFC8785_JCS(inner_request.input))
```

The frozen engine response remains the parity authority.

### 5.6 Version, collision, and error rules

1. A compact format string MUST identify exactly one compact schema semantic
   digest. A new collision fails generation admission.
2. An `expansion_profile_id` MUST identify exactly one registry-entry digest.
   Rebinding an ID fails admission even if the new template is schema-valid.
3. The tuple `(compact_format_version, target_generation_id,
   target_request_format_version, target_response_format_version)` MUST map to
   exactly one expansion algorithm and contract digest.
4. Registry collisions are build/admission failures, not runtime classes and
   not semantic FAIL responses.
5. An expander MUST NOT fall back to another profile, response version,
   generation, or template after any error.

The five compact selector fields are `format_version`, `expansion_profile_id`,
`target_generation_id`, `target_request_format_version`, and
`accept_response_format_version`. The minimal scanner may read only those
fields to select a declared profile. It may not classify the decision input or
accept the rest of the request before full schema validation. All runtime
failures before successful direct-request emission use the distinct error wire
in section 5.7; neither a direct 0.5 response nor a frozen response format is
borrowed.

### 5.7 Compact-expander error wire

The compact expander has one error format, distinct from every direct-engine
and frozen response format:

```text
B1-COMPACT-EXPANDER-ERROR-0.5
```

Its top-level schema and nested error schema are closed. The top-level object
has exactly these required fields:

| field | exact rule |
|---|---|
| `format_version` | const `B1-COMPACT-EXPANDER-ERROR-0.5` |
| `ok` | const `false` |
| `request_id` | `RUN_[A-F0-9]{24}` echo or sentinel under the law below |
| `result` | const `ERROR` |
| `exit_code` | `2` for every client/protocol error; `3` only for `ERR_INTERNAL` |
| `errors` | array with `minItems: 1`, `maxItems: 1`, containing the one selected closed error object |
| `output` | const `null` |
| `error_response_sha256` | nonzero uppercase SHA-256 of the self-zero preimage below |

The sole error object has exactly `code`, `message`, `pointer`, and
`precedence`. `pointer` is an NFC RFC 6901 pointer or the empty root pointer,
with a maximum of 4096 Unicode scalar values and only canonical `~0`/`~1`
escapes. Code, message, and precedence are inseparable:

| code | precedence | exact message | exit |
|---|---:|---|---:|
| `ERR_EMPTY_INPUT` | 10 | `Input is absent or empty.` | 2 |
| `ERR_UTF8` | 20 | `Input is not strict UTF-8.` | 2 |
| `ERR_BOM` | 30 | `UTF-8 BOM is forbidden.` | 2 |
| `ERR_DUPLICATE_KEY` | 40 | `Duplicate JSON object key.` | 2 |
| `ERR_JSON` | 50 | `Invalid JSON or trailing bytes.` | 2 |
| `ERR_NFC` | 60 | `String is not Unicode NFC.` | 2 |
| `ERR_NUMBER` | 70 | `Number violates the safe integer model.` | 2 |
| `ERR_GENERATION_UNDECLARED` | 75 | `Generation declaration is absent.` | 2 |
| `ERR_GENERATION_UNSUPPORTED` | 76 | `Generation declaration is not supported.` | 2 |
| `ERR_SCHEMA` | 80 | `Compact request does not validate.` | 2 |
| `ERR_LIMIT` | 90 | `A deterministic resource limit was exceeded.` | 2 |
| `ERR_INTERNAL` | 100 | `Compact expansion failed internally.` | 3 |

No other code, message, precedence, or exit is admitted. In particular,
INAPPLICABLE exit 4 belongs to a successfully expanded direct 0.5 decision and
can never appear on this error wire.

To seal an error object `E`, replace only `E.error_response_sha256` with
`ZERO64` and compute:

```text
error_response_sha256 =
  SHA256_UPPER(RFC8785_JCS(E with error_response_sha256 = ZERO64))
```

The preimage excludes LF. On failure the expander writes exactly
`RFC8785_JCS(E) || LF` atomically to stdout, writes nothing to stderr, emits no
partial expanded request, and does not invoke a target engine. The process exit
is the sealed `exit_code`. A seal mismatch in a recorded expander error is a
verification failure; it is not reclassified by the expander.

#### Request-ID echo and sentinel

The sentinel is exactly `RUN_000000000000000000000000`. Echo the received
`request_id` only if strict decoding through the NFC and safe-number checks has
produced one top-level object with one `request_id` whose value already matches
`^RUN_[A-F0-9]{24}$`. Otherwise use the sentinel. Thus raw parse failures,
duplicate `request_id` keys, a non-object top level, and a missing or malformed
request ID use the sentinel. A valid request ID is echoed on selector, schema,
post-selection registry, and expansion failures. An `ERR_LIMIT` before safe
request-ID extraction uses the sentinel; one after extraction echoes it.

#### Selector taxonomy

A syntactically valid selector is a string matching
`^[A-Z0-9][A-Z0-9._-]{0,159}$`. This is the compact specialization of the
shared direct-and-compact taxonomy in section 1; a direct request applies the
same four classifications to its direct selector set and emits its direct
error wire. Recognition is per selector position in the admitted registry,
not a search across arbitrary string values. Apply these rules to the five
compact selector pointers:

1. A missing selector property in a top-level object contributes
   `ERR_GENERATION_UNDECLARED` at that property's pointer.
2. A present non-string or syntactically malformed selector contributes
   `ERR_SCHEMA` at that property's pointer.
3. A syntactically valid selector value unrecognized in that selector position,
   recognized only by a disabled entry, or recognized by an entry unavailable
   in the invoked build contributes `ERR_GENERATION_UNSUPPORTED` at that
   property's pointer.
4. A recognized and enabled `expansion_profile_id` uniquely selects one
   registry row. After all five values are individually recognized and enabled,
   any selector value that differs from that row contributes `ERR_SCHEMA` at
   the differing selector pointer. This is a recognized tuple contradiction,
   not an unsupported generation.
5. Only an exact enabled tuple advances to full target-specific compact-schema
   validation. There is no prefix match, inferred generation, downgrade, or
   alternate-profile retry.

`ERR_GENERATION_UNDECLARED` is therefore reserved for absence. An unknown
profile string is UNSUPPORTED, not UNDECLARED. A 0.5 compact format paired with
the recognized frozen response offer is a tuple contradiction and is SCHEMA,
not a downgrade request.

#### Phase-local candidate pooling and pointer selection

After strict raw parsing, compact validation is fail-closed and phase-local.
The expander builds error candidates rather than using library exception order,
and each candidate is `(precedence, pointer, code)`. The common/selector pool
contains every common compact-schema candidate that does not require a target
profile, including top-level type, required non-selector fields, additional
properties, request-ID shape, and operation/obligation shape, plus every
selector candidate under the taxonomy above.

The common/selector pool and target pool are never combined. After the common
pointer-budget pass, the expander constructs the complete common/selector pool.
If it is nonempty, the expander selects and emits its one error and stops before
verifying the selected registry entry's target pins, constructing a target
schema, or enumerating any target pointer. Only an empty common/selector pool
may advance to registry verification. Only successful registry verification
may reach the target pointer-budget pass and construction of a fresh
target-specific decision-input and exact-pair candidate pool. The prior pool is
empty by construction whenever the target phase is reached.

Schema pointers are canonicalized as follows:

- a missing required property points to the absent child;
- an additional property points to that property;
- type, const, enum, pattern, length, range, item, and value failures point to
  the failing instance;
- operation/obligation/decision-input mapping failures point to every field
  participating in the failed equality; and
- deterministic discriminators select one schema branch; library-level
  `oneOf` summary diagnostics never enter the pool.

Before constructing candidates for a schema phase, the expander performs a
deterministic pointer-budget pass for that phase. It enumerates, without
emitting diagnostics:

1. the canonical pointer to every present instance location that the phase's
   schema can inspect, including every additional property and array item;
2. the canonical pointer to every absent required child of each reached object;
   and
3. every operation/obligation/decision-input equality pointer the phase can
   emit.

The common-schema pass runs after strict decoding and before any common or
selector candidate is constructed. The target-schema pass runs only after the
common/selector pool is empty, an exact enabled selector tuple is resolved, and
the selected registry entry is verified, and it runs before any target-specific
candidate is constructed. Pointer tokens are escaped per RFC 6901 before
length measurement; the leading `/` separators and escaped-token characters
count, and length is measured in Unicode scalar values. The root pointer has
length zero. A canonical pointer of exactly 4096 scalar values is admitted. If
any enumerated pointer is longer than 4096, the reached phase stops and emits
only `ERR_LIMIT` at the empty root pointer. Candidate construction for that
phase has not begun, and every later phase is skipped.

A target-phase pointer longer than 4096 therefore produces the sole root
`ERR_LIMIT` only when the target phase is actually reached. A nonempty
common/selector pool prevents all target pointer construction, so a latent
target 4097-pointer cannot replace an earlier common or selector error. When a
target pointer-budget limit is emitted, the prior pool is empty by the target
phase precondition. A pointer-budget limit after safe request-ID extraction
echoes the valid ID under the rule above. This boundary applies even if the
overlong location would otherwise have produced `ERR_SCHEMA`; pointer
truncation and parent-pointer substitution are forbidden.

If the common pointer-budget pass succeeds, construct the full common/selector
pool. If it is nonempty, select the one candidate with the lowest numeric
precedence and emit it immediately. At equal precedence choose the
lexicographically smallest pointer by Unicode scalar-value sequence. If both
are equal, choose the ASCII-lexicographically smallest code. Only an empty pool
advances to selected-entry verification. After that verification and a
successful target pointer-budget pass, construct the full target pool and use
the same selection rule; only an empty target pool advances to expansion. Raw
byte/JSON failures have the empty pointer and their fixed precedence. Other
deterministic resource limits are likewise checked at their declared reached
phase boundary before that phase's candidate generation and emit only
`ERR_LIMIT` at the empty pointer, so a partial pool is never used.

Only after an exact selector tuple and an empty common/selector pool does the
expander verify the selected registry entry before target-specific schema
validation. An admitted entry whose byte length, digest, template, substitution
pointers, or contract pin no longer matches its admission record produces
`ERR_INTERNAL` at the empty pointer. The same mapping applies to an unexpected
local expansion failure after the common/selector phase.
Disabled or unavailable entries remain UNSUPPORTED; they are not internal
corruption. Admission-time identifier collisions reject the build before an
expander is runnable.

#### Required compact-error fixtures

The compact error pack MUST pin exact JCS+LF bytes, seal, request-ID value,
pointer, code, message, precedence, output, stderr, and process exit for:

- every raw error from 10 through 70 and `ERR_LIMIT` before and after safe
  request-ID extraction;
- each selector missing alone and all selectors missing together;
- non-string and malformed values at each selector pointer;
- unrecognized and disabled values at each selector pointer;
- one and multiple recognized tuple contradictions;
- simultaneous missing, unsupported, and schema candidates to prove numeric
  precedence;
- equal-precedence candidates whose pointer order differs from discovery order;
- a mixed common-schema plus target-schema case with an exact enabled selector
  tuple and valid retained request ID: an additional top-level `z_common`
  property contributes common `ERR_SCHEMA` at `/z_common`, while an APPLICABLE
  target decision input omits required `/decision_input/facts`. The fixture MUST
  emit the byte-exact common error without constructing the target schema;
- a mixed common-schema plus target-4097 case with the same common error and an
  otherwise-valid target decision input containing a target-only property whose
  canonical pointer is exactly 4097 scalar values. The fixture MUST emit the
  byte-exact `/z_common` `ERR_SCHEMA`; the unreached target budget MUST NOT emit
  root `ERR_LIMIT`;
- a mixed common-schema plus selected-registry-corruption case with the same
  common error and a controlled selected entry whose target digest pin is
  corrupt. The fixture MUST emit the byte-exact `/z_common` `ERR_SCHEMA` before
  registry pin verification; it MUST NOT emit `ERR_INTERNAL`;
- for each of those three mixed cases, pin the fixed valid `request_id` and its
  exact echo, the complete JCS+LF stdout bytes, `error_response_sha256` receipt,
  empty stderr, process exit 2, zero partial direct-request bytes, and zero
  target-engine invocations;
- a reached-target pointer-boundary trio whose compact requests use the exact
  enabled generation/profile selector tuple, a valid digest-pinned selected
  registry entry, and no common compact-schema or selector candidate. Each
  request is otherwise target-valid except for one additional property directly
  under `decision_input`, so the location is target-only. Its property token is
  made only of ASCII `A` and has length 4079, 4080, or 4081; after RFC 6901
  escaping, the 16-scalar `/decision_input/` prefix makes the complete
  diagnostic pointer exactly 4095, 4096, or 4097 scalar values. The 4095- and
  4096-pointer cases MUST emit `ERR_SCHEMA`/80, message
  `Compact request does not validate.`, at their complete exact target pointer.
  The 4097-pointer case MUST emit the sole `ERR_LIMIT`/90, message
  `A deterministic resource limit was exceeded.`, at the empty root pointer,
  with no target candidate constructed and no pointer truncation or parent
  substitution. All three MUST pin the same fixed valid `request_id` and exact
  echo, complete JCS+LF stdout, `error_response_sha256` receipt, empty stderr,
  process exit 2, zero partial direct-request bytes, and zero target-engine
  invocations;
- otherwise-valid compact objects with one additional top-level property made
  only of ASCII `A`: key lengths 4094 and 4095 create exact 4095- and
  4096-scalar pointers and produce `ERR_SCHEMA` with the complete pointer, while
  key length 4096 creates a 4097-scalar pointer and produces sole `ERR_LIMIT` at
  the empty pointer; all three fixtures echo their valid request ID;
- nested property tokens containing `/` and `~` at the pointer-budget boundary
  to prove canonical escaping is measured before the 4096 comparison;
- malformed, missing, duplicate, and valid request IDs to prove sentinel/echo;
- selected-entry digest, length, template, pointer, and contract-pin corruption
  to prove `ERR_INTERNAL`, empty pointer, exit 3, and no fallback; and
- mutation of every sealed error field to prove self-zero verification.

The compact error schema, format semantic digest, fixtures, receipts, manifest,
and conformance runner are new 0.5 artifacts. They do not change a direct or
frozen response schema.

In particular, the compact wire's 4096-scalar pointer budget does not cap,
truncate, or substitute for a direct-engine error pointer. Once compact
expansion succeeds and its JCS+LF output is passed to the direct engine, the
core section 4.1.2 `DIGESTED_RFC6901_SHA256_96` law exclusively owns any direct
error-pointer containment.

### 5.8 Parity obligations

No compact profile is admitted until all of the following pass:

1. **Expansion byte fixture:** a reference direct constructor and the compact
   expander receive the same IDs, decision input, target pair, and pinned
   template. The expander-only CLI MUST write exactly the reference direct
   constructor's sealed request bytes as JCS+LF to stdout, write zero bytes to
   stderr, exit 0, and invoke no target engine.
2. **Response parity:** invoking the target engine on those two byte-identical
   direct requests as a separate harness step yields byte-identical response
   bytes.
3. **Semantic-pack parity:** every semantic fixture entry for the target
   generation supplies its IDs and decision input to both constructors. The
   constructed direct request bytes and final response bytes MUST match. For a
   legacy 0.3 profile, the canonical-template response MUST additionally be
   byte-identical to the frozen fixture's expected response even though the
   fixture's inert inner-request bytes may differ.
4. **Fuzz parity:** every entry in the seeded semantic fuzz corpus supplies the
   same tuple to direct and compact-expanded paths; constructed request bytes
   and final response bytes MUST match for every entry. The seed is recorded
   in the test file. Compact-wire parser mutations are a separate error-law
   corpus and do not replace this full semantic-corpus differential.
5. **Error parity:** mutations after expansion (digest, seal, ID, generation,
   or schema) select the same direct-engine error as the equivalent direct
   mutation; compact-only failures emit byte-exact section-5.7 error objects and
   never a target-engine response.
6. **Cross-platform parity:** the same registry and compact bytes produce the
   same stdout bytes, empty stderr, exit 0, and zero target-engine invocations
   on every admitted platform; the separate target step then produces the same
   response bytes and target exit.
7. **Compact-error parity:** every raw, selector, base-schema,
   target-schema, registry-corruption, and local-runtime error fixture produces
   byte-identical `B1-COMPACT-EXPANDER-ERROR-0.5` stdout, the expected exit,
   empty stderr, and zero target-engine invocations across platforms.

A single mismatch rejects the profile. Performance or request-size
measurements cannot waive byte parity.

### 5.9 Compact example

```json
{
  "format_version": "B1-SEMANTIC-DECISION-COMPACT-0.5",
  "expansion_profile_id": "B1-INNER-TEMPLATE-0.5",
  "target_generation_id": "B1-GENERATION-0.5",
  "target_request_format_version": "B1-SEMANTIC-DECISION-REQUEST-0.5",
  "accept_response_format_version": "PCB-RUNNER-RESPONSE-0.5",
  "request_id": "RUN_0123456789ABCDEF01234567",
  "operation_handle": "OPR_7A807E16F793A8437DD18F21",
  "obligation_id": "OBL-30",
  "decision_input": {
    "format_version": "B1-SEMANTIC-FACTS-0.5",
    "operation_handle": "OPR_7A807E16F793A8437DD18F21",
    "obligation_id": "OBL-30",
    "applicability": {
      "status": "APPLICABLE",
      "applicability_profile_id": "HOST-SELECTION-PROFILE-1"
    },
    "facts": {
      "intent_episode_id": "EPISODE_001",
      "intent_purpose_id": "PURPOSE_A",
      "intent_scope_ref": "SCOPE_A",
      "intent_action_class": "ACTION_CLASS_A",
      "intent_version_sha256": "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC1",
      "candidate_pool": [
        {
          "record_id": "REC_A",
          "episode_id": "EPISODE_001",
          "purpose_id": "PURPOSE_A",
          "scope_ref": "SCOPE_A",
          "action_class": "ACTION_CLASS_A",
          "version_sha256": "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC1",
          "similarity_rank": 1
        }
      ],
      "pool_record_ids": ["REC_A"],
      "compatibility_verdicts": [
        {"record_id":"REC_A","compatible":true,"rejection_reasons":[]}
      ],
      "compatible_record_ids": ["REC_A"],
      "incompatible_record_ids": [],
      "selected_record_ids": ["REC_A"],
      "excluded_records": [],
      "excluded_record_ids": []
    }
  }
}
```

The caller does not send inner packet material or any digest. The expander
produces them and the complete sealed request deterministically.

### 5.10 Alternatives and unresolved compact-profile questions

Rejected alternatives:

- treating missing `inner_request` fields as implicit defaults inside the
  sealed parser makes the same wire bytes context-dependent;
- accepting arbitrary caller templates recreates the overhead and broadens the
  authority surface; and
- identifying a legacy target only by the colliding 0.2 format string repeats
  E1.

Open before adoption:

1. Choose and pin the actual inner template bytes. This draft deliberately
   does not author regenerated fixture worlds.
2. Decide whether the compact representation itself needs a compact-input
   digest. It is not required for deterministic sealed expansion because the
   resulting direct request binds the decision input and complete envelope.
3. Decide whether the frozen-0.3 adapter ships in the same registry or a
   legacy-only registry. Either way its generation and contract digest must be
   explicit.

## 6. Combined migration and regeneration obligations

Adoption is atomic at the new-generation boundary. It requires all of the
following new artifacts or equivalent sections in new artifacts:

1. unique 0.5 request, response, decision-input, compact, compact-expander
   error, applicability, and fixture-profile schemas;
2. exact-pair generation negotiation plus direct and compact error-law fixtures,
   including the shared missing/non-string-or-malformed/unsupported/tuple-
   contradiction taxonomy and compact precedences 10 through 100;
3. the digest-bound fixture-class profile registry;
4. the digest-bound compact-expansion profile registry;
5. the 0.5 OBL-24 compiled predicates and authority entries;
6. the applicability decision branch, result mapping, fifth fixture class,
   exit-code-4 reservation, exact 1-through-160 ASCII
   `applicability_profile_id` language and both-branch 159/160/161 boundary
   fixtures, shared union reference derivation with 64-cap and truncation, the
   APPLICABLE-empty plus INAPPLICABLE-duplicate/64/65 fixture split,
   branch/source schema-negative fixtures, and one INAPPLICABLE semantic
   fixture per admitted operation;
7. the OBL-30 derivation algorithm, checked projections, ordered rejection
   reasons, and revised authority entries;
8. regenerated semantic, competence, negative, metamorphic, direct error-law,
   compact error-wire including common-plus-target, common-plus-target-4097,
   common-plus-registry-corruption phase-law cases, and the reached-target
   4095/4096/4097 pointer trio, wrapper parity, transcript, and compact/direct
   parity fixtures;
9. inherited direct E6 containment fixtures from core section 4.1.2: otherwise
   identical ordinary zero-receipt responses whose `B` is exactly 16,777,215,
   16,777,216, and 16,777,217 bytes, with the first two carrying the complete
   inline pointer and the last carrying `DIGESTED_RFC6901_SHA256_96`; plus the
   separate top-level additional-property witness whose name is exactly
   8,388,608 ASCII `/` characters and whose complete selected pointer is one
   leading `/` plus 8,388,608 `~1` escapes, exactly 16,777,217 scalars and
   UTF-8 bytes. These fixtures MUST pin the final response JCS+LF bytes and
   length, pointer digest and scalar/UTF-8 lengths, exact first/last 96-scalar
   fragments, the validated `decision_input_sha256` or `ZERO64`,
   `request_raw_sha256`, unchanged code/message/precedence/request ID/exit, and
   receipt, and MUST prove selection precedes containment without truncation or
   parent substitution;
10. regenerated control digests, pack seals, receipts, manifests, examples, and
   documentation that refer only to new 0.5 bytes; and
11. a migration tool or documented transform that fails closed on inconsistent
    legacy OBL-30 bookkeeping and never rewrites a historical record.

Before adoption, the complete existing validation gate remains green and the
new 0.5 gate MUST additionally prove:

- no tracked sealed 0.2/0.3 byte changed;
- frozen old engines reject 0.5 requests under their unchanged error law and
  never interpret them as 0.2 or 0.3;
- new engines select only an exact declared request/response pair and use
  missing -> `ERR_GENERATION_UNDECLARED`/75, present non-string or malformed ->
  `ERR_SCHEMA`/80, syntactically valid unknown/disabled/unavailable ->
  `ERR_GENERATION_UNSUPPORTED`/76, and recognized tuple contradiction ->
  `ERR_SCHEMA`/80 on both direct and compact wires, with no fallback;
- INAPPLICABLE exits 4 while direct and compact `ERR_INTERNAL` exits 3;
- every direct error inherits core section 4.1.2 exactly: complete-pointer
  selection precedes representation, an ordinary zero-receipt response at
  16,777,215 or 16,777,216 bytes uses the complete inline pointer, one at
  16,777,217 bytes uses `DIGESTED_RFC6901_SHA256_96`, and the 8,388,608-slash
  additional-property witness uses that bounded object while retaining the
  selected error, request ID, exit, request bindings, and receipt;
- `applicability_profile_id` admits exactly
  `^[A-Z0-9][A-Z0-9._-]{0,159}$`, with byte-exact 159/160/161 boundary
  fixtures on both APPLICABLE and INAPPLICABLE branches;
- record-reference union, dedupe, unsigned-UTF-16 order, 64-cap, and truncation
  match APPLICABLE empty and INAPPLICABLE duplicate, 64-distinct, and
  65-distinct fixtures, with no impossible empty-INAPPLICABLE case;
- every compact failure emits the sole sealed compact-error format with exact
  selector taxonomy, request-ID echo/sentinel, pointer, stdout/stderr, and exit;
- compact validation emits a selected common-or-selector error before selected
  target registry verification or target pointer construction; target
  validation and its pointer budget run only when the prior pool is empty, and
  the mixed common-plus-target, common-plus-target-4097, and
  common-plus-registry-corruption fixtures pin that ordering byte-for-byte;
- compact pointer-budget fixtures admit exact 4095- and 4096-scalar diagnostic
  pointers and convert a 4097-scalar pointer to sole root `ERR_LIMIT` before
  candidate construction only within the phase that is actually reached; the
  target-phase boundary is independently pinned by an exact enabled tuple,
  valid registry entry, empty prior pool, and target-only 4095/4096/4097
  diagnostic-pointer trio;
- every compact success emits only the expanded direct-request JCS+LF on
  stdout, emits empty stderr, exits 0, and invokes no engine; target invocation
  is a separate parity-harness step;
- compact/direct byte and response parity over every semantic fixture and the
  seeded fuzz corpus;
- authority-register agreement in both directions for every new required
  field; and
- deterministic output under the admitted runtime profile with clock,
  randomness, network, and ambient environment denied.

No sealed 0.3 fixture, receipt, pinned example output, or historical acceptance
record is a migration target. Frozen clients may continue to use their frozen
wire and the additive 0.4 closures; 0.5 behavior begins only after explicit
generation negotiation.

## 7. Adoption questions summary

At the proposal-text level, direct E6 is no longer a future design item: this
document inherits the complete `DIGESTED_RFC6901_SHA256_96` law from core
section 4.1.2 and the boundary obligations in section 6. The combined candidate
is not implemented or eligible for adoption until the complete section-6
artifact and independent-acceptance chain exists. Subject to that evidence
gate, these direction choices remain honestly open:

1. approve parameterized OBL-24 rather than the narrow artifact-audit rename;
2. name at least one non-default fixture-class profile and decide whether
   required and allowed class sets may differ;
3. decide whether applicability profile IDs are opaque host IDs or registered
   contract IDs and whether basis refs may be empty;
4. confirm that every admitted operation permits INAPPLICABLE;
5. confirm OBL-30 select-all-compatible behavior, canonical projection order,
   and removal of the two redundant caller fields;
6. pin, without generating experiment or oracle material in this draft, the
   exact compact expansion template and registry artifacts.

Until those questions are resolved, this file remains **PROPOSED / NOT
ADOPTED** and cannot serve as a conformance, security, or performance claim.
