# Deterministic fuzz campaign report

> **Current re-run values (2026-08-17).** This is a dated report; the inline
> counts below are as-of its date and several have since moved as later waves
> added regressions and custody bindings. A third party re-running today should
> expect: grounded-0.4 regression `checks=517 failures=0`; lint-gate meta-test
> `checks=9 failures=0`; authority ledger `141 semantic / 34 presence_only /
> 10 inert_disclosed / 14 inert_registered_debt` of 199 required fields;
> `verify_receipts.py` `checks=267 failures=0`; `verify_hygiene.py`
> `HYGIENE_PASS allowed_raw_receipt_warnings=1120 admitted_diagnostics=5
> unexpected_diagnostics=0 custody_hashes=17/17`. The historical numbers are
> left in place deliberately — this report is evidence of what was observed on
> its date, not a live dashboard. ERRATA F-WP2-001 records why the authority
> census moved (30 dual-use fields had been wrongly subtracted).

## Verdict

**PASS — the user-authorized 50,000-case reference half is complete.** The
unchanged integrated `fuzz/fuzz.py` oracle credited 50,000 distinct
deterministic cases and exactly 100,000 fresh runner executions with zero
candidate invariant breaches, harness/configuration failures, retries, or
unadjudicated findings.

The current aggregate target is 100,000 cases. Its second, disjoint 50,000-case
half is intentionally **NOT RUN**: it is reserved for a paired
batch-vs-isolated campaign after O1 admission. Nothing in this report claims
that deferred half or the 100,000-case aggregate is complete.

> **Superseded on this point (annotated 2026-08-17).** The deferred half has
> since been executed as the batch campaign; see `orchestration/BATCH_50K.md`
> (50 chunks, 50,000 / 50,000 selected requests and responses in order, 50,000
> unique candidate raw SHA-256 values, zero findings) and
> `orchestration/FINAL_REPORT.md`. `BATCH_50K.md` also reconciles the two
> figures that otherwise look contradictory: the aggregate is **100,000
> scheduled case identities** but **67,599 unique raw byte strings**, because
> the first half's 50,000 seeded identities collapse to 17,599 unique inputs
> while the second half contributes 50,000 raw-byte-unique strings disjoint
> from the first. The "100,000 cases" figure in `README.md` and `ACCEPTANCE.md`
> is therefore an identity count and is correct; this paragraph's NOT RUN
> statement was true only on this report's date. Read in isolation it now
> understates the completed work.

The 20,000-case throughput pilot is reported separately below but, per the
final user-directed accounting, is included in the 50,000-case reference half.

## Exact totals

| Segment | Base seed and completed seed range | Cases | Runner executions | Workers | Breaches / harness errors / retries |
|---|---|---:|---:|---:|---:|
| Pilot | `0x5252465A00000000`–`0x5252465A00000013` | 20,000 | 40,000 | 4 | 0 / 0 / 0 |
| A | `0xA100000000000000`–`0xA10000000000000D` | 14,000 | 28,000 | 4 | 0 / 0 / 0 |
| B | `0xB100000000000000`–`0xB100000000000007` | 8,000 | 16,000 | 4 | 0 / 0 / 0 |
| C | `0xC100000000000000`–`0xC100000000000007` | 8,000 | 16,000 | 4 | 0 / 0 / 0 |
| **Reference half** | four disjoint seed ranges | **50,000** | **100,000** | 4 per segment | **0 / 0 / 0** |

Every segment used 1,000-case chunks and the documented schedule
`seed = base_seed + zero_based_chunk_id`. Within a chunk, the unchanged oracle
generated indices `0..999` in its fixed strategy order. The seed ranges do not
overlap, so every credited identity is distinct by
`(seed,index,strategy,input_sha256)`.

All runs used:

- CPython `3.12.10` at
  `C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe`;
- Windows 11 build 26200 on node `JD`, with 22 logical CPUs; and
- four campaign workers, a five-second per-runner timeout, and a 900-second
  per-chunk budget.

The pilot's resumed 8,000 cases measured 20.942 cases/second. Its normalized
four-worker whole-pilot rate was 18.257 cases/second. Stream A's normalized
rate under concurrent B/C load was 13.304 cases/second. No safety-threatening
resource behavior was observed.

## Strategy and exit counts

The first eight oracle strategies in fixed order — `fixture_core_valid`,
`fixture_core_defect`, `fixture_wrapper_valid`, `fixture_wrapper_defect`,
`grammar_drop_required`, `grammar_wrong_type`, `grammar_unknown_member`, and
`grammar_binding_mismatch` — each ran **1,650** times.

Each of the other 23 strategies ran **1,600** times: `grammar_fact_shape`,
`utf8_edges`, `bom`, `invalid_utf8`, `lone_surrogate`, `duplicate_key`,
`deep_nesting`, `deep_known_envelope`, `huge_integer`, `nfc_key`, `nfc_value`,
`noncanonical_whitespace`, `missing_lf`, `crlf`, `trailing_bytes`, `truncate`,
`bit_flip`, `byte_insert`, `byte_delete`, `byte_splice`, `root_scalar`,
`empty_input`, and `random_grammar`.

