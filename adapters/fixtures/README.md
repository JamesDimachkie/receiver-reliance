# WP1 outcome fixtures

`parent_corpus_408.jsonl` and `parent_truth_408.jsonl` are byte-exact snapshots
of the 2026-08-10 native-record proof inputs:

- corpus: `09B4B05FE26CF46F063EC637C1A4D27B4D5190961756888099F96254C49B334E`
- truth: `4FEEF9BE65DD7523849CEE71B5A43EA6F7667710745E71D79C0EE5B054E3E2C7`

Each corpus row remains raw `{record_id,family,native,observations}` data; truth
is separate. `fixture_extract.py` validates all 408 record identities and
raw-row digests, joins truth by `record_id`, and proves that the two E7 files
are the exact row-ordered 211-record `LIFECYCLE` subset.

The parent lifecycle schema contains only
`observations.lifecycle_event_timestamps`. It does **not** contain typed
acknowledgment evidence. Portable preflight checks contradiction before
applicability: three equal/non-increasing rows are `REJECTED_INVALID`, while
the 208 noncontradictory untyped rows are `INSUFFICIENT_EVIDENCE`. The fixture
bytes are not rewritten or enriched. Typed lifecycle rows in unit tests are
synthetic preflight-contract cases, not outcome evidence.
