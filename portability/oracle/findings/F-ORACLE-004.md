# F-ORACLE-004 — repeated escaped lone-surrogate keys lose duplicate precedence

Status at discovery: credible portability-oracle defect; accepted implementation
unchanged. Found by fresh refuter R-ORACLE-3 after the F-ORACLE-003 correction
on 2026-08-10.

## Deletion-minimized replay

```text
raw repr: b'{"\\ud800":0,"\\ud800"'
raw hex: 7b225c7564383030223a302c225c756438303022
raw length: 20
raw SHA-256: 9710A2170A8CA613B65BBD743F0FA8C7ADD761629B55D3BB44DA9D5DD6C035D0
schedule: isolated invocation; no transport schedule
```

Both member names decode to the same invalid lone high-surrogate value. The
frozen error law pools that repeated decoded name and selects duplicate key
(precedence 40) before invalid JSON (precedence 50), even though later syntax
and framing are incomplete. All 20 single-byte deletions remove the mismatch.

## Contract-expected / accepted bytes

```text
exit: 2
stderr: empty
stdout length: 342
stdout SHA-256: 6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01
stdout:
{"errors":[{"code":"ERR_DUPLICATE_KEY","message":"Duplicate JSON object key.","pointer":"","precedence":40}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"A7E43CA772D54C98193C02100AC1F23E75B312DCAF3F3857E737A805DBF92D29","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

Accepted generations 0.2 and 0.3 each reproduced this tuple byte-identically
twice.

## Oracle-actual bytes before correction

```text
selected error: ERR_JSON
precedence: 50
stdout length: 338
stdout SHA-256: 9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2
stdout:
{"errors":[{"code":"ERR_JSON","message":"Invalid JSON or trailing bytes.","pointer":"","precedence":50}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"121508D748E28E6D0A7CF3B2903AA979ADFB45E8D6A58D2929236C32AAC3C99C","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

Root cause: the independent parser raised on the first escaped lone surrogate,
so it never retained the invalid decoded name long enough to recognize the
second occurrence. A correction must preserve invalid decoded surrogate
identity for duplicate pooling while still classifying a lone occurrence as
`ERR_JSON`.

## Environment and determinism

```text
OS: Windows-11-10.0.26200-SP0
Python: CPython 3.12.10 [MSC v.1943 64 bit (AMD64)]
Executable: C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe
Accepted generations: 0.2 and 0.3
Runs per generation: 2
All four accepted runs: exit 2, empty stderr, stdout SHA 6D204C04...9C01
Wall-clock or random input: none
Network: none
Resource anomaly: none observed
```

R-ORACLE-3 stopped after this first credible finding. Correction custody
belongs to F-ORACLE-4, followed by a new fresh refuter.
