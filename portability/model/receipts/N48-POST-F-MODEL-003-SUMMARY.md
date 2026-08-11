# Post-F-MODEL-003 complete N=48 enumeration — attempt 1 summary

Date: 2026-08-11 (run 2026-08-10 22:16–22:52 PDT / 2026-08-11 05:16:32–05:52:26 UTC)

Status: **ADMITTED** (2026-08-11). Fresh author-separated refuter
R-MODEL-3 attacked this receipt across eight vectors: independent
reimplementation matched the explorer exactly through N=28; alias
exclusivity re-verified at N=24 (37,713 contexts, every rejected alias
edge absent); the quotient-material hash was proven to cover state
material only, making its identity with the rejected receipt benign;
closed-form derivations reproduced every small terminal class; the
embedded receipt SHA, all capture and input hashes, and the verbatim
domain text were re-verified; determinism was established including
PYTHONHASHSEED invariance across three seeds. Execution being blocked in
the refuter's sandbox, its two condition-resolving probes were run
verbatim by the custodian: the fast probe passed in full, and the full
probe — a complete independent N=48 re-enumeration — reproduced the
receipt byte-for-byte (`R_MODEL_3_FULL_PROBE ALL_PASS`,
`inadmissible_alias_edges 16260520`, receipt `CD6210F8...732E`).
Verdict: **NO-NEW-EVIDENCE**. `EXPECTED_COUNTS.json`, the model README,
and the full-test constants now carry these adjudicated values; the
F-MODEL-002 values remain quarantined as rejected history.

## Custody

- Branch `sol/rr-portability-modelcheck-20260810`, HEAD
  `4e788d21e882a30bdda2aec3f780537161f81644`, nothing staged, before and
  after the run.
- Free physical memory before launch: 6,841,736 KB. Peak working set of
  the enumeration process: 1,366,290,432 bytes (1,303 MiB), sampled every
  30 s (`N48-postF3-attempt1.memsample.txt`).
- No retry occurred; this is attempt 1 and it terminated exit 0.

## Frozen inputs (SHA-256, verified before and after the run)

| File | SHA-256 |
|---|---|
| `parser_model.py` | `F8157FA5791D957C4D9E424B4C2F560A0D7B103A6B2A6B316BCD822BA178BE74` |
| `domain.py` | `43E9E3AB1B9DD30F253C6FFE4FDCF6F9440268711775966E6F0EF3CA4307C395` |
| `explorer.py` | `EFABCEC2791FEA56B198CB00EDF0B16D29F4D4458FEEE5007CDD6EFA01579DC2` |
| `closures.py` | `566719CF78DF4BB7BA584A85A9F60F2ABB01873B4BB8676B3A680CBA4EE58991` |
| `transport_model.py` | `D4F4C0CA90BA0ACE791B6E78929CF31480A6E85F49F726D4EFE6B2086E058BBC` |
| `reference_checker.py` | `74C14338D727781545F046B3EBE462AA5A129C615DD352EDCB6AEBCD9D67666D` |
| `r3_schedules.json` | `116C7C5BB92F3B1B255A7EE7F42C076A5A8E6432601C44BF5670D98B32D99705` |
| `test_model.py` | `2067064788AA9D51427739F5E2E63031AE7DEE6ABED096B6B00A0792A37A43EC` |

## Preconditions (all passed before launch)

1. Focused suite: 17 tests, OK, 1 intentional full-enumeration skip
   (re-verified after the run with the same result).
2. Minimized witnesses and neighbors: 10/10 pass
   (`precheck_witness.py`, `885C...` inputs hashed below).
3. Alias exclusivity: exhaustive reachable-state check that exactly one
   of KEY_A/KEY_A_REPEAT is admissible per state, through **N=32**
   (declared floor N=16, adjudication mandate N=24; driver
   `precheck_alias.py`). Reported by the run author; re-execution is
   delegated to the fresh refuter.
