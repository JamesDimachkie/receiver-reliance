# R-O1 refutation — persistent audited NDJSON batch mode

## Verdict

**REJECT WITH FINDINGS.** The candidate preserves ordering, statelessness,
audited byte parity, flushing, stderr silence, and clean EOF on ordinary
blocking pipes, and it meets the performance target. It nevertheless fails
two required transport/resource falsifiers:

1. `serve()` accepts a permitted short `BinaryIO.write()` as success, emits a
   truncated non-JSON response, flushes it, and returns zero.
2. `source.readline()` is unbounded, bypassing the frozen runner's bounded
   `MAX_INPUT_BYTES + 1` read. A delimiter-free client can grow the persistent
   process until host memory exhaustion before the engine can issue its
   bounded protocol error.

No candidate file was modified. The reviewed candidate is the cherry-pick
`633404564c8b332746262a341c8e0ca1b39feeb4` of O1
`cfe503aeefbb547b19a831fdb2484d6f81b60372`, based exactly on integration
`99997edd12b640228f2a0a8be074ad84483e5dfe`.

## Findings

### RO1-01 — short writes silently corrupt response framing

`grounded-0_4/rr_batch.py:43` calls
`sink.write(response_bytes(raw_line))` once and ignores the returned byte
count. `BinaryIO.write()` may make a short write (notably on non-blocking or
custom transports). The following deterministic probe used a sink that
accepts one third of each buffer, exactly as reported by its return value:

```powershell
@'
import io, pathlib, sys
here = pathlib.Path.cwd() / "grounded-0_4"
sys.path.insert(0, str(here))
import rr_batch

class PartialSink:
    def __init__(self):
        self.data = bytearray(); self.calls = 0; self.flushes = 0
    def write(self, data):
        self.calls += 1
        n = max(1, len(data) // 3)
        self.data.extend(data[:n])
        return n
    def flush(self):
        self.flushes += 1

sink = PartialSink()
expected = rr_batch.response_bytes(b"\n")
code = rr_batch.serve(io.BytesIO(b"\n"), sink)
print(code, sink.calls, sink.flushes, len(sink.data), len(expected), bytes(sink.data) == expected)
'@ | python -B -
```

Observed: `serve_code=0 calls=1 flushes=1 actual=271 expected=814
exact=False`. The written prefix has no terminal LF. With another request,
the next response prefix is concatenated to it, so the one-request/one-line
framing guarantee is lost while `serve()` still reports a clean outcome.

This was not reproduced on the normal blocking `sys.stdout.buffer` pipe; that
path returned full writes in all runs. The defect is still within the explicit
partial-write charter and the declared `BinaryIO` surface. A repair must loop
over a `memoryview` until the full response is accepted and must define
zero/`None`/`BlockingIOError` behavior before flushing.

### RO1-02 — unbounded line acquisition defeats the 16 MiB input bound

The frozen runtime declares `MAX_INPUT_BYTES = 16777216` and the one-shot ABI
reads at most `MAX_INPUT_BYTES + 1` bytes
(`baseline-run/implementation-output-0.3/pcb_runner.py:452`). The batch path
instead calls unbounded `source.readline()` at `rr_batch.py:40`; the engine's
length rejection occurs only after the entire line is resident.

Minimal resource probe:

```powershell
@'
import io, pathlib, sys, tracemalloc
here = pathlib.Path.cwd() / "grounded-0_4"
sys.path.insert(0, str(here))
import rr_api, rr_batch

class OversizeSource:
    def __init__(self, n): self.n = n; self.done = False
    def readline(self):
        if self.done: return b""
        self.done = True
        return b"x" * self.n + b"\n"

n = rr_api.b1.MAX_INPUT_BYTES * 2
tracemalloc.start()
sink = io.BytesIO()
code = rr_batch.serve(OversizeSource(n), sink)
_, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
print(n + 1, rr_api.b1.MAX_INPUT_BYTES, peak, len(sink.getvalue()), code)
'@ | python -B -
```

Observed: input `33,554,433` bytes, engine maximum `16,777,216`, peak traced
allocation `67,109,323` bytes (2.00001x input), response `840` bytes,
`serve()` exit `0`, embedded protocol exit `2`. The returned response is
correct once allocation succeeds; the failure is that memory use scales with
an untrusted physical line and can prevent any response or continuation at
all.

A persistent fix needs a bounded incremental line reader that, after crossing
the cap, drains through the next LF without retaining the line. Because the
audited object binds `request_raw_sha256`, exact oversized-input parity also
requires incremental hashing (or an explicit protocol decision about what
bytes the over-limit audit binds). Merely passing a size to `readline()` would
incorrectly turn one overlong physical record into multiple requests.

## Evidence that held

### Candidate differential gate

Twice executed from repo root:

```powershell
python -B grounded-0_4/test_batch.py --perf
```

Both runs: `fixtures=372 semantic=124 fuzz=256 fuzz_fast=223
fuzz_special=33 checks=2030 failures=0 perf=on`.

- All 112 primary + 12 supplemental semantic fixtures and all 224 primary +
  24 supplemental wrapper arms matched audited isolated bytes.
- The deterministic P3 corpus (`seed=0x0B10F042`) matched on all 256 cases,
  including empty input, missing LF, CRLF, internal LF framing, BOM, invalid
  UTF-8, duplicate keys, NFC traps, lone-surrogate escape, deep nesting, and
  huge integers.
