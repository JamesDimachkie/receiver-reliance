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

### Raw source binding for both admitted v3 receipts

| Role | Source | Raw SHA-256 |
|---|---|---|
| harness | `../ladder.py` | `B5436C851C849CFB2B39A7EC2B35C258E501E3171A2ECD6BE6AF913329CC27E6` |
| focused tests | `../test_ladder.py` | `C709415907E90DC0478E45C60508D5E3331AFD78D83C5E76F2F8CD927DCBDA77` |
| clean oracle implementation | `../../oracle/oracle.py` | `2148F0C9C4ED38692B9C6658EC48CDD9628688E6C1708345C89A44AB91A05F17` |
| clean oracle public API | `../../oracle/__init__.py` | `747CF1373F63C6DFB7F1A01744EB0B9A9D91FED17F127FFD0C510AF924AA3BFF` |

These hashes bind the raw source set used by the current v3 normative and
smoke receipts. Any change to one of these files invalidates that binding and
requires a new receipt; prose-only changes do not rewrite the recorded run.

## Admitted v3 evidence

### Normative

`normative-correction-attempt3.json`:

- raw SHA-256:
  `98786009478343F4A7D84FC594A67C7E09BE64483865123AC1C73E4144525699`;
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
- no host ceiling; CPython 3.14t was `INFRA_UNAVAILABLE`.

### Focused smoke

`smoke-correction-attempt3.json`:

- raw SHA-256:
  `E552F98CDF741A7CAEBA20F950FCCE7DACC5378F880EAD49EE10884159DD2B7F`;
- `RR-CONCURRENCY-LADDER-3` / `RR-CONCURRENCY-WORKER-3`, status `PASS`;
- lowered, nonnormative bounds: `P = 1, 2`, five requests per caller, both
  modes, two identical-seed runs, no soak, and no free-threaded probe;
- focused package tests against the bound source set: 15/15 `PASS`.

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

## Dirty-worktree and resource qualification

Both v3 receipts record baseline HEAD
`4e788d21e882a30bdda2aec3f780537161f81644` and `git.clean=false`. They are
raw-source-bound by this status record and independently recomputed, but they
are **not clean-commit-bound evidence**.

Both runs overlapped the separately authorized compact model explorer. During
the normative run, at 2026-08-10T20:39:24.5979851-07:00, model PID 13136
(`python -B -m portability.model.explorer --compact --progress`) used
291,999,744 private bytes, 299,155,456 working-set bytes, and three threads;
host free physical memory was 2,022,305,792 of 16,556,150,784 bytes. Receipt
resource observations are therefore coexecution stress evidence, **not
isolated performance evidence or an isolated-machine resource baseline**. No
duplicate ladder was run.

Recommendation only: after the first authorized commit, rerun the v3 focused
smoke and normative ladder from that clean source commit if charter time and
resource headroom permit. This recommendation does not start or authorize a
rerun.
