# F-ORACLE-012 — host recursion ceiling leaks as `ERR_JSON`

Status before correction: credible independent-oracle portability defect;
accepted implementation unchanged. Found by fresh refuter R-ORACLE-11 at
frozen closure 45 on 2026-08-10.

## Depth-minimal replay

```text
raw construction: `[` repeated 497, then `0`, then `]` repeated 497, then LF
raw length:       996
raw SHA-256:      7CF05E162193A98C7ACB5104CBF719CC3D9301F1494CE4CE07E13128E7D67B3E
schedule:         isolated invocation; no transport schedule
```

The record is strict UTF-8, exactly LF-framed, canonical JSON, NFC, and within
the safe-number profile. Its root is an array, so schema failure at the empty
root pointer (precedence 80) wins before the exceeded nesting limit
(precedence 90). The otherwise identical depth-496 neighbor already produced
that required `ERR_SCHEMA` result, making depth 497 minimal for this host-stack
leak.

## Contract-expected / accepted bytes

Both accepted generations produced the same exact result in the supplied
refuter evidence:

```text
exit: 2
stderr: empty
stdout length: 335
stdout SHA-256: BAA52EC96ED84A513C18D3FFCB10BC8B4A7E3B5D8FF8C3061B06708178629EAA
stdout:
{"errors":[{"code":"ERR_SCHEMA","message":"Request does not validate.","pointer":"","precedence":80}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"33524008D41EE8D3DBC9EAB632101EE74A59FC1FD103F4C28EF2F920F3880BF7","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

## Rejected oracle behavior

The clean oracle's recursive parser reached Python's recursion ceiling and
converted `RecursionError` to `ERR_JSON`, producing stdout SHA-256
`9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2`.
That host-dependent classification bypassed both the independently specified
root-schema result and the contract's own deterministic nesting limit.

## Narrow correction

F-ORACLE-12 replaces raw parsing, canonical serialization, and validation
walking recursion with explicit work stacks. Allocation remains bounded by the
pre-decode 16,777,216-byte physical-record guard; the parser has no
input-independent retry or expansion. Regressions cover depths 496, 497,
1,024, and 4,096 under an artificially lowered Python recursion limit, plus a
malformed deep record, deep noncanonical spelling, duplicate, number, and NFC
precedence, and the declared nesting-limit neighbor inside a schema-valid root
envelope.

This correction author did not read, import, or execute the accepted
implementation, conformance/grounded/proof runners or outputs, or any of the
five forbidden implementation files. The accepted-result tuple above is
adjudicated finding evidence supplied by the fresh refuter. Acceptance still
requires a new fresh refuter.