- Malformed lines continued, repeats were stateless, output was JCS+LF with no
  CR, stderr was empty, EOF was clean, and the in-memory full-write sink saw
  one flush per response.

### Fresh-context raw/sequence/pipe harness

An inline stdlib-only Python harness (seed `0x524F31`) ran 74 assertions with
zero failures, apart from the two deliberately separate falsifiers above:

- 17 exact framing streams: zero-byte EOF, one/two empty lines, missing LF,
  extra LF, CRLF, CRLF followed by empty line, terminated plus unterminated
  records, escaped and literal embedded LF, BOM, invalid UTF-8, duplicate key,
  scalar root, whitespace, and bare CRLF;
- 1,024 generated physical lines of 0–256 arbitrary bytes excluding LF,
  including NUL, CR, and high bytes; persistent output exactly equaled the
  concatenated per-line `decide_audited()` JCS+LF bytes in order;
- a 600-request deterministic sequence mixing primary semantic,
  supplemental semantic, wrapper, empty, CRLF, and invalid-UTF-8 requests;
- five interactive requests written across arbitrary 1–4,093 byte stdin
  chunks and flushed before reading each response;
- execution from a temporary foreign CWD under hostile `PYTHONPATH`,
  `PYTHONHOME`, `PYTHONIOENCODING=utf-16`, random hash seed, `LC_ALL=C`,
  `LANG=C`, and a different `TZ`, using the documented `-I -B` ABI; and
- an 800-request pipeline whose reader was delayed 200 ms to fill/apply pipe
  backpressure, then drained concurrently: 800 ordered responses, exact byte
  parity, empty stderr, clean exit.

These checks found no state leakage, order divergence, Unicode/locale/CWD/env
dependency, clean-EOF defect, or ordinary blocking-pipe flush/backpressure
failure.

## Performance and arithmetic

The final paired run was explicitly contention-labelled:

```powershell
$before = @(Get-Process -Name python -ErrorAction SilentlyContinue).Count
python -B grounded-0_4/test_batch.py --perf
$after = @(Get-Process -Name python -ErrorAction SilentlyContinue).Count
```

There were 21 Python processes both before and after the run. Samples in
ms/request over the same 124 semantic fixtures were:

| path | samples | median |
|---|---|---:|
| paired in-process `decide_audited()` | 6.185714, 6.379727, 6.617462 | 6.379727 |
| persistent `-I -B` batch | 4.990574, 5.029117, 5.539656 | 5.029117 |

Observed paired ratio: `0.788297x`, below the required `3x`. Against P1's
recorded audited in-process median `5.288240 ms`, the observed batch median is
`0.951000x`; P1's exact ceiling is `15.864720 ms`. Against P1's isolated
one-shot stdio median `154.984114 ms`, it is a `30.8174x` amortized speedup.
The arithmetic holds, but the host was contended and cross-run ratios are not
portable performance claims. A prior run in this lane also passed at
`0.767020x` paired ratio.

## Full expanded gate

All commands exited zero from the stated directories:

```powershell
Push-Location baseline-run
python -B implementation-output-0.2/run_conformance_0_2.py
python -B implementation-output-0.3/run_conformance_0_3.py --suite all
Pop-Location
python -B grounded-0_4/test_grounded_0_4.py
python -B grounded-0_4/lint_contract.py --gate
python -B grounded-0_4/test_lint_gate.py
python -B grounded-0_4/test_properties.py
python -B grounded-0_4/test_audit_adversarial.py
python -B proof/test_proof_harness.py
python -B fuzz/fuzz.py --ci-smoke
python -B grounded-0_4/test_batch.py --perf
```

Observed results: conformance `800 failures=0`; composed `800 + 107`, both
zero; grounded `504/0`; lint `0 findings`; lint meta `7/0`; properties
`2,296/0` at seed `0x5EED8785`; audit adversarial `6,497/0`; proof harness
`7/7`; fuzz smoke `31/31` at seed `0x0B10F042`; batch `2,030/0`.

## Candidate diff and residual uncertainty

Candidate diff: 3 new files, 515 insertions —
`grounded-0_4/rr_batch.py` (52), `grounded-0_4/test_batch.py` (366), and
`perf/BATCH_O1.md` (97). Frozen/sealed paths, candidate files, workflow files,
dependencies, remotes, and external workspace data were untouched.

Residuals:

- No multi-gigabyte exhaustion was attempted; the source-level unbounded read
  plus the bounded 32 MiB/67 MiB allocation observation is the stopping proof.
- OS-level blocking stdout always completed full writes here; RO1-01 is a
  confirmed short-write behavior of the declared `serve(BinaryIO, BinaryIO)`
  surface, not a claim that this Windows pipe happened to short-write.
- Forced downstream disconnect, process kill, and signal behavior were not
  used as correctness criteria because no transport can deliver a response to
  a vanished reader.
- The deterministic corpora are broad but not exhaustive. No semantic byte
  divergence or state leak was found within them.

Stop condition reached: two minimized, independently reproducible defects are
sufficient to reject O1; no candidate patch was attempted in the refuter lane.

Authored-By: sol-ro1 (gpt-5.6-sol)
