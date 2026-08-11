# Receiver-reliance portability — Fable adjudication return

Date: 2026-08-10

Status: **HISTORICAL FREEZE — ADJUDICATION WAS REQUIRED AT THAT TIME**

Historical-scope note (2026-08-11): this status describes the 2026-08-10
freeze and is not the branch's current disposition. The adjudication was
subsequently executed; `PORTABILITY_VALIDATION.md` is the authoritative current
report, and `LEDGER.md` records the corrective release audit.

Custodian at freeze: Sol root

Authority: `planning/epistemic-handoff/MASTER_PROMPT_RR_PORTABILITY_20260810.md`

Authority SHA-256: `154A9E5397D5D5B5422FD5D7053E7D1E6C6544C5D0152866598E6DC990F9C478`

## 1. Why this packet exists

James directed Sol to stop before another complete N=48 model receipt and
return the state to Fable for adjudication. This packet therefore does not
claim convergence and does not authorize a new enumeration, commit, push,
hosted run, merge, or deployment.

Fable is asked to decide whether another N=48 enumeration is warranted, what
preconditions must hold if it is, and whether the remaining live and sandbox
corrections should precede it. No model process was active when this packet was
written.

## 2. Frozen repository and custody state

- Post-restart continuity note: James restarted the PC before he could confirm
  whether Sol had finished. After the restart, Sol re-verified that this packet
  persisted, the branch and HEAD below were unchanged, the index was empty,
  and no model enumeration process was running. This is recovered persisted
  state, not an assumption that the prior session remained uninterrupted.
- Branch: `sol/rr-portability-modelcheck-20260810`
- Required baseline and current HEAD:
  `4e788d21e882a30bdda2aec3f780537161f81644`
- Separately pushed continuation commit, deliberately not rebased here:
  `389642e9c306efef86470c212d30a8c1ee5f2bdd`
- Index: empty.
- Tracked worktree: unchanged from the required baseline.
- Nonignored untracked surface before this packet: 104 files under the
  portability workflow and `portability/`; this packet is the 105th.
- `git status --short` before adding this packet contained only:
  `?? .github/workflows/portability.yml` and `?? portability/`.
- No portability commit or push exists.
- No hosted matrix or hosted Linux sandbox execution has occurred.
- The task claim remains `in_progress`; validation fields have not been closed.
- All moving subagents were stopped at safe boundaries before this packet was
  written. No N=48 or supplemental model process remains.

## 3. Executive adjudication state

| Lane | State at handoff | Admissible evidence | Blocking fact |
|---|---|---|---|
| Clean-room oracle | **ADMITTED locally** | 35/35 tests; 124 semantic + 248 wrapper = 372 bindings; two distinct no-new-evidence refutations | Successful semantics are fixture-closed; no arbitrary novel semantic claim |
| Concurrency | **ADMITTED locally, qualified** | v3 receipt and fresh independent recomputation; 15/15 focused tests; 242,400 audited-envelope projections | Receipt was generated from a dirty baseline worktree and is not an isolated performance baseline |
| Finite model M | **REJECTED / decision required** | F-MODEL-003 focused correction passes 16 tests | Both complete N=48 receipts are rejected; no post-F-MODEL-003 N=48 run exists |
| Live transport | **REJECTED / correction required** | Eight schedules and W coverage passed under the F-LIVE-004 author state | Fresh refuter showed programmer exceptions can be laundered as infrastructure; F-LIVE-005 is unimplemented |
| Sandbox | **REJECTED / correction required** | F-SANDBOX-021 author suite passed 73/73 on CPython 3.12 and 3.14 | Fresh refuter showed Windows UNC paths are accepted as POSIX; F-SANDBOX-022 is unimplemented; no live Linux daemon evidence |
| Hosted matrix/workflow | **PROVISIONAL** | Matrix suite 44/44; dead commands fixed; exact Node24 action pins | Model/live/sandbox counts are not settled; no hosted receipts; final count removal was not rerun after freeze |
| Reports and close | **PENDING** | This adjudication packet only | `PORTABILITY_VALIDATION.md`, ledger close, terminal Fable return, commits, pushes, hosted receipts, and clean-worktree proof are absent |

