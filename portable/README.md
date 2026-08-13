# Portable receiver-reliance bundle

Candidate version: `0.1.0-rc.1`

This directory is the transfer boundary for the additive integration surfaces.
It does not replace the sealed 0.2/0.3 artifacts or widen their claims. It
answers a narrower operational question: are the exact runtime and authority
bytes being executed the bytes that were reviewed, and do those same bytes
pass on every supported host/runtime row?

The boundary has five parts:

1. `inventory.json` declares every shipped runtime, authority, and gate input.
   It is derived from evidence, not hand-picked: the union of the Python-audit
   traced execution inputs of the two admitted WP5 receipts, the WP4 author
   receipt's self-declared candidate closure, and the portable/adapters gate
   tooling itself. The manifest proves the declared bytes match; completeness
   of the declaration rests on that recorded derivation.
2. `build_manifest.py` deterministically derives byte lengths and SHA-256 pins
   into `MANIFEST.json`.
3. `verify_bundle.py` fails closed on manifest drift, unsafe paths, symlinks,
   missing or extra declarations, or byte mismatch.
4. `gate.py` verifies the manifest and runs the portable preflight, independent
   implementation, and correlated sidecar checks with the current interpreter.
5. `cli.py` provides the stable `verify`, `doctor`, `preflight`, `decide`, and
   `sidecar` command surface.

From any checkout root:

```text
python -B portable/build_manifest.py --check
python -B portable/verify_bundle.py
python -B portable/build_bundle.py --check-deterministic
python -B portable/cli.py doctor
python -B portable/gate.py
```

No command depends on the checkout's absolute path, a shell, a platform process
census, or a writable repository. Temporary test state uses the host's standard
temporary-directory API. Normative output is UTF-8 and paths in the manifest are
NFC-normalized repository-relative POSIX paths.

## Support claim boundary

Local success is not cross-system evidence. A bundle is eligible for a bounded
support statement only after the *same committed manifest and file hashes* pass
the existing hosted normative matrix on CPython 3.12, 3.13, and 3.14 on Linux,
macOS, and Windows. A missing row is missing evidence, not a pass. Architecture
and runner availability remain recorded separately by the matrix.

The manifest self-seal detects accidental or adversarial drift but is not a
signature or external trust root. A recipient authenticates the repository
commit or release by its normal distribution channel, then uses this verifier
to prove that the unpacked bytes still match that authenticated tree.

## Nonclaims

This is not universal portability, a security certification, efficacy evidence,
or independent external confirmation. Host-specific truth still belongs to the
host. The portable preflight validates evidence shape and contradictions; it
does not invent observations that an integration did not supply.
