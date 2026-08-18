# Withheld artifacts — what is not published, and why

This repository's claims are checkable from published bytes plus the
conformance suites; where a chain crosses an unpublished artifact, the
artifact is pinned by digest so any future release is verifiable against
bytes already frozen here. This file is the complete ledger of what stays
unpublished, the reason, and the pin that keeps each item honest.
Published evidence lives in `evidence/` (see its README for the recipe).

| Artifact | Why withheld | Verifiability anchor |
|---|---|---|
| `TOOLCHAIN_MANIFEST_0_1.json` | Carries machine-path provisioning evidence from the operator's workstation (privacy). Both conformance modes run without it; only manifest regeneration needs it. | Path, byte length, and raw SHA-256 pinned in the contract under `toolchain_manifest_tree_reference`. |
| Foundation 0.4 / 0.4.1 / 0.4.2 and the Gate 0 governing documents | Working documents of the research program this baseline was carved from; they specify the still-unrun blinded experiment (arms, endpoint, forfeit rules). Publishing them is deferred until that experiment's design freeze no longer depends on limiting exposure. | SHA-256 digests quoted in `evidence/A1_CAPABILITY_FLOOR_0_1.md` (subordination block). |
| Research collision map, comparator collision adjudication, comparator-floor review (prior-art snapshot components S41–S43) | Same program-internal category: field mapping and admission records for the research program, releasable at the operator's discretion later. Their evidentiary role for THIS artifact is fixed by digest. | Byte lengths and raw SHA-256 digests pinned inside the shipped `supplemental-0_3/PRIOR_ART_SNAPSHOT_0_3.json`. |
| Ten-round adversarial review probe history (0.2 acceptance) and the blind reviewer's session transcript | Embedded in interactive session records that interleave unrelated operator context; extraction without that context is the summarized record already published. | Round-by-round table with probe counts, findings, and dispositions in `ACCEPTANCE.md`. Forward practice has improved: the continuation run's refuter reports are published in full under `orchestration/refuters/`. |
| `proof/corpus.jsonl`, `proof/truth.jsonl`, `proof/verdicts_*.jsonl`, `proof/requests_log*.jsonl` | Working copies the operator-only extractor writes in place. They are NOT the reproduction path and nothing published depends on them: the same 408 records and their referee truth are published verbatim as `adapters/fixtures/parent_corpus_408.jsonl` and `adapters/fixtures/parent_truth_408.jsonl` (byte-identical, 213,408 and 41,277 bytes). | Reproduce the headline detection result from published bytes with `python -B adapters/outcome_receipt.py --check`; the published fixtures carry the same digests these working copies would. |
| Research program source components, integration notes, superseded 0.1-generation artifacts | Not part of the baseline artifact; excluded from release scope (see `baseline-run/RUNBOOK.md`). | The shipped contracts pin every authority the runtime actually loads. |

Two properties keep this ledger honest:

1. **Nothing withheld is load-bearing for the published claims.** Every
   conformance, regression, lint, property, adversarial, and batch check in
   this repository runs from published bytes alone, and so does the
   applicability result: `python -B adapters/outcome_receipt.py --check`
   replays all 408 records from `adapters/fixtures/` and reproduces
   `detection 18/18, 0 new false holds`.
   One precise exception, stated rather than implied: the `proof/` arm scripts
   (`arm_baseline.py`, `arm_b1.py`, `score.py`) read `proof/corpus.jsonl`,
   which only the operator-only `extract_corpus.py` writes. That pipeline is
   therefore NOT third-party runnable end to end. It is also not the
   reproduction path — the published `adapters/fixtures/` pair carries the same
   408 records byte-identically, and `proof/corpus.synthetic.jsonl` with
   `proof/synthetic_corpus.py` exercise the harness itself from published
   bytes. No published number depends on running `extract_corpus.py`.
2. **Every withheld item that any published chain references is
   digest-pinned in published bytes**, so a later release can be verified
   against commitments made now — withholding cannot be used to swap
   evidence after the fact.
