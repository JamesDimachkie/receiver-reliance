# Proposed generation 0.5 core wire, binding, and sealed-response contract

> **PROPOSED / NOT ADOPTED / NOT IMPLEMENTED.** This document is a design
> candidate for a future sealed generation. It is not an amendment to the
> accepted 0.2 or composed 0.3 contracts, does not change any accepted byte,
> and is not evidence that a 0.5 implementation or fixture pack conforms.
> Within this document, **MUST**, **MUST NOT**, **SHOULD**, and **MAY** describe
> requirements of the proposed 0.5 candidate only.

## 1. Purpose and authority boundary

This proposal closes only the three confirmed defect classes identified as
ERRATA E1, E2, and E3:

1. give the next generation a distinct request wire-format string and an
   explicit, fail-closed response-format negotiation;
2. place the decision-input digest, predicate evaluation trace, and derived
   record references inside the receipt-sealed response; and
3. replace the two misleading inner-request digest fields with a direct
   `decision_input` digest and a self-zero seal over the complete request
   envelope.

The accepted 0.2 and composed 0.3 artifacts remain independent frozen
authorities. This proposal consumes their operation registry, deterministic
profile, class precedence, and host/engine boundary as design inputs; it does
not rewrite them. Any 0.5 semantic changes, including the disposition of E4,
E5 or E7, require a separately reviewed semantic authority. The response
shape below admits the companion proposal's `INAPPLICABLE` branch so the two
drafts do not prescribe incompatible 0.5 schemas; the trigger and semantics of
that branch remain owned by the semantic authority. When this core proposal
and a semantic proposal otherwise disagree, the candidate is incomplete and
MUST NOT be sealed until the disagreement is resolved in new 0.5 bytes.
This core owns E6's direct exact-pointer containment representation in section
4.1.2; the companion semantic authority inherits it without redefining it.

The engine remains a deterministic classifier of host-attested facts. It does
not make those facts true, serialize concurrent state, execute effects,
authenticate digests, or establish external conformance. `HOST_OBLIGATIONS.md`
H1 through H3 and H5 through H6 continue to describe the integration boundary.
H4 remains the rule for frozen generations with no abstention mechanism; a
separately adopted 0.5 semantic authority may move calibrated abstention into
an explicit `INAPPLICABLE` input and response branch. In particular, the new
digests are consistency and transcript-binding mechanisms, not signatures or
claims of authenticity.

### 1.1 Normative constants

| Name | Proposed exact value |
|---|---|
| interface id | `B1-SEMANTIC-DECISION-INTERFACE-0.5` |
| semantic contract version | `B1-SEMANTIC-DECISION-0.5` |
| request format | `B1-SEMANTIC-DECISION-REQUEST-0.5` |
| response format | `PCB-RUNNER-RESPONSE-0.5` |
| effect-receipt domain | `B1-SEMANTIC-EFFECT-RECEIPT-0.5` |
| zero digest sentinel | 64 ASCII `0` characters (`ZERO64`) |
| digest algorithm/encoding | SHA-256, uppercase hexadecimal, exactly 64 characters |
| canonical JSON | RFC 8785 JCS encoded as UTF-8 |

The request and response strings above are new wire identities. They MUST NOT
be aliases for `B1-SEMANTIC-DECISION-REQUEST-0.2` or
`PCB-RUNNER-RESPONSE-0.2`.

## 2. Proposed wire and generation negotiation (E1)

### 2.1 Exact-pair negotiation

Every 0.5 request MUST contain both:

```json
{
  "format_version": "B1-SEMANTIC-DECISION-REQUEST-0.5",
  "accept_response_format_version": "PCB-RUNNER-RESPONSE-0.5"
}
```

These fields are an exact-pair offer, not a version range. A 0.5 endpoint
supports exactly the pair in section 1.1. It MUST NOT select a lower, higher,
or lexically similar generation, and it MUST NOT infer a generation from
operation handles, request shape, nested packet strings, fixture labels, or
any ambient configuration.

On a valid semantic decision, the response `format_version` MUST be the exact
offered `accept_response_format_version`. Because 0.5 offers only one response
format, no preference or server-choice ordering exists.

The nested legacy `inner_request.format_version` remains an auxiliary packet
format identifier. It is not the outer semantic generation declaration and
MUST NOT participate in outer dispatch or generation negotiation.

### 2.2 Undeclared and unsupported generations

Generation inspection occurs only after the input has passed the strict
UTF-8/JSON/NFC/number checks and the parsed root is an object. It precedes
general target-specific request-schema validation. The two direct selectors
are `format_version` and `accept_response_format_version`. For either field, a
syntactically valid selector is a string matching exactly
`^[A-Z0-9][A-Z0-9._-]{0,159}$`; recognition is per selector position in the
admitted direct-generation registry.

Apply this four-way taxonomy without fallback:

1. A missing selector property produces `ERR_GENERATION_UNDECLARED` at that
   property's pointer, precedence 75.
2. A present non-string or a string that fails the selector syntax produces
   `ERR_SCHEMA` at that property's pointer, precedence 80.
3. A syntactically valid selector that is unrecognized in that position,
   recognized only by a disabled entry, or recognized by an entry unavailable
   in the invoked build produces `ERR_GENERATION_UNSUPPORTED` at that
   property's pointer, precedence 76.
4. Individually recognized and enabled selector values that do not form the
   one admitted direct request/response tuple produce `ERR_SCHEMA` at every
   selector pointer whose value contradicts the tuple, precedence 80.

Inspect `format_version` first because it selects the direct request schema.
Only an exact recognized and enabled request format permits inspection of
`accept_response_format_version`; an undeclared, malformed, unsupported,
disabled, or unavailable request format cannot cause generation-specific
interpretation of the response offer. Once the request format selects its
unique admitted tuple, apply the same four categories to the response offer.
Only the exact enabled tuple advances to general target-specific schema
validation. There is no prefix match, inferred generation, downgrade, retry,
or selection by an identifier found anywhere else in the request.

