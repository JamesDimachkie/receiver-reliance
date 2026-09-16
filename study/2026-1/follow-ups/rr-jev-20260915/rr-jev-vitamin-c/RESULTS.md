# RR–Jev follow-up: useful evidence sensitivity, no additional RR decision benefit

Completed September 15, 2026 Pacific. Project-generated benchmark study, not an
external validation or a field trial. **We found a useful positive result, a
negative RR result, and a problem with treating benchmark labels as truth.**

Jev's support probability fell when the evidence changed from benchmark-supporting
to benchmark-negative in **112/120 pairs**. RR and an equally informed conventional
policy made **identical decisions in all 480 workflow episodes**. Some benchmark
labels conflict with the supplied passages, so the raw label-agreement score is
not a clean estimate of model correctness.

## What actually ran

We froze 120 contrast pairs from 120 distinct Wikipedia pages in the authors'
VitaminC test set: 60 SUPPORTS/REFUTES and 60 SUPPORTS/NOT ENOUGH INFO pairs marked
as real revisions. Selection used a fixed hash ordering before model outcomes.
The same claim is judged against two slightly different passages. These are
independently authored benchmark annotations; we did not write their labels.
[Dataset and attribution](https://huggingface.co/datasets/tals/vitaminc),
[original paper](https://aclanthology.org/2021.naacl-main.52/).

All **240 live calls** completed, returning **jev-1.13.0** through `jev-latest`.
The unchanged question from our first pilot received only the claim, evidence
passage and intended factual-summary use. No labels or benchmark IDs were sent.
No prompt or threshold was tuned on these outcomes. The release rule remained:
supports choice, support probability at least .90, confidence at least .80.

Four simulated episodes per pair covered both change directions and both unchanged
states. These are **480 correlated replays of 240 judgments**, not 480 independent
test examples or a reconstruction of Wikipedia's chronological edit sequence.
Both primary policies used the same source, assessment, mandate and one permitted
reissue after invalidation. The actual RR engine ran 720 times; it was not a mock.

## Frozen-label results

| Measure | Observed result |
|---|---:|
| Exact three-way agreement with dataset labels | 194/240 (80.8%) |
| Pairs with both labels matched | 81/120 (67.5%) |
| Pairs whose predicted label changed | 101/120 |
| Pairs whose support probability decreased | 112/120 (93.3%) |
| Median support-probability decrease | .95 |
| Benchmark-negative examples released | 1/120 (0.83%) |
| Benchmark-positive examples withheld | 38/120 (31.7%) |
| Benchmark-positive examples released | 82/120 (68.3%) |
| Pairs with both release decisions matching gold | 81/120 |

The 95% Wilson intervals are **0.15–4.57%** for negative-label release and
**24.0–40.4%** for positive-label withholding. Each denominator has one example
per page. These describe this balanced benchmark sample, conditional on its
labels; they do not account for annotation errors, missing context, model training
contamination or deployment prevalence.

| Dataset label → predicted label | supports | contradicts | insufficient |
|---|---:|---:|---:|
| supports (120) | 101 | 7 | 12 |
| contradicts (60) | 3 | 43 | 14 |
| insufficient (60) | 4 | 6 | 50 |

A semantic accept-all reference would release all 120 benchmark-negative examples.
The fixed Jev gate withheld 119 of them, while also withholding 38 benchmark
positives. That is a measurable selectivity/completion tradeoff; the annotation
audit below prevents interpreting every withheld positive as valid work lost.

## The most important surprise: the score's labels are not all defensible

We retained all original labels and all original scores. Post-outcome inspection
of disagreements was purposive, not a new blind annotation study. An independent
reviewer checked the following supplied-source conflicts:

| Example | What the frozen data says | Why the label is problematic |
|---|---|---|
| Bulgaria, `5ee3932bc9e77c0008cca2b4_1` | Claim: 250 recoveries; passage: 243 on the same date; gold: SUPPORTS | The count does not match. Jev chose contradicts with .99 confidence. Its rejection is counted against the gold label. |
| Collateral Beauty, `5ebbf32bc9e77c0009295730_1` | Claim attributes ratings to Rotten Tomatoes; passage attributes them to Metacritic; gold: SUPPORTS | A rating from a different named service does not establish the claimed attribution. Jev chose insufficient. |
| Robert Huth, `5ece9463c9e77c000846776e_1` | Claim names Man United; passage names Manchester City; gold: SUPPORTS | The passage does not establish the named-opponent claim. This does not prove no other match occurred. Jev rejected support. |
| Windsor, `5ec7d50ec9e77c0008442b43_2` | Claim says the Dutch established Windsor; passage calls Windsor the first English settlement and attributes Dutch founding to Huys de Goede Hoop; gold: SUPPORTS | The claim transfers a fact to a different settlement. Jev rejected support. |

The sole released benchmark-negative example,
`5ee3932bc9e77c0008cca656_2`, asks about **the district of Heinsberg** while the
passage says **Heinsberg** initiated school closures. Jev returned support
probability **1.00** and confidence **1.00**; gold is NOT ENOUGH INFO. The missing
city/district distinction makes this a confident benchmark disagreement, **not
an unequivocally demonstrated false factual release**. We do not relabel it or
claim zero semantic errors.

There is also an input-context limitation in our own design. We excluded page
titles with benchmark metadata, but some excerpts depend on antecedents such as
“the county” or “the track.” Removing an informative page title can make an
otherwise labeled claim harder to establish from the supplied passage alone.
This affects claims about Jev accuracy; it does not change the fact that the two
receiving policies saw identical inputs and tied. We did not rerun with added
context after seeing results. A subsequent semantic study should preserve useful
source context, independently adjudicate labels, then freeze a new evaluation set.

## Tightening confidence thresholds did not fix the observed disagreement

This threshold table was specified before inference. All rows retain the supports
choice requirement and .80 confidence gate.

| Minimum support probability | Negative-label releases /120 | Positive-label withheld /120 |
|---|---:|---:|
| .50 | 1 | 32 |
| .80 | 1 | 32 |
| **.90 — primary** | **1** | **38** |
| .95 | 1 | 45 |
| .99 | 1 | 67 |

Raising .90 to .99 withheld 29 additional benchmark-positive examples and did not
remove the sole negative-label acceptance, which had probability 1.00. This is a
useful boundary of score-only gating on this sample. It is not a validated new
threshold recommendation or a general calibration verdict. TypeSafe's confidence
describes distribution concentration, not overall workflow correctness.
[Confidence documentation](https://docs.typesafe.ai/confidence).

## What this says about RR

| Workflow measure (480 repeated episodes) | RR + Jev | Conventional + Jev | Stale-cache diagnostic |
|---|---:|---:|---:|
| Released | 166 | 166 | 166 |
| Releases against a negative label | 2 | 2 | 83 |
| Withheld against a positive label | 76 | 76 | 157 |
| Refreshes | 240 | 240 | 0 |
| Logical semantic checks | 720 | 720 | 480 |

The two negative-label releases in each primary arm are replays of **one** unique
example. The unchanged and changed-direction uses repeat the same checker bank.
All initial changed-source assessments were rejected and then refreshed; unchanged
uses retained their original assessment. Both primary policies finished with valid
structural bindings. The actual released bytes were retained and checked against
the current claim, source hash/revision, purpose and assessment.

The stale cache is deliberately incomplete. Its worse results show why evidence
freshness matters, **not an RR-specific advantage**. A capable conventional policy
obtained the same protection and the same completion as RR. This study therefore
finds **no incremental RR release-decision benefit in this narrow contract**.
It does not establish broad equivalence, nor test whether RR reduces engineering,
audit, maintenance or coordination effort in a real multi-party workflow.

Decision: **NARROW**. Jev is promising as an evidence-sensitive checker requiring
review/abstention policy. RR correctly governed assessment freshness here, but its
additional practical value remains unproven. The next RR-specific question would
need measured implementation or audit burden against a capable alternative;
another equally expressive toy policy comparison alone cannot establish that value.

## Cost, provenance and verification

- 240 judgment POSTs; **259,220** submitted JSON bytes; **125,692 input tokens**.
- Median HTTP round trip **238 ms**; maximum **369 ms**. Not end-to-end workflow latency.
- RR worker time totaled **111.657 seconds** over 720 invocations. This includes
  this harness's process/controller path and is not a fair production speed comparison.
- Coupled-bank workflow accounting is 377,076 logical input tokens per primary
  arm. Actual paid/service input was 125,692 tokens, not the sum across replay arms.
- At the previously documented advertised $0.042/million input-token rate, the
  arithmetic estimate is **$0.00528**. This is not a checked invoice or current
  account billing statement; tokens and request counts are the direct observations.
- Prospective freeze and independent pre-inference review; 32 qualified actual-RR
  configurations; 240 raw response records; 720 live-bank RR receipts; 332 exact
  released artifacts. A separate fresh-context final audit checks the evidence.
- The completed first pilot and published RR study remain unchanged. No model
  retraining, post-outcome threshold selection, retry, replacement or extra sample.

Initial model discovery returned HTTP 401 with a stale/incorrect clipboard
credential, before any judgment POST. James then explicitly authorized encrypted
storage. The replacement authenticated, was stored with Windows-user DPAPI and
restricted ACLs, and was successfully reloaded without the clipboard. The separate
credential amendment/review/receipt document this; no plaintext key is in this
bundle. The initial credential's rejection cause beyond HTTP 401 is unknown.

The full fixed sample and planned audit provide meaningful positive, negative and
measurement-quality findings. Collection stopped at its declared 240-call budget;
we did not continue searching for a favorable RR result.

Evidence: [protocol](PROTOCOL.md), [freeze](freeze.json), [selected source rows](selected.json),
[semantic judgments](results/semantic.json), [summary](results/summary.json),
[workflow rows](results/episodes.json), [pre-inference review](REVIEW.md),
[final audit](FINAL-AUDIT.md), [dataset license](LICENSE-DATA.txt).
