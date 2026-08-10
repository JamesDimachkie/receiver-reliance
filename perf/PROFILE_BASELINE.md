# Receiver-reliance performance baseline

## Verdict

**PASS — measurement baseline only; no engine optimization was made.** The
stdlib-only profiler completed byte-parity prechecks and measured all 124
committed semantic fixture entries. On this host, a fresh-process stdio
decision had a 154.984 ms median corpus-average latency versus 5.119 ms for
`decide()` in process. The paired ratio median was 30.274x. Interleaved
`decide_audited()` measurements were 1.033x the `decide()` cost at the paired
ratio median.

These numbers are a baseline for comparison on this host, not portable
performance guarantees. In particular, “stdio” includes Windows process
creation, CPython startup, imports, engine work, and pipe I/O; it is not an
isolated serialization cost.

## Environment and run configuration

- Frozen engine source SHA: `7581bdaa018b1af6ff214aec7870577f9eeda75c`
- Profiler parent SHA at measurement: `d1be3d70ed1c3aabf3663ce0bf4768b3d8b193a7`
- Python: CPython 3.12.10, MSC v.1943, 64-bit
- Executable: `C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe`
- Platform: Windows 11 `10.0.26200`, AMD64
- Processor string: `Intel64 Family 6 Model 170 Stepping 4, GenuineIntel`
- Logical CPU count: 22
- Timer: `QueryPerformanceCounter()`, monotonic, nominal resolution `1e-7` s
- Workload: 112 primary 0.2 semantic fixtures plus 12 supplemental 0.3
  semantic fixtures, sorted by UTF-8 `entry_id`
- Reported repetitions: 5 for every aggregate
- Warmups: 1 per in-process fixture/probe and 1 per stdio fixture
- Inner loops: 5 calls averaged per in-process timing sample; stdio uses 1
  fresh process per sample
- Memory: 1 full 124-entry corpus loop per sample, 5 samples after 1 warmup
- Child Python flags: `-I -B`, matching the fixed subprocess ABI in both
  frozen conformance runners and the runbook's one-request command
- Percentile method: linear interpolation over sorted samples

The profiler first checked `decide()` output, the sealed response inside
`decide_audited()`, and fresh-process stdio output against the committed
expected bytes. All 124 entries passed before timing began.

### Why stdio uses isolated mode

Isolated mode is part of the intended fixed subprocess ABI, not an optional
hardening variant:

- Both frozen conformance runners invoke their subprocess path as
  `[toolchain, "-I", "-B", pcb_runner.py, "execute"]` and describe it as the
  fixed ABI.
- `baseline-run/RUNBOOK.md` calls this the sealed subprocess-ABI mode and uses
  `python -I -B .../pcb_runner.py execute` in its single-request example.
- `README.md` routes single-request use to that sealed subprocess ABI.

The original P1 report accidentally measured `-B` without `-I`. Every number
in this corrected report comes from a new default five-sample run using
`-I -B`; the earlier stdio figures are superseded.

## Integration-path latency

Each raw sample below is the corpus-average milliseconds per decision for one
reported repetition. `decide()` and `decide_audited()` are interleaved per
fixture, and the first/second call order alternates by repetition to reduce
time-of-run bias.

| Path | Raw samples (ms/decision) | n | min | median | mean | pstdev | p95 | max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `decide()` in process | 5.125130, 5.147125, 5.117556, 5.027911, 5.119398 | 5 | 5.027911 | 5.119398 | 5.107424 | 0.041129 | 5.142726 | 5.147125 |
| `decide_audited()` in process | 5.342227, 5.286149, 5.288240, 5.321474, 5.175358 | 5 | 5.175358 | 5.288240 | 5.282690 | 0.057640 | 5.338076 | 5.342227 |
| fresh-process stdio (`-I -B`) | 156.396369, 155.355519, 151.663302, 152.528397, 154.984114 | 5 | 151.663302 | 154.984114 | 154.185540 | 1.788974 | 156.188199 | 156.396369 |

Paired comparison samples and summaries:

| Comparison | Raw ratio samples | n | min | median | mean | pstdev | p95 | max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| stdio / `decide()` | 30.515593, 30.182973, 29.635886, 30.336334, 30.273896 | 5 | 29.635886 | 30.273896 | 30.188936 | 0.297169 | 30.479741 | 30.515593 |
| `decide_audited()` / `decide()` | 1.042359, 1.027010, 1.033353, 1.058387, 1.010931 | 5 | 1.010931 | 1.033353 | 1.034408 | 0.015781 | 1.055181 | 1.058387 |

## Spread across all 124 semantic fixture entries

This table summarizes the 124 per-entry medians; it is a workload spread, not
five timing repetitions. The stdio spread is particularly sensitive to
process scheduling.

| Path | n | min | median | mean | pstdev | p95 | max | Fastest / slowest entry by median |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `decide()` | 124 | 3.389500 | 4.608990 | 5.005281 | 1.312078 | 8.011049 | 8.751740 | `SEMFX-OBL-03-FAIL-3C938464DFACBB5A` / `SEMFX-OBL-29-IO-5F7E5E0A995BC8C9` |
| `decide_audited()` | 124 | 3.411800 | 4.714290 | 5.175306 | 1.460924 | 8.757627 | 10.089440 | `SEMFX-OBL-02-IO-240A61327FBD9401` / `SEMFX-OBL-29-INV-29D474BA69CE7F2D` |
| fresh-process stdio (`-I -B`) | 124 | 120.622400 | 146.491300 | 151.798326 | 19.925308 | 190.290145 | 257.315800 | `SEMFX-OBL-01-FAIL-A85C56149C721165` / `SEMFX-OBL-21-INV-42CC45E35ACBF1AB` |

## Startup and direct component probes

### Fresh-process wall probes

These probes overlap. They show increasingly complete fresh-process paths;
they do not form additive phases.

| Probe | Raw samples (ms) | n | min | median | mean | pstdev | p95 | max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| isolated interpreter process, no-op | 29.1355, 28.6358, 31.2195, 30.5295, 32.7529 | 5 | 28.6358 | 30.5295 | 30.4546 | 1.4779 | 32.4462 | 32.7529 |
| isolated interpreter + engine import | 81.7695, 96.8686, 88.1404, 79.1924, 89.8296 | 5 | 79.1924 | 88.1404 | 87.1601 | 6.2432 | 95.4608 | 96.8686 |
| isolated interpreter + import + authority load/verify | 102.7015, 112.3533, 118.1979, 110.1401, 134.2183 | 5 | 102.7015 | 112.3533 | 115.5222 | 10.5838 | 131.0142 | 134.2183 |

For orientation only, the median residuals are 57.611 ms for import minus
no-op and 24.213 ms for authority minus import. Because the processes are
different observations and the sample distributions overlap, these
subtractions are **not causal phase measurements**.

### Authority load and verification

`authority_documents.cache_clear()` precedes each direct sample. This makes
the application cache cold, but it does not flush filesystem or OS caches.

| Raw samples (ms) | n | min | median | mean | pstdev | p95 | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| 11.7570, 6.7690, 13.8917, 7.4450, 10.8239 | 5 | 6.7690 | 10.8239 | 10.1373 | 2.6752 | 13.4648 | 13.8917 |

### Direct valid-path components

These direct probes are deliberately non-additive:

- Schema walk calls the frozen binding/request error-pool logic plus response
  validation over a prebuilt response.
- Classify calls the frozen predicate classifier directly.
- Seal calls the exact self-zero JCS + SHA-256 primitive over a prebuilt
  response; response assembly is excluded.

| Probe | Raw corpus-average samples (ms/decision) | n | min | median | mean | pstdev | p95 | max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| schema walk, valid path | 6.358455, 6.307933, 6.311439, 6.346472, 6.345278 | 5 | 6.307933 | 6.345278 | 6.333915 | 0.020343 | 6.356059 | 6.358455 |
| classify | 0.028167, 0.026243, 0.026111, 0.024243, 0.023972 | 5 | 0.023972 | 0.026111 | 0.025747 | 0.001527 | 0.027783 | 0.028167 |
| seal primitive | 0.029863, 0.028662, 0.031929, 0.028814, 0.029320 | 5 | 0.028662 | 0.029320 | 0.029718 | 0.001183 | 0.031516 | 0.031929 |