An unknown request generation therefore cannot cause the implementation to
interpret generation-specific fields. Missing and unsupported declarations
are rejected deterministically rather than falling through to 0.2 or 0.3.

Generation errors emitted by a dedicated 0.5 endpoint use the 0.5 protocol
error response schema and its self-zero receipt. A future version-neutral
front dispatcher would need its own separately versioned error wire; this
proposal does not define one.

This error wire governs the **direct core engine only**, after a complete 0.5
core envelope has been delivered to it. It does not automatically govern
parsing, validation, or deterministic expansion of the companion compact
surface. Compact-expansion failures MUST use the separate, required contract
in `GEN_0_5_SEMANTICS.md` section 5.7, **Compact-expander error wire**, whose
format is `B1-COMPACT-EXPANDER-ERROR-0.5`; they MUST NOT be mislabeled as core
`PCB-RUNNER-RESPONSE-0.5` errors. That companion contract owns compact
generation/schema failures (exit 2) and compact registry/runtime internal
failures (exit 3). Only after compact expansion succeeds and produces a
complete sealed core request do sections 2.1, 2.2, and 6 govern the direct
engine result.

The companion draft also exclusively owns the compact process shell and
diagnostic-pointer budget. Its section 5.4 requires successful expansion to
emit exactly the direct-request JCS+LF bytes atomically on stdout, emit empty
stderr, exit 0, and invoke no target engine. Its section 5.7 MUST use
phase-local fail-closed validation. The common/selector pointer-budget pass
runs before any common or selector candidate is constructed. If that pass
succeeds, the expander constructs the common/selector candidate pool and, when
the pool is nonempty, immediately selects and emits its winner; selected-entry
verification, target validation, target diagnostic-pointer enumeration, and
the target pointer-budget pass are then unreachable. Only an empty
common/selector pool may advance to selected-entry verification and the target
phase. The reached target pointer-budget pass runs before any target candidate
is constructed, admits exact 4095- and 4096-scalar diagnostic pointers, and
maps a 4097-scalar pointer to sole root `ERR_LIMIT`. A target-phase `ERR_LIMIT`
therefore cannot discard or replace a prior common/selector candidate: no
target pointer is enumerated and no target limit is evaluated while that prior
pool is nonempty. Those compact rules do not silently become direct-core
response rules; their fixtures and receipts remain owned by the companion
compact contract.

### 2.3 Legacy dispatch and compatibility

The 0.2/0.3 collision is grandfathered history, not a negotiation mechanism.
A host serving either legacy generation MUST select it through an explicit
deployment boundary such as a separate executable, endpoint, or immutable
launch argument. Because their outer request-format strings collide, a host
MUST NOT claim to infer 0.2 versus 0.3 from the received bytes.

A multi-generation host MAY route the distinct 0.5 request string to the 0.5
engine. If it also exposes a frozen legacy path, that path MUST emit the exact
legacy response bytes and MUST NOT graft 0.5 fields into those responses.
Sending a legacy request to a dedicated 0.5 endpoint produces
`ERR_GENERATION_UNSUPPORTED`; it is never upgraded implicitly.

## 3. Proposed 0.5 request envelope (E3)

### 3.1 Closed top-level shape

The 0.5 request schema is a closed JSON object (`additionalProperties:false`)
with exactly these required members:

| Field | Proposed constraint and authority |
|---|---|
| `format_version` | constant `B1-SEMANTIC-DECISION-REQUEST-0.5`; outer dispatch authority |
| `accept_response_format_version` | constant `PCB-RUNNER-RESPONSE-0.5`; exact response offer |
| `request_id` | `^RUN_[A-F0-9]{24}$`; echoed in the response |
| `operation_handle` | one handle from the adopted 0.5 operation registry |
| `obligation_id` | the unique obligation mapped from `operation_handle` |
| `inner_request` | validates against the composed legacy inner-packet request schema; auxiliary and non-authoritative for classification |
| `decision_input` | validates against the adopted 0.5 decision-input schema; the only fact profile supplied to classification |
| `decision_input_sha256` | non-zero uppercase hex digest defined in section 3.2 |
| `request_envelope_sha256` | non-zero uppercase hex self-zero seal defined in section 3.3 |

The 0.5 schema removes `inner_request_raw_sha256` and `inner_input_sha256`.
Their names and preimages bind the classification-inert half of the old
envelope and MUST NOT be repurposed with new meanings.

Within the adopted 0.5 decision-input schema,
`applicability.applicability_profile_id` is required in both the `APPLICABLE`
and `INAPPLICABLE` branches and MUST be a JSON string matching exactly
`^[A-Z0-9][A-Z0-9._-]{0,159}$`. Its admitted language is therefore 1 through
160 ASCII characters; the anchors require a match of the complete string and
do not admit line-mode or terminal-newline behavior. Every admitted value is
therefore already NFC and contains no CR or LF. No broader bounded-string
schema, Unicode identifier rule, 240-scalar reference bound, or
implementation-selected limit may substitute for this syntax. Whether
otherwise syntactically valid values remain opaque host IDs or must also
resolve through an adopted profile registry is the companion semantic
authority's separately listed adoption choice; that choice does not alter this
common wire syntax. A missing, non-string, or nonmatching value is `ERR_SCHEMA`
at
`/decision_input/applicability/applicability_profile_id` and cannot reach
applicability evaluation or reference derivation.

The following echo constraints remain mandatory and are pooled as
`ERR_SCHEMA` binding findings:

- outer `request_id` equals `inner_request.request_id`;
- outer `operation_handle` equals `inner_request.operation_handle` and
  `decision_input.operation_handle`;
- the adopted operation registry maps that handle to exactly the outer and
  `decision_input.obligation_id`; and
- `inner_request` remains classification-inert. No label, expected output,
  producer identity, provenance string, free prose, or nested packet fact may
  change classification or the three E2 response fields.

