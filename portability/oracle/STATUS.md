# Clean-room oracle status

This file is the authoritative current-disposition index for the clean-room
oracle. [`PROVENANCE.md`](PROVENANCE.md) records source and custody boundaries;
the files under [`findings/`](findings/) preserve discovery-time witnesses and
rejected behavior. A finding's discovery-time label is historical evidence,
not a statement that the corrected behavior remains defective.

## Current disposition

F-ORACLE-001 through F-ORACLE-013 are corrected in the current oracle. In
particular, the discovery-time "credible defect" wording in F-ORACLE-006,
F-ORACLE-007, and F-ORACLE-008 is not a current defect classification. The
future-work language in F-ORACLE-009 and F-ORACLE-012 is also historical: the
required fresh refutations were subsequently completed.

| Finding | Rejected behavior preserved by the witness | Current disposition |
|---|---|---|
| [F-ORACLE-001](findings/F-ORACLE-001.md) | Duplicate precedence and pointer lost before framing adjudication | Corrected; duplicate evidence is pooled and uses the contract's empty pointer. |
| [F-ORACLE-002](findings/F-ORACLE-002.md) | LF-only record classified as invalid JSON | Corrected; LF-only and zero-byte records classify as `ERR_EMPTY_INPUT`. |
| [F-ORACLE-003](findings/F-ORACLE-003.md) | Valid request ID erased on missing-LF framing error | Corrected; a valid parsed request ID survives framing adjudication. |
| [F-ORACLE-004](findings/F-ORACLE-004.md) | Repeated escaped lone-surrogate keys lost duplicate precedence | Corrected; invalid decoded key identity remains available for duplicate pooling. |
| [F-ORACLE-005](findings/F-ORACLE-005.md) | Number error selected before an earlier canonical-byte error | Corrected; independent canonical-byte adjudication precedes the numeric-profile error. |
| [F-ORACLE-006](findings/F-ORACLE-006.md) | Root scalar/array schema closure was unroutable | Corrected within the declared raw-ABI schema subset; non-object roots select root `ERR_SCHEMA`. |
| [F-ORACLE-007](findings/F-ORACLE-007.md) | Noncanonical escape lost to NFC error | Corrected; canonical spelling/order is adjudicated before NFC. |
| [F-ORACLE-008](findings/F-ORACLE-008.md) | Canonical object without declared dispatch escaped schema routing | Corrected within the declared subset; absent or undeclared `format_version` selects `/format_version`. |
| [F-ORACLE-009](findings/F-ORACLE-009.md) | Legal surrounding whitespace erased the parsed request ID | Corrected in the clean-room replacement; the later clean refutations satisfy the finding's former acceptance requirement. |
| [F-ORACLE-010](findings/F-ORACLE-010.md) | Oversize input reached BOM/decode handling before the size guard | Corrected; the 16,777,216-byte physical-record maximum is enforced before decode or parser allocation. |
| [F-ORACLE-011](findings/F-ORACLE-011.md) | Missing required member was assigned an invented child pointer | Corrected within the declared subset; top-level `required` failures use the containing root pointer. |
| [F-ORACLE-012](findings/F-ORACLE-012.md) | Python recursion depth changed deep-record classification | Corrected with explicit parse, serialization, and validation stacks; the later clean refutations satisfy the finding's former acceptance requirement. |
| [F-ORACLE-013](findings/F-ORACLE-013.md) | CPython's decimal-conversion cap escaped classification | Corrected with lexical number scanning and bounded integer emission. |

## Post-correction evidence

The current oracle implementation, tests, and custody record are bound by
these SHA-256 values:

| Artifact | SHA-256 |
|---|---|
| `oracle.py` | `2148F0C9C4ED38692B9C6658EC48CDD9628688E6C1708345C89A44AB91A05F17` |
| `test_oracle.py` | `27DEBE76E80FAE81FBA9B6C26FF2451F688027C0DC15D4FEEAC8B8FAE71F9339` |
| `PROVENANCE.md` | `74F4716D5FBE12DE875CD76D5FA7A42DA31C6F353A40083DC9DCB55CDE429999` |

Focused oracle tests pass 35/35. Four-pack validation admits 124 semantic and
248 wrapper bindings, 372 unique records, with binding SHA-256
`78FC43470C9AD4C41932CD38926F8430A004D02FE18E065D3DD6BE59A5A4B80B`.

Two consecutive post-correction refutations added no new oracle evidence:

- R-G compared all 57 frozen cases exactly against both accepted ABIs, then
  exercised 24 hostile deep/number/size neighbors. Its frozen-comparison
  manifest SHA-256 is
  `0DF6F8315E2DEAF7EC25E95CC5FDB5534A9DFE140232A35A8384FD4C2B8B0FCC`;
  its 24-case adjacent manifest SHA-256 is
  `6688E9C5FFF08302E89419BF538F9D0B61A7C3877A4B1C9EE8ADEC3AA821786A`.
- Distinct seeded refutation R-H compared 122 cases exactly against both
  accepted ABIs. Seed `0x52524F48434C454E`; manifest SHA-256
  `D835093E1B9EA0CC529BF050A90FBAD93D534F7D9769EA1030F0D8E2845C8D78`.

These are oracle-local negative results. They do not merge frozen fixture
coverage, bounded raw classification, or cross-platform execution into one
case count.

## Bounds, exposure, and nonclaims

- Successful semantic and wrapper responses are fixture-closed to the four
  frozen packs. An otherwise valid request outside those packs raises
  `OutsideFixture`; arbitrary novel decision semantics are not implemented.
- JCS number emission is integer-only. Raw number classification is lexical
  and host-cap-independent, but no general floating-point RFC 8785 claim is
  made.
- The raw classifier is bounded by the 16,777,216-byte physical-record guard
  and implements only the documented raw-ABI schema-routing subset. It is not
  a full JSON-Schema evaluator.
- This is a treatment-exposed lane. Its authors and custodians will not author
  the research program's future blinded worlds, oracle, gold, or renderer.

No efficacy, novelty, security, fuzzing-completeness, external-standard,
or universal-portability claim. The proof tier stays `internal held-out`.
The only defensible success statement: independent cross-platform,
cross-architecture, cross-runtime, bounded-state, and transport-scheduling
validation found no divergence within the stated environments and bounds —
with everything outside the model reported as outside the model.
