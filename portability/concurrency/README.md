# Bounded concurrency ladder

This stdlib-only harness exercises the accepted grounded 0.4 batch surface in
two ways: concurrent in-process callers of `rr_batch.serve`, and concurrent
real `rr_batch.py` processes. It does not modify the accepted implementation.

The normative command is:

```text
python -B portability/concurrency/ladder.py --attempt 3 --receipt portability/concurrency/receipts/normative-release-audit-head-8a525b1-attempt3.json
```

It freezes the following bounds and refuses larger CLI values:

- callers `P = 1, 2, 4, 8, 16, 32`;
- 200 physical NDJSON requests per caller;
- two identical-seed runs at every mode/level, compared byte-for-byte;
- 1,000 requests per caller at the two highest fully passing levels;
- 120 seconds shared by both runs and the cancellation probe for each
  `(mode, P, request-count)` level;
- one acknowledgement-driven cleanup-after-cancellation probe per level;
- automatic `P <= 8` repetition on CPython 3.14t only when a candidate both
  exposes `sys._is_gil_enabled()` and reports that the GIL is disabled.

Each caller receives a reproducible sequence with a class-covering valid
synthetic fixture every 50 records and seeded malformed records elsewhere.
All callers rendezvous on a named start barrier. OS interleaving remains an
uncontrolled stress dimension; the harness never uses sleeps to decide an
outcome. Receipts record request and response order hashes per caller,
aggregate output bytes, exits/stderr, elapsed time, deadlock/timeout status,
RSS, handles/FDs, threads, process counts, and cancellation cleanup.

The harness keeps transport parity and semantic correctness as two distinct
obligations:

1. **Physical transport comparator.** Each unique raw input is run once in a
   fresh isolated `grounded-0_4/rr_batch.py` process and cached for that worker.
   Concurrent library/process output must match those audited 0.4 physical
   lines exactly. Because this comparator is derived from the accepted code
   under test, it proves only that concurrency preserved isolated physical
   output. It is explicitly not a semantic oracle.
2. **Independent semantic oracle.** Every concurrent physical line is parsed
   as strict UTF-8 integer-domain JSON; checked for the exact audited 0.4
   top-level type, version, and fields; checked for its audit seal, request hash
   binding, and independent clean-room JCS+LF spelling; then its
   `sealed_response` is independently canonicalized and compared byte-for-byte
   with `FixtureOracle.expected_record(raw)`. The accepted implementation never
   supplies this semantic expectation.

The semantic audit checks the outer envelope's strict JSON, exact top-level
surface, canonical spelling, self-zero seal, request binding, and exit/class
agreement with the oracle-validated sealed response. It does not independently
validate the meaning of every other nested `audit` member, such as
`engine_generation`; that remains an explicit outer-audit nonclaim.

The O-ORACLE `relation_concurrency_vs_isolated` helper is not cited as CUT
transport proof. Its own oracle-only metamorphic statement remains separate
from observations of concurrent accepted-code execution.

The controller stops at the first byte/order/count/cleanup/progress invariant
failure or recognized host resource ceiling. It never retries a deterministic
failure and accepts only `--attempt 1..3`. On divergence, the receipt includes
the first differing physical record, exact raw input and expected/actual bytes
in base64, hashes, exit evidence, environment, resources, and the seeded
caller schedule. No accepted implementation repair is attempted.

For a quick harness-only smoke check without changing normative bounds:

```text
python -B portability/concurrency/ladder.py --levels 1,2 --requests 5 --skip-soak --no-free-threaded --attempt 3 --receipt portability/concurrency/receipts/smoke-release-audit-head-8a525b1-attempt3.json
```

The smoke command lowers coverage and is not a normative ladder receipt.
`smoke-release-audit-head-8a525b1-attempt3.json` is the current v3 smoke
preflight; `normative-release-audit-head-8a525b1-attempt3.json` is the current
v3 normative run. Both record clean source HEAD `8a525b1`.
Historical v1 receipts are stale—specifically, historical `smoke.json` records
`INVARIANT_FAILURE`, never PASS—and the stopped v2 receipt records the
adjudicated semantic/transport layer mismatch. Exact receipt/source hashes,
R-CONC-4's independent recomputation, and the outer-audit nonclaim are in
`receipts/STATUS.md`.

The earlier `*-correction-attempt3.json` receipts record `git.clean=false` at
baseline HEAD `4e788d2` and overlapped the compact model explorer. They are
retained as superseded history, not current evidence. Exact current and
historical hashes, source bindings, and resource qualifications are in
`receipts/STATUS.md`.

This lane is treatment-exposed. It must never author the research program's
future blinded worlds, oracle, gold, or renderer.

## Nonclaims

This is bounded negative evidence. It does not establish efficacy, novelty,
security, fuzzing completeness, external-standard conformity, or universal
portability. Expected bytes cover the exact four frozen fixture packs plus the
independent raw-record classifier's bounded error surface; valid requests
outside those frozen packs remain outside the oracle's claim.
