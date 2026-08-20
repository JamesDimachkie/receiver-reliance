# Errata and recorded defects

E1–E7 entered after the 2026-08-10 external review; E8–E9 after the
2026-08-12 Deep Security Scan (Intake 10); E10–E16 during the hardening
campaign that followed it; E17–E18 during the v1.2.1 release review; E19
after the 2026-08-19 audit.

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

**Independent rediscovery of the third item, with a certificate.** The decision-law
checker in `law/` reached the unreachable OBL-30 disjunct on its own, by search
over all 150 row disjuncts rather than by reading this entry: 149 produced
concrete witnesses, one did not, and the certificate machinery then upgraded that
single empty search to a universal proof. It reports
`OBL-30/MALFORMED_OR_BOUNDARY#12` under certificate `SINGLETON_VALUE_MEMBER` —
`NOT_FUNCTIONAL_BY` fires only when two items of `/facts/excluded_records` share
`record_id` and differ on `exclusion_reason`, and the sealed schema fixes
`exclusion_reason` to the one-member domain `['INTENT_INCOMPATIBLE']`, so no
schema-valid input can satisfy it at any array length. That is PROVEN over the
full schema domain, not bounded, and it matches this entry including its
conditionality on the enum size.

Two consequences worth stating. First, `refuted=1` is the checker's expected
steady state, so it is the *only* refutation the lane may carry silently: any
further move off `refuted=1` is either a new dead row or this one resolved by a
versioned enum extension, at which point the certificate stops applying and the
count falls to 0 without anyone editing a pin. Second, the disposition is
unchanged — this remains a contract-design item, inert within the admitted input
space, misclassifying nothing. `law/README.md` and `law/PROOF_REPORT.md` carry
the derivation.

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
audit object, on the error path included. 0.4.2 extends the sealed set with
both decision-table contract digests (E18). 0.4 objects remain verifiable by
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
receipt's raw SHA-256 is pinned in three places —
`portability/verify_hygiene.py` (`ALLOWED`) and `portable/MANIFEST.json`, and it
is consumed by `second-implementation/verify_artifacts.py` as `author-file-hash`
rows. (An earlier revision of this erratum counted four, adding
`portable/inventory.json`; that file records `path` and `role` only and carries
no digest at all. Corrected at the v1.2.1 publication preflight.) Editing the
receipt's bytes cascades through all three custody surfaces to correct a status
string that no verifier reads and no published number depends on.

**The deferral condition fired during the 1.2.1 hardening campaign, and the
correction was still not made — stated plainly rather than left to be found.**
This erratum used to defer to "the next sealed second-implementation
generation ... when the pins move anyway", and the pins moved twice.

`9243cd2`, the consolidated evidence-rebind event, regenerated the receipt
(`FF22DA0F...` to `CB42DDBF...`) and rebuilt `portable/MANIFEST.json`. It did
**not** touch `portability/verify_hygiene.py`, whose `ALLOWED` digest stayed at
the superseded value; that moved three days later at `af0caf7`, a separate
21-file commit outside the rebind's six-round review. An earlier revision of
this paragraph attributed the `ALLOWED` update to the rebind, which is wrong and
was caught by the v1.2.1 delta review; the two-commit account above is the
measured one. Between those commits `verify_hygiene`'s custody hash for this
receipt did not match the file it names.

The status string and `official_author_strike_count` were left stale through
both. For the rebind, the reason holds: it was scoped to evidence bindings and
reviewed as such across six rounds, and reopening a sealed receipt's semantic
fields inside it would have changed what that review had accepted. For
`af0caf7` there is no such reason — the custody surface was reopened and the
semantic correction simply was not made. Recorded as a second missed
opportunity rather than presented as one deliberate deferral. Until an event
opens the receipt for its own reasons, `RI5.md` governs.

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

## E12 — A published source pin refers to bytes that have since moved

`portability/concurrency/receipts/STATUS.md` publishes four raw SHA-256 values
under "Raw source binding for the current clean v3 receipts" and states that any
change to one of those files invalidates the binding and requires a new receipt.
One of the four no longer matches.

`4ea69dc` bound the clean v3 normative and smoke receipts, with
`portability/concurrency/ladder.py` at
`B5436C851C849CFB2B39A7EC2B35C258E501E3171A2ECD6BE6AF913329CC27E6`. Four changes have moved
it since:

1. `ca1ccfe` changed exactly one line — `AUDITED_FORMAT_VERSION` from
   `B1-AUDITED-DECISION-0.4` to `B1-AUDITED-DECISION-0.4.1`, the F-MATRIX-016
   migration — taking the digest to
   `D40F692AEC6197C005E74F12BE996C860A4FF1A5FF821E828B84CFA1585E044A`.
2. The `pinned_tools` adoption replaced the ladder's bare `git` argv with
   `pinned_tools.git()`, taking it to
   `7CF10CC692FCF938CD69D831FA74C9AD94994073212ACBB75B3F61E57701E798`.
3. The 0.4.2 count-migration completion moved `AUDITED_FORMAT_VERSION` from
   `B1-AUDITED-DECISION-0.4.1` to `B1-AUDITED-DECISION-0.4.2` after `0ff243c`
   moved the audit format itself and left this pin behind -- the hosted
   normative cells rejected every fresh envelope (`audited_envelope_version`)
   until it moved -- taking the digest to
   `CB7D1FA56C50C99576A7B1E717A06E6C902A5262400B5DE0D52143FDBC706C12`.
4. The ERRATA E15 redaction adoption routed the ladder receipt through
   `portability/receipt_paths.py` at its single write boundary, so a new receipt
   no longer records the operator home directory in `runtime.executable` or in a
   controller traceback, taking the digest to
   `CD725088C497E36BA9906DB49104F451ECBB7AA1DCF3C2E3F9627722B81050E3`.

The second and fourth moves are worth stating plainly: the guard this erratum installed is
what surfaced it. The adoption commit ran `verify_receipts`, which failed
`source_pin.errata_current`, so the change could not land without either
disclosing the move or reverting it. That is the difference between a
disposition and a note. `ladder.py` was adopted rather than exempted because its
`git` invocation is provenance evidence for the concurrency receipts, and an
exemption would have left the one harness whose source is published as a receipt
binding resolving its authority from the ambient `PATH`.

The fourth move followed the same law and was surfaced the same way: the
redaction change failed `source_pin.errata_current` on its first run, so it had
to be disclosed here or reverted. The ladder was redacted rather than exempted
because a receipt writer that keeps publishing an account name is the defect E15
exists to stop, and the one harness whose source is itself a published receipt
binding is the worst available place to keep that exception.

The other three pins — `test_ladder.py`, `oracle/oracle.py`,
`oracle/__init__.py` — still equal their published digests exactly.

**The pin is not refreshed.** Rewriting it to the current digest would assert
that these bytes produced the recorded 242,400-envelope, 213.937-second run.
They did not. A stale pin with a disposition is honest; a refreshed pin is a
false provenance claim.

What this does not invalidate: the two receipt files are byte-unchanged and
still bind to their published raw digests, their recorded clean-source HEAD
`8a525b16` is unchanged, and the worker-run and audited-envelope totals still
recompute from the receipts. The oracle projection, the physical cache binding
and the R-CONC-4 refutation all rest on the three unmoved pins.

What it does invalidate: the claim that the *current* `ladder.py` bytes are the
bytes that produced those receipts. Anyone re-running the ladder at this
revision is running the 0.4.2 auditor, not the 0.4 auditor the receipts
recorded. F-MATRIX-016 establishes why such migrations are required — the 0.4.1
and 0.4.2 envelopes keep the frozen six-field surface, so the auditor's seal
recompute and oracle projection hold unchanged over them — but that is an argument about
equivalence, not evidence of re-execution. **That gap closed on 2026-08-19:**
`normative-regeneration-head-2f29e6b-attempt1.json` is a full re-run at the
fourth-move bytes reproducing the recorded totals exactly (32 worker runs,
242,400 audited envelopes), bound with its smoke sibling in
`portability/verify_receipts.py`. The 4ea69dc pin above still stays as
published — it describes which bytes produced the *v3* receipts, and no
re-run changes that.

Enforcement: `portability/verify_receipts.py` now hashes all four published
sources. Three must equal their published digests. `ladder.py` is bound to the
newest digest recorded above, so a further undisclosed move fails the gate
rather than hiding behind the disclosed ones. Two of the four moves were forced
through this disclosure by that guard rather than remembered by an author, which
is the reason the count in this erratum can be trusted at all.
`portability/concurrency/findings/F-CONC-004.md` carries the full record.

## E13 — A replay verifier reported green over a red gate for four commits

