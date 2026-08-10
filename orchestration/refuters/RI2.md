# RI2 — corrected second-implementation refutation

## Verdict

**REJECT-with-findings.** The UTF-16 correction in original candidate commit
`9f7e016b7410a33a24d72d2b137df8343dff29db` repairs RI1's astral/BMP
counterexample, but the corrected independent evaluator still diverges from
both frozen runners on contract-adjudicated escaped lone-surrogate input. A
minimal scalar is returned as the wrong sealed error, and the accepted
surrogate-key regression makes the API raise and the CLI emit no protocol
response. This is a byte- and behavior-observable **CRITICAL** raw-ABI defect.

The isolated audit worktree was created from exact integration SHA
`4d019108ede6459ae926fbca13802b06a48de2f1` on `sol/w-ri2`. Original candidate
commits `161e06b21a12a246fa7c876f2133a623946c68cb` and
`9f7e016b7410a33a24d72d2b137df8343dff29db` were cherry-picked unchanged as
local commits `3b6d309` and `6dda082`. `git diff --exit-code 9f7e016b... HEAD --
second-impl` was clean before this report; RI2 authored only this file.

## Finding RI2-001 — CRITICAL — escaped lone surrogates select the wrong error and can escape the ABI

The smallest minimized differential input is a valid UTF-8 byte sequence whose
JSON string decodes to an unpaired high surrogate:

```text
input bytes:  b'"\ud800"\n'
input hex:    225c7564383030220a
input SHA-256: B16AF5D32E117E1E4A4132716A6DFB0621BB990D1BFCCE97A9DF73774D0984F3
```

Both frozen generations select canonical-form `ERR_JSON`; the candidate
instead maps the decoded surrogate to raw-byte `ERR_UTF8`. API and CLI behavior
within each implementation agreed, all six surface executions returned exit `2`, and
all stderr values were empty:

| Surface | Error / pointer / precedence | stdout SHA-256 | receipt |
|---|---|---|---|
| frozen 0.2 API + CLI | `ERR_JSON` / empty / `50` | `9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2` | `121508D748E28E6D0A7CF3B2903AA979ADFB45E8D6A58D2929236C32AAC3C99C` |
| frozen 0.3 API + CLI | `ERR_JSON` / empty / `50` | `9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2` | `121508D748E28E6D0A7CF3B2903AA979ADFB45E8D6A58D2929236C32AAC3C99C` |
| corrected candidate API + CLI | `ERR_UTF8` / empty / `20` | `A051A3447A52A44D7E969AC904D195609714D148E0A8F40EDC3ED0F188735B5B` | `E204DA15B27C1AC4A22E2044CD51DF4A46E9994F7DBC3E288330B314216858FB` |

The repository's exact accepted regression is only four bytes longer:

```text
input bytes:  b'{"\ud800":0}\n'
input hex:    7b225c7564383030223a307d0a
input SHA-256: 8BA9AF9592D9FED7D0E9277137B1F224B9BB222AA3E8252C333CA28046140741
```

Frozen 0.2 and 0.3 APIs and CLIs again return exit `2`, empty stderr, and the
same sealed `ERR_JSON` bytes (`9543...67C2`). The candidate API instead raises
`UnicodeEncodeError`; its CLI exits `1`, writes **zero stdout bytes**, and emits
a traceback on stderr. The final stderr line is:

```text
UnicodeEncodeError: 'utf-8' codec can't encode character '\ud800' in position 2: surrogates not allowed
```

This behavior is already adjudicated, not an oracle preference. The primary
contract distinguishes invalid raw UTF-8 (`ERR_UTF8`, precedence 20) from
invalid/canonical JSON (`ERR_JSON`, precedence 50). The accepted composed
error-law gate pins `surrogate-key-alone-is-json` to the exact second input and
`ERR_JSON` at `baseline-run/implementation-output-0.3/run_conformance_0_3.py:590`;
`ACCEPTANCE.md:45` records the round-6 surrogate-key canonical-shadow fix.

### Root cause

`parse_json_bytes` correctly decodes the ASCII escape as raw UTF-8, but after
`json.loads` it treats a decoded unpaired surrogate as `ERR_UTF8` at
`second-impl/second_impl.py:203-236`. Raw UTF-8 has already succeeded; the
surrogate instead makes RFC 8785 serialization invalid and must select
`ERR_JSON`. For a surrogate member name, the generated error pointer itself
contains the surrogate. `_error` then calls the new `jcs()` serializer at lines
`775-792`; its `ensure_ascii=False` UTF-8 encoding fails at line 91. Because the
exception is thrown inside the `except ProtocolProblem` handler at lines
`804-805`, the sibling broad handler cannot contain it.

### Counterevidence sought

- `python -B second-impl/test_raw_properties.py` passed `12,004/12,004`, but its
  2,000 parse-precedence cases cover only eight fixed families and contain no
  surrogate escape. Its 10,000 ordering cases use valid scalar values.
- The fixture cross-test passed `827/827`, but the sealed fixture corpus does
  not exercise this accepted error-law case against the candidate.
- The entire reference/grounded repository gate passed, including the exact
  surrogate-key closure in composed conformance. That proves the frozen oracle
  is internally green and is counterevidence against reference drift; it does
  not exercise the independent candidate on the same closure.
- The RI1 astral/BMP bytes now agree exactly in both orders, so the correction
  did fix its named defect. That does not rescue this separate raw-wire defect.

## RI1 correction replay

