# Host obligations — the explicit contract for integrators

The engine deterministically classifies fact profiles and seals decisions.
Everything operational around that — state, truth, atomicity, derivation,
effects — belongs to the host. The external review correctly observed that
this division was implicit and its cost undisclosed; this document makes it
explicit and testable. Each obligation carries a conformance check an
integrator can run against their own host.

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
host must decline to force the mapping — forcing it measured a 32.6%
false-hold rate on real records in `proof/RESULTS.md`; declining measured
0% with no detection loss.

*Conformance check:* your adapter declares, per obligation, the native
precondition under which it maps a record, and abstains otherwise; abstentions
are logged, not silently dropped.

## H5. Input binding and transcripts

The sealed 0.2/0.3 response does not bind the decision input (recorded
defect, `ERRATA.md` E2). Hosts that need an auditable decision must either
use `grounded-0_4/rr_api.py::decide_audited` (audit seal binds request
bytes, decision-input digest, and the sealed receipt) or record full
transcripts and verify with the core transcript evaluator. Do not present a
bare sealed receipt as evidence of *what* was decided — it proves only that
*a* decision of that class was sealed under that request id.

*Conformance check:* `grounded-0_4/test_grounded_0_4.py` (the BINDING
section) — two different fact profiles must never share an audit seal in
your pipeline.

## H6. Effects

The engine never executes, mediates, or observes effects. Effect receipts
are digests over the host's own attested effect fields. Execution,
authorization enforcement at the effector, and post-hoc reconciliation of
observed effects against receipts are host duties.

*Conformance check:* for every executed effect, your system can produce the
audited decision whose `effect_receipt_sha256` matches the recomputed
preimage from your effect log.
