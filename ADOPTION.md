# Adoption ledger — what is unfixed, and the treatment for each

This artifact's claim is that every published result is mechanically
re-derivable from published bytes. That claim is checkable today
([README.md](README.md) "Contributing / re-verification"). This file is the other half:
the recorded, unfixed work between here and an artifact a third party can
adopt. Each row leads with its status, what it means for an adopter, and how
to check it; the treatment for each item and who it belongs to is recorded,
in full, in [ADOPTION_HISTORY.md](ADOPTION_HISTORY.md).

Nothing here is new information. Each row cites the canonical record; this page
exists because those records are scattered and a reader should not have to
assemble the list. Rows leave when the work lands, not when the wording
improves.

Each row below is the short form: its status, what it is and what it means for
you, and what to run to check it. The long-form record behind every row — each
correction, each reopening, each disclosed residual — is in
[ADOPTION_HISTORY.md](ADOPTION_HISTORY.md), one section per row, and the last
column of each row links to it. Nothing was dropped in the move.

**This page does not own hardening state.** The 2026-08-12 deep-scan
remediation — 99 findings, 86 verified live against current bytes, organised
into waves W1 to W7 — is tracked in an operator-workspace campaign ledger that
is **not published** ([WITHHELD.md](WITHHELD.md) records why, with the same
rule as every other withheld item: nothing published depends on it). What a
third party can read for the same state is published and self-contained: the
commit history of this repository, where each wave lands as a scoped commit whose
message names its findings; [ERRATA.md](ERRATA.md), which carries the
dispositions those waves produced (E12–E16 are this campaign's); and the
`findings/` trees under `second-implementation/`, `perf/sidecar/` and
`portable/`. Rows A4, A5 and A6 below describe part of the same finding set
through the Intake 10 cluster lens. A4's cluster C2 and A6's five supervision
bounds sit inside the still-open remainder of W5 and W6. No count of that
remainder is quoted here, because the only authority for one is the withheld
ledger and this paragraph would then promise checkability and immediately break
it. What is checkable is the shape of the blocker, and it is the same for most of
them: the repair would change bytes that a committed receipt records, so it needs
a designed evidence-regeneration event rather than an inline edit — the event
shape `ERRATA.md` E12 and E14 describe.

## Blocking for a third party

| # | Status | What it is, and what it means for you | How to check it | Canonical record, and the full history |
|---|---|---|---|---|
| A1 | **Closed** 2026-08-18 | A fresh clone of the default branch is what passes the gates: `hardening-industry-grade` was merged fast-forward into `main` and pushed, and the release is tagged `v1.2.1`. Verify that on your own clone rather than trusting this row. | `python -B portability/verify_live.py` on the clone; `git rev-list --left-right --count origin/main...HEAD` — expect `0	0` on a fresh clone of the default branch | [Full history: A1](ADOPTION_HISTORY.md#a1--what-a-fresh-clone-gives-you) |
| A2 | **Closed** 2026-08-19 | The hosted robustness matrix (three-OS x CPython 3.12/3.13/3.14) triggered on a branch that existed neither locally nor on the remote, so it ran only by manual dispatch; `conformance.yml` fires on every push and every pull request and was unaffected throughout, and `portability.yml` fires on `main` only. The trigger was retargeted to `main` — an edit that crossed a recorded owner gate and was ratified by the 2026-08-18 release — and hosted runs 32225089695 and 32270122137 completed green there on 2026-08-19, the first ever. The claim itself was never unverified — [portability/THIRD_PARTY_REPRODUCTION_20260818.md](portability/THIRD_PARTY_REPRODUCTION_20260818.md) is the clean-clone proof — but its multi-OS half rested on pinned hosted receipts from an earlier commit, and it is now recorded live. | the two workflow `on:` blocks under `.github/workflows/`; hosted `robustness-verification` runs 32225089695 (at `e27e331`) and 32270122137 (at `69853aa`) | [Full history: A2](ADOPTION_HISTORY.md#a2--the-hosted-robustness-gate) |
| A3 | **Open** — in flight, outside this repo | No conforming second implementation exists, so byte-parity is a property of the reference implementation against itself. Attempt 4 was refuted by `RI5.md` over 592 confirmed divergences across five independent mechanisms; three author strikes are recorded. This is the one row still open, and it bounds what may be claimed next, not what is claimed today. | nothing to run here — the live attempt is the B1 comparator packet lane, external to this repository | [ERRATA.md](ERRATA.md) E10, `orchestration/LEDGER.md`. [Full history: A3](ADOPTION_HISTORY.md#a3--a-conforming-second-implementation) |
| A4 | **Closed** 2026-08-19 | Every peripheral loader now ingests through one strict law, `portability/strict_ingest.py`, rather than a bare `json.loads` — four of four adoptable surfaces; the frozen second-implementation CLI is attempt evidence and cannot be adopted, as its history records. Adoption uses the law's safety half only (duplicate keys, non-finite constants, lone surrogates, the core's bounds), which all 69 published receipts satisfy, so it rejects nothing already shipped. | `python -B portability/test_strict_ingest.py` — 26 tests, which recompute the adopted surfaces from `git ls-files`; `python -B portability/verify_receipts.py` | `orchestration/robustness/INTAKE_10_SCAN_DISPOSITIONS.md` cluster C2; `portability/strict_ingest.py`. [Full history: A4](ADOPTION_HISTORY.md#a4--one-shared-strict-ingest-law) |
| A5 | **Closed** 2026-08-19 | Evidence harnesses resolved `git` and `docker` by bare name from the ambient `PATH`, so a receipt's commit provenance was only as trustworthy as the operator's `PATH` — a forged `git` made `verify_hygiene` report `HYGIENE_PASS` with custody 17/17 while a planted modification was still on disk. Eight of eight harnesses now resolve through `portability/pinned_tools.py`, which resolves tools inside an administrator-write-only directory named by `RR_TOOL_DIR` and refuses to fall back to `PATH`; this row was reopened twice on the way there, both times for the same reason — a control that had landed but was outside the decision path. With `RR_TOOL_DIR` unset the argv is byte-identical to today's, so this is hardening an operator enables rather than a migration the artifact performs, and that unset residual stays disclosed. | `python -B portability/test_pinned_tools.py` — 12 tests, which recompute the migrated harnesses from `git ls-files`; `python -B perf/sidecar/verify_receipts.py` — expect `checks=134 failures=0` | same file, cluster C5; the caveat itself is recorded in [TRUST_MODEL.md](TRUST_MODEL.md)'s boundary table. [Full history: A5](ADOPTION_HISTORY.md#a5--ambient-tool-resolution-in-the-evidence-harnesses) |
| A6 | **Closed** 2026-08-19 | Long-lived harnesses treated process-tree and deadline totality as local detail, and five bounds were disclosed as deliberately unrepaired. All five are now repaired in the bytes: the deadline covers the write phase, cleanup contains the process tree, stderr arriving after envelope correlation is charged to the interaction it belongs to, execution-input receipts pin file bytes at each read, and an LF-less flood raises `BatchRecordLimitError` at a physical-line ceiling. The four that moved receipt-pinned sources are recorded by the 2026-08-19 regeneration event. One residual stays disclosed: read-time pinning hashes every repository read inside every traced process, so regenerated profiling numbers are not comparable byte-for-byte with the 2026-08-12 numbers. | `python -B perf/sidecar/test_supervision_bounds.py` — expect `supervision bounds: checks=37 failures=0`; `python -B perf/sidecar/verify_receipts.py` — expect `checks=134 failures=0`, the regeneration event's custody; `python -B grounded-0_4/test_public_surface.py` — expect `PUBLIC-SURFACE PASS: 38 checks`, which pins the batch record limit | `perf/sidecar/findings/F-WP5-006.md`; same dispositions file, cluster C6. [Full history: A6](ADOPTION_HISTORY.md#a6--process-tree-and-deadline-totality) |
| A7 | **Closed** | The distribution is self-verifying rather than published: `generate_engine_manifest.py --stage` copies the eleven engine files into the package, `--verify-stage` re-checks the staged tree, and a wheel built from that staging, installed with no checkout beside it, verifies all eleven at import and refuses on drift. The supported integration mode today is an editable install from a checkout (`pip install -e .`); the staged wheel is the proven path beyond it. | `python -B receiver_reliance/generate_engine_manifest.py --check`; `--stage` then `--verify-stage` for the wheel path; `python -B receiver_reliance/test_engine_manifest.py`; the install-and-verify evidence is [portability/THIRD_PARTY_REPRODUCTION_20260818.md](portability/THIRD_PARTY_REPRODUCTION_20260818.md) | `pyproject.toml`; `receiver_reliance/engine_manifest.json`. [Full history: A7](ADOPTION_HISTORY.md#a7--a-self-contained-distribution) |

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
a census that finds no consumer outside the maintainer's control (re-run
2026-08-19; the page also records the sibling consumer its previous wording
denied), and records that the first external consumer — or any
embedding where handoff senders are adversarial to the receiver's own tooling —
promotes the deferred hardening set — A4, A5 and A6 here — to blocking work
before that embedding ships. **All three closed on 2026-08-19**, so the trigger
now finds that set satisfied in advance: A4 four of four surfaces on the shared
ingest law (`portability/test_strict_ingest.py`, 26 tests), A5 eight of eight
harnesses on `pinned_tools` with the `RR_TOOL_DIR`-unset residual still
disclosed (`portability/test_pinned_tools.py`, 12 tests), A6 five of five
supervision bounds repaired (`perf/sidecar/test_supervision_bounds.py`,
`checks=37 failures=0`). What firing the trigger promotes is therefore
re-verification of those three against the bytes a host actually embeds — run
the named suites on the clone — not work still to be done. Adopting this
artifact is exactly the event that fires it. A1 and A2 were the only rows that
blocked reproducing what is already claimed, and the 2026-08-18 publication
closed the first and ratified the second, so what a clone of the default branch
gives you now is what passes the gates. A3 is the one row still open, and it
bounds what may be claimed next, not what is claimed today.

`adapters/mcp/` is the first surface in this tree built to be wired into a stack
outside it, so it is where that trigger stops being hypothetical. It does not
fire on the commit: the gate is an in-repo consumer, verified by this
repository's own gates, and no outside party relies on it
([TRUST_MODEL.md](TRUST_MODEL.md)'s census now records it as an in-repo
consumer, and still finds none outside the maintainer's control). It fires when a host
wires the server into its own client, because that host is then the first
external consumer and its senders are by construction adversarial to the
receiver's tooling. A4, A5 and A6 — the rows that promotion names — all closed
on 2026-08-19, so what such a host owes is re-running their three proof suites
against the bytes it embeds rather than waiting on open work; the adapter's own
README restates this where a host will read it. The gate adopts the shared
ingest law at birth rather than inheriting a bare one, so it enlarges A4's
guarded set without enlarging A4's remainder.
