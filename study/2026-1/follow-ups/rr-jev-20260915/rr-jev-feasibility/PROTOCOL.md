# RR + Jev: changing evidence feasibility pilot

Authorized by James's "ok go" on September 15, 2026 (Pacific), following discussion of a small feasibility study. This is a separate, local development pilot. The completed 1,805-episode RR study and all original source/evidence remain unchanged.

## Question and sufficient proof

Can a Jev semantic assessment improve the correctness of released synthetic text claims, and does invoking actual RR produce different receiving decisions from conventional relational checks with the same information and repair budget?

Deliver: a runnable harness invoking the actual R-all implementation; prospectively fixed synthetic cases and analysis; retained real API requests/responses; independently reviewed comparison; measured results including null results. This is not a new full-treatment confirmatory study, public preregistration, human evaluation, field trial, or independent replication.

## Population and arms

Six hand-authored synthetic source/claim families, crossed with eight transitions: unchanged, contradictory source update, harmless source update, overstated claim, changed intended purpose, revised artifact, expired assessment, revoked assessment. Total: 48 constructed episodes, each with an initial assessment and one later receiving opportunity. The six families, not 48 independent observations, are the base units. No inferential intervals or significance tests. No natural prevalence estimate. Templates and labels are development fixtures, not held-out or human-adjudicated data.

Primary arms: conventional without Jev, R-all without Jev, conventional with Jev, R-all with Jev. Conventional policy independently checks the same relevant relationships from the host's observed facts. It is expressive for this declared pilot population, not a complete conventional reimplementation of every R-all operation. Always-recheck with Jev is a cost diagnostic. No comparison against a deliberately weak cache is a claim of RR value.

All arms get identical sources, claims, current uses, lifecycle information, and at most one refresh/reissue. A revoked assessment cannot be repaired by an AI opinion. Refresh requires a fresh, explicit simulated issuer declaration from a standing synthetic issuer. No-Jev arms carry unverified sender claims, not fabricated model outputs. Jev arms release only when the returned label is supports, P(supports) >= 0.90, and confidence >= 0.80. Thresholds are fixed before inference; they are exploratory policy values, not calibrated guarantees. All other labels and uncertain answers are withheld. There is no generated answer repair in this pilot.

The host binds source bytes AND source revision through full parent identities. Changing source_content alone is not a sufficient RR check. Exact claim/artifact changes preserve the old declaration until the authorized refresh. Intended use is checked against the original declaration. Full RR runs through its existing fresh-process worker with actual engine-call observations and independent observe.verify. Test fixtures use honest simulated host observations; no authenticity or real OS enforcement is claimed.

The existing RR artifact JSON parser forbids floating-point values. Preserve Jev's complete answer losslessly as JSON text in the artifact's answer_json field, alongside request/response hashes and model identity. Decode it for thresholding and equality checks. Qualification covers both unverified sender payloads and Jev-shaped payloads with fractional probabilities; these structural fixtures are not model measurements.

## Semantic experiment

Use the official POST https://api.typesafe.ai/v1/systemone contract. Question: supplied evidence's support for the exact claim. Choices: supports / contradicts / insufficient. State contains only synthetic claim, source text, and intended use. Gold labels, transition labels, policy arms, expected decisions and task IDs never enter the request. Each distinct request is collected once and shared across arms to isolate policy effects. Request order is seeded and fixed. Reuse of bank responses is an experimental coupling; logical check counts are separate from actual API calls. Replayed latency and logical cost are not independently measured end-to-end workflow performance.

Use jev-latest. Authenticated model discovery offered only jev-latest and jev-preview on September 15; no immutable version was advertised. Record the requested alias, returned model, model discovery response, times, request/response hashes and source pins. Byte replay is reproducible; future inference with the alias is not promised identical.

Budget: at most 40 unique POST attempts, one attempt per request, 1,000,000 total submitted JSON bytes, 30-second request timeout. No automatic paid retries. At the advertised $0.042 per million input tokens and zero output price, 1 million input tokens would be $0.042; bytes are an engineering submission cap, not an exact token or billing cap. Record actual reported tokens and estimated token charge separately from invoices. Stop on HTTP/authentication/malformed-response failure; retain successful partial results and account for missingness. No purchases or billing configuration.

Credentials enter process memory from James's explicitly identified clipboard and are sent only as an Authorization header to api.typesafe.ai over TLS. No redirects, no key files, no key output, no custom endpoint. Child RR workers must not inherit the API key. Clear the environment copy immediately after loading it in the HTTP client. Only synthetic data goes to TypeSafe.

## Outcomes and analysis

Per arm: policy-replay released claims; semantically unsupported/contradicted releases; hard-revocation violations; supported permitted claims withheld; initial reuse vs refresh; logical semantic checks; true paid collection calls; reported tokens; estimated charge; service latency; actual RR structural invocation latency. Exact engine and observer outputs and released artifact bytes are retained; scored claim and assessment must equal the released payload. Return a positive, null, adverse, or inconclusive result. Author labels are manually explicit, independently reviewed for ambiguity, and never derived from Jev. Missing service data is not scored as a model answer or silently excluded.

Refresh/reissue triggers a logical semantic check even for artifact-only revision or expiry when the semantic request is identical. Both primary comparators use this same policy. These are deliberately simple policies, not optimal content-addressed semantic caches; a competent implementation could separate authorization reissue from assessment recomputation. Retained raw service text is sanitized for any echoed credential before hashing and storage, and replay checks its hash and equality to parsed results.

Success criteria for feasibility are executable evidence binding, meaningful model measurements, and a fair interpretable comparison, not an RR win. A tie against conventional checks is a valid result. No value conclusion from cost alone without correctness/usefulness, and no general superiority or cost-saving claim from constructed policy replay. Source provenance establishes the code run, not semantic truth. Engineering time is unmeasured.

## Freeze and continuation

Freeze protocol, synthetic cases, harness and relevant original RR source hashes before semantic outcome collection. Local pre-outcome freeze is not public preregistration. Independent review may repair invalid design before the freeze; changes after inference require a clearly separate run/amendment. A later held-out study would need independently sourced/adjudicated cases, justified thresholds and sample size, competent comparator parity, and a separate scope decision. Do not relabel these fixtures held-out.
