# Clean-room portability oracle

This directory contains a stdlib-only oracle for the receiver-reliance
portability session. It was rebuilt without reading, importing, or executing
the rejected oracle lineage or the accepted implementation. The exact custody
record is in `PROVENANCE.md`.

For the authoritative current disposition of F-ORACLE-001 through
F-ORACLE-013 and the two clean refutations that followed their corrections,
see [`STATUS.md`](STATUS.md). Finding files preserve discovery-time evidence;
their phrases such as "credible defect" or "requires a fresh refuter" do not
describe the current oracle unless `STATUS.md` says so.

The oracle has two intentionally separate surfaces:

1. An iterative raw-record classifier independently parses strict UTF-8 JSON,
   preserves object pairs and numeric lexemes, orders object members by
   unsigned UTF-16 code units, emits integer-domain RFC 8785 bytes, applies the
   frozen error precedence, retains a valid request ID even when physical
   framing/canonicality fails, and constructs self-zeroed protocol errors.
2. An exact four-pack lookup verifies and serves 124 semantic and 248 wrapper
   request/response bindings (372 unique records). It verifies raw bindings,
   independent JCS+LF reconstruction, pack/entry/pair/case/response/transcript/
   attention-card self-zero seals, and wrapper normalized-output digests before
   admitting a record.

Run the closure and focused relations with:

```powershell
python -B portability/oracle/test_oracle.py
python -B portability/oracle/oracle.py validate-fixtures
```

The following expected-error smoke probe emits the classified
`ERR_EMPTY_INPUT` response and intentionally exits 2. That protocol exit is
the expected result, not a harness or test failure:

```powershell
python -B portability/oracle/oracle.py classify-hex 0a
```

The relation helpers cover physical-line equality, input-partition invariance,
request-sequence permutation invariance, concurrency-vs-isolated equality,
oversize-drain next-record invariance, and deterministic comparison of supplied
cross-process/cross-platform observations. The tests execute a two-process
replay locally. The platform comparator does not claim that platforms which
were not actually observed were executed; hosted receipts remain separate
evidence.

## Bounds and nonclaims

- JCS number emission is deliberately limited to this contract's integer-only
  profile. Raw JSON numbers are scanned and checked lexically, without passing
  their decimal text through the host's configurable integer-conversion cap.
  Invalid number lexemes are held stable while canonical spelling of the
  surrounding value is checked so error precedence remains observable.
- Full decision predicate evaluation is not reimplemented. Expected successful
  semantic/wrapper bytes are admitted only for the four frozen packs. A valid
  request outside those packs raises `OutsideFixture`.
- Physical records over 16,777,216 bytes are classified as `ERR_LIMIT` before
  UTF-8 decode or parser allocation; exactly-at-limit records continue through
  the ordinary classifier.
- Raw parsing, canonical serialization, and validation walking use explicit
  work stacks rather than Python recursion. Their allocation is bounded by the
  physical-record guard, so host recursion limits cannot change a contract
  result at or beyond the declared nesting limit.
- Schema routing is the bounded raw-ABI subset required by this session: root
  object, declared `format_version`, top-level `required` failures located at
  the root object, and present `request_id` validation located at that member.
  Other present-member and nested-schema validation is not reimplemented; this
  is not a claim of full JSON-Schema evaluation.
- This is bounded negative evidence, not an efficacy, novelty, security,
  fuzzing-completeness, external-standard, or universal-portability claim.
