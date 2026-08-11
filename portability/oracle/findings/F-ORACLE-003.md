# F-ORACLE-003 — valid request ID lost on a framing error

Status at discovery: credible portability-oracle defect; accepted implementation
unchanged. Found by fresh refuter R-ORACLE-2 after the F-ORACLE-002 correction
on 2026-08-10.

## Minimized replay

```text
raw repr: b'{"request_id":"RUN_000000000000000000000001"}'
raw hex: 7b22726571756573745f6964223a2252554e5f303030303030303030303030303030303030303030303031227d
raw length: 45
raw SHA-256: EA1B9663B4B708277F8D82340AFFBB9C387518D85EFC7E9F44F5F6665752BC91
schedule: isolated invocation; no transport schedule
```

The payload is strict JSON and contains a valid nonzero request ID, but the
physical record lacks terminal LF. The deterministic runtime contract says to
retain a request ID after strict JSON parsing and `RUN_[A-F0-9]{24}`
validation. Missing LF selects `ERR_JSON`; it does not erase that parsed ID.

All 45 single-byte deletions eliminate this exact mismatch. Changing the final
ID nibble from `1` to `0` also eliminates it because the oracle's incorrectly
zeroed value then happens to equal the input. This pins the nonzero valid-ID
boundary.

## Contract-expected / accepted bytes

```text
exit: 2
stderr: empty
stdout length: 338
stdout SHA-256: 69BDF8EB18E76E0C31692CC87977FAEB9437AEDB0935D2FBB8F616DC5FDE3B24
stdout:
{"errors":[{"code":"ERR_JSON","message":"Invalid JSON or trailing bytes.","pointer":"","precedence":50}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"0FC00640300C6E851F079169DE23D0B9FEEC17E6191FDB06AE64A697AAC472E3","request_id":"RUN_000000000000000000000001","result":"INCOMPLETE"}\n
```

Accepted generations 0.2 and 0.3 each reproduced this tuple byte-identically
twice.

## Oracle-actual bytes before correction

```text
selected error: ERR_JSON
request_id: RUN_000000000000000000000000
stdout length: 338
stdout SHA-256: 9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2
stdout:
{"errors":[{"code":"ERR_JSON","message":"Invalid JSON or trailing bytes.","pointer":"","precedence":50}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"121508D748E28E6D0A7CF3B2903AA979ADFB45E8D6A58D2929236C32AAC3C99C","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

Root cause: the oracle completed strict parsing but returned on the framing
error before extracting and validating `request_id` from the parsed object.

## Environment and determinism

```text
OS: Windows-11-10.0.26200-SP0
Python: CPython 3.12.10 [MSC v.1943 64 bit (AMD64)]
Executable: C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe
Accepted generations: 0.2 and 0.3
Runs per generation: 2
All four accepted runs: exit 2, empty stderr, stdout SHA 69BDF8EB...3B24
Wall-clock or random input: none
Network: none
Resource anomaly: none observed
```

R-ORACLE-2 stopped after this first credible finding. The repeated
lone-surrogate-key candidate remains deliberately unadjudicated for the next
fresh refuter. Correction custody belongs to F-ORACLE-3.
