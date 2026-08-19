# Source — MAST task derailment / disobeying task specification

**Public sources.**

- Mert Cemri, Melissa Z. Pan, Shuyi Yang, Lakshya A. Agrawal, Bhavya Chopra,
  Rishabh Tiwari, Kurt Keutzer, Aditya Parameswaran, Dan Klein, Kannan
  Ramchandran, Matei Zaharia, Joseph E. Gonzalez, Ion Stoica, *Why Do
  Multi-Agent LLM Systems Fail?*, <https://arxiv.org/abs/2503.13657>
  (HTML: <https://arxiv.org/html/2503.13657v2>). NeurIPS 2025 Datasets &
  Benchmarks.

**Fetched 2026-08-18.** Content read as data.

## What the public source describes

The paper introduces MAST, described in the abstract as the first Multi-Agent
System Failure Taxonomy, with 14 failure modes in 3 categories, built from over
1,600 annotated execution traces across 7 multi-agent frameworks, with six
expert annotators reaching a Cohen's kappa of 0.88.

The two modes this incident adapts, quoted from the paper's taxonomy table:

- **FM-1.1 Disobey task specification** — "Failure to adhere to the specified
  constraints or requirements of a given task" (category FC1, Specification
  Issues).
- **FM-2.3 Task derailment** — "Deviation from the intended objective or focus
  of a given task, potentially resulting in irrelevant actions" (category FC2,
  Inter-Agent Misalignment).

The paper reports the category shares as roughly 41.8% specification and system
design, 36.9% inter-agent misalignment, and 21.3% task verification and
termination.

## Why this is checkable

Both modes have an observable instance in code-producing agent systems: an agent
declares the scope it will work in, and the commit it produces touches paths
outside that declaration. The declaration and the changed-path set are both
recorded artifacts. No judgement about the agent's objective is required — only
a set comparison over opaque path strings.

## Note on the corpus's own instance

The paper's traces are not published as individual named incidents in a form
this corpus can cite record-by-record. What this incident adapts is the taxonomy
entry, instantiated in a scenario the corpus author constructed to have the
shape FM-1.1/FM-2.3 describe. That is disclosed in `METHOD.md` item 1 and is a
weaker provenance than the Anthropic and AgentDojo incidents in this corpus.
