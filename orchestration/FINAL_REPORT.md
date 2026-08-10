# Receiver-reliance continuation final report

Date: 2026-08-10

Integration branch: `sol/rr-continuation-20260810`

Baseline: `4a90f9ed043c446dadd7d6715863ba9b88ff2b0d`

Validated content through the completed campaign report:
`bdfd9f796a98d59b236760b1b273a3231850d647`. This report and the final
ledger close are the only later content changes.

## Verdict

**PASS for the adopted continuation changes, with explicit non-admissions.**
The final integration branch preserves every protected and sealed byte, passes
the expanded validation gate, fixes one audited-reference defect, adds a
bounded persistent NDJSON transport, folds audited classification into one
traced pass, and records the user-authorized 100,000-case campaign with zero
observed parity or invariant failures.

The independent second implementation and the proposed generation-0.5 drafts
are **not adopted**. Four successive independent-implementation refuters found
four distinct minimized raw-ABI divergences. Three specification refuters
closed earlier issues but left two byte-observable ambiguities. Those candidate
trees remain off integration.

This work does not establish efficacy, novelty, security, fuzzing
completeness, or external-standard conformance. The proof evidence tier remains
`internal held-out`; nothing in this run upgrades it.

## Per-goal outcomes

| Goal | Outcome | Primary evidence | Remaining uncertainty |
|---|---|---|---|
| Preserve the accepted 0.2/0.3 surfaces | PASS | frozen 0.2: 800/0; composed: 800/0 + 107/0; protected-path diff count 0 | local Windows/CPython coverage only |
| Strengthen gates | PASS | lint meta 7/0, properties 2,296/0, adversarial 6,497/0, proof 7/7, fuzz smoke 31/31 | seeded and fixture-bounded, not exhaustive |
| Resolve audited-reference defect | PASS | `exact_reference` now requires exact-key equality; 6,497 adversarial checks plus 976 RF1 probes | future schema keys still require review |
| Reduce integration cost | PASS for batch transport | corrected batch suite 2,160/0; RO2 no defect; 50,000-case paired campaign 0 failures | timing is host- and workload-specific |
| Remove duplicate audited classification work | PASS for work reduction | 1,142/0 equivalence checks; exact 116 of 1,060 predicate calls removed; RO3 no defect over 11,000 generated differentials | benchmark was neutral; no speedup claim |
| Large deterministic campaign | PASS at the user-reduced target | 100,000 seeded case identities; 67,599 unique raw byte strings; zero findings | not the handoff's original one-million target |
| Independent second implementation | REJECTED / NOT ADMITTED | 827 candidate checks plus candidate properties passed, but RI1-RI4 each found a minimized divergence | author-separated, not blind; seven descriptors were not executable requests |
| Proposed generation 0.5 | NOT ADOPTED | RSPEC, RSPEC2, and RSPEC3 reports | exact profile-id bound and compact error-pooling law remain unresolved |
| Documentation and runtime matrix | PASS | documentary audit; denominator corrected to 133/390 = 34.1%; CPython 3.12.10 and 3.14.5 matrix green | no Linux/macOS/ARM/CPython 3.13 run |

## Final expanded validation

The final campaign worktree ran the complete expanded gate after the 50,000
paired batch cases. Every command exited zero:

| Surface | Result |
|---|---:|
| Frozen 0.2 conformance | 800 checks, 0 failures |
| Composed 0.3 conformance | 800 + 107 checks, 0 failures |
| Grounded 0.4 regression | 504 checks, 0 failures |
| Contract lint | 0 findings across 199 required fields |
| Lint mutation meta-test | 7 checks, 0 failures |
| Seeded properties | 2,296 checks, 0 failures |
| Audited adversarial suite | 6,497 checks, 0 failures |
| Portable proof harness | 7 tests, all passed |
| Deterministic fuzz smoke | 31/31 strategies, 0 failures |
| Corrected batch regression and performance | 2,160 checks, 0 failures |
| Single-pass audited equivalence | 1,142 checks, 0 failures |

After adding only the campaign report, ledger close, and this final report,
the root custodian reran the same functional gate: all counts remained green;
the non-performance batch invocation reported 2,149/0; single-pass reported
1,142/0; `git diff --check` passed; and the protected-path diff was still zero.

The original four-command gate contributes 2,211 check observations
(`800 + 800 + 107 + 504`) plus lint. The integrated additive suites contribute
12,140 more (`7 + 2,296 + 6,497 + 7 + 31 + 2,160 + 1,142`), for 14,351
routine check/test observations plus lint. This count excludes refuter-only
probes, cross-interpreter repetitions, candidate-only tests, and the 100,000
campaign cases.

## Performance before and after

