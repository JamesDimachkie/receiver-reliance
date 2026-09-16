# RR + Jev feasibility results

Status: completed exploratory pilot; not confirmatory evidence of field value.

**Adding Jev helped on these fixtures. RR did not outperform the equally informed conventional policy.** With either policy, Jev eliminated all 12 unsupported/contradicted releases while retaining all 30 supported, permitted claims. The policies agreed on every episode, both with and without Jev. This is evidence of a working integration and a useful semantic check on simple examples, not evidence of incremental RR value.

48 synthetic handoff episodes from six source families; 30 actual Jev calls shared across arms.

| Arm | Released | Bad semantic releases | Revocation violations | Useful claims withheld | Logical semantic checks |
|---|---:|---:|---:|---:|---:|
| conventional_without_jev | 42 | 12 | 0 | 0 | 0 |
| rr_without_jev | 42 | 12 | 0 | 0 | 0 |
| conventional_with_jev | 30 | 0 | 0 | 0 | 84 |
| rr_with_jev | 30 | 0 | 0 | 0 | 84 |
| conventional_always_recheck | 30 | 0 | 0 | 0 | 90 |

Jev label accuracy: 30/30 unique development questions. Reported input tokens: 14,521; estimated token charge $0.000610 at $0.042/million input tokens (not an invoice). Observed service median 0.227s; max 0.284s.

## Interpretation

The model returned `jev-1.13.0` for every call requested under `jev-latest`. Model discovery exposed aliases only; the returned identifier is a provenance record, not a verified immutable endpoint we can request later.

The 48 episodes included 30 supported/permitted cases, 12 contradicted or unsupported cases, and six revoked assessments. Jev matched all 30 unique author-labeled questions (18 supports, nine contradicts, three insufficient). These easy, synthetic questions are too few and too correlated to establish calibration, reliability on unfamiliar data, or frontier-level performance.

RR and conventional checking both used 84 logical semantic checks versus 90 for always-recheck. The six avoided checks occurred only when nothing changed. This saving belongs equally to both policies; it is not an RR advantage. Logical checks reuse one recorded response bank and are not 84 separately measured service calls. Revision/expiry reissues deliberately trigger checks even when their semantic request is identical, so these policies are not optimal caches.

Without Jev, both policies released the 12 semantically bad claims after a structurally valid reissue. RR verifies the supplied relationships; it does not establish that a source supports a claim. Jev supplies that separate, fallible judgment.

Qualification also retained counterexamples: changing source text alone or an observed-purpose field without changing the checked binding did not cause RR to reject. A requested-revision-only mismatch was rejected by the conventional policy but passed RR. These are limits of the invoked bridge's checks, not evidence of general security efficacy. The pilot therefore explicitly bound source bytes/revision into parent identities and current use into the declaration.

## Verification

Five failure-oriented local tests passed. Final qualification passed 192 configurations with and without fractional Jev-shaped answers, plus three falsification controls. An author-separated reviewer verified the repaired integration before the freeze and API collection. The post-run audit reverified 168 actual RR invocation receipts, 240 policy rows, all 174 materialized presented artifacts, raw response hashes, token accounting, and unchanged frozen source bytes. Credential scan found zero copies of the live key in the pilot outputs. See `results/verification.json` and `REVIEW.md`.

Some earlier qualification traces remain as development history; only `qualification/result.json` and its `_plain_`/`_jev_` trace configurations describe the final hash-bound qualification.

## What would demonstrate more value

A next study should use independently adjudicated, held-out handoffs with changing evidence and realistic ambiguity. Give RR and a competent conventional system the same Jev checks, source access, reissue authority, and repair budget. Measure unsupported presentations, supported work completed, review burden, actual service cost, and implementation/maintenance effort. Keep policy tuning separate from the final test set. A measured engineering or auditability advantage could matter even if receiving decisions remain tied; neither was measured here.

The completed published RR study remains unchanged. This pilot is a separate feasibility result, and the next study described above has not been run.

## Limits

- Hand-authored development fixtures; six correlated families, not held-out evidence or field prevalence
- Identical bank responses coupled across arms; logical token costs are replay projections, not separately billed workflows
- Actual RR invoked; comparator implements only declared pilot contract; honest simulated host
- No generated semantic repairs or human-review outcomes; no engineering-effort comparison
- Model alias can change; stored-response replay reproducible, future inference not guaranteed identical

See PROTOCOL.md, freeze.json, qualification/result.json, live/ and results/ for exact definitions and receipts.
