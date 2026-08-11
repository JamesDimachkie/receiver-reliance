# F-SANDBOX-023 — duplicate gate summaries could self-authorize PASS

Status: **RESOLVED locally.** Contradictory-summary and malformed-count
regressions are included in the terminal 76/76 focused suite.

The expanded-gate validators used first-match regular expressions. A command
could exit zero after printing an expected success summary and then print a
contradictory failure or count summary; the first match alone authorized PASS.
The same ambiguity existed across the core, composed, all six grounded checks,
lint meta-gate, internal proof, and fuzz validators. Invalid UTF-8 also escaped
the declared gate-failure boundary.

Each validator now requires exactly one authoritative summary. Count payloads
must be finite JSON objects whose values are nonnegative exact integers; lint
requires exactly one zero-failure line; unittest requires one expected `Ran`
line, one `OK`, and no failure marker; fuzz requires one full PASS summary.
Strict UTF-8 failures become `GateFailure`. Successful command stdout and
stderr are retained as canonical base64 and cross-checked against their byte
counts and hashes by the host, so the receipt preserves the transcripts that
the unique-summary decision consumed.

The regression exercises valid-then-invalid and invalid-then-valid duplicate
orderings for every validator family, plus invalid-only summaries and invalid
UTF-8. No command transcript is admitted solely from a first match.
