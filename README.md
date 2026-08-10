# Receiver-reliance baseline — conformance suite and reference implementation

Release 1.0, composed generation. License: Apache-2.0 (see `LICENSE`;
Copyright 2026 James Dimachkie).

## What this is, and where it comes from

When one autonomous agent hands records to another — claims, versions,
grants, lifecycle events, effect receipts — the receiving side needs a
deterministic, auditable way to decide what it may rely on. This repository
is the **baseline layer** of a research program studying that decision: a
frozen 28-operation decision engine ("B1"), a supplemental 2-operation
generation that closes its reviewed capability gaps, their conformance
fixture suites, and reference implementations that reproduce both suites
byte-for-byte. The composed 30-operation surface was ruled complete by a
candidate-blind completeness review against a hash-pinned prior-art basis
(see "The supplemental 0.3 generation" below).

The program's larger question — whether a specific receiver-local binding
rule causally improves handoff outcomes against a strong baseline — is a
blinded experiment that is *not* part of this artifact and has not produced
results. What ships here is the part with standalone value: a
content-addressed, independently checkable comparator you can run, port, or
adapt.

The engine is deliberately narrow: it deterministically classifies
structured fact profiles that the caller assembles and supplies, and seals
the decision. It does not retrieve records, store lifecycle state, enforce
policy, run clarification dialogues, or execute effects. Those live in the
host system. Some schema-required inputs are bound for future semantics and
are classification-inert today (disclosed under "What this does not claim").

The 30 operations — the 28-operation accepted core plus the two
supplemental rows — cover the obligation surface a careful receiver faces:
vocabulary and purpose binding, exact reference resolution, scope and
interval consistency, evidence independence, version functionality,
write-set visibility, dependency acyclicity, lifecycle ordering, effect
authorization windows, nonce replay, untrusted-content validation,
render/effect binding, terminate-as-unresolved when the basis is absent,
selective clarification triage (proceed, ask, or hold, with burden
accounting), and intent-compatible selection from frozen candidate pools.
Each operation classifies structured facts into `VALID`,
`MALFORMED_OR_BOUNDARY`, `BINDING_OR_CONFLICT`, or `OMISSION_OR_INCOMPLETE`
via a machine-readable predicate table evaluated in frozen precedence order.
"B1-ATTENTION" is the same engine behind a wrapper that adds a neutral
attention card, so experiment arms can control for ceremony.

## Quickstart

Requires any CPython 3.12. From `baseline-run/`:

```bash
python -B implementation-output-0.2/run_conformance_0_2.py
```

Expected: `... failures=0`, exit 0. The run reports 798 checks: 720
fixture-pinned (112 semantic entries, 370 competence mutations, 224 wrapper
arms, 10 negatives, 4 metamorphic relations) plus 78 harness-owned
deterministic error-selection closures.

The composed runner executes the accepted 0.2 suite AND the supplemental
0.3 suite (905 checks total) under the composed 30-operation interface:

```bash
python -B implementation-output-0.3/run_conformance_0_3.py --suite all
```

Expected: two summary lines, `798 ... failures=0` and `107 ... failures=0`,
exit 0. `baseline-run/RUNBOOK.md` documents the layout, the sealed
subprocess-ABI mode, running single requests by hand, and how to read
fixtures.

## Design properties worth stealing

- **Everything is digest-pinned.** Fixture packs, receipts, and responses
  carry self-zero SHA-256 seals over RFC 8785 JCS canonical bytes; the
  contract and implementation sources are pinned by raw SHA-256 in the
  manifest and receipts. Any reimplementation can be checked for
  byte-exact agreement with the reference on the full pinned suite.
- **Anti-teaching-to-the-test fixtures.** Fixture labels and provenance are
  decoys: 370 competence mutations rename labels, swap authoritative facts
  under fixed labels, and flip digests to kill any implementation that
  pattern-matches metadata instead of evaluating the decision table.
- **Deterministic error law.** One error per response, selected by precedence
  then lexicographically-first mismatched pointer; even error responses are
  byte-pinned in fixtures.
- **Strict runtime profile.** No clock, randomness, network, or ambient
  environment; integer-only JSON; NFC; byte-exact replay.

## Independent adversarial review

The reference implementation went through ten adversarial rounds of
author-separated review (a different AI lane from the one that wrote it)
under a fixed charter: reproduce both conformance modes, re-derive every
digest, and attack the contract with probes the fixtures cannot reach. The
rounds surfaced 22 real conformance defects, every one fixed and pinned as
a regression case. The first round alone caught a critical RFC 8785
member-ordering bug that corrupted canonical output. Two findings were
refuted against the contract's own pinned bytes. Both refutations held on
re-examination. The final round, the heaviest (45 designed probes plus
70,000 randomized grammar and totality cases), found no implementation
defect: no input crashed, exceeded the output limit, or broke a seal.

