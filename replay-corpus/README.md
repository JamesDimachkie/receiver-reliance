# Incident replay corpus

Twelve publicly documented agent-system failures, each adapted into
receiver-reliance fact profiles and replayed through the real portable preflight
and the real audited decision API. Every incident ships at least one defective
record and a clean twin; the runner replays all of them from the exact bytes on
disk and compares against pinned expectations.

**The one claim this corpus makes: RR classifies this adapted record as
`<class>`.** No incident claims RR would have prevented, stopped, detected, or
altered its source event. Nothing here is evidence of efficacy, security,
novelty or interoperability, and this corpus does not extend the artifact's
claims — see [TRUST_MODEL.md](../TRUST_MODEL.md), which governs. The reason each
class comes out the way it does is a property of the frozen decision tables, not
of the incident.

## Run

From the repository root:

```bash
python -B replay-corpus/replay_incidents.py
```

```text
replay-incidents: incidents=12 executable=12 checks=27 holds=15 clean_pass=12 failures=0
```

Exit 0 only when every pinned expectation holds. `--incident NAME` replays one,
`--verbose` prints each record's preflight status, class and audit digest. The
runner is stdlib-only apart from the engine import, reads no clock, no network
and no ambient environment, and locates the checkout by walking up from its own
file. It runs as `incident-replay-corpus` in `portability/matrix/plan.json`.

## Composition

12 incidents, 27 request records — 12 clean twins and 15 defective — over 12 of
the 30 composed obligations (OBL-02, -03, -06, -10, -11, -12, -22, -23, -25,
-26, -27, -28). Expected audited classes across the 27: 12 `VALID`, 11
`OMISSION_OR_INCOMPLETE`, 2 `MALFORMED_OR_BOUNDARY`, 2 `BINDING_OR_CONFLICT`.
Every expected class was derived from the frozen predicate table before the
record was executed, then confirmed against the engine; none was back-filled
from observed output.

Each incident directory holds `SOURCE.md` (the public record and what it says),
`METHOD.md` (what was adapted and where judgment entered), `expected.json` (the
pinned expectations), and `records/`.

## Provenance and license posture

**No third-party code, data file, or corpus was vendored into this repository.**
Every file under `incidents/` is either prose written for this corpus or a
synthetic JSON record. The request envelopes are carriers taken from this
repository's own sealed fixture packs
(`baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json`,
`supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json`) with
only `decision_input.facts` replaced; every identifier, digest, scope and
purpose string in them is synthetic. There is no personal data, no customer or
employer material, and no operator-workspace content anywhere in the corpus.

Sources are cited by URL and identifier and used as facts, not as content:

| Incidents | Source | Form used |
|---|---|---|
| 01–08 | Anthropic, *Risk Report: August 2026*, public edition, <https://www.anthropic.com/aug-2026-risk-report> | Paraphrased factual description with section pointers. Incident 03's figures are independently corroborated by press coverage cited in its `SOURCE.md`. |
| 09–10 | AgentDojo (ETH Zurich SPY Lab), <https://github.com/ethz-spylab/agentdojo>, paper <https://arxiv.org/abs/2406.13352> | One named task identifier (`InjectionTask4`, incident 09) and one suite-level attack pattern (incident 10), with the described outcomes. Three strings are retained verbatim from the cited task file: the task identifier, the attacker account literal, and the action name (each located in the incidents' `SOURCE.md`/`METHOD.md`/records). Beyond those, no AgentDojo code, task data, or fixture was copied, and no injection text was reproduced. (Wording corrected 2026-08-20 under the census-correction rule; the prior cell said no task data was copied, which was too terse to be accurate.) |
| 11–12 | MAST, *Why Do Multi-Agent LLM Systems Fail?*, <https://arxiv.org/abs/2503.13657> | Five failure-mode definitions quoted with attribution (FM-1.1 and FM-2.3 in incident 11; FM-3.1, FM-3.2 and FM-3.3 in incident 12) across two author-constructed fixtures, plus reported aggregate figures; incident 12 also draws population figures from the Anthropic report row above, as its `SOURCE.md` records. No trace data was copied. (Wording corrected 2026-08-20; the prior cell said two entries quoted a sentence each.) |

Because nothing is vendored, no third-party license terms attach to any file
here; the corpus is covered by this repository's own `LICENSE` (Apache-2.0).
Readers redistributing the *sources* remain subject to those projects' terms.

