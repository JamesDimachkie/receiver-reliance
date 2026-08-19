# Worked example — one handoff, decided end to end

This page walks one concrete reliance decision through the reference
engine: records in, classification out. The three request files in
`examples/` reproduce it byte-exactly. It isolates one of the 30
operations, the single-use-grant check (OBL-26), so the mechanics fit on
a page. A real receiver evaluates every applicable operation, not one.

The boundary stated up front: the engine classifies a structured fact
profile that the caller assembles and supplies. It does not fetch
records, establish provenance, or verify that the facts describe the
world. Those duties stay with the host system ("Who owns what" below,
and "What this does not claim" in the README).

## The scenario

An orchestrator agent finishes its session and hands a worker agent a
package: authority to apply exactly one configuration change, plus the
records describing that authority. The change is identified by the
SHA-256 of its content, so the grant binds to that change and no other.
Before acting, the worker must decide whether the records support the
action.

The worker's host maps the records into the fact profile for the
single-use-grant operation:

| Field | Meaning |
|---|---|
| `grant_not_before`, `grant_expires_at` | Validity window as integer instants. The window is half-open: expiry is exclusive. |
| `invocation_time` | When the worker intends to use the grant. |
| `invocation_nonce` | The single-use token for this invocation. |
| `prior_invocation_nonces` | Every nonce already spent against this grant. |
| `consumption_state` | `UNUSED` or `CONSUMED`, per the handed-over lifecycle records. |
| `revocation_checked_at`, `revoked_at` | When revocation state was last checked, and any recorded revocation. |
| `effect_sha256`, `execution_receipt_effect_sha256` | Hash of the authorized change, and the hash the execution receipt reports. |
| `effect_receipt_count` | How many execution receipts the package carries. |

Integer instants carry whatever clock convention the caller uses. The
engine compares order only.

## Case 1 — every record checks out

`examples/handoff-clean.json` carries this fact profile:

```json
{
  "consumption_state": "UNUSED",
  "effect_receipt_count": 1,
  "effect_sha256": "2699FD9A24F8C15A054D43917ED899BC192760B937AAE059AF05F7B76D1A100C",
  "execution_receipt_effect_sha256": "2699FD9A24F8C15A054D43917ED899BC192760B937AAE059AF05F7B76D1A100C",
  "grant_expires_at": 100,
  "grant_not_before": 0,
  "invocation_nonce": "NONCE_GRANT_0042_USE_1",
  "invocation_time": 50,
  "prior_invocation_nonces": [],
  "revocation_checked_at": 50,
  "revoked_at": null
}
```

The on-disk file is the full request envelope in canonical one-line
form, with this object under `decision_input.facts`. Run it from the
repository root:

```bash
python -B baseline-run/implementation-output-0.2/pcb_runner.py execute < examples/handoff-clean.json
```

The engine returns one canonical line, byte-exact:

```
{"errors":[],"exit_code":0,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":true,"output":{"effect_receipt_sha256":"0FE2186FEF799740549FB09E2DE9C9301224F6AEBA2DA11407A3C6E30B169042","obligation_id":"OBL-26","operation_handle":"OPR_2B12C8F8D4240FDA61CDA198","record_references":[],"result_object":{"behavior_class":"VALID","conclusion":"SATISFIED"},"status":"PASS","unresolved_reasons":[]},"receipt_sha256":"80E1246BD487952B6265AFD78D079F624E83679B95BD0215EF37444928FE0A10","request_id":"RUN_79C6159D70C325864718621F","result":"PASS"}
```

`VALID` / `SATISFIED`, exit code 0. The invocation falls inside the
window and the nonce is fresh. Revocation was checked with none
recorded, and the execution receipt matches the authorized change hash.
The response seals the decision (`receipt_sha256`) and the matched
effect (`effect_receipt_sha256`).

## Case 2 — nobody checked revocation

`examples/handoff-unchecked-revocation.json` changes one field from
case 1: `revocation_checked_at` is `null`. Nothing in the package proves
anyone consulted the revocation state before use.

```
{"errors":[],"exit_code":1,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":true,"output":{"effect_receipt_sha256":null,"obligation_id":"OBL-26","operation_handle":"OPR_2B12C8F8D4240FDA61CDA198","record_references":[],"result_object":{"behavior_class":"BINDING_OR_CONFLICT","conclusion":"VIOLATED"},"status":"FAIL","unresolved_reasons":[]},"receipt_sha256":"243BD3DCAB343EC19E0969C21F9C40CD8FF44FF46C8E576E57F336B36C9BB4BF","request_id":"RUN_C7E09F7DD66624252460E2FD","result":"FAIL"}
```

