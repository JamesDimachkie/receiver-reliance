# F-PORTABLE-001 — portable admission did not bind one bounded cross-platform snapshot

Status: fixed in hardening wave W4. Deep-scan findings
`csf_3e0dd9a17a1cd46ded2db43a`,
`csf_da6256526408ba305731b68f`,
`csf_bd3343438678a1b1f6cb9d53`,
`csf_ba0fc3d1b78ac7385c00a294`,
`csf_d1bf0c1b557800b80e3f402d`,
`csf_e9e52aeb75782ce488c4ac61`, and
`csf_e18bcccbf31f8a1bb9e43104`.

## Evidence

Manifest generation followed link-like ancestors, while verification and ZIP
creation reopened paths across separate passes. Generation and verification
admitted names that alias on supported filesystems. Manifest, inventory, and
payload bytes were fully allocated before their ceilings or declarations were
checked. Verification authenticated the inventory bytes without proving that
its path/role declarations exactly matched manifest rows, accepted
noncanonical manifest spellings, and allowed deep JSON to escape as
`RecursionError`.

## Repair

One portable path contract now rejects symlinks, junctions/reparse points,
Windows device names, trailing-dot/space components, invalid Windows
characters, names outside a conservative ASCII component profile, case-fold
aliases, duplicate filesystem identities, traversal, and non-NFC names. Manifest and
inventory JSON are stat-bounded before reads and depth-checked before decoding;
payloads are stat-checked against per-file and aggregate ceilings before read.
Manifest bytes must be the exact canonical serialization, and manifest
path/role declarations must equal the authenticated inventory declarations.

`verify_snapshot` returns the exact verified manifest, inventory, and payload
bytes. The ZIP builder consumes only that snapshot and includes both bootstrap
files; it never reopens source paths after verification. The remaining
filesystem race surface is the platform's directory-resolution semantics
during the verifier's component walk; resolved final paths and opened-handle
identity checks narrow that surface, but this is not a claim of kernel-level
`openat2` equivalence on every supported OS.
