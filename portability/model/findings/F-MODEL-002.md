# F-MODEL-002 — replacement custody and layer-retention adjudication

Status: receipt rejected by F-MODEL-003; its counts and hashes are superseded
and must not be used.

F-MODEL-2 took exclusive custody of `portability/model/**` after James directed
the custodian to stop using F-MODEL-1-RESUME. No model explorer process was
running when custody transferred. This author did not communicate with that
worker or rely on its conclusions.

The prior lane had three distinct failures that are not accepted as evidence:

- F-MODEL-001 made the old N=48 receipt semantically stale by separating the
  decoded identities of the three `KEY_B` variants.
- A corrected retained-all-layers run exhausted the available host resources
  before producing a receipt.
- A later run did not leave captured terminal output from which counts could be
  admitted. The old counts, README prose, and test constants therefore remain
  rejected until replaced by one attached completed run.

F-MODEL-2 attempt 1 used the layer-release implementation with full
`ParseState` dictionary keys. It was intentionally stopped at the observed host
commit ceiling rather than risking another machine-wide freeze: the last
completed layer was N=37 (3,597,683 cumulative states; 44,635,034 transitions),
peak sampled working set was 2,172,067,840 bytes, peak private bytes were
2,170,707,968, and OS virtual/commit headroom had fallen to about 2.2 GB with
eleven growing layers left. Exit was -1; stdout was empty with SHA-256
`E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`.
This partial run is not enumeration evidence.

## Independent layer-retention check

`reference_checker.py` keeps every reachable state and multiplicity to the end;
the streaming explorer releases a length layer immediately after processing it.
The implementations were compared field-for-field, including terminal classes
and multiplicities, excluded frontier edges and trace-prefix multiplicities,
and quotient-material hash.

The checked bounds N = 0, 1, 2, 4, 7, 10, 13, 16, 18, 20, 24, and 28 all
matched. The four largest supplemental checks were:

| N | states | transitions | quotient SHA-256 |
|---:|---:|---:|---|
| 18 | 12,837 | 83,100 | `985BE2883F1F5681E81058C12648D4B43055CAED8259368687C947E63DF437D6` |
| 20 | 26,714 | 175,340 | `2A823ACC1767AA45B7A82D39C76ACDE0FA1767CD4298F810F5D602B3EB0A3525` |
| 24 | 102,504 | 704,312 | `AC14F3473DB6BA844FBF2E62CA1443ED0DE7D894E4E761C267DF80523E557CFA` |
| 28 | 347,764 | 2,495,261 | `8022A559AFC24F29E1F90CA1B003AD388B42A33B6DB6886BFC50655158E39134` |

Every concrete token expansion is nonempty, and both explorers assert that
every admitted transition strictly increases `byte_length`. Consequently, all
incoming contributions to a length layer originate in smaller layers and have
arrived before that layer is processed; no released layer can be reached again.
Attempt 2 also stores the non-length fields in an injective 64-bit key. A
separate reachable-prefix test verifies pack/unpack identity and absence of
collisions; the retained reference continues to use `ParseState` keys.

The retained checker is deliberately not used at N=48: its retained history is
the resource failure already being avoided. The full run uses the streaming
explorer only after the independent bounded equivalence above.

## Completed enumeration

F-MODEL-2 attempt 2 completed with exit 0 under an attached 90-minute wrapper:

- parser elapsed: 2,774.266 seconds; wrapper elapsed: 2,782.266 seconds;
- quotient states: 37,432,306;
- transitions: 310,451,001;
- terminal transitions: 68,157,505;
- excluded frontier edges: 176,168,977;
- quotient material SHA-256:
  `2C233FBF0DD68F1BA3C73BFB9F344473B9EA265CF43D770934A76D586329DD2A`;
- receipt SHA-256:
  `C27DEB152C1FDD720EB0FAAE8AD32A06B6DF5DED45763E9E14012F93524D69E9`;
- stdout capture SHA-256:
  `6E31130B0E969A23095E5D9952C5640C8587260E4BCD39D035B31C8BFC654772`;
- stderr progress capture SHA-256:
  `3B42B2C98DD27AF4D1F9E118D7B3EFA3885450AFDFE8895FF0B8F016744878FA`;
- sampled peaks: 1,351,905,280 working-set bytes, 1,358,868,480 private
  bytes, 170 handles, and 4 threads.

The receipt retains the frozen domain wording. Non-embedded prose clarifies
that the R=3 library comprises two fixed-serial and four seed-selected recipes;
`R3_STRICT_ALTERNATION` is a historical identifier, not an every-step
alternation invariant. At that rejected-receipt stage, the completed author
evidence still required a fresh R-MODEL refuter before custody could call the
model lane clear; the supersession below records what followed.

## Supersession

R-MODEL-3 subsequently found that the two labels with raw expansion `"a"`
were both admitted outside object-key duplicate contexts. The same physical
line could therefore reach conflicting terminal classes. F-MODEL-003 owns the
correction and a fresh complete enumeration; every N=48 count and hash above
is retained only as rejected historical evidence.
