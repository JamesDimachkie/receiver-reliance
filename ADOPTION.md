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
| A2 | The hosted robustness gate cannot fire. `.github/workflows/robustness-verification.yml` triggers on pushes to `sol/rr-robustness-20260811`, a branch that exists neither locally nor on the remote, so its three-OS x CPython 3.12/3.13/3.14 matrix and the WP4 campaign run only by manual dispatch. `portability.yml` triggers on `main` only. On the branch where the artifact actually lives, only `conformance.yml` runs. The claim itself is not unverified — see [portability/THIRD_PARTY_REPRODUCTION_20260818.md](portability/THIRD_PARTY_REPRODUCTION_20260818.md) for a clean-clone reproduction on CPython 3.12, 3.13 and 3.14 at this commit — but that run is Windows-only, so the multi-OS half rests on pinned hosted receipts from an earlier commit. | the two workflow `on:` blocks | Retarget both triggers to `main` plus the active release branch. | repository owner — the Intake 10 dispositions place CI edits behind an explicit owner gate |
| A3 | No conforming second implementation exists. The WP4 attempt-3 candidate sits at `campaign_gate = DEFERRED_PENDING_FRESH_CONTEXT_REFUTER_ZERO_DIVERGENCE`; three author strikes are recorded. Until one exists, byte-parity is a property of the reference implementation against itself. | [ERRATA.md](ERRATA.md) E10, `orchestration/LEDGER.md` | The live attempt is the B1 comparator packet lane, external to this repository: an unexposed implementer receives an eleven-file public projection and must clear 907/907 in-process and subprocess conformance, the 30-row 372-check composed gate, and a candidate-unchanged predicate. | in flight, outside this repo |
| A4 | Peripheral loaders do not share the core's one strict ingest law. The public decision surface now routes object and byte requests through the same bounded total parser (see the W3-grounded section of the Intake 10 dispositions), but the portability matrix and receipt loaders, the portable verifier, the second-implementation CLI, and the live/schedule parsers each still canonicalize on their own terms. | `orchestration/robustness/INTAKE_10_SCAN_DISPOSITIONS.md` cluster C2 | Extract the core's strict parser into one bounded-ingest module and adopt it in each named loader, with a per-loader parity regression asserting identical accept/reject sets. This is the one item on this page a hostile sender can exercise directly. | unstarted |
| A5 | Evidence harnesses resolve `git` and `docker` by bare name from the ambient `PATH` in seven files, so a receipt's commit provenance is only as trustworthy as the operator's `PATH`. Environment passthrough and unverified sandbox reporting are the same cluster. | same file, cluster C5; the caveat itself is recorded in [TRUST_MODEL.md](TRUST_MODEL.md)'s boundary table | The disclosure half is already done and checks out: the boundary table records ambient-authority residue as a caveat rather than a defended boundary, and all 49 receipts under `portability/receipts/` do carry host, platform or runner identification, so the claim that receipts scope themselves to the recorded host is verifiable and true. What remains is the hardening half: resolve every tool through an absolute path, scrub the environment, and verify sandbox fields instead of reporting them. Note for whoever takes it: `shutil.which("git")` is not the fix, because it resolves to the same `PATH` entry an attacker would have planted. Closing this needs either an operator-supplied pinned path, which is a new config surface, or the resolved path recorded in each receipt, which re-digests receipts that are currently SHA-pinned. Both are real decisions rather than edits. | disclosure done; hardening unstarted |
| A6 | Long-lived harnesses treat process-tree and deadline totality as local detail. Five bounds are disclosed and deliberately unrepaired: the deadline covers the await phase but not the write phase; failure cleanup terminates the direct child only, so grandchildren survive; stderr arriving after envelope correlation surfaces on the next interaction rather than retroactively; an LF-less flood costs bounded memory but unbounded work; execution-input receipts pin file bytes at manifest time rather than at each read. | `perf/sidecar/findings/F-WP5-006.md`; same dispositions file, cluster C6 | Each is a bounded change to `rr_sidecar.py` or `grounded-0_4/rr_batch.py`: job-object or process-group containment, a write-phase deadline, retroactive stderr adjudication, a documented flood ceiling, and read-time pinning. The batch-overlimit half of this class is already closed. | unstarted |
| A7 | There is no self-contained distribution yet. `pyproject.toml` still declares one integration mode, an editable install from a checkout. | `pyproject.toml`; `receiver_reliance/engine_manifest.json` | **Authority decision made: the repository stays authoritative and the installed copy proves it holds the published bytes.** Half of this row is now closed. `receiver_reliance/engine_manifest.json` pins all eleven engine files by byte length and SHA-256 under a self-zero seal; importing the package verifies every one before executing any of them and refuses to import on drift; `generate_engine_manifest.py --check` fails on unrecorded engine change, and `test_engine_manifest.py` proves the check fires — one appended byte in any of the eleven, an absent file, an absent manifest — and that the bundled `_engine/` layout imports without a checkout beside it. The closure was DERIVED by tracing what the process opens, not by reading imports: a hand-written list missed four files, so an earlier revision of this row claimed 302,260 bytes across seven files when the engine is really **1,182,122 bytes across eleven**, three of them B1-pinned frozen authority. What remains is packaging alone: stage the eleven into `receiver_reliance/_engine/`, declare them as package data, build, and prove a wheel installed into a clean virtual environment decides correctly. | self-check done and tested; packaging remains |

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
promotes A4, A5's hardening half and A6 to blocking work before that embedding ships. Adopting
this artifact is exactly the event that fires that trigger. A1 and A2 are the
only rows that block reproducing what is already claimed; the rest bound what
may be claimed next.