The complete self-zero request seal still binds `inner_request` as part of the
wire transcript. Binding it does not give it classification authority.

### 3.2 Direct decision-input digest

Let `JCS(x)` be the UTF-8 bytes of RFC 8785 canonical JSON and `H(x)` be the
uppercase hexadecimal SHA-256 of byte string `x`. The field is:

```text
decision_input_sha256 = H(JCS(request.decision_input))
```

No prefix, suffix, NUL, BOM, CR, LF, or surrounding envelope bytes are in this
preimage. The digest is computed from the complete `decision_input` object,
including `operation_handle`, `obligation_id`, `applicability`, and `facts`
exactly when the selected branch contains `facts`.

A mismatch contributes `ERR_SCHEMA` at `/decision_input_sha256`.

### 3.3 Complete request-envelope self-zero seal

Create `request_zeroed` as a deep copy of the complete parsed request after
all fields are present, replacing only `request_envelope_sha256` with
`ZERO64`. Do not zero `decision_input_sha256` or any nested field. Then:

```text
request_envelope_sha256 = H(JCS(request_zeroed))
```

The input framing LF is excluded. The final on-wire request is
`JCS(request_with_final_seal) || LF`.

A mismatch contributes `ERR_SCHEMA` at `/request_envelope_sha256`. If both
the direct input digest and envelope seal mismatch, both findings enter the
joint error pool; the global precedence/pointer rule selects the emitted
error. This two-level binding means:

- changing `decision_input` without resealing is detected directly;
- changing the declared input digest without resealing is detected by the
  envelope seal; and
- changing outer echoes, generation declarations, or `inner_request` without
  resealing is detected by the envelope seal.

The seal is deliberately not a keyed authenticator. A caller that is allowed
to construct a request can recompute it.

### 3.4 Binding evaluation order

For a syntactically valid 0.5 root object, implementations MUST:

1. resolve the exact request/response generation pair;
2. validate the closed request schema and composed inner-request schema;
3. pool all echo/registry binding mismatches;
4. recompute and compare `decision_input_sha256`;
5. recompute and compare `request_envelope_sha256`; and
6. evaluate adopted applicability, then the operation table when applicable,
   only if the joint `ERR_SCHEMA` binding pool is empty.

Steps 2 through 5 are conceptually pooled. An implementation MAY compute them
in another deterministic order, but the selected externally visible error
MUST be the same as the rule in section 6.

## 4. Proposed sealed response (E2)

### 4.1 Response families

Every response is a closed object with the existing top-level response
family fields:

`format_version`, `request_id`, `ok`, `result`, `errors`, `output`,
`exit_code`, and `receipt_sha256`.

For 0.5, `format_version` is always `PCB-RUNNER-RESPONSE-0.5`. The semantic
PASS and semantic FAIL branches preserve the existing meanings, and the
schema admits the separately proposed applicability branch:

- semantic `VALID`: `ok:true`, `result:"PASS"`, `errors:[]`, `exit_code:0`;
- semantic defect class: `ok:true`, `result:"FAIL"`, `errors:[]`,
  `exit_code:1`; and
- semantic `INAPPLICABLE`: `ok:true`, `result:"INAPPLICABLE"`, `errors:[]`,
  `exit_code:4`; and
- protocol error: `ok:false`, `result:"INCOMPLETE"`, exactly one error,
  `output:null`, and exit code 2, except `ERR_INTERNAL`, which uses exit code
  3.

#### 4.1.1 Direct-error `request_id` extraction

The direct error sentinel is exactly `RUN_000000000000000000000000`. For each
request, initialize the error-response `request_id` candidate to that sentinel.
Replace it exactly once with the decoded request identifier only after all of
these conditions hold:

1. the complete input has passed the empty-input, strict-UTF-8, BOM,
   duplicate-key, JSON/framing, NFC, and safe-number checks at precedences 10
   through 70, plus every resource limit whose phase precedes construction of
   the safe parsed tree;
2. the decoded top level is exactly one JSON object;
3. the raw object contains exactly one decoded top-level member name equal to
   ASCII `request_id`, counted before any parser could collapse duplicate keys;
   and
4. that member's decoded value is a string matching
   `^RUN_[A-F0-9]{24}$`.

This is a single-key rule. Two `request_id` occurrences use the sentinel even
when their values are identical, and first-key/last-key parser behavior MUST
NOT select an echo. Empty input, invalid UTF-8, BOM, any duplicate key, invalid
JSON or framing, any non-NFC string, any invalid number, a non-object root, and
a missing or malformed request ID all use the sentinel. Escaped member-name or
value spellings are judged after JSON decoding; the decoded member occurrence
is what is counted and the decoded identifier is what is echoed.

For the direct profile in section 5, the pre-extraction resource limits are
the complete input-byte cap and the nesting and scanned-container member/item
caps encountered while constructing the safe tree. They use the sentinel.
Every limit evaluated only after that tree and the valid single request ID have
been retained, including response-size containment, is post-extraction and
echoes the retained ID.

After the four conditions succeed, retain the extracted identifier for every
later direct error. A generation or general schema error therefore echoes a
valid extracted ID, except that a root-type or request-ID schema error cannot
pass extraction and uses the sentinel. `ERR_LIMIT` and `ERR_INTERNAL` use the
sentinel when they occur before extraction completes and echo the retained ID
when they occur afterward. Implementations MUST NOT attempt a second partial
extraction while containing an internal failure. This phase boundary, rather
than exception order or an implementation's parsed-tree behavior, owns every
direct error response and hence its `receipt_sha256` bytes.

#### 4.1.2 Direct exact-pointer containment (E6)

The direct engine first constructs every complete canonical RFC 6901 pointer
and selects the error under section 6 using those complete pointers. Only the
already selected pointer is represented. Representation never changes error
selection, code, message, precedence, protocol-error class, `request_id`, exit,
or the section 4.1.1 extraction phase.

