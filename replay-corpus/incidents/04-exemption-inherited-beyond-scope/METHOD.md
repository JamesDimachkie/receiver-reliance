# Method — 04-exemption-inherited-beyond-scope

**Demonstrable claim.** RR classifies the adapted
`defective-org-wide-inheritance` record as `OMISSION_OR_INCOMPLETE` /
`UNRESOLVED` and the clean twin as `VALID` / `SATISFIED`.

## Obligation selected

`OBL-25` — *"Preserve non-malleable origin, principal, and action-class
bindings across every authorization propagation; copying, transformation, or
handoff cannot widen authority."* Operation handle
`OPR_165CED459B7901D4CA3E3B2A`.

Decision-table limb that fires: `NOT_SUBSET` of
`/facts/propagated_principal_ids` in `/facts/issuer_principal_ids`. Automatic
inheritance by seats the issuer never named is exactly a propagated principal
set that is not a subset of the issuing one.

## The adaptation

| Incident element | Fact field | Value |
|---|---|---|
| the approved workforce subset | `issuer_principal_ids` | `["PRINCIPAL_APPROVED_WORKFORCE_SUBSET"]` |
| seats holding the exemption (clean) | `propagated_principal_ids` | same single member |
| seats holding it after allocation expanded (defective) | `propagated_principal_ids` | approved subset **plus** `PRINCIPAL_EXPANDED_ALLOCATION_SEATS` |
| what the exemption permits | `issuer_action_class_ids` / `propagated_action_class_ids` | `["ACTION_BIOCLASSIFIER_EXEMPT_USE"]`, unchanged on both sides |
| the exemption's origin binding | `origin_binding_sha256` | SHA-256 of `exemption-origin-binding/approved-subset` |

## Where judgment entered

1. **"Roughly 4×" collapses to one extra member.** The classification turns on
   set inclusion, not cardinality: one unapproved principal and a thousand
   produce the same class. The corpus uses one, which understates the incident's
   scale and changes nothing mechanically. It also means the corpus cannot
   demonstrate anything about magnitude.
2. **Principals are opaque identifiers.** `PRINCIPAL_APPROVED_WORKFORCE_SUBSET`
   and `PRINCIPAL_EXPANDED_ALLOCATION_SEATS` are labels chosen by the corpus
   author. The public record does not publish the customer's role structure.
3. **The action class is held constant.** The incident widened *who* held the
   exemption, not *what* it permitted, so `propagated_action_class_ids` matches
   the issuer's on both records and that disjunct never fires. A different
   incident (see `08-legacy-instructions-child-agents`) exercises the effect-set
   limb.
4. **"Automatically inherited" is not modelled as a mechanism.** The adaptation
   records only the end state — a wider propagated set — not the inheritance
   machinery that produced it. Classification does not depend on the mechanism.
5. **`origin_binding_sha256` is required and not in the public record.** It is a
   hash of an ASCII label, present so the `BINDING_OR_CONFLICT` limb (absent
   origin binding) does not fire. Declared fabrication under H3.
6. **Carrier envelope.** Request envelope verbatim from the frozen fixture entry
   named in `expected.json`; only `decision_input.facts` is incident-derived.

## Preflight lane — `abstain_uncalibrated`

Native evidence in family `AUTHORIZATION_PROPAGATION`; no portable calibration
rule exists, so the preflight returns `INSUFFICIENT_EVIDENCE` with
`PREFLIGHT_FAMILY_UNCALIBRATED`. Abstention, not a pass and not a detection.
The engine leg runs anyway, as a demonstration rather than a compliant
integration.

## What a green replay demonstrates

RR classifies a propagation whose principal set exceeds the issuer's as
`OMISSION_OR_INCOMPLETE`, and returns `VALID` when the propagated set is
contained in the issued one.

## What it does not demonstrate

That RR would have altered the real incident; that the profile is true of the
world (H1); anything about bioclassifier exemptions as a policy matter.

## Reproduce

```
python -B replay_incidents.py --incident 04-exemption-inherited-beyond-scope --verbose
```
