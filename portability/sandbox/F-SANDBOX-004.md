# F-SANDBOX-004 — overflow JSON number escapes receipt classification

Status: **RESOLVED locally.** Correction retained; final focused suite green.

The exact host flow was given container exit 0 and this 28-byte stdout record:

```json
{"status":"PASS","x":1e309}
```

Its SHA-256 is
`44d53aeaaa818ab046ad6eef1ad2db5be22dda16bf3db10f5aa4d4a1a1b768bd`.
Python's JSON decoder converted `1e309` to positive infinity. The subsequent
canonicalization used `allow_nan=False` and raised a raw `ValueError`, so the
outer host catch mislabeled the untrusted container output as
`SANDBOX_SETUP_FAILURE` instead of `INVALID_CONTAINER_RECEIPT`. The path was
fail-closed, but its receipt classification and integrity boundary were wrong.

The correction installs a finite-only JSON float parser. It rejects positive
and negative overflow forms at any nesting depth, while the existing constant
hook rejects `NaN`, `Infinity`, and `-Infinity`. JSON decoding and
canonicalization type/value failures are translated to `InnerReceiptError`,
which keeps the exact host flow on `INVALID_CONTAINER_RECEIPT` with exit 1.
Regressions cover the minimized payload, nested overflow, all three non-finite
constants, malformed exponent syntax, finite neighbors, canonicalization
failures, and the mocked outer host classification. The complete synthetic
PASS and honest infrastructure-unavailable controls remain in the full suite.