The selected error's `pointer` is `oneOf` exactly two mutually exclusive
branches: (a) an NFC string containing the complete RFC 6901 pointer, including
the empty root pointer, or (b) this closed object with exactly these members:

```json
{
  "method": "DIGESTED_RFC6901_SHA256_96",
  "pointer_sha256": "<SHA-256 uppercase hex of UTF8(full pointer)>",
  "pointer_scalar_length": 0,
  "pointer_utf8_length": 0,
  "prefix_96_scalars": "<exact first min(96,N) scalars>",
  "suffix_96_scalars": "<exact last min(96,N) scalars>",
  "decision_input_sha256": "<validated digest or ZERO64>",
  "request_raw_sha256": "<SHA-256 uppercase hex of exact received bytes>"
}
```

The object has `additionalProperties:false`. Its digest strings are exactly 64
uppercase hexadecimal characters; `pointer_scalar_length` and
`pointer_utf8_length` are safe nonnegative integers. `N` is the complete
pointer's Unicode-scalar length. Prefix and suffix overlap when `N < 192` and
are not deduplicated. `request_raw_sha256` hashes the exact received request
bytes, including the framing LF when present. `decision_input_sha256` is the
validated request field once available and otherwise `ZERO64`. Those request
bindings support retrieval or recomputation of the complete pointer, while the
pointer digest and lengths verify it. This representation binds but does not
inline the complete pointer; its fragments are never substitute pointers.

Let `B` be the JCS+LF byte length of the ordinary response containing the full
pointer string and with only `receipt_sha256` replaced by `ZERO64`. Compute `B`
without allocating the full response: JCS-encode all other fixed response
parts, stream the exact pointer through JSON string escaping while counting
bytes, and add one LF byte. If `B <= 16,777,216`, the inline branch is
mandatory. If `B > 16,777,216`, `DIGESTED_RFC6901_SHA256_96` is mandatory.
The response receipt is then computed under section 4.6 and seals the chosen
representation and both request bindings. The bounded-object response MUST
fit the same cap; failure is the ordinary post-extraction root `ERR_LIMIT`
response, with retained request ID and exit 2, and does not recurse.

This direct-engine law is inherited by direct semantic errors. It is separate
from, and does not modify, the compact expander's 4096-scalar pointer budget.

### 4.2 Required semantic output members

For semantic PASS, semantic FAIL, and semantic `INAPPLICABLE`, `output` is a
closed object with exactly these required fields:

| Field | Proposed derivation |
|---|---|
| `operation_handle` | echo of the validated outer request |
| `obligation_id` | unique registry mapping for the operation |
| `status` | existing class-to-status mapping |
| `result_object` | exactly `{behavior_class, conclusion}` under the adopted class mapping |
| `decision_input_sha256` | exact validated request field; independently recomputable using section 3.2 |
| `request_envelope_sha256` | exact validated request seal from section 3.3 |
| `first_match_predicates` | fixed three-boolean precedence trace from section 4.3 |
| `matched_class_witness` | deterministic minimal witness array from section 4.4 |
| `record_references` | derived array from section 4.5; never caller-selected output |
| `record_references_truncated` | boolean indicating whether the derived candidate set exceeded the 64-item output cap |
| `unresolved_reasons` | existing deterministic class-derived array |
| `effect_receipt_sha256` | 0.5-domain effect seal where applicable, otherwise `null` |

These fields are inside the response's `receipt_sha256` preimage. An ordinary
non-effect response therefore binds what was decided even when
`effect_receipt_sha256` is `null`.

The inherited class-to-output map is exact:

| Behavior class | top-level `result` | `output.status` | `result_object.conclusion` | exit code |
|---|---|---|---|---:|
| `VALID` | `PASS` | `PASS` | `SATISFIED` | 0 |
| `MALFORMED_OR_BOUNDARY` | `FAIL` | `FAIL` | `VIOLATED` | 1 |
| `BINDING_OR_CONFLICT` | `FAIL` | `FAIL` | `VIOLATED` | 1 |
| `OMISSION_OR_INCOMPLETE` | `FAIL` | `FAIL` | `UNRESOLVED` | 1 |
| `INAPPLICABLE` | `INAPPLICABLE` | `INAPPLICABLE` | `INAPPLICABLE` | 4 |

`result_object.behavior_class` is the table's first-column value.
`unresolved_reasons` is `[]` for every class except
`OMISSION_OR_INCOMPLETE`; for that class it is exactly
`["<obligation_id>: authoritative semantic basis is absent or inconsistent"]`
with the actual obligation id substituted. The E1-E3 core does not authorize
a change to that mapping or string.

### 4.3 `first_match_predicates`

This field is a closed object with exactly three boolean members in the
adopted class precedence:

```json
{
  "MALFORMED_OR_BOUNDARY": false,
  "BINDING_OR_CONFLICT": false,
  "OMISSION_OR_INCOMPLETE": false
}
```

After successful schema/envelope validation, an adopted semantic authority
may select `INAPPLICABLE` before the operation table; in that branch all three
members are `false` without evaluating the defect predicates. Otherwise,
starting at `MALFORMED_OR_BOUNDARY`, evaluate predicates in precedence order.
Store the result for each evaluated predicate. At the first `true`, select
that class, stop evaluating later classes, and set every later member to
`false`. If all three evaluate to `false`, select `VALID`. Thus a later
`false` after a match means "not evaluated because an earlier class won," as
on the grounded 0.4 surface; it is not a claim that the later predicate was
total or evaluated.

### 4.4 `matched_class_witness`

`matched_class_witness` is a deterministic minimal structural trace of the
selected outcome path. It is not a proof that host-attested facts are true.

For `VALID`, the array is exactly empty. For `INAPPLICABLE`, the array is
exactly
`[{"op":"EQ","pointers":["/applicability/status"]}]`, recording the
pre-table applicability short-circuit without pretending a defect predicate
ran. For a selected defect class, trace the same predicate evaluation that
selected the class:

