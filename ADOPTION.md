# Adoption ledger — what is unfixed, and the treatment for each

This artifact's claim is that every published result is mechanically
re-derivable from published bytes. That claim is checkable today
([README.md](README.md) "Re-verify everything"). This file is the other half:
the recorded, unfixed work between here and an artifact a third party can
adopt, with the treatment for each item and who it belongs to.

Nothing here is new information. Each row cites the canonical record; this page
exists because those records are scattered and a reader should not have to
assemble the list. Rows leave when the work lands, not when the wording
improves.

## Blocking for a third party

| # | Blocker | Canonical record | Treatment | Owner |
|---|---|---|---|---|
| A1 | What `git clone` gives you is not what passes the gates. `origin/main` is six commits behind `hardening-industry-grade`, which additionally carries uncommitted working-tree edits. `HYGIENE_PASS`, the 517-check grounded regression, the 193 receipt checks, the withdrawal of the bare `decide` route, and the reconciled 100,000-identity figure are all true only on the hardening branch. | `git rev-list --left-right --count origin/main...hardening-industry-grade` | Merge the hardening branch into `main` and publish. No code change is involved; it is a publication decision. | repository owner |
| A2 | The hosted robustness gate cannot fire. `.github/workflows/robustness-verification.yml` triggers on pushes to `sol/rr-robustness-20260811`, a branch that exists neither locally nor on the remote, so its three-OS x CPython 3.12/3.13/3.14 matrix and the WP4 campaign run only by manual dispatch. `portability.yml` triggers on `main` only. On the branch where the artifact actually lives, only `conformance.yml` runs. | the two workflow `on:` blocks | Retarget both triggers to `main` plus the active release branch. | repository owner — the Intake 10 dispositions place CI edits behind an explicit owner gate |
| A3 | No conforming second implementation exists. The WP4 attempt-3 candidate sits at `campaign_gate = DEFERRED_PENDING_FRESH_CONTEXT_REFUTER_ZERO_DIVERGENCE`; three author strikes are recorded. Until one exists, byte-parity is a property of the reference implementation against itself. | [ERRATA.md](ERRATA.md) E10, `orchestration/LEDGER.md` | The live attempt is the B1 comparator packet lane, external to this repository: an unexposed implementer receives an eleven-file public projection and must clear 907/907 in-process and subprocess conformance, the 30-row 372-check composed gate, and a candidate-unchanged predicate. | in flight, outside this repo |
| A4 | Peripheral loaders do not share the core's one strict ingest law. The public decision surface now routes object and byte requests through the same bounded total parser (see the W3-grounded section of the Intake 10 dispositions), but the portability matrix and receipt loaders, the portable verifier, the second-implementation CLI, and the live/schedule parsers each still canonicalize on their own terms. | `orchestration/robustness/INTAKE_10_SCAN_DISPOSITIONS.md` cluster C2 | Extract the core's strict parser into one bounded-ingest module and adopt it in each named loader, with a per-loader parity regression asserting identical accept/reject sets. This is the one item on this page a hostile sender can exercise directly. | unstarted |
| A5 | Evidence harnesses carry ambient host authority: bare `git`/`docker` resolution, environment passthrough, and sandbox fields reported optimistically rather than verified. | same file, cluster C5 | Two closures are acceptable and the cheaper one is honest: reduce every affected receipt's language to what was actually verified, now; pin tool resolution, scrub the environment, and verify sandbox fields at the trigger. The language reduction costs no behaviour change and removes the overclaim. | unstarted |
| A6 | Long-lived harnesses treat process-tree and deadline totality as local detail. Five bounds are disclosed and deliberately unrepaired: the deadline covers the await phase but not the write phase; failure cleanup terminates the direct child only, so grandchildren survive; stderr arriving after envelope correlation surfaces on the next interaction rather than retroactively; an LF-less flood costs bounded memory but unbounded work; execution-input receipts pin file bytes at manifest time rather than at each read. | `perf/sidecar/findings/F-WP5-006.md`; same dispositions file, cluster C6 | Each is a bounded change to `rr_sidecar.py` or `grounded-0_4/rr_batch.py`: job-object or process-group containment, a write-phase deadline, retroactive stderr adjudication, a documented flood ceiling, and read-time pinning. The batch-overlimit half of this class is already closed. | unstarted |
| A7 | There is no self-contained distribution. `pyproject.toml` supports one integration mode, an editable install from a checkout, because the package locates the frozen engine and the sealed contract and fixture data relative to that checkout. | `pyproject.toml` build comment | Ship the sealed contract and fixture data as package data and assert a manifest digest at import, so an installed copy proves it holds the same bytes the repository publishes. | unstarted |

## Deliberately kept, disclosed, not blocking

- The applicability result (18/18 detection at zero new false holds) is
  reproducible from published bytes through the adapters replay documented in
  `proof/README.md`, but the `proof/` arm scripts themselves need an
  operator-only extractor and are not third-party runnable end to end. The
  result is checkable; that one path is not.
- The frozen 0.4 sealed response path still returns `VALID` for the closure
  gaps `ERRATA.md` E2 and E5 record. The audited surface fails closed on the
  same inputs. Sealed bytes may not change by charter, so this asymmetry is
  permanent for this generation, and is why `decide_audited` is the supported
  route.
- The subprocess-ABI conformance mode pins the Windows CPython embeddable and
  is not portable by construction; the in-process suites carry the portability
  claim.

## The trigger, stated once

`TRUST_MODEL.md` maintains this artifact as a research artifact on the basis of
a zero-consumer census, and records that the first external consumer — or any
embedding where handoff senders are adversarial to the receiver's own tooling —
promotes A4, A5 and A6 to blocking work before that embedding ships. Adopting
this artifact is exactly the event that fires that trigger. A1 and A2 are the
only rows that block reproducing what is already claimed; the rest bound what
may be claimed next.