All timings are local observations, not portable budgets or causal component
estimates.

| Measurement | Workload | Result |
|---|---|---:|
| P1 `decide()` baseline | 124 semantic fixtures, 5 samples | 5.119398 ms/request median |
| P1 `decide_audited()` baseline | same | 5.288240 ms/request median |
| P1 frozen one-shot `-I -B` stdio | same | 154.984114 ms/request median |
| O1 corrected persistent batch | 124 fixtures, 3 paired samples | 5.305274 ms/request median |
| O1 same-run direct audited | same | 6.551335 ms/request median |
| O1 batch / direct | same | 0.809801x |
| O1 speedup vs P1 one-shot context | cross-run context | 29.213x |
| RO2 persistent batch | independent refuter run | 3.915655 ms/request median |
| RO2 same-run direct audited | independent refuter run | 5.244278 ms/request median |
| RO2 batch / direct | same | 0.746653x |
| B50 persistent batch | 50,000 unique requests | 2.16153881 ms/request |
| B50 same-run direct audited | same requests | 2.405233246 ms/request |
| B50 batch / direct | same run | 0.8986815784x |
| B50 fresh `rr_batch.py` process sample | 128 spaced requests | 95.56205 ms/request median |
| B50 persistent speedup vs its fresh sample | same candidate plan | 44.21019394x |
| B50 persistent speedup vs P1 frozen one-shot context | cross-run context | 71.70x |

The real-world win is process amortization. The single-pass change has an
exact work-reduction claim, not a speed claim: its final observational
optimized/legacy median was 1.008255x. Scheduler load, cache state, antivirus,
process startup, and the different corpora make cross-run timing comparisons
context rather than causal attribution.

## Campaign accounting

The throughput pilot remains a separately identified evidence tranche but is
counted inside the first 50,000 cases; it was not rerun or double-counted.

| Tranche | Seeded case identities | Runner/paired observations | Findings |
|---|---:|---:|---:|
| Pilot | 20,000 | 40,000 fresh runner executions | 0 |
| Stream A | 14,000 | 28,000 fresh runner executions | 0 |
| Stream B | 8,000 | 16,000 fresh runner executions | 0 |
| Stream C | 8,000 | 16,000 fresh runner executions | 0 |
| Reference half | 50,000 | 100,000 fresh runner executions | 0 |
| Paired batch half | 50,000 | 50,000 persistent responses matched to 50,000 direct audited responses; 128 fresh samples | 0 |
| **Aggregate** | **100,000** | two evaluated arms per scheduled case, plus 128 fresh samples | **0** |

The first half contains 50,000 distinct seeded identities but 17,599 unique
raw SHA-256 values because multiple strategies can converge on the same bytes.
The second half contains 50,000 raw-byte-unique requests and excludes every
first-half raw hash. The aggregate therefore contains **100,000 case
identities and 67,599 unique raw byte strings**.

Second-half identity and result evidence:

- first-half ordered identity root:
  `0B40CC2963B56770909650D006CCE89EBC5DBF4534942E62FD91797820BA2090`;
- second-half ordered candidate root:
  `9F46680E1D7D0006126ACB046F6CB0EC0CC3EA1CDA094FC8B1A484489B056B20`;
- second-half execution-chunk root:
  `4CD27BA5EEF94C24824C3EE019AF6763958090D92132770E231E646A6FEB2968`;
- uncommitted checkpoint SHA-256:
  `AEA89922596B2CCD68ADEC5EF23E7DE3EAED758C270FD8F04351389B9268AC86`;
- 50/50 chunks and 128/128 fresh samples passed; persistent parity failures
  were zero; worst observed child peak working set was 22,671,360 bytes.

No raw corpus, stdout, stderr, or checkpoint was committed.

## Independent implementation result

The author-separated implementation reached its own reported 827/827 total:

- 124 semantic fixture entries;
- 248 wrapper arms;
- 416 executable competence cases;
- 20 negative cases;
- 12 metamorphic relations; and
- 7 descriptor-only supplemental cases adjudicated from fixture metadata,
  not executed as materialized requests.

It additionally passed candidate-local raw-order, surrogate, and duplicate
property suites. That evidence did not overcome four independent minimized
counterexamples:

1. RI1: RFC 8785 UTF-16 member ordering divergence;
2. RI2: escaped lone-surrogate classification and a key-path crash;
3. RI3: duplicate-key precedence lost when the terminal LF is absent; and
4. RI4: ordinary incomplete duplicate-key pointer `/a` instead of the frozen
   empty pointer.

The candidate is therefore rejected and absent from the integration tree.
This result is useful negative evidence about reimplementation sensitivity,
not a claim of independent confirmation.

