# Formal verification of the Receiver-Reliance decision law

**What this is.** RR's conformance battery establishes *implementation matches
contract*. This checks something the battery cannot: whether the **contract
itself is coherent** — whether its rows are reachable, its classification total,
its precedence chain terminating, and its 0.4 closure layer tighten-only. Some of
those come out proven outright; others come out proven only over a stated finite
abstraction. Which is which is the point of the report.

**What it is not.** It is not a proof of the whole system. It covers the sealed
decision tables and their schemas. The wire layer, the parse layer, effect
receipts, transcripts and wrapper parity are out of scope and are named as such
in [model/ASSUMPTIONS.md](model/ASSUMPTIONS.md) A8.

Everything below is written to one rule: **PROVEN means over the full schema
domain. PROVEN-BOUNDED means over a stated finite abstraction. NOT CHECKED means
not checked.** Where a result is bounded, the bound is stated. Where a search
came up empty, the report says "no witness found", never "unreachable" — unless
a universal certificate accompanies it.

## 0. Run

```
verify-law: obligations=30 properties=872 proven=766 bounded=105 refuted=1 errors=0
```

Runtime **509.68 s** on one core. 40,907,363 predicate
evaluations (each executed by both shipped engines and compared),
3,960 calls through the sealed `decide_audited`
pipeline. `errors=0` means the **checker** ran clean; findings are reported as
findings, never as errors.

| property | PROVEN | PROVEN-BOUNDED | REFUTED | ERROR |
|---|---:|---:|---:|---:|
| `A1.row-satisfiable` | 90 | 0 | 0 | 0 |
| `A2.disjunct-satisfiable` | 149 | 0 | 1 | 0 |
| `A3.disjunct-class-reachable` | 145 | 4 | 0 | 0 |
| `A4.valid-reachable` | 30 | 0 | 0 | 0 |
| `A5.disjunct-sole-reason` | 142 | 7 | 0 | 0 |
| `B1.precedence-dependent-pair` | 87 | 0 | 0 | 0 |
| `B1.precedence-independent-pair` | 0 | 3 | 0 | 0 |
| `C1.precedence-total-order` | 1 | 0 | 0 | 0 |
| `C2.valid-is-declared-fallthrough` | 1 | 0 | 0 | 0 |
| `C3.operation-classification-total` | 30 | 0 | 0 | 0 |
| `C4.no-unclassified-input` | 0 | 30 | 0 | 0 |
| `D1.error-precedence-distinct` | 1 | 0 | 0 | 0 |
| `D2.error-codes-distinct` | 1 | 0 | 0 | 0 |
| `D3.error-precedence-is-total-order` | 1 | 0 | 0 | 0 |
| `D4.pointer-order-is-total` | 1 | 0 | 0 | 0 |
| `E1.no-closure-targets-VALID` | 1 | 0 | 0 | 0 |
| `E2.closure-outputs-are-defect-classes` | 0 | 1 | 0 | 0 |
| `E3.closure-row-reachable` | 3 | 0 | 0 | 0 |
| `E4.closure-layer-never-moves-a-defect-class` | 0 | 30 | 0 | 0 |
| `E5.closure-layer-never-yields-VALID-after-firing` | 0 | 30 | 0 | 0 |
| `S1.contract-structure` | 20 | 0 | 0 | 0 |
| `S2.pointer-literal-separation-exact` | 1 | 0 | 0 | 0 |
| `S3.operators-declared` | 1 | 0 | 0 | 0 |
| `S4.facts-schema-flat` | 30 | 0 | 0 | 0 |
| `X.evaluator-agreement` | 1 | 0 | 0 | 0 |
| `X2.model-matches-sealed-engine` | 30 | 0 | 0 | 0 |

**Search modes across A2/A3/A5** (450 searches): 262 `exhaustive` — the full
Cartesian product over the goal's support was enumerated; 116 `bounded` —
budget-limited local search; 70 decided structurally without a search
(single-disjunct rows under A5). Every negative result below came from a
`bounded` search, so none is an exhaustive-and-empty result being read as a
proof.

**Findings:** 87 `PRECEDENCE-DEPENDENT` (a census, not defects), 4
`SHADOWED-DISJUNCT`, 7 `NEVER-SOLE-REASON`, 1 `UNREACHABLE-ROW-DISJUNCT` (the
E6 result).

