# MCP gate — the preflight and the audited decision, over a wire

A stdio MCP server that puts one deterministic, auditable reliance decision in
front of a record an agent received. It is the repository's first surface built
for a consumer outside it, and it consumes the artifact exactly the way that
consumer would: through the package API and the shipped preflight, not through
engine internals.

The parent lane is the portable preflight (`../README.md`) and its three-status
law governs here unchanged. This directory adds no fourth status and re-derives
none of its rules.

## What it is

One pipeline, per checked record:

```text
MCP tool-call result
  -> mappers/                        native evidence record + fact profile
  -> adapters.preflight              READY | REJECTED_INVALID | INSUFFICIENT_EVIDENCE
  -> receiver_reliance.decide_audited   only when READY
  -> receiver_reliance.verify_audit_seal   the envelope is checked, not trusted
  -> compact verdict + one JSONL audit line
```

Three tools. `rr_gate_check` classifies one received record, appends the full
audited decision to the audit log, and returns a compact verdict.
`rr_gate_batch` classifies a list of received records in one call: each item
runs the identical per-record pipeline — its own preflight, its own audited
decision, its own content-addressed decision id — with order preserved, and a
failing item reported at its index without affecting its siblings. Every item
that reaches a decision appends its own audit line; an item that raised was
not judged and appends none. The batch-level `enforcement_action` aggregates:
BLOCK when any item blocked or any item errored (not judged may not read as a
pass), while each item keeps its own per-item value. Batching reduces the
caller's per-record wire and loop cost (for a host whose tool calls are model
turns) and changes nothing about any decision; it is bounded at 64 items per
call, the same bounded-ingest posture every peripheral surface carries. `rr_gate_explain` takes a decision
id from that log, re-verifies that envelope's seal from the bytes on disk, and
returns the witness trace, the first-match map, and the frozen decision-table
predicate that produced the class.

## The verdict vocabulary, and where each value comes from

The gate reports three verdicts. They are not a fourth preflight status: each one
is a restatement of a preflight status or an audited class, and the underlying
value is always reported beside it.

| Verdict | Reached from | Meaning |
|---|---|---|
| `NO_FINDING` | `READY`, then audited class `VALID` | The engine found no defect on the one obligation checked, from the facts the caller supplied. Not an authorization, and not a statement about any other obligation. |
| `HOLD` | `REJECTED_INVALID`, or an audited defect class, or `AUDIT_INCOMPLETE`, or `PROTOCOL_ERROR`, or a seal that did not recompute | Either a defect was detected, or no decision could be certified. Fail-closed: the two outcomes are distinguished in `audited_behavior_class` and `reason`, never merged into a pass. |
| `ABSTAIN` | `INSUFFICIENT_EVIDENCE` | The record does not carry the obligation's semantics, so the mapper declined. Abstention is the designed outcome. Forcing inapplicable mappings measured 133 false holds among 390 clean records in `proof/RESULTS.md`; declining measured 0% with no detection loss. |

`audited_behavior_class` is a closed **six**-value set, not four: the frozen law
assigns four, and the audited surface adds `AUDIT_INCOMPLETE` and
`PROTOCOL_ERROR`, neither of which is a class the law assigns
([TRUST_MODEL.md](../../TRUST_MODEL.md)). This gate handles all six, and
`test_mcp_gate.py` fails if a seventh appears or if either surface-added value
ever reads as a finding about the record.

## Running it

Requires CPython 3.12+. Stdlib only, no packages, no build step. `-B` keeps
bytecode out of the artifact tree.

```text
python -B adapters/mcp/rr_mcp_gate.py --calibrate    112/112 pack entries reproduce
python -B adapters/mcp/demo.py                       five scenarios over real MCP stdio
python -B adapters/mcp/test_mcp_gate.py              checks=129 failures=0
```

Calibration is the gate on the request side of the boundary. The adapter builds
its engine request by templating a shipped conformance fixture entry —
substituting only `decision_input.facts` and the request ids, and recomputing
every bound digest — and `--calibrate` proves that recomputation reproduces all
112 entries of `B1_PRIMARY_BASELINE_SEMANTIC_FIXTURES_0_2` byte-exactly before
any of a caller's facts are substituted into one. If it does not print 112/112,
the request being sent is not the shape the conformance suite validated.

Wiring it into a client is a config block. `mcpServers` is the near-universal
shape; adjust the key name if the client differs.

```json
{
  "mcpServers": {
    "rr-gate": {
      "command": "python3.12",
      "args": ["-B", "/path/to/receiver-reliance/adapters/mcp/rr_mcp_gate.py"],
      "env": {
        "RR_MCP_GATE_AUDIT_LOG": "/var/log/rr/rr_mcp_audit.jsonl"
      }
    }
  }
}
```

