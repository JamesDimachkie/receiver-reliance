# Concurrency receipt status

## Historical v1 evidence — stale

All v1 receipts are retained only as provenance. They use
`RR-CONCURRENCY-LADDER-1` / `RR-CONCURRENCY-WORKER-1` and do not bind the
admitted clean-room oracle API.

| Receipt | Recorded status | Current classification |
|---|---|---|
| `normative-correction-attempt1.json` | `PASS` | stale / superseded |
| `smoke-correction-attempt1.json` | `PASS` | stale / superseded |
| `smoke.json` | `INVARIANT_FAILURE` | stale harness-failure evidence; never a PASS receipt |

No v1 status or hash supports the current concurrency claim.

## Historical v2 evidence — stopped

`normative-clean-oracle-attempt2.json` is **STOPPED / REJECTED**, not a CUT
divergence. `RR-CONCURRENCY-LADDER-2` compared audited 0.4 physical envelopes
directly with the clean oracle's projected sealed-response bytes. R-CONC-3
adjudicated that `INVARIANT_FAILURE` as a harness-layer mismatch. The compact
adjudication is in `../findings/F-CONC-003.md`. The receipt is preserved but
supports neither a CUT defect claim nor current validation.

## Current v3 contract

A current receipt must use `RR-CONCURRENCY-LADDER-3`, contain
`RR-CONCURRENCY-WORKER-3`, and keep these obligations distinct:

- exact concurrent library/process physical lines against cached one-record
  isolated accepted `rr_batch.py` output, explicitly marked non-semantic; and
- independently parsed and JCS+LF-validated audited 0.4 envelopes whose
  projected `sealed_response` exactly equals
  `portability.oracle.FixtureOracle.expected_record(raw)`.

The physical cache binding and oracle `fixture_binding_sha256` are separate.
The independent semantic check validates the outer envelope's strict JSON,
exact top-level fields/types/version, JCS+LF spelling, self-zero audit seal,
request hash, and exit/behavior agreement with the oracle-validated sealed
response. It does **not** independently validate the meaning of every other
nested `audit` member, including `engine_generation`; that is an explicit
outer-audit nonclaim.

### Raw source binding for the current clean v3 receipts

| Role | Source | Raw SHA-256 |
|---|---|---|
| harness | `../ladder.py` | `B5436C851C849CFB2B39A7EC2B35C258E501E3171A2ECD6BE6AF913329CC27E6` |
| focused tests | `../test_ladder.py` | `926D75C5C64A3D44D18FB40D85CA59CE3AC0BF2600C12ACE2BCBF749EF364630` |
| clean oracle implementation | `../../oracle/oracle.py` | `2148F0C9C4ED38692B9C6658EC48CDD9628688E6C1708345C89A44AB91A05F17` |
| clean oracle public API | `../../oracle/__init__.py` | `747CF1373F63C6DFB7F1A01744EB0B9A9D91FED17F127FFD0C510AF924AA3BFF` |

These hashes bind the raw source set used by the current clean v3 normative
and smoke receipts. Any change to one of these files invalidates that binding
and requires a new receipt; prose-only changes do not rewrite the recorded
run.

**ERRATA E12 — the `../ladder.py` digest above is stale, and stays stale.**
`4ea69dc` bound these receipts. Two changes have moved `ladder.py` since:
`ca1ccfe` (`AUDITED_FORMAT_VERSION` `B1-AUDITED-DECISION-0.4` to `0.4.1`, the
F-MATRIX-016 migration) and the `pinned_tools` adoption, which replaced its bare
`git` argv. The file now hashes to
`7CF10CC692FCF938CD69D831FA74C9AD94994073212ACBB75B3F61E57701E798`. The pin is
not refreshed, because refreshing it would assert that the current bytes
produced the recorded run. What that invalidates and what it does not is set out
in [`../findings/F-CONC-004.md`](../findings/F-CONC-004.md) and `ERRATA.md` E12.
`portability/verify_receipts.py` now enforces all four rows of this table: the
other three must equal the current bytes exactly, and `ladder.py` is bound to
the post-erratum digest, so a second undisclosed move fails the gate.

