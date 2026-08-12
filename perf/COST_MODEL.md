# Integration cost model

## Current host-scoped observations

These are observations for CPython 3.12.10 on Windows 11 `10.0.26200`, AMD64,
over the 124 committed semantic fixtures sorted by UTF-8 `entry_id`. They are
not budgets or portable performance guarantees. An optional Windows `tasklist`
image-name-prefix snapshot observed 9 Python/PyPy/GraalPy-named processes
before and 10 after. That racy, permission-dependent Windows probe is not a
universal process census. Scheduler, power, antivirus, cache state, and other
desktop load were uncontrolled.

| Integration mode | Included work | Observed median | Choose it when |
|---|---|---:|---|
| `decide()` library | Frozen decision in the caller's Python process | **2.856 ms/decision** | You need only the frozen sealed response and can load trusted code in process. |
| `decide_audited()` library | Frozen response plus request binding, witnesses, closures, record references, and audit seal | **2.936 ms/decision** | You need the audited envelope in the same Python runtime. Paired audited/direct ratio median: **1.033x**. |
| persistent framed sidecar | One audit-traced isolated sidecar startup, 124 `RR-SIDECAR/1` request/response frames, digests, pipe I/O, response flushes, clean shutdown | **5.402 ms/request** | You need audited bytes across an anonymous local process/language boundary. Paired sidecar/audited ratio median: **1.782x**. |
| fresh isolated stdio | One audit-traced `python -I -B ... pcb_runner.py execute` process per frozen decision | **227.178 ms/decision** | Low-volume tooling or per-decision failure isolation where startup latency is secondary. Paired ratio to `decide()`: **76.518x**. |

The sidecar and audited library return audited 0.4 payloads. The fresh ABI
returns a frozen sealed response. Choose output semantics and integration
boundary before comparing time.

All figures are paired/interleaved receipt samples. Library and hotpath probes
use 11 repetitions and three inner calls per fixture. Whole-corpus sidecar and
fresh-process probes use three alternating-order repetitions. Sidecar samples
were `5.488954, 5.401788, 5.314694` ms/request; fresh-process samples were
`228.112729, 225.344965, 227.177932` ms/decision. Every Python process in the
evidence run used `-B`, a unique empty temporary `-X pycache_prefix`, and the
Python repository-read audit hook, so the observations include custody
instrumentation.

## Hot-path profile

- SHA-256 over already canonical decision input: **0.000781 ms** median.
- Decision-input JCS plus SHA-256: **0.009529 ms**, paired ratio **12.127x**.
- SHA-256 over raw request bytes: **0.001920 ms**.
- Complete audit self-zero JCS plus SHA-256: **0.021327 ms**, paired ratio
  **11.536x**.
- Accepted single-pass audited decision: **3.101564 ms**, paired ratio
  **0.995779x** to its retained legacy oracle. Individual ratios ranged from
  **0.985817x** to **1.013786x**.

The accepted single-pass path remains byte-identical, reduces predicate work
on 93/124 fixtures, and saves 116 atomic calls across the corpus. Its ratios
still straddle parity, so no speedup is claimed and no new optimization is
admitted.

Instrumented attribution over 372 audited calls placed `decide_audited` at
4.342 s cumulative, frozen `_execute` at 4.265 s, and frozen `schema_errors`
at 3.666 s. These overlapping cProfile values are attribution only and cannot
be summed into causal shares. Digest math is not the integration bottleneck;
changing the frozen validation walk is outside this additive package.

## Choice guidance

1. Need audited witnesses and request binding in a Python host: use
   `decide_audited()`.
2. Need the same audited payload across an anonymous local process boundary:
   keep `perf/sidecar/rr_sidecar.py` alive and use
   `perf/sidecar/supervised_client.py` one request at a time.
3. Need only the frozen sealed decision in process: use `decide()`.
4. Need an occasional one-shot sealed decision: use the documented `-I -B`
   ABI and accept process-startup-scale latency on this host.
5. Need concurrency: create independent in-process workers or independent
   sidecars. No pool or concurrency-throughput claim is measured here.

Re-run on the deployment host and representative request-size distribution
before setting objectives, timeouts, or capacity. Do not derive throughput as
`1000 / median`; queueing, tails, saturation, and response consumption are not
modeled.

## Admitted receipt custody

- `perf/receipts/robustness/profile-windows-cpython-3.12-20260812-attempt6.json`
  — raw SHA-256
  **F54B6300ACA8BB4E3D7BBE7F8F1A110B7D558A5E9E8D7448DD5F7315CC3B0166**;
  embedded pre-seal SHA-256
  `694A5CABB14F5F4616135B5C4EBF67CCD0933422138CDC6403375772FBBB0737`.
- `perf/receipts/robustness/sidecar-parity-windows-cpython-3.12-20260812-attempt9.json`
  — raw SHA-256
  **E082C27DB6CE00B95A594A26FD0460BC632D54E0CE4CB159C85A6EF56E8AB4AF**;
  embedded pre-seal SHA-256
  `1268D1EC32A766A2918651188EC550FD0F6243BB027F7FF1357E46FF386CB047`.