`RR_HOME` is optional and defaults to this checkout. Set it when the server file
is vendored away from the artifact it decides against. `RR_MCP_GATE_AUDIT_LOG`
defaults to the host's temporary directory, which is fine for a demo and wrong
for anything you intend to keep: retaining the log, and binding it to the action
actually taken, is H5 and stays with the host.

Then call `rr_gate_check` on one record actually relied on:

```json
{
  "call": {
    "server": "docs",
    "tool": "get_record",
    "record_reference": {
      "requested": "res://tickets/T-42",
      "returned": "res://tickets/T-42",
      "declared_revision_sha256": "9F86D0…",
      "revision_digest_domain": "canonical-json:/structuredContent/record"
    }
  },
  "result": { "isError": false, "content": [], "structuredContent": {} },
  "reliance": { "intent": "ACT_ON_RECORD", "description": "why you are relying on it" }
}
```

`requested` is the only field required to get a decision. Everything else narrows
what can be checked; omitting a field never fabricates it, and every omission
comes back in `mapper_notes`.

## What it consumes, and what it deliberately does not

Everything this adapter takes from the rest of the repository comes through a
surface the root README's "The supported surface" section pins:

| Surface | Used for |
|---|---|
| `receiver_reliance.decide_audited` | the one supported evidentiary route |
| `receiver_reliance.verify_audit_seal` | checking every envelope before reporting it |
| `receiver_reliance.AUDIT_FORMAT` | the envelope format the verdict names |
| `adapters.preflight` and the three statuses | eligibility, detection, abstention |
| `adapters.portable_preflight.canonical_json_bytes` | bounded canonicalization for evidence and request digests |
| `portability/strict_ingest.load_safe` | every byte read that this process did not produce |

The three engine-internal handles on `grounded-0_4/rr_api.py` — `b1`,
`pcb_runner`, `authority_surface` — are reachable by construction and are not
used here. Two consequences are worth stating rather than leaving to a reader:

- **Request digests are recomputed with the `adapters` canonicalizer, not the
  engine's `jcs_bytes`.** Calibration proves the two agree byte-exactly over all
  112 shipped entries. If they ever diverged, the failure could not be a wrong
  classification: the engine re-derives the bound digests itself, so a mismatch
  returns `PROTOCOL_ERROR` at exit code 2 rather than a decision. The suite pins
  that behavior with a deliberately corrupted request.
- **The predicate `rr_gate_explain` shows is read from the two published contract
  documents and bound to the decision.** Each contract's SHA-256 is compared
  against the `governing_authorities` member the envelope itself recorded, and
  the result is reported as `matches_decision`, `differs_from_decision`, or
  `unbound`. What is displayed is therefore the predicate that governed *that*
  decision, not whichever bytes happen to be on disk now.

One control a host may already have turned on does **not** sit in this path.
[`deployment/`](../../deployment/README.md)'s admission profile is a pre-engine
bound over raw request *bytes*, applied by a host at its own transport seam. This
gate hands `decide_audited` a Python object it built from a fixture template, so
an operator who set `RR_ADMISSION_MAX_REQUEST_BYTES` has bounded their own
transport and has not bounded this one. Nothing here is oversized — the templated
requests are a few kilobytes — but a host should not read that variable as
covering this seam.

## The audit line

Every decision — including preflight rejections and abstentions — appends one
JSONL line carrying the full audited decision: the `B1-AUDITED-DECISION-0.4.2`
envelope with its self-zero seal, the matched-predicate witness trace, the
per-class first-match map, the derived record references, closure findings, and
the six `governing_authorities` digests naming the exact policy bytes that
governed it — closure policy, authority register, engine capabilities, engine
runner, and both decision-table contracts (`ERRATA.md` E8, E18).

Two different fact profiles can never share an audit seal (HOST_OBLIGATIONS H5;
pinned in `test_mcp_gate.py`). Decision ids are content-addressed, so identical
evidence yields an identical id and the log may hold duplicates;
`rr_gate_explain` returns the most recent with `occurrences_in_log`.

No payload storage, no network. The native evidence record and the audit log
carry identities, digests, labels and the caller's stated intent. Result payload
content is never copied into either. The server is local stdio and opens no
sockets.

## Observe-only by default

The server classifies and logs. It does not block. `RR_MCP_GATE_ENFORCE=1`
exists, ships off, and only ever escalates a `HOLD` — and even then, what
"blocked" means in a given stack is that stack's policy, not this server's.
`HOLD` is a classification. Whether it stops an agent, annotates a context, opens
a review, or does nothing is a decision this server deliberately does not make.

## What stays with the host

The adapter makes [HOST_OBLIGATIONS.md](../../HOST_OBLIGATIONS.md) H1–H6 easier
to satisfy. It absorbs none of them.

