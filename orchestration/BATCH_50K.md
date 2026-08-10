# B50 second-half batch campaign report

## Verdict

**PASS.** The authorized run completed all 50 chunks and 50,000 selected
requests with zero parity, count, order, stderr, exit, timeout, identity, or
uniqueness failures. All 128 fresh-process samples also passed. Both fixed
performance gates were met, and the expanded repository validation gate was
green after the run.

The campaign ran once from integration commit
`df33b82388ee4d399fd6e891d6c9e9bc6b51853e` with:

```text
python -I -B perf/batch_campaign.py --run --state-dir perf/.batch-campaign-work-sol-low
```

The atomic checkpoint is intentionally ignored and uncommitted at
`perf/.batch-campaign-work-sol-low/batch_campaign.json`. Its SHA-256 is
`AEA89922596B2CCD68ADEC5EF23E7DE3EAED758C270FD8F04351389B9268AC86`.
Independent parsing after process exit verified every chunk and sample record.
The state directory contains only that checkpoint; no raw corpus, expected
response, stdout, or stderr artifact was retained.

## Counts and identity

| Item | Result |
|---|---:|
| Execution chunks | 50 / 50 passed |
| Selected requests | 50,000 / 50,000 |
| Responses | 50,000 / 50,000, in order |
| Persistent parity failures | 0 |
| Fresh-process samples | 128 / 128 passed |
| Candidate unique raw SHA-256 values | 50,000 |
| Candidate overlap with first-half raw hashes | 0 |
| First-half scheduled case identities | 50,000 |
| First-half unique raw hashes | 17,599 |
| Aggregate scheduled case identities | 100,000 |
| Aggregate unique raw bytes | 67,599 |

The first half therefore contributes 50,000 seeded case identities but only
17,599 unique raw byte strings. The second half contributes 50,000
raw-byte-unique strings, all disjoint from the first half. “100,000 cases” is
an identity count; “67,599 unique raw bytes” is the deduplicated input count.

Identity roots and relevant source identities were:

| Identity | SHA-256 |
|---|---|
| First-half ordered identity root | `0B40CC2963B56770909650D006CCE89EBC5DBF4534942E62FD91797820BA2090` |
| Second-half ordered candidate root | `9F46680E1D7D0006126ACB046F6CB0EC0CC3EA1CDA094FC8B1A484489B056B20` |
| Second-half execution-chunk root | `4CD27BA5EEF94C24824C3EE019AF6763958090D92132770E231E646A6FEB2968` |
| Fresh-sample identity | `9271519A73EA322E861E7801678564BD09D1EF1B095A02CD799B7A5B97B284E5` |
| `batch_campaign.py` | `73825EA3EAD72A8F20C79104FAC1AD79598A2DE8DF85E227DE7106A82A17FB3B` |
| `fuzz.py` | `D1F792238A56F5F870F05BBF8B36A6A84C03181AB3C784C746998CF639B26200` |
| `rr_api.py` | `EFF02D41169F04452942486005E8EDF537DB1BBC488B8CDE8C323B91CD827F26` |
| `rr_batch.py` | `86775EF47CE38EFB191747CCA374993631B2E88C9BEA9CBE945B3D77C9D3DEB8` |

## Timing and resources

The checkpointed run began at `2026-08-10T19:59:00Z` and finished at
`2026-08-10T20:03:06Z`.

| Measure | Result |
|---|---:|
| Persistent child batch time | 108.0769405 s |
| Persistent latency | 2.16153881 ms/request |
| Per-chunk latency median | 2.17608065 ms/request |
| Per-chunk latency p95 | 2.37530501 ms/request |
| Direct `decide_audited` time | 120.2616623 s |
| Direct `decide_audited` latency | 2.405233246 ms/request |
| Direct JCS encoding time | 1.3522398 s |
| Direct total time | 121.6139021 s |
| Persistent / same-run direct ratio | 0.8986815784x |
| Persistent / P1 audited in-process median | 0.4087444613x |
| Fresh-process median | 95.56205 ms/request |
| Fresh-process p95 | 172.193095 ms/request |
| Fresh-process range | 76.4734–259.1579 ms/request |
| Persistent speedup vs fresh median | 44.21019394x |
| Worst observed child peak working set | 22,671,360 bytes |
| Input bytes processed | 135,714,518 |
| Output / expected bytes | 42,887,951 / 42,887,951 |
| Maximum expected response | 1,476 bytes |

The persistent path passed both explicit thresholds: it was below `3.0x` the
same-run direct cost and below `15.864720 ms/request` (three times P1's
`5.288240 ms` audited in-process median). P1's `154.984114 ms` frozen
one-shot stdio result is context only, not a like-for-like audited path.

## Environment

- Windows 11 `10.0.26200`, AMD64, 22 logical CPUs.
- CPython 3.12.10, 64-bit (`pythoncore-3.12-64`).
- Campaign implementation identity: integration commit
  `df33b82388ee4d399fd6e891d6c9e9bc6b51853e`.
- Child peak memory used the Windows peak-working-set probe; 6,632 resource
  samples were recorded across persistent chunks.

## Expanded validation

All commands exited 0 after the campaign:

| Gate | Result |
|---|---|
| Frozen 0.2 conformance | 800 checks, 0 failures |
| Frozen 0.3 conformance | 800 + 107 checks, 0 failures |
| Grounded 0.4 regression | 504 checks, 0 failures |
| Contract lint | 0 findings |
| Lint gate meta-tests | 7 checks, 0 failures |
| Properties | 2,296 checks, 0 failures |
| Audit adversarial | 6,497 checks, 0 failures |
| Proof harness | 7 tests, all passed |
| Fuzz CI smoke | 31 / 31 cases, 0 failures |
| Batch regression and perf | 2,160 checks, 0 failures; median ratio 0.882733x |
| Single-pass audit equivalence | 1,142 checks, 0 failures |
| Single-pass observational benchmark | optimized / legacy median 1.008255x |

## Limitations

This is a deterministic, local, synthetic-input parity and performance
campaign on one Windows host. Scheduler contention, pipe behavior, startup
cost, and memory observations can differ on other machines and Python builds.
The additional-unique selection is intentionally not strategy-balanced;
finite cases already present in the first half were excluded. Fresh-process
sampling covers 128 deterministically spaced inputs, not every selected input.

The campaign establishes the recorded parity, identity, and local performance
results only. It makes no claim of efficacy, novelty, security, fuzzing
completeness, or external-standard conformance, and it does not change the
evidence tier of the research program.
