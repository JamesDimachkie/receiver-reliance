# Hosted portability matrix

This directory is treatment-exposed. It must not author future blinded worlds,
oracles, gold data, or renderers for the research program.

`plan.json` is the deterministic inventory and command manifest.
`receipt.py` is a standard-library-only runner, environment probe, receipt
writer, and coverage summarizer. It never installs a package, reads a secret,
or converts a failed normative command into infrastructure absence.

The normative plan contains CPython 3.12, 3.13, and 3.14 on all six requested
OS/architecture rows. Fifteen rows are scheduled. The three requested
`macos-13` x64 rows are retained but emitted as `INFRA_UNAVAILABLE`: as checked
on 2026-08-10, GitHub's current standard hosted-runner table no longer lists
that label, and scheduling a nonexistent label can wait 24 hours. CPython on
`macos-15-intel` is collected only as a stress/non-substitute observation.
The free-threaded 3.14t row additionally runs the bounded concurrency harness
through `P = 1, 2, 4, 8` with 200 requests per caller and the harness's two-run
byte comparison. Every focused row runs the repo-root focused model regression
and package-mode concurrency regression, then a small `P = 1, 2`
controller smoke against the format-version-3 concurrency API. The complete
N=48 model enumeration is deliberately not repeated across the hosted matrix:
hosted rows verify only the bounded focused closures. Full-model evidence
is `ADMITTED` from its separate local N=48 run and fresh refuter verdict; the
matrix neither admits nor substitutes that separately scoped full-model
evidence. This keeps the matrix executable without turning one
finite enumeration into fifteen redundant long-running jobs.
`plan.json` schedules `portable-bundle-gate` on every normative row, so every
row run from the current plan verifies and executes the exact checked-in
portable bundle. That gate covers the three-way host preflight, independent
total runtime, raw-boundary probes, correlated sidecar transport, receipt
bindings, and deterministic archive construction. A local bundle hash is not
substituted for any hosted row. **The committed hosted evidence under
`../receipts/hosted/` predates that command.** Run 31562391384 executed the
17-command manifest of its own era; `portable-bundle-gate` was added afterwards
and F-MATRIX-015 migrated the planned count from 17 to 18 in the same change.
`portability/verify_receipts.py` declares that era explicitly
(`HOSTED_ERA_ABSENT_COMMANDS`, `HOSTED_ERA_EXPECTATIONS`) and replays all 25
committed rows through the current row validator against it, so the difference
between what the plan now schedules and what the committed receipts prove is
enforced rather than assumed.
Concurrency v3 keeps its proof layers separate: concurrent physical bytes are
compared with isolated grounded transport bytes, while each inner
`sealed_response` is compared with the independent semantic oracle. That
semantic projection does not oracle every nested outer-audit metadata field,
including `engine_generation`.
Python Development Mode, a pydebug capability probe, PyPy 3.12/3.11, and
GraalPy are stress or off-contract observations, never normative substitutes.
The GraalPy row deliberately separates the `graalpy-24.0` setup/distribution
release family from its Python 3.10 language level. The workflow records the
pinned setup action's resolved GraalPy patch release; summary validation binds
that observation to the 24.0 family and independently binds `sys.version_info`
to Python 3.10. The contract language floor remains 3.12, so this row remains
off-contract and cannot substitute for a supported CPython row.

Outcomes are intentionally separate:

- `PASS`: the requested environment was present and every declared command,
  exit, and expected suite count passed.
- `DIVERGENCE`: a normative command, exit, timeout, or count differed. This
  returns nonzero and stops that job at the first failing command.
- `OBSERVED_DIVERGENCE`: the same observation on a stress or off-contract row;
  it is not a normative claim.
- `INFRA_UNAVAILABLE`: a durable receipt explicitly proves a predeclared runner
  absence or an observed setup/runtime-build capability failure. It does not
  fail the matrix.
- `RECEIPT_MISSING`: a scheduled row produced no durable receipt. For a
  normative row this is a closed failure because runner/job failure, a killed
  receipt writer, and upload/download loss cannot be distinguished safely.

Every runnable receipt, including explicit setup/runtime absence, binds the
workflow SHA and a clean checkout. Executed receipts additionally record OS,
release, kernel, architecture and emulation probe; implementation, full
version, build flags,
GIL state, word size, byte order, locale and filesystem encodings; exact
commands; suite counts; stream hashes; exits; elapsed time; and bounded host
and child-process resource observations. The final summary preserves the three
predeclared unscheduled `macos-13` rows as evidenced `INFRA_UNAVAILABLE` rows.
It never synthesizes infrastructure evidence for a scheduled runnable row.
Normative job failure, missing/invalid receipts, and receipt artifact transport
failure are not interchangeable across evidence classes. Normative and
expanded-gate receipt failures are gating: a missing, invalid, divergent, or
transport-lost normative artifact keeps the workflow red. Stress and
off-contract rows are observation-only and cannot substitute for a normative
row. Their failures, missing receipts, and `OBSERVED_DIVERGENCE` outcomes
remain visible as row outcomes; invalid receipt artifacts are additionally
listed in `observation_errors`. None becomes a normative failure.

Summary validation binds each executed argv, cwd, timeout, expected count, and
result projection to the checked-in manifest. For every executed outcome it
also recomputes the plan binding for OS family, native non-emulated machine,
runtime identity and CPython/PyPy/GraalPy language major/minor, the closed
`sys.version_info` release-level/serial schema and its `sys.version` prefix, GraalPy's
separate setup-resolved distribution family, requested stress capability, 64-bit
little-endian ABI, UTF-8 encodings, clean checkout, and `GITHUB_SHA`. Malformed
hashes, negative metrics, inconsistent resources, or top-level count drift are
rejected. This is a fail-closed structural and self-consistency check, not
independent process attestation: hashes cannot prove byte contents that the
receipt does not embed.

Downloaded receipt JSON is treated as hostile input. Numeric evidence is
validated without lossy integer-to-float or decimal-to-binary coercion:
booleans, negative zero, non-finite values, oversized integers, extreme
exponents, out-of-range version/exit metadata, and timings beyond the command's
declared timeout plus bounded collection slack make the summary red. Exact
Decimal parsing preserves tiny positive values and the deterministic writer
retains them as JSON numbers. Even a validator exception is converted into a
durable invalid-receipt result rather than terminating summary production.
Before decoding, each JSON input is capped at 16 MiB and scanned iteratively
with a maximum structural depth of 64. Canonical output uses an explicit-stack
writer with the same depth limit and a 64 MiB byte ceiling, so deeply nested
artifacts cannot exhaust the Python call stack or suppress the durable red
summary.

Local checks:

```text
python -B portability/matrix/test_receipt.py
python -B portability/model/test_model.py
python -B -m portability.concurrency.test_ladder
python -B portability/matrix/receipt.py emit-matrix --role normative_matrix
python -B portability/matrix/receipt.py emit-matrix --role stress_matrix
```

## Nonclaims

No efficacy, novelty, security, fuzzing-completeness, external-standard, or universal-portability claim.
The proof tier stays `internal held-out`. Matrix
evidence alone does not establish the charter's bounded cross-platform success
statement; that requires terminal evidence from the other lanes and hosted
jobs.
