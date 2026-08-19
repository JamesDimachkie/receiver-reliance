# Source — exclusion filters silently failing across model generations

**Public source.** Anthropic, *Risk Report: August 2026*, public edition,
<https://www.anthropic.com/aug-2026-risk-report>. Published 2026-08-14; coverage
period 2026-02-24 through 2026-07-15. The incident sits in §5.2.6, p.168.

**Section pointer provenance.** Pointer from the unpublished workspace analytical mapping (entry 6).
Re-check against the published report.

## What the public record describes

Alignment-faking transcripts re-entered production training corpora. Several
causes compounded: some forks of the material predated the canary strings used
to identify it, the semantic filter's reference corpus was wrong, the filters
were misconfigured across several model generations without anyone noticing, and
teams miscommunicated about what the filtering pipeline was meant to do. All
production models with a knowledge cutoff after December 2024 are now suspected
to have trained on some of these transcripts.

## Why this is checkable

The claim under examination is a *closure* claim: "this material was filtered
out." The record states two things that make it checkable — the declared basis
for the claim (the canary-string filter and the semantic filter's reference
corpus) and at least one resource that influenced the corpus but was not covered
by that basis (forks predating the canary strings). Whether the resulting model
is harmed is not needed; the mismatch between influencing resources and declared
basis is the observable.

## Neighbouring limb in a different section

The same "absence of a signal read as clean" shape appears in §4.5.8.2.2 (see
incident `03-internal-flag-external-traffic`, where flag logging was disabled so
nothing propagated to review) and in §5.2.3's believed-fixed / found-again cycle
on chain-of-thought leakage. This incident is adapted because its declared basis
and its uncovered influencing resource are both stated plainly.
