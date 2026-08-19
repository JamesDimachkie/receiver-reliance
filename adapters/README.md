# Portable preflight fallback

WP1 reached its three-strike boundary in F-WP1-009. The shipping fallback is
therefore narrow: a calibration playbook and a stdlib-only preflight for
native evidence and optional host-produced fact profiles. It is not a general
host adapter, runner, transcript verifier, replay store, or effect API.

The versioned result taxonomy has exactly three values:

| status | meaning | accounting |
|---|---|---|
| `READY` | the bounded rule found sufficient, noncontradictory native evidence; an optional profile agrees with it | eligibility only; not a pass or engine decision |
| `REJECTED_INVALID` | evidence or profile assertions are malformed or contradictory | detection; never a pass |
| `INSUFFICIENT_EVIDENCE` | required host semantics are unavailable | abstention; never a pass |

[DIAGRAMS.md](../DIAGRAMS.md#a4--the-preflight-and-the-calibration-cliff)
draws why the status is not an early-exit chain and why `READY` is
unreachable for an uncalibrated family.

Python use is deliberately small:

```python
from adapters import READY, preflight

result = preflight(native_record, optional_host_fact_profile)
if result.status != READY:
    record_preflight_result(result.as_dict())
    do_not_invoke_engine()
```

`READY` does not authorize invocation by itself. The integration still owns
atomic state observation, profile construction, engine request binding,
runner custody, replay, transcripts, and effects under H1–H6.

## Portable JSONL CLI

The CLI reads stdin and writes stdout by default, uses no embedded absolute
path, and does not interpret evidence paths through the local operating
system:

```text
python -B adapters/portable_preflight.py < records.jsonl > results.jsonl
```

Each input row is either a native record or a closed wrapper with `record` and
optional `fact_profile`. The CLI exits 0 only when every emitted result is
`READY`; otherwise it exits 2 after emitting every result. `--input` and
`--output` accept caller-supplied paths when redirection is inconvenient.

The optional `RR-PORTABLE-FACT-PROFILE-1` envelope contains exactly:
`format_version`, `record_id`, `obligation_id`,
`native_evidence_sha256`, `facts`, `derivations`, and `fabricated_fields`.
Preflight checks its record/evidence binding, closed facts, calibrated
field-level evidence pointers, and requires `fabricated_fields` to be empty.
It validates a host-produced profile but never constructs one for the host.

## Bounded measured mappings

The current rules cover the four native-record corpus families: `REF` /
OBL-02, `SCOPE` / OBL-03, `SUPERSEDE` / OBL-15, and `LIFECYCLE` / OBL-17.
Paths remain opaque, case-sensitive evidence strings; there is no drive,
separator, current-directory, filesystem, or shell interpretation.

On the raw-SHA-pinned all-408 corpus, native structure alone yields 192
`READY`, 8 `REJECTED_INVALID`, and 208 `INSUFFICIENT_EVIDENCE`. The invalid
set is exactly five stale REF alias/path contradictions plus three
equal/non-increasing lifecycle timestamp contradictions. The insufficient set
is exactly the 208 noncontradictory lifecycle rows whose timestamps do not
establish typed acknowledgment semantics.

The bounded offline receipt reports 0 new false holds and 18/18 detection:
8/18 are preflight invalid detections and 10/18 are detected by the accepted
core after `READY`. The latter replay uses explicitly non-shipping mutable
measurement machinery and does not widen the fallback API.

Run the portable suite with
`python -B adapters/test_portable_preflight.py`. Reproduce provenance and the
all-408 receipt with `python -B adapters/fixture_extract.py --check` and
`python -B adapters/outcome_receipt.py --check`.

Current-byte local evidence covers CPython 3.12, 3.13, and 3.14
(`RUNTIME_EVIDENCE.md`, re-pinned 2026-08-13). The recorded runs meet the
requested 3.12–3.14 evidence bar. Package completion beyond the delivered
fallback is still not claimed.

## One consumer of it, in this tree

[`mcp/`](mcp/README.md) is a stdio MCP server that runs this preflight and then
`receiver_reliance.decide_audited` over records an agent received from a tool
call. It is a **consumer** of the fallback above, not a widening of it: it adds
no fourth status, re-derives none of these rules, and its own verdict vocabulary
restates a preflight status or an audited class with the underlying value
reported beside it. The three-status law on this page governs there unchanged.

It is also the first surface in this repository built for a consumer outside it,
which is a posture question before it is a code question:
[TRUST_MODEL.md](../TRUST_MODEL.md) and [ADOPTION.md](../ADOPTION.md) record what
the first external consumer promotes to blocking work, and `mcp/README.md`
restates that trigger where a host wiring the server will read it.
