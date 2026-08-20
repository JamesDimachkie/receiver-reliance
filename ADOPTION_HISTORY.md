# Adoption ledger — the full record, row by row

[ADOPTION.md](ADOPTION.md) is the ledger a third party reads to find out what
is open, what closed, and what to run. This page is its other half: the
complete record behind each row — every correction, every reopening, every
disclosed residual, and every self-criticism those rows carried.

Nothing here is new information and nothing was rewritten in the move. Each
section below carries the four cells its row held in ADOPTION.md's table —
blocker, canonical record, treatment, owner — as they stood on 2026-08-19,
under those same four labels; the only change is line wrapping. Dates inside a
section belong to the events that section names, and the section as a whole
reads as of 2026-08-19.

| Row | Section | Status |
|---|---|---|
| A1 | [What a fresh clone gives you](#a1--what-a-fresh-clone-gives-you) | closed |
| A2 | [The hosted robustness gate](#a2--the-hosted-robustness-gate) | closed |
| A3 | [A conforming second implementation](#a3--a-conforming-second-implementation) | in flight, outside this repo |
| A4 | [One shared strict ingest law](#a4--one-shared-strict-ingest-law) | closed |
| A5 | [Ambient tool resolution in the evidence harnesses](#a5--ambient-tool-resolution-in-the-evidence-harnesses) | closed |
| A6 | [Process-tree and deadline totality](#a6--process-tree-and-deadline-totality) | closed |
| A7 | [A self-contained distribution](#a7--a-self-contained-distribution) | closed |

---

## A1 — What a fresh clone gives you

**Blocker**

~~What `git clone` gives you is not what passes the gates.~~ **Closed
2026-08-18 by publication.** `hardening-industry-grade` was merged
fast-forward into `main` and pushed, and the release is tagged `v1.2.1`.
`HYGIENE_PASS`, the 517-check grounded regression (521 since 0.4.2 sealed the
decision table — ERRATA E18), the 267 receipt checks (297 since the charter
gate grew from eleven commands to nineteen and Event B bound the two
regeneration receipts), the withdrawal of the bare `decide` route, the
reconciled 100,000-identity figure, the shared bounded-ingest law, the
recompute verifier and the self-verifying distribution are all true on the
default branch a third party clones.

**Canonical record**

`git rev-list --left-right --count origin/main...HEAD` — expect `0	0` on a
fresh clone of the default branch

**Treatment**

Merged and published; verify with `python -B portability/verify_live.py` on
the clone rather than trusting this row.

**Owner**

**closed**

---

## A2 — The hosted robustness gate

**Blocker**

The hosted robustness gate could not fire.
`.github/workflows/robustness-verification.yml` triggered on
`sol/rr-robustness-20260811`, a branch that exists neither locally nor on the
remote, so its three-OS x CPython 3.12/3.13/3.14 matrix and the WP4 campaign
ran only by manual dispatch. `portability.yml` triggers on `main` only.
`conformance.yml`, the third workflow, triggers on every push and every pull
request and is unaffected by any of this — it is the only gate that has always
run on the hardening branch. The claim itself was never unverified — see
[portability/THIRD_PARTY_REPRODUCTION_20260818.md](portability/THIRD_PARTY_REPRODUCTION_20260818.md)
for a clean-clone reproduction on CPython 3.12, 3.13 and 3.14 — but that run
is Windows-only, so the multi-OS half rests on pinned hosted receipts from an
earlier commit.

**Canonical record**

the two workflow `on:` blocks

**Treatment**

The robustness trigger was retargeted to `main`, which is also the only branch
`portability/sandbox/run_sandbox.py` accepts as release authority. **That edit
was made directly, crossing a recorded owner gate** — the campaign's operating
law reserves `.github/workflows/**` edits to the repository owner and routes
them through a separate worktree lane. (That law lives in the withheld
campaign ledger, so this row states the fact and does not cite an unpublished
file as its authority; [WITHHELD.md](WITHHELD.md) records the class.) It is
**ratified by the 2026-08-18 release**, named as one of that authorization's
three explicit inclusions; the routing law is unchanged and stands for every
future `.github/workflows/**` edit. `portability.yml` was left alone because
the matrix suite pins its trigger block byte-exactly. The multi-OS half closed
on 2026-08-19: hosted `robustness-verification` runs 32225089695 (at
`e27e331`) and 32270122137 (at `69853aa`) completed green on `main` — the
first ever, because ERRATA E17's ambient-variable validator had failed every
cell until it was fixed in the same commit the first green run validated.

**Owner**

**closed** — trigger ratified, hosted multi-OS runs recorded

---

## A3 — A conforming second implementation

**Blocker**

No conforming second implementation exists. Attempt 4 was refuted by `RI5.md`
over 592 confirmed divergences across five independent mechanisms; three
author strikes are recorded. The author-increment receipt's `campaign_gate` is
still `DEFERRED_PENDING_FRESH_CONTEXT_REFUTER_ZERO_DIVERGENCE` and its status
string is stale, both recorded in [ERRATA.md](ERRATA.md) E10. Until one
exists, byte-parity is a property of the reference implementation against
itself.

**Canonical record**

[ERRATA.md](ERRATA.md) E10, `orchestration/LEDGER.md`

**Treatment**

The live attempt is the B1 comparator packet lane, external to this
repository: an unexposed implementer receives an eleven-file public projection
and must clear 907/907 in-process and subprocess conformance, the 30-row
372-check composed gate, and a candidate-unchanged predicate.

**Owner**

in flight, outside this repo

---


**Dated correction, 2026-08-20 (appended; nothing above rewritten).** Two
present-tense statements in this section were true when written and are
stale as of this date: "The live attempt is the B1 comparator packet lane,
external to this repository" and the status phrase "in flight, outside
this repo" (the same phrase stands in this file's top index row for A3,
kept there as a record). The B1 comparator lane's current generation has
no scheduled attempt. The live row
(`ADOPTION.md` A3) now reads "Open — no attempt scheduled." This page is a
record; the sentences above keep the wording they had when the events they
describe happened.

## A4 — One shared strict ingest law

**Blocker**

~~Peripheral loaders do not all share the core's one strict ingest law.~~
**Closed 2026-08-19 — four of four surfaces adopted.**
`portability/verify_receipts.py` (twelve sites), the `portability/live`
transport (controller and worker, three sites), the `portability/matrix`
verifier (two sites), and the `portable/` offline bundle (`verify_bundle.py`,
`gate.py`, `cli.py` — four sites) all ingest through
`portability/strict_ingest.py`. The shared law gained numeric-fidelity
passthrough (`parse_float`/`parse_int`) so the matrix verifier keeps Decimal
evidence without restating the law, and every adopter keeps the dimension it
was already stronger in: the matrix loader its byte-size admission and lexical
structure preflight, `verify_bundle.py` its lexical depth-and-balance scan
ahead of the parser, `cli.py` its pre-allocation manifest ceiling.

**Canonical record**

`orchestration/robustness/INTAKE_10_SCAN_DISPOSITIONS.md` cluster C2;
`portability/strict_ingest.py`

**Treatment**

`portability/strict_ingest.py` is the shared law, with its nesting and member
ceilings **read from the frozen core** rather than restated, and a test that
fails if the module hardcodes them. It deliberately separates two halves,
because measurement showed they differ against bytes already published:
**safety** (duplicate keys, non-finite constants, lone surrogates, the core's
bounds) which all 69 published receipts satisfy, and **framing** (one trailing
LF, no BOM, no CR, NFC) which three deliberately-CRLF receipts violate under
`* -text`. Adoption uses safety only, so it rejects nothing shipped;
`verify_receipts` still reported its then-pinned `checks=193 failures=0`.
Before adoption its bare `json.loads` silently accepted duplicate keys, `NaN`,
`Infinity`, lone surrogates, 200-deep nesting, CRLF and missing trailing LF on
receipts produced by hosted CI on other machines. **Correction to the C2
disposition: the "second-implementation CLI" it names cannot be adopted at
all.** `verify_artifacts.py`, `rr2.py` and `cli.py` are among the 25
`candidate_files` of the frozen author-increment receipt, and
`verify_artifacts.py` verifies `author-file-hash` for every candidate row
including its own path — editing it breaks its own check against a published
receipt pinned in three custody surfaces. It is frozen attempt evidence, not
live infrastructure. **Phase 2's hard part was self-containment, and it was
answered by declaration, not by a copied constant.** `portable/` is an offline
bundle whose file set is `portable/inventory.json`; the law reads its ceilings
from the frozen core at
`baseline-run/implementation-output-0.3/b1_capabilities.py`, which the
inventory already declared, so declaring `portability/strict_ingest.py`
alongside it makes the law resolve inside the bundle with nothing restated.
The manifest moved from 60 files to 61 (22 runtime), and
`strict_ingest.CORE_PATH` now names the frozen core publicly so the bundle
authenticates the core it executes without restating that path either.
`cli.py` is the one site where the load order had to change, and it says so
rather than hiding it: the manifest index byte-authenticates every declared
module, and the index is itself now admitted under the law, so the law's own
bytes are the single pre-index bootstrap. They are re-checked against their
declared manifest rows the moment the index exists — before any other
repository module loads and before any command runs — so an undeclared or
altered law stops the process at import.

**Owner**

**closed** — four of four adopted (2026-08-19), the bundle re-bound at 61
files, and the three `portable/*` exemptions deleted rather than left
satisfied; adoption is enforced by recompute —
`test_strict_ingest.AdoptionIsComplete` enumerates the adopted surfaces from
`git ls-files`, holds an empty exemption set, and fails on any bare
`json.loads(` in them, on any exemption that stops describing its file, on the
three bundle files dropping out of the enumeration, and on the bundle ceasing
to declare either the law or the frozen core it reads;
`second-implementation/*` is not edited as live infrastructure — the W3/W4
hardening changes applied to the candidate itself are recorded in
[ERRATA.md](ERRATA.md) E10

---

## A5 — Ambient tool resolution in the evidence harnesses

**Blocker**

Evidence harnesses resolve `git` and `docker` by bare name from the ambient
`PATH` in seven files, so a receipt's commit provenance is only as trustworthy
as the operator's `PATH`. Environment passthrough and unverified sandbox
reporting are the same cluster.

**Canonical record**

same file, cluster C5; the caveat itself is recorded in
[TRUST_MODEL.md](TRUST_MODEL.md)'s boundary table

**Treatment**

The disclosure half is already done and checks out: the boundary table records
ambient-authority residue as a caveat rather than a defended boundary, and all
49 receipt JSONs under `portability/receipts/` outside `hosted/MANIFEST.json`
do carry host, platform or runner identification, so the claim that receipts
scope themselves to the recorded host is verifiable and true. What remains is
the hardening half: resolve every tool through an absolute path, scrub the
environment, and verify sandbox fields instead of reporting them. **Both
halves are now done, and the choice between the two candidate fixes was
settled empirically rather than by argument.** A verification lane forged a
`git` binary: `verify_hygiene` reported `HYGIENE_PASS` with custody 17/17
while the planted modification was still on disk, two forged calls turned a
receipt gate from `FAIL` to `PASS` against a forged HEAD, and
`shutil.which("git")` resolved to the forgery — confirming `which` was never a
defence. Of the two candidates, the per-receipt resolved path was rejected: it
is a record rather than a control, and it re-digests every SHA-pinned receipt
for zero prevention. `portability/pinned_tools.py` implements the other:
`RR_TOOL_DIR` resolves tools to absolute paths inside an
administrator-write-only directory and refuses to fall back to `PATH`, while
an unset variable leaves the argv **byte-identical to today's**, so no receipt
digest moves and hardening is something an operator enables rather than a
migration the artifact performs. **Correction, and the reason this row was
reopened:** landing the module was not adopting it. `pinned_tools` was called
from nowhere for four commits, so every harness still built its argv from a
bare name and the three scan findings that name those call sites
(`csf_d5b39499`, `csf_16f2cc06`, `csf_211167ec`) stayed live while the module
and its tests were green — a control outside the decision path. **Correction,
and the second time this row has been reopened for the same reason.** A5 read
**closed** while three harnesses had never migrated at all — and the guard
cited as proof could not see them, because `test_pinned_tools.py` iterated a
hardcoded five-file list instead of enumerating the tree. `perf/profile.py`
and `proof/extract_corpus.py` were migrated first (neither was pinned by
anything). `perf/sidecar/_evidence.py` was the worst of the three and the last
to go: its `_git()` writes the `head`/`clean`/`status_sha256` provenance block
into both admitted WP5 receipts, which is precisely the defect this row's
blocker names. It is pinned by seven `perf/receipts/robustness/*` receipts and
by the portable manifest, so migrating it moves recorded evidence — which is
why it waited for the evidence-regeneration event rather than for a quieter
moment. **It is now migrated, inside that event rather than instead of it.**
The event is recorded: `perf/sidecar/verify_receipts.py` failed on the moved
source pin (enumerated in `perf/SIDECAR.md`) until the 2026-08-19 regeneration
admitted fresh receipts at the migrated bytes, and now reports
`checks=134 failures=0`; the boundary the exemption named was crossed
deliberately, with the disclosure landing in the same change as the move. It
imports `pinned_tools` inside `_git()` rather than at module scope, because
the file is a declared runtime member of the `portable/` bundle and
`portability/pinned_tools.py` is not; the reason is recorded at the import,
and no bundle command reaches that function. The guard now recomputes from
`git ls-files` and fails on any undeclared bare-tool file or any exemption
that has gone stale, with both arms negative-tested. It detects two shapes,
because the first revision saw only one: an argv literal, and a bare tool name
produced for an argv some other way — a `return "git"` fallback or a module
constant. The second shape was introduced by the same commit that wrote the
guard, and the guard could not see it, which is the failure this gate exists
to prevent and is recorded here rather than quietly repaired. Nineteen call
sites across eight production harnesses now resolve through it (`run_sandbox`
alone accounts for eleven): `verify_hygiene`, `run_local_expanded_gate`,
`concurrency/ladder`, `matrix/receipt`, `sandbox/run_sandbox`, `perf/profile`,
`perf/sidecar/_evidence` and `proof/extract_corpus`. 12 regression cases pin
both halves plus the adoption itself, including one that fails if any harness
reverts to a bare name. Adopting it moved `ladder.py`'s bytes, which are a
published receipt source pin, and the E12 guard refused the change until that
second move was disclosed; `ladder.py` was adopted rather than exempted
because its `git` call is provenance evidence for the concurrency receipts.
Disclosure remains the floor and `TRUST_MODEL.md` now carries the
demonstration: the trust root moves from `PATH` to configuration, it does not
vanish, and a receipt is not evidence its host was sound.

**Owner**

**closed** — eight of eight harnesses migrated, the guard recomputing from
`git ls-files` with one design-reasoned exemption (`proof/extract_corpus.py`),
and the 2026-08-19 WP5 regeneration records the migration in admitted receipts
(profile attempt8, parity attempt11 as first recorded; superseded the same day
by profile attempt9 and parity attempt12 at the total-redactor bytes, which
are what `ADMITTED` names at this tip; `perf/sidecar/verify_receipts.py` 134/0
either way). The `RR_TOOL_DIR`-unset residual stays disclosed.

---

## A6 — Process-tree and deadline totality

**Blocker**

Long-lived harnesses treat process-tree and deadline totality as local detail.
Five bounds were disclosed as deliberately unrepaired. **All five are now
repaired in the bytes; what is outstanding is the evidence that records four
of them.** Repaired now: the deadline covers the write phase, so a child that
never reads can no longer hold the writer in a blocking write; cleanup
contains the process tree through a Windows job object or a POSIX process
group, so grandchildren no longer survive it; stderr arriving after envelope
correlation is charged to the interaction it belongs to, with a `retroactive`
adjudication row, instead of surfacing on the next interaction or only at
`stop(check=True)`; execution-input receipts pin file bytes at each read
rather than at manifest time. Repaired earlier: ~~an LF-less flood costs
bounded memory but unbounded work~~ — `grounded-0_4/rr_batch.py` has carried a
134,283,264-byte physical-line ceiling since `5946e4c`, raising
`BatchRecordLimitError` and answering with exactly one sealed
`ERR_BATCH_RECORD_LIMIT` response, so one-response-per-line consistency is
kept rather than broken.

**Canonical record**

`perf/sidecar/findings/F-WP5-006.md`; same dispositions file, cluster C6

**Treatment**

The four bounds were bounded changes to `perf/sidecar/supervised_client.py`
(job-object or process-group containment, a write-phase deadline, retroactive
stderr adjudication) and to `perf/sidecar/_trace_exec.py` with
`perf/sidecar/_evidence.py` (read-time pinning). This row used to name
`rr_sidecar.py`; the supervision shape all three of the first bounds describe
lives in the client, not in the 82-line launcher. **They were blocked by one
mechanical boundary, the block was enforced rather than asserted, and the
change crosses it deliberately rather than waiting it out.** Each of those
files is pinned byte-exactly in the `source_sha256` map of an admitted WP5
receipt with no errata row — `supervised_client.py` by
`sidecar-parity-windows-cpython-3.12-20260812-attempt10.json`,
`_trace_exec.py` and `_evidence.py` by both admitted receipts — so
`python -B perf/sidecar/verify_receipts.py` fails the instant any of them
moves and `portable/gate.py` goes red with it. It did exactly that —
`checks=133 failures=7`, enumerated in `perf/SIDECAR.md` while the red stood,
because E14's lesson is that an undisclosed red gate is the defect, not the
red itself. Read-time pinning also moved the execution-input manifest schema
from `receiver-reliance/wp5-complete-execution-input-manifest-1` to `-2`,
which `verify_receipts` now requires along with `input_pin_time: "read"` and
`read_pinned_events == repo_open_events`. **No `SOURCE_PIN_ERRATA` row was
added for these seven.** E14 rows exist for sources the campaign changed and
never intends to re-run; these are changed precisely so a fresh run can be
recorded, and an erratum row would convert a scheduled event into a permanent
disposition. That event is recorded (2026-08-19): a fresh profiling and parity
run on this Windows CPython 3.12 host — `profile-…-attempt8.json`,
`sidecar-parity-…-attempt11.json` — with `ADMITTED`, the inventory and the
manifest rebound, the event shape [ERRATA.md](ERRATA.md) E12 and E14 describe,
shared with A5's last migrated harness (`perf/sidecar/_evidence.py`, the same
file). The repairs do not wait for it to be checkable:
`perf/sidecar/test_supervision_bounds.py` reports
`supervision bounds: checks=37 failures=0`, and every bound carries an arm
that fails without its repair — the write deadline must fire on a deaf child
and must NOT fire when the same child accepts a request that fits the pipe
buffer; a grandchild dies with the supervised tree and demonstrably survives
the `Popen.kill()` supervision used to do instead; late stderr is charged to
interaction N while in-flight stderr is charged to N as non-retroactive; and a
read-time pin that disagrees with the manifest-time bytes, two reads that
disagree, and a read with no pin each stop collection. One further disclosure
belongs to bound 5 rather than to the event: read-time pinning hashes every
repository read inside every traced process, so regenerated profiling numbers
include that cost and are not comparable byte-for-byte with the 2026-08-12
numbers. **Bound 4's closure is recorded rather than quietly dropped**,
because the reason it went stale is itself the finding: the repair landed
inside the window E14 documents, when `perf/sidecar/verify_receipts.py` was
exiting 1 undisclosed and nothing was reporting the state of these files. Its
enforcement is `grounded-0_4/test_public_surface.py`, which asserts the exact
bounded read count (`_MAX_PHYSICAL_LINE_BYTES // _READ_CHUNK_BYTES + 1`) and
the deterministic `ERR_BATCH_RECORD_LIMIT` outcome;
`PUBLIC-SURFACE PASS: 38 checks`.

**Owner**

**closed** — five of five bounds repaired in the bytes, proven by
`perf/sidecar/test_supervision_bounds.py` (37 checks, negative arms), and
recorded by the 2026-08-19 regeneration event (`verify_receipts` 134/0 over
the fresh receipts). Bound 4 closed 2026-08-15, disclosed 2026-08-19.

---

## A7 — A self-contained distribution

**Blocker**

~~There is no self-contained distribution yet. `pyproject.toml` still declares
one integration mode, an editable install from a checkout.~~ **Closed** —
struck rather than deleted, in the same style as A1.

**Canonical record**

`pyproject.toml`; `receiver_reliance/engine_manifest.json`

**Treatment**

**Authority decision made: the repository stays authoritative and the
installed copy proves it holds the published bytes.** Half of this row is now
closed. `receiver_reliance/engine_manifest.json` pins all eleven engine files
by byte length and SHA-256 under a self-zero seal; importing the package
verifies every one before executing any of them and refuses to import on
drift; `generate_engine_manifest.py --check` fails on unrecorded engine
change, and `test_engine_manifest.py` proves the check fires — one appended
byte in any of the eleven, an absent file, an absent manifest — and that the
bundled `_engine/` layout imports without a checkout beside it. The closure
was DERIVED by tracing what the process opens, not by reading imports: a
hand-written list missed four files, so an earlier revision of this row
claimed 302,260 bytes across seven files when the engine is really **eleven
files**, three of them B1-pinned frozen authority. The byte total is
deliberately not asserted in the present tense here, for the same reason the
wheel size below is not: it moves with the engine bytes. It was 1,182,122 when
this row was written and at the 2026-08-18 third-party reproduction;
`0ff243c`/`5073238` sealed the decision-table contracts into the audit path
and took it to **1,183,665**, which `receiver_reliance/engine_manifest.json`
records as `total_byte_length` and
`python -B receiver_reliance/generate_engine_manifest.py --check` recomputes.
Packaging is done too: `--stage` copies the eleven into
`receiver_reliance/_engine/` (gitignored, so the repository stays the only
committed authority), `--verify-stage` re-checks the staged tree, and the
resulting wheel (a byte size is deliberately not quoted here: `pyproject.toml`
embeds `README.md` in wheel metadata, so the figure moves with the prose and
the two published measurements, 161,426 and 161,988, are both already stale)
installed into a virtual environment with no checkout beside it verifies all
eleven files at import, reports the repository's own manifest digest, returns
`VALID` on `examples/handoff-clean.json` with four governing authorities
pinned (the 0.4.1 format current at that run; the 0.4.2 format seals six —
ERRATA E18), and refuses to import when one byte is appended to a policy file
inside `site-packages`. Evidence:
[portability/THIRD_PARTY_REPRODUCTION_20260818.md](portability/THIRD_PARTY_REPRODUCTION_20260818.md).

**Owner**

**closed**
