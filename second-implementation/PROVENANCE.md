# Author-separation provenance

This implementation was authored from the public contract/control documents,
schemas, fixture packs, run instructions, and the minimized RI1–RI4 reports.
It was not authored from either frozen implementation's source.

## Read set

- `C:/Users/james/New folder/AGENTS.md`
- `C:/Users/james/New folder/.agent-tasks/TASK-20260811-RR-ROBUSTNESS.json`
- `C:/Users/james/New folder/planning/epistemic-handoff/MASTER_PROMPT_RR_ROBUSTNESS_20260811.md`, section 8
- `orchestration/CRITICISM_ADJUDICATION.md`, Intake 9
- repository public documents: `README.md`, `ACCEPTANCE.md`, `ERRATA.md`,
  `HOST_OBLIGATIONS.md`, `WITHHELD.md`, and `baseline-run/RUNBOOK.md`
- `access/A2_SHARED_DOMAIN_VOCABULARY_BASELINE_PROJECTION_0_1.schema.json`
- `access/SANITIZED_PRIMARY_BASELINE_IMPLEMENTER_PACKET_0_1.json`
- `baseline-run/control/B1_CAPABILITY_MATRIX_0_1.json`
- `baseline-run/control/B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json`
- `baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json`
- `baseline-run/fixtures/B1_WRAPPER_PARITY_FIXTURE_PACK_0_2.json`
- `supplemental-0_3/control/B1_COMPOSED_CAPABILITY_MATRIX_0_3.json`
- `supplemental-0_3/control/B1_SUPPLEMENTAL_COMPARATOR_CONTRACT_0_3.json`
- authority-binding fields only from
  `supplemental-0_3/receipts/SUPPLEMENTAL_FIXTURE_ACCEPTANCE_RECEIPT_0_3.json`
- `supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json`
- `supplemental-0_3/fixtures/B1_SUPPLEMENTAL_WRAPPER_PARITY_FIXTURE_PACK_0_3.json`
- `orchestration/refuters/RI1.md` through `RI4.md`

## Forbidden-source non-exposure

The author did not open or read:

- `baseline-run/implementation-output-0.2/**`
- `baseline-run/implementation-output-0.3/**`
- `grounded-0_4/**`
- any old rejected second-implementation source or worktree
- any other reference implementation source

The frozen composed runner was loaded and invoked only as a black-box execution
target during bounded differential preflight. Runtime symbol names, call
signatures, and public constants were queried to establish a callable target;
no source bytes, source lines, bytecode disassembly, or code-object contents
were displayed or inspected. `coverage_campaign.py` invokes only its CLI entry
point. After F-WP4-002 and F-WP4-005, local `sys.monitoring` branch events
require a fixed set spanning parse, schema, classification, dispatch, and
predicate helpers; receipts expose code-object names and opaque edge identities
solely to prove those steering targets were observed. `bounded_preflight.py`
compares black-box tuples without monitoring or introspection.

## Runtime imports

An AST census over the Python files reports only standard-library imports plus
the local `rr2` and `coverage_campaign` modules. The runtime implementation has no network, clock, randomness,
environment-variable, subprocess, or reference-implementation dependency.
Test and campaign tools use standard-library `subprocess`, `random`, and
`importlib` outside the runtime implementation. Fresh refuter attempts 1 and 2
found six valid defects; their reports and repairs are recorded as
`findings/F-WP4-001.md` through `F-WP4-006.md`. Final author attempt 3 added no
new divergence and did not change the official strike count of 2.

Author attempt 4 repaired `findings/F-WP4-007.md`, a multi-error pointer
selection divergence discovered by the hosted coverage-guided campaign against
the attempt-3 bytes. The attempt-4 author worked from the primary contract's
error-selection clause, the campaign witness, and black-box differential
probes of the frozen composed CLI only; no reference implementation source
was opened, and every probe expectation was pinned from observed black-box
reference output before being written into `test_cross.py`. The strike count
remains 2: the campaign is the custodian's terminal instrument, not a
refuter round.

The runtime reads exactly four authority files. It authenticates the
supplemental contract by the external receipt's raw SHA-256, then derives the
primary-contract, packet, and projection length/SHA-256 pins from those
authenticated bytes. The external receipt supplies no supplemental-contract
byte length, so none is claimed or enforced. A verifier instruments the
runtime load and fails unless the read multiset is exactly those four files.

Custody is a disclosure, not independently provable historical access control.
