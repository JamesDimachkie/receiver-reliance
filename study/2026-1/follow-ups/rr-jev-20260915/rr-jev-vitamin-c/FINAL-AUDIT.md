# Final independent evidence audit

Date: 2026-09-16 UTC (September 15 Pacific). Reviewer: `vitc_final_audit`, a
fresh-context reviewer separate from the implementation/report author.

**PASS. No material defect or repair required in the scientific evidence and
reviewed report.** One bounded final audit was completed. The reviewer made no API
requests, accessed no credentials, reran neither the model nor the RR engine, and
changed only this file and `results/final-audit.json`.

The reviewed `RESULTS.md` SHA-256 is
`F7D1B6E40EBE8B7810AE30DC77270FE9B0197B0C450C5752728F36A0203DAA84`.
The machine-readable audit binds the report, freeze, summary, semantic rows and
workflow rows and records the checked counts and interpretation limits.

## Evidence integrity and scoring

- All nine frozen study/dependency hashes, all 59 RR source hashes, the dataset
  hash, qualification identity and pre-inference review identity matched. The
  complete RR source manifest matched, not only a selected subset of files.
- Independently reconstructed dataset selection and shuffled request order:
  120 pairs from 120 pages, 60 pairs per negative-label stratum, 240 unique
  requests and 259,220 submitted bytes. Requests contain only the declared
  claim, source text, factual-summary purpose and unchanged pilot question.
- Matched all 240 sequential attempt entries to successful raw-response records,
  their exact requests, byte counts, timestamps, parsed responses and hashes.
  There were no missing or extra judgment-response records. Recorded response
  probabilities, choices and token accounting passed validity checks.
- Independently recomputed every semantic row, pair row, summary metric,
  threshold diagnostic and Wilson interval from the original labels and recorded
  responses. Results are 194/240 label agreements, 81/120 both-label matches,
  112/120 support-probability decreases, one benchmark-negative release and
  38 benchmark-positive withholdings at the frozen gate.
- Independently reconstructed all 480 episode definitions and checked all 1,440
  result rows across the three arms. The primary arms matched on release,
  refresh and final structural result in all 480 episodes. Each performed 240
  refreshes and 720 logical checks using the same response bank and budget.
- Verified all 720 saved RR receipts with the existing offline observer and
  matched their COMMON documents to the frozen bridge construction. The saved
  receipts contain 720 actual engine calls: 240 `R_LINEAGE_CONCLUSIVE` outcomes
  and 480 `R_ACCEPTANCE_APPLICABLE` outcomes. Also reverified all 32 qualification
  receipts offline. No runtime or engine was rerun for these checks.
- Verified all 332 presentation files against the exact delivered bytes, current
  claim, source digest/revision, purpose and current assessment. The fractional
  answers round-trip without loss through `answer_json`. Trace and presentation
  filename sets exactly match the expected coverage, with no extras or gaps.

The audit independently recomputed selection and scoring. It reused the frozen
bridge to compare serialized COMMON documents and the existing observer to check
wire/witness integrity, with direct payload checks as an additional constraint.
This is an author-separated internal consistency audit under the honest-host
assumption, not independent engine reimplementation, remote service attestation,
or protection against an administrator fabricating local evidence.

## Semantic and claim review

The report correctly presents benchmark agreement rather than a clean correctness
estimate. Independent inspection confirms its four supplied-source problems:

| Pair | Observation |
|---|---|
| `0012D56A7F2646890268` | Gold SUPPORTS pairs 250 recoveries in the claim with 243 on the same date in the passage. |
| `0047BE43CEBDFD573A9F` | Gold SUPPORTS attributes a rating to Rotten Tomatoes while the passage gives a Metacritic rating. |
| `01796F4EDF78B1C1ED82` | Gold SUPPORTS names Man United while the passage names Manchester City; it does not establish the claimed opponent. |
| `00FB48EB337F08B01DF9` | Gold SUPPORTS transfers Dutch founding from Huys de Goede Hoop to Windsor, which the passage calls an English settlement. |

All four were withheld. The Robert Huth passage does not prove that no other
match occurred; the defensible conclusion is failure to establish support for
the exact supplied claim. The report preserves that distinction.

The only released benchmark-negative item is
`5ee3932bc9e77c0008cca656_2`: the claim specifies the district of Heinsberg while
the passage says Heinsberg. Its reported support probability and confidence are
both 1.00. This establishes a confident disagreement with the NOT ENOUGH INFO
label. The supplied excerpt does not settle the city/district referent well
enough to call it an unequivocally false factual release. The report neither
relabels it nor infers zero semantic errors.

Page titles and missing antecedents matter: excerpts referring to “the county,”
“the track,” or “It” can omit the named subject in the claim. Excluding page
metadata means some requests lack useful source context. This limits interpretation
of Jev's raw score while leaving the primary-policy input parity intact.

The purposive, post-outcome inspections above are not a complete blind adjudication
of 240 examples. No gold labels were changed, no adjusted “clean” accuracy was
computed, and no inference was repeated. The report's positive evidence-sensitivity
result and its probability-gate tradeoff are supported by the recorded data.

The RR conclusion is appropriately bounded: no additional release-decision
benefit over this capable conventional policy in the simulated, honest-host,
direct-mandate source-change contract. The stale-cache diagnostic cannot establish
an RR-specific advantage. Repeated workflow episodes are not additional independent
semantic observations. Neither this tie nor its receipts establish broad
equivalence, security efficacy, real-world demand, or reduced implementation and
audit effort.

## Audit limits

Credential storage, ACL/authentication and plaintext scanning were separate
root-owned checks; the reviewer did not access the secret or independently attest
those claims. The credential amendment was read for scope. External pricing and
invoices, current Wikipedia truth, training contamination and future model-alias
behavior were not revalidated in this bounded offline audit. The report identifies
those scientific and billing limits rather than treating them as direct findings.

Evidence: [frozen protocol](PROTOCOL.md), [freeze](freeze.json),
[reviewed report](RESULTS.md), [machine-readable audit](results/final-audit.json),
[semantic rows](results/semantic.json), [summary](results/summary.json),
[workflow rows](results/episodes.json), [pre-inference review](REVIEW.md).
