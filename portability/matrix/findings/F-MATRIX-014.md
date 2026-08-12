# F-MATRIX-014 — branch-migration pins failed closed on the first main run

Status: **RESOLVED in the commit carrying this finding; the first green
`main` portability run after it supersedes the red run below.**

After the side branch was merged to `main` and its ref retired, the
operator approved retargeting the workflow's push trigger from the retired
branch to `main`. Two authority pins deliberately bind that trigger state
and were not migrated in the same commit:

- `portability/matrix/test_receipt.py`
  (`WorkflowDefinitionTests.test_authority_boundary_and_triggers`) pins
  the workflow's exact `on:` block, so every normative row failed
  `matrix-receipt-tests` at its first command;
- `portability/sandbox/run_sandbox.py` (`EXPECTED_BRANCH`) pins the
  branch the sandbox host preflight accepts, so the sandbox job recorded
  `PREFLIGHT_FAILURE: unexpected branch 'main'` and exited nonzero.

Run `31567769263` (`03e8d1d`, the first push-triggered run on `main`)
therefore failed 15 normative rows, the sandbox job, and the summary,
while the conformance workflow passed. Both failures are the pins working
as designed: trigger and branch state may not drift without a same-commit
update to the tests that bind them.

Resolution: both pins now bind `main` — the regex asserts the retargeted
trigger block and `EXPECTED_BRANCH` accepts the consolidated branch. The
authority boundary is otherwise unchanged: read-only permissions,
single-branch push plus `workflow_dispatch` only, and the forbidden
trigger/secrets/cache list stay pinned. No accepted-implementation or
receipt behavior is involved; this is a workflow-authority migration
defect, the same class as F-MATRIX-013.
