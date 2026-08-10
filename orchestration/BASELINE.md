# Validation baseline

- Verdict: **PASS**
- Branch: `sol/w-w0`
- Integration branch: `sol/rr-continuation-20260810`
- Integration SHA / checked-out HEAD: `9264af86746ac713ffaaaa4a299b0f8ff8b7e4c8`
- Python: `Python 3.12.10`

## Clean-checkout proof

Run from the repository root before validation:

```text
$ git status --short --branch
## sol/w-w0
$ git rev-parse HEAD
9264af86746ac713ffaaaa4a299b0f8ff8b7e4c8
```

The absence of paths after the branch line proves that the worktree was clean before the validation commands ran.

## 1. Frozen 0.2 conformance suite

Working directory: `baseline-run/`

Command:

```text
python -B implementation-output-0.2/run_conformance_0_2.py
```

Standard output (verbatim):

```text
mode=in-process counts={"semantic": 112, "competence": 370, "wrapper_arms": 224, "negative": 10, "metamorphic": 4, "error_law": 80} failures=0
```

Standard error: empty.

Exit code: `0`

## 2. Frozen 0.3 conformance suite

Working directory: `baseline-run/`

Command:

```text
python -B implementation-output-0.3/run_conformance_0_3.py --suite all
```

Standard output (verbatim):

```text
mode=in-process suite=0.2 counts={"competence": 370, "error_law": 80, "metamorphic": 4, "negative": 10, "semantic": 112, "wrapper_arms": 224} total=800 failures=0
mode=in-process suite=0.3 counts={"competence": 53, "metamorphic": 8, "negative": 10, "semantic": 12, "wrapper_arms": 24} total=107 failures=0
```

Standard error: empty.

Exit code: `0`

## 3. Grounded 0.4 regression suite

Working directory: repository root.

Command:

```text
python -B grounded-0_4/test_grounded_0_4.py
```

Standard output (verbatim):

```text
grounded-0.4 regression: checks=504 failures=0
```

Standard error: empty.

Exit code: `0`

## 4. Contract lint gate

Working directory: repository root.

Command:

```text
python -B grounded-0_4/lint_contract.py --gate
```

Standard output (verbatim):

```text
authority ledger: {'inert_disclosed': 10, 'inert_registered_debt': 14, 'presence_only': 64, 'semantic': 111} of 199 required fields
lint: 0 findings
```

Standard error: empty.

Exit code: `0`

## Final verdict

**PASS.** All four commands matched the expected untouched baseline and exited with code 0. The 0.2 count categories sum to 800; the 0.3 runner reported totals of 800 and 107; the grounded regression reported 504 checks; every failure count was zero; and the lint gate reported zero findings.