No accepted-implementation divergence was established. Every admitted finding
is a defect in a model, oracle, harness, workflow, receipt validator, or
sandbox validator.

## 4. Model receipts: both are rejected

### 4.1 Rejected pre-F-MODEL-001 receipt

The original N=48 receipt used an unsound quotient that assigned distinct raw
keys the same decoded-key identity. Its historical values included quotient
SHA `D2C035988A5BB4EFDCDC29E33249D88B77142CBBE73A310DEB7CB55B8C2EFC88`
and receipt SHA
`081180E9941C04044F203BB4F7B948D091E4F19DA666DD7ECBDF03C03EDE2B14`.
They are rejected evidence.

### 4.2 Rejected F-MODEL-002 receipt

The compact streaming run completed and was durably captured, but a fresh
refuter later falsified its symbolic domain.

- quotient states: `37,432,306`
- transitions: `310,451,001`
- terminal transitions: `68,157,505`
- symbolic terminal traces:
  `37384254939538232037952930021192672958828308`
- excluded frontier edges: `176,168,977`
- excluded trace prefixes:
  `399021998104723850046785009167233023810124673`
- quotient SHA-256:
  `2C233FBF0DD68F1BA3C73BFB9F344473B9EA265CF43D770934A76D586329DD2A`
- receipt SHA-256:
  `C27DEB152C1FDD720EB0FAAE8AD32A06B6DF5DED45763E9E14012F93524D69E9`
- captured stdout SHA-256:
  `6E31130B0E969A23095E5D9952C5640C8587260E4BCD39D035B31C8BFC654772`
- captured stderr SHA-256:
  `3B42B2C98DD27AF4D1F9E118D7B3EFA3885450AFDFE8895FF0B8F016744878FA`

Those hashes prove receipt integrity, not model soundness. The minimized
F-MODEL-003 witness showed the same physical record had two admitted symbolic
encodings with conflicting terminal classes:

- raw bytes: `"a"\n`
- hex: `2261220a`
- base64: `ImEiCg==`
- raw SHA-256:
  `EE195DB0CD14979ECE92E4AC42D91FEF87D1EE254F8DF170907CD674DAB12D44`
- `KEY_A:plain, LF` classified `PARSE_OK`
- `KEY_A_REPEAT:plain, LF` classified `ERR_JSON`

The receipt, every N=48 count above, terminal multiplicities, and quotient
material hash are therefore rejected.

## 5. Current F-MODEL-003 correction — focused only

The fresh author stopped before any new complete enumeration.

Implemented:

- contextual label selection now precedes all parser branches, including
  `INVALID` and `DONE`;
- `KEY_A_REPEAT` is admitted only while consuming an object key after the same
  object has already seen decoded key `a`;
- otherwise `KEY_A` is the only admissible label for the identical raw spelling;
- frozen-alias inventory, the exact witness regression, and reachable-state
  alias checks through N=16 were added;
- F-MODEL-002 is explicitly marked rejected.

Observed after correction:

- `KEY_A, LF` -> `PARSE_OK`;
- `KEY_A_REPEAT` from the initial state -> outside M;
- focused suite: 16 passes and one intentional full-enumeration skip;
- elapsed: 1.235 seconds.

Not completed:

- the supplemental retained-versus-streaming N=18–28 comparison was
  interrupted before yielding a result;
- no post-F-MODEL-003 N=48 enumeration was launched;
- no fresh post-correction refuter has run;
- `EXPECTED_COUNTS.json`, README count tables, and full-test constants still
  contain the rejected F-MODEL-002 values and must not be cited as current.

Current model custody hashes:

