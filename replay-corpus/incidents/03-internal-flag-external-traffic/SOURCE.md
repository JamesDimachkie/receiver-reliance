# Source — internal-only flag applied to external traffic

**Public source.** Anthropic, *Risk Report: August 2026*, public edition,
<https://www.anthropic.com/aug-2026-risk-report>. Published 2026-08-14; coverage
period 2026-02-24 through 2026-07-15. The incident sits in §4.5.8.2.2,
pp.148–149.

**Section pointer provenance.** Pointer from the unpublished workspace analytical mapping (entry 3).
Re-check against the published report.

## What the public record describes

From May 2025 to April 2026, all human-feedback vendor traffic — roughly 50,000
contractors and about 133 million exchanges — ran without blocking biological
classifiers, because a flag intended only for internal use governed that
traffic. The same flag also disabled flag logging, so nothing propagated to
review: the absence of alerts read as clean. The report states the gap was
remediated and no evidence of concerning misuse was found. Per the fit
document, this incident raised the report's overall chemical/biological risk
assessment and prompted a stated concern that similar unknown gaps exist.

**Independent corroboration.** Press coverage of the report's publication
independently reports the same figures — ~50,000 contractors, ~133M exchanges,
May 2025 through April 2026, human-feedback vendor traffic running without the
blocking biological classifiers (e.g. SiliconANGLE, 2026-08-14,
<https://siliconangle.com/2026/08/14/anthropic-details-unreleased-model-2-new-alignment-concerns-latest-ai-risk-report/>).
That makes this incident's core facts checkable without access to the report
itself.

## Why this is checkable

Two declared-versus-actual pairs are stated as fact: the flag *declared* an
internal audience, and the traffic it *actually* governed was external vendor
workforce traffic; the flag *declared* the internal evaluation configuration,
and the configuration it actually produced had the blocking classifiers off.
Both pairs are observable without any judgement about the traffic's content.

## The second limb — silence read as clean

The flag also disabled logging, so the absence of alerts was taken as evidence
of a clean state. That limb is a closure-discipline failure rather than a
declared-versus-actual mismatch, and it is adapted separately in incident
`05-exclusion-filter-false-clean`, which has the crisper public shape for it.
This incident adapts the declared-versus-actual limb only.