The profile pins the Python-audit-visible repository inputs across its full
traced child set; the sidecar receipt (728 checks) pins its own traced set.
Exact traced-set/pin-set equality is verified by
`perf/sidecar/verify_receipts.py`. This is Python `open` audit-event custody
for repository regular files in the traced Python process tree, not native
or OS-wide I/O provenance — and pins record file bytes at manifest time
(after the run), not at each read: a file mutated mid-run is pinned at its
post-run content (F-WP5-006).

Both receipts bind their actual `sys.orig_argv`, including `--receipt` and the
immutable target path. `verify_receipts.py` pins their raw bytes, embedded
seals, manifests, source/data hashes, envelope probes, stable PID, no-replay,
stderr, EOF, and platform-labelled process observation.

## Immutable chronology (not current authorities)

Earlier receipts remain byte-untouched and are excluded from current numbers:

- profile `20260811.json`
  (`FF1367551CE16C0FD7369B9E348E8F8235D2D59CE939CE8EE87B33881FFED8B0`):
  overlapped an accidentally live duplicate profiler; hand-maintained custody.
- profile `20260811-attempt2.json`
  (`C2EE7E8F8B8D9FFCFEF1136B483F08D52DAA684001727D5C047F7E6E702CC0A9`):
  rerun of the pre-trace schema; still lacked complete execution-input custody.
- profile `20260812-attempt3.json`
  (`87FC091EAAFAB4328D78BDBCBC4105A1F099AB36B0EF997148D9DD5CEB6B9C5D`):
  first complete-manifest schema, before unique trace-ID argv binding.
- profile `20260812-attempt4.json`
  (`938CE0B718FE4A42CB4923719C472213E3BAFCEE243CC62EDDA91F15AED82274`):
  unique trace IDs and complete custody, but measured the superseded unframed
  sidecar and used an unscoped scalar process-count label.
- sidecar `20260811.json`
  (`4B8FE3E695EA4C6C2DBD46A0731F11E71FC4C8E103AFAB22D74C041CDA0DFE02`):
  initial 4 MiB client bound and pre-total supervisor.
- sidecar `20260811-attempt2.json`
  (`38B3FA5AFCE771E9788750A83569634778DF0B17C2E2EEB95AC9ABA18A846300`):
  corrected the response bound but did not bind the actual receipt argv.
- sidecar `20260812-attempt3.json`
  (`CD33B4CFAB9637430D9A612AFE2A2EFC89FC38C24464D8D5B4B99F916750082C`):
  added a response-overlimit probe whose child retained a pre-request race.
- sidecar `20260812-attempt4.json`
  (`328F7A541E538F688A8AE6A880CC953914BBA99A7A2F2315E58EFCD42AEECD02`):
  made that probe wait for a request; still lacked complete traced custody and
  actual receipt argv.
- sidecar `20260812-attempt5.json`
  (`96FCA86A26A75168D3B1B59F6FD9AB54B573359FC01678BBDC5574BC1659DBFC`):
  added complete Python-read custody, actual argv, stderr/EOF/no-replay probes;
  it did not cover the one-byte mid-write witness.
- sidecar `20260812-attempt6.json`
  (`6F31ED7A66CC5874EA96E78951E9125401AFD2938D1083835D5A902AC65EF567`):
  covered the 1 MiB mid-write `POISON` witness with phases and epochs, but
  response identity still depended on timing/queue state rather than a
  request-bound transport envelope.
- sidecar `20260812-attempt7.json`
  (`3DB36E66D6F927558257C95CBD7352E8B044F50459CB67DE864C263F4FFAA977`):
  introduced the request-bound frame and passed 723 checks, but its test prose
  treated an OS-dependent completed-write observation as a required zero. The
  same `POISON` response was rejected; attempt 8 corrects only that evidence
  classification and rebinds the source bytes.
- profile `20260812-attempt5.json`
  (`8F8A7EE1F97456CD4131C03AF5C21FAD7743C89ACCF385603675EC13BFBC3093`):
  the first admitted profile; superseded because the Intake 10 grounded
  0.4.1 governance increment changed pinned sources
  (`rr_api.py`, `rr_batch.py`, `test_single_pass_audit.py`) under it.
- sidecar `20260812-attempt8.json`
  (`B81D79867F5EACD8ABCF93FEE29DACFA405AD738FA52AC5FDFBA7AFB3A7C0518`):
  the first admitted sidecar receipt; superseded by the same grounded
  source-pin change plus the F-WP5-007 repairs (valid early responses were
  spuriously rejected; the counted-timeout probe raced child cold start;
  stderr capture covered only the first chunk).

## Admission and nonclaims

**Charter fallback taken.** No optimization lands. The evidence supports
known scoped costs and a concrete stdlib-only framed anonymous-stdio package.
It supports no universal latency, throughput, scalability, security,
availability, efficacy, external-standard, or cross-platform claim.
