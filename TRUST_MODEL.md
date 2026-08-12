# Trust model — what this repository's evidence claims, and for whom

This page is the canonical trust declaration for the whole artifact. Where a
lane document states a narrower boundary (`portable/THREAT_MODEL.md`,
`HOST_OBLIGATIONS.md`, `perf/SIDECAR.md`), this page governs the reading and
those pages supply the per-surface detail. Criticisms and scan findings are
adjudicated against THIS declaration
(`orchestration/CRITICISM_ADJUDICATION.md`, standing protocol; Intake 10 is
the first batch adjudicated under it).

## The trust root

The authenticated repository commit — the bytes a consumer obtained from the
authenticated remote or release — is the only trust root. Everything below
it is content-addressed: seals and digests prove **integrity and
reproducibility relative to that root**, never provenance. Nothing in this
repository is signed; there is no key infrastructure, deliberately. A party
who can rewrite the repository can rewrite any in-repo pin along with it, so
an in-repo digest is drift detection, not authentication
(`portable/THREAT_MODEL.md` states the same rule for the bundle manifest).

## What each evidence class proves

| Evidence | Proves | Does not prove |
|---|---|---|
| Sealed 0.2/0.3 response | This response object is internally intact (self-zero seal) and byte-reproducible from the request under the sealed contract | What facts were judged (recorded defect E2 — use the audited surface) |
| Audited decision (`B1-AUDITED-DECISION-0.4.1`) | The class, witness trace, and record references derived from these exact request bytes under the exact governing policy bytes named in `governing_authorities` (E8) | Who ran it, when, or that the host's attested facts were true (H1) |
| Conformance / fixture receipts | The named suite reproduced the pinned expectations at the recorded counts on the recorded host | Anything about hosts or bytes not named in the receipt |
| Hosted matrix receipts | A named GitHub Actions run (an authority external to this repo) observed the recorded outcomes for the pinned plan rows | Rows not executed; bytes newer than the bound head |
| Harness receipts (perf, sidecar, WP1 outcome) | The measurement, on the recorded host and corpus, scoped exactly as the receipt states | Generalization to other hosts, workloads, or corpora |

`READY` from the portable preflight is **eligibility, never a pass**:
sufficient, noncontradictory native evidence under the fail-closed boundary
law (`adapters/portable_preflight.py` module docstring). `REJECTED_INVALID`
is detection; `INSUFFICIENT_EVIDENCE` is abstention; `AUDIT_INCOMPLETE`
means a VALID class could not be certified by a complete closure pass (E9).

## Trust boundaries, by surface

| Boundary | Untrusted side | Defense |
|---|---|---|
| Wire bytes → parser/engine | Fully attacker-controlled | One total bounded parser law: size before allocation, duplicate rejection, integer domain, NFC, deterministic errors |
| Host evidence → preflight | Attested, not authenticated | Three-state fail-closed preflight detects internal inconsistency; it cannot prove a lying observer (H1) |
| Repository/bundle bytes → verifiers | Trusted **after** commit-root authentication | Digest pins detect drift; they do not authenticate an untrusted directory |
| Supervisor ↔ sidecar child | Child output untrusted until correlated | Versioned envelope binding sequence + request-byte digest to a completely written request; no replay |
| Harness/tooling → receipts | Operator's own machine (trusted OS assumption) | Receipts scope their claims to the recorded host; ambient-authority residue is a recorded caveat, not a defended boundary |

## Who consumes this, today

Verified consumer census, 2026-08-12 (method: content search for
`receiver_reliance`, `decide_audited`, `portable_preflight`, and the wire
format strings across the operator's workspace and adjacent project trees;
one unrelated production repository excluded by standing operator policy):
**zero external or sibling code consumers exist.** Every present consumer is
in-repo (the proof harness, the lanes, the verifiers) or a reader of the
public repository. No party currently relies on preflight `READY` or on
audit seals as adversarial-grade guarantees.

The artifact is therefore maintained as a **research artifact**: consumers
re-verify from the commit root; receipts exist to make that re-verification
mechanical. This posture is a recorded decision, not an accident.

**Re-adjudication trigger:** the first external consumer, or any embedding
where handoff senders are adversarial to the receiver's own tooling,
re-opens the deferred hardening set recorded in Intake 10 (shared canonical
ingest for every peripheral surface; sidecar lifecycle limits as protocol;
harness ambient-authority elimination) as blocking work before that
embedding ships.

## Non-claims

Unchanged from the README and charter: no security, efficacy, novelty,
external-standard, or universal-portability claim. This page does not add a
guarantee; it bounds what the existing evidence machinery may be read as
claiming.
