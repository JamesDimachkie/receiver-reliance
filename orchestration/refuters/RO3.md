# R-O3 refutation — single-pass audited classification

## Verdict

**PASS — NO DEFECT FOUND.** O3 preserves the legacy audited object and JCS
bytes over every executable request-bearing fixture family, 11,000 additional
deterministic semantic cases, all frozen executable predicate operators,
closure tightening, both core and wrapper output shapes, forged sealed-class
divergence, and contended concurrent replay. The selected defect predicate is
evaluated once instead of twice while its witness, precedence map, and
short-circuit order remain unchanged. `VALID` continues to carry an empty
witness.

No candidate file was modified. The reviewed candidate is cherry-pick
`787f64fe09a47f716794529e008d0b62faf1f651` of O3
`d82f492cfcda56c6d8d47d26e41d535d01be273d`, based exactly on integration
`1123cdd2b9a4d87b2eaaf9169972d0e88a405cd9`.

## Exact parity evidence

### Candidate gate

`python -B grounded-0_4/test_single_pass_audit.py` exited zero:

```text
single-pass work reduction: reduced_fixtures=93/124 atomic_calls_saved=116
single-pass audit equivalence: checks=1142 failures=0 fixtures=124 fuzz=256 reference_seed=0x5EED0A03 reference_cases=128
```

This checks all 124 accepted semantic fixture requests as both raw bytes and
objects, 256 deterministic grammar/byte cases, 128 exact-reference/decoy
objects, 64 valid generated OBL-02 references, basic threaded replay, and two
forged-class directions. The committed test is useful but its 256 generated
cases are mostly protocol-path probes, not the requested large semantic
differential; the independent sweeps below supply that missing falsification.

### All executable request-bearing fixture families

I materialized the pinned competence and metamorphic mutations with the
accepted conformance harness, decoded both wrapper arms, and included every
negative fixture that actually reaches the runner plus the 57 raw error-law
cases. For each input I compared the pre-O3 `classify`-then-`_trace` audited
oracle with O3 `decide_audited`, including exception type/message or final JCS
object bytes:

| Family | Compared |
|---|---:|
| accepted semantic requests | 124 |
| materialized competence requests | 423 |
| wrapper arms | 248 |
| executable wrapper negatives | 12 |
| materialized wrapper metamorphic arms | 24 |
| raw error-law inputs | 57 |
| **Total** | **888** |

Result: `888/888` exact, zero divergence. Ordered corpus SHA-256:
`E1884AFEB24C123D9189F1C3DD4910637FCFB3561808415F236F62959BBEB86D`.
The remaining negative fixtures test pair cardinality, arm-parity metadata, or
recorded transcript binding rather than a `decide_audited` request; the full
conformance gate below covers them in their owning evaluators.

### 11,000 generated semantic cases

The independent corpus exhaustively crossed each fact field over every
accepted same-operation fixture value, then added deterministic one-scalar
near-valid mutations until the bound was reached:

| Partition | Cases | Runner accepted | Protocol error |
|---|---:|---:|---:|
| accepted-value cross-products | 7,420 | 7,420 | 0 |
| one-scalar near-valid mutations | 3,580 | 2,121 | 1,459 |
| **Total** | **11,000** | **9,541** | **1,459** |

Every final audited object and JCS byte string matched the legacy oracle.
Ordered corpus SHA-256:
`852FE34F97B856FBC5BB80A08CE49EA683CA0EA80F7BAF87CE5F822C79472BDF`.
The 9,541 accepted sealed classes were 7,696
`MALFORMED_OR_BOUNDARY`, 808 `BINDING_OR_CONFLICT`, 529
`OMISSION_OR_INCOMPLETE`, and 508 `VALID`. Audited classes were respectively
7,696, 811, 529, and 505: three frozen-`VALID` cases were correctly tightened
by OBL-30 closures, byte-identically to the legacy path. The grounded gate also
retained the explicit inverted-verdict and stale-selection closure
regressions.

Instrumentation observed every one of the 38 executable frozen atomic
operators. The table's 39th operator name, `NO_EARLIER_CLASS_MATCH`, is the
declarative `VALID` sentinel and is intentionally not passed to
`_eval_atomic`. The frozen tables contain 25 `any`, 27 `all`, and 8 `not`
nodes.

### Nested witness, precedence, and short-circuit probes

Four synthetic tables selected each defect class once and `VALID` once. The
selected predicate nested `all(any(all(...), all(any(..., all(not(...))))))`
and placed never-total atoms after false `all` branches and the first true
`any` branch. O3 matched legacy class, fired map, and witness in all four
cases. The defect witness contained only the selected gate, first-true branch,
deep true atom, and `not` marker; discarded/late branches never appeared.
`VALID` returned three false fired-map entries and an empty witness.

Atomic-call order was exactly the legacy classification order with only the
second selected-predicate evaluation removed:

| Selected class | Legacy atoms | O3 atoms |
|---|---:|---:|
| `MALFORMED_OR_BOUNDARY` | 12 | 6 |
| `BINDING_OR_CONFLICT` | 13 | 7 |
| `OMISSION_OR_INCOMPLETE` | 14 | 8 |
| `VALID` | 3 | 3 |

This also confirms the intended qualification on “single pass”: the frozen
engine still classifies to produce the sealed response and the audit still
reclassifies defensively. O3 removes the audit path's separate re-evaluation
of the selected predicate; it does not reduce the whole public request to one
total classification.

### Forgery, references, errors, and concurrency