To be precise about what "acceptance" means here: the reviewer's formal
verdict in every round, including the last, was REJECT-with-findings. It
never issued a sign-off. The loop ended under a pre-stated stopping rule
when the heaviest round found zero implementation defects and its sole
finding was adjudicated against the contract's pinned text as a
contract-design non-closure rather than an implementation defect. The
implementing lane made that call, and its reasoning is on record.
Acceptance is that convergence. What a reader can verify from these bytes
is the final accepted state: the digests and the suite that reproduces
them. The round history is the authoring lanes' internal record,
summarized in `ACCEPTANCE.md` and disclosed as such.

Two items are recorded as **contract-design non-closures** rather than
implementation bugs:

1. Exact RFC 6901 error pointers can, on pathological deeply-nested inputs,
   exceed the wrapper response schema's 240-character pointer cap; no
   implementation can satisfy both frozen clauses for that input class.
2. The wrapper transcript-binding evaluator, as specified, verifies schema
   validity, envelope bindings, echo consistency, and seal integrity, but
   not that a recorded response is the correct semantic derivation of its
   request. (The *core* transcript evaluator does require that; the wrapper
   one omits it by construction.) To semantically verify a recorded wrapper
   triple, re-run the reference implementation on the request and compare,
   or use the core evaluator. A future contract revision can fold the
   derivation step into the wrapper evaluator.

The round-by-round summary — probe counts, findings, dispositions, and the
final digests — lives in `ACCEPTANCE.md`. The complete probe-level process
record is retained outside this release.

## The supplemental 0.3 generation

An adversarial capability-gap review of the accepted 28-operation core
found two capability classes established by current prior art that the
surface did not represent: selective clarification (gap-driven query
selection, answer ingestion, re-evaluation, and unnecessary-query burden
accounting) and intent-compatible selection (compatibility evaluated
before similarity over a frozen candidate pool, with auditable exclusion
reasons). The 0.3 generation closes both gaps additively — zero accepted
0.2 bytes changed — under `supplemental-0_3/`:

- a supplemental contract that inherits the 0.2 semantic law by digest and
  adds two decision-table rows (OBL-29 `SELECTIVE_CLARIFICATION`, OBL-30
  `INTENT_COMPATIBLE_SELECTION`), composed 30-operation schemas derived
  from the pinned bases by a stated mechanical rule, and a versioned
  wrapper interface;
- byte-sealed fixture packs at the accepted density (12 semantic entries,
  12 wrapper pairs / 24 arms, 53 competence cases including five named
  metamorphic families: unnecessary asks, answer replay, wrong-intent
  similarity lures, intent changes, incompatible distractors), plus
  nonempty retrieved-content coverage for the untrusted-content operation;
- a dated, hash-pinned prior-art snapshot fixing the completeness basis,
  with a treadmill guard: later prior art is absorbed only at an explicit
  versioned re-freeze, never by reopening a sealed acceptance;
- an extended reference implementation (`implementation-output-0.3/`)
  covering all 30 operations in both execution modes, built by a separate
  lane from the fixture author.

Its acceptance chain mirrors the core's and is disclosed in
`ACCEPTANCE.md`: independent fixture acceptance (round 1 FAIL with two
valid blockers, fixed; round 2 PASS with zero findings; the receipt ships
in `supplemental-0_3/receipts/`), adversarial implementation acceptance
(round 1 ACCEPT: 5,132 executions including randomized and differential
sweeps, zero valid defects), and a candidate-blind completeness review of
the composed matrix from an isolated evidence bundle, which returned
COMPLETE with the conditional selection row admitted (verdict shipped at
`supplemental-0_3/BLIND_GATE_VERDICT_0_3.md`; the reviewer's custody
confirmation was corroborated against its session transcript).

A third contract-design non-closure joins the two above, found by the
implementation-acceptance reviewer and ledgered rather than patched: one
MALFORMED disjunct of OBL-30 (contradictory duplicate exclusion reasons)
is unreachable while the exclusion-reason enum has a single member; it
misclassifies nothing and re-activates at any future enum extension.

## Where this sits among adjacent systems

Orientation, not a ranking (see "What this does not claim"). Four adjacent
efforts:

