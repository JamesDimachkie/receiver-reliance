# T1 Stream C (Sol) campaign report

Date: 2026-08-10

Lane: `sol-t1c-light` (`gpt-5.6-sol`, low)

Branch: `sol/w-t1c-sol`
Audited source commit: `0ffa0e41da97b17039505180da261587399d2ba6`

## Verdict

PASS for the final user-directed Stream C allocation: 8,000 of 8,000 cases completed in eight atomic 1,000-case chunks, with zero candidate breach chunks and zero retries. The oracle performed exactly 16,000 fresh runner executions. This is campaign evidence only; it does not establish efficacy, novelty, security, or external-standard conformance.

Final aggregate:

```text
rr-campaign: verdict=PASS cases=8000/8000 runner_executions=16000 chunks=8/8 breach_chunks=0 identity_root_sha256=D5882C941936877C38B84E7FB12234D9C2431AB7C80C69E5690EB9F3BBD3A875 checkpoint_sha256=0D4C6BD1FFA451DC38A395F12A48CF032FE94E7590899D3F6B4BF1EA6D542D8A
```

Exit counts were `0: 529`, `1: 535`, and `2: 6,936`. Every completed chunk was classified `no_invariant_breach`.

## Frozen execution identity

- Python: `C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe`, CPython 3.12.10 (64-bit).
- Campaign driver SHA-256: `6658F8BA5B347BB5E6A5AFFD108B8E6A485A36342A8511B7148A2D8FB53E9CAB` (`fuzz/campaign.py`).
- Oracle SHA-256: `D1F792238A56F5F870F05BBF8B36A6A84C03181AB3C784C746998CF639B26200` (`fuzz/fuzz.py`).
- Frozen runner SHA-256: `83319385C8B6D28965F4683B8C0689FB70158E86ED35D54E7467E8E3DF076E09` (`baseline-run/implementation-output-0.3/pcb_runner.py`).
- Base seed: `0xC100000000000000`; seed schedule: base plus zero-based chunk id.
- Chunk size: 1,000; workers: exactly 4; case timeout: 5 seconds; chunk budget: 900 seconds; retry ceiling: 1.
- Final state directory (not committed): `fuzz/regressions/.campaign-c-sol-100k`.

No overlapping Stream C seed process was present at either launch. The independently assigned Stream A process used a disjoint `0xA100...` seed range.

## Launches and allocation changes

The initial launch, PID 13496 at `2026-08-10T19:26:37Z`, targeted 333,000 cases in `.campaign-c-sol`. The user reduced the aggregate campaign while its first wave was in flight. The parent was stopped first and its exact oracle descendants were then cleared. It had zero durable chunks. Its unmodified aborted checkpoint remains out of Git with SHA-256 `2B6E677A43BF1988AA9FC0FE751F180B0DE97BC0C9994407FA4D144F5158B582`.

A fresh final-state launch, PID 15480 at `2026-08-10T19:31:16Z`, initially targeted 33,000 cases. The allocation was subsequently reduced to 16,000 and finally to 8,000 after accounting for the shared 20,000-case pilot. The process was stopped parent-first only after the second four-chunk wave had been atomically checkpointed, leaving exactly 8,000 durable PASS cases. A zero-pending `--phase resume --target-cases 8000` invocation finalized and validated the checkpoint without generating any additional case.

The first four chunks took 400.735 to 401.746 seconds each, for a measured concurrent rate of 9.9565 cases/second. The second wave took 364.018 to 364.733 seconds per chunk. The 20,000-case reporting threshold was not reached because the final authorized allocation was reduced below it.

## Chunk identities

| Chunk | Seed | Identity SHA-256 | Seconds |
|---:|---:|---|---:|
| 0 | `0xC100000000000000` | `EC4B9E08ED888F864F6313F39FB08CE6127C387807A986D835B8A41370E49939` | 400.735 |
| 1 | `0xC100000000000001` | `9A15F444AC15842AA0A2FF834AB2D91C0B93BA608773F813D8081E97C06E4DAE` | 401.746 |
| 2 | `0xC100000000000002` | `5828F752E55D8756B0155DA18C928979EE710022B585F8F49FB3C6682E7A1247` | 401.036 |
| 3 | `0xC100000000000003` | `743F664646944DDCDC84F5F46A0B1AADC3A03970C559FEBC76FC6A85D9645142` | 401.261 |
| 4 | `0xC100000000000004` | `D071268DE59D8517C1AC9D6219B0FA3E2DF9D0C02F153AAC0423DF32DD1F6582` | 364.018 |
| 5 | `0xC100000000000005` | `824D0BB4784AEB7078A83834D8F9EB144D118291113956149665117B8B6FBCB0` | 364.733 |
| 6 | `0xC100000000000006` | `E6444D1B249E9B83C32E51C94692E9225216EEC160F9D0243033D080BAD22BBB` | 364.087 |
| 7 | `0xC100000000000007` | `C7D3C6E724119943FA87715B7B8BDCFD7E5936E94BA114A45834AEBA4D141B0E` | 364.345 |

## Exact continuation schedule

No continuation is authorized by this report. If a future user instruction extends Stream C before the checkpoint's six-hour cap expires, resume the same final state with the same audited commit, Python, hashes, chunk size, workers, timeout, and retry ceiling. Set `--target-cases` to the new cumulative Stream C total and use `--phase resume`; the next pending chunk is id 8 with seed `0xC100000000000008`, followed by monotonically increasing chunk ids/seeds. Re-verify that no `0xC100...` campaign is running before resumption. If the recorded six-hour deadline has elapsed, the existing driver will stop rather than silently reset the cap; any new campaign requires a separately authorized fresh state directory and recorded seed allocation.

The checkpoint directories, logs, failure-output directories, and any bulk corpus remain uncommitted.
