# F-ORACLE-010 — oversized physical record must be rejected before BOM/decode

Status before correction: credible independent-oracle precedence and bounded-
memory defect; accepted implementation unchanged. Found by the fresh clean-room
refutation at shared frozen closure 3/57 on 2026-08-10.

## Minimized boundary replay

```text
raw construction: UTF-8 BOM ef bb bf followed by ASCII `0` repeated 16,777,214 times
raw prefix hex:   efbbbf30...
raw length:       16,777,217 (declared maximum + 1)
raw SHA-256:      FD23ED50B5FD04CAC39CFC1651C8EF1E3EA2418067B2B12B47D0A4F0AA34549C
schedule:         isolated invocation; no transport schedule
```

The allowlisted frozen host packet requires rejecting input exceeding
16,777,216 bytes before decode. Both accepted generations were observed by the
refuter to return the same exact `ERR_LIMIT` response twice:

```text
exit: 2
stderr: empty
stdout length: 352
stdout SHA-256: 92F0618093EE73A5FFAC007FB12BC6003389B696C549CE2A6EA5FAEB1C4AE8D7
stdout:
{"errors":[{"code":"ERR_LIMIT","message":"A deterministic resource limit was exceeded.","pointer":"","precedence":90}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"2F6D86BFC16ADC188D29B90C0DE39FF17AE5CF51F50A649ED6906673EEB1A7BD","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

## Rejected oracle behavior

Before correction the clean oracle decoded the full record and selected
`ERR_BOM`, producing 329 stdout bytes with SHA-256
`FDC0643FF678992BBB56947A76BF8F02192F5664BA8C4F4F10F8D1E2F37E2BAA`.
That behavior violated both the recorded boundary precedence and the bounded-
memory classification requirement.

The narrow correction rejects any physical record longer than the declared
maximum before creating decoded text, parser state, or canonical payload. At
exactly the limit, ordinary UTF-8, BOM, JSON/framing, NFC, number, schema, and
resource classification remains in force. Regression neighbors cover a short
BOM, at-limit BOM, invalid UTF-8 on both sides of the size boundary, framing on
both sides of the boundary, and next-record invariance after oversize drain.

This correction author did not execute the accepted implementation. The
accepted-result tuple above is adjudicated finding evidence supplied by the
fresh refuter.
