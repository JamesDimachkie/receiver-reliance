# Documentary consistency audit

> **Superseded counts (annotated 2026-08-17, re-measured 2026-08-19).** This
> audit is dated 2026-08-10 and its verification column records what was live
> *then*. Four of those numbers have since moved, so this document must not be
> read as a current validation gate:
>
> | Then (2026-08-10) | 2026-08-17 | Now (2026-08-19) |
> |---|---|---|
> | grounded regression 504 checks | `checks=517 failures=0` | `checks=521 failures=0` |
> | lint-gate meta-test 7 checks | `checks=9 failures=0` | `checks=9 failures=0` |
> | authority census 111 semantic / 64 presence-only | `141 semantic / 34 presence_only` (of 199) | unchanged |
> | `verify_receipts` 154 checks | `checks=267 failures=0` | `checks=297 failures=0` |
>
> The middle column is itself a dated observation and is kept rather than
> overwritten: a "Now" column that gets silently rewritten is the failure this
> table exists to expose. `python -B portability/verify_live.py` recomputes all
> four at the bytes you have checked out. ERRATA `F-WP2-001` records why the
> authority census moved: 30 dual-use fields had been wrongly subtracted from
> the semantic count. The rows below are left unedited on purpose — this is a
> dated observation record, not a dashboard.

Audit date: 2026-08-10

Audited revision: `dfae0c219921919d4d1fe42f536fa01a46477432`

Owned documents: `README.md`, `ERRATA.md`, `HOST_OBLIGATIONS.md`, and
`baseline-run/RUNBOOK.md`. This file records the evidence used to check their
counts, paths, commands, format strings, and quoted digest. No sealed artifact
was edited.

Disposition codes:

- **VC** — verified against current repository bytes or a live command.
- **HP** — historical/pinned statement agrees with `ACCEPTANCE.md`, but the
  repository explicitly says the underlying process record is not included.
- **IA** — intentionally absent artifact, accurately disclosed as absent.
- **UR** — unresolved here because the required external bytes are excluded by
  the repository-only data boundary.
- **FIX** — demonstrated drift or ambiguity corrected in an owned document.

## Counts and numerical claims

