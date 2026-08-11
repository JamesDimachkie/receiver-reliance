# F-SANDBOX-012 — forced cleanup exception suppresses the host receipt

Status: **RESOLVED locally.** Correction retained; final focused suite green.

The exact mocked host flow reached a valid primary `PASS`, assigned the
lowercase container identifier `a` repeated 64 times, and then entered forced
cleanup. `docker rm --force <id>` raised `subprocess.TimeoutExpired` at the
declared 30-second cleanup bound. The exception escaped the `finally` block,
so `_emit` was never called: the host returned no receipt and no ordinary exit
classification. `OSError` and other cleanup-call exceptions had the same
zero-receipt behavior.

The correction moves forced removal behind a total ordinary-exception and
result-shape boundary. Cleanup now classifies success, timeout, launch failure,
unexpected call exception, nonzero exit, malformed `CompletedProcess` fields,
and the absence of a created container. Captured byte streams retain lengths
and SHA-256 digests; malformed stream shapes retain their Python type without
being passed to the digest function. Every cleanup object records the primary
status and exit that preceded it.

A cleanup failure after primary `PASS` now emits exactly one canonical host
receipt with `status=CLEANUP_FAILURE` and exits 1. When a primary setup,
timeout, or receipt-validation failure already exists, that primary status and
detail retain precedence while the cleanup object independently records its
failure. Direct and exact full-flow regressions cover timeout, `OSError`,
nonzero removal, malformed return/exception shapes, successful removal, and
the no-container path.
