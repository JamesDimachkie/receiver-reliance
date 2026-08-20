# Native-records usefulness proof

The external review's bar: *"Until an independent system can feed it native
records — not precomputed verdicts — and it beats a much smaller
schema-plus-policy validator on real handoff outcomes, the rational skeptical
position is: impressive conformance engineering, unproven research
importance."* This directory is that test, run against the operator's own
recorded multi-agent coordination system.

On the review's evidence ladder this is the **internal held-out benchmark**
tier ("interesting signal"), not the preregistered blinded tier: the corpus,
adapter, and referee were built by a treatment-exposed lane in one workspace.
It is exactly the infrastructure the blinded tier reuses.

## Protocol

- `extract_corpus.py` walks REAL recorded artifacts — hash-pinned research
  handoffs, structured task-claim JSON files, a version-superseded document
  chain, task lifecycle history from git — and emits `corpus.jsonl`
  (raw native claims + raw world observations; no verdicts) and
  `truth.jsonl` (mechanical ground truth, referee-only). Ten seeded
  perturbations of clean records give controlled positives; arms are blind
  to provenance. Shared observations carry raw facts only; every derived
  judgment (glob-scope reduction, version-testimony merge, supersession
  blame join) is decision work each arm does or fails to do itself.
- `arm_baseline.py` — the "much smaller" comparator: single-record
  schema+policy rules (~60 lines), no cross-entity joins (stated design
  boundary, the realistic shape of a quick gate).
- `arm_b1.py` — host adapter + the frozen composed 0.3 engine, unmodified.
  The adapter derives fact profiles from raw observations and logs every
  schema-required field it must invent (`fabricated_fields` — the
  adapter-burden metric). `--calibrated` adds one applicability rule:
  OBL-17 is declined for records with no second lifecycle event.
  `--subprocess` measures the shipped stdio ABI instead of in-process calls.
- `score.py` — referee. Joins verdicts with truth; emits `RESULTS.md` +
  `results.json`.

Both arms read `corpus.jsonl` and nothing else (same-information rule).

## Result (2026-08-10 run, 408 records: 398 real, 10 seeded; 18 defective)

| arm | detected | false holds | mean latency |
|---|---|---|---|
| baseline gate | 17/18 | 0 | 0.009 ms |
| B1 strict adapter | 18/18 | 133/390 clean (34.1%) | 3.0 ms (105 ms via stdio ABI) |
| B1 calibrated adapter | 18/18 | 0 | 2.0 ms |

- The five REAL defects found in live records (task files whose result
  pointers rot when handoffs were archived) were caught by both arms.
- The one defect only B1 caught is the relational one: a document relying
  solely on a superseded version chain member — the blame join a quick
  single-record gate omits by design.
- The strict arm's 133 false holds all come from forcing OBL-17
  (acknowledgment-after-effect) onto single-event lifecycles that have no
  acknowledgment concept. The contract has no applicability/abstention
  mechanism; the adapter must either refuse (calibrated) or fabricate and
  false-hold (strict). This is a confirmed contract gap. Its practical half
  closed host-side rather than in the contract: the exported three-state
  preflight (`adapters/README.md`) abstains explicitly, and replaying the same
  408-record corpus gives 0 new false holds, 208 insufficient, detection 18/18
  (`python -B adapters/outcome_receipt.py --check`). The contract-level half is
  still open and is not on any 0.4 list — 0.4 shipped through 0.4.2 without an
  `INAPPLICABLE` class, and `ERRATA.md` E7 defers it to a new sealed
  generation.
- Adapter burden: 768 fabricated field values across 384/408 decisions —
  the quantified form of the review's "the host does the hard part."

## Honest limits

Small defect population (18, 10 of them seeded); one workspace, one
operator, four obligation families exercised out of 30; the SUPERSEDE
difference rests on one real instance; adapter and referee share an author.
A preregistered, author-separated, multi-domain run is the next tier.

## Reproduce

```bash
python -B extract_corpus.py && python -B arm_baseline.py && python -B arm_b1.py && python -B arm_b1.py --calibrated && python -B score.py
```

Extraction is operator-only: `extract_corpus.py` requires
`RR_SOURCE_WORKSPACE` to point at the source workspace and exits with an
explanation otherwise. `corpus.jsonl`, `truth.jsonl`, verdicts, and request
logs are workspace-derived and stay untracked (see `.gitignore`); the
committed artifacts are the protocol (this file, the four scripts), the
deterministic synthetic corpus pair, and the results snapshot
(`RESULTS.md`, `results.json`).

## Reproducing this without the operator workspace

The operator-only pipeline above is not the third-party path, and you do not
need `RR_SOURCE_WORKSPACE` to check the headline number. The same 408 records
and their referee truth are published verbatim in this repository:

| Withheld working copy | Published, byte-identical |
|---|---|
| `proof/corpus.jsonl` (213,408 bytes) | `adapters/fixtures/parent_corpus_408.jsonl` |
| `proof/truth.jsonl` (41,277 bytes) | `adapters/fixtures/parent_truth_408.jsonl` |

So from a clean clone, with no private inputs, this replays every record and
reproduces the detection result:

```bash
python -B adapters/outcome_receipt.py --check
```

Expected: `WP1 all-408 fallback replay: 0 new false holds, 208 insufficient,
detection 18/18; FALLBACK_DELIVERED_RUNTIME_BAR_MET`.

To exercise this harness itself from published bytes, use the synthetic pair
(`corpus.synthetic.jsonl`, `truth.synthetic.jsonl`, regenerated by
`synthetic_corpus.py`) with `test_proof_harness.py`.

What third parties still cannot re-derive is the *extraction* step — turning a
live coordination workspace into fact profiles — because that reads the
operator's private records. The 408 extracted records themselves, the referee
truth, and the scoring are all published and checkable. Read the limits in
"Honest limits" above before quoting any number from here.
