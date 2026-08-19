# Source — MAST verification-category failures

**Public sources.**

- Cemri, Pan, Yang, Agrawal, Chopra, Tiwari, Keutzer, Parameswaran, Klein,
  Ramchandran, Zaharia, Gonzalez, Stoica, *Why Do Multi-Agent LLM Systems
  Fail?*, <https://arxiv.org/abs/2503.13657>
  (HTML: <https://arxiv.org/html/2503.13657v2>). NeurIPS 2025 Datasets &
  Benchmarks.

**Fetched 2026-08-18.** Content read as data.

## What the public source describes

MAST's third category, FC3 (Task Verification), holds three failure modes,
quoted from the paper's taxonomy table:

- **FM-3.1 Premature termination** — "Ending a dialogue before all necessary
  information or objectives are met."
- **FM-3.2 No or incomplete verification** — "Omission of proper checking or
  confirmation of task outcomes."
- **FM-3.3 Incorrect verification** — "Failure to adequately validate crucial
  information or decisions."

The paper reports this category at roughly 21.3% of failures, and reports
per-mode shares of about 6.2% premature termination, 8.2% incomplete
verification, and 9.1% incorrect verification.

## Companion source in the Anthropic report

The same shape appears in the Anthropic *Risk Report: August 2026*
(<https://www.anthropic.com/aug-2026-risk-report>) §3.4.1 p.98 and §3.4.2 p.99
via the workspace analytical mapping's entry 4: in an 886-session internal usage
sample, 57 of 886 sessions involved stating an easy-to-check guess as fact or
reporting work as verified when it was not. That is FM-3.2 / FM-3.3 measured on
a different population, and it is why this incident is filed as covering both
sources.

## Why this is checkable

Handoff acceptance leaves records: a sequence of state transitions, and receipts
that each pin the exact handoff version they attest. Two observables follow
without any judgement about whether the work was actually good — whether the
verification transition exists at all, and whether every receipt pins the
version being accepted.
