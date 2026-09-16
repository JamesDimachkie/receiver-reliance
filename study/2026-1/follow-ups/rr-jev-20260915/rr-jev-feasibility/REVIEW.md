# Independent bounded implementation review

Date: 2026-09-16 UTC (September 15 Pacific).
Reviewer: fresh-context `rr_jev_review` subagent. Implementation author: root.
Scope: local feasibility pilot only. No paid API call, credential access, or modification of the original RR worktree was performed by this reviewer. This review file is the reviewer's only deliverable write.

## Verdict

**PASS for the declared bounded pilot, before semantic outcome collection.** No remaining blocking finding in the reviewed candidate. This is an internal author-separated review, not external human review, independent replication, production assurance, or general RR conformance.

The final qualification result is PASS with **192 receiver configurations and zero failures**: 48 episodes, initial/refreshed states, and both unverified-sender and Jev-shaped fractional-answer fixtures. Three additional falsification controls remain explicit. I independently verified that qualification binds the current study files, RR source files, cases, and request plan. At review time no live POST-attempt log or freeze file existed; root must freeze these reviewed bytes before collection.

## What was verified

- Actual R-all is invoked through the frozen worktree's fresh-process worker, with `observe.verify` checking exact request, construction, and actual engine-call evidence. The source worktree's untracked full-treatment files are included in the hash manifest; a Git commit alone is not used as their identity.
- The conventional comparator parses the same COMMON document and implements independent relational checks. It neither reads R's output nor the gold labels. Its claim is appropriately limited to the pilot's direct-history contract. The retained requested-revision control shows a real C/R difference instead of forcing equality.
- Captured artifact content binds claim, original source digest and revision, intended use, and semantic assessment. Expected source-parent identity comes from the current source; observed parent identity comes from the captured state. A changed artifact retains its old exact-claim declaration until reissue.
- The primary semantic API state contains only claim, source text, and intended use. Gold labels, transition labels, arm, and expected outcomes are absent. The six-family development corpus has 30 distinct requests and no inconsistent gold labels across duplicate requests. The formerly ambiguous integration-test example now explicitly states an integration-test failure.
- Collected sanitized raw service text is retained, hashed, and compared with parsed response data on replay. Qualification binds current source/case/request identities; freeze rejects stale qualification; freeze verification checks the saved qualification file hash.
- Released envelope content is materialized as exact local bytes. Scoring asserts that the presented claim and assessment equal the intended current claim and selected assessment; the presentation hash is retained. This remains policy replay under an honest simulated host.
- HTTP authentication uses the fixed TLS host `api.typesafe.ai`, with no redirect handling or configurable endpoint. The API-key environment entry is removed before RR workers can start. Both model-discovery and POST response bodies use credential-echo sanitization. Each POST has a recorded intent, a 30-second socket timeout, no automatic retry, and fixed attempt/submission-size caps.

## Findings repaired before admission

1. Duplicate purpose identifiers caused RR schema refusal while C accepted. The mandate purpose list is now deduplicated.
2. Raw response bytes were previously only hashed, without storage or replay comparison. Sanitized raw text and replay checks now close that gap.
3. A prior qualification PASS could previously be reused after source changes. Qualification/source/case/request binding and qualification-hash replay checks now close that gap.
4. Initial measurement recorded a release Boolean without an actual presentation artifact. Exact envelope content is now saved and checked.
5. **The original Jev-shaped payload failed actual RR admission because RR artifact JSON forbids floating-point numbers.** The initial qualification covered only no-Jev payloads. The repaired bridge carries the complete answer as JSON text in `answer_json`, within the exact hashed artifact. The outer artifact remains admissible, while Python decodes the original numeric answer for threshold evaluation. I independently exercised ordinary fractional values and scientific-notation probabilities through the actual RR worker: both returned `R_ACCEPTANCE_APPLICABLE`, agreed with C, and round-tripped the original answer exactly. These were explicitly synthetic qualification fixtures, not Jev results.

## Required interpretation limits

The completed 1,805-episode study is unchanged. These are six hand-authored development families and 48 correlated episodes, not held-out data, natural prevalence, or an efficacy trial. Shared bank responses deliberately couple the arms. Logical calls and token totals are replay projections; repeated identical semantic requests on reissue do not represent an optimal semantic cache. The always-recheck arm is diagnostic. A raw weak-cache arm is unnecessary for the current primary comparison and must not be implied. Mutable model aliases limit future inference reproducibility. Source hashes prove identity, not semantic truth, provenance authenticity, or protection against a hostile host.

## Exact reviewed identities

| File | SHA-256 |
|---|---|
| `cases.py` | `58244069A929DE123C0AEBCC48C96EE3CE371FE0652E8FDE55D53D769FCB6F86` |
| `pilot.py` | `183438172781F542F2DF92EBBDFFDBB8275F79063255C80DD296C433B74AAA85` |
| `PROTOCOL.md` | `EABA416EE77C65F499223A3CBEB7ABBFFDEA24FE7C8E096276F064ECB74D29D4` |
| `test_pilot.py` | `99B18673F778D3C5E93102A1F06ED57356FD594806FD361D77A05AAE51625A24` |
| `qualification/result.json` | `79F0DD53AC9ED07ED9AEE03F1B504D84B1637FD5C27F0563040D83A5C4BDFFB4` |

Fingerprint of canonical complete RR source-hash mapping: `61D5BCC642D2C49A853B949DD569FE9D30FAF254E2704F266B3752447C3639AF`. The retrievable individual-file mapping is in `qualification/result.json`, and will be carried into `freeze.json`.