- [Microsoft's Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)
  is a broad agent governance and security toolkit: policy over actions
  and messages (including inbound allow/deny), peer trust scoring and
  handshakes, capability grants, identity, sandboxing, and audit. Its
  published surfaces (as of August 2026) gate whether a peer, message, or
  action is permitted; per-record semantic validation of received records
  — completeness, conflicting claims, lifecycle consistency — is left to
  the application layer.
- [Agent Trust Negotiation](https://datatracker.ietf.org/doc/draft-somoza-dmsc-atn-agent-trust-negotiation/)
  (an individual IETF Internet-Draft) negotiates trust *before* work
  begins: capability manifests, delegation chains, session receipts. It
  establishes the relationship; it does not classify the records that
  later flow across it.
- [SCITT (RFC 9943)](https://www.rfc-editor.org/rfc/rfc9943.html) makes
  signed statements transparent: append-only logs and inclusion-proof
  receipts prove a statement was registered by an identified issuer. It
  does not judge whether a statement's content is consistent, complete,
  or in conflict with what the receiver already holds.
- [CHAP](https://github.com/BrightbeamAI/chap) records human-agent
  collaboration: hash-linked envelopes of drafts, edits, and rationales.
  It audits the decision history; it does not render the reliance
  decision.

This artifact sits between those layers: *after* records arrive and
*before* the receiver acts on them, it deterministically classifies each
obligation from caller-assembled facts, with the whole decision surface
byte-pinned and replayable. Its distinguishing properties are checkable:
one integrated decision table spanning all 30 operations, exact byte
behavior in two execution modes, competence mutations that kill
metadata-pattern-matching implementations, paired wrapper arms for
ceremony control, and a published defect-to-regression review record. The
adjacent systems compose with it: a session established by ATN, receipts
drawn from a SCITT log, or actions governed by a policy engine can all
feed the fact profiles this engine classifies.

## What this does not claim

No efficacy, novelty, security, or interoperability claim. No conformance to
any external standard or cited system: the suite tests conformance to THIS
contract only. Acceptance means the reference implementations conform to
their contracts under adversarial review; it is not a security audit and not
a fuzzing-completeness guarantee. Independent re-verification and a second
implementation for cross-testing are invited (see "Contributing" below). The
outcome-value experiment has not run. The capability-gap
review that motivated the 0.3 generation is closed by it: both reviewed
classes now have rows, fixtures, and an accepted implementation, and the
composed surface was ruled complete against the pinned prior-art snapshot.
That is completeness relative to a dated basis, not to all future prior
art (the snapshot's treadmill guard governs). The clarification and
selection capabilities the new rows classify are source-derived capability
classes; no external system's model, taxonomy, or branding is imported,
and the prior-art citations carry no efficacy claim.

Disclosed inert surface: the wrapper's `budget` and `pause_state` are
schema-validated and parity-enforced across arms but behaviorally inert.
`clarification_state` is no longer fully inert: the 0.3 wrapper pack binds
it to the clarification row's semantic facts under a recorded
fixture-authoring law (`REQUESTED` and `RESOLVED` receive their first
coverage there), while it remains fixed to `NONE` throughout the accepted
0.2 arms and carries no classification authority anywhere. Some operation
fact profiles likewise require fields their class predicates never
consume: the untrusted-content operation (OBL-22) classifies only the
caller-supplied validation verdict facts. Its five content-digest arrays
are exercised nonempty by the 0.3 supplemental entries, and classification
is demonstrably insensitive to them, which is the operation's disclosed
semantics (the caller's verdict is the authority). In the selection row,
`similarity_rank` and the intent tuple are deliberately
non-authoritative for classification; that non-authority is the tested
property, exercised by the similarity-lure and intent-change metamorphic
families.

## Contributing / re-verification

The highest-value additions are adversarial: a coverage-guided fuzzing
campaign against the reference runner, and an independent second
implementation cross-tested against the same fixture packs. Both are
welcome; neither exists yet. To re-verify what is here, run the conformance
suite (both modes), then re-derive every seal per the RUNBOOK.

## Provenance and exclusions

Authorship is disclosed rather than scrubbed. Under a role-separation
protocol, fixture packs, reference implementations, and every acceptance
come from pairwise-distinct AI lanes, and the 0.3 generation records a
further constraint honestly: its fixture-author lane is the same lane that
wrote the 0.2 implementation (the exposure is disclosed inside the 0.3
contract), so its implementation extension was produced by yet another
lane and every 0.3 acceptance re-derived expectations from contract bytes
alone. Actor identifiers in the receipts record which lane did what.

The machinery inside this artifact is the machinery that built it. The
receipts that governed construction are instances of the shipped
specification, not an external process note: both implementer build
receipts and both fixture-acceptance receipts validate against the
receipt schemas defined in the contracts they ship beside, their
self-zero seals follow the contracts' own seal rules, and the
role-separation law they obey is a contract section. (The implementation
manifests follow the shipped manifest schema's shape; that schema's
digest constants are 0.2-generation-specific by construction, so the 0.3
manifest pins its own generation's authorities in the same fields.)
Checking the construction story therefore uses the same moves as
checking the artifact: validate the schemas, recompute the seals,
compare the digests. Excluded from this release: the pinned offline
toolchain (reproduce it from the official CPython 3.12.4 Windows embeddable
zip,
`https://www.python.org/ftp/python/3.12.4/python-3.12.4-embed-amd64.zip`,
SHA-256 `15fea3c9367653a85086fe37216b4d1a1c78688fa5e1587e1db0b0f658856564`,
with `python312._pth` left stock and site imports disabled), the research
program's source components, and internal process records. The toolchain's
provenance manifest (`TOOLCHAIN_MANIFEST_0_1.json`) is withheld because it
carries machine-path provisioning evidence; the contract pins its path,
byte length, and digest under `toolchain_manifest_tree_reference`, so a
future release of it is verifiable against these bytes. Both conformance
modes run without it; only manifest regeneration requires it (see the
RUNBOOK).