`3985356` added two regressions to `proof/test_proof_harness.py`, taking it from
7 tests to 9, and did not migrate the count the eleven-command charter gate
declares. `portability/sandbox/expanded_gate.py` pinned validator `unittest_7`,
which requires exactly `Ran 7 tests`, so
`python -B portability/run_local_expanded_gate.py` exited 1 at gate 8 of 11 and
gates 9 to 11 never executed. Run by hand they were green; the gate as a whole
was red.

Two custody programs should have caught it. Neither could.

`portability/verify_receipts.py` reported `checks=193 failures=0` throughout,
and every one of those checks was true. It replays the stdout recorded in the
sealed gate receipts, and that recorded stdout says `Ran 7 tests`, so the
validator it re-runs agreed with the bytes it was given. A replay verifier
cannot observe a suite that changed after the transcript was captured.

`portability/sandbox/run_sandbox.py` — the arm that runs the same gate inside
the hardened container, and the one check that would have executed the suite
rather than a recording — compared the checkout's branch for equality with
`main` and exited `PREFLIGHT_FAILURE` before touching Docker. On the branch
where the hardening work was happening it could not run at all.

So the gap was structural, not an oversight: the only program that recomputed
was unreachable on the branch under review, and the only program that was
reachable did not recompute.

Repairs, all in the commit carrying this erratum:

- the validator family is parameterized by the count in its name
  (`unittest_<n>`, matching the existing `checks_<n>` convention) and the live
  GateSpec declares `unittest_9`. `unittest_7` survives as era-legacy, reached
  only through `verify_receipts.LEGACY_GATE_VALIDATORS`, so the two SHA-pinned
  gate receipts still replay under the count their own era declared;
- the declaration migrated in the same change everywhere it appears:
  `run_sandbox.EXPECTED_OBSERVED`, `matrix/plan.json`,
  `verify_receipts.HOSTED_ERA_EXPECTATIONS`, and the historical witness freeze
  in `test_sandbox.py` that pins seven pre-F015 receipt digests;
- `run_sandbox.py` keeps `main` as the sole release-authority branch and admits
  verification branches, which their receipts record by name. Narrow authority
  did not require unreachable verification;
- `test_sandbox.py` derives the true test count from
  `proof/test_proof_harness.py` by parsing it and fails if the declaration
  disagrees. A declared count that nothing derives from the artifact is a pin
  waiting to go stale;
- `portability/verify_live.py` is new and is now the first command the README
  tells a third party to run. It re-executes every charter gate at the current
  bytes, holds the live output against both declared authorities — the gate's
  own validators and the matrix plan's expectations — and compares it with what
  the sealed receipt recorded. It prints which evidence it recomputed and which
  it could only replay, and it exits non-zero on any divergence from the sealed
  receipt that nobody declared.

Same class as E12, and that is the point. E12 is a pin that stopped describing
the bytes it names; this is a transcript that stopped describing the suite it
names. Both were invisible because the verifier over them replays recorded
evidence. Replay and recompute are different guarantees and this artifact now
says which one it is offering.

## E14 — Seven receipt provenance pins went stale and the verifier failed undisclosed

Both admitted WP5 receipts carry a `source_sha256` map recording the bytes that
produced their profiling run. The hardening campaign changed four of those
sources, so seven pin rows across the two receipts stopped matching the current
bytes: `grounded-0_4/rr_api.py` (W1 withdrew the bare `decide` route, W3 added
runtime byte-authentication), `grounded-0_4/authority_surface.py` (W3 register
nesting and vocabulary authentication), `grounded-0_4/rr_batch.py` (W3 batch
overlimit cap and OBL-30 R1–R3 pool bindings), and
`perf/sidecar/profile_robustness.py` (the W3-adapters/W4 rebind). Every other
pin in both receipts still matches exactly, including all frozen contract,
fixture and engine bytes.

`python -B perf/sidecar/verify_receipts.py` therefore exited 1 with
`checks=126 failures=7`, and nothing surfaced it. `perf/SIDECAR.md` listed the
command under "Verification" with no caveat, and `portable/gate.py` carried the
same failure as `sidecar-receipts exit=1`, holding that gate at
`checks=9 failures=1`. Two red gates at tip, undisclosed, for the same reason in
different places.

The pins are not rebound. They record which bytes produced a recorded run, and
rewriting them would assert that the hardened sources produced the 2026-08-12
numbers; no run at current bytes has been recorded. They also could not be
rewritten without breaking custody, because they live inside receipt bodies whose
raw digests are pinned by the verifier's own `ADMITTED` table, by the 61-file
portable manifest, and by each receipt's self-zero seal.

