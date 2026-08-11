# F-SANDBOX-018 — effective repository mount was not retained

Status: corrected by fresh F-SANDBOX-18; awaiting fresh refutation.

The request-side `HostConfig.Mounts` entry exactly matched the intended
read-only repository bind, but Docker inspect's independent root `Mounts`
entry reported this different effective source:

```text
C:\arbitrary\effective-forged-repository
```

The former selected projection discarded root `Mounts`, so the host could
start a container whose effective `/repo` came from an unrelated tree despite
an exact request declaration. The frozen Windows-custody witness uses the
mandated worktree source
`C:\Users\james\New folder\receiver-reliance-worktrees\portability`; its
canonical container-inspect object is 1,681 bytes with SHA-256
`377617a476f6122efb35562eea09b5f2736a642767c2703a98b419d481842031`.
The forged source's UTF-8 SHA-256 is
`200a92799147453fd469ad4af756403847655dbf950fe19116bda0bfc1113acf`.

The correction retains and validates the two mount representations
independently before container start. `HostConfig.Mounts` remains bound to the
exact requested source, target, read-only flag, type, and consistency.
Docker's root `Mounts` must separately contain exactly one bind with the same
exact source and `/repo` destination, `Mode="ro"`, JSON boolean `RW=false`,
and `Propagation="rprivate"`. The effective mount object has an exact schema;
missing, extra, mistyped, relative, traversal, alternate-separator,
case-mutated, other-source, writable, wrong-mode, and wrong-propagation forms
all fail closed as `SANDBOX_SETUP_FAILURE` before `docker start`.

The trusted repository path is resolved once with native host semantics, then
compared to both unnormalized inspect strings. Native hosted Linux therefore
binds one absolute POSIX identity across plan, request, and effective mount.
Docker Desktop path translation remains an honest setup failure rather than an
admitted alias. Mismatch receipts retain untrusted source types and SHA-256
digests, never the raw untrusted source. Direct and complete mocked host-flow
regressions preserve the exact witness and every declared mutation class while
retaining F-SANDBOX-017 request-side coverage.

F-SANDBOX-021 separates this frozen-source hash from active hosted-path
semantics; the security assertion remains exact source equality on the current
host.
