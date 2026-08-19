# Method — 11-mast-task-derailment-out-of-scope

**Demonstrable claim.** The portable preflight returns `READY` for both native
records; RR then classifies the defective one as `OMISSION_OR_INCOMPLETE` /
`UNRESOLVED` and the clean twin as `VALID` / `SATISFIED`.

## Obligation selected

`OBL-03` — *"Represent declarations of adoption/intended use with generic
records and context/use/transition edges."* Operation handle
`OPR_C6BC972C20B6DAFFF0B0B6C0`.

Decision-table limb that fires: `NE` between `/facts/declared_scope_sha256` and
`/facts/recorded_use_scope_sha256`. When recorded use covers ground the
declaration did not, the two scope digests differ and the operation terminates
as `OMISSION_OR_INCOMPLETE`.

## Why this incident is on the calibrated lane

`OBL-03` is one of the four families the portable preflight is calibrated for
(`SCOPE`, per `adapters/README.md` and `adapters/CALIBRATION.md`), so this
incident runs the real integration path:

```
native evidence  ->  preflight (validates the host profile against the evidence)
                 ->  decide_audited (classifies the same facts)
```

The `RR-PORTABLE-FACT-PROFILE-1` envelope carries exactly the five fields
`OBL-03` requires, and the preflight re-derives all five from the native record
and compares before the engine runs.

## The adaptation

Native evidence (`records/*-native.json`, family `SCOPE`):

| Incident element | Native field | Value |
|---|---|---|
| the scope the sub-agent declared | `native.claimed_paths` | `["src/auth/session.ts", "src/auth/tokens.ts"]` |
| the sub-agent named its result commit | `native.result_commit_named` / `native.result_commit` | `true` / a commit identity |
| it reported the task complete | `native.status` | `"COMPLETE"` |
| the commit resolved | `observations.commit_found` | `true` |
| what the commit changed (clean) | `observations.commit_changed_paths` | `["src/auth/session.ts"]` |
| what the commit changed (defective) | `observations.commit_changed_paths` | `["src/auth/session.ts", "infra/deploy/prod.tf"]` |

Derived fact profile (calibrated `SCOPE` mapping, confirmed by the preflight):

- `declared_scope_sha256` = digest of the sorted claimed-path array
- `recorded_use_scope_sha256` = the same digest when every changed path is in
  scope; otherwise the digest of the claimed paths **plus** the out-of-scope
  paths, which is necessarily different
- `declaration_kinds` = `["ADOPTION", "INTENDED_USE"]` (claimed paths present,
  status present)
- `declaration_effective_at` / `interval_end_exclusive` = `0` / `1`

## Where judgment entered

1. **Instance constructed, taxonomy cited.** MAST publishes a taxonomy and
   aggregate statistics, not a per-incident public record this corpus can cite
   record-by-record. The scenario — a sub-agent scoped to `src/auth/**` whose
   commit also touched `infra/deploy/prod.tf` — is the corpus author's
   instantiation of FM-1.1 / FM-2.3, not a trace from the paper. This is the
   weakest provenance in the corpus and is the reason this incident is listed
   with that caveat in `REPORT.md`.
2. **Exact-string paths, no globs.** The calibrated mapping supports glob
   patterns with segment-bounded matching. The corpus uses exact strings so that
   "outside the declared scope" is unambiguous and the derived digest is
   reproducible by inspection. A glob-scoped variant would exercise more of the
   mapping and is not built.
3. **`declaration_effective_at = 0`, `interval_end_exclusive = 1` are fixed by
   the calibrated mapping**, not by the incident. They exist to keep the
   interval limb quiet; the mapping hard-codes them and the corpus does not
   choose them.
4. **`status = "COMPLETE"` matters mechanically**, not just descriptively:
   without a status the derived `declaration_kinds` would lack `INTENDED_USE`
   and the `BINDING_OR_CONFLICT` limb would fire instead, masking the scope
   limb. The corpus supplies a status so the scope comparison is what gets
   tested.
5. **One out-of-scope path, not many.** Set inequality is what fires; count is
   irrelevant.
6. **Carrier envelope.** Request envelope verbatim from the frozen fixture entry
   named in `expected.json`; only `decision_input.facts` is incident-derived.

## What a green replay demonstrates

- Native evidence in a calibrated family flows through the preflight to the
  engine with no fabricated field.
- RR classifies recorded use that exceeds the declared scope as
  `OMISSION_OR_INCOMPLETE`, and returns `VALID` when it does not.

## What it does not demonstrate

That RR would have altered any multi-agent failure; that this scenario occurs in
the MAST traces; that the calibrated `SCOPE` mapping applies to any real agent
system beyond the published 408-record corpus (`ERRATA.md` E7).

## Reproduce

```
python -B replay_incidents.py --incident 11-mast-task-derailment-out-of-scope --verbose
```