Enforcement: `SOURCE_PIN_ERRATA` in `perf/sidecar/verify_receipts.py` declares
each drifted (receipt, source) pair with both digests. Each such row now yields
two checks — the erratum must quote the digest the receipt still publishes, and
the current bytes must equal the recorded post-erratum digest — so the historical
pin cannot be quietly rewritten and a further undisclosed move fails. The command
reports `checks=134 failures=0`. `perf/sidecar/findings/F-WP5-008.md` carries the
record and `perf/SIDECAR.md` now states the command's scope.

**The red window that followed is closed.** The F-WP5-006 supervision
repairs and A5's migration moved three pinned sources and the manifest
schema, so the command reported `checks=133 failures=7` — enumerated in
`perf/SIDECAR.md` while it stood — until the 2026-08-19 regeneration event
recorded fresh receipts at those bytes and rebound `ADMITTED`, the portable
inventory and the manifest. No `SOURCE_PIN_ERRATA` rows were spent on that
window: this page's rows exist for sources never intended to re-run, and
those were changed precisely so a fresh run could be recorded.

Same class as E12 and E13.

## E15 — Tracked files contain the maintainer's home directory

**Fifty-two** tracked files in this public repository record an absolute path
under the maintainer's home directory. The leak is an account name, not a
secret, and it has no evidentiary purpose — the interpreter identity that
matters is the implementation, version and build, each recorded in its own
field — but a published file that names someone's home directory undermines the
artifact it is meant to support.

**This erratum said "ten" until the v1.2.1 publication preflight, and ten was
wrong.** One case-insensitive grep returns the true set. That is the more
serious defect: not the account name, but a disclosure page a reader can falsify
faster than they can read it. The count is corrected here, the disposition is
stated per class rather than per hand-listed file, and the declaration is
checked by a program instead of asserted by prose.

The fifty-two split into two classes, and the class decides the treatment:

| Class | Count | What they are | Treatment |
|---|---|---|---|
| **Frozen** | 39 | Digest-pinned by another tracked file, by the 61-file portable manifest, or as a `candidate_files` row of the author-increment receipt: the seven `profile-windows-*` and ten `sidecar-parity-*` robustness receipts, five concurrency receipts, four charter-gate receipts, `N48-independent-refuter-20260811.json` and its memsample, the five `F-ORACLE-*` findings, `RI2`–`RI4`, `perf/PROFILE_BASELINE.md`, `adapters/fixtures/parent_corpus_408.jsonl`, and `second-implementation/PROVENANCE.md`. | **Cannot be edited without destroying what they attest** — but the enforcement is not uniform, and the difference matters. **Twelve** are refused by a running program: `portability/verify_receipts.py`, `portability/verify_hygiene.py`, `perf/sidecar/verify_receipts.py::ADMITTED`, the 61-file portable manifest, the author-increment receipt, or `adapters/outcome_receipt.py`. The remaining **twenty-seven** are pinned by a published digest table inside another tracked file — `perf/COST_MODEL.md`, `orchestration/CRITICISM_ADJUDICATION.md`, `portability/oracle/PROVENANCE.md`, `portability/concurrency/receipts/STATUS.md` — which a reader can check by hand and no program reads. That is a real gap, and it is stated here rather than smoothed over: a prose pin detects nothing on its own. |
| **Recorded** | 13 | Not digest-pinned, but each is a record of an observed run or a historical witness held on purpose: three concurrency receipts, `orchestration/MATRIX.md`, `FUZZ_CAMPAIGN.md`, the two `fuzz-streams/T1*_SOL.md` stream logs, `N48-POST-F-MODEL-003-SUMMARY.md`, and the five-file sandbox cluster — the four `F-SANDBOX-018`–`021` findings plus `portability/sandbox/test_sandbox.py`, whose `FROZEN_WINDOWS_REPOSITORY_SOURCE` is a synthetic constant, **not** a string any hosted receipt recorded (the hosted sandbox receipt records `/home/runner/work/...`; an earlier revision of this erratum claimed otherwise and was wrong). | **Deliberately not redacted, for two different reasons.** Eight of the thirteen are records of an observed run, and scrubbing one would make the repository's account disagree with what was observed — the failure class E12, E13 and E14 exist to prevent. The five-file sandbox cluster is not that: it records no observation. Its reason is that the constant is cross-pinned across five files whose published byte lengths and digests are *derived from it*, so redacting it means recomputing six figures across the cluster; it is a frozen historical custody surface, not a witness. Both are reasons to leave it; only the first is about evidence, and conflating them would be the kind of tidy sentence this page exists to avoid. (These files are not immutable — their prose is corrected when it goes stale; it is the recorded observation that is not rewritten.) |