## Current clean v3 evidence

### Normative

`normative-release-audit-head-8a525b1-attempt3.json`:

- raw SHA-256:
  `B1782A43E4E4615569948953FFC45659BF0A820BEB67136F73FEDFDEAFE29998`;
- clean source HEAD
  `8a525b167b95a3b6b512282938199eba09594a24`, with zero status bytes;
- `RR-CONCURRENCY-LADDER-3` / `RR-CONCURRENCY-WORKER-3`, status `PASS`;
- all declared levels `P = 1, 2, 4, 8, 16, 32`, 200 requests per caller,
  and the `P = 16, 32` 1,000-request soaks passed in both library and process
  modes across two identical-seed runs;
- all 16 paired cases were byte-identical; all 32 worker runs had equal
  isolated-physical and concurrent aggregate hashes; and 242,400 actual
  audited envelopes passed independent sealed-response projection;
- physical cache binding
  `AC74DD0932D4476E6374DE7F1A8596C9173A909FBB21845D8AFD13DE3E3A74BD`;
- oracle binding
  `78FC43470C9AD4C41932CD38926F8430A004D02FE18E065D3DD6BE59A5A4B80B`;
- no host ceiling; CPython 3.14t was `INFRA_UNAVAILABLE`;
- 213.937 seconds elapsed. The audit launched no concurrent validation
  workload during this local run; resource fields are not a universal
  performance baseline.

### Focused smoke

`smoke-release-audit-head-8a525b1-attempt3.json`:

- raw SHA-256:
  `8CBA926DFB61B2C729C5CEAB95FF89350B99AFAF03809CBDDEAF6B8AC7719030`;
- clean source HEAD
  `8a525b167b95a3b6b512282938199eba09594a24`, with zero status bytes;
- `RR-CONCURRENCY-LADDER-3` / `RR-CONCURRENCY-WORKER-3`, status `PASS`;
- lowered, nonnormative bounds: `P = 1, 2`, five requests per caller, both
  modes, two identical-seed runs, no soak, and no free-threaded probe;
- 17.109 seconds elapsed. The focused package suite was rerun separately
  against the same source set and passed 15/15.

The smoke receipt is executable preflight evidence only. It cannot substitute
for the normative receipt.

### Independent refutation

R-CONC-4 returned **NO DEFECT / no new evidence**. It independently rebuilt
all deterministic input sequences and all 11 isolated physical envelopes;
recomputed every caller request, order, output, and aggregate hash across 16
cases / 32 runs; and recomputed the semantic projection digest for all 242,400
occurrences. It reproduced the receipt, physical-cache, and oracle bindings
listed above. The corrupted sealed-response, outer exit/class, and physical
comparator negatives failed in their intended layers. Every repeat-2 cleanup
had zero lingering PIDs/threads, and the CPython 3.14t `INFRA_UNAVAILABLE`
probe hashes reproduced. R-CONC-4 retained the outer-audit nonclaim above.

The ladder/oracle sources and deterministic workload contract refuted by
R-CONC-4 are unchanged in the clean receipts. The clean rerun reproduced the
same physical-cache and oracle bindings and the same 242,400-envelope total.
R-CONC-4 did not independently re-execute the new wall-clock/resource fields,
which remain observational and outside the semantic claim.

## Superseded dirty v3 evidence

`normative-correction-attempt3.json` (raw SHA-256
`98786009478343F4A7D84FC594A67C7E09BE64483865123AC1C73E4144525699`) and
`smoke-correction-attempt3.json` (raw SHA-256
`E552F98CDF741A7CAEBA20F950FCCE7DACC5378F880EAD49EE10884159DD2B7F`)
remain as historical evidence only. They record baseline HEAD `4e788d2`, a
dirty worktree, and—in the normative run—coexecution with the compact model
explorer. Their resource fields are stress observations, not isolated
performance evidence. They no longer support the current clean-source claim.

The current clean receipts supersede that custody limitation without deleting
the history.
