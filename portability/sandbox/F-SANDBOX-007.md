# F-SANDBOX-007 — zero-byte stream digest is internally inconsistent

Status: corrected by fresh F-SANDBOX-7; awaiting fresh refutation.

An otherwise complete canonical synthetic PASS set
`commands[0].stdout_bytes=0` while retaining a nonempty digest spelling of
`0000000000000000000000000000000000000000000000000000000000000001`.
It then recomputed the deterministic projection, which intentionally excludes
stream evidence. Both direct inner-receipt validation and the exact host flow
accepted the inconsistent claim.

The exact canonical witness is 7,561 bytes with SHA-256
`4433ea1bb53c148d391f680322a3fe2ed597505c5d97bf7edae034dc6d6574fb`.

The correction requires every stdout or stderr stream claiming zero bytes to
carry SHA-256 of the empty byte string:
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Any mismatch is an `InnerReceiptError`, which the host classifies as
`INVALID_CONTAINER_RECEIPT` with exit 1. Regressions cover stdout and stderr
through direct and host validation, the exact minimized witness, and the
one-byte nonzero neighbors.

This is only a deterministic internal-consistency check. A successful command
does not include its stdout or stderr transcript in the PASS receipt, so
nonzero stream hashes remain structural, self-reported evidence and cannot be
independently recomputed by the host.
