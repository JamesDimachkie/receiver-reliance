# Host obligations — the explicit contract for integrators

The engine deterministically classifies fact profiles and seals decisions.
Everything operational around that — state, truth, atomicity, derivation,
effects — belongs to the host. The external review correctly observed that
this division was implicit and its cost undisclosed; this document makes it
explicit and testable. Each obligation carries a conformance check an
integrator can run against their own host.
[DIAGRAMS.md](DIAGRAMS.md#a1--the-division-of-labour-and-the-paths-that-do-not-exist)
draws this division, including the three things the engine never touches.

## H1. State truthfulness

Facts describing state (`consumption_state`, `prior_invocation_nonces`,
`revoked_at`, staged/visible write sets, lifecycle sequences) are the host's
attestation. The engine's verdict is conditional on it: garbage in, sealed
garbage out. The engine detects *internally inconsistent* attestations, not
false ones.

*Conformance check:* replay a recorded decision after mutating the host's
state store; the re-derived fact profile must change, and the audited
decision's `decision_input_sha256` must change with it.

## H2. Atomicity and replay (OBL-26 and every single-use grant)

The engine classifies a host-attested consumption state; it holds no state
and cannot serialize concurrent invocations. "Single-use" is enforced by the
host's transaction that (a) checks-and-consumes the nonce atomically, and
(b) derives `consumption_state`/`prior_invocation_nonces` from that same
transaction. Two concurrent calls with the same fresh nonce will BOTH be
classified VALID — by design. If your system needs replay prevention, it
lives in your store's transactional guarantee, and the engine verifies the
bookkeeping you attest.

*Conformance check:* run the concurrent-replay probe against your host
adapter (not the bare engine): exactly one of two racing invocations may
reach the engine with `consumption_state = "UNUSED"`.

## H3. Derive facts; never assert conclusions

Every fact you can compute from records you hold, compute — the proof
harness's adapter derives glob-scope reductions, version-testimony merges,
and supersession blame joins from raw observations. Fields that carry
conclusions (verdicts, projections, dispositions) must be derived by a
process you can audit, and on the grounded 0.4 surface the closure
predicates cross-check them against the facts they claim to summarize
(`grounded-0_4/closures_0_4.json`). The authority register
(`grounded-0_4/authority_register_0_4.json`) tells you exactly which fields
carry classification authority — do not spend derivation effort on
registered-inert fields, and do not rely on them being checked.

*Conformance check:* `python -B grounded-0_4/lint_contract.py --gate` plus
your adapter's own fabricated-field count (see `proof/arm_b1.py` for the
instrumentation pattern) — fabrications should be zero for fields the
register marks `semantic`.

## H4. Applicability calibration

Obligations demand their full fact profile; the contract has no abstention
mechanism (recorded gap, see `ERRATA.md` E7). If a record genuinely lacks an
obligation's semantics (a lifecycle with no acknowledgment event, say), the
host must decline to force the mapping — forcing it produced 133 false holds
among 390 clean records (34.1%) in `proof/RESULTS.md`; declining measured
0% with no detection loss.

*Conformance check:* your adapter declares, per obligation, the native
precondition under which it maps a record, and abstains otherwise; abstentions
are logged, not silently dropped.

## H5. Input binding and transcripts

The sealed 0.2/0.3 response does not bind the decision input (recorded
defect, `ERRATA.md` E2). Hosts that need an auditable decision must either
use `grounded-0_4/rr_api.py::decide_audited` (the 0.4.2 audit seal binds
request bytes, decision-input digest, the sealed receipt, and the governing
closure-policy/authority-register/engine/decision-table-contract digests —
see `TRUST_MODEL.md` for exactly what that seal proves) or record full
transcripts and verify with the core transcript evaluator. Do not present a
bare sealed receipt as evidence of *what* was decided — it proves only that
*a* decision of that class was sealed under that request id.

The supported import for that surface is the package, from a checkout root:
`import receiver_reliance as rr; rr.decide_audited(request)` — the
`grounded-0_4/` directory name is a filesystem path, not an importable
module. A ready-made request envelope is `examples/handoff-clean.json`, and
[EXAMPLE.md](EXAMPLE.md) walks it end to end.

*Conformance check:* `python -B grounded-0_4/test_grounded_0_4.py` (the
BINDING section) — two different fact profiles must never share an audit
seal in your pipeline.

## H6. Effects

The engine never executes, mediates, or observes effects. Effect receipts
are digests over the host's own attested effect fields. Execution,
authorization enforcement at the effector, and post-hoc reconciliation of
observed effects against receipts are host duties.

*Conformance check:* for every executed effect, your system can produce the
audited decision whose `effect_receipt_sha256` matches the recomputed
preimage from your effect log.

## H7. Request admission, and what a bound costs

The engine spends whatever a request's shape costs and cannot decline. Its
error law obliges a full traversal per `oneOf` branch before it may emit
`ERR_LIMIT` (precedence 90), so an oversized object is walked after it has
already failed, and the only thing that ends the walk is the frozen ceiling
`MAX_INPUT_BYTES = 16,777,216`. Deciding which requests are worth evaluating
at all is therefore the host's, like state and effects.

No bound is free, and the arithmetic is published. The contracts declare
requests up to **3,392,691 bytes** legal (`oneOf/27`, OBL-28) while this
artifact's entire 372-request fixture corpus tops out at **4,399** — so any
bound low enough to control cost rejects requests the contract declares valid.
A structural-member proxy does not escape it: a contract-legal OBL-01 request
at declared caps carries 82,363 structural tokens and costs 9.2 ms, while an
adversarial one carrying 18,057 costs 566 ms, because a comma inside a string
literal is a structural token and is legal. A deployment that declares a bound
has narrowed its own contract and owes that fact to its callers, in whatever
document publishes its supported request shapes. A deployment that declares
none has accepted the frozen ceiling's cost, which is equally a decision.

`deployment/` ships one implementation of this obligation, off unless an
operator enables it; nothing here requires it, and its unset state is
byte-identical to its absence.

*Conformance check:* `python -B deployment/test_admission.py` — its
`TheProfileRejectsContractLegalRequests` arm states the obligation as a test:
a request the frozen engine seals `ok` is refused under a declared bound, and
the refusal records which authority refused it rather than implying the engine
would have. For your own host the equivalent check is that every request shape
your deployment refuses before evaluation appears as refused in the request
contract you publish to your callers.