4. Retained-versus-streaming equivalence: **IDENTICAL for every bound
   N=18..28, 0 divergences**, with per-bound counts and quotient material
   hashes recorded durably in `precheck-retained-vs-streaming.txt`.
5. Packed-key injectivity/round-trip: covered by the focused suite's
   `test_packed_state_is_lossless_over_reachable_prefixes`.

## The run

- Command: `python -B -m portability.model.explorer --compact --progress`
  with `PYTHONHASHSEED=0`, stdout/stderr redirected to the durable
  captures below (sampler-recorded command line confirms the exact
  invocation; interpreter `C:\Users\james\AppData\Local\Python\bin\
  python.exe`, CPython 3.12.10, Windows).
- Exit code 0; elapsed 2,153 s.

## Captures (SHA-256)

| File | SHA-256 |
|---|---|
| `N48-postF3-attempt1.stdout.txt` | `AB53DCB62E8C60D9E6D9DD59A249174E34CA97CDBF199C810B72F36AAEBC985A` |
| `N48-postF3-attempt1.stderr.txt` | `0BF3067D55683F6EB725E2790165D665735B86C13EFE95A8CBAC4E39D63FA601` |
| `N48-postF3-attempt1.memsample.txt` | `55FD53A62677D3FEAAF43E40B800F34A1563C0BC0B1295329FB32C618AEF2313` |
| `precheck-retained-vs-streaming.txt` | `DC5DE278C57BE84EC380031C24E886022AB0257A5037C16D69A4AB6E5C2170B1` |
| `precheck_alias.py` | `885C0A21CA99544F70BB937BC5CA18CF7DDC38B6CFCDA4142AC249D3B1F39372` |
| `precheck_retained.py` | `DD4C81EBDE34019DED47BE1EBF5CE96B5C070FDBF446B7801A9498F7F0260633` |
| `precheck_witness.py` | `9EC388E318982202905F93BBDF75AF8267CF624DA2D699702E7418AB353FBC18` |
| `extract_counts.py` | `420318F6147BAC7091ED7C17CAD4FD92A5C9AF294FCC369BECE8D787F38ED19D` |

## Extracted counts (primary; not to be compared to the REJECTED tables
as truth)

- receipt SHA-256 (embedded):
  `CD6210F8706C7B37B6CD25A9EF67B53696207EAFED716284151D67B20444732E`
- quotient states: `37,432,306`
- quotient transitions: `294,190,481`
- terminal transitions: `68,157,505`
- symbolic terminal traces:
  `34269567869926335890219352245333204780922262`
- excluded frontier edges: `192,429,497`
- excluded trace prefixes:
  `365700154247143020084708553153258324529440021`
- quotient material SHA-256:
  `2C233FBF0DD68F1BA3C73BFB9F344473B9EA265CF43D770934A76D586329DD2A`
- terminal classes (quotient terminals / symbolic traces):
  - ERR_DUPLICATE_KEY: `42,834,308` /
    `675566583720040912468381243260334`
  - ERR_EMPTY_INPUT: `1` / `1`
  - ERR_JSON: `25,322,938` /
    `63807811495662732114712055391876178185844`
  - ERR_NFC: `41` / `1155471776161497`
  - ERR_UTF8: `170` /
    `34205760057755106574384599270371782039028553`
  - PARSE_OK: `47` / `5945693544286033`

## Internal consistency observed at collection

Against the REJECTED F-MODEL-002 receipt: quotient states, terminal
transitions, and every per-class quotient-terminal count are unchanged;
quotient transitions decreased by exactly `16,260,520` while excluded
frontier edges increased by exactly `16,260,520` (the inadmissible alias
edges moved from admitted to excluded); symbolic traces decreased only in
the duplicate-bearing and ERR_JSON/ERR_UTF8 classes, while
ERR_EMPTY_INPUT, ERR_NFC, and PARSE_OK symbolic traces are identical —
matching the F-MODEL-003 witness geometry. These are observations, not
adjudication.
