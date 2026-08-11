# F-SANDBOX-021 — active mount semantics were coupled to a Windows custody hash

Status: corrected by fresh F-SANDBOX-21; awaiting fresh refutation.

The F-SANDBOX-017 through F-SANDBOX-020 regression block mixed two different
obligations: custody of historical canonical witnesses produced in the
mandated Windows worktree, and active semantic validation against the
repository source resolved on the current host. In particular, the
F-SANDBOX-020 positive request-mount fragment was asserted universally as 171
bytes with SHA-256
`2f7ff46e5f4f59082d6b0445969bd56bbf2f79c2609b245a171e58da8b0a85e9`,
and its complete inspect object as 1,733 bytes with SHA-256
`d1e6e191beb0a144fbc45cb99215f365dc8a7d2769b49927fbc54fc188dff1a1`.
Those values include the explicit frozen source
`C:\Users\james\New folder\receiver-reliance-worktrees\portability`.

Replacing only that source with the native hosted-Linux checkout
`/home/runner/work/receiver-reliance/receiver-reliance` yields a valid
154-byte request mount with SHA-256
`cae1355c2e29e74679d28ed562a4986b650263774a3a8a0a36aeca18ff7e87f9`
and a valid 1,699-byte inspect object with SHA-256
`85fb5aff6d5eae5ca008110f7749554ff07518ae6644babdbbc1257d1cca56c2`.
The former test therefore failed on the very native hosted Linux lane it was
intended to validate, before testing the F-SANDBOX-020 consistency omission.

The correction makes the distinction explicit. Historical byte/hash custody
fixtures name the frozen Windows source directly and continue to preserve all
F-SANDBOX-017 through F-SANDBOX-020 witness hashes. Active positive and
negative tests contain no universal source-dependent length or digest: they
bind the create argument, request mount, effective mount, selected projection,
and full mocked host flow to the repository identity supplied by that host.
Simulated Windows drive, Windows UNC, native Linux, and native macOS roots
exercise exact platform rendering. Cross-platform full-flow neighbors prove
that each exact identity reaches `docker start`, while changing either active
mount source still fails closed before start. Foreign path dialects, relative
roots, unsupported hosts, and comma-bearing sources are rejected.

F-SANDBOX-020's security behavior is unchanged: native omission of the Moby
`Consistency` member is required and projected as abstract
`consistency="default"`; any explicit member remains an unsupported extra.
No source normalization or alias is admitted, and request/effective source
equality remains exact.
