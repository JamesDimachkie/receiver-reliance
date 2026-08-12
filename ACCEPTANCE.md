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
  `DE4BD0886F35096CC411F4E502BC30B7951344C7EB507A6FAFA9BBAEF4FA8402`
- Build-receipt self-zero SHA-256:
  `30D880DBB72A5FDCE58D43CFD8838FD79B7786AD4AD3DCB069B8388F7924A943`
- Conformance: 800 checks green, in-process and pinned-toolchain
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
`78089DFC2AEF21349655067D2DEB54CBDEF557E5FA29CD4A27668B03C3A2B50E`;
build-receipt self-zero
`94415D89EA778C46C27B49C2757F5522033639F33CC5F65314E0FD26A5C9B6D9`;
implementation tree seal
`BEE90E62010D7F810A8993CD5D9E1382F6E7EE5A8DE6B83A30655E0E6B47264A`.

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

## v1.1 — cross-interpreter determinism correction (2026-08-10)

Running the conformance suite on CPython builds other than the pinned 3.12.4
exposed an interpreter-dependent classification of deeply nested inputs. A
pathologically deep (5000-level) bare array resolved to `ERR_LIMIT` on 3.12.4
and to `ERR_SCHEMA` on stock 3.14 and non-Windows 3.12. Author-separated review
of the first fix showed the divergence was broader than a bare array: deep
objects and well-formed-looking envelopes with deep inner values diverged too,
one class as far as `ERR_INTERNAL`. Only inputs past the 128-level nesting limit
were affected. All 720 fixture-pinned checks were identical across builds.

Root cause: for a deeply nested input, the classification depended on the
depth at which a given CPython build aborts `json.loads` (and downstream recursive
canonicalization or schema evaluation), which is interpreter- and
platform-specific. The frozen precedence law already ranks `ERR_SCHEMA`
(root-type, 80) above `ERR_LIMIT` (structural, 90), and the shallow siblings
`schema-root-beats-nesting-limit` (depth 130) and `schema-root-beats-item-limit`
assert exactly that — but a deep input reached the recursive parser before the
root type was classified, so the answer moved with the interpreter.

Fix: inputs past the 128-level nesting limit are now classified at the parse
layer from the iterative, depth-immune scan alone, before the recursive tree
parser runs — the same fence the wrapper transcript evaluator already applied at
`_strict_wire_value` (round-7 R7-DIV-004), extended to the main parse path. The
scan sees the whole input at any depth. The shallow envelope of the
protocol-error response (core vs wrapper, echoed `request_id`) is read
iteratively. No recursive operation runs on a structure past the nesting limit,
so classification is a pure function of the input bytes. The full response bytes
are byte-identical on CPython 3.12.4, 3.12.10, and 3.14.5 (across a major-version
boundary) for every affected class: bare arrays, unknown-format objects,
known-format objects, wrapper requests, and valid-looking envelopes with deep
inner values (the former `ERR_INTERNAL` case). Three error-law closures pin
these classes as regression cases. The composed suite is now 800 + 107 = 907
checks and passes on all three interpreters and on the Linux/macOS/Windows CI
matrix.

The change touches only the iterative scanner (one additive depth flag) and
`pcb_runner`'s parse/dispatch path. No fixture pack, contract, or schema
changed, and the 720 fixture-pinned response bytes and their seals are
byte-unchanged. The implementation manifests and build receipts were
regenerated to pin the new source bytes and the two added closures (digests in
"Final accepted state" above and in the 0.3 acceptance chain).

Also in v1.1: a repository `.gitattributes` tells git to treat every file as
binary, so git never rewrites line endings on checkout. A Git-for-Windows
`autocrlf` clone was converting the content-addressed files to CRLF, which broke
the digest self-check on load.

Provenance: the v1.0 implementation and its ten-round acceptance stand as
recorded. The v1.1 determinism correction was authored by the lead reasoning
lane and independently reviewed by a separate author-separated lane. That
review rejected a first, narrower fix for missing the deep-object classes, which
produced the parse-layer design recorded here. The reviewer's identity and final
disposition are recorded with this release.

## v1.2 — validation layers, hosted evidence, public consolidation (2026-08-11)

Everything between v1.1 and v1.2 is additive: zero bytes changed under the
sealed 0.2/0.3 fixture packs, control surfaces, or accepted reference
implementations. What landed, each with its own evidence record:

- the grounded 0.4 layer answering the external review — library and
  audited APIs, tighten-only closures, the CI-gated authority register and
  lint, and the native-records usefulness proof (internal held-out tier);
- the deterministic seeded fuzz campaign (100,000 case identities, zero
  findings) and the recorded second-implementation attempt, rejected four
  times by fresh-context refuters (`orchestration/refuters/`);
- the portability program: finite model with admitted N=48 enumeration,
  independent oracle, deterministic live-transport replay, bounded
  concurrency ladder, hosted CPython 3.12/3.13/3.14 matrix across six
  OS/architecture rows, and a hardened daemon-real Linux container gate,
  with all hosted receipts committed under `portability/receipts/hosted/`
  and bound by the 193-check `verify_receipts.py`
  (`orchestration/PORTABILITY_VALIDATION.md`);
- the blind completeness review's published input bundle (`evidence/`);
- repository consolidation to a single public `main`, with the first
  public run's authority-pin failure adjudicated as F-MATRIX-014 rather
  than amended away.

Provenance: multi-lane authorship under the recorded role-separation
protocol throughout; the orchestration ledger carries the per-actor
chronology, including the four red hosted runs and their pinned findings.

## How to reproduce

From `baseline-run/`, with any CPython 3.12:

```bash
python -B implementation-output-0.2/run_conformance_0_2.py
```

The composed suite (accepted 0.2 plus supplemental 0.3, 907 checks):

```bash
python -B implementation-output-0.3/run_conformance_0_3.py --suite all
```

Then re-derive the seals per `baseline-run/RUNBOOK.md`. The reviewers used
the pinned offline toolchain for the sealed subprocess-ABI mode; the RUNBOOK
documents reproducing it from the official CPython 3.12.4 embeddable.