- a true atomic node appends one closed object
  `{"op":<operator>,"pointers":[...]}`; `pointers` is the sorted,
  duplicate-free list of every string value in that atomic node that begins
  with `/`, including such strings inside list-valued operator arguments;
- a true `all` node concatenates every child's witness in declared child
  order;
- a true `any` node uses only the first true child's witness in declared
  child order; and
- a true `not` node appends exactly
  `{"op":"not","of":<child operator or "compound">}`.

Pointer sorting uses ascending Unicode scalar-value sequence and is
locale-independent, matching the grounded 0.4 trace construction. This is
separate from the protocol error tie-break, which continues to use UTF-8
pointer bytes.
The trace MUST use the same evaluator and short-circuit decisions as
classification; a divergence is `ERR_INTERNAL`, not a second classification
result.

The adopted 0.5 predicate table MUST make every possible witness fit at most
64 entries and every atomic pointer list fit at most 16 entries. Each emitted
pointer is an RFC 6901 pointer of at most 240 Unicode scalar values. Exceeding
these is a contract/fixture admission failure; implementations MUST NOT
silently truncate a predicate witness.

### 4.5 Derived `record_references`

Build one candidate multiset as the union of all three sources below. The law
is identical for `APPLICABLE` and `INAPPLICABLE`; applicability MUST NOT hide
its subject or basis references from the sealed response. Derivation begins
only after the companion semantic authority's mutually exclusive applicability
branch schema has passed.

1. **Facts-derived candidates.** When `decision_input.facts` is present, walk
   it recursively. An absent facts source contributes zero candidates.
   Key tests are case-sensitive. Add a string leaf when its containing object
   member name contains `record_id` or is exactly `exact_reference`;
   prefix/suffix decoys around `exact_reference` do not match. For an array
   whose containing member name ends in `_record_ids` or is exactly
   `pool_record_ids`, add every string item and do not recurse into its items.
   A non-string item in such a reference-bearing array is `ERR_SCHEMA`, not a
   silently ignored candidate. Recurse into every other object or array.
2. **Applicability subject.** Add the schema-valid present
   `decision_input.applicability.subject_record_id` exactly once. An absent
   subject source contributes zero candidates.
3. **Applicability basis.** Add every string item of a schema-valid present
   `decision_input.applicability.basis_record_refs`, including an item already
   seen in either earlier source. An absent basis source and a present empty
   list each contribute zero candidates.

Source presence is branch-specific and total. An APPLICABLE decision input
requires `facts` and forbids both subject and basis fields. An INAPPLICABLE
decision input forbids `facts`, requires a nonempty bounded-string subject, and
requires a unique bounded-string basis list that may be empty. An absent
branch-forbidden source contributes the empty candidate sequence; it is not
treated as JSON `null`. A missing required source, a present forbidden source,
JSON `null`, a wrong container/scalar type, or an invalid string is
`ERR_SCHEMA` and never reaches reference derivation. These rules therefore do
not turn a schema-invalid source into an empty source.

Every candidate MUST be a nonempty NFC string of at most 240 Unicode scalar
values. For each candidate `s`, compute `JCS(s)`, the RFC 8785 canonical UTF-8
bytes of the JSON string value. Deduplicate candidates by exact `JCS(s)` byte
equality. Order the surviving strings by the lexicographic sequence of their
unsigned UTF-16 code units, exactly the RFC 8785 member-name ordering rule,
with `JCS(s)` bytes as a deterministic tie-break. No locale, case folding,
input order, hash iteration order, or Unicode scalar-value sort participates.

Let `N` be the distinct count after JCS-byte deduplication. Emit the first
`min(N,64)` ordered strings as `record_references`. Set
`record_references_truncated` to `true` exactly when `N > 64`, otherwise
`false`. An empty union therefore emits exactly `[]` and `false`; duplicates
within or across facts, subject, and basis sources emit once; exactly 64
distinct combined references emit all 64 and `false`; 65 or more emit the
first 64 in the specified UTF-16/JCS order and `true`.

The output is never copied from a caller-supplied `record_references` field
and never hard-coded per operation or fixture. Any future replacement of the
name-based extraction rule with a field registry is a semantic-format change
requiring new fixtures and a new response authority.

### 4.6 Response receipt self-zero rule

Create `response_zeroed` as a deep copy of the complete response, replacing
only the top-level `receipt_sha256` with `ZERO64`. Then:

```text
receipt_sha256 = H(JCS(response_zeroed))
```

No LF is included. Stdout is exactly `JCS(response_with_final_receipt) || LF`.
The implementation builds the entire response in memory and makes one atomic
stdout write; stderr is empty.

Because the zeroed preimage contains all of `output`, the receipt binds the
decision-input digest, request-envelope seal, predicate trace, record
references, truncation flag, class, conclusion, and effect receipt together.

### 4.7 Effect receipt interaction

The E1-E3 core does not change which operations emit effect receipts:
OBL-19, OBL-20, OBL-26, and OBL-28 emit one only when their derived class is
`VALID`; every other operation/class, including `INAPPLICABLE`, emits `null`.
It also does not change the host's responsibility for effects. A 0.5 effect
receipt uses the new domain
`B1-SEMANTIC-EFFECT-RECEIPT-0.5` and retains a required
`decision_input_sha256` member computed exactly as in section 3.2. Its
operation-specific field derivations remain subject to the separately
adopted 0.5 semantic contract.

No 0.5 effect receipt is expected to be byte-identical to an accepted 0.2 or
0.3 effect receipt merely because the fact profile is equal. Legacy receipt
bytes remain frozen on legacy paths.

## 5. Determinism and resource caps

Unless a future 0.5 contract supplies new justified and fixture-pinned
limits, the candidate inherits the current deterministic profile:

