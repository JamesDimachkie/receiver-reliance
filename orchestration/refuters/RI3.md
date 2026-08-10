# RI3 — twice-corrected second-implementation refutation

## Verdict

**REJECT-with-findings.** Original candidate commits
`161e06b21a12a246fa7c876f2133a623946c68cb`,
`9f7e016b7410a33a24d72d2b137df8343dff29db`, and
`934edd4d070fe6f4bffbc32f5effe3cf4f786699` close both prior minimized
counterexamples, but the twice-corrected evaluator still violates the frozen
raw error-selection law. A duplicate member detectable in a non-LF-terminated,
incomplete object must select `ERR_DUPLICATE_KEY` at precedence 40. The
candidate short-circuits on framing and instead seals `ERR_JSON` at precedence
50. The error, receipt, stdout bytes, and stdout digest therefore diverge on
both API and CLI surfaces from both frozen generations.

This is a contract-adjudicated **CRITICAL** raw-ABI defect. The authorized
stop-on-real-divergence condition fired after minimization, so the planned
20,000-input generated expansion was not run.

The isolated worktree was created from exact integration commit
`99997edd12b640228f2a0a8be074ad84483e5dfe` on `sol/w-ri3`. The three original
candidate commits were cherry-picked unchanged, in the requested order, as
local commits `9c96ebfe2cd5530cd4b4c7d56d5dbdebef645d87`,
`7ca0b41706d75ec3de56ba5152d516d922b678d3`, and
`fbb5d215e90b107baa01f45e8f7e479075b7abd7`. Before this report,
`git diff --exit-code 934edd4d070fe6f4bffbc32f5effe3cf4f786699 HEAD --
second-impl` returned 0; both trees resolve to
`630b8364ab71e79ed80080442f850c0637ec2f12`.

## Finding RI3-001 — CRITICAL — framing short-circuit defeats duplicate-key precedence

The minimized input is eight ASCII bytes. It contains a complete first empty
member name and a second complete duplicate member name, then ends before the
colon/value/object terminator and without LF:

```text
input repr:   b'{"":0,""'
input hex:    7b22223a302c2222
input length: 8
input SHA-256:
10779FCB480886B954ACEAE3C495771971BAA338F1A8FE55A48EB68965B4D6FD
```

Both APIs and both CLIs returned exit 2 with exactly empty stderr. Frozen 0.2
and 0.3 agreed byte-for-byte with one another, as did the candidate API and
CLI with each other; the two implementation families did not agree:

| Surface | Selected error | Pointer | Precedence | stdout bytes | stdout SHA-256 |
|---|---|---|---:|---:|---|
| frozen 0.2 API + CLI | `ERR_DUPLICATE_KEY` | empty | 40 | 342 | `6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01` |
| frozen 0.3 API + CLI | `ERR_DUPLICATE_KEY` | empty | 40 | 342 | `6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01` |
| candidate API + CLI | `ERR_JSON` | empty | 50 | 338 | `9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2` |

The exact frozen stdout was:

```text
{"errors":[{"code":"ERR_DUPLICATE_KEY","message":"Duplicate JSON object key.","pointer":"","precedence":40}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"A7E43CA772D54C98193C02100AC1F23E75B312DCAF3F3857E737A805DBF92D29","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

The exact candidate stdout was:

```text
{"errors":[{"code":"ERR_JSON","message":"Invalid JSON or trailing bytes.","pointer":"","precedence":50}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"121508D748E28E6D0A7CF3B2903AA979ADFB45E8D6A58D2929236C32AAC3C99C","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

### Contract adjudication and root cause

This is not an oracle preference:

- `baseline-run/control/B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json:490-494`
  requires one error selected by precedence and then RFC 6901 pointer UTF-8
  order; duplicate key precedes JSON/trailing-byte failure.
- `access/SANITIZED_PRIMARY_BASELINE_IMPLEMENTER_PACKET_0_1.json:13248-13252`
  repeats the ordered chain as empty, UTF-8, BOM, duplicate key,
  JSON/trailing bytes, NFC, number, schema, limit, internal.
- Both frozen conformance suites explicitly pin `dup-beats-noLF` to
  `ERR_DUPLICATE_KEY` with empty pointer
  (`run_conformance_0_2.py:387-395` and
  `run_conformance_0_3.py:537-545`). `ACCEPTANCE.md:41` records the accepted
  duplicate-key plus trailing-byte precedence correction.

The candidate checks LF framing at `second-impl/second_impl.py:193-194` and
raises `ERR_JSON` before constructing its duplicate-preserving decoder at
lines 198-206. Consequently `_convert_pairs` is unreachable on any no-LF
input. The frozen parser records framing as one pooled fact, scans duplicate
members at `pcb_runner.py:248-255`, and then selects precedence jointly.

A neighboring well-framed probe, `b'{"":0,"":0}\n'`, found a second
byte-level incompatibility: both frozen generations emit the empty duplicate
pointer, while the candidate emits `/`. Its stdout digests are respectively
`6D204C...29C01` and `CEF0955E...A02C9`. That reinforces rejection under the
byte-parity bar, but RI3-001 does not depend on resolving the less-explicit
question of duplicate-location reporting: the eight-byte precedence mismatch
alone is fully adjudicated.

### Counterevidence sought

- `test_raw_properties.py` passed all 12,004 candidate-local cases, but its
  2,000 precedence cases rotate through one fixed error family at a time. It
  never combines a detectable duplicate with missing LF or incomplete JSON.
- `test_surrogate_properties.py` passed all 12,292 cases. Its 2,048
  interactions combine a surrogate with six other families, but the duplicate
  arm is properly LF-terminated and therefore cannot detect this short-circuit.
- The fixture cross-test passed its mixed `827/827` aggregate, but its sealed
  fixture requests do not exercise this raw error-law input against the
  candidate.
- The full frozen/grounded gate passed. That is strong counterevidence against
  frozen-reference drift and collateral repository damage; most of that gate
  does not run `second-impl`.
- The exact RI1 and RI2 inputs now agree on all six API/CLI surfaces, documented
  below. Those corrections are real but do not cover combined raw precedence.

## Prior finding replay — both corrections close their named repros

The exact RI1 ordering pair and RI2 escaped-surrogate scalar/key were replayed
through frozen 0.2 API/CLI, frozen 0.3 API/CLI, and candidate API/CLI. For every
input, all six tuples `(exit, stdout bytes, stderr bytes)` were identical;
every exit was 2 and every stderr was exactly `b''`.

| Input | Input SHA-256 | Exact common error | stdout bytes | stdout SHA-256 |
|---|---|---|---:|---|
| astral/BMP canonical `7b22f0908080223a302c22ee8080223a307d0a` | `898F487E1FFD5284DB606603F67AD297CDDB19D339CE5DDFD570B28D16D74014` | `ERR_SCHEMA`, `/format_version`, 80 | 350 | `309E457F8DE3B7970333ABBB017D54BC12507F93E6C833AA9F38130EBC0080CF` |
| BMP/astral noncanonical `7b22ee8080223a302c22f0908080223a307d0a` | `74E3BA01F245DF1466E43A5DE7DFDAF97588B58EC84BC649A1FE60CF91AFC7D0` | `ERR_JSON`, empty, 50 | 338 | `9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2` |
| escaped lone-surrogate scalar `225c7564383030220a` | `B16AF5D32E117E1E4A4132716A6DFB0621BB990D1BFCCE97A9DF73774D0984F3` | `ERR_JSON`, empty, 50 | 338 | `9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2` |
| escaped lone-surrogate key `7b225c7564383030223a307d0a` | `8BA9AF9592D9FED7D0E9277137B1F224B9BB222AA3E8252C333CA28046140741` | `ERR_JSON`, empty, 50 | 338 | `9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2` |

The exact 350-byte common schema response was:

```text
{"errors":[{"code":"ERR_SCHEMA","message":"Request does not validate.","pointer":"/format_version","precedence":80}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"751D09EF378C383F1521A6818019E017A7A3667E636DAA06C2A37CCBCAC3E890","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

The exact 338-byte common JSON response was:

```text
{"errors":[{"code":"ERR_JSON","message":"Invalid JSON or trailing bytes.","pointer":"","precedence":50}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"121508D748E28E6D0A7CF3B2903AA979ADFB45E8D6A58D2929236C32AAC3C99C","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

## Differential campaign and terminal stop

The deterministic expansion plan bound at least 20,000 generated/raw inputs
against both frozen generations and the candidate, with explicit strata for
all raw-precedence combinations, duplicate keys and escaped-pointer locations,
paired and unpaired surrogate escapes, valid and invalid UTF-8 edges, NFC,
safe-number boundaries and invalid number lexemes, schema and binding pools,
both wrapper configurations, and generated valid semantic requests across all
30 operations.

Before expansion, the targeted raw-precedence probe produced a frozen/candidate
divergence. Eleven distinct inputs were then used only to confirm, adjudicate,
and minimize the family from a well-framed named key to the eight-byte input
above. The terminal condition therefore fired with **11 targeted inputs and 0
of the planned 20,000 generated expansion inputs executed**. This is the
authorized real-divergence exception, not a no-defect campaign. No claim is
made about the untouched matrix; additional defects may remain.

## Candidate suites

All candidate-local suites ran unmodified under CPython 3.12.10
(`C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe`):

```powershell
python -B second-impl/test_cross.py
python -B second-impl/test_raw_properties.py
python -B second-impl/test_surrogate_properties.py
```

Results:

- cross-test: `827/827`;
- raw ordering/precedence: `12,004/12,004`, seed `0xB1C0DE30`;
- escaped-surrogate suite: `12,292/12,292`, seed `0xB1C0DE33`.

The exact API replay loaded each frozen `pcb_runner.py` in isolation, called
`_execute(raw)`, and serialized `b1.jcs_bytes(response) + b"\n"`; it called
`second_impl.execute(raw, repo_root)` for the candidate. Exact CLI commands
were:

```powershell
python -B baseline-run/implementation-output-0.2/pcb_runner.py execute
python -B baseline-run/implementation-output-0.3/pcb_runner.py execute
python -B second-impl/cli.py
```

Each command received the named bytes on stdin; stdout, stderr, and process
exit were captured as raw bytes/integers without text normalization.

## Full expanded repository gate

The full gate ran unmodified and passed:

```powershell
Set-Location baseline-run
python -B implementation-output-0.2/run_conformance_0_2.py
python -B implementation-output-0.3/run_conformance_0_3.py --suite all
Set-Location ..
python -B grounded-0_4/test_grounded_0_4.py
python -B grounded-0_4/lint_contract.py --gate
python -B grounded-0_4/test_lint_gate.py
python -B grounded-0_4/test_properties.py
python -B grounded-0_4/test_audit_adversarial.py
python -B proof/test_proof_harness.py
python -B fuzz/fuzz.py --ci-smoke
```

Results:

- frozen 0.2: `800` checks, `0` failures;
- composed 0.3: `800/800` baseline and `107/107` supplemental;
- grounded regression: `504/504`;
- authority lint: `0` findings over `199` required fields;
- lint meta-test: `7/7`;
- properties: `2,296/2,296`, seed `0x5EED8785`;
- audit adversarial: `6,497/6,497`;
- proof harness: `7/7`;
- fuzz smoke: `31/31`, seed `0x000000000B10F042`, all 31 strategies,
  `budget_exhausted=false`.

The contemporaneous campaign was the named single Sol four-worker stream.
Resource timing is labeled only and did not change timeouts, budgets, cases,
or assertions: frozen 0.2 19,573 ms; composed 0.3 25,750 ms; grounded 1,188
ms; lint 130 ms; lint meta 1,850 ms; properties 180 ms; audit adversarial 462
ms; proof 727 ms; fuzz smoke 6,011 ms.

## Cross-test denominator audit

The `827` arithmetic independently recounts as:

| Family | Baseline | Supplemental | Total |
|---|---:|---:|---:|
| semantic byte comparisons | 112 | 12 | 124 |
| competence, materialized/executed | 370 | 46 | 416 |
| competence, descriptor-only | 0 | 7 | 7 |
| wrapper-arm byte comparisons | 224 | 24 | 248 |
| wrapper negative checks | 10 | 10 | 20 |
| wrapper metamorphic checks | 4 | 8 | 12 |
| **aggregate** | **720** | **107** | **827** |

Only `124 + 416 + 248 = 788` rows are direct candidate-output byte
comparisons. The 20 negative and 12 metamorphic rows are rejection/relation
checks. Most importantly, the following seven supplemental competence records
remain descriptor-only and were not executed as candidate inputs:

`A0AAB3E298DA...`, `53186D2261BF...`, `3C051B1A76A3...`,
`4D482F64F42D...`, `AF93F8416FB1...`, `25125CAB6E3B...`, and
`D6C6F537B6B5...`.

They validate supplied seals, raw digests, behavior classes, base bindings,
or declared wrapper relations. They cannot be claimed as implementation
agreement, and this report does not describe `827` as executed candidate
inputs.

## Provenance, custody, and teaching-shortcut audit

- All three original candidate commits carry the required
  `Authored-By: sol-i1 (gpt-5.6-sol)` trailer. RI3 made no candidate edit.
- An AST import census of `second_impl.py` found only `base64`, `binascii`,
  `dataclasses`, `hashlib`, `json`, `pathlib`, `re`, `typing`,
  `unicodedata`, and `__future__`; `cli.py` adds only `sys` and local
  `second_impl`. Runtime source has no network, subprocess, clock, randomness,
  or ambient-environment dependency.
- Runtime file reads are confined to `Contracts._load`. The runtime loads the
  primary and supplemental contracts plus the projection and sanitized packet
  declared in `PROVENANCE.md`. Fixture reads occur only in `test_cross.py`.
- A runtime literal search found no frozen implementation path,
  `receiver_reliance`, `grounded-0_4`, or proof path. No fixture ID, expected
  response table, or source-level teaching shortcut was found in runtime
  files.
- The disclosure names six pre-first-light authorities, four post-first-light
  fixture packs, RI1's raw counterexample, and RI2's report commit. The source
  and commit sequence are consistent with that narrative. Git cannot prove
  historical file access or the asserted first-light timing; the initial
  evaluator and its first-light narrative share one commit. Provenance remains
  a disclosure, not independently verifiable custody proof.

## Residual uncertainty

- The terminal finding intentionally prevented the 20,000-input expansion, so
  raw combination, wrapper, schema, and valid-semantic strata beyond the
  targeted/minimized family remain untested in RI3.
- Candidate-local suites demonstrate substantial internal coverage but omit
  the exact combined-precedence path that rejects the candidate.
- Historical custody cannot be proven from repository state.
- The well-framed duplicate-pointer discrepancy remains an additional frozen
  byte-parity failure even if future contract prose chooses to clarify where a
  duplicate parse error should point.

Report commit: this report's commit; the exact SHA is supplied in the handoff
to avoid a self-referential field.