- Eight real examples covered all four sealed classes in both core
  `result_object` and wrapper `payload` shapes. Replacing each class with every
  other class plus `None`, `"UNKNOWN"`, empty string, `0`, `false`, and `{}`
  produced 80 scenarios: all 72 divergences raised the exact legacy
  `RuntimeError("trace classification diverged from sealed response")`; the 8
  unchanged controls remained byte-identical.
- Exact-reference behavior passed 128 shuffled decoy objects and 64 generated
  valid OBL-02 requests. `not_exact_reference_backup`,
  `untrusted_exact_reference_note`, and `exact_reference_suffix` remained
  excluded while exact `exact_reference` and record-ID keys remained present.
  The 6,497-check adversarial audit gate independently retained the F1
  exact-key regressions.
- Error parity covered the 1,459 generated protocol errors, 57 raw error-law
  inputs, 12 executable wrapper negatives, and the full frozen error gates.
- A 12-thread, 4,096-task deterministic mix of semantic and both wrapper-arm
  requests had zero legacy/O3 differences. A sequential replay matched every
  threaded O3 byte string. Ordered output SHA-256:
  `8F23A75E065390DEF5568BF3F255E56273C7ECC13CF14B930CF3C64C1430C649`.

## Work reduction and benchmark adjudication

An independent recount reproduced the candidate's exact 116-atom reduction:

| Selected class | Fixtures | Atoms removed |
|---|---:|---:|
| `MALFORMED_OR_BOUNDARY` | 31 | 38 |
| `BINDING_OR_CONFLICT` | 31 | 33 |
| `OMISSION_OR_INCOMPLETE` | 31 | 45 |
| `VALID` | 31 | 0 |
| **Total** | **124** | **116** |

The full fixture work count moved from 1,060 to 944 atomic calls, a
`116 / 1,060 = 10.9434%` reduction in that narrow counter. It is not a claim
of equivalent end-to-end speedup because parsing, schema validation, sealing,
and closure/reference work dominate the public call.

The candidate's 11 paired/interleaved timing samples were arithmetically
correct. Legacy median was `8.511698 ms`, O3 median was `8.486981 ms`, median
of paired ratios was `0.998143x`, and ratio of the two medians was
`0.997096x`. Individual paired ratios ranged from `0.953383x` to `1.009203x`;
O3 was lower in 6 samples and higher in 5. This contended run does not
establish a meaningful runtime win, and no such win is needed for admission.
It does refute any stronger performance reading of the atom-count reduction.

## Mutable-state and side-effect inspection

`b1._eval_atomic`, `_trace`, and the closure evaluators perform no external
effects; their mutations are confined to local collections. O3 introduces no
module-level write and its branch/witness lists are call-local. Ordinary
sequential and concurrent calls left the decision-table JCS SHA-256 unchanged
at `BC3204967A037D74293901F04CDED3162B00104EBE3B1ED201A0EB3ED2CFF894`.

The underlying `b1.decision_table()` is an `lru_cache` returning the same
mutable nested object on every call; a temporary sentinel mutation was visible
through a second reference and was then removed, restoring the exact hash.
This is a pre-existing implementation-internal residual, not an O3 mutation.
Similarly, a caller that monkeypatches private `_eval_atomic` or
`decision_table` observes fewer callbacks under O3 because eliminating that
second evaluation is the optimization itself. Exact parity therefore assumes
the frozen authority tables and private evaluator hooks are not concurrently
mutated by the host. The documented `decide`/`decide_audited` API exposes no
such mutation operation, and 12-thread read-only use was stable.

## Full expanded gate

All commands exited zero from the required directories:

```powershell
Push-Location baseline-run
python -B implementation-output-0.2/run_conformance_0_2.py
python -B implementation-output-0.3/run_conformance_0_3.py --suite all
Pop-Location
python -B grounded-0_4/test_grounded_0_4.py
python -B grounded-0_4/lint_contract.py --gate
python -B grounded-0_4/test_lint_gate.py
python -B grounded-0_4/test_properties.py
python -B grounded-0_4/test_audit_adversarial.py
python -B proof/test_proof_harness.py
python -B fuzz/fuzz.py --ci-smoke
python -B grounded-0_4/test_single_pass_audit.py
```

Observed results: frozen conformance `800 failures=0`; composed conformance
`800 + 107`, both zero; grounded `504/0`; lint `0 findings`; lint meta `7/0`;
properties `2,296/0` at seed `0x5EED8785`; audit adversarial `6,497/0`; proof
harness `7/7`; fuzz smoke `31/31` at seed `0x0B10F042`; O3 `1,142/0`.

## Residual uncertainty

- The deterministic semantic corpus is broad and reaches every executable
  operator, but it is not an exhaustive proof over the schema's full value
  space or every compound predicate path.
- Performance was measured under active label/timing contention and is
  observational only. The semantic admission rests on exact parity, not
  timing.
- Mutation of cached authority objects or private evaluator hooks is outside
  the public contract and remains capable of changing behavior, as it did
  before O3.
- The separately pinned CPython 3.12.4 subprocess toolchain is absent from this
  checkout, so sealed ABI mode was not rerun. The in-process gate used CPython
  3.12.10; O3 changes only the grounded Python API and test.

Stop condition reached: no defect was found after the bounded required
falsifiers and full gate. O3 is admissible on semantic parity; no candidate
patch was attempted in the refuter lane.

Authored-By: sol-ro3 (gpt-5.6-sol)
