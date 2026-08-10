# T1 Stream B — Sol campaign record

## Verdict

PASS for the final user-directed Stream B allocation: 8,000/8,000 deterministic cases completed, with zero candidate invariant-breach chunks and 16,000 exact fresh runner executions. The campaign was stopped parent-first immediately after the eighth atomic chunk checkpoint; no Stream B process remained afterward.

This is one stream of the reduced reference campaign, not evidence for the original handoff's >=1,000,000-input T1 threshold.

## Frozen identity

- Audited commit: `0ffa0e41da97b17039505180da261587399d2ba6`
- Branch/worktree: `sol/w-t1b-sol`, `receiver-reliance-worktrees/t1b_sol`
- Interpreter: `C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe`, CPython 3.12.10
- `fuzz/campaign.py` SHA-256: `6658F8BA5B347BB5E6A5AFFD108B8E6A485A36342A8511B7148A2D8FB53E9CAB`
- `fuzz/fuzz.py` SHA-256: `D1F792238A56F5F870F05BBF8B36A6A84C03181AB3C784C746998CF639B26200`
- frozen runner SHA-256: `83319385C8B6D28965F4683B8C0689FB70158E86ED35D54E7467E8E3DF076E09`
- Base seed: `0xB100000000000000`; chunk size: 1,000; workers: 4
- Chunk budget: 900 seconds; case timeout: 5 seconds; retry ceiling: 1

## Final evidence

- Count: 8 chunks / 8,000 cases / 16,000 exact runner executions
- Seeds: `0xB100000000000000` through `0xB100000000000007`
- Identity root SHA-256: `B7E502E50DDF9CE4E59A7C3B26573408479EB7865B3FD6A4637E611A23BE216B`
- Atomic checkpoint SHA-256: `DE891C2FD98814D26AD643B19D1F351477F832738D94D548989FC7C829BDD867`
- Exit counts: exit 0 = 528; exit 1 = 537; exit 2 = 6,935
- Candidate breach chunks: 0
- Per-worker observed rate: 2.54–2.70 cases/second. The first four chunks completed in 392.555–393.296 seconds; the second four in 370.301–370.823 seconds.
- Strategy distribution is deterministic and totals 8,000: 23 strategies at 256 cases each and 8 strategies at 264 cases each.

The checkpoint directory is `fuzz/regressions/.campaign-b-sol-100k/`. It is evidence only and is intentionally not committed.

## Allocation changes and aborted evidence

The stream was launched initially for 333,000 cases. The user then reduced it to 33,000, then 16,000, and finally corrected the final Stream B allocation to 8,000 because the 20,000-case pilot counts toward the 50,000-case reference half.

The first target-change experiment at `fuzz/regressions/.campaign-b-sol/` completed zero cases. During its stop, child processes were terminated before the campaign parent, causing four empty-output `harness_error` records and retries. Those records are operator-induced orchestration interruptions, not runner findings. That state is quarantined, is excluded from every count above, and must never be merged. Its last checkpoint SHA-256 was `80042FF3A372271305C08C0C271D962D1372E5A70AB3C258281E799ACB65D003`.

The clean replacement launched at 2026-08-10T19:30:22Z with PID 21388. Later reductions were applied parent-first, followed by exact orphan cleanup, so the clean checkpoint was unchanged at each atomic stop.

## Deterministic extension schedule

Only with renewed authorization, extend the clean checkpoint using the same interpreter, state directory, base seed, chunk size, four workers, timeouts, and retry ceiling. Use `--phase resume` and increase `--target-cases`:

1. `16000` adds chunks 8–15, seeds `0xB100000000000008` through `0xB10000000000000F`.
2. `33000` then adds chunks 16–32, seeds `0xB100000000000010` through `0xB100000000000020`.
3. `333000` then restores the original Stream B allocation, adding chunks 33–332 through seed `0xB10000000000014C`.

The checkpoint's six-hour full-phase deadline remains anchored to 2026-08-10T19:30:22Z (deadline 2026-08-11T01:30:22Z). A continuation after that deadline requires an explicitly authorized new campaign state; the driver will not silently reset this cap.