Residual negatives, all "no witness found within budget", none claimed as
unreachable:

- `A3` (disjunct does not yield its class in any input found):
  - `OBL-26/OMISSION_OR_INCOMPLETE#0`
  - `OBL-29/OMISSION_OR_INCOMPLETE#1`
  - `OBL-29/OMISSION_OR_INCOMPLETE#2`
  - `OBL-30/BINDING_OR_CONFLICT#0`
- `A5` (disjunct never found to be the sole reason for its class):
  - `OBL-26/OMISSION_OR_INCOMPLETE#0`
  - `OBL-29/BINDING_OR_CONFLICT#0`
  - `OBL-29/BINDING_OR_CONFLICT#1`
  - `OBL-29/BINDING_OR_CONFLICT#3`
  - `OBL-29/OMISSION_OR_INCOMPLETE#1`
  - `OBL-29/OMISSION_OR_INCOMPLETE#2`
  - `OBL-30/OMISSION_OR_INCOMPLETE#0`
- `A2` (satisfiable-but-no-witness, no certificate available):
  - (none)


---

## 1. The headline: ERRATA E6's unreachable disjunct, rediscovered

The task set a built-in validity check: RR already knows that one MALFORMED
disjunct of OBL-30 is unreachable. If this machinery could not see it, the model
would be wrong.

The checker was not told which disjunct, which operation, or which operator to
look at. It enumerates the 150 disjuncts of the 90 defect rows, searches each
for a witness, and offers a universal-unsatisfiability certificate only to those
that come up empty. It flagged exactly one:

**`OBL-30/MALFORMED_OR_BOUNDARY#12`**

```json
{
 "key": "record_id",
 "op": "NOT_FUNCTIONAL_BY",
 "path": "/facts/excluded_records",
 "value": "exclusion_reason"
}
```

Certificate `SINGLETON_VALUE_MEMBER`:

> NOT_FUNCTIONAL_BY fires only when two items of /facts/excluded_records share record_id and differ on exclusion_reason. The sealed schema fixes exclusion_reason to the 1-value domain ['INTENT_INCOMPATIBLE'], so two items can never differ on it. Unsatisfiable for every schema-valid input, at any array length.


Compare with the contract's own record ([ACCEPTANCE.md], third recorded
non-closure):

> one MALFORMED disjunct of OBL-30 (contradictory duplicate exclusion reasons,
> `NOT_FUNCTIONAL_BY` over `excluded_records`) unreachable for schema-valid
> inputs while the exclusion-reason enum has a single member

Same operation, same class, same operator, same field, same reason, and the same
conditionality — the certificate is explicitly a statement about the size of the
`exclusion_reason` domain, so it re-activates the moment that enum is extended,
exactly as the ledger says.

**Epistemic status: PROVEN.** Not bounded. The argument does not mention the
abstraction: `NOT_FUNCTIONAL_BY` fires only when two array items agree on
`record_id` and *differ* on `exclusion_reason`; the sealed schema fixes
`exclusion_reason` to a one-member enum; two items cannot differ on a one-member
domain. This holds at any array length, for every schema-valid input.

This result is also the model's own validation: 149 of 150 disjuncts produced
concrete witnesses, and the one that did not is the one RR had already found by
human review.

---

## 2. Results by property class

### (a) Row reachability

| property | claim |
|---|---|
| `A1.row-satisfiable` | every defect class row of every operation is satisfiable |
| `A2.disjunct-satisfiable` | every individual disjunct of every row is satisfiable |
| `A3.disjunct-class-reachable` | the disjunct actually *yields* its class under the frozen precedence |
| `A4.valid-reachable` | VALID is reachable for the operation (the law is not vacuously all-defect) |
| `A5.disjunct-sole-reason` | the disjunct can be the *only* reason its class fires |

A2 is the strict reading of "every class predicate row is satisfiable by some
schema-valid input", pushed down to disjunct granularity because that is where
E6 lives. A3 and A5 are strictly stronger and were added because a row that is
satisfiable but permanently shadowed is a different kind of dead code.