| Segment | Exit 0 | Exit 1 | Exit 2 | Exit 3 | Total |
|---|---:|---:|---:|---:|---:|
| Pilot | 1,325 | 1,336 | 17,339 | 0 | 20,000 |
| A | 926 | 940 | 12,134 | 0 | 14,000 |
| B | 528 | 537 | 6,935 | 0 | 8,000 |
| C | 529 | 535 | 6,936 | 0 | 8,000 |
| **Reference half** | **3,308** | **3,348** | **43,344** | **0** | **50,000** |

## Digest evidence

The atomic checkpoints retain every completed chunk's ordered identity digest.
Each segment root is SHA-256 over its ordered chunk evidence; each checkpoint
SHA-256 covers the complete JSON state, including chunk summaries, run events,
runtime, counts, stdout/stderr digests, and target-change history.

| Segment | Identity root SHA-256 | Final checkpoint SHA-256 |
|---|---|---|
| Pilot | `8D0560B4F4C2F233E8709D1BFB7B88332A16706977F14B8DBD314B400A8DB738` | `FC7839A2D138CE40EDF0F7FE77E141AF420614845BBE2480B5C32DECE0DD653A` |
| A | `FEF76E9997648C37AA40C38FE04AFEBF2B5C169C03DE381F544560BCE6BDC468` | `4014A5012D4FB65F53D259D9B0D107A2DFC43474D0CE936F2D36CBFCD20ACE23` |
| B | `B7E502E50DDF9CE4E59A7C3B26573408479EB7865B3FD6A4637E611A23BE216B` | `DE891C2FD98814D26AD643B19D1F351477F832738D94D548989FC7C829BDD867` |
| C | `D5882C941936877C38B84E7FB12234D9C2431AB7C80C69E5690EB9F3BBD3A875` | `0D4C6BD1FFA451DC38A395F12A48CF032FE94E7590899D3F6B4BF1EA6D542D8A` |

The combined evidence digest is
`4274E263F680328089B13D24A164341C999C36128ED7A269B38696DDBA858CFD`,
computed as SHA-256 of these ASCII lines in order:

```text
pilot,20000,8D0560B4F4C2F233E8709D1BFB7B88332A16706977F14B8DBD314B400A8DB738
A,14000,FEF76E9997648C37AA40C38FE04AFEBF2B5C169C03DE381F544560BCE6BDC468
B,8000,B7E502E50DDF9CE4E59A7C3B26573408479EB7865B3FD6A4637E611A23BE216B
C,8000,D5882C941936877C38B84E7FB12234D9C2431AB7C80C69E5690EB9F3BBD3A875
```

Pilot and A identities were independently regenerated from their recorded
seeds and compared with all 34 stored chunk digests: no mismatch. B and C ran
from separate Sol-managed worktrees; their final evidence commits are
`01957c2` and `85b5457`, respectively.

## Findings and adjudications

There were no candidate invariant breaches and therefore no regression input
or engine patch. No harness/configuration failure was misclassified as a
runner finding.

The pilot was interrupted after 12,000 durable cases during orchestration
custody correction and resumed from its atomic checkpoint. Stream A was
stopped and resumed at durable boundaries as the user reduced its allocation
from 334,000 to 34,000, then 18,000, and finally 14,000. Those changes and the
deferred extension schedule are recorded in the A checkpoint. B and C were
likewise finalized at their user-directed 8,000-case allocations. Completed
chunks were preserved; killed in-flight target-change attempts were not
credited as cases or runner executions.

## Counterevidence sought

For every credited case, the unchanged oracle performed two fresh one-shot
runner processes and checked strict UTF-8 framing, one JCS response plus LF,
schema validity, success/error shape, seal recomputation, output size, exit-code
agreement, empty stderr, timeout behavior, and byte-identical two-run
determinism. Campaign summaries were rejected unless oracle counts matched
independently regenerated strategy counts and the requested seed/chunk plan.

The post-campaign validation gate also passed:

| Check | Result |
|---|---|
| Frozen 0.2 conformance | 800 checks, 0 failures |
| Composed 0.2 + 0.3 conformance | 800 + 107 checks, 0 failures |
| Grounded 0.4 regression | 504 checks, 0 failures |
| Contract lint gate | 199 required fields classified, 0 findings |
| P3 fuzz smoke | 31/31 strategies, 62 runner executions, 0 failures |

## Residual uncertainty and extension schedule

This is bounded deterministic adversarial evidence, not exhaustive coverage or
a security proof. Credited execution totals exclude partial subprocess work
discarded when user-directed target reductions stopped in-flight chunks; no
such partial chunk contributes to identities, exit counts, or the verdict.

The remaining 50,000 cases of the 100,000-case aggregate are reserved for a
new, disjoint paired batch-vs-isolated schedule. That extension must not launch
until O1 admission defines the pairing and evidence contract. Its eventual
report must combine without reusing any pilot/A/B/C seed above.

Blinding note: this work was limited to build, test, verification, and
orchestration. It did not author regenerated worlds, an oracle, gold outputs,
or a renderer.

## Diff and commits

- `fuzz/campaign.py` is the stdlib-only resumable campaign driver. Bootstrap
  commit: `6708bbc4a2408a4a0221c94aad99746045093566`.
- Runtime-drift rejection, interruption evidence, and validator-failure
  classification were added in audited Sol commit
  `0ffa0e41da97b17039505180da261587399d2ba6`.
- This report is the only additional tracked deliverable. No checkpoint,
  corpus, or regression file is committed; no regression exists.
- `fuzz/fuzz.py`, the frozen engine, sealed bytes, workflow files, and every
  forbidden path remain unchanged. Nothing was pushed.
