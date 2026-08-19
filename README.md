# Receiver-reliance baseline — conformance suite and reference implementation

Release 1.2.1 — the hardening point release of the 1.2 composed
generation. License: Apache-2.0 (see `LICENSE`;
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
clean clone at `72efd11`, the tenth commit of this release, in
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

## Repository map

What each top-level directory holds, and which class it belongs to. **Live
surface** is code you can call or run today. **Frozen evidence** is sealed bytes
that may not change by charter — defects there are handled by additive guards
and `ERRATA.md` dispositions, never by editing the bytes. **Harness** is
verification machinery that produces or checks receipts. **Records** are the
process history that claims elsewhere cite.

| Directory | Class | What is in it |
|---|---|---|
| `receiver_reliance/` | live surface | The installable package. `engine_manifest.json` pins all eleven engine files by byte length and SHA-256; importing verifies every one before executing any of them and refuses to import on drift. |
| `grounded-0_4/` | live surface | The audited decision layer — `decide_audited`, the authority register, the closure policy, the lint gate, the 521-check regression. This is the one supported evidentiary route. |
| `adapters/` | live surface | The stdlib-only three-state preflight, its calibration playbook, and the outcome receipt that reproduces the 18/18-detection-at-0.0%-false-holds result. |
| `portable/` | live surface | The self-contained bundle: manifest, builder, gate, CLI, threat model, operator runbook. |
| `examples/` | live surface | The three handoff records [EXAMPLE.md](EXAMPLE.md) decides end to end — clean, inconsistent, unchecked revocation. |
| `deployment/` | live surface, off by default | One operator-enabled control: a pre-engine byte bound that narrows this deployment's contract in exchange for bounding what an oversized request can cost. Unset it is byte-identical to its absence; set, it rejects requests the published contract declares valid, which [deployment/README.md](deployment/README.md) states as the price rather than a caveat. Not part of the supported surface; obligation at [HOST_OBLIGATIONS.md](HOST_OBLIGATIONS.md) H7. |
| `baseline-run/` | frozen evidence + harness | The frozen 0.2 and 0.3 engines, their sealed contracts and fixture packs, both conformance runners, and the RUNBOOK — plus `verify_conformance_authority.py`, the additive gate that actually executes both suites because the frozen manifest emitters write `failures: 0` and `PASS` as literals (`ERRATA.md` E16). |
| `supplemental-0_3/` | frozen evidence | The sealed 0.3 comparator contract and composed capability matrix, the two supplemental fixture packs, the hash-pinned prior-art snapshot, and the candidate-blind completeness verdict. |
| `second-implementation/` | frozen evidence | The author-increment attempt, its provenance and non-exposure record, and thirteen recorded findings. Twenty-four of these files — plus `orchestration/REIMPLEMENTERS_GUIDE.md` — are the `candidate_files` of a published receipt whose verifier checks their hashes, including its own path, so this tree is attempt evidence rather than live infrastructure and is not edited as such. The candidate itself did receive the W3/W4 hardening changes, which is recorded in [ERRATA.md](ERRATA.md) E10 and visible in `git log -- second-implementation/` ([ADOPTION.md](ADOPTION.md) A4). |
| `access/` | frozen evidence | The sanitized implementer packet and the shared-domain vocabulary projection schema: the public projection an author-separated implementer is given, and nothing beyond it. |
| `evidence/` | frozen evidence | Byte-exact releases of the two custody files the candidate-blind completeness reviewer read that did not otherwise ship here, with the recipe that checks them against their pins. The reviewer's other two files already sit in `supplemental-0_3/`. |
| `portability/` | harness | Five validation lanes — a finite behavioral model, an independent no-read oracle, deterministic live transports, a bounded concurrency ladder, and the hosted matrix with its container sandbox — plus the custody verifiers and `verify_live.py`, the recompute gate this README tells you to run first. |
| `perf/` | harness | Cost model, profiling campaigns, and the sidecar supervisor with its transport envelope, adversarial child, and receipt verifier. |
| `proof/` | harness | The applicability arms, the synthetic corpus and truth set, and the scoring harness behind `proof/RESULTS.md`. |
| `law/` | harness | The machine-checked coherence of the sealed decision law itself, as distinct from any implementation's conformance to it: 872 properties over the composed 30 operations, each labelled proven over the full schema domain or proven only over a stated finite abstraction. Its `refuted=1` is [ERRATA.md](ERRATA.md) E6's third non-closure, rediscovered by search with a universal certificate. |
| `replay-corpus/` | harness | Twelve publicly documented agent-system failures adapted into fact profiles and replayed through the real preflight and the real audited API, 27 records against pinned classifications. It demonstrates classification, not efficacy: no incident claims RR would have altered its source event. |
| `fuzz/` | harness | The deterministic seeded campaign. It contributes 50,000 of the 100,000-identity aggregate; the other half ran as the batch campaign (`perf/batch_campaign.py`, `orchestration/BATCH_50K.md`). Together: 67,599 unique raw byte strings, zero findings. |
| `orchestration/` | records | Ledgers, the standing criticism-adjudication protocol, the external-validation and portability-validation reports, the minimized refuter reports, and `REIMPLEMENTERS_GUIDE.md`. |
| `continuation-specs/` | drafts | Proposed generation-0.5 core and semantic drafts. **Not adopted, not implemented, not evidence** — each carries that banner at the top, and nothing in this release depends on them. |
| `.github/workflows/` | harness | The hosted conformance, portability, and robustness gates. Which of them fires on which branch is recorded, including what does not fire, in [ADOPTION.md](ADOPTION.md) A2. |

The root documents divide the same way. [TRUST_MODEL.md](TRUST_MODEL.md) is
canonical for what every seal and receipt may be read as claiming and who is
assumed to consume it; [HOST_OBLIGATIONS.md](HOST_OBLIGATIONS.md) is the
caller's half of the contract; [ERRATA.md](ERRATA.md) records known defects and
how each is enforced; [ADOPTION.md](ADOPTION.md) is the recorded-and-unfixed
list with a treatment and an owner per row; [ACCEPTANCE.md](ACCEPTANCE.md)
records what was accepted and under which protocol; [WITHHELD.md](WITHHELD.md)
ledgers what is deliberately not published and why; [EXAMPLE.md](EXAMPLE.md) is
one handoff decided end to end; [DIAGRAMS.md](DIAGRAMS.md) draws the
boundary, the decision law, the request path and the evidence chain as
eleven diagrams; [SECURITY.md](SECURITY.md) is how to report a
defect.

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
abstention bucket. The calibration cliff this creates is drawn in
[DIAGRAMS.md](DIAGRAMS.md#a4--the-preflight-and-the-calibration-cliff).

Be clear about its scope: WP1 stopped at a three-strike boundary
(`F-WP1-009`), so this is a preflight, **not** a general host adapter, runner,
transcript verifier, replay store, or effect API. Read
`adapters/README.md` for the exact taxonomy and `adapters/CALIBRATION.md` for
the playbook.

**Then satisfy the host contract.** [HOST_OBLIGATIONS.md](HOST_OBLIGATIONS.md)
is the testable division of labour — state truthfulness, atomicity,
derive-don't-assert, applicability calibration, input binding, effects,
request admission. H1–H7 remain yours regardless of preflight status. For decisions you intend to rely
on, call `decide_audited` (see the grounded 0.4 layer below), not the frozen
response path.

Honest status on adoption: `TRUST_MODEL.md` records **zero external or sibling
code consumers** to date. Nothing here has been load-tested by an integrator
other than its author, and the applicability limits in `ERRATA.md` E7 are the
first thing a new consumer should read. What is recorded-and-unfixed between
this artifact and one you could adopt -- with the treatment and owner for each
item -- is ledgered in [ADOPTION.md](ADOPTION.md).

## The supported surface

`grounded-0_4/test_public_surface.py` is this artifact's operative definition
of what it supports: 38 checks pinning the withdrawal of the bare decision
route, fact binding on the audited surface, closure authority over the frozen
verdict, authenticated authority-register and closure-policy bytes, and the
batch transport's finite work ceiling. What that suite pins is supported. What
it does not pin is reachable, not promised. This section states the callable
surface, the exceptions, the response shape, and the value domains, so an
integrator does not have to read source to find them.
[TRUST_MODEL.md](TRUST_MODEL.md) remains canonical for what any of it may be
read as claiming; nothing here adds a guarantee.

### What you may call

| Import surface | Names |
|---|---|
| `receiver_reliance` | `__all__` is exactly `decide_audited`, `decide_audited_observed`, `response_bytes_observed`, `verify_audit_seal`, `closure_findings`, `derive_record_references`, `AUDIT_FORMAT`, `DecisionObservation`, `ENGINE_MANIFEST_SHA256`. Also public and outside `__all__`: `ENGINE_MANIFEST` — the parsed `engine_manifest.json`, keys `format_version` (`RR-ENGINE-MANIFEST-1`), `file_count` (11), `total_byte_length`, `manifest_sha256`, `files` — and `__version__`. |
| `receiver_reliance.conformance` | `execute` only. Explicitly non-evidentiary; see "What is not supported". |
| `adapters` | `__all__` is exactly these ten: `preflight`, `process_jsonl`, `PreflightResult`, `PreflightIssue`, `READY`, `REJECTED_INVALID`, `INSUFFICIENT_EVIDENCE`, `RESULT_STATUSES`, `RESULT_FORMAT_VERSION`, `FACT_PROFILE_FORMAT_VERSION`. Also public and outside `__all__`: the `portable_preflight` submodule. |
| `grounded-0_4/rr_api.py` | No `__all__`. Public names: `decide_audited`, `closure_findings`, `derive_record_references`, `conformance_execute`, `authority_for_operation`, `AUDIT_FORMAT`, `GOVERNING_AUTHORITIES`, `RuntimeIntegrityError`, plus the loaded-module handles `authority_surface`, `b1`, and `pcb_runner`. The three handles are the byte-verified engine internals: reachable by construction, deliberately not an API. |
| `grounded-0_4/rr_batch.py` | `serve(source, sink)`, `response_bytes(raw_line)`, `main()`, `BatchRecordLimitError`. |

`AUDIT_FORMAT` is the audit envelope's `format_version` string.
`ENGINE_MANIFEST_SHA256` is `ENGINE_MANIFEST["manifest_sha256"]` — the digest
of the manifest that gated the import, which is what a third party compares
against the repository's. The literal value is deliberately not repeated here:
any engine change rotates it, and a stale digest in this README would be a new
claim gap of exactly the kind this section exists to close. It is pinned in
[portability/THIRD_PARTY_REPRODUCTION_20260818.md](portability/THIRD_PARTY_REPRODUCTION_20260818.md).

`decide_audited(request)` takes a Python object **or** exact wire bytes and
returns the audited envelope described below. `bytes` is the wire form; a
`bytearray` or `memoryview` is not, and takes the object path, where it is
refused as `ERR_JSON`. An object is canonicalized under the frozen wire limits
— 16,777,216 request bytes, 128 nesting levels, 100,000 aggregate members or
items, integers within the IEEE-754 safe range — and a request that cannot be
canonicalized is refused rather than truncated or coerced.

`closure_findings(obligation_id, decision_input)` returns the tighten-only
findings for one obligation without running a decision. Its surface is narrow
by construction: `closures_0_4.json` defines closures for OBL-30 alone, so
every other obligation ID returns an empty list — and an unknown obligation ID
returns an empty list as well, indistinguishably. It does not validate the ID.

`derive_record_references(facts)` returns the sorted, deduplicated,
64-item-capped record identifiers present in a fact profile. Its signature
carries a second parameter, `prefix`, which the implementation accepts and
never reads; passing it changes nothing. Treat the function as single-argument
until that parameter is either removed or given meaning.

`authority_for_operation(operation)` takes an obligation ID or an operation
handle and returns the register row set for it, where each field carries a
`status` of exactly one of four values: `semantic`, `presence_only`,
`inert_disclosed`, `inert_registered_debt`. The register is re-read and
re-authenticated on every call.

`verify_audit_seal(envelope)` recomputes an envelope's `audit_sha256` over its
own bytes, with that field zeroed, and returns whether it matches. It is total —
anything that is not a sealed envelope returns `False` rather than raising — so
it is safe to call on bytes you did not produce. **What a `True` proves:** these
envelope bytes are internally intact and were sealed by something implementing
this contract. **What it does not prove:** who produced it, when, or that the
facts it judged were true. Nothing here is signed, deliberately
([TRUST_MODEL.md](TRUST_MODEL.md)), so a party who can author an envelope can
author its seal. This detects corruption and tampering in transit; it is not
authentication, and `receiver_reliance/test_audit_seal.py` pins that limit with
a re-forging test that must succeed.

`decide_audited_observed(request, observer=None)` and
`response_bytes_observed(request, observer=None)` are `decide_audited` and the
transport's response line with one measurement handed to a caller-supplied
`observer` after the result exists. The observer is an **argument**: there is no
install call, no module-level slot, and no environment variable that turns one
on, so two callers in one process cannot instrument each other and a caller that
passes none is not instrumented at all. `observer=None` is the default and is a
passthrough — one identity test, then the same call, no clock read taken
(measured at 24 ns on Windows/CPython 3.12).

**Observability here is a property of the wrapper, not of the engine.** No
sealed envelope records that an observer was attached, because no part of a
decision depends on one: the same request yields the same envelope bytes and the
same `audit_sha256`, observed or not. An envelope is not evidence about who was
watching, and `receiver_reliance/test_observe.py` is the proof rather than the
assertion — it re-decides `examples/`, all 124 committed semantic fixtures in
both wire and object form, seven protocol-error surfaces, six object-refusal
surfaces and 155 deterministic `fuzz/fuzz.py` cases, with and without observers,
and compares JCS bytes. This is the second attempt at this seam. The first was
refuted by its own byte test: its observer *returned* the envelope, a host added
a correlation id, and the response moved from 1,774 bytes to 1,799.

**What an observer sees.** One `DecisionObservation` per decision — a
`NamedTuple` whose every field is an `int`, a `str` or `None`: `decision_class`
and `exit_code` (the envelope's own), `request_bytes` and `response_bytes`,
and four spans, `ingest_ns`, `decide_ns`, `serialize_ns`, `wall_ns`, plus
`cpu_ns`. It holds no reference to the envelope, the response bytes, or the
request, so an observer that keeps records keeps no request content.

**What an observer cannot see.** Request or response content, obligation,
operation handle, record identifiers, digests, closure findings, witness trace
— none of it is in the record, and none of it is reachable from one. Nor can it
see inside the frozen engine: `ingest_ns` is the wrapper's own pre-engine work
and nothing more, because decoding, canonicalization and the size ceiling all
happen behind `decide_audited`. Today the wrapper admits nothing, so `ingest_ns`
is the cost of reading a length. `serialize_ns` and `response_bytes` are `None`
from `decide_audited_observed`, which forms no response bytes. `cpu_ns` is
process-wide, and its granularity is the platform's: measured on
Windows/CPython 3.12 the process-CPU clock advances once per 15,625,000 ns
against a decision of roughly 2.8–3.5 ms, so nearly every record on that host
reports zero — while `time.get_clock_info("process_time").resolution` there
*declares* 100 ns. No constant is published for this, because the declared one
is the number that is wrong; `test_observe.py` measures the effective tick
wherever it runs and prints it.

**What an observer cannot do.** Alter control flow, or change a byte. Its
return value is discarded, so it cannot substitute a decision by returning one.
Every exception it raises is discarded, of any class — including
`KeyboardInterrupt` and `SystemExit` — so that "an observer cannot change a
decision" is total rather than true for the classes someone remembered. Two
consequences, disclosed rather than hidden: a broken observer is invisible to
the caller and must carry its own error channel, and an interrupt delivered
while the observer runs is swallowed with it, a window an observer widens by
blocking. Engine exceptions are **not** caught: the suppression covers the
observer and nothing else. Nothing here writes a file, opens a socket, or reads
the environment (`ERRATA.md` E17).

**What this is not.** A sandbox. One frame above an observer there is nothing
but the record and the observer itself — the wrapper releases the envelope
before the call, and the suite pins that — but an observer that walks `f_back`
reaches the wrapper and the decision it holds. That is not a hole this seam
opened: a host able to pass an observer was already able to rebind
`decide_audited` outright. The guarantee is that the seam hands over no
reference and takes no authority, not that Python withholds authority the caller
already had, and `test_observe.py` pins the limit with a frame-walking observer
that must **succeed** — the same shape as the re-forging test above. An
untrusted observer belongs in another process. Nor is it a budget: a blocking
observer delays its caller and nothing here bounds it.

**Why it exists, and what is deliberately absent.** This artifact prices a
decision by request length, and that proxy under-charges 43 of the 136 requests
in its own measured corpus at p50 (measurement phase, 2026-08-19). An admission
bound built on a proxy that is wrong a third of the time is a bound on paper, so
the measuring lands first and alone. Absent by decision, not oversight: no
counters, no histograms, no ring buffer, no aggregation, no emitter, no
per-predicate tracing, no memory profiling, no sampling policy, no observed
`serve` loop — a host that wants an observed stream calls
`response_bytes_observed` once per line. The instrumented path costs 1,165 ns
per decision on Windows/CPython 3.12 with a no-op observer, which is 0.033% of a
3.5 ms decision; the observer's own work is the host's, and is not in that
number.

`rr_batch.serve(source, sink)` is a supported transport, not merely a file
with recorded bounds. It reads one request per physical line from a binary
source, writes exactly one JCS response plus LF per line, and flushes each one.
Every line goes through the same `decide_audited` path and is sealed
identically, so a malformed line is a per-request protocol error rather than a
stream failure.

### What you may catch

- **`ImportError`**, from `import receiver_reliance`, when any of the eleven
  manifested engine files does not match `engine_manifest.json` by byte length
  and SHA-256. The message names the path, the expected length and digest, and
  the found ones. This fires before any engine byte executes.
- **`RuntimeIntegrityError`** (subclass of `RuntimeError`), defined in
  `grounded-0_4/rr_api.py` and not re-exported by the package. It is what the
  grounded layer raises when a pinned file fails byte authentication. Through
  the package you will not see it for those eleven files, because the manifest
  gate raises `ImportError` first; you see it when `grounded-0_4/rr_api.py` is
  imported directly, which is what `rr_batch.py` does. That it is not on the
  package's export list is a gap in the surface, not a claim that the exception
  is private.
- **`AuthorityRegisterError`** (subclass of `ValueError`), plus `KeyError` for
  an unknown operation selector and `TypeError` for a non-string one, from
  `authority_for_operation`.
- **`ValueError`** from constructing a `PreflightResult` with a status outside
  `RESULT_STATUSES`.
- **`BatchRecordLimitError`** is exported but does not cross the transport
  boundary: `serve` catches it and converts it into a sealed
  `ERR_BATCH_RECORD_LIMIT` response.

`decide_audited` and `preflight` return rather than raise for caller data.
Across the inputs exercised here — wire bytes, `bytearray`, `memoryview`,
`str`, `int`, `float`, `None`, list, empty dict, `set`, a self-referential
dict, and a dict nested past the depth ceiling — every call produced an
envelope or a result. That is measured totality over those inputs, not a proof
of totality.

### What you get back

`decide_audited` returns an **audit envelope** wrapping the frozen engine's
**sealed response**. They are different objects with different authority: the
sealed response is the frozen engine's verbatim output and is preserved
byte-for-byte; the envelope's `audited_behavior_class` is the 0.4 surface's
verdict, which closures may tighten but never loosen. Six keys, always present:

| Key | Value domain |
|---|---|
| `format_version` | Exactly `AUDIT_FORMAT`. Closed. |
| `sealed_response` | The frozen response object, verbatim. Two shapes; see below. |
| `exit_code` | The frozen engine's exit status: `0`, `1`, `2`, or `3`. |
| `audited_behavior_class` | Closed six-value set: `VALID`, `MALFORMED_OR_BOUNDARY`, `BINDING_OR_CONFLICT`, `OMISSION_OR_INCOMPLETE`, `AUDIT_INCOMPLETE`, `PROTOCOL_ERROR`. A consumer switching on this field must handle all six ([TRUST_MODEL.md](TRUST_MODEL.md)). |
| `audit` | The audit object; keys below. |
| `audit_sha256` | 64 uppercase hex: the self-zero seal recomputed over the whole envelope with this field zeroed. |

The `audit` object. Four keys are unconditional on every path; the rest are
path-conditional, and their absence is meaningful:

| Key | When present | Value domain |
|---|---|---|
| `request_raw_sha256` | Always | 64 uppercase hex over the exact request bytes, or null when no request bytes existed — an object that failed canonicalization, or a batch record that never terminated. |
| `engine_generation` | Always | Exactly `composed-0.3-frozen`. Closed. |
| `governing_authorities` | Always | Closed six keys, each 64 uppercase hex: `closure_policy_sha256`, `authority_register_sha256`, `engine_capabilities_sha256`, `engine_runner_sha256`, `decision_table_contract_sha256`, `composed_contract_sha256`. These are the bytes that governed this decision (`ERRATA.md` E8, E18). The grounded evaluator's own bytes are **not** among them; they are authenticated by the commit root alone. |
| `decision_input_sha256` | Always | 64 uppercase hex over the JCS bytes of `decision_input`, or null when the request never reached classification. |
| `object_request_error` | Only when a Python object could not be canonicalized | Closed: `ERR_JSON`, `ERR_NUMBER`, `ERR_LIMIT`. Its presence means refusal, not classification. |
| `errors` | Only when the sealed response is not `ok` | The sealed error array, each entry `{code, pointer, message, precedence}`. One error per response, by the deterministic error law. |
| `first_match_predicates` | Only when the sealed response is `ok` | Closed three keys — the three defect classes — with boolean values. **At most one is true.** This is the short-circuited evaluation order: after a match, later classes read false because they were not evaluated. It is not the same field as a fixture entry's `first_match_predicates`, where more than one can be true (`baseline-run/RUNBOOK.md`); do not read one as the other. |
| `matched_class_witness` | Only when the sealed response is `ok` | Array of atoms from the matched class predicate: `{op, pointers}`, or `{op: "not", of: ...}`. Empty when the **sealed** class is `VALID`, there being no matched predicate to witness — including when a closure then tightened the audited class to a defect, because the witness traces the frozen predicate table and not the closures. That evidence is in `closure_findings`. |
| `record_references` | Only when the sealed response is `ok` | `derive_record_references` over `decision_input.facts`: sorted, deduplicated, at most 64 strings. This is the derived list the sealed response lacks. |
| `record_references_truncated` | Only when the sealed response is `ok` | Boolean; true exactly when the derived set exceeded the 64-item cap, so the cap is disclosed rather than silent. |
| `closure_findings` | Only when the sealed response is `ok` | Array, empty when nothing fired. A fired entry is `{closure_id, fired, tightens_to, statement}`; an errored entry is `{closure_id, fired, evaluator_error}` with the error string truncated. **Three** closure IDs reach a caller here — `OBL-30-C1`, `-C2`, `-C3` — because the sealed `closures_0_4.json` defines closures for OBL-30 alone and `closure_findings` returns exactly those. Three further OBL-30 identifiers, `-R1` through `-R3`, exist as runtime bindings inside the evaluator and are **not** enumerated by the sealed closure-policy digest; that gap is a disclosed residual, not a fourth-to-sixth closure you can call. An errored closure on an otherwise-`VALID` decision makes the class `AUDIT_INCOMPLETE` (`ERRATA.md` E9). |
| `transport_error`, `request_prefix_sha256`, `request_prefix_bytes` | Only from `rr_batch`, and only when a record crossed the physical-line ceiling without terminating | `transport_error` is `ERR_BATCH_RECORD_LIMIT`. The prefix fields report the digest of the bytes actually consumed and that count, so the refusal names what it saw without claiming a digest of a request it never received in full. |

The sealed response has two shapes, distinguished by its own `format_version`.
The **core** shape (`PCB-RUNNER-RESPONSE-0.2`) carries `format_version`,
`request_id`, `ok`, `result`, `errors`, `output`, `exit_code`,
`receipt_sha256`; `output` is null on a protocol error and otherwise carries
the class at `result_object.behavior_class`. The **wrapper** shape
(`B1-WRAPPER-SEMANTIC-RESPONSE-0.2`) additionally carries `configuration`
(`B1` or `B1-ATTENTION`), `operation_handle`, and `obligation_id` at top level,
seals under `response_sha256` rather than `receipt_sha256`, and puts the class
at `output.payload.behavior_class`. In both shapes `result` is `PASS`, `FAIL`,
or `INCOMPLETE`.

### Exit codes

The frozen engine's status appears in three places and means the same thing:
`exit_code` in the audit envelope, the second element of `conformance.execute`'s
tuple, and the process status of the stdio runner. `0` is `VALID`; `1` is any of
the three defect classes; `2` is a protocol error; `3` is reserved for
`ERR_INTERNAL`. The fuzz campaign's invariant is that process and response exit
codes agree and lie in `{0,1,2,3}` (`fuzz/README.md`). **The audited class is not
derivable from the exit code:** a closure that tightens `VALID` to a defect
leaves `exit_code` at `0`, because the sealed response is preserved verbatim.

`rr_batch` is framing, not a gate. Its process status is `0` after a normally
consumed stream, including a stream whose every line was a protocol error; each
request's status lives in that request's envelope. It returns nonzero only for a
transport failure.

The adapters CLI is a gate, and has exactly two statuses: `0` when every emitted
result is `READY`, `2` otherwise. An empty or blank-only stream is `2`, with one
`INSUFFICIENT_EVIDENCE` row carrying `PREFLIGHT_STREAM_EMPTY`, so an exit-status
check can never read "no evidence supplied" as "all records READY".

### The preflight result, and its issue codes

`preflight(record, fact_profile=None)` returns a `PreflightResult`: `status`,
`record_id`, `family`, `obligation_id`, `native_evidence_sha256`,
`profile_checked`, `issues`. `as_dict()` adds `format_version` and renders
`issues` as objects. `status` is one of the three values in `RESULT_STATUSES`,
resolved by the fail-closed precedence law — `REJECTED_INVALID` over
`INSUFFICIENT_EVIDENCE` over `READY` — across every control layer that ran, so
`issues` may mix layers and a code does not by itself determine the status. A
`READY` result carries no issues. `profile_checked` is true only when profile
validation actually ran, never merely because a profile was supplied.

Each `PreflightIssue` is `{code, pointer, message, remediation,
evidence_pointers}`. Only `code` is a stable machine surface; `message` and
`remediation` are prose. The code set holds **57** values today, grouped by the
four calibrated record families (`REF`/OBL-02, `SCOPE`/OBL-03,
`SUPERSEDE`/OBL-15, `LIFECYCLE`/OBL-17) plus the shared envelope, stream, and
fact-profile layers: 11 envelope/stream/family, 11 `REF`, 11 `SCOPE`, 6
`SUPERSEDE`, 8 `LIFECYCLE`, 10 profile. The authoritative list is the string
constants in `adapters/portable_preflight.py`.

Closed today does not mean frozen: unlike the sealed 0.2/0.3 bytes, this list is
live-surface code and a calibration change may extend it. It is not a contract;
it is what the current bytes emit. `adapters/CALIBRATION.md` is the playbook for
the mappings behind it, and those mappings cover only the four families —
everything else abstains as `PREFLIGHT_FAMILY_UNCALIBRATED`.

### What is not supported

- **A bare `decide` route.** Withdrawn (`ERRATA.md` E2/E5). The package exports
  no `decide` and `grounded-0_4/rr_api.py` defines none; the public-surface
  suite pins both absences so the route cannot silently return.
- **`receiver_reliance.conformance`.** `execute(request)` runs one request
  through the frozen engine and returns `(response, exit_code)` byte-faithful to
  the stdio runner. It exists so the conformance suites, the perf harnesses, and
  ports can reproduce frozen behavior. Its sealed response binds no decision
  facts and applies no 0.4 closure, so it is not evidence of a decision — the
  namespace is named for reproduction on purpose.
- **Anything the public-surface suite does not pin.** The engine-internal module
  handles on `rr_api` (`b1`, `pcb_runner`, `authority_surface`), every
  underscore-prefixed name, and the harness, verifier, and record trees under
  `orchestration/`, `portability/`, `perf/`, `proof/` and `fuzz/` are reachable
  and are not an integration API.
- **`deployment/`.** An operator-enabled admission bound, off by default and
  pinned by its own suite rather than by the public-surface suite. Enabling it
  rejects requests this contract declares valid — the derived contract maximum
  is 3,392,691 bytes against a 4,399-byte corpus maximum, a factor of 771 — so
  it narrows the deployment's contract instead of widening the engine's. It
  bounds input size, not the cost of a request it admits, and it is not a
  security boundary. [deployment/README.md](deployment/README.md) states the
  trade; [HOST_OBLIGATIONS.md](HOST_OBLIGATIONS.md) H7 states the obligation.
- **`continuation-specs/`.** Proposed drafts: not adopted, not implemented, not
  evidence. Fields named only there describe a generation that does not exist in
  this release.
- **Any surface as adversarial-grade.** `TRUST_MODEL.md` records zero external or
  sibling code consumers to date. Nothing above is a security, interoperability,
  or efficacy claim; it is a description of what the current bytes expose.

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
re-examination. The final round (45 designed probes plus
70,000 randomized grammar and totality cases) found no implementation
defect: no input crashed, exceeded the output limit, or broke a seal.

To be precise about what "acceptance" means here: the reviewer's formal
verdict in every round, including the last, was REJECT-with-findings. It
never issued a sign-off. The loop ended under a pre-stated stopping rule
when the final round found zero implementation defects and its sole
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
byte-pinned and replayable. Its properties are checkable: one integrated
decision table spanning all 30 operations, exact byte behavior in two
execution modes, competence mutations that kill metadata-pattern-matching
implementations, paired wrapper arms for ceremony control, and a published
defect-to-regression review record. **Nothing here integrates with the
adjacent systems named above.** No adapter, fixture, schema mapping, or test
for any of them exists in this tree, and none is claimed: a host that
establishes a session, keeps a transparency log, or runs a policy engine still
assembles the fact profiles this engine classifies, by its own means. The
descriptions above are of published surfaces as documented, read in August
2026; they are orientation for a reader, not a compatibility statement and not
a comparison this artifact can adjudicate.

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
  (`B1-AUDITED-DECISION-0.4.2`, ERRATA E8/E9) additionally seals the
  governing closure-policy, authority-register, engine-source, and both
  decision-table contract digests into every audit, discloses
  record-reference truncation explicitly, and
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

`grounded-0_4/test_grounded_0_4.py` (521 checks) pins parity with every
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
hash-bound manifest. **Run this one first.** It re-executes the
eleven-command charter gate at the bytes you have checked out and states
plainly which evidence it recomputed and which it could only replay:

```bash
python -B portability/verify_live.py
```

Expected: `verify-live: gates=11 passed=11 declared_era_divergences=3
undeclared_divergences=0 failures=0`. The three declared divergences are
real and deliberate — the sealed close receipt recorded 504 grounded
checks, 7 lint-gate checks and 7 proof tests, and the current suites have
521, 9 and 9. Each is declared in `verify_receipts.LEGACY_GATE_VALIDATORS`,
so the sealed transcripts still replay under their own era while the live
gate enforces current counts. An *undeclared* divergence is a defect, and
this program is what turns it into a red exit instead of a silent green.

Then the two custody verifiers, which re-derive the recorded chain from
bytes:

```bash
python -B portability/verify_receipts.py
```

```bash
python -B portability/verify_hygiene.py
```

Expected: `verify-receipts: checks=267 failures=0`, then `HYGIENE_PASS`.

The conformance surface has its own authority gate, because the frozen manifest
emitters write `failures: 0` and `result: "PASS"` as literals without running
anything (`ERRATA.md` E16):

```bash
python -B baseline-run/verify_conformance_authority.py
```

Expected: `conformance-authority: checks=32 failures=0 declared_divergences=4`.
It executes both suites and requires the declared counts to equal the observed
ones, refuses bytecode that would execute in place of a manifested source,
compares the supplemental fixture packs' authority pins against the sealed
control bytes, and refuses to call the subprocess mode available unless a
digest-verified toolchain is present. The four declared divergences are the two
pack pins that genuinely disagree, in both packs; E16 states why neither side can
move.

Read what these two do and do not establish: they bind committed receipt
bytes, rehash the sources those receipts name, and re-run recorded
transcripts through the gate validators. They cannot tell you the artifact
still passes its own gates, because the transcripts were captured in the
past. `verify_live.py` exists because that distinction was not merely
theoretical here: commit `3985356` added two proof-harness tests and left
the charter gate declaring seven, and the live gate was red for four
commits while `verify_receipts` reported green — truthfully, on the
recorded bytes. `ERRATA.md` E13 records it.

The separated-evidence report is
[orchestration/PORTABILITY_VALIDATION.md](orchestration/PORTABILITY_VALIDATION.md).
It records the full hosted chronology — four red runs, each adjudicated
into a pinned harness finding, before the green one — and the exact claim
scope: validation holds within the executed environments and declared
finite bounds, and nowhere else.

## The decision law itself: what is proven, and what is not

Everything above establishes that implementations match the contract. It says
nothing about whether the **contract** is coherent. [law/](law/README.md) checks
that directly, against the sealed contract bytes rather than any
implementation's behaviour: `python -B law/verify_law.py` reports

```text
verify-law: obligations=30 properties=872 proven=766 bounded=105 refuted=1 errors=0
```

Every property carries exactly one status word, and the difference is the whole
point. **PROVEN** means over the full schema domain: positive results are
witnesses that validate against the sealed `decision_input_schema` branch and
evaluate true in two independent shipped engines, and structural results are
arguments whose every premise was machine-checked from sealed bytes. So proven,
for all 30 composed operations: classification is total and terminating with no
fall-through to an undeclared default; error selection is a strict total order
over ten distinct precedences and UTF-8 pointer order; no closure row names
`VALID` as its target, so the closure layer cannot emit `VALID` for any input;
90 defect rows and 149 of 150 disjuncts carry an executed witness; 20
contract-structure invariants hold, including the pin tying the loaded 0.2 bytes
to the digest the 0.3 supplement names as its inheritance base; and both shipped
engines agreed on all 40,907,363 evaluations.

**PROVEN-BOUNDED** means over a stated finite abstraction, and 105 results are
that rather than proven. Behavioural closure monotonicity and "no unclassified
input" are sampled through the real `decide_audited`, not universally argued.
Where a witness search came up empty the report says "no witness found", never
"unreachable". None of it reaches the wire layer, the parser, effect receipts,
transcripts or wrapper parity, which are outside the model and named as outside
it — and none of it is evidence of efficacy, security or novelty. A coherent
decision law is not a useful one, and [TRUST_MODEL.md](TRUST_MODEL.md) still
governs what any of this may be read as claiming.

The `refuted=1` is the expected steady state, not a failure. The checker
independently flagged OBL-30 / `MALFORMED_OR_BOUNDARY` disjunct #12 as
unreachable and produced a universal certificate: `NOT_FUNCTIONAL_BY` needs two
items of `/facts/excluded_records` that share `record_id` and differ on
`exclusion_reason`, and the sealed schema fixes that field to a one-member enum.
That is [ERRATA.md](ERRATA.md) E6's third recorded non-closure, reached by search
over 150 disjuncts rather than by reading the errata — 149 produced witnesses,
one did not, and the certificate machinery upgraded that single negative to a
proof. It is self-maintaining: extend the enum in a future sealed revision and
the certificate stops applying and the count drops to 0 on its own. Any other
move off `refuted=1` is a new dead row.

The full run takes about eight minutes and needs `jsonschema`, so what sits in
the matrix is `law/verify_law.py --structural-only`: the 26 table-level
properties that need neither, which double as a drift detector over the eleven
sealed files the lane pins.

Alongside it, [replay-corpus/](replay-corpus/README.md) adapts twelve publicly
documented agent-system failures — eight from Anthropic's August 2026 risk
report, two from AgentDojo, two from MAST — into fact profiles and replays 27
records through the real preflight and the real audited API against pinned
classifications (`python -B replay-corpus/replay_incidents.py`). Read its claim
narrowly: it demonstrates that RR *classifies* an adapted record a particular
way. No incident claims RR would have prevented, detected or altered its source
event, ten of the twelve fabricate at least one schema-required field, and each
`METHOD.md` states exactly where judgment entered.

## Contributing / re-verification

The highest-value additions are adversarial, and both invited classes now
have recorded first attempts. A deterministic seeded campaign ran on
2026-08-10 across two harnesses: `fuzz/fuzz.py` contributed 50,000 case
identities and `perf/batch_campaign.py` the other 50,000, for a
100,000-identity aggregate with 67,599 unique raw byte strings and zero
findings (`orchestration/FUZZ_CAMPAIGN.md`, `orchestration/BATCH_50K.md`). A coverage-guided
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
re-verify what is here, run the conformance suite (the in-process mode runs
from a clean clone; the sealed subprocess-ABI mode needs the separately
reproduced `baseline-run/toolchain/python.exe`, and
`baseline-run/verify_conformance_authority.py` reports its absence rather than
skipping it), then re-derive every seal per the RUNBOOK, then, from the repository root, run
`python -B grounded-0_4/test_grounded_0_4.py`,
`python -B grounded-0_4/lint_contract.py --gate`,
`python -B grounded-0_4/test_lint_gate.py`,
`python -B receiver_reliance/generate_engine_manifest.py --check`,
`python -B receiver_reliance/test_engine_manifest.py`,
`python -B receiver_reliance/test_audit_seal.py`,
`python -B receiver_reliance/test_observe.py` (which re-decides every
committed corpus with and without an observer and compares JCS bytes),
`python -B portability/test_home_path_disclosure.py` (which recomputes
`ERRATA.md` E15's disclosure against current bytes),
`python -B deployment/test_admission.py` (25 tests over the off-by-default
admission profile, including the arm that proves enabling it rejects a request
the frozen engine seals `ok`),
`python -B law/verify_law.py --structural-only`,
`python -B replay-corpus/replay_incidents.py`, and the two custody
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
