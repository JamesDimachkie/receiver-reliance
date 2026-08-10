# RI4 — third-corrected second-implementation refutation

## Verdict

**REJECT-with-findings.** Original candidate commits
`161e06b21a12a246fa7c876f2133a623946c68cb`,
`9f7e016b7410a33a24d72d2b137df8343dff29db`,
`934edd4d070fe6f4bffbc32f5effe3cf4f786699`, and
`093f51131223b728ce2ae4e204b3db2e087970c9` close the exact RI1, RI2, and
RI3 examples. The third correction nevertheless introduces a general
duplicate-pointer incompatibility: for an ordinary nonempty duplicate member,
both frozen generations pin the error pointer to the empty string, while the
candidate emits the duplicate's RFC 6901 location. The different pointer
changes the response bytes and receipt on both API and CLI surfaces.

This is a contract-adjudicated **CRITICAL** raw-ABI defect. The ten-byte
counterexample is one-byte-deletion minimal. The authorized stop-on-real-
divergence condition fired during targeted preflight, so the planned
12-worker, at-least-20,000-input generated expansion was not launched.
**Recommendation: NOT ADMITTED.** After four author-separated refuter rounds,
the candidate has required three treatment-informed corrections and still
misses an accepted raw-ABI closure. Its cumulative RI1/RI2/RI3 treatment
exposure also means another patched generation could no longer serve as a
fresh independent second implementation, even if it repaired this finding.

The isolated worktree was created from exact integration commit
`8a30d1aaa13e5bfddb84df9cc6db2731fd8e0d8b` on `sol/w-ri4`. The four original
candidate commits were replayed unchanged, in order, as local commits
`0053fa7`, `0c146b7`, `21e31f0`, and `0028a56`. Before this report,
`git diff --exit-code 093f51131223b728ce2ae4e204b3db2e087970c9 HEAD --
second-impl` returned 0. Both `second-impl` trees resolve to
`3f51718e3a11ea7b8bae19976d9a7b27b4ed3dd0`.

## Finding RI4-001 — CRITICAL — duplicate locations violate the frozen empty-pointer ABI

The minimized input is ten ASCII bytes. Its first `a` member is complete and
the second duplicate member name is complete; the input then ends before the
second colon/value, object terminator, and required LF:

```text
input repr:   b'{"a":0,"a"'
input hex:    7b2261223a302c226122
input length: 10
input SHA-256:
F5EECE3728CC6AFC1FF909758FEF968D8F2EBD0B6F70C5A0B75C6CC47BED4F58
```

Every surface returned exit 2 with exactly empty stderr. Frozen 0.2 and 0.3
agreed byte-for-byte with one another, as did the candidate API and CLI; the
two implementation families did not agree:

| Surface | Error | Pointer | Precedence | Receipt | stdout bytes | stdout SHA-256 |
|---|---|---|---:|---|---:|---|
| frozen 0.2 API + CLI | `ERR_DUPLICATE_KEY` | empty | 40 | `A7E43CA772D5...2D29` | 342 | `6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01` |
| frozen 0.3 API + CLI | `ERR_DUPLICATE_KEY` | empty | 40 | `A7E43CA772D5...2D29` | 342 | `6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01` |
| candidate API + CLI | `ERR_DUPLICATE_KEY` | `/a` | 40 | `FF74C85626E8...7C7D` | 344 | `A31D913ADAE1F48F61F66C70A41097A70826522A37F00A8FA2A4195A22A26D42` |

The six-surface evidence-record SHA-256, over sorted compact JSON records
containing surface, exit, error, pointer, precedence, output sizes/digests,
stderr sizes/digests, and receipt, is
`2D7C9D2FD8B3CBC04D7791AC6B7F6478418C09362AFD46C5C37339B140211261`.

The exact frozen stdout was:

