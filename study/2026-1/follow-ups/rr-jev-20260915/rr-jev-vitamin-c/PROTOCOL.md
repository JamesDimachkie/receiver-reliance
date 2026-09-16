# RR–Jev follow-up: changing evidence from VitaminC

Status: prospective local protocol; no study inference at creation, 2026-09-15 PT.

## Question and decision

Can a Jev support check prevent reliance on unsupported claims when source evidence
changes subtly? Does actual Receiver-Reliance (RR) improve release decisions over
an equally informed conventional policy using the same checker, artifact binding,
and one reissue opportunity? This is a benchmark-based empirical boundary study,
not a field evaluation or a claim of a new verification method.

The prior pilot's 30/30 semantic labels were easy author-written fixtures; both
receiving policies tied. Our prior is that Jev will be useful but imperfect, and
that the capable policies may again tie. A high-confidence unsupported release
defeats a perfect semantic-protection claim. Any observed policy disagreement must
be examined before attributing advantage to RR.

## Source and sampling

Use the authors' `tals/vitaminc` test.jsonl, repository revision
`be6febb761b0b2807687e61e0b5282e459df2fa0`, SHA-256
`7ad1808dbc30c62e0a1427a53022d0dfaff668a1fde3c4b612a2d266edd753ad`.
Only rows marked `revision_type=real`; group by (case_id, claim). Eligible groups
have exactly two rows with identical page and claim, distinct evidence, one
SUPPORTS and the other REFUTES or NOT ENOUGH INFO. Each evidence passage must be
at most 6,000 characters. Sort groups by SHA-256 of seed `rr-jev-vitc-20260915-v1`
plus case_id and claim. Traverse once, admitting 60 pairs of each negative-label
type and at most one pair per page. Fail if the quota cannot be filled. Freeze all
selected rows, metadata, requests, protocol, source and implementation bytes.

The 120 pairs (240 judgments) are an evaluation set with respect to our local
prompt and threshold development, not a claim of absence from Jev's training.
The public benchmark is from 2021; training contamination is unknown. Labels are
independent of this study's authors, not infallible ground truth. No relabeling or
replacement after outcomes. Preserve original scores if later inspection finds
ambiguities. The balanced, page-distinct sample is not a deployment prevalence
estimate. A page is the sampling/uncertainty unit; episodes are repeated measures.

Source: Schuster, Fisch, Barzilay (NAACL 2021),
https://aclanthology.org/2021.naacl-main.52/ and
https://huggingface.co/datasets/tals/vitaminc . Their real revisions and claims
were human annotated; this does not establish present-day Wikipedia truth.
Dataset license: Wikipedia article terms where available, otherwise CC BY-SA 3.0.
Retain the supplied license and selected row provenance; local research only.

## Checker and workflows

Reuse the first pilot's frozen three-way question without tuning. Map SUPPORTS to
supports, REFUTES to contradicts, NOT ENOUGH INFO to insufficient. Send only claim,
source_text and factual-summary intended_use. Exclude labels, IDs, page names,
benchmark canary and transition direction from model state. Use `jev-latest` and
record returned versions. One response bank is coupled across all policy arms.

Primary semantic release rule is unchanged: choice supports, P(supports) >= .90,
and confidence >= .80. Confidence measures concentration, not correctness.

For each pair, run four workflow episodes: support→negative, negative→support,
unchanged support, unchanged negative (480 total). These directions are simulated
workflow orderings; do not claim they reproduce Wikipedia's actual chronology.
Bind current source bytes and simulated revision to parent identities, and exact
claim, purpose and assessment to presented artifact bytes. Changed episodes get
revision 2; unchanged episodes retain revision 1. Run the existing actual RR host
and engine read-only; preserve the lossless `answer_json` bridge for fractions.

Primary arms: RR+Jev and the prior independent conventional relation checker+Jev.
Both see the same current evidence, direct mandate, history, validity and checker
answers, and may refresh/reissue once after structural invalidation. Neither
generates a corrected claim. Report semantic errors, legitimate supported work
withheld, structural outcomes, refreshes, logical checks and recorded worker time.
Times are harness measurements, not production latency or fair implementation-cost
benchmarks. Frozen bridge files define the restricted direct-mandate contract.

Diagnostics: (1) fresh Jev versus releasing every claim, (2) stale semantic cache
that keeps its original assessment across changes. The stale cache is deliberately
incomplete and cannot establish an RR-specific advantage. Every current source
gets a fresh judgment in the bank irrespective of initial verdict, avoiding
selection on initially accepted cases. Unchanged uses reuse the same sample;
this study does not test run-to-run stochastic consistency.

## Outcomes, uncertainty and stopping

Report all 240 three-way labels, confusion matrix, both-correct pair count,
support-probability drop from support to negative evidence, unsupported releases
among 120 negative examples, withheld support among 120 positives, and agreement
of primary policies. Fixed threshold diagnostics at .50/.80/.90/.95/.99 use
P(supports), supports choice, and the same .80 confidence gate; they are descriptive,
not a newly validated threshold choice. Report 95% Wilson intervals for primary
negative-release and positive-withheld rates; there is one such example per page.
Do not present 480 repeated episodes as 480 independent evidence examples.

No desired sign determines continuation. Complete the fixed sample before looking
at model errors. A quantified semantic limitation, meaningful sensitivity result,
policy tie or informative label ambiguity counts as evidence. No optional stopping
on favorable results. Stop after this full evaluation and independent audit; any
additional data collection requires a separately frozen follow-up protocol.

Research budget: one review lane, one pre-inference repair batch and fresh check;
one final independent evidence audit and one repair if material defects emerge.
Material means incorrect scoring, leaked labels/keys, incomparable inputs/budgets,
wrong artifacts, missing attempts, source drift, or claims stronger than evidence.
Do not spawn nested research. Root is implementation and integration writer.

API budget: at most 240 POST attempts and 1,000,000 submitted JSON bytes, no automatic
retries, 30-second request timeout, 2 MB response cap. No new purchase or billing
configuration. Key from James's authorized clipboard stays in memory; fixed TLS
api.typesafe.ai only, never persist/print it, remove before RR subprocesses.
Only public benchmark excerpts leave this machine. No publication, deployment,
source-study edits, outreach, human-subject collection or ongoing automation.

Implementation fixes before freeze are allowed and documented. After freeze,
stop collection on drift or service failure; retain partial evidence, identify
missingness, and do not silently rerun or replace cases. Evaluate from recorded
responses without additional calls. A result can narrow/reject a proposed claim;
it cannot establish field utility, broad calibration, causal superiority or demand.
