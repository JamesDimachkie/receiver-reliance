# Hardened Linux sandbox

This sandbox supplements the native portability jobs. It does not replace any
native operating-system, architecture, or runtime result.

The lane is treatment-exposed. Nothing here may author the research program's
future blinded worlds, oracle, gold, or renderer. The sandbox reads only the
checked-out repository and the synthetic proof corpus used by the expanded
gate.

## Run

From the repository root, with a clean checkout descended from
`4e788d21e882a30bdda2aec3f780537161f81644`:

```text
python -B portability/sandbox/run_sandbox.py
```

Add `--receipt PATH` to persist the same canonical JSON that is written to
stdout. `--print-plan` emits the exact Docker build and create commands without
contacting Docker. Exit 0 means all twenty expanded-gate commands exited 0 and
their declared counts were observed. Exit 1 is a setup, hardening, gate,
timeout, or cleanup failure. Exit 2 with `status=INFRA_UNAVAILABLE` means a
Docker CLI or Linux daemon was not available; absence is recorded and is not a
normative test failure. Even when the Docker probe cannot reach a daemon, that
receipt includes the exact Git state, host profile, Dockerfile-derived image
identity, and build/create plan that would have run.

Static checks require only the repository's supported Python runtime:

```text
python -B portability/sandbox/test_sandbox.py
```

## Effective boundary

The Dockerfile pins the multi-architecture manifest for the official
`python:3.14.1-slim-bookworm` image. The host runner creates, inspects, then
starts the container with:

- the repository as the sole bind mount, mounted read-only at `/repo`;
- a read-only root filesystem and one application-writable tmpfs at `/tmp`,
  exactly 256 MiB with `noexec,nosuid,nodev`;
- network mode `none`, every capability dropped, and
  `no-new-privileges=true`;
- numeric user and group `65532:65532`;
- 2 CPUs, 4 GiB memory with no additional swap, 256 PIDs, and 16 MiB shared
  memory;
- no environment file, secret mount, Docker socket, device, host namespace,
  or privileged mode. Only fixed non-secret environment values are supplied.

The bind source is an exact identity, not merely a destination and read-only
flag. The host resolves the trusted checkout path once using native platform
semantics, records that source and its SHA-256 in the plan, supplies the same
string to `docker create`, and verifies two independent Docker representations
before start. The request-side `HostConfig.Mounts` entry must be the sole
read-only bind from that exact source to `/repo`. Its exact `BindOptions`
object must contain only `Propagation="rprivate"`, which the create command
requests explicitly with `bind-propagation=rprivate`; omitted, malformed,
additional, recursive, create-source, or alternative propagation options fail
closed. The CLI does not request a consistency mode, and Moby's request-side
`Consistency` member is `omitempty`; the native default inspect shape must
therefore omit that member. An explicit empty member, a non-default value, or
any non-string/value-shaped variant is an unsupported extra and fails closed.
The selected receipt records the validated omission as the abstract
`consistency="default"`; it does not claim Docker emitted that field. The root
`Mounts` entry must independently report the sole effective
bind with the same exact source and destination, `Mode="ro"`, JSON boolean
`RW=false`, and the same `Propagation="rprivate"`. Both arrays and every
required member are bound; missing, extra, mistyped, alternate, or mismatched
request/effective mounts fail closed even when the other representation is
exact. Inspected source
metadata is never normalized, so relative, traversal, alternate-separator,
case-mutated, or other-source forms cannot alias the intended checkout. A
mismatch receipt records each untrusted source's type and digest rather than
its raw value.

The regression suite keeps historical byte custody separate from active
portability semantics. Canonical witnesses whose hashes were first recorded in
the mandated Windows worktree carry that frozen Windows source explicitly;
they are not treated as universal hosted-path hashes. Active assertions derive
their expected identity from the current resolved checkout and exercise exact
Windows, Linux, and macOS source forms through create, both inspect mount
representations, and the full mocked start boundary. A source-dependent byte
length or digest is never used as the success oracle for an active hosted
path.

This dual source binding is directly portable to the native hosted Linux
sandbox, where the trusted host resolution, request metadata, and effective
metadata expose the same absolute POSIX path. Docker Desktop can translate a
Windows or macOS client path into a Linux-VM-internal effective source. The
harness deliberately does not guess translation aliases: if either inspect
representation differs from the exact path supplied by the plan, the Desktop
run ends as `SANDBOX_SETUP_FAILURE` before container start and supplies no
sandbox PASS evidence. The hosted native Linux result remains the normative
sandbox lane.

The effective environment is also fail-closed. The pinned base metadata and
every Dockerfile/create entry form one exact `Config.Env` allowlist, including
an explicit `HOSTNAME=rr-sandbox` so the runtime does not add an unrepresented
name. The inspect parser requires unique, valid `NAME=value` strings and exact
names and values; missing, extra, malformed, duplicated, secret-like, or
value-mutated entries stop the run before start. Only sorted names plus the
validated, public `HOSTNAME=rr-sandbox` value enter the selected-config
receipt. After the inner record validates, its observed name set must equal
those inspected names exactly, and its secret-name set must be consistent and
empty. No other environment value is copied into the selected-config receipt
or a mismatch detail.

Hostname identity is independently bound across the same boundary. The create
plan supplies `--hostname rr-sandbox` and `HOSTNAME=rr-sandbox`; container
inspect must expose exact string `Config.Hostname="rr-sandbox"`; and the
inner gate records the kernel UTS-namespace observation from
`os.uname().nodename` and the process's `HOSTNAME` value, both of which must
also equal `rr-sandbox` before any repository command runs. Only that one
allowlisted, non-secret environment value is retained; general environment
values remain excluded. Both observations are included in the stable boundary
projection and reconciled by the host to inspected `Config.Hostname`, the
validated `Config.Env` value, and the declared plan. Missing, null, wrongly
typed, case-mutated, whitespace-mutated, or different values fail closed
before host PASS.

