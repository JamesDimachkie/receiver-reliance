# Modelling assumptions

Every claim `verify_law.py` makes rests on the assumptions below. They are
listed so a reader can attack them directly. Where an assumption is checkable,
the checker checks it and the check is named; where it is not, it is marked
**UNCHECKED** and its blast radius is stated.

The load-bearing distinction throughout: **positive results are witnesses**
(concrete inputs, re-validated against the sealed schema and re-evaluated by two
independent shipped engines), so they cannot be wrong in the direction that
matters. **Negative results are only as strong as the abstraction**, unless a
universal certificate accompanies them.

---

## A1 — The operator vocabulary is defined by the shipped engines, not by me

The frozen predicate language specifies 38 atomic operators in prose
(`predicate_language.atomic_operators`). This model does not re-implement them.
It imports two independent shipped implementations —
`baseline-run/implementation-output-0.2/b1_capabilities.py` (`eval_predicate`)
and `second-implementation/rr2.py` (`evaluate_predicate`) — and uses them as the
executable definition.

*Why:* hand-writing 38 operators from prose would put my reading of the contract
between the sealed rows and every result. That is the classic way a formal
verification effort proves something about a model nobody has any reason to
believe.

*What it costs:* the results are statements about the law **as the shipped
engines evaluate it**. If both engines diverged from the contract prose in the
same way, this checker would inherit that divergence.

*What contains the cost:*
- the two engines are genuinely independent — `second-implementation/rr2.py`
  imports no part of `b1_capabilities`, only the standard library, and its
  `PROVENANCE.md` records that it was authored from the contract, control
  documents, schemas and fixture packs rather than from either frozen
  implementation's source. So the differential is a real second opinion, not a
  wrapper around the first;
- **every** evaluation in the run is put through both and compared — a
  disagreement raises `EvaluatorDivergence` and aborts the run (property
  `X.evaluator-agreement`);
- the conformance battery already binds both engines to 124 sealed fixtures
  with expected outputs authored by a separate role;
- property `X2.model-matches-sealed-engine` compares this checker's own
  precedence walk against `rr_api.decide_audited`'s sealed
  `first_match_predicates` on every end-to-end sample, in all 30 operations.

**UNCHECKED residual:** a common-mode error shared by both engines *and* the
sealed fixtures. Nothing here would see it.

## A2 — The sealed rows and schemas are read, never transcribed

Class predicates, class precedence, the per-operation `facts` schemas, the
operation registry, the error registry and the closure table are all loaded from
repository bytes, and every file is SHA-256 pinned at load and recorded in the
output (`model/sources.py`). No predicate appears in this codebase's source.

Checked by: `S1.contract-structure` (20 invariants, including that the 0.2
contract bytes this model loaded match the digest the 0.3 supplement pins as its
inheritance base, and that all 28 inherited schema branches are unchanged in the
0.3 composition).

## A3 — Pointer/literal separation is structural

The predicate language does not tag which JSON members are RFC 6901 pointers.
This model uses the rule *a string beginning with `/` is a pointer; anything
else is a literal*, plus the two members that name a field inside an array item
(`key`, and `value` under `NOT_FUNCTIONAL_BY`).

Rather than assume this is exact, `S2.pointer-literal-separation-exact` checks
it over all 90 defect rows: it reports any literal that begins with `/` and any
pointer that does not begin with `/facts/`. The run finds zero of both, and
every pointer in the sealed law is exactly `/facts/<field>` — depth two, never
deeper. So *support* (the set of fields a predicate reads) is computed exactly,
not approximately.

## A4 — Fields are independent, so "vary the support, default the rest" is complete

Predicate evaluation is a pure function of the paths it resolves. Combined with
`S4.facts-schema-flat` — every `facts` schema is a flat object whose only
keywords are `type`, `additionalProperties`, `required` and `properties`, with
no `allOf` / `if` / `dependentRequired` / cross-field constraint — this gives
two things:

1. varying only the fields a goal reads, while holding the others at a
   schema-valid default, loses no witnesses;
2. a document assembled from per-field-valid candidates is itself schema-valid,
   so the inner search loop may skip per-candidate validation.

Every **accepted** witness is still validated in full against the sealed
`decision_input_schema` branch with `jsonschema` 4.26.0 (`verify_witness`).

## A5 — Request envelopes come from the sealed fixture packs, facts do not

