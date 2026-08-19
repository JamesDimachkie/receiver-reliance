# Method — 02-superseded-threshold-copied

**Demonstrable claim.** The portable preflight returns `READY` for both the
defective and the clean native record; RR then classifies the defective one as
`OMISSION_OR_INCOMPLETE` / `UNRESOLVED` and the clean twin as `VALID` /
`SATISFIED`. Nothing here is a claim about what would have happened in the real
deployment.

## Obligation selected

`OBL-02` — *"Give every record and material revision exact immutable identity;
exact references never mean latest."* Operation handle
`OPR_3A4599E3E3125ED732D36DE3`.

Decision-table limb that fires: `NOT_FUNCTIONAL_BY` over `/facts/record_versions`
keyed `record_id` → `revision_sha256`. When one record identity carries two
distinct revision digests, the reference is not a function and the operation
terminates as `OMISSION_OR_INCOMPLETE`. That is the mechanical statement of
"this citation does not resolve to one revision."

## Why this incident is on the calibrated lane

`OBL-02` is one of the four families the portable preflight is calibrated for
(`REF`, per `adapters/README.md` and `adapters/CALIBRATION.md`). So this incident
runs the real integration path rather than a synthetic one:

```
native evidence  ->  preflight (validates the host profile against the evidence)
                 ->  decide_audited (classifies the same facts)
```

The `RR-PORTABLE-FACT-PROFILE-1` envelope in `records/*-profile.json` carries
exactly the fields `OBL-02` requires — `exact_reference` and `record_versions`
— and the preflight re-derives them from the native record and compares. A
profile that drifted from the evidence would come back `REJECTED_INVALID`
before the engine ran. The same two fields are what
`decision_input.facts` carries in the engine request: no second mapping step,
no widening.

## The adaptation

Native evidence (`records/*-native.json`, family `REF`):

| Incident element | Native field | Value |
|---|---|---|
| the configuration record cited by the deploying change | `native.referenced_record` | `THRESHOLD_CONFIG_STAGE1_PROBE` |
| the value that was hand-copied | `native.claimed_sha256` | SHA-256 of `stage1-probe-threshold/previous-classifier-value` |
| the record was found at that identity | `observations.referenced_record_found` | `true` |
| the revision actually at that identity | `observations.observed_sha256` | SHA-256 of `stage1-probe-threshold/opus-4-7-calibrated-value` |

Derived fact profile (produced by the calibrated `REF` mapping, then confirmed
by the preflight):

- `exact_reference` = `THRESHOLD_CONFIG_STAGE1_PROBE`
- `record_versions` = the observed revision, plus the claimed revision when the
  citing record asserts one

In the **defective** record the two digests differ, so `record_versions` binds
one `record_id` to two revisions. In the **clean twin** the claim and the
observation agree, so both entries carry the same revision and the mapping stays
functional.

## Where judgment entered

1. **Digests stand for content, not content.** The two SHA-256 values are
   hashes of short ASCII labels chosen by the corpus author. The report does not
   publish the configuration bytes. Any two distinct digests produce the same
   classification; any two equal digests produce the clean class. Nothing about
   the real threshold value is represented, asserted, or needed.
2. **"Hand-copied from the previous classifier" → a digest disagreement.** The
   incident is described in terms of *how* the wrong value got there. The
   adaptation keeps only the observable consequence: the citing record's claim
   and the resolved revision disagree. Provenance of the disagreement is not
   modelled, and the classification does not depend on it.
3. **Choice of obligation.** `OBL-15` (exact-version correction and cascading
   repair) and `OBL-21` (versioned expectation replay through one matching
   suite) both have plausible readings of this incident. `OBL-02` was chosen
   because it is the one with a calibrated preflight family, which lets the
   incident run the full native-evidence path instead of a facts-only one. The
   alternatives were not built.
4. **The profile is host-authored.** The corpus author wrote the profile
   envelope by following the calibrated mapping documented in
   `adapters/CALIBRATION.md`; the preflight then independently re-derived it and
   agreed. That agreement is the check — it is not evidence that the mapping is
   the *right* mapping for a real threshold-configuration system.
5. **Five days, some traffic, neither forwarded nor blocked nor logged.** None
   of that is represented. The adaptation covers the reference defect only, not
   its consequences.
6. **Carrier envelope.** As in every incident here: the request envelope comes
   verbatim from the frozen fixture entry named in `expected.json`; only
   `decision_input.facts` is incident-derived.

## What a green replay demonstrates

- Native evidence in a calibrated family flows through the preflight to the
  engine with no fabricated field (`fabricated_fields` is empty and the
  preflight enforces that).
- The engine classifies the two-revision reference as `OMISSION_OR_INCOMPLETE`
  and the one-revision reference as `VALID`.
- The audit seal binds the exact request bytes on disk, so the replay cannot
  silently drift.

## What it does not demonstrate

- That RR would have altered the real incident.
- That the calibrated `REF` mapping is applicable to real classifier
  configuration records. It is calibrated against the published 408-record
  corpus and nothing else (`adapters/OUTCOME.md`, `ERRATA.md` E7).
- Truth of the attested facts (H1).

## Reproduce

```
python -B replay_incidents.py --incident 02-superseded-threshold-copied --verbose
```
