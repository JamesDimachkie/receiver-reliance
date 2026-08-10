# Receiver-reliance continuation ledger

Integration branch: `sol/rr-continuation-20260810`

Custodian: Sol root (`gpt-5.6-sol`), sole merger.

The baseline SHA for this run is `4a90f9ed043c446dadd7d6715863ba9b88ff2b0d`.
Worker branches start from a gate-green integration commit and never merge
their own work. Timestamps are recorded in Pacific time on 2026-08-10.

| Worker | Objective | Spawn | End | Verdict | Integration |
|---|---|---|---|---|---|
| W0 | Verify the untouched validation baseline | 2026-08-10 11:18 PDT | 2026-08-10 11:21 PDT | PASS | merged as `5374438`; integration gate green |
| P1 | Profile current integration-path costs | 2026-08-10 11:22 PDT | — | CORRECTION RUNNING | candidate `d1be3d7`; rerunning exact `-I -B` stdio ABI after custodian review |
| P2 | Prove lint gates fail on controlled mutations | 2026-08-10 11:22 PDT | 2026-08-10 11:27 PDT | PASS | merged as `d3e86e9`; 7/7 meta-tests; integration gate green |
| P3 | Build deterministic grammar and byte fuzz harness | 2026-08-10 11:23 PDT | 2026-08-10 11:36 PDT | PASS | merged as `8a92536`; 31-strategy smoke; integration gate green |
| P4 | Add seeded property tests | 2026-08-10 11:23 PDT | 2026-08-10 11:30 PDT | PASS | merged as `331f78f`; 2,296 checks; integration gate green |
| P5 | Add adversarial audited-surface tests | 2026-08-10 11:24 PDT | 2026-08-10 11:30 PDT | RED — valid defect, RESOLVED | test merged as `489b3db` after F1; 6,497/6,497 pass; integration gate green |
| P6 | Build synthetic proof corpus and regressions | 2026-08-10 11:24 PDT | 2026-08-10 11:33 PDT | PASS | merged as `105dc33`; 7 proof tests; integration gate green |
| P7 | Draft proposed 0.5 core wire and audit rules | 2026-08-10 11:24 PDT | 2026-08-10 11:40 PDT | CANDIDATE GREEN | `75de333`; awaiting RSPEC |
| P8 | Draft proposed 0.5 semantics and compact profile | 2026-08-10 11:25 PDT | 2026-08-10 11:45 PDT | CANDIDATE GREEN | `ba45778`; awaiting RSPEC |
| P9 | Audit documentary counts, paths, commands, and digests | 2026-08-10 11:28 PDT | 2026-08-10 11:39 PDT | PASS | merged as `6f3dcce`; denominator/path drift corrected; integration gate green |
| F1 | Fix audited-reference exact-key false positive | 2026-08-10 11:31 PDT | 2026-08-10 11:34 PDT | PASS | merged as `1cc2d35` after RF1; integration gate green |
| I1 | Build independent composed-surface implementation | 2026-08-10 11:32 PDT | 2026-08-10 11:44 PDT | CANDIDATE GREEN | `161e06b`; 827/827, awaiting RI1 |
| RF1 | Refute F1 exact-key fix | 2026-08-10 11:34 PDT | 2026-08-10 11:38 PDT | NO-DEFECT-FOUND | report merged as `fec60ff`; 976 probes; integration gate green |
| T1 | Run deterministic million-input fuzz campaign | 2026-08-10 11:38 PDT | — | RUNNING | `sol/w-t1`; six-hour cap, durable chunks |
| T2 | Run cross-interpreter validation matrix | 2026-08-10 11:39 PDT | 2026-08-10 11:43 PDT | PASS | merged as `1217cb6`; CPython 3.12.10 and 3.14.5; integration gate green |
| D1 | Correct proof false-hold denominator | 2026-08-10 11:44 PDT | 2026-08-10 11:46 PDT | PASS | merged as `3faaedd`; 133/390 = 34.1%; integration gate green |
| RI1 | Refute independent second implementation | 2026-08-10 11:45 PDT | — | RUNNING | `sol/w-ri1`; fixture, provenance, and 20k differential attack |
| RSPEC | Refute 0.5 proposal consistency | 2026-08-10 11:46 PDT | — | RUNNING | `sol/w-rspec` |
