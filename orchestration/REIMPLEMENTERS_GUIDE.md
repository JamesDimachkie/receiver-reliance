# Reimplementer's guide

This guide is for an outside implementer reproducing the composed 30-operation
receiver-reliance interface without reading the reference implementation. It
documents the traps that defeated four earlier attempts and the additional
traps found while authoring the in-house separated implementation.

## Start with the authorities, not the examples

Treat the public primary and supplemental contracts as the algorithm. The
schemas define the admitted wire objects, the operation registry binds handles
to obligations, the decision tables define the four behavior classes, and the
seal clauses define the bytes to hash. Fixtures are conformance evidence and
mutation material; their labels, entry IDs, expected responses, and provenance
are never classification inputs.

Verify authority custody before admitting parsed bytes. Authenticate the
supplemental contract against the raw SHA-256 supplied by its external
acceptance receipt, then derive the primary-contract, packet, and projection
pins from those authenticated contract bytes. The resolver explicitly
declares exact byte length plus raw SHA-256 for the packet and projection and
fails closed on a mismatch. The accepted-0.2 generation does the same for the
primary contract. The external receipt does not declare a supplemental-
contract byte length, so do not turn a locally observed length into an
authority pin. A path name or valid JSON parse is not custody.

A practical architecture has five independent layers:

1. strict raw JSON scanning and RFC 8785 canonical-byte verification;
2. schema validation plus envelope and digest binding;
3. a generic interpreter for the frozen predicate language;
4. deterministic core/wrapper response construction and self-zero seals;
5. transcript, fixture-relation, and raw-ABI tests.

Keep those layers separate. Most subtle failures are precedence leaks between
them.

## The four historical traps

### 1. RFC 8785 member ordering is UTF-16 code-unit ordering

Python's ordinary Unicode string order is not RFC 8785 member order for every
astral/BMP pair. Sort member names by unsigned UTF-16 code units. The RI1 pair
uses U+10000 and U+E000: the astral key is first canonically even though normal
code-point order says otherwise. This rule applies recursively to every object
and therefore to every sealed preimage.

### 2. Escaped lone surrogates are invalid JSON for this profile

Do not let a permissive decoder materialize `\ud800` or `\udfff` as Python
strings. Reject lone high or low surrogates in scalar values and member names.
Accept only a correctly paired high-surrogate/low-surrogate escape and combine
it to the corresponding scalar. Lone-surrogate inputs resolve to the frozen
`ERR_JSON` raw response.

### 3. A complete duplicate name wins before later framing errors

Duplicate recognition happens when the second complete member name is known,
not after its colon, value, object terminator, or final LF arrives. Thus both a
well-framed duplicate and the truncated `{"":0,""` select
`ERR_DUPLICATE_KEY`, ahead of `ERR_JSON`. A decoder that reports only after a
complete parse will get the missing-LF/truncation precedence wrong.

### 4. Duplicate-key errors use the frozen empty pointer

The raw ABI pins duplicate errors to `pointer:""`, including ordinary
nonempty and nested duplicate keys. Do not emit the duplicate's RFC 6901
location. The ten-byte RI4 witness `{"a":0,"a"` is deletion-minimal and
must produce the same empty-pointer response as the other duplicate cases.

## Additional traps found in the new authoring pass

### Canonicality can preempt NFC

An escaped spelling of a decomposed string may already violate the exact JCS
input requirement. Verify that the parsed value re-serializes to the original
bytes before selecting `ERR_NFC`; otherwise a noncanonical escape can be
misreported as normalization failure. NFC still wins for a canonically encoded
decomposed scalar.

### Repair the request ID as soon as a complete object is parseable

Parse-layer errors after a complete request object is available can retain a
schema-valid outer `request_id`, even when the final LF is missing or canonical
member order is wrong. Early failures that cannot yield a valid ID use
`RUN_000000000000000000000000`. This affects the response seal, so getting only
the error code right is insufficient.

### Schema, binding, digest, and limit precedence is not one generic walk

Byte equality depends on the exact failed pointer. Important examples:

- an invalid inner-request envelope format selects
  `/inner_request/format_version` before stale envelope digests;
- a mutation inside `inner_request.input` selects `/inner_input_sha256`
  before the inner input's own schema detail;
- after the input digest agrees, an inner-request raw digest mismatch selects
  `/inner_request_raw_sha256`;
- outer/inner request-ID drift selects `/inner_request/request_id`, even when
  the outer ID is itself malformed;
