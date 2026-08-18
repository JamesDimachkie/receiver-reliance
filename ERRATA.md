# Errata and recorded defects

E1–E7 entered after the 2026-08-10 external review; E8–E9 after the
2026-08-12 Deep Security Scan (Intake 10).

Confirmed against the artifact at cc6f3657 by reproducing the external
review's probes (conformance 800+107 green; OBL-08/OBL-30 mutation probes;
OBL-26 replay; wire-format collision; 199 required fields / 24 never-referenced
fields in the fact-field authority census).
Sealed 0.2/0.3 bytes are never edited: fixes land additively in
`grounded-0_4/` or are scheduled for the next sealed generation. Each
erratum names its enforcement so the class cannot recur silently.

## E1 — Wire-format collision between generations

`B1-SEMANTIC-DECISION-REQUEST-0.2` is declared by BOTH the accepted 0.2 and
the composed 0.3 surfaces, which behave incompatibly on 0.3-only operations
(same bytes: ERR_SCHEMA from 0.2, PASS from 0.3). There is no wire-level
negotiation. *Status:* grandfathered by name in the authority register;
`grounded-0_4/lint_contract.py` L2 fails CI on any NEW collision. Next
sealed generation must declare a distinct format string and reject
undeclared generations.

## E2 — Sealed responses do not bind the decision input

Ordinary (non-effect) responses carry no digest of the facts they judged;
materially different fact profiles under one request id produce
byte-identical receipts, and `record_references` is hard-coded empty.
*Status:* fixed on the additive surface —
`grounded-0_4/rr_api.py::decide_audited` seals
`request_raw_sha256` + `decision_input_sha256` + the frozen receipt into an
audit object, carries the matched-predicate witness trace and derived record
references (`grounded-0_4/test_grounded_0_4.py` BINDING section enforces
divergence).
Next sealed generation folds these fields into the sealed response schema.
*2026-08-16 hardening:* the frozen defect itself is immutable (sealed 0.2/0.3
bytes never change), and the top-level `receiver_reliance.decide` export
that reached it as a supported route is WITHDRAWN (deep-scan
csf_abbd6848); frozen execution survives only as the explicitly
non-evidentiary `receiver_reliance.conformance.execute` /
`rr_api.conformance_execute`. `decide_audited` is the one supported
evidentiary decision API; `grounded-0_4/test_public_surface.py` pins the
withdrawal.

## E3 — Envelope digests bind the inert half of the request

`inner_request_raw_sha256`/`inner_input_sha256` bind `inner_request`, which
classification never reads; `decision_input`, the only classification
input, is not digest-bound anywhere in the envelope. *Status:* audited
surface binds it (E2 fix); next sealed generation rebinds the envelope
digests to `decision_input`.

## E4 — OBL-24's coverage enum is self-referential

The "artifact coverage" obligation's value set is hard-coded to THIS
artifact's four fixture classes, so the row cannot express generic modality
coverage — it audits the machinery that built it. *Status:* recorded;
excluded from the native-records proof for that reason; next sealed
generation parameterizes the class set or renames the row to its actual
scope.

## E5 — OBL-30 accepted caller bookkeeping contradicting supplied facts

Inverting every `compatibility_verdicts` boolean, or shrinking
`selected_record_ids` while leaving `undispositioned_compatible_record_ids`
stale, left the sealed verdict byte-identical VALID: the projections and
the disposition ledger were trusted, not derived, though fully derivable
from other supplied fields. *Status:* fixed on the audited surface by
tighten-only closures (verdict/projection agreement; derived disposition
exhaustiveness — `grounded-0_4/closures_0_4.json`); regression-pinned. The
intent tuple remains non-authoritative BY CONTRACT (disclosed); the register
carries it as `inert_disclosed`.
*2026-08-16 hardening:* the frozen engine's acceptance of contradicted
bookkeeping is immutable and remains reachable only through the
non-evidentiary conformance namespace; the supported route that bypassed
the closures (top-level `decide`, deep-scan csf_0479d1a9) is WITHDRAWN, so
every supported decision returns the closure-tightened
`audited_behavior_class`. `grounded-0_4/test_public_surface.py` pins an
inverted-verdict case tightening to `BINDING_OR_CONFLICT` on the supported
surface.

## E6 — Recorded contract non-closures (unchanged from ACCEPTANCE.md)

The RFC 6901 pointer-cap conflict, the wrapper transcript evaluator's
missing semantic re-derivation step, and the unreachable OBL-30 MALFORMED
disjunct stand as recorded. They are contract-design items for the next
sealed revision, not implementation defects.

## E7 — No applicability/abstention mechanism