`BINDING_OR_CONFLICT` / `VIOLATED`, exit code 1. Checking revocation
before use is part of the law for this operation. Even with no
revocation recorded, an unchecked grant is not usable. The host refuses,
or repairs the gap: check the revocation state, rebuild the profile,
evaluate again.

## Case 3 — the records contradict each other

`examples/handoff-inconsistent.json` changes one field from case 1:
`consumption_state` is `CONSUMED`. The package now claims the single-use
grant was already spent, while `prior_invocation_nonces` records no
prior use.

```
{"errors":[],"exit_code":1,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":true,"output":{"effect_receipt_sha256":null,"obligation_id":"OBL-26","operation_handle":"OPR_2B12C8F8D4240FDA61CDA198","record_references":[],"result_object":{"behavior_class":"OMISSION_OR_INCOMPLETE","conclusion":"UNRESOLVED"},"status":"FAIL","unresolved_reasons":["OBL-26: authoritative semantic basis is absent or inconsistent"]},"receipt_sha256":"FD85B00CD22573D269E7C23A5D24EF66FF807177D79BCA1DD1EF4E75E6963CE9","request_id":"RUN_4F5C2C4E04DB160D8E03DBF6","result":"FAIL"}
```

`OMISSION_OR_INCOMPLETE` / `UNRESOLVED`, exit code 1, with the reason
`OBL-26: authoritative semantic basis is absent or inconsistent`. The
records cannot all be right, and the engine refuses to guess which one
is wrong. This is the deliberate third outcome: a contradictory or
absent basis terminates as `UNRESOLVED`, never as a silent pass and
never as an arbitrary pick. The host asks the sender for the missing
record, or fetches it, and evaluates again.

## Reading a classification

| `result_object` | Exit code | What the host typically does |
|---|---|---|
| `VALID` / `SATISFIED` | 0 | Proceed with the action the profile describes. |
| `MALFORMED_OR_BOUNDARY` or `BINDING_OR_CONFLICT` / `VIOLATED` | 1 | Refuse, or repair the named defect and re-evaluate. |
| `OMISSION_OR_INCOMPLETE` / `UNRESOLVED` | 1 | Ask the sender or fetch the missing basis, then re-evaluate. |
| `INCOMPLETE` (protocol error — the request never reached classification) | 2 | Fix the request; nothing was judged. |
| `INCOMPLETE` (`ERR_INTERNAL`) | 3 | Report it; the engine refused rather than guessed. |

The proceed / refuse / ask policy belongs to the host. The engine
classifies and seals. It never acts.

## Who owns what

| Layer | Responsibility |
|---|---|
| Host system | Retrieve records, establish provenance and authenticity, assemble the fact profile, enforce the resulting decision, run any clarification dialogue. |
| This engine | Deterministically classify the supplied profile against the frozen decision table, select errors under the frozen precedence law, seal the response. |
| Not claimed | That supplied facts describe the world. Efficacy, security, novelty, interoperability (README, "What this does not claim"). |
| Composes with | Identity and session establishment, transparency logs and receipts, authorization policy, effect enforcement (README, "Where this sits among adjacent systems"). |

## Reproduce

The three requests are canonical RFC 8785 JCS bytes with a trailing LF,
as the wire contract requires. Expected responses, byte-exact:

| Request | Response SHA-256 |
|---|---|
| `examples/handoff-clean.json` | `0ED564514A2A2D8F7CCFBDC1A50EA12DB32AB5EB96F865D33C3A9AB8490020AC` |
| `examples/handoff-unchecked-revocation.json` | `39BD0885E84EBC41BE164C7FE5998D4322B5F44B8B01A9871236CBC5F51E4CF4` |
| `examples/handoff-inconsistent.json` | `8BC2F92E35C51B1D75B30C8AD08FF66E45B8F8E755F7BE0F1E68DDFA6633ADBF` |

The composed 0.3 runner returns the same bytes for these requests:

```bash
python -B baseline-run/implementation-output-0.3/pcb_runner.py execute < examples/handoff-clean.json
```

Response bytes for all three cases are identical on CPython 3.12.10 and
3.14.5. The release's cross-interpreter determinism record is in
`ACCEPTANCE.md`, "v1.1 — cross-interpreter determinism correction". To
build requests of your own, start from any fixture entry
(`baseline-run/RUNBOOK.md`, "Run one request by hand"). The envelope
binds `inner_request` by hash. If you edit `inner_request`, recompute
`inner_request_raw_sha256` and `inner_input_sha256`. Editing only
`decision_input.facts` requires no hash changes.