**Unverified pointers, disclosed.** The Anthropic section and page pointers in
incidents 01–08 come from an unpublished workspace analytical mapping of the
report onto RR obligations — referred to throughout the incident documents as
"the fit document" — and were **not** re-derived by re-paginating the published
report. Each `SOURCE.md` says so and tells a reader to re-check. The mapping
itself is not published and is cited by entry number only.

## Two lanes, and the honest gap

`expected.json` records a `preflight_lane` per incident, and the difference is
not cosmetic.

**`calibrated` — 2 incidents (02, 11).** The obligation is one the portable
preflight has rules for. These run the real integration path: native evidence →
`preflight(native, profile)` returns `READY` after re-deriving the fact profile
from the evidence and finding it identical → the same facts go to
`decide_audited`. `fabricated_fields` is empty and the preflight enforces that.
These two are the strongest artifacts in the corpus.

**`abstain_uncalibrated` — 10 incidents.** The obligation is outside the
preflight's four calibrated families. Each still ships native evidence and the
runner still calls the preflight on it, which returns `INSUFFICIENT_EVIDENCE`
with `PREFLIGHT_FAMILY_UNCALIBRATED`. That abstention is recorded as the
expected result rather than routed around.

**The gap.** Under `adapters/README.md`, a non-`READY` preflight means *do not
invoke the engine*. This corpus invokes it anyway on those ten, because what it
demonstrates is the engine's classification, not a compliant integration. A host
reaching those obligations legitimately would first build an integration-owned
adapter and pass the promotion gate in `adapters/CALIBRATION.md`. Ten of twelve
incidents therefore show an engine classification over a corpus-author-assembled
profile — exactly the [HOST_OBLIGATIONS.md](../HOST_OBLIGATIONS.md) H3/H4
fabrication the artifact tells hosts not to do, done deliberately and declared
in each `METHOD.md`.

## What the runner checks beyond the class

Per record, and any one of them turns the run red:

- the SHA-256 of the request bytes on disk equals the digest pinned in
  `expected.json`, so a silently edited record fails;
- `audit.request_raw_sha256` equals that same digest — the seal is bound to the
  exact replayed bytes;
- the audit self-zero seal recomputes;
- `audit.governing_authorities` carries the **closed six-key set** the audited
  envelope declares (closure policy, authority register, engine capabilities,
  engine runner, and both decision-table contracts). Closed, not a subset: a key
  appearing or disappearing is a failure.

The six-key assertion moved once. The corpus was authored against the pre-0.4.2
engine, which named four authorities; [ERRATA.md](../ERRATA.md) E8 sealed both
decision-table contracts into the envelope and the set became six. Replaying the
unchanged corpus against the released engine failed all 27 records on that one
assertion and on nothing else — every class, conclusion, exit code, request
digest and seal still held. The pin was moved; the closed-set shape is the point
of keeping it.

A negative control was run during construction: tampering one defective record's
facts so it would classify `VALID` produced `failures=1`, `executable=no` for
that incident, and exit code 1.

## Known weaknesses

Stated plainly so a reviewer does not have to find them:

- **Ten of twelve incidents fabricate at least one schema-required field.** Every
  instance is listed in that incident's `METHOD.md` under "Where judgment
  entered". This is the central limitation.
- Incidents 11 and 12 instantiate a published *taxonomy*, not a published
  *incident*; their provenance is weaker than the other ten.
- Incident 03 fires two decision-table disjuncts at once, so it does not isolate
  which one produced the class.
- Incident 06's two support-state fields are conclusions the corpus author drew
  from prose. H3 requires an auditable derivation; there is none.
- Incident 08 does not implement the mapping the fit document proposed, and says
  so.
- Prompt injection (incidents 09, 10) is outside RR's reach, and adapting the
  *outcome* of an injection does not change that. Both `SOURCE.md` files say so.
- Nothing here is author-separated. The corpus author is the artifact's author,
  and no reviewer has checked the adaptations.

Under the repository map this is a **harness**: machinery that produces a
checkable result. It is not frozen evidence and not a conformance surface, and
`TRUST_MODEL.md`'s census line is unaffected — a corpus authored by the
artifact's own author is neither an external consumer nor a sibling one, and
that census counts consumers outside the maintainer's control.