| Claim and owned location | Evidence source or command | Disposition | Uncertainty |
|---|---|---|---|
| Release 1.1; Apache-2.0; 2026 copyright (`README.md`) | `git rev-parse v1.1^{}` peels to release commit `8589b43d...`; `LICENSE` begins “Apache License Version 2.0”; repository history dates the release to 2026. | VC | Copyright ownership itself is a repository assertion, not independently adjudicated. |
| 28 accepted operations + 2 supplemental = 30 composed (`README.md`, `RUNBOOK.md`) | JSON parse: `len(baseline-run/control/B1_CAPABILITY_MATRIX_0_1.json.rows)=28`; `len(supplemental-0_3/control/B1_COMPOSED_CAPABILITY_MATRIX_0_3.json.rows)=30`; base/supplemental/composed operation registries are 28/2/30. | VC | None. |
| Four result classes (`VALID`, `MALFORMED_OR_BOUNDARY`, `BINDING_OR_CONFLICT`, `OMISSION_OR_INCOMPLETE`) | Base contract predicate table and both live conformance summaries. | VC | None. |
| 0.2: 112 semantic, 370 competence, 224 wrapper arms, 10 negative, 4 metamorphic, 80 error-law = 800; 720 fixture-pinned (`README.md`, `ERRATA.md`, `RUNBOOK.md`) | Fixture JSON declares and contains 112 entries, 370 competence cases, 112 pairs/224 arms, 10 negatives, and 4 metamorphic cases. Live `python -B implementation-output-0.2/run_conformance_0_2.py` from `baseline-run/` reported the same counts and `failures=0`. Arithmetic: fixture-pinned `112+370+224+10+4=720`; total `720+80=800`. | VC | Frozen runner module docstrings still say 78 error-law closures (55+19+4), but live functions return 57+19+4=80 and the runbook/output are current. The frozen source cannot be edited in this lane. |
| Error-law split: 57 parse/limit/canonicality, 19 fixture-derived pools, 4 transcript guards (`RUNBOOK.md`) | Read-only import of frozen `run_conformance_0_2.py`: `len(error_law_cases())=57`, `len(error_pool_cases(...))=19`; runner adds 4 strict-wire guards. | VC | Same stale frozen docstring noted above. |
| 0.3 supplemental: 12 semantic, 53 competence, 12 pairs/24 arms, 10 negative, 8 metamorphic across five named families = 107 (`README.md`, `RUNBOOK.md`) | Supplemental fixture JSON declares and contains 12 entries, 53 competence cases, 12 pairs/24 arms, 10 negatives, and 8 metamorphic cases. The competence/fixture names cover unnecessary asks, answer replay, wrong-intent similarity lures, intent changes, and incompatible distractors. Live composed runner reported `total=107 failures=0`. | VC | None. |
| Composed suite 800+107=907 (`README.md`, `ERRATA.md`, `RUNBOOK.md`) | Live `python -B implementation-output-0.3/run_conformance_0_3.py --suite all` from `baseline-run/` reported totals 800 and 107, both with zero failures. | VC | None. |
| Ten 0.2 review rounds; 22 valid defects; 2 refuted findings; final 45 probes and 70,000 randomized cases (`README.md`) | `ACCEPTANCE.md` lines 3-24 and 38-57 give the round table and explicitly classify it as internal history not independently verifiable from release bytes. | HP | Probe-level process record is outside the release. |
| Two original contract non-closures, 240-character cap, and one supplemental non-closure (`README.md`, `ERRATA.md`) | `ACCEPTANCE.md` lines 59-74 records the two original items and cap; lines 133-139 records the third. The base schema has `maxLength: 240`; the supplemental exclusion-reason enum contains one member. | VC for schema shape; HP for review discovery history | None beyond the historical-process limitation. |
| Supplemental acceptance counts: round 1 with two fixture blockers; round 2 PASS/zero; implementation round 1 with 5,132 executions/zero valid defects; blind review COMPLETE (`README.md`) | `ACCEPTANCE.md` lines 82-131 and shipped `supplemental-0_3/BLIND_GATE_VERDICT_0_3.md`. | HP | The detailed execution record and reviewer session transcript are not in this release; only the pinned summary/verdict is available. |
| Five nonempty OBL-22 content-digest arrays; 0.2 `clarification_state=NONE`; 0.3 adds `REQUESTED`/`RESOLVED` (`README.md`, `RUNBOOK.md`) | Decoding fixture requests found five `*_sha256s` arrays in the supplemental OBL-22 IO entry, all nonempty; 0.2 wrapper arms: `NONE=224`; 0.3 arms: `NONE=18`, `REQUESTED=4`, `RESOLVED=2`, with pair parity true. | VC | None. |
| Four effect-bound operations (`RUNBOOK.md`) | Supplemental contract's inherited effect scope names OBL-19, OBL-20, OBL-26, and OBL-28. | VC | None. |
| External review on 2026-08-10 against `cc6f3657`; zero sealed 0.2/0.3 paths changed (`README.md`, `ERRATA.md`) | `git show -s cc6f3657` resolves to `cc6f3657f...`, dated 2026-08-10. `git diff --name-only cc6f3657..dfae0c2 --` over all frozen path sets and protected files returned no paths. | VC | “Independent external” is provenance asserted by the repository; authorship was not independently reconstructed. |
| Proof: calibrated 18/18, zero false holds; strict 133 false holds; in-process 2.998 ms vs subprocess 104.99 ms (`README.md`, `HOST_OBLIGATIONS.md`) | `proof/results.json` and generated `proof/RESULTS.md`: calibrated TP/FN/FP/TN = 18/0/0/390; strict = 18/0/133/257; recorded means 2.998 ms and 104.99 ms. README timing wording now identifies these as recorded proof-run measurements. | VC for committed snapshot | Timing is historical and machine-dependent, not a universal performance guarantee. |
| Strict adapter “clean-record” false-hold percentage (`ERRATA.md`, `HOST_OBLIGATIONS.md`) | `proof/results.json` defines false-hold rate as `fp/(fp+tn)`: `133/(133+257)=133/390=34.1%`. The former 32.6% was `133/408`, the full-corpus share, mislabeled as a clean-record rate. | FIX | `proof/README.md` remains outside this lane and still contains the same 32.6%-of-clean denominator error. |
| Grounded regression has 504 checks (`README.md`) | Live `python -B grounded-0_4/test_grounded_0_4.py` reports `checks=504 failures=0`. | VC | None. |
| Authority census: 199 required = 111 semantic + 64 presence-only + 10 disclosed inert + 14 registered debt; 24 never referenced (`ERRATA.md`) | Live `python -B grounded-0_4/lint_contract.py --gate` reports those four category counts and `lint: 0 findings`; `10+14=24`. Opening shorthand was expanded to state the denominator and subset. | VC/FIX | None. |
| CPython 3.12 runtime family; pinned 3.12.4 toolchain; current verification on 3.12.10 (`README.md`, `RUNBOOK.md`) | `python --version` returned 3.12.10; contract `toolchain_manifest_tree_reference.expected_version` is 3.12.4; `ACCEPTANCE.md` records byte parity on 3.12.4 and 3.12.10 (also 3.14.5). | VC/HP | The phrase “any CPython 3.12” is not exhaustively provable across every build, but two 3.12 versions are recorded and the current one passes. |
| Four adjacent-system bullets (`README.md`) | The section contains exactly four bullets. | VC for documentary count | External project descriptions and “as of August 2026” were not refreshed; external access is outside this repository-only sweep. RFC 9943 is treated as an identifier, not a count. |

