# Adversarial review and acceptance record

The reference implementation in `baseline-run/implementation-output-0.2/`
reached acceptance through ten adversarial rounds of author-separated
review — by a different AI reasoning lane from the one that authored the
implementation — under a fixed, read-only charter. Each round
independently: reproduced both conformance modes, re-derived every
content-addressed digest, and ran self-designed adversarial probes against
the *contract text* that the frozen fixture packs cannot reach. Every valid
finding was fixed and pinned as a permanent regression case before the next
round.

To be precise: the reviewer's formal verdict in every round, including
round 10, was REJECT-with-findings. It never issued a sign-off. Acceptance
is the implementing lane's convergence claim under a pre-stated stopping
rule: the final, heaviest round found zero implementation defects, and its
sole finding was adjudicated against the contract's pinned text as a
contract-design non-closure (below) rather than an implementation defect.

What is independently checkable from this repository is the final
accepted state: the digests below, and the suite that reproduces them.
The round-by-round record is the authoring lanes' internal history,
disclosed and summarized here, not independently verifiable from these
bytes alone.

## Final accepted state

- Implementation manifest self-zero SHA-256:
  `5F3A7CE04F9D92035525025C4C464CD4F5E3D644B2CAA42A0975A2176919C2C6`
- Build-receipt self-zero SHA-256:
  `7518F55FB61BBC4965BAF6725998AF36E47A22005A3F0702638EB83CD68458B1`
- Conformance: 798 checks green, in-process and pinned-toolchain
  subprocess-ABI. The 720 fixture-pinned checks were byte-identical in
  every round; only harness closures and the implementation grew.

## Round-by-round

| Round | Reviewer probes | Findings | Valid impl defects fixed | What the round hit |
|---|---|---|---|---|
| 1 | 47 | 4 | 4 | RFC 8785 UTF-16 member ordering (CRITICAL), negative-zero model, combined-error precedence, recursive JSON equality |
| 2 | 29 | 2 | 2 | duplicate-key + trailing-byte precedence, joint schema/binding error pool |
| 3 | 29 | 2 | 2 | LF-framing gate ordering, root-type vs resource-limit precedence |
| 4 | 33 | 1 | 1 | echo-only suppression in the joint pool (mixed schema+binding) |
| 5 | 30 | 5 | 2 (+1 partial) | canonicality vs number model, limit/schema pooling, echo tie-break, wrapper pool — plus 2 findings **refuted** against pinned bytes |
| 6 | 50 | 3 | 3 | surrogate-key canonical shadow, recursion-abort error pooling, integer-digit-cap as number model |
| 7 | 65 | 4 | 4 | class-precedence short-circuit, iterative pointer-accurate profile scanner, strict transcript wire-parsing |
| 8 | 138 | 1 | 1 | surrogate-total selection ordering (100k randomized grammar diffs, scanner held) |
| 9 | 29 | 3 | 3 | unhashable-selector guards, response-family-preserving internal-error and output-cap containment |
| 10 | 45 | 1 | 0 | no implementation defect under 70k+ fuzzed inputs; sole finding ledgered as a contract non-closure |

Totals (sum of the rows above): 26 findings raised, of which 22 were valid
implementation defects (all fixed and pinned), 1 partial, 2 refuted against
the contract's own pinned bytes, and 1 ledgered as a contract-design
non-closure. A second non-closure (the pointer-cap conflict, below) was
recorded from round-9 analysis without being tallied as a finding.
Reviewer precision fell as real defects thinned (rounds 1–4: 9 of 9 valid;
round 5: 2 of 5; round 10: 0 of 1), the expected convergence signature.

## Recorded contract-design non-closures (not implementation defects)

1. **Pointer-cap conflict.** Exact RFC 6901 error pointers on pathological
   deeply-nested inputs can exceed the wrapper response schema's
   240-character pointer cap. No implementation can satisfy both frozen
   clauses for that input class; this is a conflict between two contract
   clauses, independently confirmed by the reviewer.
2. **Wrapper transcript semantic binding.** The wrapper transcript-binding
   evaluator's frozen 12-step specification checks schemas, envelope
   bindings, echoes, and seals, but does not re-derive the response's
   classification (the core transcript evaluator does). A well-sealed
   response whose class contradicts its request passes the wrapper
   evaluator. Verifying a recorded wrapper triple semantically requires
   re-running the reference implementation or using the core evaluator.

