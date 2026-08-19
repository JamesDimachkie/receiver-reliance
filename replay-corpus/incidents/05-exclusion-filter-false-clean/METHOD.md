# Method — 05-exclusion-filter-false-clean

**Demonstrable claim.** RR classifies the adapted
`defective-uncovered-influencing-fork` record as `OMISSION_OR_INCOMPLETE` /
`UNRESOLVED` and the clean twin as `VALID` / `SATISFIED`.

## Obligation selected

`OBL-11` — *"Close and isolate each action's declared support, authority,
policy, and influencing-resource basis."* Operation handle
`OPR_CE6168CADBF41CD7623A7D43`.

Decision-table limb that fires: `NOT_SUBSET` of
`/facts/influencing_resource_sha256s` in `/facts/declared_basis_sha256s`. A
resource that influenced the outcome but sits outside the declared basis makes
the closure incomplete, and the operation terminates as
`OMISSION_OR_INCOMPLETE` rather than passing on the strength of the declaration.

That is the mechanical form of the discipline the fit document names: "we
filtered it" is clean only relative to an attested basis; a resource outside the
basis leaves the claim unresolved rather than clean.

## The adaptation

| Incident element | Fact field | Value |
|---|---|---|
| the canary-string filter | member of `declared_basis_sha256s` | SHA-256 of `exclusion-basis/canary-string-filter` |
| the semantic filter's reference corpus | member of `declared_basis_sha256s` | SHA-256 of `exclusion-basis/semantic-filter-reference-corpus` |
| resources that actually influenced the corpus (clean) | `influencing_resource_sha256s` | the same two members |
| forks predating the canary strings (defective) | extra member of `influencing_resource_sha256s` | SHA-256 of `influencing-resource/pre-canary-transcript-fork` |
| the basis class the claim must carry | `required_basis_classes` | `["POLICY"]` |
| basis closed before the decision it governs | `closure_time` / `decision_frontier_time` | `0` / `1` |

## Where judgment entered

1. **Four compounding causes reduced to one.** The public record names four:
   pre-canary forks, a wrong semantic reference corpus, misconfiguration across
   generations, and cross-team miscommunication. The adaptation represents only
   the first, because only it has the shape `OBL-11` evaluates (a resource
   outside the declared basis). The other three are real parts of the incident
   that this record does not represent, and their absence is not a judgement
   that RR would classify them.
2. **`closure_time` and `decision_frontier_time` are invented.** The public
   record gives no closure instant. `0 < 1` is the minimal non-firing pair for
   the `MALFORMED_OR_BOUNDARY` limb. Declared fabrication under H3; a real host
   would derive both from its own ledger or abstain.
3. **`required_basis_classes = ["POLICY"]`** is likewise required by the
   operation and not stated in the incident. `POLICY` is the member the
   `BINDING_OR_CONFLICT` limb demands, so this value keeps that limb quiet.
4. **Digests stand for resources, not resources.** Hashes of ASCII labels; any
   distinct member outside the declared set produces the same class.
5. **"Suspected to have trained on some of these transcripts"** is a downstream
   consequence and is not represented. The record covers the closure claim only.
6. **Carrier envelope.** Request envelope verbatim from the frozen fixture entry
   named in `expected.json`; only `decision_input.facts` is incident-derived.

## Preflight lane — `abstain_uncalibrated`

Native evidence in family `CLOSURE_BASIS`; no portable calibration rule exists,
so the preflight returns `INSUFFICIENT_EVIDENCE` with
`PREFLIGHT_FAMILY_UNCALIBRATED`. Abstention, not a pass and not a detection.

## What a green replay demonstrates

RR classifies a closure claim with an influencing resource outside its declared
basis as `OMISSION_OR_INCOMPLETE`, and returns `VALID` when the influencing set
is contained in the declared basis.

## What it does not demonstrate

That RR would have altered the real incident; that the profile is true of the
world (H1); anything about training-data contamination as a subject.

## Reproduce

```
python -B replay_incidents.py --incident 05-exclusion-filter-false-clean --verbose
```