- a misspelled top-level member is reported at that member's pointer;
- a schema-invalid non-object root reports the root pointer, not a fabricated
  `/format_version` pointer;
- excessive nesting in a value that is already schema-invalid can remain
  `ERR_SCHEMA`; do not automatically emit `ERR_LIMIT` merely because the raw
  scanner observed deep nesting.

Use explicit staged checks for these boundaries. A generic validator is useful
inside each stage but cannot choose the stage order for you.

### JSON Schema error selection is part of the wire behavior

The interface does not merely require rejection. It requires one exact error,
then one exact pointer selected in UTF-8 byte order within its precedence pool.
Account for `allOf`, `oneOf`, conditionals, content-addressed `$ref`s,
`additionalProperties`, required members, arrays, uniqueness, patterns, and
numeric limits. When a composed `oneOf` has no matching operation branch, the
root may be the correct schema pointer even if a more descriptive child
failure exists.

### Raw parsing and canonicalization must not consume the Python call stack

Fresh refuter attempt 1 found a totality failure at 498 unmatched array
openers: the recursive candidate CLI raised `RecursionError` and printed a
traceback while the frozen ABI returned sealed `ERR_JSON`. Use explicit stacks
for JSON container parsing, JCS serialization, and recursive string/NFC walks.
Test open, balanced, object, array, and mixed structures on both API and CLI
surfaces around the runtime recursion boundary. As a final containment layer,
turn unexpected runtime exceptions into the sealed internal-error tuple; never
allow stderr traceback output.

### Integer-only JCS still needs a number lexer

Do not rely on the host decoder to collapse `1`, `1.0`, `1e0`, and `-0` into a
common value. The profile accepts safe integers only. Invalid number grammar
is `ERR_JSON`; a syntactically valid float, negative zero, or out-of-range
integer is `ERR_NUMBER` at the UTF-8-smallest pointer.

Do not convert an unbounded digit string before classifying it. Python 3.12's
configurable maximum decimal-string conversion length can turn a valid but
unsafe integer into a host `ValueError`; a generic containment layer then
misreports it as `ERR_INTERNAL`. Compare sign, digit length, and lexicographic
magnitude against the safe-integer bound first. Do not use `float` or `Decimal`
for already-invalid fraction/exponent forms. Preserve framing precedence:
4301 digits with LF is `ERR_NUMBER`, while the same token without LF is
`ERR_JSON`.

### Size checks have their own precedence boundary

The raw ABI ceiling is 16,777,216 bytes. At exactly that size, earlier layers
still win: invalid UTF-8, BOM, a complete duplicate name, invalid number, or a
schema-invalid canonical scalar keeps its own result. At 16,777,217 bytes,
`ERR_LIMIT` wins before any of those contents are decoded or scanned. Cover
both sides with fixed-size constructions; testing only an ordinary oversized
blob does not establish precedence.

### Self-zero seals exclude the final LF

For response, attention-card, transcript, and other self-zero seals, set only
the named seal member to 64 zeroes, hash the exact JCS bytes, then store the
uppercase digest. The transport LF is never part of that seal preimage.
Inner-request raw SHA-256 is a separate contract rule and includes its stated
LF; inner-input SHA-256 hashes JCS bytes with no LF.

### Wrapper parity is stronger than equal classification

The B1 and B1-ATTENTION arms may differ only in the enumerated configuration,
card, seal, and transcript fields. Remove only `configuration` and
`attention_card` from the requests and compare the remaining bytes. Reordered
candidate pools, budget, pause state, clarification state, or semantic request
content are real parity failures even if both arms classify identically.

## Predicate interpreter notes

Resolve every predicate path against `decision_input`, never the inner packet
or fixture metadata. Compare set items by their JCS bytes. Implement all atomic
operators generically, including graph cycle detection, functional-by-key
checks, strict base64 decode/re-encode, sequence relations, and the supplemental
clarification/selection projections. Evaluate class predicates in the frozen
order: malformed, binding/conflict, omission/incomplete, then valid. Do not
infer valid by fixture suffix.

## Minimum regression order

Before broad generation, run:

1. RI1's astral/BMP ordering pair;
2. RI2's scalar and key lone-surrogate inputs;
3. RI3's truncated and well-framed empty-key duplicates;
4. RI4's nonempty duplicate witness;
5. all semantic fixture entries through both API and CLI;
6. every materializable competence mutation;
7. all wrapper arms, transcript bindings, parity relations, and negative rows.