No file in the set can be redacted without breaking a digest another file
publishes, rewriting a record of an observed run, or recomputing a cross-pinned
cluster. That is why the number of redactions is zero.

The forward half is a real fix and was made when the class was confirmed. The
new charter-gate receipt this campaign produced repeated the defect —
`portability/run_local_expanded_gate.py` recorded `sys.executable` verbatim into
`runtime.executable` and into every `executed_argv` — so the runner now redacts
the home directory to `<HOME>`, preserving path structure below it, and the
receipt was regenerated rather than shipped with the leak.

**The forward half was not complete, and an earlier revision of this erratum said
it was.** Three further writers were still producing new instances:
`portability/matrix/receipt.py` wrote `sys.executable` verbatim into
`environment.runtime.executable` and expanded the plan's `{python}` template to
the same absolute path in the recorded `argv`; `perf/profile.py` wrote it into
`system.executable`; `perf/sidecar/_evidence.py` wrote it into `runtime`, into the
real `command` argv, into `executed_argv` and into the temporary pycache root of
every WP5 receipt; and `portability/concurrency/ladder.py` wrote it once per run,
once per worker run, and wrote a checkout path inside a controller traceback. The
matrix writer escaped the count above only because matrix receipts are generated on
hosted runners, whose home directory is not the maintainer's — a maintainer-local
run that got committed would have leaked immediately.
`adapters/outcome_receipt.py` records no argv at all, so naming it as a
generator that records argv safely was simply wrong. `run_sandbox.py` does build
its argv from repository-relative plan entries.

**All four now redact, through one implementation rather than four.** `_redact` was
not ported into the other writers; it moved to `portability/receipt_paths.py` and
`run_local_expanded_gate.py` calls it there, so there is one rule and not five
copies to drift. Each writer applies it to the whole receipt tree at its single
write boundary rather than to an enumerated field list, because the field nobody
enumerated — a traceback, a child argv, a cProfile function label — is exactly the
one that ships the leak. The match is case-insensitive and separator-insensitive,
because the gate's pattern is; a case-sensitive redactor would have reported a
guarantee the gate then falsified. `portability/test_receipt_redaction.py` holds
each writer's real boundary against the gate's own compiled pattern under a
synthetic home, and fails if a second home-directory redactor appears anywhere in
the tracked tree. Residue: redaction rewrites the home directory as
`pathlib.Path.home()` spells it, so an 8.3 short name, a UNC spelling, a
substituted drive or a symlink to the same directory is a different string and is
not redacted. The gate remains the backstop — it recomputes over tracked bytes, so
an unredacted spelling surfaces as a gate failure rather than as a silent leak.

**Scope, stated because `git clone` ships more than HEAD.** The count, the
classes and the gate all describe *tracked files at the published commit*. The
repository's history carries more: a scan of the whole object database finds the
pattern in roughly eighty blobs across fifty-five paths, including
`portability/receipts/local-expanded-gate-hardening-6776332.json`, the leaked
charter-gate receipt this erratum describes as regenerated. It was regenerated
and removed from the tip — it was not removed from history, and the honest
release posture is the full release history unsquashed. So the sentence above
means the leak is not in what you check out; it does not mean the leak is not in
what you cloned. Filtering history is not planned: it would rewrite published
commits, which this project does not do.

**What is new in 1.2.1: the disclosure is now a control.** This erratum
previously ended by saying nothing enforced it, and justified that with the
claim that a repository-wide scan "would have to admit ten frozen exceptions,
which makes it a table of known values rather than a control". Both halves were
wrong — the exceptions number thirty-nine, and a table of known values IS a
control when a program compares it against current bytes and fails on any
difference:

```bash
python -B portability/test_home_path_disclosure.py
```