The exact RI1 canonical input and its reverse were independently sent through
the frozen 0.3 API/CLI and corrected candidate API/CLI:

| Input | Input SHA-256 | All four surfaces | stdout SHA-256 |
|---|---|---|---|
| `7b22f0908080223a302c22ee8080223a307d0a` | `898F487E1FFD5284DB606603F67AD297CDDB19D339CE5DDFD570B28D16D74014` | exit `2`, empty stderr, `ERR_SCHEMA`, `/format_version`, precedence `80` | `309E457F8DE3B7970333ABBB017D54BC12507F93E6C833AA9F38130EBC0080CF` |
| `7b22ee8080223a302c22f0908080223a307d0a` | `74E3BA01F245DF1466E43A5DE7DFDAF97588B58EC84BC649A1FE60CF91AFC7D0` | exit `2`, empty stderr, `ERR_JSON`, empty pointer, precedence `50` | `9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2` |

The response receipts also agreed exactly (`751D09EF...E890` canonical,
`121508D7...C99C` reverse). RI1-001 is therefore closed by the correction.

## Differential campaign and terminal stop

A temporary inline Python harness imported `fuzz/fuzz.py` only as the input
generator, loaded the frozen 0.3 runner and candidate in separate modules, and
compared `(exit_code, stdout bytes, stderr bytes)`. Wrapper-fixture sources
were routed to `execute_wrapper`; all other cases used `execute`. Seed
`0x005249325EED8785`, all 31 P3 strategies, and 1,000 generated inputs were
evaluated in the exploratory batch. The batch reported 416 raw tuple
mismatches; that aggregate was not adjudicated because some wrapper-origin
mutations lose their in-wire dispatcher and require separate interface
interpretation.

The first unambiguous core mismatch was generated index 12:

```text
case_id: S005249325EED8785-C000012-lone_surrogate-DC638594F89D
strategy: lone_surrogate
source: synthetic:lone-surrogate-escape
input SHA-256: DC638594F89D2494EEDEA44568C07EE69802E079562DCAF7504399285EFE5F7C
input: b'{"format_version":"B1-SEMANTIC-DECISION-REQUEST-0.2","x":"\ud800"}\n'
```

It was minimized to the 9-byte scalar above, then replayed through both frozen
generations and both candidate surfaces. Once the divergence was adjudicated
against the accepted error-law closure, the charter's terminal stop condition
fired. The planned at-least-20,000 expansion was therefore intentionally not
run. No claim is made that the remaining observed mismatches are all defects.

## Repository gate

Commands ran under CPython `3.12.10` (`C:\Users\james\AppData\Local\Python\bin\python.exe`).
The 48-worker P3 campaign was active and CPU use was about 91%; fuzz smoke
nevertheless completed within its unchanged contract budget, so no isolated
rerun was needed.

```powershell
python second-impl/test_cross.py
python -B second-impl/test_raw_properties.py
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

- candidate cross-test: `827/827`;
- candidate raw properties: `12,004/12,004`, seed `0xB1C0DE30`;
- frozen 0.2 conformance: `800` checks, `0` failures;
- composed 0.3 conformance: 0.2 suite `800/800`, 0.3 suite `107/107`;
- grounded regression: `504/504`;
- authority lint: `0` findings over `199` required fields;
- lint meta-test: `7/7`;
- properties: `2,296/2,296`, seed `0x5EED8785`;
- audit adversarial: `6,497/6,497`;
- proof harness: `7/7`;
- fuzz smoke: `31/31`, seed `0x000000000B10F042`, all 31 strategies,
  `budget_exhausted=false`.

## Provenance, teaching-shortcut, and denominator audit

- An AST census of `second_impl.py` and `cli.py` found only standard-library
  imports plus local `second_impl`. There is no network, subprocess, clock,
  randomness, or ambient-environment dependency in runtime code.
- Runtime file reads are confined to `Contracts._load` and the four declared
  contract/access authorities at lines 398-401. Runtime string-literal search
  found no fixture IDs, wrapper-pair IDs, expected-response keys, frozen
  implementation paths, `receiver_reliance`, grounded, proof, or URL literals.
  No source-level teaching table or fixture shortcut was found.
- Both original candidate commits carry `Authored-By: sol-i1 (gpt-5.6-sol)`.
  Source inspection is consistent with the disclosed custody story, but Git
  cannot prove historical reads or the claimed first-light ordering.
- The `827` aggregate is arithmetically `124` semantic + `416` executable
  competence + `7` descriptor-only + `248` wrapper arms + `20` wrapper
  negatives + `12` wrapper metamorphic checks. The seven descriptors remain
  nonexecuted: six validate supplied response seals/digests/classes and one
  validates a declared base-response binding. Current stdout and README call
  them descriptor adjudications and do not call `827` executed candidate
  inputs. The phrase “exact agreement counts” in the README remains broader
  than this mixed aggregate, but the adjacent disclosure prevents a new hidden
  denominator claim. RI1-002's underlying caveat still applies.

## Residual uncertainty

- The terminal divergence prevented the at-least-20,000 differential
  expansion and adjudication of later mismatches; additional independent
  candidate defects may remain.
- Historical custody cannot be established from a same-commit provenance
  narrative.
- The repository gate is strong counterevidence for frozen-reference drift and
  collateral breakage, but most of it does not execute `second-impl`.

Report commit: this report's commit; the exact commit SHA is supplied in the
handoff to avoid a self-referential field.