| | Obligation | Still the host's, specifically |
|---|---|---|
| **H1** | State truthfulness | Every identity, digest, and lookup outcome passed in is the host's attestation. The engine detects internally inconsistent attestations, not false ones. A deceptive attester defeats this by construction. |
| **H2** | Atomicity and replay | The gate holds no state and cannot serialize concurrent calls. Single-use semantics live in the host's store transaction. |
| **H3** | Derive facts, never assert conclusions | The mapper derives what it can observe from the call and the result, and discloses what it dropped. How the requested reference was learned, and how the digest was produced, are the host's derivations to audit. |
| **H4** | Applicability calibration | The mapper declares its native precondition and abstains otherwise. Extending it to another shape or obligation means meeting the promotion gate in `mappers/DESIGN.md`, receipt included. |
| **H5** | Input binding and transcripts | Satisfied for decisions made here: `decide_audited` binds request bytes, decision-input digest, and the governing policy digests. Retaining the log, and binding it to the action actually taken, is the host's. |
| **H6** | Effects | The gate never executes, mediates, or observes effects. Enforcement, reconciliation of executed effects against decisions, and what a `HOLD` does are all the host's. |

## What "calibration" measured, and what it did not

`--calibrate` measures one thing: that this adapter's envelope construction
reproduces every shipped pack entry byte-exactly. It is a statement about request
shape. It is **not** a measurement of mapping accuracy, detection rate, or false
holds on a host's own records.

The applicability result the abstention design rests on — 18/18 detection at zero
new false holds — is `proof/RESULTS.md` and `adapters/OUTCOME.md`, measured over
the synthetic 408-record corpus, not over MCP traffic. The mapper here covers one
family and one obligation: `REF` / OBL-02, exact reference resolution. Everything
else abstains as `PREFLIGHT_FAMILY_UNCALIBRATED`. Until 2026-08-20 no measurement
existed for MCP traffic of any kind; on that date the maintainer ran the first
one — twelve tool results captured from three locally-run open-source reference
servers and classified through this gate, retained as harness-side internal
evidence, not published in this repository. It measured presence of integrity
semantics on the transport, not detection, accuracy, or efficacy; the mapper's
coverage statement above is unchanged by it.

## What this does not claim

Inherited from [TRUST_MODEL.md](../../TRUST_MODEL.md), which remains canonical.
Nothing here adds a guarantee.

- **No security claim.** This is not a security control and not a security audit.
  It classifies attested facts; it does not authenticate the attester.
- **No efficacy claim.** The rule-value experiment has not run. Nothing here
  shows that gating records improves handoff outcomes.
- **No novelty, interoperability, or external-standard claim.** The suite tests
  conformance to this artifact's own contract only. MCP revision coverage
  (`2025-06-18`, `2025-03-26`, `2024-11-05`) is what this server negotiates, not
  a compatibility guarantee against any particular client.
- **`READY` is eligibility, never a pass**, and `NO_FINDING` is a classification,
  never an authorization.
- **A verified seal proves integrity relative to the repository commit, not
  provenance.** Nothing is signed; there is no key infrastructure. `True` from
  `verify_audit_seal` means these envelope bytes are internally intact and were
  sealed by something implementing this contract — not who produced it, when, or
  that the attested facts were true.
- **A receipt is not evidence that the host producing it was sound.** The
  artifact demonstrates this against itself: a forged `git` earlier on `PATH`
  made a hygiene verifier report `HYGIENE_PASS` with a planted modification still
  on disk.

## Before a host depends on this

[TRUST_MODEL.md](../../TRUST_MODEL.md) maintains this artifact as a research
artifact on a zero-external-consumer census, and records that **the first
external consumer — or any embedding where handoff senders are adversarial to the
receiver's own tooling — promotes the deferred hardening set to blocking work
before that embedding ships**. [ADOPTION.md](../../ADOPTION.md) states the same
trigger once and names the rows: A4 (one bounded ingest law on every peripheral
surface), A5 (no harness resolving a tool by bare name from the ambient `PATH`)
and A6 (process-tree and deadline totality in the long-lived harnesses). All
three closed on 2026-08-19, so the trigger now finds that set satisfied in
advance. What a host owes is re-running their proof suites against the bytes it
actually embeds — `portability/test_strict_ingest.py`,
`portability/test_pinned_tools.py`, `perf/sidecar/test_supervision_bounds.py` —
not waiting on open work.

Committing this directory does not fire that trigger; wiring it into a host does,
and an MCP gate's whole premise is that the sender of the record is not trusted
by the receiver's tooling. Read those two pages before depending on this in
anything that matters.

## Extending it

Another exchanged shape means another mapper, and mappers are cheap to write and
expensive to earn. [mappers/DESIGN.md](mappers/DESIGN.md) carries the four laws
every mapper obeys, full designs for Microsoft Agent Framework objects and
A2A-style messages, and the promotion gate from
[../CALIBRATION.md](../CALIBRATION.md) — the part that matters is item 7, a
paired receipt keeping invalid and insufficient results separate against held-out
truth. Without one you have a plausible mapping, not a calibrated one.
