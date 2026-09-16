# Independent pre-inference implementation review

Date: 2026-09-16 UTC (September 15 Pacific).
Reviewer: `vitc_review`, separate from the implementation author.
Scope: the bounded local VitaminC follow-up in `PROTOCOL.md`.

## Verdict

**PASS for collection under the declared protocol.** No blocking implementation
finding remains in the reviewed snapshot. At review time, neither `freeze.json`
nor `live/attempts.jsonl` existed. Freeze these reviewed bytes, this review, and
the matching qualification receipt before inference. Preserve the single-writer
freeze during collection. This is an internal author-separated review, not
external replication, a semantic outcome, or general RR conformance certification.

The reviewer made no API requests, accessed no credentials, changed no source
files, and ran no new RR subprocesses. This file is the sole reviewer write.

## Independent checks

- Recomputed the SHA-256 of the source `test.jsonl` and independently reconstructed
  sampling from its real-revision groups. The saved selection matches exactly:
  120 pairs, 120 distinct pages, 60 SUPPORTS/REFUTES pairs and 60 SUPPORTS/NOT ENOUGH
  INFO pairs, with the prescribed eligibility rules, hash ordering and page cap.
- Reconstructed every request from the selected rows and the unchanged pilot
  question. The saved shuffled plan matches exactly: 240 unique requests and
  259,220 submitted JSON bytes. Request state has exactly `claim`, `source_text`
  and `intended_use`; no benchmark metadata, labels, identifiers, canary, or
  transition fields are added. Naturally occurring text inside a claim or
  passage is preserved.
- Reconstructed all 480 episode states and labels. Both changed directions use
  current source revision 2; unchanged directions retain revision 1. The four
  episodes per page remain correlated workflow replays, not independent samples.
- Checked 960 initial/refreshed COMMON constructions offline. The conventional
  policy rejects changed parents before reissue and accepts the refreshed
  direct-mandate documents. Fractional Jev-shaped answers round-trip exactly
  through `answer_json`. This check used synthetic responses, not model outcomes.
- Independently verified all 32 saved actual-RR invocation receipts with the
  observer, without rerunning qualification. Every receipt agrees with its saved
  observation and expected structural outcome. Qualification binds the current
  study files and current complete RR source-hash mapping.
- Reviewed the common bridge and comparator. Both primary arms receive the same
  constructed document and coupled response bank, with one refresh opportunity.
  The conventional checker neither reads an RR decision nor uses benchmark labels.
  RR is the actual engine through the existing fresh-process invocation path.
- Reviewed exact-presentation checks: a released artifact must bind the current
  claim, source digest, revision, purpose and current semantic assessment. The
  actual presented bytes and their digest are retained.
- Reviewed scoring: three-way labels, confusion counts, both-correct pairs,
  support-probability differences, fixed threshold diagnostics, and primary
  policy mismatches use the correct current labels. Primary negative-release
  and supported-withheld rates each use 120 examples, one per page, and Wilson
  intervals. Repeated workflow totals are kept separate from those rates.
- Reviewed collection and replay: fixed TLS host, no redirect handling or
  automatic retry, recorded intent before each POST, 240-attempt/1,000,000-byte
  caps, 30-second socket timeout, 2 MB response cap, and stop-on-service-error
  behavior. The API-key environment entry is removed before RR workers; raw
  response text is sanitized for an exact credential echo before persistence.
  Replay checks expected attempts, requests, raw-response hashes, parsed answers
  and service response validity. Missing or invalid responses cannot become a
  complete empirical report.

## Interpretation requirements

The negative-release rate is relative to the frozen benchmark labels. A confident
release against a negative label disproves perfect agreement with those labels;
calling an example an unequivocal semantic failure additionally requires inspecting
its exact claim and evidence. Annotation ambiguity must be reported without
changing the original score or replacing the example.

This design changes only source parents inside an honest, simulated,
direct-mandate workflow. A primary-policy tie establishes no incremental RR
benefit in that contract; it cannot establish broad equivalence or field utility.
The stale-cache diagnostic is deliberately incomplete and cannot establish an
RR-specific advantage. Training contamination and future alias behavior remain
unknown. The sample's balanced composition is not deployment prevalence. Timing
and logical checks are harness measurements and replay accounting, not a fair
implementation-cost comparison.

No empirical result was available or reviewed. Full collection, recorded-response
analysis, exact-example inspection and the final evidence audit remain required.

## Exact reviewed identities

| File | SHA-256 |
|---|---|
| `PROTOCOL.md` | `684CA1FCEABCECDAC3F22D585F0A619249D926DBC2551EB62619BCECE6DC463F` |
| `study.py` | `923B9207D95533121B5893526D212AEE0A2A1A3EEBC512B8FF1346A16AC97A49` |
| `selected.json` | `AE42C0F38FF239268C29F0E627C819CC68467852F7CA36BB7A9636E614CB4CA3` |
| `episodes.json` | `2614FE7EAB25DA01020A827BC53FBFE04789A37EF6D35480272D32567CB59D2A` |
| `request-plan.json` | `66A409F1F047F73F6759E859BAF74FFD50D00C8B0BD44754E1F066DB71145A8E` |
| `LICENSE-DATA.txt` | `E5727854E203FC66D725CAA6D8E97E541F64A906D1D15D19E63F32BB52134DD1` |
| `qualification/result.json` | `67023D9ED06FA2031107D63927C46AEC98BC01B989BEFFCE20D2174043FCBC67` |
| `../rr-jev-feasibility/pilot.py` | `183438172781F542F2DF92EBBDFFDBB8275F79063255C80DD296C433B74AAA85` |
| `../rr-jev-feasibility/cases.py` | `58244069A929DE123C0AEBCC48C96EE3CE371FE0652E8FDE55D53D769FCB6F86` |
| `../rr-jev-feasibility/freeze.json` | `02B13382A7F9CEB24B0CF2B3F5535D354C40A88200D03F13619969213808B66D` |

Source dataset SHA-256:
`7ad1808dbc30c62e0a1427a53022d0dfaff668a1fde3c4b612a2d266edd753ad`.
Fingerprint of the canonical complete RR source-hash mapping:
`61D5BCC642D2C49A853B949DD569FE9D30FAF254E2704F266B3752447C3639AF`.
The retrievable per-file mapping is in `qualification/result.json`.
