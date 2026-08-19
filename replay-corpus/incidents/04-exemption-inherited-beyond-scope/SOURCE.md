# Source — exemption inherited far beyond its approved scope

**Public source.** Anthropic, *Risk Report: August 2026*, public edition,
<https://www.anthropic.com/aug-2026-risk-report>. Published 2026-08-14; coverage
period 2026-02-24 through 2026-07-15. The incident sits in Appendix 6.5, p.181.

**Section pointer provenance.** Pointer from the unpublished workspace analytical mapping (entry 1).
Re-check against the published report.

## What the public record describes

An enterprise customer held a bioclassifier exemption approved for a defined
subset of its workforce. When the organisation's seat allocation expanded, the
exemption was automatically inherited by roughly four times the approved number
of seats, because the exemption was scoped to the organisation rather than to
users or roles. Those unintended seats were the majority of all exemption seats
granted. A scoping effort was already open but stalled awaiting tooling.

Anthropic's own named root-cause fix was to scope exemptions to individual users
or roles rather than to whole organisations.

## Why this is checkable

The failure is a propagation failure with an observable shape: an authorisation
issued to one principal set was carried, unchanged in kind, to a strictly larger
principal set. Both sets are stated. No judgement about the exemption's subject
matter enters the mapping.

## Note on the named fix

The report's stated fix — bind grants to users or roles, never to a group whose
membership can expand under you — is the same rule the receiver-reliance
artifact encodes as non-transitive, receiver-local grants. That convergence is
worth noting and is not evidence of anything: two designs arriving at the same
rule is not a measurement of either.
