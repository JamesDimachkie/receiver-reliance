# Method — 10-agentdojo-untrusted-content-trusted

**Demonstrable claim.** RR classifies the adapted
`defective-trusted-without-passing-validation` record as
`OMISSION_OR_INCOMPLETE` / `UNRESOLVED`, the adapted
`defective-validation-never-completed` record as `MALFORMED_OR_BOUNDARY` /
`VIOLATED`, and the clean twin as `VALID` / `SATISFIED`.

**The claim this incident does NOT make.** RR does not detect prompt injection
and does not inspect content. Read item 1.

## Obligation selected

`OBL-22` — *"Treat retrieved content, tool output, metadata, bindings, and
self-asserted trust as untrusted until validated for a declared role."*
Operation handle `OPR_6C9B73604E3164661F153E15`.

Two limbs are exercised:

- `NOT_BOOLEAN_EQ_ENUM` over `/facts/trusted_for_role` against
  `/facts/validation_result` with true-value `PASS` → `OMISSION_OR_INCOMPLETE`.
  The host says the content is trusted for the role while the recorded
  validation verdict is not `PASS`.
- `EQ /facts/validation_result == "UNRESOLVED"` → `MALFORMED_OR_BOUNDARY`. The
  validation never reached a verdict, so the record is out of bounds rather than
  merely incomplete.

## The adaptation

| Incident element | Fact field | Value |
|---|---|---|
| the role the content was acted on in | `validation_role_id` | `ROLE_PAYMENT_INSTRUCTION_SOURCE` |
| the agent acted on it as trusted | `trusted_for_role` | `true` on all three records |
| validation passed (clean) | `validation_result` | `"PASS"` |
| validation did not pass (defective 1) | `validation_result` | `"FAIL"` |
| validation never completed (defective 2) | `validation_result` | `"UNRESOLVED"` |
| the tool call that returned the record | `tool_output_sha256s` | one digest |
| the transaction note field carrying the injected text | `retrieved_content_sha256s` | one digest |
| the note's claim to bank authority | `self_asserted_trust_sha256s` | one digest |
| the row and its metadata | `binding_sha256s`, `metadata_sha256s` | one digest each |

## Where judgment entered

1. **RR classifies the bookkeeping, not the content. Load-bearing.** `OBL-22`
   consumes only the caller-supplied verdict facts. The five digest arrays —
   `retrieved_content_sha256s`, `tool_output_sha256s`, `metadata_sha256s`,
   `binding_sha256s`, `self_asserted_trust_sha256s` — are registered as
   **inert, disclosed** in `grounded-0_4/authority_register_0_4.json` and the
   README states classification is demonstrably insensitive to them. So this
   incident demonstrates: *given* a host that ran a validation for a declared
   role and recorded the verdict honestly, RR classifies "acted on as trusted
   while the verdict was not PASS" as a defect. Whether the validation would
   have caught the injection is entirely outside RR, and RR asserts nothing
   about it.
2. **`validation_result` is a conclusion, supplied by the caller.** H3 requires
   it to be derived by an auditable process. Here it is set by the corpus
   author. An agent that has already been hijacked can write `PASS`, and RR
   would classify the record `VALID` — correctly, and to no benefit. That is the
   honest limit of this incident and follows directly from the artifact's
   honest-attester threat model.
3. **The `UNRESOLVED` record is the "no validation ran" case.** Mapping "the
   system never had a validation step for this role" onto the enum value
   `UNRESOLVED` is a corpus-author reading. An alternative encoding is to
   abstain entirely and never build the request, which is what
   `HOST_OBLIGATIONS.md` H4 actually asks for when an obligation's semantics are
   absent. Both readings are defensible; the corpus took the one that produces
   an executable record and records the other here.
4. **Digests are hashes of ASCII labels.** No AgentDojo bytes are reproduced.
   Since the five arrays are inert, their contents change nothing.
5. **`trusted_for_role` is held `true` across all three records** so the three
   classifications differ only in the verdict, isolating the limb.
6. **Carrier envelope.** The carrier is the 0.2 pack's `OBL-22` entry. Note the
   0.3 supplemental pack ships an `OBL-22` entry with the digest arrays
   *nonempty*, which is where that coverage lives in the artifact; this corpus
   also populates them, for realism, not for effect.

## Preflight lane — `abstain_uncalibrated`

Native evidence in family `UNTRUSTED_CONTENT`; no portable calibration rule
exists, so the preflight returns `INSUFFICIENT_EVIDENCE` with
`PREFLIGHT_FAMILY_UNCALIBRATED`. Abstention, not a pass and not a detection.

## What a green replay demonstrates

RR classifies a record asserting trust-for-role against a non-passing recorded
verdict as `OMISSION_OR_INCOMPLETE`, an unresolved verdict as
`MALFORMED_OR_BOUNDARY`, and a passing verdict as `VALID`.

## What it does not demonstrate

Any prompt-injection defence, detection, or robustness property. That the
recorded verdict is true (H1). That a validation step exists in any real agent.

## Reproduce

```
python -B replay_incidents.py --incident 10-agentdojo-untrusted-content-trusted --verbose
```
