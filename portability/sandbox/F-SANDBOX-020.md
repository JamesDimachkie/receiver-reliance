# F-SANDBOX-020 — native omitted consistency was rejected

Status: corrected by fresh F-SANDBOX-20; awaiting fresh refutation.

The request-side mount validator required a `Consistency` member even though
the pinned Moby `mount.Mount` representation tags that member `omitempty` and
the scheduled `docker create --mount` command requests no consistency option.
Deleting only `HostConfig.Mounts[0].Consistency` from the otherwise exact
native inspect shape therefore stopped the hosted Linux lane before
`docker start`.

The frozen Windows-custody request-mount fragment uses source
`C:\Users\james\New folder\receiver-reliance-worktrees\portability` and is 171
bytes with SHA-256
`2f7ff46e5f4f59082d6b0445969bd56bbf2f79c2609b245a171e58da8b0a85e9`.
Its complete canonical container-inspect witness is 1,733 bytes with SHA-256
`d1e6e191beb0a144fbc45cb99215f365dc8a7d2769b49927fbc54fc188dff1a1`.

The correction changes only the representation of the default consistency
mode. The exact request schema now requires `Consistency` to be absent and
projects that proven omission to the internal value `consistency="default"`.
An explicit empty member is not admitted without evidence that the pinned
native implementation emits it; every explicit member—empty, non-default,
mistyped, or structured—is an extra and fails closed before start. The plan
records both the abstract default and the required omitted inspect member.

The source, target, JSON-boolean read-only flag, exact
`BindOptions={"Propagation":"rprivate"}`, effective root mount, image,
container, process, hostname, environment, resource, and security bindings are
unchanged. Direct projection/assertion and the complete mocked host flow prove
that the exact omission reaches attached start and host `PASS`. A mutation
matrix proves that explicit empty, `default`, non-default, null, boolean,
integer, array, and object members stop before start. Historical F-SANDBOX-014
through F-SANDBOX-019 hashes reconstruct their old explicit-empty evidence
only for custody; current positive fixtures use the native omitted shape.

Primary representation evidence:

- Moby `api/types/mount.Mount.Consistency` is tagged `json:",omitempty"` in
  the pinned source used by F-SANDBOX-019.
- Docker CLI's scheduled bind-mount create form exposes no consistency option;
  it requests read-only and `bind-propagation=rprivate` only.

F-SANDBOX-021 separates these frozen-source custody hashes from active
hosted-path semantics. Native omission remains tested against the current
host's exact resolved source without a universal source-dependent byte hash.
