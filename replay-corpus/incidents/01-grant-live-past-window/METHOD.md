# Method — 01-grant-live-past-window

**Demonstrable claim.** RR classifies the adapted `defective-window-overrun`
record as `MALFORMED_OR_BOUNDARY` / `VIOLATED`, the adapted
`defective-revocation-unchecked` record as `BINDING_OR_CONFLICT` / `VIOLATED`,
and the clean twin as `VALID` / `SATISFIED`. Nothing here is a claim about what
would have happened in the real deployment.

## Obligation selected

`OBL-26` — *"Enforce authorization continuously through expiry and revocation,
atomically consume single-use grants, reject replay, and emit one effect-linked
execution receipt."* Operation handle `OPR_2B12C8F8D4240FDA61CDA198`.

Selected because the incident carries both limbs this operation's decision table
evaluates: the half-open validity window (`OUTSIDE_HALF_OPEN` →
`MALFORMED_OR_BOUNDARY`) and the presence of a revocation check
(`ANY_ABSENT` over `revocation_checked_at` → `BINDING_OR_CONFLICT`).

## The adaptation

| Incident element | Fact field | Value | How derived |
|---|---|---|---|
| predeployment testing window opens | `grant_not_before` | `0` | arbitrary origin; the engine compares order only |
| model launch — intended end of the grant | `grant_expires_at` | `100` | window end, exclusive |
| use during predeployment testing | `invocation_time` (clean) | `50` | any instant inside the window |
| use two weeks after launch | `invocation_time` (defective) | `114` | one integer unit per day, launch at 100 |
| revocation state consulted | `revocation_checked_at` | `50` / `null` | `null` encodes "not executed" |
| no revocation recorded | `revoked_at` | `null` | the public record does not state a recorded revocation |
| the authorised effect | `effect_sha256` | SHA-256 of the ASCII label `helpful-only-access-grant/cbrn-testing-org` | synthetic stand-in for the effect's content digest |
| the execution receipt | `execution_receipt_effect_sha256` | same digest | matched, so this limb does not fire |

## Where judgment entered

Every item below is a corpus-author decision, not something the public record
states.

1. **Choice of obligation.** The report names no obligation. `OBL-20`
   (pre-effect gate over an authorisation window) would also fire on the window
   limb. `OBL-26` was chosen because it covers both limbs in one operation. The
   alternative mapping was not built.
2. **Integer encoding of dates.** The engine compares order only, so the class
   is invariant under any monotone encoding of the same ordering. `0 / 100 /
   114` is one such encoding; "two weeks" contributes nothing beyond
   `invocation_time >= grant_expires_at`.
3. **Fabricated single-use bookkeeping.** `invocation_nonce`,
   `prior_invocation_nonces`, `consumption_state`, `effect_receipt_count`,
   `effect_sha256`, and `execution_receipt_effect_sha256` are **not** in the
   public record. They are schema-required for this operation, so the corpus
   supplied non-firing values in order to isolate the limb the incident
   describes. This is exactly the fabrication `HOST_OBLIGATIONS.md` H3 and H4
   tell a host not to do: a real host lacking these facts must abstain, not
   invent them. The corpus does it deliberately and declares it here so the
   demonstration is legible; the declaration is the point.
4. **Minimal delta.** Each defective record differs from the clean twin in
   exactly one field, so the classification change is attributable to that
   field and nothing else.
5. **The clean twin is constructed, not observed.** It shows what the same
   profile shape classifies as when the described defect is removed. It is not
   a claim that such a record existed.
6. **Carrier envelope.** The request envelope (`inner_request`, its two
   binding digests, `request_id`) is taken verbatim from the frozen conformance
   fixture entry named in `expected.json` (`carrier_fixture_entry_id`), per
   `EXAMPLE.md`: editing only `decision_input.facts` requires no hash
   recomputation. The inner bundle therefore still carries the fixture's
   synthetic records, including an `observable_external_facts` entry naming the
   fixture case. Only `decision_input.facts` is incident-derived.

## Preflight lane — `abstain_uncalibrated`

`records/native-uncalibrated.json` carries native evidence in family
`EFFECT_GRANT`. The portable preflight has calibration rules for four families
only (`REF`, `SCOPE`, `SUPERSEDE`, `LIFECYCLE`), so it returns
`INSUFFICIENT_EVIDENCE` with issue `PREFLIGHT_FAMILY_UNCALIBRATED`. That is an
**abstention** — not a pass and not a detection.

Under the preflight's own contract (`adapters/README.md`), a non-`READY` result
means the integration does not invoke the engine. This corpus invokes it
anyway, because the corpus is demonstrating the engine's classification, not a
compliant integration. A real host reaching this operation legitimately would
have to build an integration-owned adapter and pass the promotion gate in
`adapters/CALIBRATION.md`. That gap is the honest state of this incident.

## What a green replay demonstrates

- The engine classifies the window-overrun profile as `MALFORMED_OR_BOUNDARY`
  and the unchecked-revocation profile as `BINDING_OR_CONFLICT`, deterministically
  and under a seal that binds the exact request bytes on disk.
- Removing the single defective field returns the profile to `VALID`.

## What it does not demonstrate

- That RR would have altered the real incident. The rule-value experiment is
  unrun.
- That the fact profile is true of the world. The engine classifies what a
  caller attests (H1); the corpus author is the attester here.
- Anything about the incident's underlying subject matter.

## Reproduce

```
python -B replay_incidents.py --incident 01-grant-live-past-window --verbose
```
