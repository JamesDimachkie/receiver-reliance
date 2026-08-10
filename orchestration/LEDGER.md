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
| P7 | Draft proposed 0.5 core wire and audit rules | 2026-08-10 11:24 PDT | 2026-08-10 12:01 PDT | CORRECTED CANDIDATE | `75de333` + `9b26bb0`; RSPEC B1-B3 correction awaiting fresh refutation |
| P8 | Draft proposed 0.5 semantics and compact profile | 2026-08-10 11:25 PDT | — | CORRECTION RUNNING | `ba45778`; resolving RSPEC B1-B3 before fresh refutation |
| P9 | Audit documentary counts, paths, commands, and digests | 2026-08-10 11:28 PDT | 2026-08-10 11:39 PDT | PASS | merged as `6f3dcce`; denominator/path drift corrected; integration gate green |
| F1 | Fix audited-reference exact-key false positive | 2026-08-10 11:31 PDT | 2026-08-10 11:34 PDT | PASS | merged as `1cc2d35` after RF1; integration gate green |
| I1 | Build independent composed-surface implementation | 2026-08-10 11:32 PDT | 2026-08-10 11:59 PDT | CORRECTED CANDIDATE | `161e06b` + `9f7e016`; UTF-16 JCS correction, 827/827 + 12,004/12,004, awaiting RI2 |
| RF1 | Refute F1 exact-key fix | 2026-08-10 11:34 PDT | 2026-08-10 11:38 PDT | NO-DEFECT-FOUND | report merged as `fec60ff`; 976 probes; integration gate green |
| T1 pilot | Establish deterministic campaign checkpoint and rate | 2026-08-10 11:38 PDT | 2026-08-10 12:00 PDT | SUPERSEDED, CHECKPOINT PRESERVED | 12,000 cases checkpointed with zero breaches; redundant 4-worker process stopped |
| T1A | Run campaign stream A under Terra | 2026-08-10 11:54 PDT | — | RUNNING | `sol/w-t1`; 334,000 disjoint cases, 16 workers, atomic `.campaign-a` state |
| T1B | Run campaign stream B under Terra | 2026-08-10 11:55 PDT | — | RUNNING | `sol/w-t1b`; 333,000 disjoint cases, 16 workers, CPython 3.14 |
| T1C | Run campaign stream C under Terra | 2026-08-10 11:57 PDT | — | RUNNING | `sol/w-t1c`; 333,000 disjoint cases, 16 workers, CPython 3.14 |
| T2 | Run cross-interpreter validation matrix | 2026-08-10 11:39 PDT | 2026-08-10 11:43 PDT | PASS | merged as `1217cb6`; CPython 3.12.10 and 3.14.5; integration gate green |
| D1 | Correct proof false-hold denominator | 2026-08-10 11:44 PDT | 2026-08-10 11:46 PDT | PASS | merged as `3faaedd`; 133/390 = 34.1%; integration gate green |
| RI1 | Refute independent second implementation | 2026-08-10 11:45 PDT | 2026-08-10 11:51 PDT | REJECT — valid defect | report merged as `94ad1d6`; RFC 8785 UTF-16 ordering divergence isolated |
| RI2 | Refute corrected independent implementation | 2026-08-10 12:01 PDT | — | RUNNING | `sol/w-ri2`; fresh Sol review plus 20k differential attack |
| RSPEC | Refute 0.5 proposal consistency | 2026-08-10 11:46 PDT | 2026-08-10 11:53 PDT | REJECT — 3 valid blockers | report merged as `e89e991`; P7/P8 corrections in review |
| O1 | Build and prove persistent NDJSON batch path | 2026-08-10 12:02 PDT | — | RUNNING | `sol/w-o1`; byte parity, statelessness, and amortized-cost target |
| O2 | Evaluate deterministic fast path | 2026-08-10 12:02 PDT | — | RUNNING | `sol/w-o2`; parity-first implementation or evidence-backed stand-down |