Expected: `home-path-disclosure: {"declared": 52, "failures": 0, "frozen": 39,
"observed": 52, "recorded": 13}`. It recomputes — it enumerates the tracked
files, reads each one, and compares the observed set against the declaration
carried in its own source. A new instance under the maintainer's Windows home
fails as `UNDECLARED`; a declared instance that stops carrying a path fails as
`STALE`, because a disclosure that silently shrinks is also a wrong disclosure.
**The first revision of this gate was itself falsified, which is worth
recording.** Its boundary was "a separator or the end of the file", so the bare
home directory at the end of a line, inside a closing JSON quote, before a
markdown backtick, or followed by a space or comma all went unseen — and that is
precisely the shape `%USERPROFILE%` and `pathlib.Path.home()` produce, making an
environment dump the likeliest future leak and the one case the gate could not
see. The v1.2.1 adversarial audit demonstrated it end to end with two tracked
probe files that the gate passed at 52/0. The boundary is now "not a word
character", proven against all three shapes; the declared count is unchanged at
fifty-two, because nothing currently tracked needed the looser rule.

**Residuals that remain, stated so the next reader does not have to find them:**
the pattern is account-specific, so a generator running under a POSIX `/home`, a
different account name, or a display-name home directory introduces an instance
this gate does not see; it decodes UTF-8 with `errors="ignore"`, so a UTF-16 or
other non-UTF-8 file is effectively skipped (none is tracked today, checked);
it matches literal text only, so an encoded representation is invisible — this
repository's own receipts store captured subprocess output base64-encoded in
`stdout_b64`/`stderr_b64`, so a locally-generated receipt whose captured output
named the home directory would pass (every base64 run of forty characters or
more in every tracked file was decoded and scanned: zero instances today); it
reads the worktree rather than the index; and **it is not yet wired into any
hosted workflow**, so today it runs when a person runs it — which is the same
"control outside the decision path" shape that reopened `ADOPTION.md` A5, and it
should be a step in the robustness workflow at the next owner-authorized
workflow edit. The gate narrows the residual E15 has always carried; it does not
close it.
**Negative proof:** both arms were exercised at the commit that added the gate —
an injected undeclared file exits 1, and removing a declared file from the
enumeration exits 1 on both the `STALE` and the count check. The gate assembles
its own search pattern from fragments so that it is not itself an instance of
what it searches for.

## E16 — The frozen conformance surface declares four things it never checks

Four scan findings land inside `baseline-run/implementation-output-*`. Those
bytes are the accepted implementation and its recorded evidence and never change,
so each is dispositioned with an additive external gate,
`baseline-run/verify_conformance_authority.py`, which reports
`checks=32 failures=0 declared_divergences=4`.

**The emitters synthesize PASS-shaped evidence** (`csf_9237eb71`). Both
`emit_manifest_0_2.py` and `emit_manifest_0_3.py` write `check_counts`,
`failures: 0` and `result: "PASS"` as literals and never invoke a conformance
runner — the only mentions of `run_conformance` are a path string and a hash of
the harness file. A changed or broken implementation can therefore be hashed into
freshly generated artifacts that still say PASS. The gate executes both suites and
requires the declared numbers to equal the observed ones. Read the scope exactly:
this makes the declaration *checkable*, it does not make the emitters safe to run
on their own, and an emitter run without the gate proves nothing about
conformance.

**Bytecode can execute in place of manifested source** (`csf_56621d97`). The
implementation manifests enumerate `b1_capabilities.py` and `pcb_runner.py` and
nothing else, while `-B` suppresses bytecode *writes* and not *reads*. A
`__pycache__` entry whose recorded mtime and size match the source is accepted by
CPython, so it can execute without either manifested digest changing. The gate
compiles each manifested source and requires any acceptable cached bytecode to
round-trip to the same code object. Proved by planting a forged `.pyc` that
matched the source's mtime and size and carried different code: the gate exits 1
and names the file to remove.

**Fixture authority is loaded but never compared** (`csf_a68931d8`). The runners
load the supplemental packs and base success on replay failures without ever
checking the packs' own `authority_pins`. Comparing them shows two rows really do
disagree: both packs pin
`contract_raw_sha256 = 0FA31FD9…` and `matrix_raw_sha256 = 5A750006…`, while the
current sealed supplemental control bytes are `6B2CAD02…` and `B369777E…`. The
pins date from an earlier draft of the supplemental generation. Neither side can
move — packs and control JSONs are both frozen sealed bytes, and the packs'
digests are pinned in turn by the implementation manifest, the 60-file portable
manifest and the WP5 receipts — so the divergence is declared with both exact
values and enforced, and a third value on either side now fails. The packet and
projection pins do match, and the gate also asserts the pack cardinality the
runners never assert, so a pack cannot be emptied while printed counts fall and
exit status stays zero.