## Paths and cross-references

| Claim and owned location | Evidence source or command | Disposition | Uncertainty |
|---|---|---|---|
| Root-local README links: `LICENSE`, `HOST_OBLIGATIONS.md`, `ERRATA.md`, `EXAMPLE.md`, `ACCEPTANCE.md`, `baseline-run/`, `baseline-run/RUNBOOK.md`, `supplemental-0_3/`, its `receipts/` and blind verdict, `grounded-0_4/` API/closure/register/lint/test files, and `proof/`/its README/results | `Test-Path` from repository root returned true for every listed distributed target. | VC | External web links were not fetched. |
| Supplemental implementation path in `README.md` | `Test-Path implementation-output-0.3` was false; `Test-Path baseline-run/implementation-output-0.3` was true. Corrected the root-relative path. | FIX | None. |
| Grounded filenames in `ERRATA.md` | Root-relative `lint_contract.py`, `test_grounded_0_4.py`, and `closures_0_4.json` did not exist. Qualified them as `grounded-0_4/...`; also qualified `rr_api.py::decide_audited`. All corrected targets exist. | FIX | None. |
| Host paths and commands: grounded closure/register/lint/API/test, proof adapter/results, and errata | `Test-Path` from repository root returned true for each file target. The BINDING test reference was expanded to an executable command. | VC/FIX | Host-specific adapter checks remain integrator obligations and cannot be run against an unspecified host. |
| Runbook paths relative to `baseline-run/`: two control files, two 0.2 fixture packs, fixture receipt, both implementation directories, `../ACCEPTANCE.md`, and supplemental control/fixtures/receipts/root | `Test-Path` after resolution from `baseline-run/` returned true for every distributed target. | VC | None. |
| `toolchain/`, `toolchain/python.exe`, `toolchain/TOOLCHAIN_MANIFEST_0_1.json`, and `toolchain/python312._pth` | `baseline-run/toolchain/` is absent, matching the disclosure. The contract pins the future manifest path as `../toolchain/TOOLCHAIN_MANIFEST_0_1.json` from `control/`, plus 11,562 bytes and SHA-256 `A6A3...C9314`; it separately pins `../toolchain/python.exe`. README/runbook wording now distinguishes the absent provenance manifest from the required sealed-mode executable. | IA/FIX | The withheld files cannot be byte-checked. |

## Commands, formats, and digests

