# WP5 robustness profile

## Verdict

**PASS by the charter fallback: no new optimization; current cost model and
request-bound anonymous-stdio sidecar admitted.**

The profile covers canonicalization, digest, audit, and integration paths over
all 124 committed semantic fixtures. The accepted single-pass audit remains
byte-identical to its legacy oracle and reduces predicate work, but paired
wall-time ratios still straddle parity. No engine optimization is admitted.

The additive sidecar now uses versioned `RR-SIDECAR/1` frames. Every response
is bound to an exact monotonic sequence, SHA-256 of all request bytes, and
SHA-256 of all response bytes. A lifecycle phase or queued line cannot
establish identity. The process uses anonymous stdin/stdout, opens no listener,
and imports only the standard library plus repository decision modules.

## Reproduced results

Environment: CPython 3.12.10, Windows 11 `10.0.26200`, AMD64. Workload: 112
primary 0.2 plus 12 supplemental 0.3 semantic fixtures, sorted by UTF-8
`entry_id`.

An optional Windows `tasklist` image-name-prefix snapshot observed 9
Python/PyPy/GraalPy-named processes before and 10 after. This was a racy,
permission-dependent Windows observation, not a universal process census.
Other desktop contention was uncontrolled.

| Path or probe | Median | Paired ratio |
|---|---:|---:|
| raw SHA-256 over canonical decision input | 0.000781 ms | — |
| decision-input JCS + SHA-256 | 0.009529 ms | 12.127x raw digest |
| raw request SHA-256 | 0.001920 ms | — |
| audit self-zero JCS + SHA-256 | 0.021327 ms | 11.536x raw digest |
| accepted single-pass audited decision | 3.101564 ms | 0.995779x legacy oracle |
| `decide()` library | 2.856157 ms | — |
| `decide_audited()` library | 2.936253 ms | 1.033291x `decide()` |
| framed persistent audited sidecar | 5.401788 ms/request | 1.781707x paired audited library |
| fresh isolated frozen stdio | 227.177932 ms/decision | 76.518408x paired `decide()` |

Ratios are medians of paired ratio vectors. Library/hotpath probes use 11
interleaved repetitions with three inner calls per fixture. Whole-corpus
sidecar and fresh-process probes use three alternating-order repetitions.
Every traced Python process used `-B`, a unique empty temporary
`-X pycache_prefix`, and a Python `open` audit hook.

The cProfile attribution run made 372 audited calls. Its largest cumulative
rows were `decide_audited` 4.342 s, frozen `_execute` 4.265 s, and frozen
`schema_errors` 3.666 s. These instrumented cumulative values overlap and must
not be summed.

## Optimization admission

The existing single-pass path saved 116 predicate-atomic calls on 93/124
fixtures and passed 1,142 equivalence checks. The current paired ratio samples
ranged from 0.985817x to 1.013786x. Work reduction is established; a stable
end-to-end speedup is not.

Decision: **do not admit a new optimization**. Publish the current-byte cost
model and framed sidecar shape, as the WP5 fallback permits.

## Sidecar evidence

`perf/sidecar/test_sidecar.py` records 728 checks and zero failures:

- direct transport frames decode to all 124 exact `decide_audited()` payloads;
- the supervisor returns those payloads from one stable PID with sequences
  1–124 and clean EOF;
- request frames with bad digest, duplicate/reordered sequence, or truncated
  payload terminate the launcher without a response for the bad frame;
- pre-, mid-, and post-write raw output fails closed;
- a child reading one byte of a 1 MiB request and emitting `POISON` is rejected
  under default and 4 KiB host writes, with zero admitted responses or
  replays; the OS-dependent completed-write observation is not identity;
- valid short writes complete, while a zero-progress write terminates;
- future, stale, duplicate, wrong-request-digest, and wrong-response-digest
  frames are never admitted as the pending response;
- EOF, child death, timeout, response overlimit, whitespace stderr, long
  stderr, and cleanup are covered; and
- a 16 MiB+1 engine request returns the exact audited `ERR_LIMIT` payload.

No scheduling delay is used for identity. Admission requires full host frame
write and flush completion plus exact envelope correlation.

## Current receipts

Profile:

- path:
  `perf/receipts/robustness/profile-windows-cpython-3.12-20260812-attempt6.json`
- raw SHA-256:
  `F54B6300ACA8BB4E3D7BBE7F8F1A110B7D558A5E9E8D7448DD5F7315CC3B0166`
- embedded pre-seal SHA-256:
  `694A5CABB14F5F4616135B5C4EBF67CCD0933422138CDC6403375772FBBB0737`

Sidecar:

- path:
  `perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260812-attempt9.json`
- raw SHA-256:
  `E082C27DB6CE00B95A594A26FD0460BC632D54E0CE4CB159C85A6EF56E8AB4AF`
- embedded pre-seal SHA-256:
  `1268D1EC32A766A2918651188EC550FD0F6243BB027F7FF1357E46FF386CB047`

The profile manifest pins 23 Python-audit-visible repository files; the
sidecar manifest pins 21 (the 0.4.1 audit surface newly reads the
authority register at import for its governing digests). The verifier requires exact traced-set/pin-set
equality, all raw hashes, actual `sys.orig_argv` including receipt target,
empty temporary bytecode caches, and the receipt-specific behavioral fields.
This custody is limited to Python `open` audit events for repository regular
files in the traced Python process tree. It is not native or OS-wide I/O
provenance.

All earlier immutable receipts remain chronological records. Their exact raw
hashes and corrected labels are in `perf/COST_MODEL.md`; none supplies current
numbers or current sidecar admission.

## Commands

```powershell
python -B perf/sidecar/profile_robustness.py --receipt perf/receipts/robustness/profile-windows-cpython-3.12-20260812-attempt6.json
python -B perf/sidecar/test_sidecar.py --receipt perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260812-attempt9.json
python -B perf/sidecar/verify_receipts.py
```

Receipt writers use exclusive creation and refuse an existing target. The
receipts store the actual re-executed `sys.orig_argv`, not merely these caller
commands.

## Limits and refutation targets

Refuters should recompute raw/embedded/source hashes, mutate every request and
response correlation field, split host writes, force zero progress, reorder
and duplicate frames across requests, truncate headers/payloads, overrun the
response bound, and verify child/thread cleanup and no replay. They should also
search for listeners, sockets, non-stdlib dependencies, shell use, and
request-derived retained state.

These observations apply only to the pinned bytes, fixture workload, runtime,
host, and desktop state. No throughput, tail-latency, capacity, concurrency,
universal portability, security, efficacy, availability, external-standard,
or optimization-speedup claim is made.
