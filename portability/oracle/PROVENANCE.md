# O-ORACLE-CLEAN-RESUME provenance and custody confirmation

Treatment-exposed lane. This author will not author any future blinded world,
gold, oracle, or renderer for the research program.

The previous `portability/oracle/{__init__.py,oracle.py,test_oracle.py,
README.md,PROVENANCE.md}` lineage was rejected for source-boundary
contamination. This author did not open, search, diff, import, or execute those
files. They were deleted wholesale with `apply_patch` and replaced from
scratch. The accepted implementation was not executed. No file named
`b1_capabilities.py`, `pcb_runner.py`, `rr_api.py`, `rr_batch.py`, or `fuzz.py`
was read. No grounded closure/authority file, conformance runner/output, or
excluded proof-workspace data was read.

## Session-control reads (not oracle-result authority)

| Source | SHA-256 |
|---|---|
| `<workspace>/AGENTS.md` (outside this repository) | `A7F955E227533FE5557133AD9B75C23C5C8AA76BD7FCC5E2037EBF47A5091934` |
| `planning/epistemic-handoff/MASTER_PROMPT_RR_PORTABILITY_20260810.md` | `154A9E5397D5D5B5422FD5D7053E7D1E6C6544C5D0152866598E6DC990F9C478` |

## Permitted specification and frozen-data reads

These are the only specification/frozen-data files read by this author:

| Source | Bytes | Raw SHA-256 |
|---|---:|---|
| `ERRATA.md` | 4,476 | `910498AD7CC3C960299F5B60EEA97D1367E9C9499C76298A52BBDCFCEE8B1B7F` |
| `HOST_OBLIGATIONS.md` | 4,620 | `F536254D3C6D09379D40EBB2CB744C6109489146BEEF20B539BA1B70FCD0F222` |
| `baseline-run/control/B1_CAPABILITY_MATRIX_0_1.json` | 37,157 | `266AB130F85206E0FA47978A1E57E5D16DF7EACD051084435C15B1840512D38E` |
| `baseline-run/control/B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json` | 321,451 | `DCFCB0714E1A7E677548057987F604D227F791F3FC3E0EA89BE5ED932447F48E` |
| `access/SANITIZED_PRIMARY_BASELINE_IMPLEMENTER_PACKET_0_1.json` | 513,384 | `73A4FF4DD8ABA41D0F68414CB754EFCDF9807FAE73354F1959420B16C5F359F3` |
| `baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json` | 1,360,792 | `F27B93B3BE8BCBF5FBF7FF7789494621D17B426E16B38E958BB932899B0961B9` |
| `baseline-run/fixtures/B1_WRAPPER_PARITY_FIXTURE_PACK_0_2.json` | 2,234,050 | `22B9A2E8C08A63CF1A29AC3CD57FB0D30108245BC538DA2E4A959A24089195C1` |
| `supplemental-0_3/control/B1_COMPOSED_CAPABILITY_MATRIX_0_3.json` | 25,976 | `B369777E51B2A64DC2C304C5949F38E13956353B496BABA8B6E488451F8C5B98` |
| `supplemental-0_3/control/B1_SUPPLEMENTAL_COMPARATOR_CONTRACT_0_3.json` | 159,277 | `6B2CAD02DDE7388D63D66E4863E5233CFBD1DC413575D9D260DB9799C7023A12` |
| `supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json` | 178,296 | `0A211174261C31924979A348B13EC43678896183ADB99D86002A51238C0AAE73` |
| `supplemental-0_3/fixtures/B1_SUPPLEMENTAL_WRAPPER_PARITY_FIXTURE_PACK_0_3.json` | 283,402 | `0F71812E52ED4C1008BB9544CFD36230BDC01966AF11FE16CFCF838ABB11BF72` |

The author also read the official RFC Editor presentation of RFC 8785 on
2026-08-10 (`https://www.rfc-editor.org/info/rfc8785/`), specifically the
input, primitive serialization, UTF-16 member ordering, and UTF-8 generation
rules in Sections 3.1 through 3.2.4. No third-party JCS implementation was read.

## Adjudicated finding reads

| Finding | SHA-256 |
|---|---|
| `findings/F-ORACLE-001.md` | `8EAACD3B1454FE67312004D2C3044D51E718A218F15B83B89B55EC2DEE73929E` |
| `findings/F-ORACLE-002.md` | `4409EE418F7F4453E3A0D5B5710A45766575A6717CA8E5BDA091FDA6A07C564F` |
| `findings/F-ORACLE-003.md` | `5FC166BB0CA7B7DA1ECCDB8246254A27EAB894862074A4233C9628B3CD07F611` |
| `findings/F-ORACLE-004.md` | `B11F00200B9E29150E5DED9E9B12AA7BC54C3683FD86E77617EC5BAF97B45D63` |
| `findings/F-ORACLE-005.md` | `BBE7D3D1254ADD0DE389153693CDFE815023C313F5CDCF6960E3D585D807A2D9` |
| `findings/F-ORACLE-006.md` | `1342FA308DDFA3809FC8A29A35441464B2BB30D80909EADD5E0E65B45B49DB82` |
| `findings/F-ORACLE-007.md` | `6F917AE140BFAF2BB4D60819BD7EFEDCC3E94A2CEAA25C346479091A77B56BEB` |
| `findings/F-ORACLE-008.md` | `4642A0216331EEF724C29A35646334CEC69E8D5DAB2984B2D00650E6A962232F` |
| `findings/F-ORACLE-009.md` | `023E2E03DB47798336D46083A4DDB2C2C20D9944A9E622FEE23849970F08A8FC` |