| Constraint | Proposed 0.5 value |
|---|---:|
| maximum input bytes, including framing LF | 16,777,216 |
| maximum output bytes, including framing LF | 16,777,216 |
| maximum JSON nesting | 128 |
| maximum members or items in a scanned container | 100,000 |
| integer range | -9,007,199,254,740,991 through 9,007,199,254,740,991 |
| witness entries | 64, no truncation |
| pointers per witness atom | 16, no truncation |
| record references emitted | 64, with an explicit truncation flag |
| error objects emitted | exactly 1 |
| direct-engine exit codes | 0 `VALID`; 1 defect; 2 non-internal protocol error; 3 `ERR_INTERNAL`; 4 semantic `INAPPLICABLE` |

Input is exactly one strict UTF-8 RFC 8785-canonical JSON value followed by
one LF. BOM, CR framing, duplicate object keys, trailing bytes, non-NFC
strings, floats, negative zero, and integers outside the safe range are
rejected. String comparison, pointer ordering, reference ordering, hashing,
and traversal MUST be independent of locale, time zone, filesystem order,
hash-map iteration order, or process state.

Engine paths have no clock, randomness, network, ambient-environment, or
mutable global-state input. The 0.5 implementation adds no runtime dependency.
Any randomized test corpus is test-only, uses a fixed seed recorded in the
test file, and records that seed on failure.

## 6. Failure precedence and exact protocol behavior

The 0.5 error registry retains the accepted ordering and inserts the two
generation errors between number-model and schema errors:

| Precedence | Code | Fixed message |
|---:|---|---|
| 10 | `ERR_EMPTY_INPUT` | `Input is absent or empty.` |
| 20 | `ERR_UTF8` | `Input is not strict UTF-8.` |
| 30 | `ERR_BOM` | `UTF-8 BOM is forbidden.` |
| 40 | `ERR_DUPLICATE_KEY` | `Duplicate JSON object key.` |
| 50 | `ERR_JSON` | `Invalid JSON or trailing bytes.` |
| 60 | `ERR_NFC` | `String is not Unicode NFC.` |
| 70 | `ERR_NUMBER` | `Number violates the safe integer model.` |
| 75 | `ERR_GENERATION_UNDECLARED` | `Request or response generation is not declared.` |
| 76 | `ERR_GENERATION_UNSUPPORTED` | `Declared request or response generation is unsupported.` |
| 80 | `ERR_SCHEMA` | `Request does not validate.` |
| 90 | `ERR_LIMIT` | `A deterministic resource limit was exceeded.` |
| 100 | `ERR_INTERNAL` | `A deterministic internal failure occurred.` |

Every detected error enters one joint selection domain except where parsing
cannot safely produce a tree. Emit exactly the error minimizing:

1. numeric precedence ascending; then
2. RFC 6901 pointer UTF-8 bytes ascending.

Generation response-offer inspection is conditional on an already supported
request generation, as specified in section 2.2; it cannot create a lower
pointer that masks an unsupported request generation. Digest, envelope echo,
registry, and schema findings share `ERR_SCHEMA` precedence and participate in
the pointer tie-break. The response-schema receipt is computed even for an
error response.

The emitted `errors` array contains exactly one closed object with exactly
`code`, `pointer`, `message`, and `precedence`. `code`, `message`, and
`precedence` are the selected row above. `pointer` is exactly one section
4.1.2 branch: the complete selected RFC 6901 pointer string (including `""`
for root) or its closed `DIGESTED_RFC6901_SHA256_96` representation. No
alternate wording, additional member, or second finding is permitted.

The error response's `request_id` is determined exclusively by section 4.1.1
before the response receipt is sealed. Error precedence and pointer selection
MUST NOT replace that echo/sentinel choice.

`ERR_INTERNAL` is a deterministic containment result for a failure that the
contract says is unreachable, including divergence between classification
and witness tracing. It MUST NOT expose exception text, stack traces, paths,
environment values, or partial output.

Semantic `INAPPLICABLE` and `ERR_INTERNAL` are non-confusable branches.
`INAPPLICABLE` is `ok:true`, has no error, has a non-null sealed semantic
output, and exits 4. `ERR_INTERNAL` is `ok:false`, has exactly one error,
has `output:null`, and exits 3. The closed 0.5 response schema MUST encode
those exit codes as distinct constants and MUST reject an `INAPPLICABLE`
response carrying exit 3 or an internal-error response carrying exit 4.

The new codes exist only in the 0.5 response schema. The legacy error
registries, numeric precedences, exact error bytes, and exit codes remain
unchanged.

## 7. Fixture-author construction rules

A fixture author implementing this proposal MUST derive expectations from the
new 0.5 contract bytes, never from fixture labels or a frozen implementation.
At minimum, the proposed pack must include:

1. one semantic entry for every adopted operation and every behavior class;
2. direct-core generation cases for each selector missing, non-string,
   syntax-malformed, syntactically valid but unrecognized, disabled, and
   unavailable; a recognized-enabled tuple contradiction; simultaneous
   generation/schema candidates proving precedence; and a legacy request sent
   to the 0.5 endpoint;
3. binding mutations that independently alter `decision_input`, its direct
   digest, the envelope seal, outer/inner echoes, and combinations that test
   the joint pointer pool;
4. two requests with the same request id and same semantic class but distinct
   facts, proving distinct `decision_input_sha256` and response receipts;
5. witness cases for atomic, `all`, `any` first-true, `not`, precedence
   short-circuiting, and `VALID`'s empty witness;
6. combined-source record-reference cases using the feasible branch split: an
   APPLICABLE request with no fact-derived candidate pins exactly `[]` and
   `false`; an INAPPLICABLE request with its required subject duplicated in
   basis pins one copy and `false`; an INAPPLICABLE request with one subject
   plus 63 distinct basis references pins all 64 and `false`; and an
   INAPPLICABLE request with one subject plus 64 distinct basis references pins
   the first 64 and `true`. Every case pins the shared UTF-16/JCS ordering and
   exact capped array. The 65-distinct case crosses a BMP/astral UTF-16 ordering
   boundary. No empty-INAPPLICABLE fixture is permitted. Schema-negative cases
   cover missing, `null`, wrong-type, and forbidden-present sources and prove
   `ERR_SCHEMA`, while valid absence of each branch-forbidden source is pinned
   as a zero-candidate contribution. Additional nonempty branch-parity cases
   MAY be added but do not replace these four boundaries;
