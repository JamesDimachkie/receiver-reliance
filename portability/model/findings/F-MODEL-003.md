# F-MODEL-003 — physical KEY_A label alias was double-counted

Status: RESOLVED 2026-08-11 — corrected, and the post-correction complete
N=48 receipt `CD6210F8...732E` was admitted after the fresh R-MODEL-3
refutation returned NO-NEW-EVIDENCE (custody and probe record:
`../receipts/N48-POST-F-MODEL-003-SUMMARY.md`).

## Minimized divergence

- Raw input: `"a"\n`
- Raw hex: `2261220a`
- Raw SHA-256:
  `EE195DB0CD14979ECE92E4AC42D91FEF87D1EE254F8DF170907CD674DAB12D44`
- Old symbolic path `KEY_A, LF`: `PARSE_OK`
- Old symbolic path `KEY_A_REPEAT, LF`: `ERR_JSON`

`KEY_A` and `KEY_A_REPEAT` intentionally share one physical expansion. The
old transition code chose between them only inside `_consume_key`; invalid,
DONE, scalar, array, and other parser phases admitted both symbolic labels.
That double-counted physical traces and could assign one byte string two
terminal classes. The F-MODEL-002 N=48 receipt is rejected.

## Correction

Label selection now precedes every parser branch. `KEY_A_REPEAT` is selected
only when the parser is consuming an object key and that same object has
already seen decoded key `a`; every other state selects `KEY_A`. The frozen
token table has been audited for raw-expansion aliases, and `"a"` is its only
alias group.

Focused regression and bounded exhaustive reachable-state collision checks
are part of `test_model.py`. Full counts and capture hashes will be recorded
only after one fresh terminal-exit-0 N<=48 enumeration.
