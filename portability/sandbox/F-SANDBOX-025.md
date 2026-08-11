# F-SANDBOX-025 — unittest PASS marker was LF-only

Status: **RESOLVED locally.** The retained failed local receipt is
`../receipts/local-expanded-gate-release-audit-rejected2.json` (raw SHA-256
`B82AF20209165F3EBBDAD61C42F5454266693109EA2AE3BE0343EB1E4ADCDE53`).
The proof harness itself ran seven tests successfully; only the receipt
validator rejected its Windows CRLF transcript.

The hardened unittest validator normalized the `Ran` line but searched the
unmodified combined stream for a line equal to `OK`. With CRLF output the
candidate was `OK\r`, so a genuine seven-test PASS stopped the expanded gate.

The validator now splits and normalizes every transcript line once, then
requires exactly one well-formed `Ran 7 tests...` line, exactly one `OK` line,
and no `FAILED` or `ERROR` summary. The regression fixture uses the real
Windows-style `Ran 7 tests in ...\r\n\r\nOK\r\n` shape; duplicate and
contradictory summary tests remain active.
