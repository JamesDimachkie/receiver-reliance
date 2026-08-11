# F-SANDBOX-024 — hardened count parser rejected real prefixed summaries

Status: **RESOLVED locally.** The retained failed local receipt is
`../receipts/local-expanded-gate-release-audit-rejected1.json` (raw SHA-256
`31F9C49E8D7E808372A399C9E868D624533D2171D99FB4CBC37EDDDB2E42AA73`).
Both CPython 3.12 and 3.14 focused suites pass 76/76 after correction.

The F-SANDBOX-023 duplicate-summary correction initially selected grounded
count candidates only when a line began with `checks=`. All six real grounded
commands put a human label before that field, such as
`grounded-0.4 regression: checks=504 failures=0`. The first clean corrective
expanded-gate run therefore stopped at command 3 even though the command
exited zero with its exact expected count.

The count validator now accepts one gate-specific human prefix while still
requiring exactly one line containing `checks=`, exactly one `checks=` field,
exactly one `failures=` field, exact nonnegative decimal values, and the
declared expected count with zero failures. Regressions cover prefixed valid
summaries, duplicates split across streams or orderings, malformed summaries,
and two contradictory summaries placed on the same line.
