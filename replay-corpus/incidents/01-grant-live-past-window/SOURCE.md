# Source — access grant left live past its window

**Public source.** Anthropic, *Risk Report: August 2026*, public edition,
<https://www.anthropic.com/aug-2026-risk-report>. Published 2026-08-14; coverage
period 2026-02-24 through 2026-07-15. The incident sits in Appendix 6.5, p.179.

**Section pointer provenance.** The appendix/page pointer is taken from the
unpublished workspace analytical mapping (entry 2),
which was written against the public edition. A reader re-checking this corpus
should confirm the pointer against the published report itself; the corpus
author did not re-paginate it.

## What the public record describes

Helpful-only model access was granted to two external CBRN testing
organisations for predeployment testing. The access stayed live for
approximately two weeks after the model launched, past the point the grant was
intended to cover. Deprovisioning was a manual step, and revocation was not
executed at the intended time.

Two distinct defects are on the record:

1. the authorisation window ended at launch, and use continued after it; and
2. revocation was not executed — nothing in the record establishes that
   revocation state was consulted before continued use.

## Why this is checkable

The two failure limbs are stated as facts about the grant's own lifecycle
(window boundary, revocation execution), not as inferences about model
behaviour. That is what makes the record adaptable to a fact profile: the
adaptation needs only a validity interval, an invocation instant, and whether
revocation state was consulted. Nothing about model capability, intent, or harm
enters the mapping.

## Related shipped material

`receiver-reliance/examples/handoff-unchecked-revocation.json` is one of the
three worked examples the artifact already ships, and it is the same defect
shape as limb 2 above. This incident's `defective-revocation-unchecked` record
is an incident-derived instance of that shape, not a copy of the shipped file.
