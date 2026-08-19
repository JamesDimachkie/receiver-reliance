# Source — safety parameter hand-copied from a superseded version

**Public source.** Anthropic, *Risk Report: August 2026*, public edition,
<https://www.anthropic.com/aug-2026-risk-report>. Published 2026-08-14; coverage
period 2026-02-24 through 2026-07-15. The incident sits in Appendix 6.5,
pp.179–180.

**Section pointer provenance.** The appendix/page pointer comes from the
unpublished workspace analytical mapping (entry 5).
Re-check it against the published report; the corpus author did not
re-paginate it.

## What the public record describes

A stage-1 probe threshold for a new classifier generation was set to the
previous classifier's numeric value — hand-copied rather than derived for the
new classifier. The copied value was too high for the new classifier. For about
five days, some traffic was neither forwarded to stage 2, nor blocked, nor
logged. The named remediation was to pair probe and threshold programmatically
instead of copying the number by hand.

## Why this is checkable

The failure is a *reference* failure with an observable shape: a configuration
record identified by name carried content from a superseded revision while the
identity it was cited under resolved to a different revision. Both sides of that
disagreement are observable without any judgement about classifier behaviour —
you can hash what the citing record claims and hash what is actually at the
cited identity.

## Related failure class in the same report

The fit document's entry 4 (§3.4.1 p.98, §3.4.2 p.99) records a neighbouring
class from the 886-session internal usage sample: corrections present in memory
or just given by the user, not followed. Both reduce to the same mechanical
question — does one record identity resolve to more than one revision? This
incident is the one with a crisper public shape, so it is the one adapted.