F-ORACLE-009 was supplied as already-adjudicated evidence in the fresh-author
brief. It was written into `findings/F-ORACLE-009.md` before being encoded as a
regression. The finding is evidence of a rejected oracle behavior, not an
accepted-implementation defect.

## Construction boundary

The implementation uses only Python's standard library. `json.loads` is used
only to read the four frozen pack containers and emitted response bytes; the
raw-record parser, UTF-16 ordering, canonical serializer, error classifier,
and self-zero recomputation are implemented in `oracle.py`. Expected successful
bytes come only from the four exact frozen pack bindings after all local seals
and hashes are independently recomputed.

## F-ORACLE-010 correction custody

F-ORACLE-10 is a fresh, treatment-exposed correction author. This author read
the session-control authorities above, the current admitted clean oracle,
tests, README, this provenance record, adjudicated findings F-ORACLE-001
through F-ORACLE-009, and the same permitted specification/frozen-data
allowlist recorded above. No repository-wide search was performed. The
accepted implementation, conformance/grounded/proof runners or outputs, and
the five forbidden implementation files were not read, imported, searched, or
executed. Oracle tests read only the four allowlisted frozen packs through
`FixtureOracle`.

The supplied refuter evidence was preserved as:

| Finding | SHA-256 |
|---|---|
| `findings/F-ORACLE-010.md` | `88E16C96772A3354EAC2BF571A43CC7039D114A599029BD171FBFC307EBA0344` |

Correction custody is limited to the pre-decode physical-record size guard and
its oracle-only regressions and relations. This author will not author any
future blinded world, gold, oracle, or renderer for the research program.

## F-ORACLE-011 correction custody

F-ORACLE-11 is a fresh, treatment-exposed correction author. This author read
the session-control authorities above, the current admitted clean oracle,
tests, README, this provenance record, adjudicated findings F-ORACLE-001
through F-ORACLE-010, and the same permitted specification/frozen-data
allowlist recorded above. Relevant schema and deterministic-runtime clauses
were inspected only within those allowlisted contract JSONs. No repository-wide
search was performed. The accepted implementation, conformance/grounded/proof
runners or outputs, and the five forbidden implementation files were not read,
imported, searched, or executed. Oracle tests read only the four allowlisted
frozen packs through `FixtureOracle`.

The supplied refuter evidence was preserved as:

| Finding | SHA-256 |
|---|---|
| `findings/F-ORACLE-011.md` | `49FC20228EF8D1ADB4B13C318D91599C5926F2ACDC96D862721DB42C22A82F18` |

Correction custody is limited to top-level required-member instance-pointer
routing and its oracle-only regressions, including declared-format missing
member combinations and the member-limit neighbor. This author will not author
any future blinded world, gold, oracle, or renderer for the research program.

## F-ORACLE-012 correction custody

F-ORACLE-12 is a fresh, treatment-exposed correction author. This author read
the session-control authorities above, the current admitted clean oracle,
tests, README, this provenance record, adjudicated findings F-ORACLE-001
through F-ORACLE-011, and only the relevant precedence and deterministic-limit
clauses within the permitted specification allowlist recorded above. No
repository-wide search was performed. The accepted implementation,
conformance/grounded/proof runners or outputs, and the five forbidden
implementation files were not read, imported, searched, or executed. Oracle
tests read only the four allowlisted frozen packs through `FixtureOracle`.

The supplied refuter evidence was preserved as:

| Finding | SHA-256 |
|---|---|
| `findings/F-ORACLE-012.md` | `3C614800EB43058A62259B8D1B159F95828572024CC92FB1F63A7EA9B42FC5F3` |

Correction custody is limited to recursion-independent raw parsing, canonical
serialization, and validation walking, plus depth, malformed-neighbor, and
precedence regressions. The 16,777,216-byte pre-decode guard remains the hard
input/allocation boundary. This author will not author any future blinded
world, gold, oracle, or renderer for the research program.

## F-ORACLE-013 correction custody

F-ORACLE-13 is a fresh, treatment-exposed correction author. This author read
the session-control authorities above, the current admitted clean oracle,
tests, README, this provenance record, and adjudicated findings F-ORACLE-001
through F-ORACLE-012. No repository-wide search was performed. The accepted
implementation, conformance/grounded/proof runners or outputs, and the five
forbidden implementation files were not read, imported, searched, or
executed. Oracle tests read only the four allowlisted frozen packs through
`FixtureOracle`.

The supplied refuter evidence was preserved as:

| Finding | SHA-256 |
|---|---|
| `findings/F-ORACLE-013.md` | `543B99B7396C4F87BE8D4A728405D3BA7524E9406416D2C276224D8A003B9D27` |

Correction custody is limited to host-cap-independent JSON-number scanning,
lexical safe-integer classification, bounded integer JCS emission, and the
associated framing, canonicality, pointer, physical-record, and ambient-cap
regressions. The 16,777,216-byte pre-decode guard remains the hard input and
allocation boundary. This author will not author any future blinded world,
gold, oracle, or renderer for the research program.
