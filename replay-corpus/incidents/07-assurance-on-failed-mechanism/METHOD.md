# Method — 07-assurance-on-failed-mechanism

**Demonstrable claim.** RR classifies the adapted `defective-shared-basis`
record as `OMISSION_OR_INCOMPLETE` / `UNRESOLVED` and the clean twin as `VALID`
/ `SATISFIED`.

## Obligation selected

`OBL-06` — *"Evaluate relevance, credibility, convergence, redundancy,
dependence, attack/defense, burden, standard, and unresolved status."*
Operation handle `OPR_EAE17ADAEB0A4F5E64603826`.

Decision-table limb that fires: `INTERSECTS` between
`/facts/claimed_independent_evidence_ids` and
`/facts/dependent_duplicate_evidence_ids`. An item asserted as independent
support that also sits in the dependent-or-duplicate set makes the convergence
claim unresolved, and the operation terminates there rather than counting the
item twice.

## The adaptation

| Incident element | Fact field | Value |
|---|---|---|
| the contamination discussion | member of `claimed_independent_evidence_ids` | `EVIDENCE_CONTAMINATION_DISCUSSION` |
| a genuinely separate result (clean) | member of `claimed_independent_evidence_ids` | `EVIDENCE_EVAL_HELDOUT_RESULT` |
| the exclusion-mechanism attestation | `dependent_duplicate_evidence_ids` | `["EVIDENCE_EXCLUSION_MECHANISM_ATTESTATION"]` |
| the same attestation also counted as independent (defective) | second member of `claimed_independent_evidence_ids` | `EVIDENCE_EXCLUSION_MECHANISM_ATTESTATION` |
| the standard the assurance is measured against | `governing_standard` | `STANDARD_PUBLISHED_REPORT` |
| whose burden it is | `burden` | `BURDEN_PUBLISHED_ASSURANCE` |
| support and attack weights | `support_weight` / `attack_weight` | `2` / `1` |

## Where judgment entered

1. **"Cites a mechanism documented as failing" → set intersection.** The public
   finding is about the *strength* of an assurance. The adaptation reduces it to
   the sharpest mechanical claim available: the same item appears on both the
   independent and the dependent list. Whether the real §2.9.4 presented the
   exclusion mechanism as independent support in that formal sense is a
   corpus-author reading, not a quotation.
2. **`support_weight = 2`, `attack_weight = 1` are invented.** They are
   schema-required and only need to be unequal (equal weights fire the
   `MALFORMED_OR_BOUNDARY` limb). The specific values encode nothing. Note that
   `governing_standard` and `burden` are registered as presence-only fields in
   `grounded-0_4/authority_register_0_4.json` — they are required to be present
   but carry no value-based authority — so their labels are decorative here and
   the corpus does not rely on them meaning anything.
3. **Evidence identifiers are labels chosen by the corpus author.** The report
   does not enumerate an evidence set.
4. **"Partially leaked into training data"** is not represented. The record
   covers the independence claim only.
5. **Two-member independent set in the clean twin.** Adding
   `EVIDENCE_EVAL_HELDOUT_RESULT` gives the clean record a second, genuinely
   disjoint item so that the clean and defective records differ only in whether
   the disputed attestation is on both lists. That second item is invented.
6. **Carrier envelope.** Request envelope verbatim from the frozen fixture entry
   named in `expected.json`; only `decision_input.facts` is incident-derived.

## Preflight lane — `abstain_uncalibrated`

Native evidence in family `EVIDENCE_INDEPENDENCE`; no portable calibration rule
exists, so the preflight returns `INSUFFICIENT_EVIDENCE` with
`PREFLIGHT_FAMILY_UNCALIBRATED`. Abstention, not a pass and not a detection.

## What a green replay demonstrates

RR classifies an assurance whose claimed-independent set intersects its
dependent-or-duplicate set as `OMISSION_OR_INCOMPLETE`, and returns `VALID` when
the two sets are disjoint.

## What it does not demonstrate

That RR would have altered the published assurance; that the corpus author's
reading of §2.9.4 is the right one; anything about data contamination as a
question.

## Reproduce

```
python -B replay_incidents.py --incident 07-assurance-on-failed-mechanism --verbose
```