**The subprocess toolchain is executed unverified** (`csf_b7bc7ed8`).
`--subprocess` launches `baseline-run/toolchain/python.exe` with no digest check
at invocation; the RUNBOOK documents a manual download-and-hash step, and nothing
enforces it. At these bytes the directory does not exist, so the mode cannot run
at all and no unverified interpreter can be launched — the gate reports that
absence explicitly instead of skipping quietly. If a toolchain is ever placed
there, the gate requires a digest manifest and verifies every file against it
before the mode may be called available. The code path inside the frozen runner is
unchanged and still performs no check of its own; that residual is the reason this
is a disposition and not a repair.

## E17 — A receipt validator's verdict depended on an ambient variable

`portability/matrix/receipt.py::_runnable_git_binding_error` compared a
receipt's recorded commit to `os.environ["GITHUB_SHA"]` inside the leaf
validator. An environment variable is not an artifact: the clause was silent
everywhere the variable was unset — every local run, the README's third-party
verification command, and every matrix child, because `SAFE_ENV_KEYS` strips
it — and unsatisfiable where it was set against sealed historical evidence,
because a workflow's current commit can never equal a head recorded before
it. The same committed bytes therefore verified 267/0 on a developer host
while the hosted robustness-verification workflow failed all nine of its
cells, and with `GITHUB_SHA` set to the empty string every runnable row was
rejected with a cause that named the recorded sha rather than the
environment.

Same family as E13: a verifier must compute its verdict from declared
inputs. E13's verifier could not see its subject; this one deliberated over
a subject that changed with the shell it ran in. (Receipts still *record*
the ambient `GITHUB_SHA` at capture time and must be internally consistent
with it — recording evidence is not the defect; deciding on the validator's
own environment was.)

*Status:* fixed (`e27e331`) — the expected commit is an explicit
`expected_sha` parameter with no default on the leaf validator, so no caller
can drop the authority by omission; passing `None` is an explicit statement
that the caller holds no external authority and asserts nothing beyond the
receipt's self-consistency. Only the `summarize` CLI reads the environment,
once, and refuses to run (exit 2) when neither `--workflow-sha` nor a
non-empty `GITHUB_SHA` supplies the commit its receipts must belong to.

*Enforcement:* `RunCurrencyAuthorityTests` in
`portability/matrix/test_receipt.py` (suite 54 → 60) holds the receipt
fixed and varies the environment — the axis the rest of the suite
deliberately does not vary. Hosted witness: run 32225089695, the first
green robustness-verification on `main`.

## E18 — The audit seal identified its governing policy but not its decision law

Found during the 2026-08-18 release review; fixed the same night
(`0ff243c`). E8 introduced `governing_authorities` so that decisions
produced under different governing bytes would be distinguishable by seal.
It sealed the closure policy, the authority register, and the two engine
source files — and not the contracts holding the thirty operations the
engine actually executes. Two parties running different decision tables
therefore emitted byte-identical `governing_authorities`, and a recipient
holding an envelope could not tell which law decided it.

Provable by construction rather than by attack: the four digests were
computed from four files, none of which was a contract, so no change to the
table could change the seal. A local tamper was always caught — both
contracts are engine-manifest rows and `import receiver_reliance` verifies
them before serving a decision — so the gap was never local forgery. It was
cross-party identification, which is the purpose an audit envelope exists
to serve.

*Status:* fixed additively — `AUDIT_FORMAT` moved to
`B1-AUDITED-DECISION-0.4.2`, whose `governing_authorities` gains
`decision_table_contract_sha256` and `composed_contract_sha256`, both read
under the same pinned-read law as the existing authorities. 0.4, 0.4.1, and
0.4.2 objects each remain verifiable by self-zero recomputation under their
recorded format strings. Read the scope exactly: the seal *identifies* the
law, it does not *authenticate* it — nothing is signed
([TRUST_MODEL.md](TRUST_MODEL.md)), and anyone who can author an envelope
can author a matching seal.

*Enforcement:* four mutation arms in `grounded-0_4/test_grounded_0_4.py`
(517 → 521 checks) prove each new digest sits inside the seal. The count
migration the format move required is itself part of this record: the
migration commit moved its pin list by hand and left two program-era pins
behind — E12's third recorded move and the `run_sandbox.py` count mirror,
both closed (by disclosure and by derivation respectively) in `5c29965`.