The corresponding 124-entry median spreads were:

| Probe | n | min | median | mean | pstdev | p95 | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| schema walk | 124 | 5.451120 | 6.210710 | 6.309203 | 0.446632 | 7.318100 | 7.828880 |
| classify | 124 | 0.002420 | 0.013750 | 0.024151 | 0.035462 | 0.073623 | 0.209980 |
| seal primitive | 124 | 0.016860 | 0.026780 | 0.027045 | 0.004804 | 0.032916 | 0.047180 |

## Peak traced memory

Timing and memory runs are separate. Values below are peak traced Python
allocations after setup, measured with `tracemalloc`; they are not RSS and do
not include native allocations, interpreter baseline memory, or child-process
memory.

| Workload | Raw peak samples (bytes) | n | min | median | mean | pstdev | p95 | max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| application-cache-cold authority load/verify | 4,206,836; 4,206,836; 4,206,836; 4,206,836; 4,206,836 | 5 | 4,206,836 | 4,206,836 | 4,206,836 | 0 | 4,206,836 | 4,206,836 |
| `decide()`, one full corpus | 45,186; 44,875; 45,068; 45,193; 44,921 | 5 | 44,875 | 45,068 | 45,048.6 | 131.5 | 45,191.6 | 45,193 |
| `decide_audited()`, one full corpus | 86,845; 86,630; 87,477; 86,737; 86,724 | 5 | 86,630 | 86,737 | 86,882.6 | 304.9 | 87,350.6 | 87,477 |

## Exact rerun commands

Run from the repository root:

```powershell
python -B perf/profile.py --output perf/profile-run.json
```

For each timed stdio decision, the profiler executes the ABI-equivalent child
command below with fixture bytes on stdin:

```powershell
python -I -B baseline-run/implementation-output-0.3/pcb_runner.py execute
```

The defaults used by this baseline are explicit equivalents of:

```powershell
python -B perf/profile.py --warmups 1 --repetitions 5 --inner-loops 5 --stdio-warmups 1 --memory-loops 1 --child-timeout 30 --output perf/profile-run.json
```

The generated JSON contains every per-entry raw sample and summary. It is a
rerunnable observation artifact and is intentionally not versioned.

## Validation gate

The profiler does not modify engine behavior. The repository's recorded
four-command gate was run from this worktree after profiling:

```powershell
Push-Location baseline-run
python -B implementation-output-0.2/run_conformance_0_2.py
python -B implementation-output-0.3/run_conformance_0_3.py --suite all
Pop-Location
python -B grounded-0_4/test_grounded_0_4.py
python -B grounded-0_4/lint_contract.py --gate
```

Observed verdict: **PASS**. All commands exited 0:

- 0.2 conformance: `failures=0`; 112 semantic, 370 competence, 224
  wrapper-arm, 10 negative, 4 metamorphic, and 80 error-law cases.
- 0.3 composed conformance: suite 0.2 `total=800 failures=0`; suite 0.3
  `total=107 failures=0`.
- Grounded 0.4 regression: `checks=504 failures=0`.
- Contract lint: `lint: 0 findings`; all 199 required fields accounted for.

## Limitations and residual risks

- Wall-clock samples include scheduler, power-state, antivirus, concurrent
  host activity, and filesystem-cache noise.
- The stdio figure is a whole fresh-process integration cost. It does not
  identify how much is process creation versus import, engine, or pipes.
- Isolated mode is included in every child and startup wall probe; the report
  makes no estimate for the isolated-mode flag alone.
- Startup probes overlap, and median subtraction cannot establish causality.
- Direct component probes cover valid semantic fixtures, use prebuilt objects
  where stated, and must not be summed into the end-to-end latency.
- Only the committed 124 semantic fixture entries are profiled. This is broad
  semantic coverage, not an exhaustive input-size or adversarial performance
  study.
- `tracemalloc` excludes native allocations and child-process memory; no stdio
  RSS claim is made.
- Re-run on the target deployment host before setting budgets or thresholds.
