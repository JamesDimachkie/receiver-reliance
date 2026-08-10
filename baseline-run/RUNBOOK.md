# B1 primary-baseline conformance suite — runbook

This directory is a self-contained, deterministic conformance suite and
reference implementation for a "receiver-local reliance decision"
baseline — a 28-operation accepted core composed with a 2-operation
supplemental generation, 30 operations in all: given structured facts
about records exchanged at an agent-to-agent handoff (provenance,
versions, scopes, grants, lifecycle events, effect receipts, clarification
triage, candidate selection), each operation deterministically classifies
the situation as `VALID`, `MALFORMED_OR_BOUNDARY`, `BINDING_OR_CONFLICT`,
or `OMISSION_OR_INCOMPLETE` and emits a byte-reproducible, digest-sealed
response.

Everything is frozen and digest-pinned: the decision rules live in a
machine-readable predicate table inside the implementer contract, the
fixtures pin exact request and response bytes, fixture packs, receipts,
and responses carry self-zero SHA-256 seals, and the contract and
implementation sources are pinned by raw SHA-256 in the manifest and
receipts. Two independent surfaces exist so they can check each other:
the fixture packs (what correct behavior is) and the reference
implementation (one program that produces it).

## Layout

| Path | What it is |
|---|---|
| `control/B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json` | The frozen contract: schemas, error model, predicate decision table (28 operations x 4 classes), effect-receipt rules, seal rules. |
| `control/B1_CAPABILITY_MATRIX_0_1.json` | The 28-row capability matrix the contract realizes. |
| `fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json` | 112 byte-exact semantic request/response pairs (28 operations x 4 classes) plus 370 competence mutation cases. |
| `fixtures/B1_WRAPPER_PARITY_FIXTURE_PACK_0_2.json` | 112 wrapper pairs / 224 arms (B1 vs B1-ATTENTION), transcripts, 10 negative cases, 4 metamorphic cases. |
| `receipts/PRIMARY_BASELINE_FIXTURE_ACCEPTANCE_RECEIPT_0_2.json` | Independent acceptance receipt for the fixture packs (sealed; carries per-section entry, arm, pair, and class counts). |
| `implementation-output-0.2/` | Reference implementation (`implementation-output-0.2/pcb_runner.py` + `implementation-output-0.2/b1_capabilities.py`), conformance harness, manifest, and receipts. |
| `implementation-output-0.3/` | Composed reference implementation covering all 30 operations (28 accepted + 2 supplemental), its conformance harness (runs BOTH suites), manifest, and receipts. Built by a separate lane; see `../ACCEPTANCE.md`. |
| `../supplemental-0_3/control/` | The supplemental 0.3 contract (two decision-table rows, composed 30-operation schemas, versioned wrapper interface) and the composed 30-row capability matrix. |
| `../supplemental-0_3/fixtures/` | Supplemental sealed packs: 12 semantic entries + 53 competence cases; 12 wrapper pairs / 24 arms + 10 negatives + 8 metamorphic cases across five named families. |
| `../supplemental-0_3/receipts/` | Independent acceptance receipt for the supplemental packs (PASS, round 2). |
| `../supplemental-0_3/` | Prior-art snapshot (the pinned completeness basis), predicate-vocabulary inventory, floor-count register, and the candidate-blind completeness verdict. |
| `toolchain/` | NOT distributed in this release. Pinned offline CPython 3.12.4 (Windows embeddable) used for the sealed ABI runs — reproduce it per "Sealed ABI mode" below. |

Not included in this release: the research program's source components,
its integration notes, the superseded 0.1-generation artifacts, and the
pinned toolchain binaries (reproduction documented below). Everything the
conformance suites need, except the optional toolchain, is present in this
tree.

## Run it

Any CPython 3.12 works for the in-process mode. The pinned toolchain is only
needed to reproduce the sealed subprocess-ABI mode. From this directory:

```bash
python -B implementation-output-0.2/run_conformance_0_2.py
```

Expected output: `mode=in-process counts={"semantic": 112, "competence": 370,
"wrapper_arms": 224, "negative": 10, "metamorphic": 4, "error_law": 80}
failures=0` and exit code 0. (`error_law` is the harness's own
deterministic closure: 57 parse-layer/limit/canonicality cases (including the
three deep-nesting schema-vs-limit determinism closures added in v1.1), 19
fixture-derived joint-pool, class-precedence, and family/output-cap
cases, and 4 transcript-evaluator strictness guards; it lives in the
harness, not the fixture packs.)

The composed runner covers all 30 operations and runs both suites:

```bash
python -B implementation-output-0.3/run_conformance_0_3.py --suite all
```

Expected output: two lines — `mode=in-process suite=0.2 ... total=800
failures=0` (byte-identical behavior to the 0.2 runner across the accepted
surface) and `mode=in-process suite=0.3 counts={"competence": 53,
"metamorphic": 8, "negative": 10, "semantic": 12, "wrapper_arms": 24}
total=107 failures=0` — exit code 0. `--suite 0.2` or `--suite 0.3` runs
one suite; `--subprocess` selects the sealed ABI mode (toolchain required,
below).

Sealed ABI mode (each case runs as a separate process through the pinned
interpreter, byte-exact stdin/stdout) requires the pinned toolchain at
`toolchain/python.exe` in this directory. It is not distributed with this
release. Reproduce it first:

