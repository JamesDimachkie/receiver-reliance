# F-SANDBOX-019 — requested bind propagation was discarded

Status: **RESOLVED locally.** Correction retained; final focused suite green.

The request-side `HostConfig.Mounts[0].BindOptions` declared
`Propagation="rshared"`, while Docker's independent root `Mounts[0]` still
reported the expected effective `Propagation="rprivate"`. The former selected
projection discarded `BindOptions`, so every retained mount field compared
equal and the host could start the container without proving that its exact
create request survived inspection.

The complete frozen Windows-custody container-inspect witness uses source
`C:\Users\james\New folder\receiver-reliance-worktrees\portability` and is
1,749 bytes with SHA-256
`6b1f90d64e2f5fe6beca5b66f30b1c041b76fcb2c5ae5720fbb04468896b62b7`.
Its canonical `{"Propagation":"rshared"}` fragment is 25 bytes with SHA-256
`a2b186f42ef8c0d06df1bb375622bec37b9df5f52aa94bba40d88b97c4c2a3cb`.

The correction makes `rprivate` explicit in the `docker create --mount`
argument and retains the corresponding request-side value. The request mount
has the exact keys emitted for this CLI form, and `BindOptions` must be exactly
`{"Propagation":"rprivate"}`. Missing or mistyped options, unknown members,
non-default propagation, source-creation, non-recursive, and either read-only
recursion override fail closed before `docker start`. The separately retained
root mount must still report the same effective `rprivate` propagation, so the
plan, request, and effective representations reconcile to one value.

This shape follows Docker's official `--mount type=bind` interface and Engine
mount type: `bind-propagation` is supported for bind mounts, `rprivate` is the
documented default, and the optional recursion and source-creation booleans are
omitted when false. The explicit form is the one scheduled for the normative
native hosted Linux job. Daemon acceptance was then confirmed: the hosted
sandbox job ran daemon-real (Docker 28.0.4) and passed in runs 31562391384
and 31564942933, with the mount rendered in exactly this form
(`sandbox-receipt.json`, `effective_mounts`). The local host reports
`INFRA_UNAVAILABLE` because its Docker daemon
is absent. Docker Desktop remains non-normative and may stop at setup as
already documented.

Direct and complete mocked host-flow regressions preserve the exact witness,
cover the supported `BindOptions` mutation surface, prove no rejection reaches
`docker start`, retain F-SANDBOX-017/F-SANDBOX-018 source binding, and keep raw
repository source spellings out of failure receipts.

Primary references:

- <https://docs.docker.com/engine/storage/bind-mounts/#options-for---mount>
- <https://github.com/moby/moby/blob/4d0229860e6fb8385dbbe178c27fa321dcdf2666/api/types/mount/mount.go>
- <https://github.com/docker/cli/blob/4f84911bfe8811e9b028e4b1fee8e7510be79387/opts/mount.go>

F-SANDBOX-021 separates that frozen-source hash from active hosted-path
semantics; active request and effective mounts remain bound to the exact
current-host source.
