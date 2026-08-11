# F-ORACLE-007 — noncanonical escape loses to NFC error

Status: credible independent-oracle precedence defect; accepted implementation
unchanged. Found by the parallel adjacent-domain refuter R-ORACLE-5B on
2026-08-10. Correction is serialized behind the active F-ORACLE-006 writer.

## Deletion-minimized replay

```text
raw repr: b'"\\u212B"\n'
raw hex: 225c7532313242220a
raw length: 9
raw SHA-256: 879346A1E13CDCE11B7E9CF17A524BAF8119519B0A8D4B9484FCDF88FA2E59AE
schedule: isolated invocation; no transport schedule
```

The scalar decodes to U+212B, which is non-NFC, while its `\u212B` spelling is
also noncanonical JCS. The frozen law selects `ERR_JSON` (precedence 50)
before `ERR_NFC` (precedence 60). All nine single-byte deletions eliminate the
mismatch.

## Contract-expected / accepted bytes

Both accepted generations reproduced this tuple twice:

```text
exit: 2
stderr: empty
stdout length: 338
stdout SHA-256: 9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2
stdout:
{"errors":[{"code":"ERR_JSON","message":"Invalid JSON or trailing bytes.","pointer":"","precedence":50}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"121508D748E28E6D0A7CF3B2903AA979ADFB45E8D6A58D2929236C32AAC3C99C","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

## Oracle-actual bytes before correction

```text
selected error: ERR_NFC
pointer: empty
precedence: 60
stdout length: 332
stdout SHA-256: 1331EF6E7315A78E08E52B1EE108F0D4594A6EE6B8F59840008E8B49414FEB6F
stdout:
{"errors":[{"code":"ERR_NFC","message":"String is not Unicode NFC.","pointer":"","precedence":60}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"093C2020D718BCEB79FE9C3D32DCBEE69778FA32CC0FAF995F7068A74D5A95C9","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

Root cause: `classify_record` returns recorded non-NFC strings before checking
the independent raw-vs-JCS canonical byte relation. A correction must check
independent canonical spelling/order before NFC while preserving `ERR_NFC` for
a canonically spelled non-NFC scalar.

R-ORACLE-5B used seed `0x52524F3542` over 496 unique declared adjacent cases
and stopped at ordered mismatch 32 after 31 matches. No later candidate was
adjudicated. A fresh author and fresh refuter are required.
