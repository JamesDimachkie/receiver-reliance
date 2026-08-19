# Machine-checked coherence of the sealed decision law

The conformance suites in `baseline-run/` establish one thing: the shipped
implementations match the frozen contract. They cannot establish that the
**contract itself is coherent** — that every row is reachable, that
classification is total and terminating, that error selection is a well-founded
total order, and that the 0.4 closure layer can only tighten. This lane checks
that, against the sealed contract bytes rather than against any implementation's
behaviour.

Two documents carry the detail: [PROOF_REPORT.md](PROOF_REPORT.md) is the
per-property epistemic breakdown, and [model/ASSUMPTIONS.md](model/ASSUMPTIONS.md)
states every modelling assumption the results rest on. Read
[TRUST_MODEL.md](../TRUST_MODEL.md) first for what any evidence in this
repository may be read as claiming; this lane adds no guarantee to that page.

## Run

From the repository root:

```bash
python -B law/verify_law.py --structural-only     # seconds, stdlib only
python -B law/verify_law.py --json law/findings.json
python -B law/summarize.py law/findings.json
```

The full run recorded here, on CPython 3.12.10 / Windows AMD64:

```text
verify-law: obligations=30 properties=872 proven=766 bounded=105 refuted=1 errors=0
```

509.68 s, 40,907,363 predicate evaluations, 3,960 calls through the sealed
`decide_audited` pipeline. The full run needs `jsonschema` (4.26.0 used here);
nothing else in this repository does, which is why it is not a matrix row.
`--structural-only` needs no third-party package and is:

```text
verify-law-structural: checks=26 failures=0
```

`law/findings.json` is generated, not committed — the same treatment
`proof/` gives its derived corpora. `RR_REPO_ROOT` overrides the checkout the
model reads; with it unset the lane walks up from its own file.

## The three status words, and what separates them

Every result carries exactly one:

- **PROVEN** — established over the **full schema domain**. Positive results are
  witnesses: a fact profile that validates against the sealed
  `decision_input_schema` branch under `jsonschema` and evaluates true in **two
  independent shipped engines** (`baseline-run/implementation-output-0.2/b1_capabilities.py`
  and `second-implementation/rr2.py`). Structural results are arguments whose
  every premise was machine-checked from the sealed bytes.
- **PROVEN-BOUNDED** — established over a stated finite abstraction only. The
  bound is named in each case. Sampling, never exhaustion.
- **REFUTED** — the property does not hold, with a counterexample or a universal
  unsatisfiability certificate recorded.

`errors=0` means the **checker** ran clean. Findings are findings, not errors.

## What this proves

Over the full schema domain, for all 30 composed operations:

- **Totality and termination of classification.** The four-class precedence is
  duplicate-free and ends at `VALID`; every operation declares all four classes;
  every `VALID` row is exactly `NO_EARLIER_CLASS_MATCH`, which the frozen
  vocabulary defines as the negation of the three earlier rows. There is no
  fall-through to an undeclared default.
- **Error-selection determinism at the table level.** Ten codes, ten distinct
  integer precedences — a strict total order — and UTF-8 byte order totally
  orders distinct RFC 6901 pointers.
- **Closure monotonicity at the table level.** No closure row names `VALID` as
  its `tightens_to` target, so the closure layer cannot emit `VALID` for any
  input whatsoever.
- **Row and disjunct satisfiability wherever a witness exists** — 90 defect rows
  and 149 of 150 disjuncts, each carrying an executed witness.
- **Contract structure** — 20 invariants, including that the loaded 0.2 bytes
  match the digest the 0.3 supplement names as its inheritance base, that all 28
  inherited schema branches are unchanged under composition, and that no
  supplemental row redefines an accepted one.
- **Model fidelity** — the two shipped engines agreed on all 40,907,363
  evaluations (zero divergences), and this checker's precedence walk matched the
  class the sealed `decide_audited` pipeline seals in all 30 operations.

## What this does not prove

Stated plainly, because the distinction is the whole point of the lane:

- **It is not a proof of the system.** It covers the sealed decision tables and
  their schemas. The wire layer, the parser, effect receipts, transcripts and
  wrapper parity are outside it and are named as outside it
  (`model/ASSUMPTIONS.md` A8). The parse layer's own exhaustive treatment is a
  different lane (`portability/model/`), which excludes post-`PARSE_OK`
  semantics for the same reason this one excludes parsing.
- **Behavioural closure monotonicity is sampled, not universal** (`E4`, `E5`,
  and `C4.no-unclassified-input`). Generated profiles were pushed through the
  real `decide_audited`; none contradicted the table-level result. The universal
  version needs a proof about the composition function, not more samples.
