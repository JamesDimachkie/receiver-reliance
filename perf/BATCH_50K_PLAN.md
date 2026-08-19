# B50 — second-half batch parity and efficiency campaign

## Status and stop gate

**HARNESS READY. The 50,000-case run was not executed in the author lane; it ran later in the Sol lane** — [../orchestration/BATCH_50K.md](../orchestration/BATCH_50K.md) records PASS at 50/50 chunks, 50,000/50,000 requests, zero failures.

This is the additive campaign requested after O1 correction.  The author lane
ran planning regeneration and one uncheckpointed 1,000-case smoke chunk only.
The full run is reserved for the post-admission execution lane.  It writes no
corpus and commits no checkpoint; its only durable local state is the
repo-local, untracked `perf/.batch-campaign-work/batch_campaign.json` (or an
explicit alternative beneath this repository).

The campaign stops immediately on any response-count, order, byte-parity,
stderr, exit-code, timeout, checkpoint-identity, uniqueness, or performance-
threshold failure.  A stopped chunk is recorded atomically and is not counted
as passed.  Resumption regenerates the complete plan and refuses any config,
source-file, interpreter, plan-root, or completed-chunk identity drift.

## Frozen first-half exclusion

`perf/batch_campaign.py` regenerates raw requests from the exact reference
50k schedule and retains only their SHA-256 identities:

| stream | base seed | chunks | cases |
|---|---|---:|---:|
| pilot | `0x5252465A00000000` | 20 (`0x00..0x13`) | 20,000 |
| A | `0xA100000000000000` | 14 (`0x00..0x0D`) | 14,000 |
| B | `0xB100000000000000` | 8 (`0x00..0x07`) | 8,000 |
| C | `0xC100000000000000` | 8 (`0x00..0x07`) | 8,000 |

- Generated identities: 50,000
- Unique raw SHA-256 values: **17,599**
- Ordered reference identity root:
  `0B40CC2963B56770909650D006CCE89EBC5DBF4534942E62FD91797820BA2090`

No prior checkpoint or corpus is read.  The raw hashes are regenerated from
the pinned oracle schedule on every invocation, so overlap exclusion is
independently reproducible.

## New-half selection identity

- Candidate base seed: `0xD150000000000000`
- Schedule: `seed = base + zero_based_source_chunk_id`
- Source chunk: 1,000 `fuzz.generate_cases` cases using the recorded strategy
  order
- Admissibility: request ends in LF and contains no earlier LF
- Selection order: non-line exclusion → reference-hash exclusion → candidate
  raw-hash deduplication → first 50,000 retained
- Source chunks required: **219**, seeds `0xD150000000000000` through
  `0xD1500000000000DA`
- Selected: **50,000 unique raw SHA-256 values**, with zero reference overlap
- Ordered candidate identity root:
  `9F46680E1D7D0006126ACB046F6CB0EC0CC3EA1CDA094FC8B1A484489B056B20`
- Ordered 50-chunk execution root:
  `4CD27BA5EEF94C24824C3EE019AF6763958090D92132770E231E646A6FEB2968`

Exclusion totals are exact: `non_single_line=29,016`,
`reference_overlap=133,151`, `candidate_duplicate=6,739`, and
`target_full=94` (unique admissible cases later in the final source chunk).

### Selected and excluded strategy distribution

| strategy | selected | non-line | reference | duplicate | target-full |
|---|---:|---:|---:|---:|---:|
| `fixture_core_valid` | 0 | 0 | 7,227 | 0 | 0 |
| `fixture_core_defect` | 0 | 0 | 7,227 | 0 | 0 |
| `fixture_wrapper_valid` | 0 | 0 | 7,227 | 0 | 0 |
| `fixture_wrapper_defect` | 0 | 0 | 7,227 | 0 | 0 |
| `grammar_drop_required` | 498 | 0 | 5,012 | 1,717 | 0 |
| `grammar_wrong_type` | 2,880 | 0 | 2,045 | 2,300 | 2 |
| `grammar_unknown_member` | 7,210 | 0 | 2 | 0 | 15 |
| `grammar_binding_mismatch` | 0 | 0 | 7,227 | 0 | 0 |
| `grammar_fact_shape` | 1,530 | 0 | 3,123 | 2,355 | 0 |
| `utf8_edges` | 13 | 0 | 6,812 | 183 | 0 |
| `bom` | 0 | 0 | 7,008 | 0 | 0 |
| `invalid_utf8` | 6,963 | 0 | 14 | 17 | 14 |
| `lone_surrogate` | 0 | 0 | 7,008 | 0 | 0 |
| `duplicate_key` | 0 | 0 | 7,008 | 0 | 0 |
| `deep_nesting` | 0 | 0 | 7,008 | 0 | 0 |
| `deep_known_envelope` | 0 | 0 | 7,008 | 0 | 0 |
| `huge_integer` | 0 | 0 | 7,008 | 0 | 0 |
| `nfc_key` | 0 | 0 | 7,008 | 0 | 0 |
| `nfc_value` | 0 | 0 | 7,008 | 0 | 0 |
| `noncanonical_whitespace` | 0 | 0 | 7,008 | 0 | 0 |
| `missing_lf` | 0 | 7,008 | 0 | 0 | 0 |
| `crlf` | 6 | 0 | 6,897 | 105 | 0 |
| `trailing_bytes` | 0 | 7,008 | 0 | 0 | 0 |
| `truncate` | 0 | 7,008 | 0 | 0 | 0 |
| `bit_flip` | 6,991 | 1 | 1 | 1 | 14 |
| `byte_insert` | 6,014 | 975 | 2 | 6 | 11 |
| `byte_delete` | 6,978 | 6 | 3 | 7 | 14 |
| `byte_splice` | 6,992 | 2 | 0 | 0 | 14 |
| `root_scalar` | 0 | 0 | 7,008 | 0 | 0 |
| `empty_input` | 0 | 7,008 | 0 | 0 | 0 |
| `random_grammar` | 3,925 | 0 | 3,025 | 48 | 10 |

