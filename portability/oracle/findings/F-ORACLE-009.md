# F-ORACLE-009 — legal surrounding whitespace loses the parsed request ID

Status before clean-room replacement: credible independent-oracle defect;
accepted implementation unchanged. The witness was adjudicated before the
O-ORACLE-CLEAN-RESUME rebuild.

## Deletion-minimal replay

```text
raw repr:   b'{"request_id":"RUN_000000000000000000000004"}\r'
raw length: 46
raw SHA-256: 7FD19849BBEC0C6291883BE4E3581A603001C4DD509602D9C9493D3D31362DC7
schedule: isolated invocation; no transport schedule
```

The carriage return is legal JSON surrounding whitespace, so strict JSON
parsing succeeds and the valid request ID is available. The physical record is
still not exactly canonical JSON plus terminal LF; therefore `ERR_JSON` is the
selected result, but it must retain `RUN_000000000000000000000004`.

All 46 single-byte deletions removed the divergence.

## Contract-expected / accepted bytes

```text
exit: 2
stderr: empty
stdout length: 338
stdout SHA-256: 8AED3D8C7B7465A17FC5BF1996FA5FAFE4877D1BAE4B23AB42BD3CA43848EBE1
stdout:
{"errors":[{"code":"ERR_JSON","message":"Invalid JSON or trailing bytes.","pointer":"","precedence":50}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"31B8CEE46755F51B870FEC237EF38972B2813E48F0993A717855699A6712911F","request_id":"RUN_000000000000000000000004","result":"INCOMPLETE"}\n
```

## Rejected-oracle bytes before replacement

The rejected oracle erased the parsed ID and emitted the all-zero request ID,
with stdout SHA-256
`9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2`.

The clean-room classifier parses legal leading/trailing JSON whitespace for
request-ID extraction, then independently applies physical framing and
canonical-byte equality. This preserves the parse result without weakening the
`ERR_JSON` result. Acceptance still requires a fresh refuter.
