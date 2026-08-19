# Method — 08-legacy-instructions-child-agents

**Demonstrable claim.** RR classifies the adapted
`defective-widened-child-authority` record as `OMISSION_OR_INCOMPLETE` /
`UNRESOLVED` and the clean twin as `VALID` / `SATISFIED`.

## Obligation selected

`OBL-10` — *"Enforce least authority and block independent-principal elevation
across principal, class, capability, target, effect, subject, purpose, and
scope."* Operation handle `OPR_38663FABE27CFF68828572D4`.

Decision-table limb that fires: `NOT_SUBSET` of `/facts/delegated_effect_ids`
in `/facts/issuer_effect_ids`. Child sessions carrying effect classes the issuer
never held is exactly a delegated effect set that is not contained in the
issuing one.

## Relationship to incident 04

`04-exemption-inherited-beyond-scope` uses `OBL-25` and widens the **principal**
set; this one uses `OBL-10` and widens the **effect** set. The two incidents
were deliberately built on different limbs so that the corpus does not
demonstrate the same subset check twice under two names.

## The adaptation

| Incident element | Fact field | Value |
|---|---|---|
| the parent session's grant | `issuer_effect_ids` | `["EFFECT_READ_CLUSTER_JOBS"]` |
| what the child sessions carried (clean) | `delegated_effect_ids` | the same single member |
| what the child sessions carried (defective) | `delegated_effect_ids` | plus `EFFECT_DELETE_CLUSTER_JOBS` and `EFFECT_SKIP_PERMISSION_PROMPTS` |
| the cluster | `issuer_target_ids` / `delegated_target_ids` | `["TARGET_SENSITIVE_CLUSTER"]` on both sides |
| the scope asked for and granted | `requested_scope_ids` / `granted_scope_ids` | `["SCOPE_SENSITIVE_CLUSTER_READ"]` on both sides |
| the parent agent session | `principal_id` | `PRINCIPAL_PARENT_AGENT_SESSION` |

## Where judgment entered

1. **`--dangerously-skip-permissions` is modelled as an effect class.** The flag
   is a runtime setting, not an effect in the artifact's vocabulary. Encoding it
   as `EFFECT_SKIP_PERMISSION_PROMPTS` — something the issuer's grant would have
   to carry for the delegation to be contained — is a corpus-author modelling
   choice, and it is the most contestable step in this incident.
2. **Two extra effect members, not one.** The defective record widens by both
   deletion and permission bypass because the public record names both. Either
   alone produces the same class, so the record does not isolate which one.
3. **Target and scope sets are held constant** so the effect limb is the only
   one that fires. In the real incident the target arguably widened too; the
   corpus does not represent that.
4. **The stale-basis story is not represented.** The fit document locates RR's
   contribution here in standing-basis staleness — a superseded instruction
   governing a new act, classified as wrong-standing. That would need the
   standing basis and policy-version digests, which the public record does not
   supply, so the corpus did not build it. `OBL-10` was mapped instead because
   the delegation delta is stated. This is a substitution, not a match, and it
   means the corpus does **not** make the fit document's entry-7 mapping
   executable.
5. **The monitoring gap and the deleted jobs are not represented.** Neither
   enters the classification.
6. **Carrier envelope.** Request envelope verbatim from the frozen fixture entry
   named in `expected.json`; only `decision_input.facts` is incident-derived.

## Preflight lane — `abstain_uncalibrated`

Native evidence in family `DELEGATION`; no portable calibration rule exists, so
the preflight returns `INSUFFICIENT_EVIDENCE` with
`PREFLIGHT_FAMILY_UNCALIBRATED`. Abstention, not a pass and not a detection.

## What a green replay demonstrates

RR classifies a delegation whose effect set exceeds the issuer's as
`OMISSION_OR_INCOMPLETE`, and returns `VALID` when the delegated sets are
contained in the issuing ones.

## What it does not demonstrate

That RR would have altered the real incident; the fit document's stale-standing-
basis mapping, which this corpus does not implement; anything about the
employee, their intent, or the deleted jobs.

## Reproduce

```
python -B replay_incidents.py --incident 08-legacy-instructions-child-agents --verbose
```
