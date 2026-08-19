# Portable bundle threat model

This document identifies engineering boundaries and residual risk. It is not a
security certification or a claim that the artifact is safe for every use.

## Assets and trust anchors

- deterministic decision and preflight behavior;
- exact contract, packet, projection, and runtime bytes;
- request/response correlation across a long-lived child process;
- host nonce, state, applicability, and effect truth.

The authenticated repository commit or release is the distribution trust
anchor. `MANIFEST.json` detects drift after that authentication; because it is
not signed, it cannot authenticate an otherwise untrusted directory by itself.
The selected CPython runtime and operating system are trusted dependencies.

## Boundaries

1. **Untrusted wire bytes → total parser.** Invalid UTF-8, excessive depth,
   duplicate keys, huge numbers, noncanonical forms, and over-limit input must
   become deterministic protocol results without interpreter exceptions.
2. **Repository files → authority resolver.** Content-addressed authorities are
   length- and digest-checked before JSON parsing or reference resolution.
3. **Host observations → portable preflight.** The host is authoritative for
   native truth. The preflight detects closed structural contradictions and
   distinguishes them from absent semantics; it cannot prove a lying observer.
4. **Supervisor → child pipes.** Output is untrusted until a complete envelope
   matches the active transport version, sequence, and request digest.
5. **Artifact → host effects.** The engine decides; the host owns effect policy,
   idempotency, reconciliation, logging, and retry.

The bundle's own bootstrap is stated rather than assumed. `cli.py` executes
`portability/strict_ingest.py`, and through it the frozen core that supplies the
ingest ceilings, before the manifest index exists — the index is now admitted
under that same law, so the law cannot be authenticated by it first. Both files
are declared bundle rows, and both are byte-authenticated against those rows
immediately after the index is built, before any other repository module loads
and before any command runs. A substituted law therefore stops the process at
import instead of deciding what the manifest says.

## Threats and controls

| Threat | Control | Residual boundary |
|---|---|---|
| file substitution or partial copy | complete bundle manifest; startup length/SHA checks; read-only deployment | a malicious party able to replace both authenticated source and verifier is outside this integrity check |
| parser stack or host numeric-limit escape | iterative bounded scanner; lexical number classification; API/CLI parity regressions | work up to declared byte ceilings still consumes bounded CPU/memory |
| stale or unsolicited sidecar output | request-bound sequence/digest envelope; poison-on-mismatch; no replay | a fully compromised child that has read the complete active request is not made trustworthy by correlation |
| stale, contradictory, or absent host evidence | three-way preflight result; build-time snapshot checks in host-specific connectors | truth not observable by the host cannot be invented by the artifact |
| timeout/EOF ambiguity after possible processing | terminate and require host reconciliation; never automatic replay | exactly-once external effects require an adopter-owned idempotency/effect ledger |
| path traversal or symlink substitution | normalized relative path contract, containment check, symlink rejection | filesystem/OS compromise remains outside the process boundary |
| secret or data exfiltration | no network listener, shell, credential store, or telemetry exporter; stdout reserved for protocol | adopters must avoid logging sensitive raw inputs in their own supervisor |
| supply-chain/runtime drift | supported-runtime matrix and exact byte manifest | matrix evidence covers named rows and versions, not all interpreters or future patches |

## Abuse cases retained as regressions

The regression set includes recursive JSON that previously escaped the CLI,
integers that cross CPython's string-conversion guard, duplicate and surrogate
edges, content-addressed authority mutation, stale and copied host evidence,
mutable runner substitution, one-byte-read response poisoning, partial writes,
duplicate/stale transport output, timeout, EOF, and child death.
