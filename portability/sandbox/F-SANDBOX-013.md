# F-SANDBOX-013 — string `false` promoted to read-only mount evidence

Status: **RESOLVED locally.** Correction retained; final focused suite green.

The exact mocked container inspect supplied the repository mount's untrusted
JSON `ReadOnly` member as the string `"false"`. `_selected_inspect` applied
`bool("false")`, promoted it to Python `True`, and `_assert_inspect` accepted
the mount as read-only. The full host flow could then start the container and
admit a structurally complete forged inner PASS receipt.

The canonical inspect witness is 1,044 bytes with SHA-256
`de64a3f9033843d5f746a99211bc8e2934bf57973de1d0a9b93c5dd1bb4883e8`.
The admitted inner receipt has SHA-256
`eb926d64f89077a1b73000b1c144c5a73a64ccce531273152967ddd20acc4f55`.

The correction removes the truthiness conversion and compares JSON-shaped
inspect evidence with exact Python/JSON types, so booleans are not equal to
integers. It requires the mount `ReadOnly` and root `ReadonlyRootfs` values to
be exact booleans equal to true. It also retains and requires exact false
booleans for `Privileged`, `PublishAllPorts`, `AutoRemove`,
`OomKillDisable`, `Init`, and legacy `Config.NetworkDisabled`; the effective
network isolation remains independently bound by `NetworkMode="none"`.
Required collection and namespace-mode metadata is shape-checked without
truthy fallback coercions.

Direct and full mocked host-flow mutation matrices cover missing, null,
string, integer, and opposite-boolean forms for every declared field. The
preserved exact witness now stops before `docker start` with
`SANDBOX_SETUP_FAILURE`/exit 1, while the exact valid neighbor and all prior
F-SANDBOX-003 through F-SANDBOX-012 replays remain green.