The supplemental pack contains seven descriptor-only competence rows. Do not
claim those as executed candidate inputs unless you independently materialize
the missing requests. Keep them visible in the denominator.

The wrapper packs also contain exactly 12 metamorphic records: four primary and
eight supplemental. Traverse those records themselves; do not substitute the
ordinary 124 pair-projection checks and call them metamorphic coverage. Bind
each record to its base pair, competence-case digest, and rule, validate the
declared response/class/seal relation, execute every materializable semantic
request and both wrapper arms, and report the seven descriptor-only relations
separately from the five candidate-executed relations.

## Coverage-guided differential campaign

Only launch the house-scale campaign after the local gate passes and a fresh-
context refuter completes a zero-divergence pass. Use a fixed seed and identity
mapping, execute the reference solely as a black box, and compare exit code,
stdout bytes, and stderr bytes. `sys.monitoring` branch events may steer corpus
retention without exposing source. Record opaque unique branch edges, branch
events, code-object count, edge-set digest, coverage-increasing identities,
case-stream digest, and unique raw-input count.

Install monitoring on private callables as well as public ones. Requiring only
one dispatch function is vacuous: an `_execute`-only falsifier can still record
a few edges and appear to pass. Define a fixed meaningful set spanning raw
parse, schema evaluation, classification, dispatch, predicate evaluation, and
atomic evaluation. Require every member to be both monitorable and observed,
report the two missing sets separately, and fail if either is nonempty. The
current frozen-target set is `_parse`, `schema_errors`, `classify`, `_execute`,
`_dispatch`, `eval_predicate`, and `_eval_atomic`.

Record a falsifier that supplies only `_execute` as both monitored and
observed. The gate must reject it and expose both missing sets. A required-name
constant without that regression can silently become vacuous during later
refactoring.

Do not invent a percentage. Without reading or disassembling the reference,
there is no honest total reachable-edge denominator. State the measured edge
count and that limitation. A final receipt is qualifying only if it executes at
least 50,000 identities with zero divergence; stopping at the first finding is
a failed preflight, not a campaign pass.

Run every Python gate with `-B` and an existing unique empty
`-X pycache_prefix` outside the repository. Child CLI probes need a different
temporary prefix per process and must fail if the prefix gains an artifact.
This is source-hygiene evidence, not semantic conformance evidence.

## Law surfaces pinned by the decisive round (RI5, 2026-08-13)

Attempt 4 repaired the pooled selection rule and still fell to five
independent mechanisms (592 executed divergences; report
`orchestration/refuters/RI5.md`, witnesses `orchestration/refuters/RI5-witnesses/`).
Pinning the selection rule is not enough: pool membership and the row the
pool is judged against carry equal authority.

- **Binding presence is all-or-nothing.** The reference's binding stage
  dereferences `inner_request` unconditionally; a missing member aborts the
  entire binding pool, which also disables combinator-site suppression
  (suppression requires a non-empty binding pool). A per-check presence gate
  that keeps partial binding errors alive diverges (DIV-001, 223-byte
  minimal witness).
- **The canonical registry row is scored over five bound echo fields** —
  `/operation_handle`, `/obligation_id`, `/decision_input/operation_handle`,
  `/decision_input/obligation_id`, `/inner_request/operation_handle` — so
  obligation evidence can select the row. A row is always returned: on a
  total tie, the first registry row in UTF-8 order. A well-formed handle
  absent from the registry must not collapse the binding pool (DIV-002; 239
  divergences on fully digest-consistent, structurally complete requests).
- **Non-finite JSON constants classify as `ERR_NUMBER`**, not generic
  invalid JSON: `NaN\n` alone is a four-byte witness (DIV-003).
- **Canonical-form `ERR_JSON` precedes `ERR_NUMBER`** when one input
  violates both laws (unsorted members or escaped keys carrying an
  out-of-domain number). Do not let a number-domain check preempt the
  canonical-form check (DIV-004).
- **Duplicate-member detection must handle lone-surrogate escapes** in
  member names; consult the committed witness for the exact bytes (DIV-005).

The candidate CLI's wrapper-format rejection was adjudicated as scope, not
divergence: wrapper semantics live at the candidate's API surface and the
cross gate exercises them there. State such scope boundaries explicitly and
early — a refuter must be able to resolve them from committed documents.

## Claims discipline

Passing the public fixture surface proves conformance on those executed bytes.
It does not prove efficacy, security, external-standard interoperability, or
fuzzing completeness. An in-house author-separated implementation does not
satisfy the invitation for a genuinely independent outside implementation;
that invitation remains open.