The end-to-end arm (`E4`, `E5`, `X2`) calls `rr_api.decide_audited`, which needs
a complete request envelope: an inner packet request plus two digests over it.
Those parts are irrelevant to the decision law but must be well formed, so one
envelope per obligation is lifted from the `-IO-` entries of the sealed fixture
packs and its `decision_input.facts` is replaced with generated facts. The
envelope digests bind the inner packet request, which is never touched, so the
substitution keeps the request valid.

Only `semantic_request_jcs_lf_base64` is read. No `expected_response`, no
`first_match_predicates` and no recorded class from a fixture entry is ever read
as an input to a result — the fixture packs are used as a source of envelopes,
never as an oracle.

## A6 — The finite abstraction, and exactly what "bounded" means

Unbounded fields (strings up to 160–1048576 chars, integers over the safe range,
arrays up to 256 items) are replaced by a small candidate list per field, built
mechanically from:

- the field's own schema (all members of an `enum`, both values of a `boolean`,
  `null` where nullable);
- every literal the operation's own sealed rows mention, filtered by the field
  schema;
- a shared per-operation atom pool (`a0`, `a1`, `a2`) so cross-field relations
  (`MEMBER`, `INTERSECTS`, `NOT_SUBSET`, self-loops, duplicate keys) are inside
  the abstraction, with the *same* first atom reused as every plain string
  field's default so coincidences are reachable;
- format archetypes — two SHA-256-shaped hex strings, canonical base64,
  non-canonical-padding base64, malformed base64 — each admitted only if the
  field's own schema validates it;
- array templates: empty, singleton, duplicate-pair, distinct-pair, reversed
  pair, triple; every ordered pair over an object pool built as "a base item
  plus one single-member variant per member", which is exactly the shape the
  relational operators need; arrays of every literal list a row mentions, and
  that list minus its head; and length-matching templates (including
  strictly-increasing and strictly-decreasing integer runs) at every length some
  row's literal list makes significant;
- derived digests: for each sealed `BASE64_SHA256_NE` pair, the true
  `SHA256_UPPER` of each base64 candidate is added to the digest field, since no
  independent enumeration would ever guess an agreeing pair.

Two search modes follow from this:

- **exhaustive** — the full Cartesian product over the goal's support fits in
  400 000 combinations and is enumerated completely. A negative result is
  genuine non-existence *over the abstraction*.
- **bounded** — the product is too large, so a deterministic seeded
  min-conflicts local search runs (20 restarts x 700 steps, with 3x the restart
  count on a second attempt at a goal that came up empty). A negative result
  means **only** "not found within budget".

Neither mode makes a negative a universal claim. That upgrade requires A7.

**UNCHECKED residual:** a row satisfiable only by a value shape absent from the
abstraction — a specific Unicode form, a 200-item array, an integer near the
safe-range boundary — would be reported as "no witness found", never as
unreachable. The certificate machinery (A7) is what keeps that failure mode from
being mistaken for a proof.

## A7 — Universal unsatisfiability requires a certificate, never a failed search

A search that finds nothing is reported as `PROVEN-BOUNDED` plus a
`NO-WITNESS-IN-ABSTRACTION` finding. It is only reported as `REFUTED` — that is,
as an unreachable row — when `model/certificates.py` produces an argument that
does not mention the abstraction at all. The certificate library covers
singleton-domain members under `NOT_FUNCTIONAL_BY`, `ABSENT` on a non-nullable
field, simultaneous `PRESENT`/`ABSENT`, `EQ` against a value outside a finite
domain, and contradictory equality pins.

Certificates are only ever *offered* to disjuncts a search already failed, so
adding one can turn "bounded" into "proven" but can never make a satisfiable row
look unsatisfiable.

## A8 — What is deliberately out of scope

- **Wire and parse layer.** The one-error law is checked as a property of the
  sealed *tables* (distinct precedences, total pointer order). Whether a single
  error code can produce two detections at the same pointer is a property of the
  scanner implementation, not of the tables, and is not checked. This is the
  half of ERRATA E6's pointer-cap item that lives outside the decision law.
- **Effect receipts, transcripts, wrapper parity.** Sealed but not part of the
  classification law.
- **The wrapper transcript evaluator's missing semantic re-derivation** (the
  second E6 non-closure) is a property of the wrapper evaluator's step list, not
  of the decision tables, and is not modelled.
- **The audited surface's out-of-band states** (`AUDIT_INCOMPLETE`,
  `PROTOCOL_ERROR`) are observed and reported where they occur, but their
  correctness is not a claim of this checker.
