# Receiver-reliance baseline — conformance suite and reference implementation

Release 1.2, composed generation. License: Apache-2.0 (see `LICENSE`;
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
host system — [HOST_OBLIGATIONS.md](HOST_OBLIGATIONS.md) is the explicit,
testable contract for that division (state truthfulness, atomicity,
derive-don't-assert, applicability calibration, input binding, effects).
Some schema-required inputs are bound for future semantics and are
classification-inert today. Call
`grounded-0_4/rr_api.py::authority_for_operation` with an obligation ID or
operation handle to ask the artifact which required fields carry authority;
the result is read from `grounded-0_4/authority_register_0_4.json`, not a
second code table. The generated one-glance view is
[grounded-0_4/AUTHORITY_TABLE.md](grounded-0_4/AUTHORITY_TABLE.md), and
`python -B grounded-0_4/generate_authority_table.py --check` fails if it
drifts from the register. Known defects and enforcement are recorded in
[ERRATA.md](ERRATA.md). What every seal and receipt in this repository
does and does not prove — and who is assumed to consume it — is declared
once, canonically, in [TRUST_MODEL.md](TRUST_MODEL.md).

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

Requires CPython 3.12 or newer; 3.12, 3.13, and 3.14 are validated on the
hosted matrix (see "Cross-platform validation" below), and re-run against a
clean clone at the current commit in
[portability/THIRD_PARTY_REPRODUCTION_20260818.md](portability/THIRD_PARTY_REPRODUCTION_20260818.md).
From `baseline-run/`:

```bash
python -B implementation-output-0.2/run_conformance_0_2.py
```

Expected: `... failures=0`, exit 0. The run reports 800 checks: 720
fixture-pinned (112 semantic entries, 370 competence mutations, 224 wrapper
arms, 10 negatives, 4 metamorphic relations) plus 80 harness-owned
deterministic error-selection closures.

The composed runner executes the accepted 0.2 suite AND the supplemental
0.3 suite (907 checks total) under the composed 30-operation interface:

```bash
python -B implementation-output-0.3/run_conformance_0_3.py --suite all
```

Expected: two summary lines, `800 ... failures=0` and `107 ... failures=0`,
exit 0. `baseline-run/RUNBOOK.md` documents the layout, the sealed
subprocess-ABI mode, running single requests by hand, and how to read
fixtures.

For one concrete handoff decided end to end (the records, the exact
commands, and byte-pinned responses for a clean, a violated, and an
unresolved case), see [EXAMPLE.md](EXAMPLE.md).

## Using it on your own records

The engine classifies fact profiles the caller assembles; it does not read your
records. Two things make that tractable rather than a research exercise.

**Start with the preflight, not the engine.** `adapters/` exports a stdlib-only
three-state preflight over native evidence plus an optional host-produced fact
profile:

```python
from adapters import READY, preflight

result = preflight(native_record, optional_host_fact_profile)
if result.status != READY:
    record_preflight_result(result.as_dict())
    do_not_invoke_engine()
```

`READY` is eligibility only — never a pass and never an engine decision.
`REJECTED_INVALID` is detection. `INSUFFICIENT_EVIDENCE` is abstention, which is
what you want when your records genuinely do not carry an obligation's
semantics: it is the alternative to fabricating values and eating false holds.
Measured over the published 408-record corpus, the preflight holds detection at
18/18 while taking the clean false-hold rate from 34.1% to **0.0%**, abstaining
on 208 rows rather than guessing (`adapters/OUTCOME.md`; reproduce with
`python -B adapters/outcome_receipt.py --check`). No defective row lands in the
abstention bucket.

Be clear about its scope: WP1 stopped at a three-strike boundary
(`F-WP1-009`), so this is a preflight, **not** a general host adapter, runner,
transcript verifier, replay store, or effect API. Read
`adapters/README.md` for the exact taxonomy and `adapters/CALIBRATION.md` for
the playbook.

**Then satisfy the host contract.** [HOST_OBLIGATIONS.md](HOST_OBLIGATIONS.md)
is the testable division of labour — state truthfulness, atomicity,
derive-don't-assert, applicability calibration, input binding, effects. H1–H6
remain yours regardless of preflight status. For decisions you intend to rely
on, call `decide_audited` (see the grounded 0.4 layer below), not the frozen
response path.

Honest status on adoption: `TRUST_MODEL.md` records **zero external or sibling
code consumers** to date. Nothing here has been load-tested by an integrator
other than its author, and the applicability limits in `ERRATA.md` E7 are the
first thing a new consumer should read. What is recorded-and-unfixed between
this artifact and one you could adopt -- with the treatment and owner for each
item -- is ledgered in [ADOPTION.md](ADOPTION.md).

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
- an extended reference implementation
  (`baseline-run/implementation-output-0.3/`)
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

## After the external review: the grounded 0.4 layer

An independent external review (2026-08-10, against cc6f3657) confirmed the
conformance engineering and pressed on what conformance cannot prove. Its
findings were reproduced probe-for-probe and answered additively — zero
sealed 0.2/0.3 bytes changed:

- `grounded-0_4/rr_api.py` — the audited decision surface `decide_audited`,
  whose seal binds the request bytes, the decision-input digest, and the frozen
  receipt, and which carries the matched-predicate witness trace and derived
  record references the sealed response lacks. In-process calling is
  substantially cheaper than the stdio ABI: the recorded proof run measured
  2.998 ms in-process against 104.99 ms via the ABI (`proof/RESULTS.md`).
  A bare `decide` export previously reached the frozen response path directly;
  it is **WITHDRAWN** (ERRATA E2, deep-scan `csf_abbd6848`) because that route
  returned sealed responses which do not bind the decision input. Use
  `decide_audited` for any decision you intend to rely on. Frozen execution
  survives only as the explicitly non-evidentiary
  `receiver_reliance.conformance.execute`, and
  `grounded-0_4/test_public_surface.py` pins the absence of `decide` so the
  route cannot silently return. The current audit format
  (`B1-AUDITED-DECISION-0.4.1`, ERRATA E8/E9) additionally seals the
  governing closure-policy, authority-register, and engine-source digests
  into every audit, discloses record-reference truncation explicitly, and
  fails closed to `AUDIT_INCOMPLETE` when a closure evaluator errors on an
  otherwise-VALID decision.
- `grounded-0_4/closures_0_4.json` — tighten-only closure predicates fixing
  the confirmed OBL-30 holes (caller projections now cross-checked against
  the verdict rows they summarize; disposition exhaustiveness derived, not
  trusted).
- `grounded-0_4/authority_register_0_4.json` +
  `grounded-0_4/lint_contract.py` — a both-directions, CI-gated ledger of
  which fact fields carry classification authority, wire-format uniqueness
  law, and the closure tighten-only law, so these defect classes cannot be
  reintroduced silently by future generations.
- `proof/` — the review's own bar, executed: native records from a real
  multi-agent coordination system, a smaller schema+policy gate as the
  comparator, referee-held ground truth. Result (internal held-out tier):
  the calibrated adapter detected 18/18 defects including the relational
  one the gate structurally misses, at zero false holds; the uncalibrated
  run exposed and measured the applicability gap (ERRATA E7). Full
  protocol and limits in `proof/README.md`.

`grounded-0_4/test_grounded_0_4.py` (517 checks) pins parity with every
frozen fixture plus the review's probes as regressions.

## Cross-platform validation: the portability program

The composed engine and its harnesses were then validated as a
portability target under the same evidence discipline. `portability/`
holds five lanes plus the verifiers that bind their receipts:

- a finite behavioral model of the reliance decision flow, its complete
  N=48 enumeration admitted after an independent fresh-context refuter
  reproduced the canonical receipt byte-for-byte (`portability/model/`);
- an independent oracle (35 tests) authored under a no-read rule against
  the implementation sources, with the exposure ledger in
  `portability/oracle/PROVENANCE.md`;
- deterministic live-transport schedules over pipes and socketpairs,
  barrier-timed, each replayed twice byte-identically
  (`portability/live/`);
- a bounded concurrency ladder at `P = 1, 2, 4, 8` with independent
  audited-envelope accounting (`portability/concurrency/`);
- a hosted matrix and a hardened Linux container sandbox
  (`.github/workflows/portability.yml`): CPython 3.12/3.13/3.14 across
  Ubuntu x64/arm64, macOS arm64, and Windows x64/arm64. All 15 runnable
  normative rows passed at plan-bound counts; the three predeclared
  `macos-13` rows are recorded as evidenced `INFRA_UNAVAILABLE`; PyPy and
  GraalPy run as off-contract observations, never as normative
  substitutes.

Hosted receipts are committed under `portability/receipts/hosted/` with a
hash-bound manifest. Two stdlib-only verifiers re-derive the custody chain
from bytes:

```bash
python -B portability/verify_receipts.py
```

```bash
python -B portability/verify_hygiene.py
```

Expected: `verify-receipts: checks=193 failures=0`, then `HYGIENE_PASS`.
The separated-evidence report is
[orchestration/PORTABILITY_VALIDATION.md](orchestration/PORTABILITY_VALIDATION.md).
It records the full hosted chronology — four red runs, each adjudicated
into a pinned harness finding, before the green one — and the exact claim
scope: validation holds within the executed environments and declared
finite bounds, and nowhere else.

## Contributing / re-verification

The highest-value additions are adversarial, and both invited classes now
have recorded first attempts. A deterministic seeded campaign (100,000
case identities, 67,599 unique raw byte strings, zero findings) ran on
2026-08-10 (`fuzz/`, `orchestration/FUZZ_CAMPAIGN.md`). A coverage-guided
differential campaign now has a recorded first run (hosted, 2026-08-13):
steering on reference branch coverage, it refuted the then-current
second-implementation candidate at identity 588
(`second-implementation/findings/F-WP4-007.md`). An independent second
implementation has been attempted under author separation and REJECTED in
seven fresh-context refutation rounds across two programs — most recently
attempt 4, refuted by a decisive round recording 592 executed divergences
across five independent mechanisms (binding-pool membership under missing
members, canonical registry-row derivation, non-finite constant
classification, ERR_JSON/ERR_NUMBER precedence order, duplicate-key
lone-surrogate handling; minimized witnesses and reports in
`orchestration/refuters/`, decisive report `RI5.md`). That is negative
evidence about reimplementation sensitivity, not independent
confirmation: a conforming second implementation still does not exist and
remains the single most valuable outside contribution. To
re-verify what is here, run the conformance suite (both modes), then
re-derive every seal per the RUNBOOK, then, from the repository root, run
`python -B grounded-0_4/test_grounded_0_4.py`,
`python -B grounded-0_4/lint_contract.py --gate`,
`python -B grounded-0_4/test_lint_gate.py`,
`python -B receiver_reliance/generate_engine_manifest.py --check`,
`python -B receiver_reliance/test_engine_manifest.py`, and the two custody
verifiers in "Cross-platform validation" above. The engine manifest is the
package's own integrity gate: importing `receiver_reliance` verifies all
eleven engine files by byte length and SHA-256 before executing any of them
and refuses to import on drift, so a checkout or a distribution that does
not hold the published bytes fails at import rather than producing decisions
from unknown code. What is deliberately not
published, and why, is ledgered in [WITHHELD.md](WITHHELD.md); the blind
completeness review's input bundle is published and verifiable under
[evidence/](evidence/README.md).

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
with `baseline-run/toolchain/python312._pth` left stock and site imports
disabled), the research
program's source components, and internal process records. The toolchain's
provenance manifest (`baseline-run/toolchain/TOOLCHAIN_MANIFEST_0_1.json`) is
withheld because it
carries machine-path provisioning evidence; the contract pins its path,
byte length, and digest under `toolchain_manifest_tree_reference`, so a
future release of it is verifiable against these bytes. Both conformance
modes run without the provenance manifest; the sealed ABI mode still requires
the separately reproduced `baseline-run/toolchain/python.exe`. Only manifest
regeneration requires the manifest itself (see the RUNBOOK).
