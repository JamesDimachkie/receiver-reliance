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
[DIAGRAMS.md](DIAGRAMS.md#c1--one-trust-root-and-everything-that-hangs-off-it)
draws every evidence class descending from that one root, with the absent
signature edge.

## What each evidence class proves

| Evidence | Proves | Does not prove |
|---|---|---|
| Sealed 0.2/0.3 response | This response object is internally intact (self-zero seal) and byte-reproducible from the request under the sealed contract | What facts were judged (recorded defect E2 — use the audited surface) |
| Audited decision (`B1-AUDITED-DECISION-0.4.2`) | The class, witness trace, and record references derived from these exact request bytes under the exact governing data bytes named in `governing_authorities` — closure policy, authority register, engine sources, and both decision-table contracts (E8; contracts sealed since 0.4.2) | Who ran it, when, or that the host's attested facts were true (H1); that the grounded evaluation layer applying those authorities (`grounded-0_4/rr_api.py`) was unmodified — evaluator bytes are not among the sealed digests and are authenticated by the repository commit root alone (E8 scope) |
| Conformance / fixture receipts | The named suite reproduced the pinned expectations at the recorded counts on the recorded host | Anything about hosts or bytes not named in the receipt |
| Hosted matrix receipts | A named GitHub Actions run (an authority external to this repo) observed the recorded outcomes for the pinned plan rows | Rows not executed; bytes newer than the bound head |
| Harness receipts (perf, sidecar, WP1 outcome) | The measurement, on the recorded host and corpus, scoped exactly as the receipt states | Generalization to other hosts, workloads, or corpora |

`READY` from the portable preflight is **eligibility, never a pass**:
sufficient, noncontradictory native evidence under the fail-closed boundary
law (`adapters/portable_preflight.py` module docstring). `REJECTED_INVALID`
is detection; `INSUFFICIENT_EVIDENCE` is abstention; `AUDIT_INCOMPLETE`
means a VALID class could not be certified by a complete closure pass (E9).

**The audited envelope is not four-valued, and the distinction matters.** The
decision *law* classifies every schema-valid decision input into exactly one of
`VALID`, `MALFORMED_OR_BOUNDARY`, `BINDING_OR_CONFLICT`,
`OMISSION_OR_INCOMPLETE` — that is a property of the frozen tables. The audited
*surface* wrapping it can additionally return `AUDIT_INCOMPLETE` and
`PROTOCOL_ERROR` (`grounded-0_4/rr_api.py`, `grounded-0_4/rr_batch.py`), neither
of which is a class the law assigns. `AUDIT_INCOMPLETE` is the fail-closed
outcome of a closure evaluator error, and it fires precisely where the law said
`VALID` — the audited surface refuses to certify what it could not completely
check. `PROTOCOL_ERROR` is what a request that never reached classification
returns.
[DIAGRAMS.md](DIAGRAMS.md#a3--six-answers-from-two-different-authorities)
draws the six values and their two origins, and
[B2](DIAGRAMS.md#b2--what-the-envelope-binds-and-the-one-thing-it-does-not)
what the seal reaches. Totality is intact; "exactly one of
four" is a statement about the law, not about the envelope, and a consumer
switching on `audited_behavior_class` must handle all six. One in-repo consumer does not:
`portability/concurrency/ladder.py` pins a five-member set omitting
`AUDIT_INCOMPLETE` and raises `InvariantFailure` on anything outside it. That is
a narrower contract over a closed fixture set rather than a claim about the
surface, and it has held across every recorded ladder run — but no proof exists
here that those inputs cannot reach a closure-evaluator error, so it is recorded
as a narrower contract, not a demonstrated impossibility.

The same correction applies one level down, and stopping at the class values
would have left the cause unfixed. Three further things a caller observes were
pinned by `grounded-0_4/test_public_surface.py` as supported and declared in no
document until this release:

- **`audit.object_request_error`** — present only when a Python object could not
  be canonicalized into a request. Its values are `ERR_JSON` (non-string key,
  cycle, or unencodable value), `ERR_NUMBER` (non-finite), and `ERR_LIMIT`
  (size, depth, or digit ceiling). When it is present the decision is a refusal,
  not a classification.
- **`grounded-0_4/rr_batch.py` is a supported transport**, not merely a file
  with recorded bounds. It serves newline-delimited requests over the same
  `decide_audited` path and seals each result identically.
- **`audit.transport_error`**, with the value `ERR_BATCH_RECORD_LIMIT`, plus
  `request_prefix_sha256` and `request_prefix_bytes` — what that transport
  returns when a record crosses the physical-line ceiling. The prefix fields
  exist so a refusal names what it saw without claiming a digest of a request it
  never received in full.

## Trust boundaries, by surface

| Boundary | Untrusted side | Defense |
|---|---|---|
| Wire bytes → parser/engine | Fully attacker-controlled | One total bounded parser law: size before allocation, duplicate rejection, integer domain, NFC, deterministic errors |
| Host evidence → preflight | Attested, not authenticated | Three-state fail-closed preflight detects internal inconsistency; it cannot prove a lying observer (H1) |
| Repository/bundle bytes → verifiers | Trusted **after** commit-root authentication | Digest pins detect drift; they do not authenticate an untrusted directory |
| Supervisor ↔ sidecar child | Child output untrusted until correlated | Versioned envelope binding sequence + request-byte digest to a completely written request; no replay |
| Harness/tooling → receipts | Operator's own machine (trusted OS assumption) | Receipts scope their claims to the recorded host; ambient-authority residue is a recorded caveat, not a defended boundary. **Demonstrated, not hypothetical:** a forged `git` placed earlier on `PATH` made `verify_hygiene` report `HYGIENE_PASS` with custody 17/17 while a planted modification was still on disk, and made a receipt gate report `PASS` against a forged HEAD. `shutil.which` resolves to the same forged binary, so it is not a defence. `portability/pinned_tools.py` lets an operator move the trust root from `PATH` to an administrator-write-only directory via `RR_TOOL_DIR`; that narrows this boundary and does not close it, because `subprocess` cannot launch from an already-verified handle on either platform. **A receipt is not evidence that the host producing it was sound.** |

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
