# Receiver-reliance continuation ledger

Integration branch: `sol/rr-continuation-20260810`

Custodian: Sol root (`gpt-5.6-sol`), sole merger.

The baseline SHA for this run is `4a90f9ed043c446dadd7d6715863ba9b88ff2b0d`.
Worker branches start from a gate-green integration commit and never merge
their own work. Timestamps are recorded in Pacific time on 2026-08-10.

| Worker | Objective | Spawn | End | Verdict | Integration |
|---|---|---|---|---|---|
| W0 | Verify the untouched validation baseline | 2026-08-10 11:18 PDT | 2026-08-10 11:21 PDT | PASS | merged as `5374438`; integration gate green |
| P1 | Profile current integration-path costs | 2026-08-10 11:22 PDT | 2026-08-10 11:54 PDT | PASS AFTER CORRECTION | merged as `eb8bfbc` + `4d01910`; exact `-I -B` ABI, 5-sample medians recorded |
| P2 | Prove lint gates fail on controlled mutations | 2026-08-10 11:22 PDT | 2026-08-10 11:27 PDT | PASS | merged as `d3e86e9`; 7/7 meta-tests; integration gate green |
| P3 | Build deterministic grammar and byte fuzz harness | 2026-08-10 11:23 PDT | 2026-08-10 11:36 PDT | PASS | merged as `8a92536`; 31-strategy smoke; integration gate green |
| P4 | Add seeded property tests | 2026-08-10 11:23 PDT | 2026-08-10 11:30 PDT | PASS | merged as `331f78f`; 2,296 checks; integration gate green |
| P5 | Add adversarial audited-surface tests | 2026-08-10 11:24 PDT | 2026-08-10 11:30 PDT | RED — valid defect, RESOLVED | test merged as `489b3db` after F1; 6,497/6,497 pass; integration gate green |
| P6 | Build synthetic proof corpus and regressions | 2026-08-10 11:24 PDT | 2026-08-10 11:33 PDT | PASS | merged as `105dc33`; 7 proof tests; integration gate green |
| P7 | Draft proposed 0.5 core wire and audit rules | 2026-08-10 11:24 PDT | — | SECOND CORRECTION RUNNING | `75de333` + `9b26bb0`; resolving RSPEC2 core blockers |
| P8 | Draft proposed 0.5 semantics and compact profile | 2026-08-10 11:25 PDT | 2026-08-10 12:28 PDT | TWICE-CORRECTED CANDIDATE | `ba45778` + `07331b5` + `5b137ca`; awaiting combined RSPEC3 |
| P9 | Audit documentary counts, paths, commands, and digests | 2026-08-10 11:28 PDT | 2026-08-10 11:39 PDT | PASS | merged as `6f3dcce`; denominator/path drift corrected; integration gate green |
| F1 | Fix audited-reference exact-key false positive | 2026-08-10 11:31 PDT | 2026-08-10 11:34 PDT | PASS | merged as `1cc2d35` after RF1; integration gate green |
| I1 | Build independent composed-surface implementation | 2026-08-10 11:32 PDT | — | THIRD CORRECTION RUNNING | prior fixes passed; resolving RI3 duplicate-vs-framing precedence divergence |
| RF1 | Refute F1 exact-key fix | 2026-08-10 11:34 PDT | 2026-08-10 11:38 PDT | NO-DEFECT-FOUND | report merged as `fec60ff`; 976 probes; integration gate green |
| T1 pilot | Establish deterministic campaign checkpoint and rate | 2026-08-10 11:38 PDT | 2026-08-10 12:24 PDT | PASS | 20,000 cases / 40,000 runner executions; zero breaches; normalized 18.257 cases/s |
| T1A Sol | Run reduced campaign stream A | 2026-08-10 12:25 PDT | — | RUNNING | target 34,000; 4,000 green at target change; 4 workers, Python 3.12 |
| T1B Sol-low | Run reduced campaign stream B | 2026-08-10 12:30 PDT | — | RUNNING | target 33,000; fresh state after operator-aborted zero-case launch; 4 workers |
| T1C Sol-low | Run reduced campaign stream C | 2026-08-10 12:31 PDT | — | RUNNING | target 33,000; fresh state after zero-case launch; 4 workers |
| T1A experiment | Attempt campaign stream A under Terra | 2026-08-10 11:54 PDT | 2026-08-10 12:14 PDT | STOPPED BY USER, NOT ADOPTED | 0 durable cases; all Terra processes stopped; state preserved only as experiment evidence |
| T1B experiment | Attempt campaign stream B under Terra | 2026-08-10 11:55 PDT | 2026-08-10 12:15 PDT | STOPPED BY USER, NOT ADOPTED | 0 durable cases; report remains off integration |
| T1C experiment | Attempt campaign stream C under Terra | 2026-08-10 11:57 PDT | 2026-08-10 12:15 PDT | STOPPED BY USER, NOT ADOPTED | 0 durable cases; report remains off integration |
| T2 | Run cross-interpreter validation matrix | 2026-08-10 11:39 PDT | 2026-08-10 11:43 PDT | PASS | merged as `1217cb6`; CPython 3.12.10 and 3.14.5; integration gate green |
| D1 | Correct proof false-hold denominator | 2026-08-10 11:44 PDT | 2026-08-10 11:46 PDT | PASS | merged as `3faaedd`; 133/390 = 34.1%; integration gate green |
| RI1 | Refute independent second implementation | 2026-08-10 11:45 PDT | 2026-08-10 11:51 PDT | REJECT — valid defect | report merged as `94ad1d6`; RFC 8785 UTF-16 ordering divergence isolated |
| RI2 | Refute corrected independent implementation | 2026-08-10 12:01 PDT | 2026-08-10 12:12 PDT | REJECT — valid defect | report merged as `99997ed`; escaped lone-surrogate divergence/crash isolated |
| RI3 | Refute twice-corrected independent implementation | 2026-08-10 12:18 PDT | 2026-08-10 12:27 PDT | REJECT — valid defect | report merged as `1123cdd`; duplicate-key precedence lost without final LF |
| RSPEC | Refute 0.5 proposal consistency | 2026-08-10 11:46 PDT | 2026-08-10 11:53 PDT | REJECT — 3 valid blockers | report merged as `e89e991`; P7/P8 corrections in review |
| RSPEC2 | Refute combined corrected 0.5 proposal | 2026-08-10 12:04 PDT | 2026-08-10 12:20 PDT | REJECT — 5 valid blockers | report merged as `9eb6fb7`; second P7/P8 corrections in progress |
| O1 | Build and prove persistent NDJSON batch path | 2026-08-10 12:02 PDT | — | CORRECTION RUNNING | `cfe503a` rejected on short writes and unbounded line acquisition; fixing after RO1 |
| RO1 | Refute O1 parity and statelessness | 2026-08-10 12:16 PDT | 2026-08-10 12:24 PDT | REJECT — 2 valid defects | report merged as `75832a8`; candidate remained unmerged |
| O2 | Evaluate deterministic fast path | 2026-08-10 12:02 PDT | — | PAUSED FOR T1 | `sol/w-o2`; interrupted without integration to free Sol campaign capacity |
| O3 | Fold audited classification into one traced pass | 2026-08-10 12:08 PDT | 2026-08-10 12:27 PDT | CANDIDATE GREEN | `d82f492`; 1,142 parity checks, ~0.17% median gain, awaiting RO3 |
| RO3 | Refute O3 semantic parity and work claims | 2026-08-10 12:28 PDT | — | RUNNING | `sol/w-ro3`; independent >=10k semantic differential |