```text
{"errors":[{"code":"ERR_DUPLICATE_KEY","message":"Duplicate JSON object key.","pointer":"","precedence":40}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"A7E43CA772D54C98193C02100AC1F23E75B312DCAF3F3857E737A805DBF92D29","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

The exact candidate stdout was:

```text
{"errors":[{"code":"ERR_DUPLICATE_KEY","message":"Duplicate JSON object key.","pointer":"/a","precedence":40}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"FF74C85626E8B2E5BBB8BB7FC7A3D5E95914DC830ABEE7D7F15179C0B4307C7D","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

### Contract adjudication and root cause

This is not an oracle preference. Both accepted error-law closures explicitly
pin ordinary nonempty duplicate inputs to `ERR_DUPLICATE_KEY` with the empty
pointer: `run_conformance_0_2.py:387-395` and
`run_conformance_0_3.py:537-545`. Those closures cover trailing bytes,
missing LF, noncanonical order, nested abort, NFC, floats, negative zero,
schema-root conflict, and member limits. The primary contract fixes the
duplicate code/message/precedence, and its error-selection law makes the
pointer part of the exact sealed response. `ACCEPTANCE.md` records the
duplicate-plus-trailing correction as an accepted reference fix.

The new scanner records `_join_pointer(frame["pointer"], key)` for each
duplicate at `second-impl/second_impl.py:284-294`, then returns the UTF-8-smallest
location at lines 366-371. Its candidate-local property suite likewise expects
`/a`, nested locations, escaped RFC 6901 tokens, and pooled UTF-8 location order
(`test_duplicate_precedence.py:48-63`, `136-211`). That is a coherent local
oracle, but it is not the frozen ABI. The correction special-cases only the
empty key at the root, which is why RI3's exact empty-key example now passes
while the ordinary nonempty case still diverges.

### Minimality and neighboring checks

Deleting each of the ten bytes in turn produced no frozen/candidate tuple
divergence on the two CLIs: 10 reductions tested, 0 divergent reductions. A
nonempty duplicate needs an object opener, two complete one-character member
names, a complete first value, the colon/comma separators, and the second
closing quote; the ten-byte witness contains no removable byte.

Before this witness, five malformed-token reachability probes combined a later
key-like token with a leading-zero number, trailing-dot number, truncated
exponent, invalid string escape, or unterminated string. Frozen 0.2, frozen
0.3, and candidate CLIs agreed on sealed `ERR_JSON` for all five; these were
counterevidence against a broader false-positive claim. The finding is the
narrower, directly pinned pointer law.

## Prior finding replay — all named corrections close their exact examples

The RI1 ordering pair, RI2 scalar/key surrogate pair, RI3 minimized empty-key
duplicate, and RI3's neighboring well-framed empty-key duplicate were replayed
through frozen 0.2 API/CLI, frozen 0.3 API/CLI, and candidate API/CLI. For every
input all six `(exit, stdout bytes, stderr bytes)` tuples were identical; every
exit was 2 and every stderr was empty.

| Input | Exact input hex | Input SHA-256 | stdout bytes | Common stdout SHA-256 |
|---|---|---|---:|---|
| RI1 canonical astral/BMP | `7b22f0908080223a302c22ee8080223a307d0a` | `898F487E1FFD5284DB606603F67AD297CDDB19D339CE5DDFD570B28D16D74014` | 350 | `309E457F8DE3B7970333ABBB017D54BC12507F93E6C833AA9F38130EBC0080CF` |
| RI1 reverse BMP/astral | `7b22ee8080223a302c22f0908080223a307d0a` | `74E3BA01F245DF1466E43A5DE7DFDAF97588B58EC84BC649A1FE60CF91AFC7D0` | 338 | `9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2` |
| RI2 escaped lone-surrogate scalar | `225c7564383030220a` | `B16AF5D32E117E1E4A4132716A6DFB0621BB990D1BFCCE97A9DF73774D0984F3` | 338 | `9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2` |
| RI2 escaped lone-surrogate key | `7b225c7564383030223a307d0a` | `8BA9AF9592D9FED7D0E9277137B1F224B9BB222AA3E8252C333CA28046140741` | 338 | `9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2` |
| RI3 incomplete empty duplicate | `7b22223a302c2222` | `10779FCB480886B954ACEAE3C495771971BAA338F1A8FE55A48EB68965B4D6FD` | 342 | `6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01` |
| RI3 well-framed empty duplicate | `7b22223a302c22223a307d0a` | `293AA0DC593A180913051A897487B774057874E861B66C828AEA380D08F523BD` | 342 | `6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01` |

The compact sorted JSON record for all 36 surface executions has SHA-256
`F9252CDF45038F046921ED5ACCDBFEF857D5EBE31A75E0D6CB8DDEE8F9703A61`.
The 350-byte schema response reproduced on all six RI1-canonical surfaces was:

```text
{"errors":[{"code":"ERR_SCHEMA","message":"Request does not validate.","pointer":"/format_version","precedence":80}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"751D09EF378C383F1521A6818019E017A7A3667E636DAA06C2A37CCBCAC3E890","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

The 338-byte JSON response reproduced on all six reverse-order and RI2
surrogate surfaces was:

```text
{"errors":[{"code":"ERR_JSON","message":"Invalid JSON or trailing bytes.","pointer":"","precedence":50}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"121508D748E28E6D0A7CF3B2903AA979ADFB45E8D6A58D2929236C32AAC3C99C","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

The 342-byte duplicate response reproduced on all six RI3 surfaces is the
exact frozen stdout already printed under RI4-001.

## Differential campaign and terminal stop

The deterministic expansion was bound at 20,000 raw/generated inputs with 12
workers and exact comparison of frozen 0.2 API/CLI, frozen 0.3 API/CLI, and
candidate API/CLI. Its planned strata covered malformed/truncated strings and
escapes, escaped-equivalent keys, invalid UTF-8 and BOM combinations, duplicate
plus JSON/framing/NFC/number/schema/limit precedence, duplicate-pointer pools
and UTF-8 ordering, empty root keys, arrays and nested objects, depth and large
inputs, key-like text inside values, baseline valid semantic requests,
baseline valid wrappers, and resource/termination behavior.

Targeted preflight ran before worker launch so an already pinned family would
not consume 120,000 surface executions. Six distinct probes were tried on all
three CLIs; the first five malformed-token probes agreed, and the sixth was
RI4-001. It was then replayed on all six surfaces and minimized across all ten
single-byte deletions. The terminal condition therefore fired with **0 of
20,000 generated expansion inputs executed** and the 12-worker pool was never
launched. This is the charter's real-minimized-divergence exception, not a
no-defect campaign; there is no PASS claim or 20,000-case stream hash.

## Candidate-local suites

All candidate-local suites ran unmodified under CPython 3.12.10
(`C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe`) and
passed:

- cross-test: `827/827`;
- raw ordering/precedence: `12,004/12,004`, seed `0xB1C0DE30`;
- escaped-surrogate: `12,292/12,292`, seed `0xB1C0DE33`;
- duplicate precedence: `13,012/13,012`, seed `0xB1C0DE34`.

The duplicate suite's green result is meaningful counterevidence for scanner
termination, prior examples, and many precedence combinations, but its
location-pointer assertions encode the incompatible behavior rather than
cross-checking it against a frozen runner.

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

Other concurrent repository work made elapsed time non-attributable. Resource
timings are labels only and did not change cases, timeouts, budgets, or
assertions: candidate suites 7,491 / 5,339 / 3,575 / 6,023 ms; frozen 0.2
34,903 ms; composed 0.3 32,600 ms; grounded 2,421 ms; lint 245 ms; lint meta
3,260 ms; properties 331 ms; audit adversarial 942 ms; proof 1,468 ms; fuzz
smoke 13,288 ms.

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
checks. The following seven supplemental competence records remain
descriptor-only and were not executed as candidate inputs:

`A0AAB3E298DA5C9F07D365E0F6984604C5114D3D7BF39201B1D8EA0C01D6869B`,
`53186D2261BFD1F329410129EBC9D741B6C6B9D2119A6344986FE3BF1192AA28`,
`3C051B1A76A380AEF7727F6CE02E0ABA80B0DF85CA6CAD4F11B058535CCD6621`,
`4D482F64F42D91D5907D0268E8C0A6522111B0640163C3EDE48A7FC765D4E33A`,
`AF93F8416FB19326031F79F3DA63FC8A67A3BE45A8D3138C63E990E640AFA01E`,
`25125CAB6E3BB1645C01F597E8213C28347631C0B29162A333304CEE67D18EE1`,
and
`D6C6F537B6B50941873C4FD17C8A75ECC0298E79EB82575458DEB1DB6634A56D`.

They validate supplied seals, raw digests, behavior classes, base bindings,
or declared wrapper relations. The current test output and README disclose
their nonexecution; this report does not describe `827` as executed candidate
inputs.

## Provenance, custody, and teaching-shortcut audit

- All four original candidate commits carry
  `Authored-By: sol-i1 (gpt-5.6-sol)`. RI4 made no candidate edit.
- An AST/import census of `second_impl.py` found only standard-library
  `base64`, `binascii`, `dataclasses`, `hashlib`, `json`, `pathlib`, `re`,
  `typing`, and `unicodedata`; `cli.py` adds only `sys` and local
  `second_impl`. Runtime code has no network, subprocess, clock, randomness,
  or ambient-environment input.
- Runtime file reads are confined to `Contracts._load`. It loads the primary
  and supplemental contracts, vocabulary projection, and sanitized packet
  declared in `PROVENANCE.md`. Fixture reads occur only in tests.
- Runtime literal search found no fixture IDs, expected-response table,
  frozen implementation path, `receiver_reliance`, grounded, proof, or URL
  literal. The one `baseline-run` literal is the declared primary-contract
  authority path. No source-level teaching shortcut was found.
- The disclosure distinguishes six pre-first-light authorities, four
  post-first-light fixture packs, and the RI1/RI2/RI3 correction evidence.
  Source and commit sequence are consistent with it. Git cannot prove
  historical reads or first-light timing; provenance remains a disclosure,
  not independently verified custody proof.

### Cross-worktree setup incident

During RI4 setup, a combined shell retained the integration checkout as its
working directory after `git worktree add`. The four requested cherry-picks
therefore first landed, cleanly and with no other edits, on the integration
checkout as accidental local commits `8373012`, `b6a8b61`, `4ca98b0`, and
`066f98a`. RI4 reported the error to the root custodian immediately, replayed
the originals into the correct isolated worktree, and issued a guarded repair:
the integration ref update required exact old value
`066f98accb48f258dfaef540178185f1cd67e1f6`, restored exact target
`8a30d1aaa13e5bfddb84df9cc6db2731fd8e0d8b`, and restored index/worktree from
that HEAD. The command channel was interrupted after execution. The root
custodian then independently verified integration branch/worktree clean at
exact `8a30d1aaa13e5bfddb84df9cc6db2731fd8e0d8b` and RI4 clean at exact
`0028a563c5ed38688716f1eaf923910bb36eabc2`, and explicitly prohibited any
further integration touch. All subsequent work occurred only in RI4. This
incident weakens no candidate-byte comparison, but it is disclosed because
worktree custody is part of the charter.

## Residual uncertainty

- The terminal finding intentionally prevented the 20,000-input expansion;
  additional duplicate-scanner, wrapper, schema, raw-precedence, or resource
  defects may remain.
- Candidate-local scanner coverage is broad, but the incompatible pointer
  oracle means a large part of its duplicate-location coverage is not parity
  evidence.
- Historical implementation custody cannot be proven from repository state.
- The repository gate is strong counterevidence against frozen-reference
  drift and collateral damage; most of it does not execute `second-impl`.

Report commit: this report's commit; the exact SHA is supplied in the handoff
to avoid a self-referential field.