Docker inspect metadata is type-bound as well as value-bound. The repository
mount's `ReadOnly` member must be the JSON boolean `true`; string and numeric
lookalikes are not coerced. `ReadonlyRootfs` must likewise be exactly true,
while `Privileged`, `PublishAllPorts`, `AutoRemove`, `OomKillDisable`, `Init`,
and the legacy `Config.NetworkDisabled` bit must be exact JSON booleans with
their declared false values. The effective network boundary remains the
separately required `HostConfig.NetworkMode="none"`. Missing, null, string,
integer, or opposite-boolean forms stop the run before container start.

The execution identity is part of the effective boundary. The image declares
the exact exec-form entrypoint
`["python","-B","/repo/portability/sandbox/expanded_gate.py"]` and an empty
command array. The create plan supplies no command override, records both
expected values, and the host requires Docker's selected `Config.Entrypoint`
and `Config.Cmd` to match them exactly before start. The host also binds the
actual process identity exposed by container inspect: root `Path` must be
`python`, and root `Args` must be exactly
`["-B","/repo/portability/sandbox/expanded_gate.py"]`. Missing, null,
inherited, shell-form, string, extra, reordered, case-mutated, path-mutated,
or wrongly typed execution fields stop the run before container output can be
treated as gate evidence.

The container object identity is bound across the same flow. Docker create
must return exactly one lowercase 64-hex identifier, with at most its single
line terminator; the inspected root `Id` must be the exact same string. The
host then uses that unchanged identifier for inspect, attached start, and
forced cleanup. Missing, null, wrongly typed, prefixed, truncated, extended,
case-mutated, whitespace-mutated, or different inspect identifiers stop the
run before start. Malformed create output is rejected before it becomes a
cleanup target.

The image identity is bound as well. The build tags one deterministic
Dockerfile-derived reference, image inspect must return a lowercase
`sha256:` plus 64-hex `Id`, and the create command consumes that same exact
tag. Before start, container inspect's root `Image` must equal the built image
ID and `Config.Image` must equal the requested tag. Both image and container
inspect responses must be duplicate-free, finite JSON arrays containing
exactly one object. A missing, malformed, case-mutated, prefixed, truncated,
extended, or different ID/tag—or ambiguous inspect JSON—stops the flow before
container output can be admitted.

Docker necessarily supplies bounded `/dev` and `/dev/shm` tmpfs mounts and
kernel pseudo-filesystems such as `/proc`; these are runtime plumbing, not
application storage. The script adds no writable bind or volume. The inner
gate verifies the read-only root and repository mounts, the exact `/tmp`
bound/options, cgroup v2 CPU/memory/PID limits, zero capability masks,
`NoNewPrivs=1`, numeric identity, loopback-only network namespace, and absence
of secret-like environment names before it touches a test command. A mismatch
stops the run.

## Receipts and stop behavior

The host receipt records the SHA and clean status; Docker client/server and
architecture; image/Dockerfile identity; selected effective container config;
build, container, and cleanup exits; elapsed time; and hashes of all captured
streams. The inner receipt records the Linux/kernel/runtime/encoding profile,
hardening proof, exact command list, expected suite counts, exits, elapsed
times, resource observations, and stdout/stderr hashes.

Forced container removal is also receipt-safe. Success, nonzero exit, timeout,
launch failure, unexpected call exception, malformed process result, and the
absence of a created container are classified without escaping receipt
emission. A cleanup failure after a primary PASS changes the host result to
`CLEANUP_FAILURE` and exit 1. If the primary run already failed, that primary
status remains authoritative while the cleanup object records both the prior
status/exit and the cleanup failure, so neither failure is discarded.

JSON uses sorted keys and compact separators. The inner receipt also carries a
`deterministic_projection_sha256` over the security boundary, exact commands,
exits, and count evidence. Raw benchmark timings, resource measurements, and
stream hashes remain in the receipt but are excluded from that replay-stable
projection because the two performance gates intentionally print timings.
Every successful-command stdout and stderr transcript is retained as canonical
base64. The host decodes it strictly and recomputes both the byte count and
SHA-256; a zero-byte stream therefore also binds SHA-256 of the empty byte
string. Transcript, count, and digest are one checked evidence surface.
Grounded count summaries may retain their gate-specific human prefix, but the
validator requires one and only one `checks=`/`failures=` summary across both
streams and rejects duplicate fields even when they share one line.
Unittest summaries are normalized line-by-line for LF or CRLF before the
single `Ran 7 tests` / single `OK` / no-failure decision.

The host treats container output as untrusted. Host `PASS` requires container
exit 0 and one canonical JSON record conforming exactly to the inner-receipt
schema: the treatment-exposed flag; Linux environment; effective identity,
mount, tmpfs, network, capability, no-new-privileges, secret-name, and cgroup
proof; the twenty ordered command identities; zero exits and timeouts; exact
declared counts; retained stream transcripts, hashes, and byte counts;
resource observations; and a host-recomputed deterministic projection hash.
Missing, extra, malformed, or inconsistent evidence produces
`INVALID_CONTAINER_RECEIPT` and host exit 1.

Execution stops at the first nonzero exit, timeout, or count mismatch. Every
executed command retains stdout and stderr as base64, so the decision transcript
survives without a retry or an attempted fix.
This is bounded negative evidence only: it is not a security, completeness,
efficacy, novelty, external-standard, or universal-portability claim.