**PROVEN results here are witnesses**, not arguments: a concrete `facts` object,
validated against the sealed `decision_input_schema` branch by `jsonschema`
4.26.0, and evaluated to `true` by both shipped engines independently. Witnesses
are recorded in `findings.json` under each result's `witness_facts`.

**Bounded results here are search failures**, recorded with the search mode and
the number of assignments examined. Every one of them is `bounded` mode —
budget-limited local search — so none is an exhaustive-and-empty result being
quietly read as a proof.

### (b) Precedence dependence

Not a bug hunt: a census. For each ordered class pair `(higher, lower)` within an
operation, the checker looks for an input satisfying **both** rows. Such an input
is classified by the frozen order alone — reverse the chain and the answer
changes.

The result is that the frozen precedence is load-bearing almost everywhere. Only
a small number of pairs had no co-satisfying input, and for those the search was
*exhaustive over the abstraction*, so they are mutually exclusive as far as the
abstraction can see — precedence is decorative for those pairs and could be
reordered without changing any classification the abstraction contains.

That the dependent set is large is the correct and expected outcome: the contract
declares a total precedence precisely so overlapping evidence resolves
deterministically. The value of the census is that the surface is now enumerated
rather than assumed, and any future row edit can be diffed against it.

### (c) Totality and termination

The classification function is **total** and **terminating**, and the argument is
structural with every premise machine-checked from bytes:

| premise | check |
|---|---|
| `class_precedence` is a finite, duplicate-free list of 4 classes | `C1` |
| `NO_EARLIER_CLASS_MATCH` is defined as "true only when the three earlier predicates are false" | `C2` |
| every operation declares a predicate for all four classes | `C3` (30/30) |
| every operation's VALID row is exactly `{"op": "NO_EARLIER_CLASS_MATCH"}` | `C3` + `S1` (30/30) |

Given those: the chain visits four rows in a fixed order and stops at the first
match, so it terminates in at most four steps; and if the first three fail, the
fourth is true by its own frozen definition, so **every input receives exactly
one class and nothing falls through to an undeclared default**.

One observation worth recording. The shipped engines implement a *three*-element
precedence list with VALID as a structural fall-through, while the contract
declares a *four*-element chain whose last row is `NO_EARLIER_CLASS_MATCH`. These
are the same function — that is precisely what the operator's frozen definition
says — but they are not the same text, and `C2` is the check that keeps them
tied.

`C4` corroborates behaviourally: sampled inputs per operation, none unclassified,
and the observed classes are recorded per operation. `C4` is PROVEN-BOUNDED — it
is sampling, and the structural argument above is what carries the universal
claim.

**A separate totality caveat, at a different layer.** The *audited* surface
(`rr_api.decide_audited`) can emit states outside the frozen four-class
vocabulary — `AUDIT_INCOMPLETE` when a closure evaluator errors on an otherwise
VALID input, and `PROTOCOL_ERROR` for a malformed request. These are declared and
they are not classifications of a schema-valid decision input, so they do not
violate (c). They are reported here because "exactly one of four classes" is true
of the decision law and not of the audited envelope, and the difference is worth
being explicit about.

### (d) Error-selection determinism

The one-error law selects by precedence, then by lexicographically-first RFC 6901
pointer.

| check | status | argument |
|---|---|---|
| `D1` error precedences are distinct | PROVEN | 10 codes, 10 distinct integers |
| `D2` error codes are distinct | PROVEN | 10 distinct codes |
| `D3` precedence is a strict total order | PROVEN | distinct integers are totally ordered, so the winning code is unique for any non-empty detection set |
| `D4` pointer order is a strict total order | PROVEN | UTF-8 byte order totally orders distinct strings, so the minimum is unique |

**NOT CHECKED, stated precisely:** that a single error code never yields two
detections at the *same* pointer. If it did, "lexicographically-first pointer"
would not disambiguate them. That is a property of the scanner implementation
(`scan_parse_profile`), not of the sealed tables, and it is the half of E6's
pointer-cap item that lives outside the decision law. Checking it needs a model
of the parse layer, which this deliverable does not build.

So (d) is proven **as a property of the sealed tables**: the selection rule is a
well-founded total order at both levels. It is not proven that the runtime
detection set always has a unique minimum.

### (e) Closure monotonicity

Five independent arms, deliberately layered:

