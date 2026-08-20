# Mapping layer — design

A mapper turns one shape that agents actually exchange into two things the
receiver-reliance artifact accepts: a **closed native-evidence record** for the
shipped preflight, and a **host fact profile** (`RR-PORTABLE-FACT-PROFILE-1`) the
preflight re-derives and cross-checks.

Every mapper obeys the same four laws.

1. **Declare an observable native precondition, per obligation.** It is a
   predicate over the raw exchanged object. It may not depend on an expected
   verdict, a truth label, a filesystem or network lookup, the current directory,
   an environment variable, or a mutable runner (`adapters/CALIBRATION.md`,
   "Write an observable native precondition").
2. **Abstain when the precondition does not hold.** Emit the uncalibrated family
   `MCP_RESULT_UNCLASSIFIED` (or the shape's equivalent) and let the shipped
   preflight return `INSUFFICIENT_EVIDENCE`. The adapter adds no fourth state and
   owns no abstention logic of its own. Forcing an inapplicable mapping is the
   measured route to false holds: 133 among 390 clean records, 34.1%
   (`proof/RESULTS.md`, HOST_OBLIGATIONS H4).
3. **Never fabricate a fact value.** `fact_profile.fabricated_fields` is `[]` and
   the preflight rejects a profile that says otherwise. A field that cannot be
   derived is omitted and the omission is disclosed in `notes`.
4. **Let the preflight check the derivation.** The mapper derives facts exactly
   as the shipped family assessor does, so drift surfaces as
   `PREFLIGHT_PROFILE_FACT_MISMATCH` → `REJECTED_INVALID` at the boundary rather
   than as a confidently wrong decision. This is verified by mutation:
   `../test_mcp_gate.py`, check `preflight:tampered-profile-rejected`.

Contradiction is always checked before applicability
(`adapters/CALIBRATION.md`): a detectable contradiction is `REJECTED_INVALID`
even when other semantics are unavailable.

---

## Implemented: `mcp_tool_result.py` — MCP `CallToolResult` → REF / OBL-02

Status: **implemented and tested** (`../test_mcp_gate.py`, which reports
`rr-mcp-gate regression: checks=129 failures=0` — 103 before the 2026-08-20
`rr_gate_batch` section, 123 before that section's review-driven hardening
the same day — and is the suite the charter gate and `adapters/mcp/README.md`
pin). Earlier revisions of this line cited `../test_mcp_tool_result.py` at 76
checks; no such file exists at any commit in this repository — `git log
--all --follow` over that path returns nothing — and no program reports a
76-check figure. The mapper's cases were landed inside the aggregate suite,
which reports only its total, so 129 is the only count here that recomputes.

**Reliance question.** An agent received a tool result and intends to act on the
record inside it. Is that record the exact record it asked for, and does the
result agree with itself about which revision it delivered?

**Native precondition.** At least one exact record identity is observable — the
caller declares what it asked for (`record_reference.requested`), or the result
declares what it carries (`record_reference.returned`), or both. No identity is
invented and `returned` is never defaulted to `requested`.

**Derivation law.** Full per-field statement in the module docstring. The two
clauses that carry the most weight:

- `requested` and `returned` are recorded as the two aliases of one reference
  observation (`native.claimed_path`, `native.referenced_record`). The shipped
  REF assessor rejects them when they disagree
  (`PREFLIGHT_REF_ALIAS_CONTRADICTION`), which is exactly "the tool returned a
  record other than the one relied on" — detected before the engine is called.
- A declared revision digest is mapped only when a `revision_digest_domain`
  (`canonical-json:<RFC 6901 pointer>`) is declared **and resolves** against the
  delivered result, so claimed and observed digests always cover the same bytes.
  An unbindable claim is dropped and disclosed (`CLAIM_UNBOUND_DIGEST_DOMAIN`),
  never compared across digest domains. Cross-domain comparison would fire
  `NOT_FUNCTIONAL_BY` on every clean record — a false-hold generator wearing a
  detection costume.

**Reachable outcomes.** All three preflight states and three of the four OBL-02
classes; the demo walks them.

| Situation | Outcome |
|---|---|
| exact identity agreed, declared digest matches delivered bytes | `READY` → `VALID` |
| result carries a different identity than the one relied on | `REJECTED_INVALID` |
| declared revision digest ≠ digest of the delivered bytes | `READY` → `OMISSION_OR_INCOMPLETE` |
| tool errored, so no version of the record was delivered | `READY` → `OMISSION_OR_INCOMPLETE` |
| reliance target is the floating alias `LATEST` | `READY` → `MALFORMED_OR_BOUNDARY` |
| no record identity observable at all | `INSUFFICIENT_EVIDENCE` |

`BINDING_OR_CONFLICT` (absent `exact_reference`) is unreachable through this
mapper by construction: the precondition requires an identity before a REF record
is emitted, so the absent case abstains instead. That is a deliberate narrowing,
recorded here rather than papered over.

---

## Specified, not implemented: Microsoft Agent Framework message/state objects

Status: **design only.** No code, no corpus, no receipt. Not promotable — see
"Promotion gate" below.

Two distinct reliance questions live in this shape, and they map to two different
obligations. Field spellings below name the member that carries each concept;
confirm the exact spelling against the framework revision you target before
implementing, since the mapping law binds to concepts, not to names.

### (a) Function-result correspondence → REF / OBL-02

**Reliance question.** The agent issued a function/tool call carrying a call id
and later ingests a function-result message into its context. Is this result the
result of the call the agent is waiting on?

**Native precondition.** The pending call declares a call identifier (the
`callId` on the function-call content) **and** the incoming result content
declares the call identifier it answers. If either side is absent — a common case
for streamed or aggregated responses — abstain. Do not match on position in the
message list; ordinal position is not identity.

**Derivation law.**

| Native field | Derived from | Abstain when |
|---|---|---|
| `native.claimed_path` | call id the agent is waiting on | pending call carries no id |
| `native.referenced_record` | call id the result content declares it answers | result declares no id |
| `native.claimed_sha256` | digest the producer declares over the result payload, if any | no declared digest, or no declared digest domain |
| `observations.referenced_record_found` | the result content is a result, not an exception/refusal record | the message is neither |
| `observations.observed_sha256` | digest over the declared domain of the delivered result content | not found |

Mismatched call ids land as `PREFLIGHT_REF_ALIAS_CONTRADICTION` before the engine
runs, the same shape as the MCP identity swap.

### (b) Thread / checkpoint resumption → LIFECYCLE / OBL-17

**Reliance question.** The agent resumes from a serialized thread or workflow
checkpoint. Is the recorded lifecycle internally consistent, and did it actually
reach the terminal acknowledgment the resuming agent is assuming?

**Native precondition — and the reason this one mostly abstains.** The calibrated
LIFECYCLE rule requires *typed* events: exactly one typed `EFFECTIVE` followed by
one terminal typed `ACKNOWLEDGMENT`, in strict sequence and strict time order
(`adapters/CALIBRATION.md`). A checkpoint's ordered message history with
timestamps is **not** acknowledgment evidence. `CALIBRATION.md` states the rule
outright: "Noncontradictory lifecycle timestamps are not acknowledgment evidence.
They remain `INSUFFICIENT_EVIDENCE` until explicit event types exist." This is the
E7 applicability gap, measured: 208 of 408 corpus rows abstained on exactly this
basis, and none of them was defective.

So the mapper maps a checkpoint as LIFECYCLE **only** when the host declares an
explicit event-type correspondence — which workflow event type is the typed
`EFFECTIVE` and which is the terminal typed `ACKNOWLEDGMENT` — and the checkpoint
carries events of those declared types. Absent that declaration it abstains, and
that is the expected outcome for most checkpoints.

**Derivation law.** Sequence ordinals from the checkpoint's own event ordering
(never re-numbered), timestamps from the recorded event instants (integer epoch
seconds; never the resume-time clock), event types by the declared correspondence
only. Duplicate ordinals, equal or decreasing timestamps, and conflicting
typed/untyped views are contradictions the preflight detects
(`REJECTED_INVALID`), which is the real value here: a checkpoint whose recorded
history disagrees with itself is one an agent should not silently resume from.

**Do not map** the framework's own state-serialization version, thread id, or
store key as a lifecycle fact. They are transport metadata, not lifecycle events.

---

## Specified, not implemented: A2A-style agent messages

Status: **design only.** No code, no corpus, no receipt. Not promotable.

**Shape.** A message carries a role, an ordered list of parts (text, file, and
structured data), its own message identifier, and the task and context
identifiers it belongs to. A task carries a status with a state value and a
timestamp, a message history, and produced artifacts.

### (a) Task-answer correspondence → REF / OBL-02

**Reliance question.** A remote agent returned a message or artifact and the
receiver is about to treat it as the answer to the task it is waiting on.

**Native precondition.** The receiver declares the task identifier it relies on
**and** the incoming message declares the task identifier it belongs to. Context
identifier alone is insufficient — a context spans many tasks, so matching on it
would let another task's answer through. Abstain when either identifier is
absent.

**Derivation law.**

| Native field | Derived from | Abstain when |
|---|---|---|
| `native.claimed_path` | task id the receiver relies on | receiver declares none |
| `native.referenced_record` | task id the incoming message declares | message declares none |
| `native.claimed_sha256` | digest the producing agent declares for the artifact, over a declared domain | no declared digest **or** no declared domain |
| `observations.referenced_record_found` | the message carries the artifact or result the task was for; a failure/rejection status is `false` | indeterminate |
| `observations.observed_sha256` | digest over the declared domain of the delivered artifact bytes | not found |

Same rule as the MCP mapper on digests: an artifact digest declared over
unspecified bytes is dropped and disclosed, never compared across domains.
Artifacts assembled from streamed chunks must be digested **after** assembly, over
the assembled bytes, or not at all.

### (b) Task status progression → LIFECYCLE / OBL-17

**Reliance question.** Did the task the receiver is relying on actually reach a
terminal state, in a consistent order, before the receiver acts on its output?

**Native precondition.** A2A task states are typed, which puts this closer to the
calibrated rule than a raw message history — but "typed" is not enough by itself.
The host must declare the correspondence between the protocol's states and the
two events the rule requires (which state is the typed `EFFECTIVE`, which is the
terminal typed `ACKNOWLEDGMENT`), the status history must carry timestamps for
those events, and the sequence must be strictly increasing. Abstain otherwise —
in particular, abstain for a task observed only in its current status with no
recorded history, which carries one instant and no ordering evidence.

**Derivation law.** One typed event per recorded status transition, ordinals from
the recorded order, timestamps parsed to integer epoch seconds from the recorded
transition instants. Never synthesize a transition the history does not record,
and never treat "the task is currently completed" as evidence that it passed
through the intermediate states.

### (c) Artifact supersession → SUPERSEDE / OBL-15 (candidate, weakest)

An updated artifact replacing an earlier one is structurally a supersession, and
the SUPERSEDE family is calibrated. But the rule needs corrected bytes, citer
identities, and a chronology **for every citer** — the set of receivers that
relied on the superseded artifact. A2A does not carry a citer set; the host would
have to supply one from its own records, and a host that cannot enumerate its
citers must abstain rather than supply a partial list. Listed for completeness;
lowest promotion priority of the three.

---

## Promotion gate — what either of these owes before it ships

`adapters/CALIBRATION.md` sets the bar, and neither design meets it yet. Before a
mapping leaves this file for code:

1. an observable native precondition (stated above for each);
2. contradiction-before-applicability ordering (inherited from the preflight);
3. a closed host profile shape (inherited: `RR-PORTABLE-FACT-PROFILE-1`);
4. field-level evidence bindings (the derivation tables above);
5. stale, partial, and adversarial tests;
6. **at least one sufficient clean case and one sufficient defect, from a real
   corpus** — neither shape has one here;
7. **a paired receipt keeping invalid and insufficient results separate**, with
   the `READY`, `REJECTED_INVALID`, and `INSUFFICIENT_EVIDENCE` counts reported
   as disjoint categories, and clean-pass / new-false-hold / detection counted
   against held-out truth.

Items 6 and 7 are the whole gate. Anyone can write the derivation table; the
receipt is what turns it from a plausible mapping into a calibrated one. Shipping
either mapper without one would repeat the forced-arm result the artifact already
measured and published against itself.
