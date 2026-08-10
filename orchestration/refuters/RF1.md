# RF1 audited-reference refutation

## Verdict

**NO-DEFECT-FOUND.** The F1 candidate implements the key law stated by the
public `derive_record_references` docstring: `record_id` is an ASCII substring
marker, while `exact_reference` is an exact key. The intended decoy-key
differential is reproducible, every independently derived boundary probe
passed, and no unrelated output change was observed.

## Candidate and review base

- Integration base: `4208ced1283bf0fb9c686ad12a52da8cb45197b6`
- P5 test commit supplied for review:
  `df6f7d7d9ce231968264d7203ed6a720f585ae3d`
- P5 commit after unchanged cherry-pick: `79a1eab`
- F1 fix commit supplied for review:
  `d6d1fa95d3caf4e197ed3046215bd6ebd1383098`
- F1 commit after unchanged cherry-pick: `d8596cf`

## Exact diff summary

Relative to the integration base, the combined candidate changes two files:

- `grounded-0_4/test_audit_adversarial.py`: new, 429 lines. It adds bounded,
  deterministic audit-surface tests and a regression proving that keys which
  merely contain `exact_reference` are not references.
- `grounded-0_4/rr_api.py`: one insertion and four deletions. It removes the
  private two-marker tuple and changes the scalar predicate from substring
  matching either marker to `"record_id" in key or key ==
  "exact_reference"`.

No sealed path, dependency declaration, workflow, runtime input, or other
implementation behavior is changed. `git diff --check` passed.

## Evidence

### Independent law derivation and focused probes

The docstring admits two distinct key rules:

1. scalar string leaves are references when the key contains the literal
   ASCII substring `record_id`, or the key is exactly `exact_reference`; and
2. direct string members of arrays whose key ends in `_record_ids` are
   references.

The result is sorted, deduplicated, and capped at 64. An independent inline
probe matrix exercised 976 assertions with zero failures:

- exact `exact_reference` and prefix, suffix, and infix decoys;
- `record_id` at the beginning, middle, and end of keys;
- keys containing only `record` or only `id`;
- a key containing both `record_id` and a decoy `exact_reference` substring,
  which correctly remains governed by the `record_id` rule;
- representative full-width-underscore and Cyrillic-letter Unicode
  confusables, all of which correctly fail ASCII matching;
- nested dict/list mixtures, `_record_ids` arrays, `pool_record_ids`, ignored
  non-string leaves, and ordinary arrays with no qualifying key;
- duplicates, lexical sorting, and cap boundaries at 63, 64, 65, and 256;
- all 720 insertion orders of a six-key profile and 100 repeat executions.

The pre-fix function was emulated from the reviewed parent bytes. Across all
124 frozen and supplemental semantic fixture requests, candidate and pre-fix
`decide_audited` results were byte-identical after JCS serialization. Direct
helper probes showed the only designed difference: each of
`not_exact_reference`, `exact_reference_backup`, and
`not_exact_reference_backup` produced `DECOY` before the fix and no reference
after it. Those values are demonstrable false positives under the docstring's
exact-key clause.

One deliberately malformed nested-special-array shape was also observed:
only direct string members were extracted, while dict/list members were
ignored. That agrees with the docstring's "string items of arrays" scope and
does not affect `decide_audited`, whose frozen schemas reject such member
types.

### Required gates

All commands ran under CPython 3.12.10 on Windows with `python -B`:

| Gate | Result |
|---|---|
| P5 `grounded-0_4/test_audit_adversarial.py` | 6,497 checks, 0 failures |
| P4 `grounded-0_4/test_properties.py` | seed `0x5EED8785`, 2,296 checks, 0 failures |
| P2 `grounded-0_4/test_lint_gate.py` | 7 checks, 0 failures |
| Grounded `grounded-0_4/test_grounded_0_4.py` | 504 checks, 0 failures |
| Lint `grounded-0_4/lint_contract.py --gate` | 0 findings |
| Frozen 0.2 conformance | 800 checks, 0 failures |
| Composed 0.2 + 0.3 conformance | 800 + 107 checks, 0 failures |
| P6 `proof/test_proof_harness.py` | 7 tests, all passed |

The proof test used only the checked-in synthetic corpus; the workspace corpus
extractor was not run.

## Counterevidence sought

I tried to falsify the change by seeking over-rejection (a genuine
`record_id` substring accidentally removed), under-rejection (an
`exact_reference` decoy still admitted), case or Unicode normalization leakage,
container-type leakage, cap off-by-one behavior, nondeterministic ordering,
repeat-run instability, and changes to audited results for schema-valid frozen
requests. None reproduced.

I also reviewed the complete combined diff for hidden scope expansion. The F1
edit is a single Boolean-law correction; P5 is test-only. No performance path
was changed, so the performance-change parity-law trigger is not applicable;
the full conformance and byte-level audited differential nevertheless passed.

## Residual uncertainty

The structural/key corpus is finite rather than exhaustive over every Unicode
code point, and execution covered one supported Python/OS combination. The
probe intentionally treats matching as literal and case-sensitive because
that is the only law stated by the docstring and implemented before the fix.
No uncertainty found is specific enough to constitute a candidate defect.
