# Receiver-reliance performance baseline

## Verdict

**PASS — measurement baseline only; no engine optimization was made.** The
stdlib-only profiler completed byte-parity prechecks and measured all 124
committed semantic fixture entries. On this host, a fresh-process stdio
decision had a 127.001 ms median corpus-average latency versus 3.955 ms for
`decide()` in process. The paired ratio median was 32.257x. Interleaved
`decide_audited()` measurements were 1.030x the `decide()` cost at the paired
ratio median.

These numbers are a baseline for comparison on this host, not portable
performance guarantees. In particular, “stdio” includes Windows process
creation, CPython startup, imports, engine work, and pipe I/O; it is not an
isolated serialization cost.

## Environment and run configuration

- Source SHA: `7581bdaa018b1af6ff214aec7870577f9eeda75c`
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
- Child environment overrides: `PYTHONDONTWRITEBYTECODE=1`,
  `PYTHONHASHSEED=0`
- Percentile method: linear interpolation over sorted samples

The profiler first checked `decide()` output, the sealed response inside
`decide_audited()`, and fresh-process stdio output against the committed
expected bytes. All 124 entries passed before timing began.

## Integration-path latency

Each raw sample below is the corpus-average milliseconds per decision for one
reported repetition. `decide()` and `decide_audited()` are interleaved per
fixture, and the first/second call order alternates by repetition to reduce
time-of-run bias.

| Path | Raw samples (ms/decision) | n | min | median | mean | pstdev | p95 | max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `decide()` in process | 3.880119, 3.984005, 3.954842, 3.874466, 3.966138 | 5 | 3.874466 | 3.954842 | 3.931914 | 0.045593 | 3.980432 | 3.984005 |
| `decide_audited()` in process | 4.068325, 4.102818, 4.031440, 4.077119, 4.024906 | 5 | 4.024906 | 4.068325 | 4.060922 | 0.029116 | 4.097678 | 4.102818 |
| fresh-process stdio | 129.773336, 128.513523, 126.155617, 127.001104, 125.678360 | 5 | 125.678360 | 127.001104 | 127.424388 | 1.519298 | 129.521374 | 129.773336 |

Paired comparison samples and summaries:

| Comparison | Raw ratio samples | n | min | median | mean | pstdev | p95 | max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| stdio / `decide()` | 33.445713, 32.257369, 31.899029, 32.778996, 31.687844 | 5 | 31.687844 | 32.257369 | 32.413790 | 0.634773 | 33.312369 | 33.445713 |
| `decide_audited()` / `decide()` | 1.048505, 1.029822, 1.019368, 1.052305, 1.014818 | 5 | 1.014818 | 1.029822 | 1.032964 | 0.015097 | 1.051545 | 1.052305 |

## Spread across all 124 semantic fixture entries

This table summarizes the 124 per-entry medians; it is a workload spread, not
five timing repetitions. The stdio spread is particularly sensitive to
process scheduling.

| Path | n | min | median | mean | pstdev | p95 | max | Fastest / slowest entry by median |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `decide()` | 124 | 3.145700 | 3.784590 | 3.853513 | 0.438556 | 4.665313 | 5.879340 | `SEMFX-OBL-01-INV-6BE1DD9792EF03D1` / `SEMFX-OBL-22-IO-291939EAD3C56032` |
| `decide_audited()` | 124 | 3.313400 | 3.895510 | 3.987376 | 0.498888 | 4.993499 | 7.289780 | `SEMFX-OBL-02-CTRL-40AA7A46632A77A9` / `SEMFX-OBL-22-IO-291939EAD3C56032` |
| fresh-process stdio | 124 | 109.470300 | 122.594900 | 125.892269 | 12.974300 | 149.082185 | 185.124300 | `SEMFX-OBL-12-CTRL-0872B8AD3612FCDD` / `SEMFX-OBL-06-FAIL-9C6AAE9F73C40A3A` |

## Startup and direct component probes

### Fresh-process wall probes

These probes overlap. They show increasingly complete fresh-process paths;
they do not form additive phases.

