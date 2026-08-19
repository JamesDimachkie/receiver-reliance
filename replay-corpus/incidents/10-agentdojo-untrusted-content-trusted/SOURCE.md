# Source — AgentDojo: tool-returned content treated as an instruction source

**Public sources.**

- AgentDojo repository: <https://github.com/ethz-spylab/agentdojo>
  (core: <https://github.com/ethz-spylab/agentdojo-core>), project site
  <https://agentdojo.spylab.ai>.
- Paper: Debenedetti, Zhang, Balunović, Beurer-Kellner, Fischer, Tramèr,
  *AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and
  Defenses for LLM Agents*, <https://arxiv.org/abs/2406.13352>.
- Banking-suite injection tasks:
  `src/agentdojo/default_suites/v1/banking/injection_tasks.py`.

**Fetched 2026-08-18.** Content read as data.

## What the public source describes

The paper's framing is that agents are vulnerable to prompt-injection attacks
"where data returned by external tools hijacks the agent to execute malicious
tasks" (abstract). The benchmark delivers attacks through exactly that channel:
fields inside records the agent's own tools return — a transaction note, a
calendar entry, a document body — carry text that the agent then follows.

In the banking suite, the injected instruction rides inside data returned by
transaction-listing tools, and the hijacked behaviours include `send_money`,
`update_scheduled_transaction`, and `update_password` calls the user never
asked for. The benchmark's published composition is 97 user tasks and 629
security test cases across suites including banking, email/workspace, Slack, and
travel.

## Why this is checkable

The structural precondition of every one of these attacks is stated by the
benchmark's own design: content that arrived through a tool was acted on as
though it were a trusted instruction source, without a passing validation for
that role. That precondition is a bookkeeping fact about the receiving system,
independent of what any particular injection said.

## Boundary this source forces

Prompt injection is listed in the workspace analytical mapping's "explicitly out
of RR's reach" section. This incident does not contradict that. See
`METHOD.md`, item 1.