## Rejected, corrected, and stood-down work

- The first O1 batch candidate was rejected because it treated partial sink
  writes as success and used unbounded line acquisition. The corrected version
  loops over counted writes, bounds acquisition, drains/hashes oversized lines,
  and passed RO2; only the corrected version is integrated.
- The independent implementation was corrected three times and rejected a
  fourth time for the four divergences above. No version is integrated.
- Generation-0.5 proposal round one had three blockers; round two had five;
  round three closed those five but retained two byte-observable ambiguities:
  no exact `applicability_profile_id` bound/pattern and conflicting compact
  error-pooling/phase-selection rules. Drafts are not integrated or adopted.
- P1's first stdio profile omitted required isolated mode. It was superseded
  by a fresh `-I -B` run; only corrected numbers are reported.
- Three Terra campaign experiments completed zero durable cases and were
  stopped at the user's direction. Their reports and states are not adopted.
- O2 fast validation was paused and then explicitly stood down under the
  handoff's budget-priority rule. O4 authority-load optimization was not
  started. P1's 10.8239 ms application-cache-cold authority measurement
  remains the baseline. These items are recorded rather than silently omitted.
- O3 is admitted for parity and exact work reduction. Its effectively neutral
  timing is not presented as an optimization win.

## Ledger and change control

The final ledger contains 38 worker/campaign/review entries. The adopted run
used one-writer worktrees and root-only cherry-picks. Before this close report,
the baseline-to-integration diff contained 43 files, 10,225 insertions, and 43
deletions. Protected-path diff count was zero for:

- `baseline-run/control/`, `baseline-run/fixtures/`, and
  `baseline-run/receipts/`;
- frozen 0.2/0.3 implementation output;
- `supplemental-0_3/` and `access/`; and
- `ACCEPTANCE.md`, `EXAMPLE.md`, `.gitattributes`, and `LICENSE`.

Nothing was pushed. No dependency, workflow, remote, or sealed artifact was
changed. The proof extractor was not run against the workspace.

One custody incident is explicitly recorded in RI4: its setup command briefly
placed four candidate cherry-picks on the integration ref instead of the RI4
worktree. The worker restored the integration ref and tree with an expected-old
guard before any root integration resumed; root independently verified the
exact pre-incident SHA and a clean tree. No candidate bytes from that incident
remain in the final integration history.

## Open with James

1. **Push/review:** decide whether to push
   `sol/rr-continuation-20260810` and open a review. No remote action has been
   taken.
2. **Privacy:** review the documentary reports and local campaign provenance
   before any cloud upload. Do not upload secrets, excluded proof-workspace
   material, withheld toolchain bytes, or uncommitted campaign checkpoints.
3. **CI proposal:** consider the exact expanded gate plus the 31-strategy fuzz
   smoke and a 1,000-case batch self-test for routine CI. Keep the full 100,000
   campaign as scheduled evidence rather than a per-change gate.
4. **A1 floor:** decide whether the repository should publish or ratify the A1
   evidence-floor language. This run does not make that publication decision.
5. **Generation 0.5:** resolve the two RSPEC3 wire ambiguities before another
   author/refuter cycle. Do not adopt the current drafts as normative text.
6. **Optional optimization:** decide whether O2 or O4 warrants a later bounded
   run. Correctness and batch amortization are already established locally;
   neither lane is required for this close.
7. **Next evidence tier — Trusted Access for Cyber / Codex Cloud:** use the
   final integration SHA as a read-only adversarial target after privacy review.

### Trusted Access stress-test brief

The cloud task should be a fresh-context refuter, not an auto-fix pass:

- clone or upload only the reviewed repository bytes at the pinned final SHA;
- forbid remote writes, pushes, workflow changes, dependency installation,
  access to secrets, proof-workspace extraction, and protected-path mutation;
- run the complete expanded gate first and record environment/tool versions;
- stress raw UTF-8/JSON/JCS handling, UTF-16 ordering, escaped surrogates,
  duplicate/error precedence, exact error pointers, seals, and final-LF rules;
- stress persistent batch framing, partial/zero writes, backpressure, huge-line
  memory bounds, EOF/CRLF boundaries, concurrency, and request statelessness;
- differential every candidate response byte, exit, stderr, and receipt against
  the accepted reference behavior;
- stop on the first credible divergence and return the smallest reproducer,
  raw-input hex and SHA-256, exact expected/actual bytes and hashes, exit/stderr,
  environment, determinism replay, and resource observation; and
- route any proposed fix to a separate author, then a separate fresh-context
  refuter. Do not let the discovery task silently modify the target.

That run could materially broaden adversarial search and platform variance,
but it would still be scoped evidence rather than a security or completeness
certification.