Every operation demands its full fact profile; a host whose records lack an
obligation's semantics must fabricate values (and eat false holds — 133 of
390 clean records, a 34.1% false-hold rate, when OBL-17 was forced onto
acknowledgment-less lifecycles) or refuse outside the contract.

*Status (updated 2026-08-17): the practical gap is closed on the live surface;
only the contract-level declaration remains deferred.* This entry previously
read as though no abstention mechanism existed, which understated what ships.

A three-state preflight is exported and reproducible today
(`adapters/portable_preflight.py`, `adapters/README.md`):
`READY` (eligibility only, never a pass), `REJECTED_INVALID` (detection), and
`INSUFFICIENT_EVIDENCE` (abstention). Integration is five lines:

```python
from adapters import READY, preflight

result = preflight(native_record, optional_host_fact_profile)
if result.status != READY:
    record_preflight_result(result.as_dict())
    do_not_invoke_engine()
```

Measured against the same 408-record corpus that produced the 34.1% figure
(`adapters/OUTCOME.md`, reproducible with
`python -B adapters/outcome_receipt.py --check`):

| arm | new false holds | clean false-hold rate | total detection |
|---|---:|---:|---:|
| historical forced arm | 133 | 34.1% | 18/18 |
| portable fallback | **0** | **0.0%** | **18/18** |

The exact taxonomy is 192 `READY`, 8 `REJECTED_INVALID`, 208
`INSUFFICIENT_EVIDENCE`. Abstention does not hide defects: **no defective row
is in the insufficient-evidence bucket**, and detection stays at 18/18 while
false holds go to zero. So a third-party host no longer has to fabricate values
or refuse outside the contract — it abstains explicitly and routes those rows
however it chooses.

Two honest limits. First, the fallback is deliberately narrow: WP1 reached its
three-strike boundary at `F-WP1-009`, so this is a preflight for native evidence
plus optional host-produced profiles — **not** a general host adapter, runner,
transcript verifier, replay store, or effect API. `READY` does not authorize
invocation by itself; H1–H6 still bind the integration. Second, abstention is
not free: 208 of 408 rows abstain because timestamps do not establish
acknowledgment semantics, so a host wanting decisions on those rows must supply
the missing semantics.

What remains genuinely deferred is the *contract-level* fix, which needs a new
sealed generation: an explicit `INAPPLICABLE` classification admitted by the
decision table with its own fixture class, so applicability is expressed inside
the sealed law rather than in front of it. Host-side calibration remains
specified at `HOST_OBLIGATIONS.md` H4 and measured in `proof/`.

## E8 — Audited decisions did not identify their governing policy bytes

Found by the 2026-08-12 Deep Security Scan (Intake 10; findings
`csf_e5e9b8cdec13c18cf70c88eb`, `csf_2e9e3a58b7bde4789bf783ba`). The 0.4
audit seal bound the request bytes and the decision-input digest, but
nothing identifying WHICH closure policy, authority register, or engine
sources governed the final class; `closures_0_4.json` loaded from the
adjacent path unpinned. Two checkouts differing only in closure policy
produced indistinguishable audit shapes. *Status:* fixed additively — audit
format `B1-AUDITED-DECISION-0.4.1` seals `governing_authorities` (closure
policy, authority register, and both engine-source digests) into every
audit object, on the error path included. 0.4 objects remain verifiable by
self-zero recomputation under their recorded format string. The repository
commit remains the root that authenticates the digests themselves
([TRUST_MODEL.md](TRUST_MODEL.md)). *Enforcement:* the GOVERNANCE section
of `grounded-0_4/test_grounded_0_4.py` pins each digest to the bytes on
disk and proves the seal covers them.

*Scope (2026-08-13, increment refutation of `f08fa34`):*
`governing_authorities` seals the governing data — closure policy,
authority register, and engine-source digests — not the grounded
evaluation layer (`grounded-0_4/rr_api.py`) that applies them. A checkout
differing only in that evaluator produces audits whose
`governing_authorities` are byte-identical; evaluator bytes are
authenticated by the repository commit root alone, per the commit-root law
in [TRUST_MODEL.md](TRUST_MODEL.md). Admitted erratum; sealing an
evaluator digest into the audit (a format bump) is queued as optional
hardening.

## E9 — Closure evaluator errors failed open to VALID

Same source (finding `csf_2e9e3a58b7bde4789bf783ba`). `closure_findings`
recorded an evaluator error as `fired: false`, so an errored tighten-only
closure contributed nothing and a VALID class stood, with the error visible
only inside `closure_findings` — a consumer reading
`audited_behavior_class` alone saw an authoritative-looking VALID.
*Status:* fixed — on 0.4.1, any closure evaluator error on a VALID decision
yields `AUDIT_INCOMPLETE` (an errored closure might have tightened it);
sealed defect classes stand, because closures only tighten. *Enforcement:*
`governance:evaluator-error-fails-closed` regression in
`grounded-0_4/test_grounded_0_4.py`.

