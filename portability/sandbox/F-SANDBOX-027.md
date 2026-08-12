# F-SANDBOX-027 — mock-derived comparator rejected real daemon serializations

Status: **RESOLVED locally; hosted rerun pending at the corrective SHA.**

After F-SANDBOX-026 restored full history, hosted run 31549925307 (SHA
`00479e6`) reached the first real Docker daemon this spec has ever executed
against. The build succeeded and the container was created; the host then
stopped with `SANDBOX_SETUP_FAILURE: effective Docker config mismatch` on
four comparisons:

- `command`: actual `null`, expected `[]`
- `network_disabled`: actual `null`, expected `false`
- `init_process`: actual `null`, expected `false`
- effective mount `mode`: actual `""` with `read_write: false`, expected
  `"ro"`

Root cause: every prior validation of `_assert_inspect` ran against mocked
inspect fixtures that pinned explicit-default spellings. The real Docker
Engine on ubuntu-latest serializes unset `Config.Cmd`,
`Config.NetworkDisabled`, and `HostConfig.Init` as `null` (or omits them)
and reports the read-only bind's cosmetic `Mode` as the empty string while
`RW` remains `false`. These are API serialization differences, not
containment differences: writability is bound by `RW`, network isolation by
`NetworkMode: "none"`, and the process contract by the strictly pinned
entrypoint.

Correction (as hardened by the author-separated review): `_assert_inspect`
normalizes exactly the shapes whose null form provably equals the declared
expectation — `null`/absent `Cmd` ≡ `[]`, `null`/absent `NetworkDisabled` ≡
`false`, and mount `Mode ""` ≡ `"ro"` only while `read_write` is `false`.
`HostConfig.Init` is deliberately NOT normalized: the Docker CLI leaves it
nil to delegate to a daemon-wide `default-init` setting, so a nil inspect
value proves delegation rather than falseness. `docker create` now passes
`--init=false` explicitly and inspection demands exact `false`. Receipts
retain the raw inspected values, every other comparison stays strict, and a
writable mount cannot hide behind the Mode normalization.

Regression pins: `sandbox/test_sandbox.py`
`test_daemon_null_default_serializations_are_containment_equal` accepts the
null and absent `Cmd`/`NetworkDisabled` serializations with Mode `""`,
requires `--init=false` in the create plan, rejects a delegated
(`null`) `Init`, rejects Mode `""` with `RW true`, and rejects a null where
the expectation is not the daemon default (`readonly_rootfs`); the prior
mutation tests keep every non-null wrong value failing, including all six
`init` mutations. The suite is 77/77.

The witness receipt is preserved in the run-31549925307 sandbox artifact;
the container had already been force-removed by the harness cleanup before
the job ended, as designed.