| File | SHA-256 |
|---|---|
| `portability/model/parser_model.py` | `F8157FA5791D957C4D9E424B4C2F560A0D7B103A6B2A6B316BCD822BA178BE74` |
| `portability/model/domain.py` | `43E9E3AB1B9DD30F253C6FFE4FDCF6F9440268711775966E6F0EF3CA4307C395` |
| `portability/model/test_model.py` | `2067064788AA9D51427739F5E2E63031AE7DEE6ABED096B6B00A0792A37A43EC` |
| `portability/model/findings/F-MODEL-002.md` | `AC0AC37B7D7263C68C79E70306A7B6B3F317EDE72A9688C6E2543E159825CA70` |
| `portability/model/findings/F-MODEL-003.md` | `B739C442DC7B6130A77731C0F42EC1AF03DDFA26543A08923097D9B7C3ECD25A` |
| rejected `EXPECTED_COUNTS.json` | `CFF645B019AA7AC7546C125BB8BE05BF1D28CCE341EFA663F00FAD5550E8B689` |
| rejected-count `README.md` | `25AAE7F742067BBD16331F13FC12763278906730A8F2AEA8F2294BF04205FFC9` |

The F-MODEL-003 edit changed `domain.py`; any future receipt must bind the new
input hash. A new receipt cannot reuse the frozen metadata hashes from the
rejected F-MODEL-002 run.

## 6. Decision requested from Fable: next N=48 receipt

Fable should choose one of these paths explicitly.

### Path A — authorize another N=48 run after preconditions

Recommended preconditions:

1. Re-run retained-versus-streaming equivalence at least through N=28.
2. Exhaustively prove, over the declared bounded prefix domain used for the
   precheck, that raw-expansion aliases are mutually exclusive per state and
   cannot reach conflicting terminal classes.
3. Re-run F-MODEL-001 and F-MODEL-003 minimized witnesses plus their neighbors.
4. Verify compact-key injectivity, round-trip, and strict byte-length increase.
5. Freeze and hash every receipt input, including the changed `domain.py`.
6. Use a durable output path or checkpointed final receipt, not stdout-only
   custody. Keep an attached wrapper with at least 90 minutes of headroom.
7. Record host memory/commit headroom and avoid concurrent memory-heavy work.
8. Admit no count until terminal exit 0, receipt recomputation, focused tests,
   and a fresh author-separated refuter all pass.

### Path B — require more model redesign before another run

Fable may judge the repeated quotient/domain defects sufficient reason to
require a stronger physical-trace canonicalization invariant or a differently
factored model before paying for another complete enumeration. If so, the
current focused patch remains experimental and no N=48 run should begin.

### Path C — decline another complete receipt

Fable may narrow the portability claim and return the bounded-state lane as
unresolved. In that case the rejected count tables must be removed or clearly
quarantined, matrix must not gate on them, and the terminal report must not use
the charter's bounded-state success statement.

Sol recommends **Path A only after all eight preconditions are independently
checked**. This is a recommendation, not an authorization.

## 7. Other unresolved lanes Fable must account for

### 7.1 Live transport — F-LIVE-005 unimplemented

F-LIVE-004 made monitor I/O failures sticky and produced 21/21 passing focused
tests, but fresh refutation showed its catch covers the entire monitor loop.
A decoder or state-machine `ValueError`/`OSError` can therefore be mislabeled
as transport `INFRASTRUCTURE_ERROR` exit 2.

The F-LIVE-005 author stopped without lasting edits. Current live source still
has the defect. Required next step: scope transport normalization to the actual
`readline()` call and provide a distinct durable internal-harness failure class
for programmer faults, followed by fresh refutation. The 21/21 result is not a
final admitted live-harness count.

Current key hashes:

- `controller.py`:
  `CFA4B94F56AE65B4975D24676838596B49415A154B1C52BD526104D35741C6E8`
- `replay.py`:
  `F09EF02C870FE3CD334F7A5B462160AE2DB61D476519DABCCFD482C1A7C0C0C1`
- `test_live.py`:
  `2E1CC1AB78F10AF3BB7770848314E2741EA344821BDBB5B862C7A267D187356A`

### 7.2 Sandbox — F-SANDBOX-022 unimplemented

F-SANDBOX-021 separated frozen Windows witness custody from active checkout
semantics and passed 73/73 tests on CPython 3.12 and 3.14. Fresh refutation then
showed a foreign Windows UNC object is accepted on Linux/Darwin because
`PureWindowsPath.as_posix()` begins with `//` and the POSIX branch checks only
for a leading slash.

Minimized unresolved witness:

```python
_repository_source_for_host(
    PureWindowsPath(r"\\server\share\receiver-reliance"),
    "Linux",
)
```

Observed result: `//server/share/receiver-reliance`.

