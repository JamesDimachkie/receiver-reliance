# Receiver-reliance finite model M

This directory is the treatment-exposed, stdlib-only executable model named in
the portability charter. It does not contain an independent oracle, future
blinded worlds, gold outputs, or a renderer.

## Run

From the repository root:

```text
python -B -m portability.model.explorer --progress
python -B portability/model/test_model.py
python -B portability/model/test_model.py --full
```

The first command emits the deterministic JSON receipt. The ordinary focused
test takes about a second and includes the accepted RI1-RI4 raw closures, every
positive short-write index of the first RO1 response, and an actual-cap
16,777,217-byte RO1/RO2 oversize-drain alignment replay. `--full` repeats the
entire N=48 enumeration. The corrected compact-state run took about 46 minutes
on the authoring machine.

## Frozen domain and enumeration

The base alphabet has exactly 12 symbols. `KEY_B` has three mutually exclusive
flags (plain, non-NFC, lone-surrogate), producing 14 concrete transition labels
without adding a base symbol. The parser lattice is bounded at 48 expanded
bytes, depth 6, and three duplicate members per object. LF and final EOF are
distinct terminal actions; zero-byte EOF is clean shutdown rather than a
physical record.

The parser quotient merges only prefixes with the same byte length, control
phase, bounded stack, duplicate fact, NFC fact, and permanent canonicality
fact. Exact arbitrary-precision multiplicities preserve how many symbolic
traces reach each merged state. `KEY_A_REPEAT` canonically labels repeated raw
`"a"` occurrences. Each `KEY_B` flag value denotes a different decoded member
name and therefore has its own seen bit; only an identical repeated variant is
the corresponding duplicate class.

The admitted post-F-MODEL-003 N=48 run produced:

| Count | Value |
|---|---:|
| parser quotient states | 37,432,306 |
| parser transitions | 294,190,481 |
| terminal transitions | 68,157,505 |
| symbolic terminal traces | 34,269,567,869,926,335,890,219,352,245,333,204,780,922,262 |
| excluded frontier edges | 192,429,497 |
| quotient material SHA-256 | `2C233FBF0DD68F1BA3C73BFB9F344473B9EA265CF43D770934A76D586329DD2A` |

The final receipt envelope SHA-256 is
`CD6210F8706C7B37B6CD25A9EF67B53696207EAFED716284151D67B20444732E`,
captured with custody evidence under `receipts/` and admitted after the
R-MODEL-3 fresh refutation (`receipts/N48-POST-F-MODEL-003-SUMMARY.md`).
Exact terminal-class counts, partition totals, scheduler counts, R=3 action
hashes, and the run environment are published in `EXPECTED_COUNTS.json`.

Two earlier complete receipts are REJECTED history and support no claim:
the pre-F-MODEL-001 receipt `081180E9...2B14` (unsound key quotient) and
the F-MODEL-002 receipt `C27DEB15...D69E9` (symbolic alias double-counting,
falsified by the F-MODEL-003 witness). The quotient material hash above
covers state material only, which is why it is unchanged from the rejected
run while 16,260,520 inadmissible alias edges moved from admitted
transitions to the excluded frontier.

The complete scheduler products are P=1/2 by R=1/2. The largest, P=2/R=2,
has 729 quotient states, 1,728 transitions, and
7,021,875,387,712,248 fair concrete schedule traces before multiplying by 81
ordered record-sequence assignments. For R=3, two fixed-serial recipes and four
seed-selected recipes are deterministically materialized and hashed; no
completeness claim is made for R=3 schedules. `R3_STRICT_ALTERNATION` is a
historical recipe identifier, not a claim that every adjacent action switches
callers.

Read partitions include every split-point subset of size 0, 1, or 2, plus
every size-3 subset of points adjacent to a lexical token boundary, LF, or the
oversize threshold. Write partitions include every subset of size at most 2
for each response. Positions within the same phase are a byte-position-renaming
bisimulation: the structural graph is explored once and every concrete subset
is retained by exact combinatorial multiplicity.

## Historical closure mapping

- RI1 is pinned byte-for-byte as a supplemental lexeme closure because its
  astral/BMP ordering-edge keys are not members of the base alphabet.
- RI2's lone-surrogate scalar is an exact `KEY_B:lone_surrogate` trace; its key
  form maps to the same trace with `1` replacing the historical scalar `0`.
- RI3's empty-key duplicate is pinned byte-for-byte and maps to the incomplete
  `KEY_A`/`KEY_A_REPEAT` EOF terminal.
- RI4 maps directly to that nonempty duplicate EOF terminal, with `1` as the
  alphabet's scalar synonym for historical `0`.
- RO1 short writes are replayed at every first-response byte index. RO1/RO2
  oversize drain is replayed at the actual 16 MiB cap and followed by another
  physical record to prove next-record alignment.

## Assumptions, reductions, and exclusions

The emitted receipt publishes the authoritative lists. In short: partitions
preserve bytes and record boundaries; pause always has a matching resume;
caller identities are not symmetry-swapped; the actual oversize boundary is a
named closure over a threshold-relative structural quotient. Outside M are
longer/deeper/more-duplicate inputs, P>2, complete R=3 scheduling, unfair
infinite schedules, OS timing/resource behavior, and semantic decision-table
coverage after `PARSE_OK`. Those surfaces belong to the live, concurrency,
matrix, sandbox, and oracle lanes.

The only model claim is that every declared quotient state, admissible token
transition, terminal action, complete P<=2/R<=2 scheduler transition, and
partition multiplicity in M was explored. This is not an efficacy, novelty,
security, fuzzing-completeness, external-standard, universal-portability, or
post-parse semantic-completeness claim.
