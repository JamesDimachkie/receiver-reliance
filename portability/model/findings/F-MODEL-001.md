# F-MODEL-001 — KEY_B variant identity was unsound

Status: corrected by F-MODEL-1; full receipt regeneration required.

## Minimized divergence

- Raw input (no LF): `7b2262223a312c2265cc8122`
- Raw SHA-256: `82E4429EF718F8C17DB01ADAC96D1E4DA1D5A2035C5C411200B87E29C9E04635`
- Symbolic trace: `LBRACE, KEY_B:plain, COLON, INT_1, COMMA, KEY_B:non_nfc, EOF`
- Old model result: `ERR_DUPLICATE_KEY`
- Frozen accepted result: `ERR_JSON`, empty pointer, exit 2
- Frozen response SHA-256: `9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2`

The old quotient gave plain `"b"`, decomposed `"e\u0301"`, and `"\\ud800"`
one `key_id`. They are different decoded strings, so this merged prefixes that
remain distinguishable by duplicate-key precedence.

## Correction

Each `KEY_B` variant now has its own seen-key bit. Repetition of the same
variant remains a duplicate. The minimized trace is `ERR_JSON`; its completed
object is `ERR_NFC`; plain/lone-surrogate and lone-surrogate/plain neighbors
remain `ERR_JSON`; repeated non-NFC and repeated lone-surrogate keys remain
`ERR_DUPLICATE_KEY`.

The correction changes the reachable quotient. No prior enumeration count or
receipt hash is reused; `EXPECTED_COUNTS.json`, the README, and full-test
constants are updated only from a fresh complete N<=48, D<=6, K<=3 run.