The F-SANDBOX-022 author stopped before edits. Required next step: validate path
dialect before rendering, preserve native Windows drive/UNC and native POSIX
paths, reject foreign dialects, and freshly refute. The 73/73 result is not a
final admitted sandbox count. Local Docker remained honestly
`INFRA_UNAVAILABLE`; no hosted Linux daemon evidence exists.

Current key hashes:

- `run_sandbox.py`:
  `AFB9EACCED958DC0B366952385E88A9F633C3D5CF184B3D199144712DDAC211D`
- `test_sandbox.py`:
  `970B8FA3556166B6D502345D2D4E9516CFC439B9A8043C03EA3D796D48C6680D`

### 7.3 Matrix/workflow — frozen provisional integration

Completed changes include package-correct bounded commands, concurrency v3
receipt paths, adversarial count-drift rejection, gating-versus-observation
separation, and exact Node24 action pins.

Settled local expected counts:

- matrix: 44;
- clean-room oracle: 35;
- concurrency: 15.

Deliberately unsettled:

- model focused count and every N=48 count;
- live count;
- sandbox count.

The matrix author stopped before a final rerun that removed or updated every
rejected provisional binding. Fable must treat `plan.json` and its last 44/44
result as provisional integration, not a release gate.

Current key hashes:

- workflow:
  `A212DF57F2ECC38264211C953ACA4B4C42AD5C3F9AD586FC2F0CA239D6F063D3`
- `plan.json`:
  `0247FFF1D6BE150580E85859BB308A7DB6A48ABEF7F32C8062F913B14606F7CD`
- `receipt.py`:
  `EA5565F0AF6AF5E1E97722B1B35388A351BEE660F8C5AC16B3573D23675ABA16`
- `test_receipt.py`:
  `3421BE7DF9F0CDF7691A82E7E8FE11DBEDB4984544B54739A966279FA2938B59`

Exact action pins in the frozen workflow:

- checkout: `3d3c42e5aac5ba805825da76410c181273ba90b1`
- upload-artifact: `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
- download-artifact: `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`
- setup-python: `ece7cb06caefa5fff74198d8649806c4678c61a1`

## 8. Locally admitted lanes

### 8.1 Clean-room oracle

- focused tests: 35/35;
- four frozen packs: 124 semantic + 248 wrapper = 372 unique bindings;
- fixture binding SHA-256:
  `78FC43470C9AD4C41932CD38926F8430A004D02FE18E065D3DD6BE59A5A4B80B`;
- oracle source SHA-256:
  `2148F0C9C4ED38692B9C6658EC48CDD9628688E6C1708345C89A44AB91A05F17`;
- oracle test SHA-256:
  `27DEBE76E80FAE81FBA9B6C26FF2451F688027C0DC15D4FEEAC8B8FAE71F9339`;
- status index SHA-256:
  `3DC6C2C4E123F00C31587EB3BE6899B81EC9A8CE83EDDAA2980C9F8B79127A96`;
- first fresh refutation compared all 57 frozen closures and 24 hostile
  boundary cases;
- second distinct seeded refutation compared 122 additional cases against both
  accepted ABIs;
- no new defect in either final pass.

Remaining scope: semantic success is closed to the four fixture packs; raw
schema routing is bounded; JCS number emission is integer-only.

### 8.2 Concurrency v3

- focused tests: 15/15;
- P=1,2,4,8,16,32 at 200 requests per caller;
- P=16,32 soaks at 1,000 requests per caller;
- library and process modes, paired identical-seed runs;
- 242,400 independently projected audited envelopes;
- normative receipt SHA-256:
  `98786009478343F4A7D84FC594A67C7E09BE64483865123AC1C73E4144525699`;
- physical comparator binding:
  `AC74DD0932D4476E6374DE7F1A8596C9173A909FBB21845D8AFD13DE3E3A74BD`;
- oracle binding:
  `78FC43470C9AD4C41932CD38926F8430A004D02FE18E065D3DD6BE59A5A4B80B`;
- fresh refuter independently recomputed every declared sequence, aggregate,
  physical comparator, semantic projection, cleanup result, and 3.14t
  `INFRA_UNAVAILABLE` receipt; no defect.

Qualification: the receipt records `git.clean=false` at the baseline and
coexecution resource observations. It is not clean-commit-bound or an isolated
performance baseline. The semantic projection does not independently oracle
every nested audit metadata field such as `engine_generation`.

## 9. Expanded gate evidence already observed

These categories remain separate and are not one merged pass count:

- frozen 0.2 parity: 800/0;
- composed 0.3 parity: 800/0 and 107/0;
- grounded 0.4 behavior: 504/0;
- contract lint: 0 findings;
- lint meta-gate: 7/0;
- properties: 2,296/0;
- audited adversarial: 6,497/0;
- internal held-out synthetic proof: 7 pass;
- seeded fuzz smoke: 31/31 strategies;
- batch: 2,160/0;
- single-pass audit: 1,142/0.

This is pre-handoff local evidence. The charter's final post-change expanded
gate has not been run and the evidence above does not close the task.

## 10. Quality and dead-prose state

A read-only whole-surface prehandoff audit found no unresolved task-marker
tokens, classic repetitive AI filler, BOMs, missing final newlines, trailing
whitespace, tabs, mixed newline encodings, malformed Markdown fences, broken
local references, undeclared third-party imports, or stray unignored temporary
artifacts.

The same audit found material evidence-quality defects and routed them rather
than hiding them:

- rejected model counts remained current-looking in README/expected-count
  surfaces;
- historical finding files could be mistaken for present disposition;
- concurrency status omitted its current smoke receipt;
- live infrastructure prose exceeded runtime classification;
- matrix commands were dead from the repository root;
- workflow actions were pinned to the retiring Node20 runtime;
- deterministic test counts were incompletely bound.

Oracle and concurrency status prose was corrected. Matrix commands and Node24
pins were corrected. Model/live/sandbox remain unresolved as described above.
A final frozen-tree dead-prose, stale-hash, count, link, and whitespace pass is
still required after Fable chooses a path and all writers stop.

## 11. Rejected and obsolete evidence that must remain separate

- contaminated original oracle lineage: rejected wholesale;
- pre-F-MODEL-001 N=48 receipt `081180...`: rejected;
- F-MODEL-002 N=48 receipt `C27DEB...`: rejected by F-MODEL-003;
- live discovery schedule SHA `C719ABA8...`: superseded by corrected W evidence;
- concurrency v1 receipts: stale;
- concurrency v2 stopped receipt
  `1DEB0148450A0F430DAB8668CB11FC9F3AD4FF56CC5D809AF2348CC20DBE9797`:
  rejected harness-layer comparison;
- live 21/21 author result: rejected as terminal evidence by F-LIVE-005;
- sandbox 73/73 author result: rejected as terminal evidence by
  F-SANDBOX-022;
- matrix model/live/sandbox count bindings: provisional and not release
  evidence;
- local Docker absence: honest `INFRA_UNAVAILABLE`, never a hosted sandbox
  substitute.

## 12. Work still required for terminal done

Depending on Fable's decision:

1. adjudicate and, if authorized, finish F-MODEL-003 prechecks and a new N=48
   run plus fresh refutation;
2. implement and freshly refute F-LIVE-005;
3. implement and freshly refute F-SANDBOX-022;
4. finalize matrix counts and run two no-new-evidence matrix passes;
5. run the full focused integration set and the final expanded gate;
6. perform the final frozen-tree quality/dead-prose audit;
7. create the first scoped commit and first authorized push;
8. collect hosted normative, expanded-gate, and Linux sandbox receipts;
9. write `orchestration/PORTABILITY_VALIDATION.md` and update
   `orchestration/LEDGER.md`;
10. run the final gate, close the claim, create the final commit, and make the
    second authorized push.

Until then, the worktree must not be described as converged or Fable-ready in
the terminal sense. This packet is the handoff *to* Fable for adjudication.

## 13. Nonclaims

No efficacy, novelty, security, fuzzing-completeness, external-standard, or
universal-portability claim. The proof tier stays `internal held-out`.

The charter's only permitted success statement is not asserted here because
the bounded model, live harness, sandbox harness, hosted matrix, final gate,
reports, commits, pushes, and clean-worktree proof remain open.