| Claim and owned location | Evidence source or command | Disposition | Uncertainty |
|---|---|---|---|
| `python -B implementation-output-0.2/run_conformance_0_2.py` from `baseline-run/` | Live exit 0; exact documented count summary; zero failures. `-B` was added to matching runbook invocations to avoid bytecode-cache writes beneath frozen implementation directories. | VC/FIX | None. |
| `python -B implementation-output-0.3/run_conformance_0_3.py --suite all` from `baseline-run/` | Live exit 0; exact two documented summary lines; totals 800/107; zero failures. | VC/FIX | None. |
| `python -B grounded-0_4/test_grounded_0_4.py`, lint `--gate`, and `python -B grounded-0_4/test_lint_gate.py` from repository root | All three live commands exited 0; outputs were 504/0, lint 0 with the 199-field census, and meta-test 7/0. README now names all three existing grounded verification surfaces. | VC/FIX | None. |
| Single-request heredoc in `RUNBOOK.md` | The Python body was executed through PowerShell standard input with `python -B -`; runner exit 0 and `byte-exact: True`. The nested runner argv already uses `-I -B`. | VC/FIX | The literal Bash heredoc wrapper was not executed on Windows; its Python body and paths were exercised equivalently. |
| `python -B implementation-output-0.2/run_conformance_0_2.py --subprocess` | Command and runner path are valid, but execution was deliberately not attempted because the accurately disclosed `toolchain/python.exe` is absent. | IA | Sealed subprocess parity is HP evidence in `ACCEPTANCE.md`, not a live result in this checkout. |
| `python -B implementation-output-0.2/emit_manifest_0_2.py` and 0.3 emitter absence behavior | Live read-only attempts with `-B`: both exited 1; 0.2 raised `FileNotFoundError` for the absent manifest and 0.3 reported the missing manifest, matching the runbook. | VC | Withheld-manifest success path cannot be exercised. |
| Shared request format `B1-SEMANTIC-DECISION-REQUEST-0.2` and E1 collision (`ERRATA.md`) | Recursive JSON scan found the value in both base and supplemental request schemas. Feeding the same supplemental OBL-30 VALID request bytes to both frozen runners produced 0.2 `ERR_SCHEMA`/exit 2 and 0.3 PASS/exit 0. Lint meta-test also proves an ungrandfathered duplicate is rejected. | VC | None. |
| Behavior/result strings, wrapper states, and fixture suffix mappings quoted in the owned docs | Compared with base/supplemental schemas, fixture-author contract, fixture entry IDs, and live response objects. | VC | None. |
| External CPython zip URL and SHA-256 `15fea3c9367653a85086fe37216b4d1a1c78688fa5e1587e1db0b0f658856564` (`README.md`, `RUNBOOK.md`) | The URL and digest agree byte-for-byte between both owned documents. No archive or independent digest authority is present in the clone. | UR | Repository-only boundary forbids fetching the archive; the digest was not re-derived. |
| Self-zero SHA-256 and raw SHA-256 behavior described generally | Both conformance runners and the grounded regression re-derived their pinned seals successfully; the hand-run response was byte-exact. | VC within shipped suites | This verifies covered artifacts, not every possible future reimplementation. |

## Final validation gate

Run from the final worktree unless a working directory is stated:

1. `python -B implementation-output-0.2/run_conformance_0_2.py` from
   `baseline-run/`: 800 checks, zero failures, exit 0.
2. `python -B implementation-output-0.3/run_conformance_0_3.py --suite all`
   from `baseline-run/`: 800 + 107 checks, zero failures, exit 0.
3. `python -B grounded-0_4/test_grounded_0_4.py`: 504 checks, zero failures,
   exit 0.
4. `python -B grounded-0_4/lint_contract.py --gate`: 199-field census,
   zero findings, exit 0.
5. `python -B grounded-0_4/test_lint_gate.py`: 7 checks, zero failures,
   exit 0.

`git diff --check` also passed. All corrections are documentary; frozen 0.2,
0.3, supplemental, access, acceptance-history, pinned-example, attributes,
and license bytes remain unchanged.