The absence of selected cases for some strategies is expected: their finite
generated requests were already present in the first reference 50k.  This is
an additional-unique-input campaign, not a claim of balanced strategy
sampling.  The checkpoint records both the table above and the complete
candidate-generated distribution.

## Per-chunk execution and evidence

Each of the 50 execution chunks contains exactly 1,000 selected requests and
starts one actual process:

```powershell
python -I -B grounded-0_4/rr_batch.py
```

For every chunk the parent process independently calls
`rr_api.decide_audited(raw)` and JCS+LF-encodes all 1,000 expectations.  The
child receives the 1,000 raw lines in order.  Admission requires:

- process exit 0, no timeout, and empty stderr;
- exactly 1,000 response lines;
- full concatenated stdout equality and per-index byte equality; and
- the regenerated 1,000-case chunk identity digest.

The atomically replaced checkpoint records chunk identity, selected range,
strategy counts, direct decision/encoding/total time, child batch wall time,
input/output bytes, response count, stdout/stderr digests, first mismatch (if
any), and child peak working set.  Peak working set is sampled through stdlib
`ctypes` on Windows or `/proc/<pid>/status` on Linux; unsupported platforms
record the resource probe as unavailable rather than inventing a value.

After all chunks pass, 128 deterministically spaced selected indices
(including indices 0 and 49,999) run through 128 fresh batch processes.  This
sample must also have exact parity.  Its raw latency samples, median, p95,
range, identities, and observed peak are checkpointed.

## Efficiency decision

The final calculation uses total child batch wall time divided by 50,000 and
compares it with direct `decide_audited` time measured separately from JCS
encoding:

1. persistent / same-run in-process direct cost must be `<=3.0x`;
2. persistent cost must be `<=15.864720 ms/request`, exactly 3× P1's recorded
   `5.288240 ms` audited in-process median; and
3. the 128-case fresh-process sample is reported as the like-for-like startup
   comparison.  P1's `154.984114 ms` frozen one-shot stdio figure is retained
   as context only because it is not the same audited output path.

The final report also includes aggregate and per-chunk median/p95 persistent
latency, direct time, ratios, fresh-process speedup, and worst observed child
peak.  Scheduler/campaign contention remains an explicit measurement caveat;
it never relaxes the thresholds.

## Smoke evidence and expected runtime

Final author-lane smoke command (no campaign checkpoint or corpus created):

```powershell
python -I -B perf/batch_campaign.py --self-test
```

With 14 other Python processes before launch:

```text
batch-campaign-self-test: checks=11 failures=0 selected=50000 reference_unique=17599 source_chunks=219 reference_root=0B40CC2963B56770909650D006CCE89EBC5DBF4534942E62FD91797820BA2090 candidate_root=9F46680E1D7D0006126ACB046F6CB0EC0CC3EA1CDA094FC8B1A484489B056B20 smoke_batch_ms=2406.332100 smoke_direct_decide_ms=2199.432300 smoke_direct_total_ms=2224.827800 smoke_peak_child_bytes=22310912 fresh_median_ms=99.242400 exclusions={"candidate_duplicate":6739,"non_single_line":29016,"reference_overlap":133151,"target_full":94}
```

The smoke regenerated both full identities, ran one real 1,000-case
persistent chunk, ran four deterministically spaced fresh processes, and
round-tripped an atomic checkpoint in a system temporary directory.  It did
not invoke `--run` and left no campaign state.

Planning took about 15 seconds.  Extrapolating the smoke gives about 4.3
minutes: 50 × (2.225 s direct-total + 2.406 s batch), plus planning and about
13 seconds for 128 fresh starts.  A **5–10 minute** wall window is the honest
operating estimate on this host, with longer runtimes possible under concurrent
fuzz load.  The 300-second per-child timeout is a safety ceiling, not the
expected chunk duration.

## Commands after admission

Read-only identity regeneration:

```powershell
python -I -B perf/batch_campaign.py --plan-only
```

Execute or resume the full campaign only in the assigned execution lane:

```powershell
python -I -B perf/batch_campaign.py --run
```

An alternate state directory must still resolve inside this repository:

```powershell
python -I -B perf/batch_campaign.py --run --state-dir perf/.batch-campaign-work-sol-low
```

The execution lane should commit only a compact results report after success;
never the checkpoint, raw corpus, stdout, or expected response bytes.  This
campaign makes no efficacy, novelty, security, fuzzing-completeness, or
external-standard conformance claim.
