# Method — 06-peer-refusal-adopted

**Demonstrable claim.** RR classifies the adapted
`defective-repetition-promotes-support` record as `OMISSION_OR_INCOMPLETE` /
`UNRESOLVED` and the clean twin as `VALID` / `SATISFIED`.

## Obligation selected

`OBL-23` — *"Prevent permission, handoff, trusted-tool traversal, receipt,
repetition, or successful execution from automatically promoting evidentiary
support."* Operation handle `OPR_60F3672F648865577D64EC8F`.

Decision-table limb that fires is a conjunction, all three of which must hold:

- `support_before != "SUPPORTED"`, and
- `support_after == "SUPPORTED"`, and
- `successful_execution_count > 0`.

In words: support appeared, and the only thing between the two states was
successful execution. `OBL-23` terminates that as `OMISSION_OR_INCOMPLETE` —
the promotion has no evidentiary basis, so the support state is unresolved
rather than established.

## The adaptation

| Incident element | Fact field | Value |
|---|---|---|
| no recorded assessment supported the position beforehand | `support_before` | `"UNSUPPORTED"` |
| the position was treated as supported afterwards (defective) | `support_after` | `"SUPPORTED"` |
| the position was still not treated as supported (clean) | `support_after` | `"UNSUPPORTED"` |
| three agents ran and reported success | `successful_execution_count` | `3` |
| the notebook entry, as an assessment record | `evidence_assessment_sha256` | SHA-256 of `evidence-assessment/safety-task-avoidance-note` |

## Where judgment entered

1. **The clean twin is the interesting choice here.** It is *not* "the agents
   did not adopt the refusal." It is "the adoption happened and was recorded,
   and the support state was not promoted by it." That is the honest clean twin
   for `OBL-23`, whose subject is the promotion, not the adoption. A reader
   expecting the clean twin to depict a healthy team should read it again.
2. **`successful_execution_count = 3` is a stand-in.** The public record gives
   three days of green metrics, not three executions. Any value greater than
   zero produces the same class; the number carries no meaning in the mapping,
   and using the day count as an execution count is a corpus-author liberty.
3. **`evidence_assessment_sha256` is present so the `BINDING_OR_CONFLICT` limb
   (absent assessment) does not fire.** Treating the notebook entry as an
   evidentiary assessment record is itself a modelling choice: the incident
   describes a note, not an assessment. Declared fabrication under H3.
4. **`support_before` / `support_after` are conclusions, not observations.**
   `HOST_OBLIGATIONS.md` H3 requires that fields carrying conclusions be derived
   by an auditable process. Here they were set by the corpus author from a prose
   description. That is the weakest link in this incident and the reason it
   would not survive as evidence in a real integration without a derivation
   pipeline behind those two fields.
5. **Three days of unreviewed green metrics** is the part of the incident that
   most matters operationally, and it is not represented at all. `OBL-23`
   classifies the promotion; it says nothing about how long the promotion went
   unexamined.
6. **Carrier envelope.** Request envelope verbatim from the frozen fixture entry
   named in `expected.json`; only `decision_input.facts` is incident-derived.

## Preflight lane — `abstain_uncalibrated`

Native evidence in family `SUPPORT_PROMOTION`; no portable calibration rule
exists, so the preflight returns `INSUFFICIENT_EVIDENCE` with
`PREFLIGHT_FAMILY_UNCALIBRATED`. Abstention, not a pass and not a detection.

## What a green replay demonstrates

RR classifies a support state that moved to `SUPPORTED` with successful
execution as the only intervening fact as `OMISSION_OR_INCOMPLETE`, and returns
`VALID` when execution did not move the support state.

## What it does not demonstrate

That RR would have altered the real incident; that the two support-state fields
were derived rather than asserted (they were asserted); anything about agent
belief, motivation, or the safety task itself.

## Reproduce

```
python -B replay_incidents.py --incident 06-peer-refusal-adopted --verbose
```