## E10 — Author-increment receipt understates the second-implementation strike count

`second-implementation/receipts/AUTHOR_INCREMENT_RECEIPT_0_1.json` reads
`status: AUTHOR_ATTEMPT_3_FINAL_PATH_A_READY_FOR_FRESH_REFUTER` with
`official_author_strike_count: 2`. That contradicts
`orchestration/refuters/RI5.md`, which is the decisive round **over attempt 4**
and records "DIVERGENCE FOUND — the candidate does not conform. Third strike;
the WP4 package falls back," over 592 confirmed divergences in 4,992
differential probes across five independent mechanisms (binding-pool
membership under a missing member, canonical registry-row derivation,
non-finite constant classification, ERR_JSON/ERR_NUMBER precedence order, and
duplicate keys with lone surrogates).

**Authoritative reading: three strikes, over attempt 4.** `RI5.md` governs; the
receipt's status string is stale.

Recorded rather than rewritten, for the same reason E2, E4 and E5 are: the
receipt's raw SHA-256 is pinned in four places —
`portability/verify_hygiene.py` (`ALLOWED`), `portable/inventory.json`,
`portable/MANIFEST.json`, and it is consumed by
`second-implementation/verify_artifacts.py` as `author-file-hash` rows. Editing
its bytes cascades through all four custody surfaces to correct a status
string that no verifier reads and no published number depends on. The next
sealed second-implementation generation should carry the corrected status at
its own re-bind, when the pins move anyway.

Two related facts remain accurate in the receipt and are **not** stale:
`campaign_gate` is still
`DEFERRED_PENDING_FRESH_CONTEXT_REFUTER_ZERO_DIVERGENCE` and
`house_scale_campaign_receipt` is still `null`. The W3/W4 hardening waves
(`F-WP4-008` through `F-WP4-013`) were applied to the candidate *after* RI5 and
have not themselves been re-refuted, so no zero-divergence fresh-context pass
exists. **No conforming second implementation exists.** That claim, in
`README.md`, is correct.

## E11 — "Sealed" carries two distinct meanings

Two unrelated senses of "sealed" appear across this artifact, and a reader who
carries one into the other's documents will misjudge the artifact's standing:

1. **Digest seal (release sense).** Used throughout `README.md`,
   `ACCEPTANCE.md` and the contracts: fixture packs, receipts and responses
   carry self-zero SHA-256 seals over RFC 8785 JCS canonical bytes, and
   "sealed 0.2/0.3 bytes" means those bytes are frozen and digest-pinned. In
   this sense the artifact is extensively sealed, and that is verifiable here.

2. **Gate 0 capability seal (research-program sense).** Used in the capability
   floor and its evidence bundle: a `CapabilityRecord` reaches
   `seal_status = SEALED` only with a complete source-to-obligation-to-fixture
   chain, an author-separated acceptance, and a bounded gap impact. In that
   sense **nothing is sealed**: `evidence/A1_CAPABILITY_FLOOR_0_1.md` records
   all 28 mandatory obligations as `UNSEALED` with `realization =
   NOT_ATTEMPTED`, `specification = DRAFT`, `test_result = NOT_RUN`, and
   `sealed_count = 0`.

Both statements are true in their own algebra. Neither implies the other, and
in particular a digest seal is **not** evidence of capability realization. The
composed control matrices remain
`FROZEN_AWAITING_EXTERNAL_ACCEPTANCE_0_3`, and OBL-30's admission is recorded
as `CONDITIONAL_ON_FRAME_REACHABILITY_M4_DROPPABLE_AT_BLIND_GATE` even though
the blind completeness gate returned `COMPLETE` with `OBL-30: ADMIT`.

## Authority census (context for E5)

Of 199 schema-required fact fields across the 30 operations: 141 are
semantically referenced by at least one value-comparing predicate, 34 are
referenced only by presence predicates, and 24 are never referenced (10
disclosed non-authoritative, 14 registered as debt). An earlier census
under-counted semantic authority by subtracting every presence-referenced path
globally, which erased 30 fields that also had value-comparing uses; finding
`grounded-0_4/findings/F-WP2-001.md` records the witness and correction. The
machine-checked ledger is `grounded-0_4/authority_register_0_4.json`;
CI-gating both directions is `grounded-0_4/lint_contract.py` L1, and the
generated public view is `grounded-0_4/AUTHORITY_TABLE.md`.