## E19 — The measurement that justified the observability seam was reproducible from no committed byte

Found by the 2026-08-19 audit. The seam's stated reason to exist was a
measured claim: a request-length proxy "under-charges 43 of the 136 requests
in its own measured corpus at p50," and the instrumented path "costs 1,165 ns
per decision … 0.033% of a 3.5 ms decision." Those five numbers appeared in
exactly two places, `README.md` and the comment above `DecisionObservation`,
and in no test, receipt, script or JSON. `receiver_reliance/test_observe.py`
pins what the seam *does* — byte-identity observed and unobserved, the record's
contents, that an observer cannot mutate a decision, this host's effective CPU
tick — and measured none of it. Nor was "136" reconcilable with any published
corpus size: the documented counts are 124 semantic fixtures and 372 audited
calls.

The corpus was real and was always derivable; nothing published said so. It is
the 112 entries of the 0.2 semantic pack, the 12 of the 0.3 pack, the three
`examples/`, and nine protocol-error requests — 136. The proxy was real too,
and was **not** published: an affine `0.10 + 1.20 × (bytes / 1024)` ms fitted
at the design phase on the maintainer's host, living in a module that never
shipped. So the artifact held every other result to mechanical re-derivation
from published bytes and shipped a surface justified by a number that met that
standard nowhere.

Re-deriving it found a second defect inside the first, and the second is the
one worth keeping. The count is not a property of the artifact; it is a
property of the artifact *and the host's speed*, and steeply so, because the
proxy is denominated in absolute milliseconds and most of the corpus prices
within a quarter of the line. Four consecutive runs on one host on 2026-08-19
returned 74, 78, 79 and 84 at a median decision of 3.37–3.42 ms; an earlier
sitting on the same host under different load returned 83 to 110 at ~4.5 ms;
scaled to the 2.936 ms profile `perf/COST_MODEL.md` records the derivation
returns the forties, and a little below that it returns none. So the original
43 was an honest measurement of one afternoon, published in a voice that
implied a constant. The worst ratio is no better — it scales with the host too.

What does survive the host is the ratio between the worst- and best-priced
request. Scaling every measured cost by the same factor leaves that quotient
where it was, so it is the one figure a second host can hold this one to:
1.86–2.15x across the 124 semantic fixtures, 3.56–4.83x across all 136. It is
also the claim the seam actually rests on — a proxy affine in length cannot
track an engine whose cost is not — and it is what the prose now leads with.

*Status:* fixed additively. `receiver_reliance/bench_observe.py` splits derived
from measured the way `deployment/derive_admission_numbers.py` does. `--corpus`
rebuilds the 136 requests from committed bytes and prints their composition and
a digest; `--corpus --check` fails on drift from the composition it declares.
`--measure` re-derives the under-charge and the seam's overhead on the caller's
host, publishing the design-phase proxy so the count is recomputable, and
prints the host-invariant spread and the near-the-line population beside the
count so the count cannot be read as a constant. The overhead half is measured
by isolating the three `perf_counter_ns` reads, the two `process_time_ns` reads
and the record build that the instrumented path adds, rather than by A/B
against `decide_audited`: at a microsecond against a millisecond, a paired A/B
reports noise. Both README passages now carry host, date and interpreter, and
point at the script.

One further number went the same way and is recorded rather than quietly
dropped. The passthrough was published at "24 ns," and building the isolation
for it showed the method cannot resolve a figure that size: paired deltas
against a same-shape function straddled zero in every run. `--measure` now
reports the range and names it unresolved, and the README states the branch
instead of a number. A measurement that reports its own resolution is the
smaller correction here; publishing the midpoint of a range containing zero
would have been the same defect as E19 itself, one release later.

*Enforcement:* `--corpus --check` is in the README re-verification battery, so
a corpus that stops being the one the prose names fails a listed command. It is
deliberately **not** a twentieth row in the charter gate or the hosted matrix:
adding a gate row is the evidence-regeneration event E12 and E14 describe, and
this correction did not earn one. Stated so a reader does not assume CI covers
it — a clone does, on the listed command. `--measure` measures on the caller's
host and stays hand-run, the same standing `derive_admission_numbers.py --cost`
has. What this erratum does not do is make a measured number portable: it makes
one re-derivable, and dates the run it came from.

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
