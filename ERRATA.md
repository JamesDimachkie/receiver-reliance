# Errata and recorded defects (post external review, 2026-08-10)

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

## E6 — Recorded contract non-closures (unchanged from ACCEPTANCE.md)

The RFC 6901 pointer-cap conflict, the wrapper transcript evaluator's
missing semantic re-derivation step, and the unreachable OBL-30 MALFORMED
disjunct stand as recorded. They are contract-design items for the next
sealed revision, not implementation defects.

## E7 — No applicability/abstention mechanism

Every operation demands its full fact profile; a host whose records lack an
obligation's semantics must fabricate values (and eat false holds — 133 of
390 clean records, a 34.1% false-hold rate, when OBL-17 was forced onto
acknowledgment-less lifecycles) or refuse outside the contract. *Status:*
host-side calibration is specified in `HOST_OBLIGATIONS.md` H4 and measured
in `proof/`; next sealed generation should admit an explicit
INAPPLICABLE declaration with its own fixture class.

## Authority census (context for E5)

Of 199 schema-required fact fields across the 30 operations: 111 are
semantically referenced by predicates, 64 are presence-only, 24 are never
referenced (10 disclosed non-authoritative, 14 registered as debt). The
machine-checked ledger is `grounded-0_4/authority_register_0_4.json`;
CI-gating both directions is `grounded-0_4/lint_contract.py` L1.