| arm | status | what it establishes |
|---|---|---|
| `E1.no-closure-targets-VALID` | **PROVEN** | the closure table's only output classes are its `tightens_to` values; none is VALID, so the closure layer *cannot emit VALID at all* |
| `E2.closure-outputs-are-defect-classes` | PROVEN-BOUNDED | behavioural mirror of E1 over sampled inputs, with a count of how often the sealed rule's "only when VALID" guard is what stops a fired closure from touching a defect class |
| `E3.closure-row-reachable` | PROVEN | every closure row fires on some input — none is dead |
| `E4.closure-layer-never-moves-a-defect-class` | PROVEN-BOUNDED | over sampled profiles run through the **sealed** `decide_audited` pipeline, no input where the frozen table gives a defect class comes out as anything else |
| `E5.closure-layer-never-yields-VALID-after-firing` | PROVEN-BOUNDED | no sampled input where a closure fired came out VALID |

E1 is the universal result and it is the strong one: it is a statement about the
closure *table as data*, so it holds for every input, including inputs no
sampling would reach. E4 and E5 are observations of the real shipped composition
— not a restatement of the rule — on generated fact profiles pushed through
`rr_api.decide_audited` with a sealed request envelope.

`E4`/`E5` are bounded because they are sampling. Making them universal would need
a proof about the composition *function* rather than its behaviour; that is
tractable (the function is four lines) and is named in the remaining work.

---

## 3. Model fidelity

Two checks exist purely to catch this checker being wrong about the law:

- **`X.evaluator-agreement`** — every predicate evaluation in the run is executed
  by both shipped engines (`b1_capabilities.eval_predicate` and
  `rr2.evaluate_predicate`) and compared. A single disagreement raises
  `EvaluatorDivergence` and aborts the run. Zero divergences.

- **`X2.model-matches-sealed-engine`** — for every end-to-end sample, this
  checker's own precedence walk is compared against the class the sealed
  `decide_audited` pipeline seals into `first_match_predicates`. All 30
  operations agree on every sample.

Together these say: the classification this report reasons about is the
classification the shipped system performs, in all 30 operations, on thousands of
generated inputs — not a paraphrase of it.

This is the refutation surface, in the spirit of `portability/model/`'s
independent refuter: the cheapest way for this checker to be wrong about the law
is for its operator semantics to drift from the shipped ones, and both of these
checks are armed to abort the run if that happens rather than to report a
comfortable result.

---

## 4. NOT CHECKED — the precise obstacles

| item | obstacle |
|---|---|
| Uniqueness of the winning pointer within one error code | needs a model of the parse/scan layer; the sealed tables do not constrain it |
| Wrapper transcript evaluator's missing semantic re-derivation (E6 item 2) | a property of the wrapper evaluator's step list, not of the decision tables |
| Effect-receipt construction, transcripts, wrapper parity | sealed, but not part of the classification law |
| Universal (rather than sampled) closure monotonicity | needs a proof about the composition function in `rr_api.decide_audited`, not about its behaviour |
| Residual A3/A5 negatives | budget-limited local search on the three largest operations; see the residual list in the results section |
| Row satisfiability over the *full* string/integer/array domains | the abstraction is finite by construction (ASSUMPTIONS A6); positives are exact, negatives are bounded unless certified |

The last row is the honest core of the whole exercise. **Every positive result in
this report is exact** — a witness that validates against the sealed schema and
evaluates true in two independent engines. **Every negative result is bounded**,
except the one carrying a universal certificate.

---

## 5. Reproduction

From the repository root:

```
python -B law/verify_law.py --json law/findings.json
python -B law/summarize.py law/findings.json
```

Runtime 509.68 s for the run recorded in this document, on CPython 3.12.10 /
Windows AMD64. Requires `jsonschema` (4.26.0 used here); `--structural-only`
does not, and that is the mode wired into
`portability/matrix/plan.json`. The checkout is found by walking up from the
lane's own file; point elsewhere with `RR_REPO_ROOT`. `law/findings.json` is
generated and untracked.

The run is deterministic, and this was checked rather than asserted. All
randomness is seeded from a SHA-256 digest of the query identity — deliberately
not Python's `hash()`, which CPython salts per process — all iteration is over
sorted collections, and nothing consults the clock, the network or the
environment.

