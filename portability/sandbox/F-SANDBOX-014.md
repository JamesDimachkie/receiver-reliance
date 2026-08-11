# F-SANDBOX-014 — effective environment was recorded but not enforced

Status: corrected by fresh F-SANDBOX-14; awaiting fresh refutation.

The exact mocked container inspect replaced `Config.Env` with
`["SECRET_TOKEN=forged"]`. `_selected_inspect` retained only the selected name,
and `_assert_inspect` did not bind that field. The host then started the
container and accepted a structurally complete forged inner PASS without
reconciling its process-observed environment to inspected configuration.

The canonical container-inspect witness is 1,147 bytes with SHA-256
`2f832130d910bd8341577fde2f77619056e3dc282209d3004f17edb4d5bbb3a4`.
Its pre-correction selected projection is 1,224 bytes with SHA-256
`dda5a3271fe0b8a30b0514357e157615d2e5da54bae54f5c53181a2dc453cd7e`.
The admitted forged inner receipt has SHA-256
`eb926d64f89077a1b73000b1c144c5a73a64ccce531273152967ddd20acc4f55`.

The correction binds the manifest-pinned base environment plus every
Dockerfile/create value as one exact deterministic allowlist. `Config.Env`
must be an array of unique `NAME=value` strings with valid names, the exact
allowlisted name set, and exact allowlisted values. Missing, extra, malformed,
duplicated, mistyped, secret-like, and value-mutated entries stop the run
before container start. Mismatch details retain names and mismatch classes but
never the untrusted values.

`HOSTNAME=rr-sandbox` is explicitly supplied so Docker's otherwise synthesized
runtime variable is present in `Config.Env`. After the inner receipt passes its
own strict schema, the host requires its sorted `boundary.environment_names`
to equal the inspected effective names exactly. Its secret-name classification
must be consistent and empty. Missing, extra, secret-like, duplicated, or
mistyped inner claims produce `INVALID_CONTAINER_RECEIPT`; no PASS is retained.

Direct and full mocked-flow regressions reproduce all three exact hashes,
exercise every declared environment shape/content class, prove rejection
occurs at the intended boundary, and retain all F-SANDBOX-003 through
F-SANDBOX-013 replays.