1. Download the official CPython 3.12.4 Windows embeddable zip,
   `https://www.python.org/ftp/python/3.12.4/python-3.12.4-embed-amd64.zip`,
   and verify its SHA-256 is
   `15fea3c9367653a85086fe37216b4d1a1c78688fa5e1587e1db0b0f658856564`.
2. Unzip it to `toolchain/` (so `toolchain/python.exe` exists) and leave
   `toolchain/python312._pth` stock — site imports stay disabled.

The sealed mode is Windows-specific (the pinned interpreter is the Windows
embeddable build). The in-process mode is portable to any CPython 3.12.

```bash
python -B implementation-output-0.2/run_conformance_0_2.py --subprocess
```

Regenerating the implementation manifests and receipts requires the
toolchain provenance manifest (`toolchain/TOOLCHAIN_MANIFEST_0_1.json`),
which is NOT distributed in this release — it carries machine-path
provisioning evidence. The contract pins its path, byte length, and raw
digest under `toolchain_manifest_tree_reference`, so a future release of
it is verifiable. Without the provenance manifest, BOTH emitters exit with
an error
(`implementation-output-0.2/emit_manifest_0_2.py` with `FileNotFoundError`;
`implementation-output-0.3/emit_manifest_0_3.py` reporting the missing
manifest); nothing else in this tree needs the
manifest. Both conformance runners run without the provenance manifest in
both modes; the sealed ABI mode still requires `toolchain/python.exe`. With
the full toolchain provenance present:

```bash
python -B implementation-output-0.2/emit_manifest_0_2.py
```

## Run one request by hand

Every fixture entry carries its exact request bytes. To execute one:

```bash
python -B - <<'EOF'
import base64, json, subprocess
pack = json.load(open("fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json", encoding="utf-8"))
entry = pack["entries"][0]
raw = base64.b64decode(entry["semantic_request_jcs_lf_base64"])
proc = subprocess.run(["python", "-I", "-B", "implementation-output-0.2/pcb_runner.py", "execute"],
                      input=raw, capture_output=True)
print(proc.stdout.decode())
print("byte-exact:", proc.stdout == base64.b64decode(entry["expected_response_jcs_lf_base64"]))
EOF
```

## Reading a fixture entry

- The verdict class of a response lives at
  `expected_response.output.result_object.behavior_class` (semantic core) or
  `output.payload.behavior_class` (wrapper responses).
- Entry-id suffixes encode the fixture class assertion: `IO` = INPUT_OUTPUT
  (expects `VALID`), `INV` = INVARIANT (`MALFORMED_OR_BOUNDARY`), `CTRL` =
  POLICY_PERMITTED_CONTROL (`BINDING_OR_CONFLICT`), `FAIL` = FAILURE
  (`OMISSION_OR_INCOMPLETE`). The authoritative mapping is
  `semantic_decision_contract.fixture_author_generation_contract` in the
  contract. These labels are assertions about the fixture, never inputs to
  classification.
- `first_match_predicates` records the raw truth value of each non-VALID
  class predicate; more than one can be true at once, and the response class
  is decided by the frozen precedence order (`MALFORMED_OR_BOUNDARY`, then
  `BINDING_OR_CONFLICT`, then `OMISSION_OR_INCOMPLETE`), not by this field.

## How a decision is made

1. The request is parsed under a strict deterministic profile (UTF-8, no
   BOM/CR, no duplicate keys, no floats, NFC strings, RFC 8785 JCS canonical
   bytes, safe-integer range, size/nesting limits).
2. The envelope is schema-validated and digest-bound: the inner request and
   its input are re-hashed and must match the declared digests; operation,
   obligation, and request identifiers must be mutually consistent.
3. The operation's class predicates from the contract's decision table are
   evaluated over `decision_input` only, in frozen precedence order
   (`MALFORMED_OR_BOUNDARY`, then `BINDING_OR_CONFLICT`, then
   `OMISSION_OR_INCOMPLETE`); first match wins, otherwise `VALID`.
   Labels, provenance strings, and fixture identifiers are never inputs to
   classification — the competence cases mutate exactly those to prove it.
4. The response is constructed deterministically (fixed field set, exact
   unresolved-reason string, effect receipt for four effect-bound operations)
   and sealed with a self-zero SHA-256.

## What this does and does not claim

- It claims: the reference implementations reproduce the accepted fixture
  packs byte-for-byte (720 fixture-pinned checks in the 0.2 generation
  plus the supplemental 0.3 packs, two execution modes each), and the
  packs carry independent acceptance receipts.
- It does not claim: efficacy, novelty, security, interoperability, or
  conformance to any external standard or cited system. The suites test
  conformance to THESE contracts only.
- The comparator surface is composed: the accepted 28-operation semantic
  core plus the supplemental 0.3 generation that closed its two reviewed
  capability gaps (selective clarification, OBL-29; intent-compatible
  selection, OBL-30), ruled complete by a candidate-blind review against
  the pinned prior-art snapshot. `clarification_state` is bound to the
  clarification row's semantic facts in the 0.3 wrapper fixtures
  (`REQUESTED`/`RESOLVED` covered there) and remains `NONE` throughout
  the accepted 0.2 arms; it carries no classification authority anywhere.
