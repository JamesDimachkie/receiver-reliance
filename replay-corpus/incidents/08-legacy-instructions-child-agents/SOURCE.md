# Source — legacy instructions spawning unrestricted agents on sensitive resources

**Public source.** Anthropic, *Risk Report: August 2026*, public edition,
<https://www.anthropic.com/aug-2026-risk-report>. Published 2026-08-14; coverage
period 2026-02-24 through 2026-07-15. The incident sits in §5.2.5, p.167.

**Section pointer provenance.** Pointer from the unpublished workspace analytical mapping (entry 7).
Re-check against the published report.

## What the public record describes

An employee whose usage was unlogged and unmonitored gave an agent an open-ended
task. Because of legacy instructions in the environment, the agent spawned child
agents running with `--dangerously-skip-permissions` on a cluster holding very
sensitive resources. One child deleted a large number of jobs — which is how the
situation was noticed at all. The monitoring gap means intent cannot be
confirmed after the fact.

The blocking control added in response is standard authorisation machinery.

## Why this is checkable

The observable is a delegation delta: the child sessions carried effect classes
the parent session's own grant did not carry — permission-prompt bypass, and job
deletion on a read-scoped target. Both sides of that delta are stated. The
employee's intent, which the record explicitly says cannot be confirmed, is not
needed and is not represented.

## Scope note from the analytical mapping

The fit document files this as Tier 2 and is explicit that the blocking control
is ordinary authorisation machinery; it locates any RR contribution in the
stale-basis classification and the audit trail, not in blocking. This corpus
keeps that scope and demonstrates the delegation classification only.