**Determinism evidence.** The full checker was run twice, the second time under
`PYTHONHASHSEED=12345`, and the two `findings.json` records compared field by
field:

| field | identical |
|---|---|
| `counts` | yes |
| `results` (all 872) | yes |
| `findings` | yes |
| `sources` | yes |
| `domain_summary` | yes |
| `evaluations` | yes |
| `elapsed_seconds` | no — 775.99 s vs 760.06 s, the only difference |

An earlier revision of this checker seeded from `hash()` and was *not*
reproducible across processes; that defect was found by running this check and
is fixed.

The construction-time console logs are not committed. What replaces them as
standing evidence is that the run above is reproducible on demand: it was
re-executed against the released engine bytes when this lane landed in the
repository, and reproduced every count in section 0 exactly — 872 properties,
766 proven, 105 bounded, `refuted=1`, `errors=0`, 40,907,363 evaluations, the
same E6 certificate — at a different wall clock. The only source digest that
moved between the two runs is `grounded-0_4/rr_api.py`, which the 0.4.2 release
grew (ERRATA E8); the classification results did not move with it.

Most of the wall clock goes to the second, harder search attempt at goals that
came up empty on the first pass (`RETRY_EFFORT` in `verify_law.py`, and
`--e2e-samples` for the sealed-pipeline arm). Setting `RETRY_EFFORT = 1` cuts the
runtime substantially and changes only how many of the residual A3/A5 negatives
get converted; it changes no PROVEN result, because those are witnesses.

`verify_law.py` writes only where `--json` says. It never writes inside
`receiver-reliance/`, runs no git command, and imports the shipped engines with
`sys.dont_write_bytecode` set so no `.pyc` is produced in the checkout.

### Pinned sources

Every artifact is SHA-256 pinned at load and the digests are recorded in
`findings.json` under `sources`. The 0.2 contract digest is additionally checked
against the digest the 0.3 supplement names as its inheritance base, so the bytes
this model reasons about are tied into the sealed 0.2/0.3 chain rather than
merely read from a path.

| SHA-256 | bytes | path |
|---|---:|---|
| `C3414FC751C3B5ECA43A4932C694641D801A21F2CF53C42BE3A8C87C234CF499` | 35399 | `grounded-0_4/authority_register_0_4.json` |
| `79C0582FAB4A04DA3FCA90ECD7B5096457D67EBA4CA7E8D6A487C5D3E2CDECD3` | 28523 | `grounded-0_4/rr_api.py` |
| `EBA198726DE960E9F59ACE5A7E1BDB701BFBA5B1BD09BC59FF4540F2B14E8F9C` | 2329 | `grounded-0_4/closures_0_4.json` |
| `DCFCB0714E1A7E677548057987F604D227F791F3FC3E0EA89BE5ED932447F48E` | 321451 | `baseline-run/control/B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json` |
| `6B2CAD02DDE7388D63D66E4863E5233CFBD1DC413575D9D260DB9799C7023A12` | 159277 | `supplemental-0_3/control/B1_SUPPLEMENTAL_COMPARATOR_CONTRACT_0_3.json` |
| `B00EA68B3902128FBA0EE622B3020EA68A2928C57FC2BD27087E8806D41A14FE` | 48843 | `baseline-run/implementation-output-0.2/b1_capabilities.py` |
| `4AA2AFCECEAA62AF10281444A92D73A141785F53BC48D267F5BE6976C13CCD7B` | 82500 | `second-implementation/rr2.py` |
| `F27B93B3BE8BCBF5FBF7FF7789494621D17B426E16B38E958BB932899B0961B9` | 1360792 | `baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json` |
| `0A211174261C31924979A348B13EC43678896183ADB99D86002A51238C0AAE73` | 178296 | `supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json` |
| `266AB130F85206E0FA47978A1E57E5D16DF7EACD051084435C15B1840512D38E` | 37157 | `baseline-run/control/B1_CAPABILITY_MATRIX_0_1.json` |
| `B369777E51B2A64DC2C304C5949F38E13956353B496BABA8B6E488451F8C5B98` | 25976 | `supplemental-0_3/control/B1_COMPOSED_CAPABILITY_MATRIX_0_3.json` |
