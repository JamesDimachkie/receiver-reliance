# Method — 12-mast-verification-without-basis

**Demonstrable claim.** RR classifies the adapted
`defective-no-verification-transition` record as `BINDING_OR_CONFLICT` /
`VIOLATED`, the adapted `defective-receipt-pins-superseded-version` record as
`OMISSION_OR_INCOMPLETE` / `UNRESOLVED`, and the clean twin as `VALID` /
`SATISFIED`.

## Obligation selected

`OBL-27` — *"Represent handoff acceptance as version-pinned proposed, accepted,
committed, executed, shipped, and verified state transitions, each separate from
and linked to its exact receipt, without collapsing recipient sufficiency,
authority, decision ownership, or downstream obligations."* Operation handle
`OPR_0FBCA8E91BDEF7697BE4D088`.

Two limbs are exercised:

- `NOT_CONTAINS_ALL` over `/facts/transition_names` against the six required
  names → `BINDING_OR_CONFLICT`. This is the MAST **FM-3.1 / FM-3.2** shape: the
  handoff was shipped without a verification transition ever being recorded.
- `NOT_ALL_EQUAL_PATH` between `/facts/receipt_handoff_version_sha256s` and
  `/facts/handoff_version_sha256` → `OMISSION_OR_INCOMPLETE`. This is the
  **FM-3.3** shape: a verification receipt exists, but it attests a different
  handoff version than the one being accepted.

## The adaptation

| Incident element | Fact field | Value |
|---|---|---|
| the handoff version being accepted | `handoff_version_sha256` | SHA-256 of `handoff-version/subtask-result-v2` |
| receipts, both pinning that version (clean) | `receipt_handoff_version_sha256s` | that digest, twice |
| a receipt pinning the superseded version (defective 2) | `receipt_handoff_version_sha256s` | that digest plus SHA-256 of `handoff-version/subtask-result-v1` |
| the full acceptance sequence (clean, defective 2) | `transition_names` | `PROPOSED, ACCEPTED, COMMITTED, EXECUTED, SHIPPED, VERIFIED` |
| shipped with no verification recorded (defective 1) | `transition_names` | the first five only |
| when each transition happened | `transition_times` | `0..5`, or `0..4` for defective 1 |

## Where judgment entered

1. **Instance constructed, taxonomy cited.** As with incident 11, MAST publishes
   a taxonomy and aggregate rates, not per-incident public records. The handoff
   scenario is the corpus author's instantiation of FM-3.1/3.2/3.3. The
   Anthropic §3.4 companion figures (57/886 sessions) are cited in `SOURCE.md`
   as a second population showing the same shape, not as the source of this
   record's values.
2. **The six-name sequence is the artifact's vocabulary, not MAST's.** `OBL-27`
   fixes `PROPOSED, ACCEPTED, COMMITTED, EXECUTED, SHIPPED, VERIFIED` as the
   required transition names. Mapping "the agent reported the task verified when
   it was not" onto "a required transition name is missing" is a corpus-author
   reading; a system that emits a `VERIFIED` transition it did not earn would
   pass this limb, and RR would classify it `VALID` on the strength of the
   host's own attestation (H1).
3. **Defective record 1 shortens both arrays together.** `transition_times` is
   truncated to five so the `COUNT_NE_PATH` limb does not fire first. That is a
   deliberate choice to make the missing-verification limb the one that
   classifies; a real record with five names and six times would classify
   `MALFORMED_OR_BOUNDARY` instead, for a different reason.
4. **Transition times are `0..5`.** Strictly increasing integers, order only;
   nothing about elapsed time is represented.
5. **Two receipts, not one.** The clean record carries two receipts so the
   defective variant can change exactly one of them, isolating the mismatch.
   The count is a corpus-author choice.
6. **Carrier envelope.** Request envelope verbatim from the frozen fixture entry
   named in `expected.json`; only `decision_input.facts` is incident-derived.

## Preflight lane — `abstain_uncalibrated`

Native evidence in family `HANDOFF_LIFECYCLE`; no portable calibration rule
exists, so the preflight returns `INSUFFICIENT_EVIDENCE` with
`PREFLIGHT_FAMILY_UNCALIBRATED`. Abstention, not a pass and not a detection.

## What a green replay demonstrates

RR classifies a handoff missing its verification transition as
`BINDING_OR_CONFLICT`, a handoff whose receipts do not all pin the version being
accepted as `OMISSION_OR_INCOMPLETE`, and the complete version-consistent
sequence as `VALID`.

## What it does not demonstrate

That RR would have altered any multi-agent failure; that a `VERIFIED` transition
was earned (RR classifies the record, not the work); that this scenario occurs
in the MAST traces.

## Reproduce

```
python -B replay_incidents.py --incident 12-mast-verification-without-basis --verbose
```
