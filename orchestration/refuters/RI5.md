# RI5 second-implementation refutation — decisive round over attempt 4

## Verdict

**DIVERGENCE FOUND — the candidate does not conform. Third strike; the WP4
package falls back.** 592 confirmed conformance divergences over 4,992
executed differential probes (9,984 process executions) across ten probe
classes, in five independent mechanisms. Three sit inside the laws attempt 4
changed; the wrapper-format CLI rejection was resolved as chartered scope and
excluded from the count.

## Candidate and review base

- Branch: `sol/rr-robustness-20260811`, candidate HEAD `2306f73f96e9e6769287d90b5047e7b286fe02bd`
  ("second-implementation: attempt 4 — pooled lexicographic error selection
  and the empty-payload law (F-WP4-007)").
- Candidate surface: `second-implementation/rr2.py` via
  `second-implementation/cli.py execute` (stdin → stdout).
- Reference: the frozen composed 0.3 CLI,
  `baseline-run/implementation-output-0.3/pcb_runner.py execute`, executed
  solely as a black box.
- Refuter: fresh-context, author-separated, with no access to the author's
  probe design beyond the committed corpus it was required to go beyond.

## Method

Both CLIs ran as real subprocesses under CPython 3.12
(`-I -B -X pycache_prefix=<temp>`, per-process prefixes). A probe diverges iff
exit code differs, stdout bytes differ (SHA-256 compared), or
stderr-emptiness differs. Code reading generated suspicions only; every
counted finding was confirmed by an executed differential probe. The existing
corpus (test_cross probes and regressions, the 44-shape battery, the campaign
witnesses including identity 588) was enumerated first; counted probes are
novel.

## Probe inventory

| class | probes | divergences |
|---|---:|---:|
| b1 framing / emptiness / whitespace / NUL / CRLF / BOM / truncation | 993 | 0 |
| b2 bound-copy / registry-majority sweep | 2,048 | 478 |
| b3 member-deletion / type-corruption | 316 | 84 |
| b4 wrapper (scope-excluded, see below) | 1,072 | 1,048 excluded |
| b5 unicode / JCS / pointer-escaping / numbers / nesting / duplicates / base64 / request-id | 563 | 33 (30 counted) |

Counted total: 4,992 probes, 592 divergences. Per-probe JSONL receipts
(~29 MB) are retained by the operator off-repository; the minimized witness
set is committed under `orchestration/refuters/RI5-witnesses/` (raw input
bytes plus both arms' stdout for every named witness).

## Mechanisms

### DIV-001 — binding presence gate (pool membership under a missing member)

`rr2.py::_binding_failures` gates on a five-name presence tuple that omits
`inner_request` and `decision_input`. The reference's
`envelope_binding_errors` begins `inner = request["inner_request"]`: with the
member absent it raises `KeyError`, the whole binding pool is discarded, and
combinator-site suppression is disabled (suppression is guarded on a
non-empty binding pool). The two implementations then select their ERR_SCHEMA
pointer from different pools. Minimal reproducer, 223 bytes
(`RI5-witnesses/DIV-001-min_input.json`): reference pointer `""`, candidate
pointer `"/decision_input"`; stdout SHA-256 `BAA52EC9…29EAA` vs
`120BD0E7…A9916`, both exit 2. The full 651-byte fixture-derived witness and
both arms' stdout are alongside. Independently re-verified by the custodian
(same exits and hashes) before this report.

### DIV-002 — canonical registry-row derivation

The reference scores registry rows over five bound echo fields
(`/operation_handle`, `/obligation_id`, `/decision_input/operation_handle`,
`/decision_input/obligation_id`, `/inner_request/operation_handle`), so
obligation evidence can select the row, and it always returns a row (on a
total tie, the first registry row in UTF-8 order). The candidate takes a
plurality over the three `operation_handle` copies only, ignores obligation
evidence, and returns no row for a well-formed handle absent from the
registry — which empties its binding pool entirely. Divergence signature
distribution over the 2,048-probe sweep: 478 divergences, of which **239 are
fully digest-consistent, structurally complete requests** (nothing missing,
nothing stale). Three representative witnesses are committed
(`RI5-witnesses/DIV-002_witness_*.json`), e.g. reference pointer
`"/decision_input"` vs candidate `"/decision_input/obligation_id"`.

### DIV-003 — non-finite constants

`NaN\n` (4 bytes): reference `ERR_NUMBER`, candidate `ERR_JSON`. Same class
for `Infinity`, `-Infinity`, and an object-embedded non-finite constant.
Witnesses: `RI5-witnesses/DIV-003_*`.

### DIV-004 — ERR_NUMBER / ERR_JSON precedence inversion

For inputs violating both the canonical-form law and the number-domain law
(unsorted members carrying an out-of-domain number; escaped-key canonical
violations), the reference reports the canonical-form `ERR_JSON`; the
candidate's number check at `rr2.py` lines 807-814 preempts it and reports
`ERR_NUMBER`. Witnesses: `RI5-witnesses/DIV-004_*`.

### DIV-005 — duplicate keys carrying lone surrogates

Duplicate-member detection interacting with lone-surrogate escape sequences
diverges. Witness: `RI5-witnesses/DIV-005_dup_surrogate_*`.

## Wrapper thread — resolved as scope, not counted

On a valid fixture wrapper request the reference CLI returns exit 0 / PASS
while the candidate CLI returns exit 2 / `ERR_SCHEMA` at `/format_version`
(`rr2.py` line 828 rejects the wrapper format categorically at the CLI). The
candidate implements wrapper semantics at its Python API,
`second-implementation/test_cross.py` routes every wrapper arm through that
API rather than the CLI, and the candidate's own scope statement limits its
CLI to one semantic request. The 1,048 differing b4 probes (plus 3
wrapper-shaped b5 probes) are therefore excluded from the conformance count
as a chartered scope difference, with the executed evidence committed
(`RI5-witnesses/WRAPPER_probe_*`).

## Reading

The selection rule attempt 4 repaired — one pooled UTF-8-minimum over
equal-precedence schema errors — is implemented correctly in both arms. The
surviving defects are in **pool membership** (which errors exist to be
selected from) and **which registry row the pool is judged against**. The
entire pre-existing corpus passes because none of it varies bound-copy row
assignment or deletes a member while leaving a binding mismatch; fifty-five
pinning probes pinned selection, not membership.

## Round accounting

Fresh-context refutation rounds against an author-separated second
implementation, each ending in at least one confirmed executed divergence:
RI1–RI4 (pre-program, four minimized raw-ABI divergences), program cycle 1
(strike 1, ledger 2026-08-12 00:28 PDT), program cycle 2 (strike 2, ledger
2026-08-12 00:50 PDT), and this decisive round (strike 3). The hosted
coverage-guided campaign run of 2026-08-13 (run 31661587861, first divergence
at identity 588, `second-implementation/findings/F-WP4-007.md`) is counted as
a campaign run, not a refuter round.

## Consequence

Per the intake protocol's three-strike law the WP4 package takes its recorded
fallback: the attempt-4 candidate remains committed as a nonconforming,
receipt-bound best-effort record (its author receipt pins its bytes; it is
not admitted and carries no conformance claim), `REIMPLEMENTERS_GUIDE.md`
gains the newly pinned law surfaces, and the README keeps its
"a conforming second implementation still does not exist" wording with
updated counts. Worktree integrity held throughout: HEAD `2306f73` before and
after the round, `git status --porcelain` empty both times, and
`git diff 2306f73 -- second-implementation/` empty.