| Probe | Raw samples (ms) | n | min | median | mean | pstdev | p95 | max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| interpreter process, no-op | 44.8335, 36.5897, 36.1558, 35.5491, 36.4112 | 5 | 35.5491 | 36.4112 | 37.9079 | 3.4807 | 43.1847 | 44.8335 |
| interpreter + engine import | 106.8117, 87.2625, 104.8062, 93.6149, 84.3939 | 5 | 84.3939 | 93.6149 | 95.3778 | 9.0470 | 106.4106 | 106.8117 |
| interpreter + import + authority load/verify | 100.3117, 101.7376, 102.1488, 99.8526, 112.6263 | 5 | 99.8526 | 101.7376 | 103.3354 | 4.7234 | 110.5308 | 112.6263 |

For orientation only, the median residuals are 57.204 ms for import minus
no-op and 8.123 ms for authority minus import. Because the processes are
different observations and the sample distributions overlap, these
subtractions are **not causal phase measurements**.

### Authority load and verification

`authority_documents.cache_clear()` precedes each direct sample. This makes
the application cache cold, but it does not flush filesystem or OS caches.

| Raw samples (ms) | n | min | median | mean | pstdev | p95 | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| 6.6029, 7.3091, 6.6146, 6.3411, 7.2826 | 5 | 6.3411 | 6.6146 | 6.8301 | 0.3928 | 7.3038 | 7.3091 |

### Direct valid-path components

These direct probes are deliberately non-additive:

- Schema walk calls the frozen binding/request error-pool logic plus response
  validation over a prebuilt response.
- Classify calls the frozen predicate classifier directly.
- Seal calls the exact self-zero JCS + SHA-256 primitive over a prebuilt
  response; response assembly is excluded.

| Probe | Raw corpus-average samples (ms/decision) | n | min | median | mean | pstdev | p95 | max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| schema walk, valid path | 3.380558, 3.256491, 3.322988, 3.226768, 3.262078 | 5 | 3.226768 | 3.262078 | 3.289777 | 0.055117 | 3.369044 | 3.380558 |
| classify | 0.013178, 0.012939, 0.012774, 0.013717, 0.012475 | 5 | 0.012475 | 0.012939 | 0.013017 | 0.000418 | 0.013609 | 0.013717 |
| seal primitive | 0.012958, 0.013306, 0.012921, 0.013223, 0.013173 | 5 | 0.012921 | 0.013173 | 0.013116 | 0.000151 | 0.013290 | 0.013306 |

The corresponding 124-entry median spreads were:

| Probe | n | min | median | mean | pstdev | p95 | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| schema walk | 124 | 2.662640 | 3.195860 | 3.215324 | 0.339366 | 3.811390 | 4.283800 |
| classify | 124 | 0.001100 | 0.007610 | 0.012289 | 0.016122 | 0.032298 | 0.097160 |
| seal primitive | 124 | 0.011540 | 0.012540 | 0.012784 | 0.001216 | 0.013648 | 0.021260 |

## Peak traced memory

Timing and memory runs are separate. Values below are peak traced Python
allocations after setup, measured with `tracemalloc`; they are not RSS and do
not include native allocations, interpreter baseline memory, or child-process
memory.

| Workload | Raw peak samples (bytes) | n | min | median | mean | pstdev | p95 | max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| application-cache-cold authority load/verify | 4,206,836; 4,206,836; 4,206,836; 4,206,836; 4,206,836 | 5 | 4,206,836 | 4,206,836 | 4,206,836 | 0 | 4,206,836 | 4,206,836 |
| `decide()`, one full corpus | 43,451; 43,194; 44,275; 42,954; 42,598 | 5 | 42,598 | 43,194 | 43,294.4 | 565.2 | 44,110.2 | 44,275 |
| `decide_audited()`, one full corpus | 87,055; 87,218; 86,956; 86,021; 86,507 | 5 | 86,021 | 86,956 | 86,751.4 | 434.7 | 87,185.4 | 87,218 |

## Exact rerun commands

Run from the repository root:

```powershell
python -B perf/profile.py --output perf/profile-run.json
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
- Startup probes overlap, and median subtraction cannot establish causality.
- Direct component probes cover valid semantic fixtures, use prebuilt objects
  where stated, and must not be summed into the end-to-end latency.
- Only the committed 124 semantic fixture entries are profiled. This is broad
  semantic coverage, not an exhaustive input-size or adversarial performance
  study.
- `tracemalloc` excludes native allocations and child-process memory; no stdio
  RSS claim is made.
- Re-run on the target deployment host before setting budgets or thresholds.
