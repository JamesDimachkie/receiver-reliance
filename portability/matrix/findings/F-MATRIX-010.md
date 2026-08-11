# F-MATRIX-010 — focused matrix commands were dead or needlessly exhaustive

Status: **RESOLVED locally.** Correction retained and covered by two
consecutive 44/44 focused passes. No hosted run has occurred. This lane is
treatment-exposed.

## Minimized executable witnesses

Two checked-in `portability_checks` commands failed from their declared
repository-root working directory before exercising a test:

```text
python -B portability/model/explorer.py --compact
# exit 1: ImportError: attempted relative import with no known parent package

python -B portability/concurrency/test_ladder.py
# exit 1: ModuleNotFoundError: No module named 'portability'

python -B portability/concurrency/ladder.py ... \
  --receipt "{runner-temp}/concurrency-focused-<entry>.json"
# exit 1: receipt path must remain under portability/concurrency
```

The model command had a second defect: after correcting only its import mode,
it would run the complete N=48 enumeration in every focused row. That complete
enumeration belongs to the separate local model lane and takes minutes. It is
now admitted from its terminal local receipt and fresh refuter, separately
from the matrix. Running it on all fifteen scheduled normative rows plus every
stress row would turn hosted portability checks into redundant full
enumerations rather than independent portability coverage.

The prose also said missing or invalid receipts kept the workflow red without
distinguishing the gating normative/expanded evidence from stress jobs marked
`continue-on-error`. The implementation similarly let a structurally invalid
known stress receipt add a global summary error and fail the summary job.

## Why this is invalid

A plan is executable evidence only if its recorded `cwd` and `argv` start the
intended program. Static manifest equality can bind a receipt to a dead command
just as precisely as to a live one. Repeating a full finite enumeration on
unrelated platform rows is not portability coverage and delays the hosted
feedback needed for convergence. Finally, an observation-only stress row must
remain visible without silently acquiring normative gating authority.

## Local correction

- The model row now runs
  `python -B portability/model/test_model.py`, the bounded focused suite. Its
  expected count is bound to the settled 17 tests. The full explorer is not a
  hosted-row command, and the matrix never treats its separately admitted
  full-model evidence as a hosted result.
- The concurrency regression now runs
  `python -B -m portability.concurrency.test_ladder`, with the settled
  format-version-3 API and an expected count of 15 tests. The existing
  bounded `P=1,2`, five-request controller smoke now writes an entry-specific
  receipt beneath `portability/concurrency/receipts/`, the v3 harness's
  enforced custody boundary; the workflow uploads that exact path.
- Matrix tests launch all three corrected entrypoints as real `--help`
  subprocesses from their declared repository-root `cwd`, with `PYTHONPATH`
  removed and a finite timeout. Static bounds/path assertions preflight the
  separately scheduled commands without running the focused suites twice
  inside every matrix row. Tests also pin IDs, module forms, expected counts,
  and the v3 receipt path. The exact model and concurrency focused commands
  were separately executed locally and produced 17/17 and 15/15 respectively.
  The v3 concurrency package command was subsequently freshly refuted with no
  defect; its semantic projection still does not oracle every nested
  outer-audit metadata field.
- Summary output now separates `gating_errors` from `observation_errors`.
  Invalid known stress/off-contract receipts remain durable observation errors
  and yield a missing observation row, but only normative/expanded failures or
  unclassified artifact-integrity errors make the summary exit nonzero.
- The README states the same gating boundary and keeps the admitted full-model
  result separate rather than admitting it through the hosted focused profile.

## Evidence boundary

These subprocess checks prove that the package/script entrypoints and argument
parsers load on the authoring host, while separate exact-command runs establish
the current focused counts and the plan binds v3 receipt custody. Hosted
execution is still required for the actual controller smoke and platform
evidence.
The focused model suite verifies historical closures and bounded structures;
it does not replace, enlarge, or admit the separately adjudicated N=48
enumeration.