- **Negative search results are not impossibility results.** Where no witness
  was found within the search budget — a handful of disjuncts on OBL-26, OBL-29
  and OBL-30 — the report says "no witness found", never "unreachable". The one
  exception is the E6 disjunct below, and it is an exception only because a
  universal certificate accompanies it.
- **It says nothing about efficacy, security, novelty, or fitness.** A coherent
  decision law is not a useful one. The repository's non-claims are unchanged.
- **It is not author-separated.** The model, the checker and this document come
  from the same program that produced the artifact. What is independently
  checkable is the run: the sources are digest-pinned, the search is
  deterministic, and both engines evaluate every predicate.

## The E6 rediscovery

`refuted=1` is the **expected steady state**. The checker independently flagged
**OBL-30 / `MALFORMED_OR_BOUNDARY`, disjunct #12** as unreachable and produced a
universal certificate for it:

> `NOT_FUNCTIONAL_BY` fires only when two items of `/facts/excluded_records`
> share `record_id` and differ on `exclusion_reason`. The sealed schema fixes
> `exclusion_reason` to the one-member domain `['INTENT_INCOMPATIBLE']`, so two
> items can never differ on it. Unsatisfiable for every schema-valid input, at
> any array length.

That is [ERRATA.md](../ERRATA.md) E6's third recorded non-closure, and
[ACCEPTANCE.md](../ACCEPTANCE.md)'s "Third recorded non-closure", reached
independently. It was found by search over 150 disjuncts, not by pattern-matching
the errata: 149 produced concrete witnesses, one did not, and the certificate
machinery then upgraded that single negative to a universal proof. The
certificate is `SINGLETON_VALUE_MEMBER` and is **PROVEN, not bounded**.

Both records agree on the conditionality, which is what makes the count
self-maintaining: extend the `exclusion_reason` enum in a future sealed revision
and the certificate stops applying, the disjunct becomes reachable, and
`refuted` drops to 0 on its own. Any *other* move off `refuted=1` is a new dead
row and should be read as one.

## Why the structural mode exists

The full run is thirteen minutes and one third-party dependency, so it cannot be
a matrix row — and a suite nothing runs is decoration. `--structural-only`
executes the two phases that need neither: the 20 contract-structure invariants,
pointer/literal separation, operator declaration, and the error-selection total
order. Every property it records is universal by construction rather than by
search, so its gate is stricter than the full run's — `refuted` is a defect
there, where in the full run `refuted=1` is the ledgered E6 disjunct. It runs as
`decision-law-structural` in `portability/matrix/plan.json`.

It is also the lane's cheapest useful role: a drift detector. It reads eleven
sealed files, pins each by SHA-256, and checks the 0.3 inheritance-base pin
against the 0.2 bytes it actually loaded. Change a sealed byte and the digests
move and the structural invariants fail loudly.

## Determinism

Demonstrated rather than asserted. All randomness is seeded from a SHA-256
digest of the query identity — deliberately not Python's `hash()`, which CPython
salts per process — all iteration is over sorted collections, and nothing reads
the clock, the network or the environment. The checker was run twice during
construction, the second time under `PYTHONHASHSEED=12345`, and the two records
were identical in every field except elapsed time. Finding that required fixing
a real defect: an earlier revision seeded from `hash()` and was not reproducible
across processes.

`verify_law.py` writes only where `--json` says. It runs no git command and
imports the shipped engines with `sys.dont_write_bytecode` set, so it leaves no
`.pyc` in the checkout.

## Layout

| Path | What it is |
|---|---|
| `verify_law.py` | The checker. Phases, the two run modes, and the final status lines. |
| `summarize.py` | Regenerates every table quoted in `PROOF_REPORT.md` from a `findings.json`, so no number in it is retyped. |
| `PROOF_REPORT.md` | Per-property results, the E6 headline, model fidelity, and the precise obstacles behind each NOT CHECKED. |
| `model/ASSUMPTIONS.md` | Every modelling assumption, numbered, with what it would take to discharge it. |
| `model/sources.py` | The only permitted reader of repository bytes. Eleven files, each hashed at load. |
| `model/law.py` | Loads the composed 30-operation law and the structural invariants from sealed bytes. |
| `model/domain.py` | The finite fact-profile abstraction per operation, and schema validation. The one module needing `jsonschema`. |
| `model/predicates.py` | The frozen predicate vocabulary as an inspectable tree. |
| `model/evaluators.py` | Both shipped engines behind one interface, compared on every evaluation. |
| `model/search.py` | Witness search. Positives are verified, never assumed. |
| `model/certificates.py` | Upgrades an empty search to a universal impossibility proof where the schema permits one. |
| `model/endtoend.py` | Drives the real sealed `decide_audited` pipeline for the behavioural arms. |
