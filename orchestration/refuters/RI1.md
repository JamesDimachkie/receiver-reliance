# RI1 — second-implementation refutation

## Verdict

**REJECT-with-findings.** Candidate `161e06b21a12a246fa7c876f2133a623946c68cb`
has a byte-observable, contract-adjudicated **CRITICAL** RFC 8785 member-ordering
defect. The first targeted differential input produced a different error code,
pointer, precedence, response seal, and stdout digest from the frozen composed
runner. Per the charter's first-high-confidence-divergence stop condition, the
20,000-input campaign was not continued.

Audit base: `6f3dcceb208e1159686782e5550040802be7af9a`. The candidate was cherry-picked
unchanged as local commit `5b1aa27`; `git diff --exit-code 161e06b... HEAD --
second-impl` was clean. Only this report is authored by RI1.

## Finding RI1-001 — CRITICAL — code-point sorting rejects valid RFC 8785 bytes

`second-impl/second_impl.py:71-79` delegates object ordering to
`json.dumps(..., sort_keys=True)`, which orders Python strings by Unicode code
point. `parse_json_bytes` then uses those bytes as its canonicality oracle at
line 218. RFC 8785 instead orders raw property names as unsigned UTF-16 code
units ([RFC 8785 section 3.2.3](https://datatracker.ietf.org/doc/html/rfc8785#section-3.2.3)).

The repository itself closes the adjudication:

- `baseline-run/control/B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json:256` requires
  exactly `RFC8785_JCS` input.
- `ACCEPTANCE.md:40` records RFC 8785 UTF-16 member ordering as a **CRITICAL**
  implementation defect fixed during accepted-reference review.
- The frozen composed runner orders with `key.encode("utf-16-be")` at
  `baseline-run/implementation-output-0.3/b1_capabilities.py:75-80`.
- The current independent property gate pins the astral/BMP edge at
  `grounded-0_4/test_properties.py:153-164` and passed 65 UTF-16 cases in this
  audit.

### Minimal reproduction and exact diff

Seed: `0x5EED8785`. Strategy: `utf16_member_order`. This object contains U+10000
and U+E000; U+10000 sorts first in UTF-16 but second by code point.

```text
input hex:
7b22f0908080223a302c22ee8080223a307d0a
input SHA-256:
898F487E1FFD5284DB606603F67AD297CDDB19D339CE5DDFD570B28D16D74014
```

Both API and CLI paths agreed within each implementation, both emitted empty
stderr, exit code `2`, one JCS+LF object, and a valid self-zero seal. They did
not agree with each other:

| Surface | Frozen composed runner | I1 candidate |
|---|---|---|
| selected error | `ERR_SCHEMA` | `ERR_JSON` |
| pointer | `/format_version` | empty |
| precedence | `80` | `50` |
| stdout SHA-256 | `309E457F8DE3B7970333ABBB017D54BC12507F93E6C833AA9F38130EBC0080CF` | `9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2` |

The reference accepts the input as canonical and reaches schema validation;
I1 rejects the same canonical bytes at its parse layer. This is not a harmless
seal-only difference.

### Counterevidence sought and adjudication

`access/SANITIZED_PRIMARY_BASELINE_IMPLEMENTER_PACKET_0_1.json:13255` contains
the gloss “RFC8785 JCS; keys sort by Unicode scalar value”. That wording is
counterevidence and is internally imprecise: RFC 8785 specifies UTF-16 code
units, not scalar/code-point order. It does not rescue the candidate because
the same authority names RFC 8785, the primary contract names RFC 8785, and
`ACCEPTANCE.md` explicitly records this exact ordering choice as a critical
accepted-reference correction. Under the parity law, the unadjudicated byte
divergence rejects I1.

## Finding RI1-002 — LOW — `827/827` is not an all-executed agreement denominator

I independently recounted the four frozen packs and reproduced
`python -B second-impl/test_cross.py`:

| Check family | Baseline | Supplemental | Total |
|---|---:|---:|---:|
| semantic entries | 112 | 12 | 124 |
| competence, materialized/executed | 370 | 46 | 416 |
| competence, descriptor-only | 0 | 7 | 7 |
| wrapper arms | 224 | 24 | 248 |
| wrapper negatives | 10 | 10 | 20 |
| wrapper metamorphic links | 4 | 8 | 12 |
| **aggregate** | **720** | **107** | **827** |

The arithmetic is correct and the command returned `827/827`. The seven
supplemental records are not self-contained executable cases: each supplies a
named multi-field `operation` and a list of `pointers`, but no singular target
pointer/replacement value and no materialized mutated request bytes. Their
case hashes and operations are:

| Case SHA-256 prefix | Operation |
|---|---|
| `A0AAB3E298DA` | `SATISFY_REQUIRED_SET_KEEP_ASKING_ACCOUNTED` |
| `53186D2261BF` | `SATISFY_REQUIRED_SET_KEEP_ASKING_UNACCOUNTED` |
| `3C051B1A76A3` | `REASK_ANSWERED_QUERY_IGNORING_INGESTED_ANSWER` |
| `4D482F64F42D` | `ADMIT_TOP_RANKED_INCOMPATIBLE_RECORD` |
| `AF93F8416FB1` | `SHIFT_INTENT_TUPLE_KEEP_STALE_SELECTION` |
| `25125CAB6E3B` | `ADD_INCOMPATIBLE_DISTRACTORS_COHERENTLY_EXCLUDED` |
| `D6C6F537B6B5` | `ABSORB_DISTRACTOR_INTO_SELECTION` |

Six descriptors carry a complete expected response, whose self seal, raw
digest, and behavior class I1 checks; the distractor-addition descriptor binds
its declared digest/class to the base entry. All seven have wrapper
metamorphic links. This is sufficient fixture-internal consistency evidence.
It is not an execution of I1 on the described mutation: `sealed_descriptor`
never calls the engine, and `wrapper_metamorphic` compares declared hashes and
relations rather than materializing a request. The frozen conformance harness
can execute them only because it supplies an external, hard-coded named-
operation materializer in `run_conformance_0_3.py`; those replacement values
are absent from the fixture records themselves.

I1 transparently labels these seven “descriptor-only” and says they were not
executed, which is counterevidence against deceptive reporting. The remaining
overclaim is the README's framing of `827/827` as an agreement count: it is an
aggregate of implementation comparisons and seven descriptor adjudications,
not 827 executed candidate inputs.

## Provenance, custody, and non-teaching audit

Evidence supporting I1's non-teaching claim:

- AST import census for runtime files found only Python standard-library
  modules plus local `second_impl`; no network, subprocess, environment,
  randomness, or clock import is present in the runtime.
- Runtime string-literal search found no fixture IDs, fixture labels,
  expected-response keys, `baseline-run/implementation-output-*`,
  `receiver_reliance`, `grounded-0_4`, proof paths, URLs, or generated expected
  tables.
- Runtime data loads are limited to the declared control/access authorities.
  Fixture and expected-response reads occur in `test_cross.py`, not in the
  imported evaluator or CLI.
- The original candidate commit has the required
  `Authored-By: sol-i1 (gpt-5.6-sol)` trailer and adds the evaluator,
  provenance, and tests in one commit.

No teaching/copying shortcut was found in candidate bytes. However, git proves
neither negative file-access history nor the asserted pre-first-light read set
and timing. Because implementation, first-light narrative, fixture test, and
provenance landed in the same commit, there is no commit boundary independently
attesting that sequence. `PROVENANCE.md` is therefore a disclosure consistent
with the source scan, not independently verifiable custody proof.

## Differential scope and stop record

A temporary uncommitted harness outside the repository used seed
`0x5EED8785`, an independent UTF-16 JCS serializer/seal checker, both in-process
raw-byte APIs, and both CLIs. Planned minimum on zero divergence: 20,000
P3-generated inputs spanning all strategies. Executed: **1** targeted input.
The first input produced RI1-001, so the charter's first-high-confidence-
divergence stop condition fired before the P3 expansion. There were no
consecutive no-information passes.

## Repository gate

The current full gate was green; this is counterevidence against collateral
reference/test breakage, not evidence that I1 satisfies adversarial parity:

- frozen 0.2 conformance: `800` checks, `0` failures;
- composed 0.3 conformance: 0.2 suite `800/800`, 0.3 suite `107/107`;
- grounded regression: `504/504`;
- authority lint: `0` findings over `199` required fields;
- P2 lint meta-test: `7/7`;
- P3 fuzz smoke: `31/31`, seed `0x000000000B10F042`, all 31 strategies;
- P4 properties: `2,296/2,296`, seed `0x5EED8785`;
- P5 audit adversarial: `6,497/6,497`;
- P6 portable proof harness: `7/7`;
- I1 fixture cross-test: `827/827`, subject to RI1-002.

## Residual uncertainty

- Git cannot prove I1's historical read/access claims.
- The access packet's “Unicode scalar value” gloss conflicts with RFC 8785's
  UTF-16 ordering. The accepted-reference history explicitly adjudicates this
  edge, but the gloss remains documentary ambiguity worth correcting only in a
  future, non-sealed revision.
- The 20,000-input differential matrix and the remaining requested adversarial
  families were intentionally not run after the terminal critical divergence;
  this report makes no claim about how many additional I1 defects exist.

Report commit: this report's commit; exact SHA is supplied in the handoff to
avoid a self-referential commit-hash field.
