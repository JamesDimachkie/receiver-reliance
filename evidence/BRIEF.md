# Completeness decision brief

You are the candidate-blind completeness reviewer for a frozen capability
matrix. You are deliberately isolated: your working directory contains
exactly this brief and three artifacts, and they are your complete
evidence base.

- `B1_COMPOSED_CAPABILITY_MATRIX_0_3.json` — the composed 30-operation
  capability matrix under decision (28 base rows plus two supplemental
  rows, OBL-29 and OBL-30).
- `A1_CAPABILITY_FLOOR_0_1.md` — the frozen capability-floor
  specification the matrix builds on (28 mandatory obligations).
- `PRIOR_ART_SNAPSHOT_0_3.json` — the dated, hash-pinned prior-art
  snapshot fixing the completeness basis for this decision.

## Isolation rules (binding)

1. Read nothing on this machine outside your working directory. Relative
   paths and digests inside the artifacts refer to material that is
   intentionally not present; do not search for it.
2. You MAY fetch the two public content URLs pinned in the snapshot
   (landing pages and PDFs) to understand the prior-art capability
   classes at source. No other network use.
3. Do not attempt to identify, reconstruct, or reason about any
   downstream use of the matrix beyond what the artifacts themselves
   state. Your judgment must rest on the artifacts and the pinned basis
   alone.
4. Write no files. Your final message is the entire deliverable.
5. End with a custody confirmation: list every file you read and every
   URL you fetched, and confirm nothing else was accessed.

## Question 1 — completeness (kill-or-continue)

Judged against the pinned prior-art basis and the capability floor: is
the composed 30-operation matrix a complete comparator capability
surface? Concretely: does any capability class established by the pinned
basis, or any mandatory obligation of the floor, lack a corresponding
operation row? Answer `COMPLETE` or `INCOMPLETE`; if `INCOMPLETE`, name
each missing capability class and the basis component that establishes
it. Do not treat prior art outside the pinned snapshot as part of the
basis; the snapshot's treadmill guard governs.

## Question 2 — conditional row admission

Row OBL-30 (`INTENT_COMPATIBLE_SELECTION`) is admitted conditionally;
its row records the condition and its droppability. Decide `ADMIT`
(the row earns its place on the surface: the pinned basis establishes
compatibility-first selection from competing frozen candidate pools as a
capability class a complete surface must carry) or `DROP` (the row is
out of frame for this surface and should be severed per its
droppability clause). Give the decisive reason either way. OBL-29 is
unconditional and is not before you for admission.

## Verdict format

1. `VERDICT: COMPLETE` or `VERDICT: INCOMPLETE` with the missing-class
   list.
2. `OBL-30: ADMIT` or `OBL-30: DROP` with the decisive reason.
3. Findings, if any: anything in the three artifacts that undermines the
   decision (internal contradiction, floor conflict, basis mismatch),
   each with the exact pointer.
4. A fresh reviewer identity of your choosing (actor id + lineage id
   strings; they must not imitate any identity string appearing in the
   artifacts).
5. The custody confirmation.
