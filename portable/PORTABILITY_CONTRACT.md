# Portability contract

The portable bundle uses observable contracts rather than host coincidences.

## Bytes and paths

- All protocol input and output is bytes with explicit UTF-8 decoding rules.
- JSON wire payloads use LF framing only where the owning protocol says so.
- Manifest paths are unique, NFC-normalized, repository-relative POSIX paths.
- Drive-qualified, absolute, empty, dot, dot-dot, backslash, and symlink paths
  are rejected before a file is read.
- Repository location and username never carry authority.

## Runtime semantics

- Supported normative runtimes are CPython 3.12, 3.13, and 3.14.
- Protocol decisions may not depend on recursion limits, integer-string limits,
  locale, hash randomization, filesystem enumeration order, or wall-clock time.
- Unbounded wire numbers are classified lexically. Host integer or floating
  conversion is permitted only after a contract bound proves it safe.
- Content-addressed authorities are byte-length- and SHA-256-verified before
  parsing or resolution.

## Host truth

- A portable preflight can validate supplied evidence, reject contradictions,
  or report that required native semantics are unavailable.
- `REJECTED_INVALID` is a detected defect. `INSUFFICIENT_EVIDENCE` is an
  abstention. Neither is `READY`, and neither may be counted as a pass.
- No general adapter may claim to derive state, applicability, acknowledgement,
  or effect truth that its host connector did not observe.

## Long-lived transport

- Pipe timing, queue emptiness, line count, and process liveness do not identify
  a response.
- Every admitted response binds a versioned transport sequence and the SHA-256
  of the complete request bytes.
- The host admits nothing until its complete request frame has been written and
  flushed and the returned envelope matches the active sequence and digest.
- Duplicate, stale, reordered, malformed, over-limit, premature, or unbound
  output poisons the session; it is never replayed as a later response.

## Evidence

- The checked-in manifest binds the exact portable bytes.
- The offline gate runs without network access or repository writes.
- The hosted matrix must execute that gate on the same commit across the
  supported OS/runtime rows. Regenerated or locally substituted bytes do not
  satisfy another row.
- Optional platform telemetry may enrich a receipt but cannot become a
  portability precondition.