7. `applicability_profile_id` max-1/max/max+1 boundary cases in both
   applicability branches: one otherwise-valid `APPLICABLE` request and one
   otherwise-valid `INAPPLICABLE` request at each of 159, 160, and 161 ASCII
   `A` characters. The 159- and 160-character requests pass the profile-ID
   field check and continue normally; the 161-character requests each produce
   `ERR_SCHEMA` at
   `/decision_input/applicability/applicability_profile_id`. Every case pins
   the complete direct response JCS+LF bytes, request-ID choice, exit, and
   receipt after all required request digests and seals are recomputed;
8. byte-exact direct protocol-error fixtures pin the selected error,
   `request_id`, complete JCS+LF response, exit, and receipt for empty input,
   UTF-8, BOM, duplicate-key (including duplicate request IDs), JSON/framing,
   NFC, number, non-object root, generation, schema, pre- and post-extraction
   `ERR_LIMIT`, and pre- and post-extraction `ERR_INTERNAL`; they also cover a
   missing/malformed ID and a valid ID echoed on later errors. Response-size
   containment, semantic `INAPPLICABLE` exit 4, `ERR_INTERNAL` exit 3, and
   schema-negative swaps prove those branches cannot share an exit code;
9. direct-containment fixtures whose otherwise identical ordinary zero-receipt
   responses have `B` exactly 16,777,215, 16,777,216, and 16,777,217 bytes.
   The first two inline the complete pointer; the last uses
   `DIGESTED_RFC6901_SHA256_96`. Each pins final JCS+LF bytes and length,
   pointer digest and both lengths, exact fragments, request bindings,
   unchanged code/message/precedence/request ID/exit, and receipt. A separate
   schema-error fixture uses a top-level property name of exactly 8,388,608
   ASCII `/` characters: its selected canonical pointer is one leading `/`
   plus 8,388,608 `~1` escapes, exactly 16,777,217 scalars and UTF-8 bytes.
   Selection occurs on that complete pointer before containment; the response
   uses the bounded object without truncation or parent substitution.
   Schema-negative mutations swap branches, add an object member, change every
   digest/length/fragment/binding, and move the threshold by one;
10. effect-receipt recomputation using the 0.5 domain; and
11. legacy rejection plus separate frozen-path parity cases proving no accepted
   0.2/0.3 output byte changed.

Fixture pack, receipt, and manifest seals use their own declared 0.5 schema
rules. No digest or count in this proposal is a substitute for actually
generating and independently accepting those artifacts.

Compact-expander fixtures are separate obligations of the companion contract.
Section 5.4 pins successful expander-only stdout, empty stderr, exit 0, and zero
engine invocations. Section 5.7 pins the distinct error format and exits plus
the pre-candidate diagnostic-pointer budget, including exact 4095/4096/4097
boundaries. It MUST also pin the phase-local fail-closed law with byte-exact
mixed cases for (a) a common-schema candidate plus a target-schema candidate,
(b) a common-schema candidate plus a target location whose diagnostic pointer
would be 4097 scalars, and (c) a common-schema candidate plus selected-registry
corruption. In all three, the common/selector winner, request-ID choice, seal,
stdout, empty stderr, and exit are pinned; selected-entry verification and the
entire target phase are unreachable, so neither a target candidate,
target-phase `ERR_LIMIT`, nor registry `ERR_INTERNAL` may replace that winner.
None substitutes for these direct-core fixture cases.

## 8. Migration and regeneration obligations

Adoption is additive. New behavior lands only in new 0.5 files and directories.
The migration cannot edit a frozen contract, fixture, receipt, implementation
output, supplemental artifact, access packet, acceptance history, or pinned
example output.

Before any 0.5 generation can be called sealed, all of the following are
required:

- issue a closed 0.5 request schema, response schema, error registry, exact
  direct-error request-ID extraction algorithm, operation registry,
  envelope-binding algorithm, and receipt/effect-seal authority with new raw
  digests; the response schema assigns exit 4 only to semantic `INAPPLICABLE`
  and preserves exit 3 only for `ERR_INTERNAL`;
- reconcile this core with the separately proposed 0.5 semantic table and
  regenerate any composed decision-input schemas from that single adopted
  authority;
- issue and fixture-pin the companion
  `B1-COMPACT-EXPANDER-ERROR-0.5` schema independently of the direct core
  response schema; a compact expansion failure never fabricates a core
  response receipt;
- generate new semantic and wrapper fixture packs, all expected JCS+LF bytes,
  competency/mutation cases (including the combined reference-boundary and
  exit-code non-confusion cases in section 7), effect vectors, transcript
  records, and internal pack seals;
- regenerate wrapper request/response/transcript schemas and transcript
  evaluator expectations because the nested semantic request and response
  bytes, raw digests, normalized response digests, and receipts change;
- obtain new independently authored fixture-acceptance receipts that validate
  every new schema, count, raw digest, internal seal, and role-separation rule;
- build a new implementation tree without runtime dependencies, then generate
  a new implementation manifest, source-set/tree digests, build receipt,
  conformance evidence, and final seal receipt under 0.5 schemas;
- update the authority register and wire-format uniqueness gate so the 0.5
  request string is machine-checked as distinct while the 0.2/0.3 collision
  remains only the named grandfathered pair;
- preserve the existing full 0.2 and 0.3 conformance gates and add a separate
  0.5 gate; and
- run the complete validation gate plus byte-parity differential checks over
  every frozen semantic fixture entry and the seeded fuzz corpus before
  merging any implementation or performance path. A parity failure rejects
  the candidate.

Legacy manifests and receipts are not regenerated. A 0.5 manifest pins only
new 0.5 authorities while referring to frozen ancestors by their existing raw
digests where inheritance is intended.

