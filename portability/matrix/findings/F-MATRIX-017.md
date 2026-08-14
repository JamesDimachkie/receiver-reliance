# F-MATRIX-017 — host-side declared counts and live-coupled historical witnesses

Status: **RESOLVED in the commit carrying this finding; the first green
`main` portability run after it supersedes the red run below.**

Portability run `31768898420` (`ca1ccfe`) reduced the failure surface to a
single job: the hardened Linux sandbox gate. The container itself exited 0
with every internal gate green at the 0.4.1 counts — the F-MATRIX-015
migration of `expanded_gate.py` held. The host harness then rejected the
passing receipt: `commands[2].observed: must equal the declared count
evidence {'checks': 504, 'failures': 0}`. Two further pin surfaces:

- `portability/sandbox/run_sandbox.py` carries `EXPECTED_OBSERVED`, a
  host-side declaration of every gate's counts, independent of the
  container-side validator table. Its `grounded_0_4_regression` and
  `lint_gate_meta` entries still declared 504 and 7; the container
  measured 517 and 9. The F-MATRIX-015 sweep missed it because the
  repo-wide `504` search was read with a truncated result list — a
  process defect recorded here deliberately;
- `portability/sandbox/test_sandbox.py`'s
  `historical_pass_receipt_before_f015()` builds the F-SANDBOX-007..014
  discovery-time witnesses from the **live** `EXPECTED_OBSERVED` table,
  despite its own contract ("preserve the exact discovery-time receipt
  bytes"). Migrating the live table therefore moved seven pinned witness
  digests. The defect is the live coupling, not the digests: the helper
  now freezes the two era-moved gates at their discovery values, which
  restores every pinned digest and byte length and keeps the committed
  finding documents true with no re-pinning.

Resolution verified locally: sandbox suite 77 OK with all witness digests
intact, `verify_receipts` 193/0, `HYGIENE_PASS` 980/2 with custody 12/12 —
and, closing the last hosted-only gap, the exact hardened sandbox job
(`run_sandbox.py`, Docker build + no-network read-only container) executed
locally against the committed tree, expecting the same PASS the hosted job
must produce. Same class as F-MATRIX-013..016; with the host declaration,
container validators, matrix plan, sealed-receipt replay, live schedules,
and envelope auditor all migrated, every known count-pin surface for the
0.4.1 era is covered.
