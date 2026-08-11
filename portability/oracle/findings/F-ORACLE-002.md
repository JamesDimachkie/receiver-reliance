# F-ORACLE-002 — LF-only physical record is empty input

Status at discovery: credible portability-oracle defect; accepted implementation
unchanged. Found by fresh refuter R-ORACLE-1 after F-ORACLE-001 correction on
2026-08-10.

## Deletion-minimal replay

```text
raw repr:   b'\n'
raw hex:    0a
raw length: 1
raw SHA-256: 01BA4719C80B6FE911B091A7C05124B64EEECE964E09C058EF8F9805DACA546B
schedule: isolated invocation; no transport schedule
```

Deleting the only byte produces `b''`, which the oracle already classifies as
`ERR_EMPTY_INPUT`; therefore this witness is deletion-minimal.

The frozen conformance suites pin `("lf-only", b"\n",
"ERR_EMPTY_INPUT", "")`. Both accepted generations returned the contract
response below twice, byte-identically.

## Contract-expected / accepted bytes

```text
exit: 2
stderr: empty
stdout length: 339
stdout SHA-256: D157963B0C06176A634B0C3F8F016A05C9EECDEF3F0479EFAD62E62C51156752
stdout:
{"errors":[{"code":"ERR_EMPTY_INPUT","message":"Input is absent or empty.","pointer":"","precedence":10}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"7C982F0A258EE9B7565FAD18CEBF3B8EA4170B7FC0BBC87FD4364A607757FEF1","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

## Oracle-actual bytes before correction

```text
selected error: ERR_JSON
precedence: 50
stdout length: 338
stdout SHA-256: 9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2
stdout:
{"errors":[{"code":"ERR_JSON","message":"Invalid JSON or trailing bytes.","pointer":"","precedence":50}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"121508D748E28E6D0A7CF3B2903AA979ADFB45E8D6A58D2929236C32AAC3C99C","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

Root cause: the oracle recognized only zero physical bytes as empty, then
stripped the terminal LF and attempted to parse an empty payload. The contract
also treats a single LF physical record as empty input.

## Environment and determinism

```text
OS: Windows-11-10.0.26200-SP0
Python: CPython 3.12.10 [MSC v.1943 64 bit (AMD64)]
Executable: C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe
Accepted generations: 0.2 and 0.3
Runs per generation: 2
All four accepted runs: exit 2, empty stderr, stdout SHA D157963B...6752
Wall-clock or random input: none
Network: none
Resource anomaly: none observed
```

R-ORACLE-1 stopped after this first credible finding and did not expand two
additional candidate families. Correction custody belongs to a new fresh
F-series author, followed by another fresh refuter.