## 9. Protected 0.2/0.3 invariants

| Protected surface | Frozen invariant | Treatment in this proposal |
|---|---|---|
| accepted files | Every byte, raw digest, self-zero seal, count, and receipt under the accepted 0.2 and composed 0.3 directories | Never edited or regenerated; 0.5 is additive |
| legacy request identity | Both accepted surfaces currently declare `B1-SEMANTIC-DECISION-REQUEST-0.2` | Collision remains recorded and grandfathered only for those two surfaces; 0.5 uses a distinct string |
| legacy response identity | `PCB-RUNNER-RESPONSE-0.2` and its exact closed branches | Unchanged on legacy paths; 0.5 uses a distinct schema/string |
| operation mapping | The composed 30 handles and their obligation mappings | E1-E3 core introduces no handle or remapping; any semantic proposal must version its changes separately |
| class law | Frozen generations use `MALFORMED_OR_BOUNDARY` before `BINDING_OR_CONFLICT` before `OMISSION_OR_INCOMPLETE`, else `VALID` | Unchanged on legacy paths; the proposed 0.5 `INAPPLICABLE` pre-table branch is separately semantic, while applicable requests preserve the frozen order |
| deterministic parse law | Strict canonical input, safe integers, one selected error, atomic JCS+LF output | Preserved; generation errors are new only in 0.5 |
| legacy envelope digests | Existing `inner_request_raw_sha256` and `inner_input_sha256` meanings and fixture bytes | Unchanged in legacy schemas; omitted, not repurposed, in 0.5 |
| legacy response references | Frozen responses contain their accepted `record_references` bytes, including empty arrays | Unchanged; derivation applies only to new 0.5 responses |
| legacy effect receipts | Existing emission scope, domains, preimages, and bytes | Unchanged on legacy paths; 0.5 has a new domain and new fixtures |
| classification authority | Decision input plus adopted predicate table; labels/provenance/inner free text are non-authoritative | Preserved; new trace/reference derivations cannot feed classification |
| engine/host boundary | Host owns truth, state, atomicity/replay, derivation, effects, and applicability calibration | Preserved; new seals do not transfer these duties to the engine |
| dependency/environment floor | No new runtime dependency; no clock, randomness, network, or ambient environment in engine decisions | Mandatory for 0.5 |
| claims boundary | Artifact conformance only; no efficacy, novelty, security, interoperability, or external-standard claim | Preserved |

## 10. Errata closure matrix and unresolved questions

The proposal is intentionally explicit about questions that must be answered
before adoption. The defaults below are normative only for this candidate;
changing one requires new proposed bytes and fixtures.

### E1 — wire-format collision

**Proposed closure.** A distinct request string, required exact response offer,
two generation-specific error codes, and no implicit downgrade make 0.5
unambiguous. Dedicated legacy dispatch remains out of band because accepted
0.2/0.3 bytes cannot identify which colliding generation was intended.

**Migration impact.** Hosts add an explicit 0.5 endpoint or launch mode and
clients construct/reseal a new request shape. All request/response/wrapper
schemas, fixtures, transcripts, receipts, and manifests are regenerated as
new 0.5 artifacts.

**Unresolved before adoption.** Should a later dispatcher define a
version-neutral error wire for unknown generations? Should future generations
continue exact single-format offers or replace the singular offer with a
bounded ordered list? What explicit deployment selector names the two frozen
legacy modes without pretending their bytes negotiate them?

### E2 — sealed responses do not bind decision input

**Proposed closure.** Every semantic response carries and receipt-seals the
direct decision-input digest, request-envelope seal, short-circuit predicate
map, minimal selected-class witness, derived references, and an explicit
reference-truncation flag.

**Migration impact.** Every 0.5 expected response byte and receipt changes;
wrapper normalized-response digests, transcripts, effect vectors, manifests,
and acceptance receipts are regenerated in new artifacts. Bare legacy
receipts remain insufficient evidence of what was decided, as stated in
`HOST_OBLIGATIONS.md` H5.

**Unresolved before adoption.** Should 0.5 additionally carry a digest of the
exact canonical request bytes including LF, as grounded 0.4's
`request_raw_sha256` does, despite the complete envelope seal and mandatory
canonical wire? Should record-reference authority move from the grounded
name-based heuristic to an explicit per-operation field registry? If the
adopted semantic proposal selects a tighten-only closure rather than a base
table row, does the witness need a separately sealed stable predicate id in
addition to the trace?

### E3 — envelope digests bind the inert half

**Proposed closure.** `decision_input_sha256` directly binds the only supplied
classification input. `request_envelope_sha256` then self-zero-binds that
digest, the complete input, all echoes, both generation declarations, and the
auxiliary inner request. The two misleading legacy field names are absent.

**Migration impact.** Clients compute two new preimages; validators pool their
mismatches with schema/echo findings; semantic fixtures add independent and
combined mutation cases. Frozen legacy digest behavior remains untouched.

**Unresolved before adoption.** Should the auxiliary `inner_request` be
removed entirely in a later major interface instead of retained and
whole-envelope-bound? Is excluding LF from the envelope seal preferable to a
separate exact-wire digest, or should both be carried? Do any host profiles
need a keyed authentication layer above these consistency seals? Such a layer
would be a separate host protocol and is outside this engine contract.

## 11. Non-claims and adoption gate

This proposal does not claim that the chosen extraction heuristic is complete
for every future fact vocabulary, that digest binding authenticates a caller,
that the classifier is effective for a host's records, or that any external
system conforms. It does not claim novelty, security, interoperability, or
compatibility beyond the explicit frozen-path behavior above.

The proposal becomes eligible for adoption only after the exact 0.5 contract,
schemas, fixtures, reference implementation, manifests, receipts, and
independent review all exist as new digest-pinned artifacts; the full
validation/parity gate is green; and no unresolved core/semantic contradiction
remains. Until then its status is exactly **PROPOSED / NOT ADOPTED**.
