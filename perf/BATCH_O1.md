# O1 persistent audited NDJSON path

## Verdict

**PASS.** `grounded-0_4/rr_batch.py` keeps the grounded 0.4 audited API in
one process and frames it as one physical input line to one JCS+LF response.
The process is request-stateless, flushes every response, continues after a
malformed line, writes nothing to stderr, and exits zero on clean EOF.  The
frozen engine's per-request exit status remains inside each audited response.

The measured batch median was **12.564314 ms/request**, or **1.220392x** the
paired in-process `decide_audited()` median of **10.295308 ms/request**.  It
also passed the target against P1's less-contended recorded baseline:
12.564314 ms is **2.3759x** P1's 5.288240 ms in-process audited median and is
below the exact 3x ceiling of **15.864720 ms**.  Against P1's fresh isolated
stdio median of 154.984114 ms, this observation is a **12.335x** amortized
speedup.

## Byte-parity and stream proof

`python -B grounded-0_4/test_batch.py --perf` completed with
`checks=2030 failures=0` and proved:

- all 372 checked-in exact fixture requests agree with the committed sealed
  response bytes and with the isolated `decide_audited()` JCS bytes: 112
  primary semantic entries, 224 primary wrapper arms, 12 supplemental
  semantic entries, and 24 supplemental wrapper arms;
- the default deterministic fuzz corpus (`seed=0x0B10F042`) has byte parity
  under NDJSON framing for all 256 cases: 223 ordinary single-line cases and
  33 special-framing cases individually adjudicated as unterminated final
  lines, internal-LF multiple records, or empty-stream EOF;
- eight explicit malformed-line classes retain their one-shot protocol-error
  bytes and per-response exit codes, without stopping the next request;
- a six-request mixed-order stream with valid repeats and interleaved invalids
  equals six isolated process results byte-for-byte, and each repeated request
  returns identical bytes;
- every response is strict UTF-8 JCS with exactly one terminal LF and no CR,
  response count equals physical request-line count, and stdout/stderr are
  empty on an empty clean shutdown; and
- the in-process stream test observes one sink flush per response.

## Performance measurement

Command, from the repository root:

```powershell
python -B grounded-0_4/test_batch.py --perf
```

Workload: the same 124 semantic fixture requests used by P1, with one untimed
cache warmup and three paired measurements.  Each batch sample starts one new
`python -I -B grounded-0_4/rr_batch.py` process, includes startup and pipe I/O,
and amortizes those costs across 124 requests.  Direct and child measurements
alternate order by repetition.

| path | raw samples (ms/request) | median |
|---|---|---:|
| in-process `decide_audited()` | 10.295308, 10.541057, 10.185807 | 10.295308 |
| persistent isolated NDJSON process | 12.140372, 12.858994, 12.564314 | 12.564314 |
| batch / paired in-process | — | 1.220392x |

There were 31 other Python processes immediately before this run, from the
active fuzz campaign and related orchestration.  That contention explains why
the paired in-process median was about 1.95x P1's 5.288240 ms recorded median;
it is a resource condition, not a functional failure.  Importantly, the batch
path still met both the paired 3x gate and the absolute 3x P1 threshold without
relaxing either criterion.

## Expanded gate

All commands exited zero:

- accepted conformance: 800 checks, failures=0;
- composed conformance: 800 + 107 checks, failures=0;
- grounded regression: 504 checks, failures=0;
- contract lint: 0 findings; lint meta-test: 7 checks, failures=0;
- properties: 2,296 checks, failures=0;
- audit adversarial: 6,497 checks, failures=0;
- portable proof harness: 7 tests, OK;
- O1 batch regression/performance: 2,030 checks, failures=0; and
- fuzz CI smoke: 31/31 cases, failures=0, budget not exhausted.

## Usage and boundaries

```powershell
python -I -B grounded-0_4/rr_batch.py
```

The transport is deliberately a physical-line protocol.  An empty byte stream
means EOF and therefore cannot also name an empty request; a raw LF inside a
purported request is a record boundary.  An unterminated final physical line is
processed once and receives the frozen LF-framing protocol error.  Processing
is sequential and blocking; concurrency, cancellation, queue limits, and host
backpressure policy remain integration concerns.  Timing is host- and
contention-specific and should be remeasured in the target deployment
environment.  This result makes no efficacy, novelty, security, or external
conformance claim.
