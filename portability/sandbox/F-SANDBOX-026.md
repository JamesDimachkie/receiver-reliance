# F-SANDBOX-026 — sandbox host preflight fails closed on shallow hosted checkouts

Status: **RESOLVED; confirmed by the green hosted runs** — portability
run 31562391384 (`7facfa3`) and the close-push run 31564942933
(`55297bb`) passed every job containing this regression.

The first authorized hosted run (workflow run 31548278804, pushed SHA
`4c9250a75e29e46275aa0d99902d49023e97ef15`) failed the
"hardened Linux sandbox • expanded gate" job in about 200 ms with the durable
host receipt `{"detail": "git preflight failed", "schema":
"receiver-reliance/sandbox-host-receipt-1", "status": "PREFLIGHT_FAILURE",
"treatment_exposed": true}` before any Docker interaction.

Root cause, reproduced locally in a `git clone --depth 1` checkout of the
pushed branch: `run_sandbox.py:_git_receipt` verifies baseline ancestry with
`git merge-base --is-ancestor 4e788d21e882a30bdda2aec3f780537161f81644 HEAD`.
`actions/checkout` defaults to a depth-1 clone, the baseline commit is absent
from shallow history, and `merge-base` exits 128 (`Not a valid commit name`),
outside the accepted `{0, 1}` set. Every other preflight command succeeds in
that environment.

The preflight behaved correctly: it failed closed on an environment in which
baseline ancestry could not be verified, and it did not misclassify the
condition as `INFRA_UNAVAILABLE` or PASS. The defect is the workflow wiring
that starved it of history. The correction sets `fetch-depth: 0` on the
sandbox job's checkout step only, preserving the strong ancestor binding
rather than weakening the check to tolerate shallow history.

Regression pin: `matrix/test_receipt.py`
`WorkflowDefinitionTests.test_sandbox_checkout_fetches_full_history` requires
the sandbox job's checkout step to declare `fetch-depth: 0`.