Both are candidates for a future contract revision.

## Supplemental 0.3 generation — acceptance chain

The 0.3 generation (two operations closing the reviewed capability gaps,
plus nonempty retrieved-content coverage for OBL-22) carries its own
acceptance chain. The 0.2 receipts above are not inherited by it.

**Independent fixture acceptance — PASS at round 2.** An author-separated
reviewer lane re-derived every expected output from the frozen contract
bytes with its own evaluator and canonicalizer. Round 1 returned FAIL with
two valid blockers: the composed wrapper response and transcript schemas
still bound only 28 operations through a third binding-chain shape the
author's derivation had missed, and one negative case declared an
unapplicable index permutation. Both were fixed, the author's verifier was
extended to catch both defect classes, and round 2 (a fresh reviewer
identity, everything re-derived) returned PASS with zero findings. The
receipt ships at
`supplemental-0_3/receipts/SUPPLEMENTAL_FIXTURE_ACCEPTANCE_RECEIPT_0_3.json`
(self-zero
`70B01072A4087A4F215812D9225D8122FC4227FC33A7CB2CA683923D39E4FE7D`).
Both ACL prior-art PDF pins were re-fetched at source and matched in both
rounds.

**Implementation build — separated lane.** Because the 0.3 fixture author
lane also wrote the 0.2 implementation (exposure disclosed in the 0.3
contract), the 0.3 implementation extension was built by a different lane
and covers all 30 operations in both execution modes. Manifest self-zero
`8D6B67C3C2454E394FC4363850F0CB3DE7F1C6C4A70956C7C1EFD21CA75B9230`;
build-receipt self-zero
`F6D3394A5F24DC453400E275AD745E2DBCA560C1E5E2C1EECED2449BF78F215D`;
implementation tree seal
`A9849351F3576569C855CF7E45429C1DCA2D8210B92B186CF3AB0708FADA3B58`.

**Adversarial implementation acceptance — ACCEPT at round 1.** Under the
same charter as the ten-round 0.2 loop (cap 5, stop at the first round
with zero valid defects), a fresh reviewer lane ran 5,132 executions
against the implementation: all 905 frozen conformance cases, 49 designed
predicate and precedence probes against the new rows, 9 envelope and
hash-binding probes, 2 composed-schema boundary probes, 42 wrapper
binding/parity/transcript probes, 517 randomized inputs from a recorded
seed (`194626982381577`) across all 30 operations, and 2,277 differential
comparisons: in-process versus subprocess ABI, and the 0.3 runner versus
the accepted 0.2 runner across the entire accepted surface. Zero valid
implementation defects. The loop concluded at its stopping rule.

**Candidate-blind completeness review — COMPLETE, selection row
admitted.** A fresh, isolated reviewer context received exactly four
files — a decision brief, the composed 30-operation matrix, the frozen
capability floor, and the pinned prior-art snapshot — and nothing else,
and ruled the composed surface COMPLETE against the basis with the
conditionally-admitted selection row earning its place (`OBL-30: ADMIT`).
Verdict shipped verbatim at `supplemental-0_3/BLIND_GATE_VERDICT_0_3.md`
(raw
`A3BFABC6424BC41F60F1C4A050D7A72BF4E55CE39E2288CC76E6726FA6635DC9`).
The reviewer's custody confirmation (exactly the four files read, no
network, no writes) was corroborated against its session transcript,
which records six tool calls, all inside the bundle.

**Third recorded non-closure.** The implementation-acceptance reviewer
found one MALFORMED disjunct of OBL-30 (contradictory duplicate exclusion
reasons, `NOT_FUNCTIONAL_BY` over `excluded_records`) unreachable for
schema-valid inputs while the exclusion-reason enum has a single member.
Ledgered like the two 0.2 non-closures: inert within the admitted input
space, misclassifies nothing, re-activates at any future versioned enum
extension.

## How to reproduce

From `baseline-run/`, with any CPython 3.12:

```bash
python -B implementation-output-0.2/run_conformance_0_2.py
```

The composed suite (accepted 0.2 plus supplemental 0.3, 905 checks):

```bash
python -B implementation-output-0.3/run_conformance_0_3.py --suite all
```

Then re-derive the seals per `baseline-run/RUNBOOK.md`. The reviewers used
the pinned offline toolchain for the sealed subprocess-ABI mode; the RUNBOOK
documents reproducing it from the official CPython 3.12.4 embeddable.
