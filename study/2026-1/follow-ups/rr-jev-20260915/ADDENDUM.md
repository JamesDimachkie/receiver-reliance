# Receiver Reliance: semantic-checking follow-up

September 15, 2026 (Pacific) · Exploratory research addendum

**Two follow-up pilots found useful evidence-sensitive behavior from a semantic
checker, but no incremental RR release-decision benefit over an equally informed
conventional policy in the tested contracts.** This narrows the practical claim;
it does not establish that RR is a dead end or that the policies are equivalent
in every setting.

This is a separate follow-up to the [published 1,805-episode RR study](https://doi.org/10.5281/zenodo.22492561).
Its papers, evidence, archive and conclusions remain unchanged. The follow-ups
use different populations and questions; their counts must not be pooled with
each other or with the published study. This is neither an erratum nor a software
release. The RR engine was unchanged; the integration bridge is experiment code.

## What changed

The pilots placed a live semantic checker, TypeSafe Jev, inside a receiving
workflow. RR checked the supplied structural relationships and applicability;
Jev assessed whether supplied evidence supported a claim. The conventional
comparator received the same relevant facts, checker responses, obligations and
reissue budget. Both policies were evaluated under an honest simulated host.

Every live response returned `jev-1.13.0` through the `jev-latest` alias. The
identifier records the observed model; it does not guarantee an immutable endpoint
or identical future inference. These pilots do not establish calibration or
frontier-level intelligence.

| Study | Evaluation unit | Observations | RR versus conventional |
|---|---|---|---|
| [Synthetic feasibility](rr-jev-feasibility/RESULTS.md) | 48 hand-authored episodes in six families; 30 unique live judgments | Adding Jev removed all 12 unsupported/contradicted releases while retaining all 30 supported, permitted claims | Same release decisions on all episodes, both with and without Jev |
| [VitaminC follow-up](rr-jev-vitamin-c/RESULTS.md) | 120 real-revision contrast pairs from 120 pages; 240 live judgments; 480 correlated workflow replays | Support probability decreased in 112/120 pairs; three-way benchmark-label agreement was 194/240 (80.8%) | Same release decisions in all 480 episodes; same 240 refreshes and 720 logical checks per policy |

The VitaminC sample was selected and the protocol frozen before inference: 60
SUPPORTS/REFUTES pairs and 60 SUPPORTS/NOT ENOUGH INFO pairs, ordered by a fixed
hash seed. No prompt, threshold or sample was changed after inspecting outcomes.
Collection stopped at the declared 240-call budget. The four episodes per pair
simulate changed and unchanged evidence, not Wikipedia's edit chronology.

The primary semantic gate required a supports choice, support probability at
least .90, and confidence at least .80. It accepted **one of 120
benchmark-negative examples** and withheld **38 of 120 benchmark-positive
examples**. Tightening the probability threshold to .99 withheld 67 positives
and retained the same negative-label acceptance. Thresholding alone did not
remove that disagreement. The stale-cache diagnostic performed worse, but a
capable conventional policy matched RR; freshness protection was not unique to RR.

## Why label agreement is not accuracy

Four purposively inspected SUPPORTS annotations conflict with the supplied
passages: mismatched counts, a different rating service, a different football
opponent, and a fact transferred between settlements. These are post-outcome
observations, not a blind relabeling exercise or an estimate of overall label
quality. All original labels and scores remain in the evidence.

The sole accepted benchmark-negative example concerns the **district of
Heinsberg**, while its passage refers to **Heinsberg** without resolving the
city/district distinction. Jev assigned support probability and confidence 1.00.
That is a confident benchmark disagreement, not an unequivocally demonstrated
false factual release. It also does not justify claiming zero semantic errors.

Our own input construction omitted page titles with benchmark metadata. Some
passages need that context to resolve an antecedent. The benchmark is public,
training contamination is unknown, and the balanced sample is not deployment
prevalence. The 38 withheld positives therefore cannot be read as 38 proven
instances of valid work lost. See the [full results and examples](rr-jev-vitamin-c/RESULTS.md).

## What this means for RR

The measured conclusion is **no incremental release-decision benefit in these
two narrow contracts**. Another comparison between equally expressive toy
policies would not by itself establish distinctive practical value.

These pilots did not measure implementation, maintenance, human review, audit or
coordination effort. They did not test adversarial cross-party binding. RR's
additional practical value remains unproven; a future RR-specific study would
need a measured engineering or audit benefit against a capable alternative in
a realistic workflow. This addendum does not start that study or reopen the
completed paper.

## Evidence and review

The supplement retains the two protocols, freezes, original reports, recorded
requests/responses, policy rows, RR invocation receipts and presented bytes.
Both pilots used actual RR invocations. The existing audits checked 168 RR
receipts and 174 presentations in the first pilot, and 720 receipts and 332
presentations in the follow-up, in addition to qualification checks.

These are internal, author-separated agent reviews under one operator, **not
external replication**. Neither receipt consistency nor agreement among reviewers
proves scientific correctness. See [feasibility review](rr-jev-feasibility/REVIEW.md),
[follow-up pre-inference review](rr-jev-vitamin-c/REVIEW.md), and
[follow-up final audit](rr-jev-vitamin-c/FINAL-AUDIT.md).

The original reports are copied byte-for-byte as historical records. Their
shorthand, including “negative RR result,” is qualified by this addendum. The
first report's proposed next study is not retroactively rewritten: the VitaminC
follow-up is a benchmark experiment, not the independently adjudicated field
study it proposed. Local credential-custody files mentioned in the second report
are deliberately excluded from the supplement; they are not scientific outcomes.

See [evidence and verification instructions](EVIDENCE.md) and
[licensing and attribution](LICENSES.md). This local update does not itself
create a public release or a new DOI.
