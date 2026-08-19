# Method — 03-internal-flag-external-traffic

**Demonstrable claim.** RR classifies the adapted
`defective-external-recipient` record as `OMISSION_OR_INCOMPLETE` /
`UNRESOLVED` and the clean twin as `VALID` / `SATISFIED`.

## Obligation selected

`OBL-12` — *"Parameterize information flows by sender, recipient, subject,
information type, transmission principle, context, purpose, and scope."*
Operation handle `OPR_06537A7F14C0E290D443B932`.

Decision-table limb that fires: the `OMISSION_OR_INCOMPLETE` disjunction
`declared_recipient_id != actual_recipient_id` **or**
`declared_scope_sha256 != actual_scope_sha256`. Both disjuncts fire in the
defective record, which is faithful to the incident: the flag's declared
audience and the traffic it governed disagreed, and so did the declared and
actual classifier configuration.

## Divergence from the fit document's mapping

The unpublished workspace analytical mapping maps this incident to
use-outside-declared-scope (the `OBL-03` class) plus closure discipline. This
corpus maps it to `OBL-12` instead, because the incident's observable delta is a
*flow parameterisation* — declared audience versus actual audience — and
`OBL-12` evaluates exactly that pair. The `OBL-03` scope shape is exercised by
incident `11-mast-task-derailment-out-of-scope`, and the closure-discipline
shape by `05-exclusion-filter-false-clean`. The divergence is recorded here
rather than resolved: the fit document's reading is not wrong, and a fuller
corpus would carry both mappings.

## The adaptation

| Incident element | Fact field | Value |
|---|---|---|
| flag declares an internal audience | `declared_recipient_id` | `RECIPIENT_INTERNAL_EVALUATION_LANE` |
| traffic actually governed (defective) | `actual_recipient_id` | `RECIPIENT_VENDOR_WORKFORCE_TRAFFIC` |
| traffic actually governed (clean) | `actual_recipient_id` | `RECIPIENT_INTERNAL_EVALUATION_LANE` |
| declared configuration | `declared_scope_sha256` | SHA-256 of `flow-scope/internal-evaluation-classifiers-on` |
| actual configuration (defective) | `actual_scope_sha256` | SHA-256 of `flow-scope/vendor-workforce-classifiers-off` |
| the flag itself | `transmission_principle` | `PRINCIPLE_INTERNAL_ONLY_FLAG` |
| collection context | `context_id` | `CONTEXT_HUMAN_FEEDBACK_COLLECTION` |
| what flowed | `information_type` | `TYPE_MODEL_EXCHANGE_TRANSCRIPT` |
| who sent | `sender_id` | `SENDER_SERVING_STACK` |

## Where judgment entered

1. **Obligation choice diverges from the analytical mapping** — see the section
   above. That is the largest judgement call in this incident.
2. **`recipient_id`, `purpose_id`, `subject_id` are schema-required and not in
   the public record.** They are filled with non-firing values. Under H3/H4 a
   real host must derive or abstain rather than fill; the corpus fills and
   declares it. Note that `context_id`, `information_type`, `purpose_id`, and
   `subject_id` are registered in `grounded-0_4/authority_register_0_4.json` as
   inert for classification, so the fill affects nothing but schema validity —
   but `recipient_id` is not inert (it feeds the `MALFORMED_OR_BOUNDARY` limb
   against `sender_id`), and its value is a corpus-author choice.
3. **Two disjuncts fire at once.** The corpus chose to make both the recipient
   and the scope diverge, because the incident describes both. That means the
   record does not isolate which disjunct produced the class. A stricter corpus
   would carry two single-delta records. This one does not, and says so.
4. **Digests stand for configurations, not configurations.** As elsewhere, the
   two scope digests are hashes of ASCII labels; any two distinct values give
   the same class.
5. **Eleven months, 133M exchanges, 50,000 contractors.** None of that is
   represented. Scale does not enter the classification.
6. **Carrier envelope.** Request envelope verbatim from the frozen fixture entry
   named in `expected.json`; only `decision_input.facts` is incident-derived.

## Preflight lane — `abstain_uncalibrated`

Native evidence in family `INFORMATION_FLOW`; the portable preflight has no
calibration rule for it and returns `INSUFFICIENT_EVIDENCE` with
`PREFLIGHT_FAMILY_UNCALIBRATED`. Abstention, not a pass and not a detection.
The corpus invokes the engine anyway to demonstrate the classification; a
compliant integration would need its own calibrated adapter first
(`adapters/CALIBRATION.md`, promotion gate).

## What a green replay demonstrates

RR classifies a declared-versus-actual flow mismatch as
`OMISSION_OR_INCOMPLETE`, and returns `VALID` when the declared and actual
parameters agree.

## What it does not demonstrate

That RR would have altered the real incident; that the fact profile is true of
the world (H1); anything about the traffic's content or its risk.

## Reproduce

```
python -B replay_incidents.py --incident 03-internal-flag-external-traffic --verbose
```
