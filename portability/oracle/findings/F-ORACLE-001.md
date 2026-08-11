# F-ORACLE-001 — duplicate precedence lost before framing adjudication

Status at discovery: credible portability-oracle defect; accepted implementation
unchanged. Discovered by Sol root during independent integration review on
2026-08-10 at baseline `4e788d21e882a30bdda2aec3f780537161f81644`.

## Smallest replay

```text
raw repr:   b'{"":0,""'
raw hex:    7b22223a302c2222
raw length: 8
raw SHA-256: 10779FCB480886B954ACEAE3C495771971BAA338F1A8FE55A48EB68965B4D6FD
schedule: isolated invocation; no transport schedule
```

The frozen contract selects errors by precedence and places duplicate key
(40) before invalid JSON/trailing bytes (50). The accepted 0.2 and 0.3
conformance suites also pin `dup-beats-noLF` to `ERR_DUPLICATE_KEY` with the
empty pointer. The new oracle instead checked terminal LF before its
duplicate-preserving parse and returned `ERR_JSON`.

## Contract-expected / accepted bytes

```text
exit: 2
stderr: empty
stdout SHA-256: 6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01
stdout:
{"errors":[{"code":"ERR_DUPLICATE_KEY","message":"Duplicate JSON object key.","pointer":"","precedence":40}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"A7E43CA772D54C98193C02100AC1F23E75B312DCAF3F3857E737A805DBF92D29","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

Two consecutive accepted 0.2 CLI runs were byte-identical with that stdout
hash, exit 2, and empty stderr. The 0.3 historical adjudication is recorded in
`orchestration/refuters/RI3.md`.

## Oracle-actual bytes before correction

```text
selected error: ERR_JSON
precedence: 50
stdout SHA-256: 9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2
stdout:
{"errors":[{"code":"ERR_JSON","message":"Invalid JSON or trailing bytes.","pointer":"","precedence":50}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"121508D748E28E6D0A7CF3B2903AA979ADFB45E8D6A58D2929236C32AAC3C99C","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

The same defect family includes ordinary duplicate locations: the frozen
contract requires the empty duplicate pointer, while the initial oracle
reported `/a` (and `/` for an empty member name). A correction must pool a
detected duplicate even when later parsing/framing fails and must emit the
contract's empty pointer for `ERR_DUPLICATE_KEY`.

## Environment and resources

```text
OS: Windows-11-10.0.26200-SP0
Python: CPython 3.12.10 [MSC v.1943 64 bit (AMD64)]
Executable: C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe
Wall-clock or random input: none
Network: none
Resource anomaly: none observed
```

Per the session charter, the discovery worker does not repair this finding.
Correction custody belongs to a fresh F-series author and acceptance requires
a subsequent fresh refuter.
