# F-MATRIX-015 — robustness-era count pins failed closed on the consolidated main

Status: **RESOLVED in the commit carrying this finding; the first green
`main` portability run after it supersedes the red run below.**

After the robustness program was consolidated to `main` (`9bbf687` →
`df7a4aa`) and its branch ref retired, the first push-triggered portability
run met the program's bytes for the first time — the robustness branch
workflow ran conformance and the program suites, never the portability
matrix. Three verification surfaces still pinned pre-robustness truths and
were not migrated by the program commits that moved them:

- `portability/matrix/test_receipt.py` pinned `commands_planned == 17` in
  two summary tests while the plan gained its eighteenth command
  (`portable-bundle-gate`), and the program's own edit added that command
  to the bounded-entrypoint expectations with a `{"tests": [9]}` shape,
  while `portable/gate.py` actually reports
  `portable gate: checks=9 failures=0` (the plan's
  `{"checks": [9], "failures": [0]}` declaration was correct). Every
  normative row failed `matrix-receipt-tests` before producing a receipt;
- `portability/sandbox/expanded_gate.py` pinned the grounded regression at
  `checks_504` and the lint-gate meta suite at `checks_7`; the robustness
  tree's truths are 517 and 9 (hosted-confirmed by robustness-verification
  run `31765740175`, re-measured locally). The hardened sandbox job
  recorded `NORMATIVE_DIVERGENCE` on a suite that itself ran 517/0;
- `portability/verify_receipts.py` replayed the two SHA-pinned
  portability-era gate receipts through the live validator table, so any
  live re-pin would fail sealed historical evidence recorded at 504/7.

Run `31766831866` (`df7a4aa`, the first push-triggered run on the
consolidated `main`) therefore failed 15 normative rows, the sandbox
expanded gate, and the fail-closed summary, while conformance
(`31766831934`) and CodeQL passed. All of it is the pins working as
designed: pinned counts may not drift without a same-change update to
every surface that binds them. Same class as F-MATRIX-013 and F-MATRIX-014.

Resolution: `commands_planned` pins moved to 18 and the
`portable-bundle-gate` expectation asserts the artifact's true
checks/failures shape; the live GateSpec validators moved to `checks_517`
and `checks_9` with the `test_sandbox.py` pins migrated in the same
change; `verify_receipts.py` gains `LEGACY_GATE_VALIDATORS` so sealed
portability-era receipts replay under the validators that governed their
era while live gates enforce the current pins. Verified locally: matrix
suite 48 OK, sandbox suite 77 OK, `verify_receipts` 193/0, `HYGIENE_PASS`
980/2 with custody hashes 12/12, and measured live counts grounded 517/0,
lint-gate-meta 9/0, batch-perf 2160/0, single-pass benchmark 1142/0.
