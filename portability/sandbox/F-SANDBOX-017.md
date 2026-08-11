# F-SANDBOX-017 — repository bind source was discarded

Status: corrected by fresh F-SANDBOX-17; awaiting fresh refutation.

The exact mocked container inspect replaced the repository bind source with
`C:\arbitrary\forged-repository` while retaining the expected read-only bind
at `/repo`. `_selected_inspect` discarded `HostConfig.Mounts[0].Source`, so
the host accepted the remaining hardening fields, started the container, and
could admit a structurally complete forged inner PASS from an unrelated host
tree.

The canonical inspect witness is 1,492 bytes with SHA-256
`a4a8cd02f444da1c5b038e9525f447938415a5144765af6b6ab0d7957bd77a1c`.

The correction resolves the trusted repository path exactly once for the host
platform, records that identity and its digest in the plan, supplies the same
spelling to `docker create`, retains the untrusted inspected `Source`, and
requires exact JSON string equality before container start. The inspected
value is deliberately not normalized: relative, traversal, alternate
separator, case-mutated, and other-source spellings cannot collapse into the
trusted identity. A missing or wrongly typed source and any additional mount
also fail closed. Mismatch details retain the untrusted source's type and
SHA-256, not its raw value; a successful effective-config receipt retains the
already declared intended source.

Direct and complete mocked host-flow regressions preserve the exact witness,
cover every declared mutation class, and prove no rejected source reaches
`docker start`. Native hosted Linux uses one resolved absolute POSIX path.
Docker Desktop may rewrite a client path to a VM-internal spelling; the
harness does not guess at or admit aliases, so such translation is an explicit
setup failure rather than sandbox PASS evidence.
