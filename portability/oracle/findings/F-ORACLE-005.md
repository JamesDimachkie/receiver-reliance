# F-ORACLE-005 — independent canonical-byte error loses to number error

Status at discovery: credible portability-oracle defect; accepted implementation
unchanged. Found by fresh refuter R-ORACLE-4 during the frozen raw-error closure
sweep on 2026-08-10.

## Deletion-minimized replay

```text
raw repr: b'["\\/",-0]\n'
raw hex: 5b225c2f222c2d305d0a
raw length: 10
raw SHA-256: 027E349A1B98549D0D680F9E0C74C2637B709F962F1CE92B450F645ED743C54C
schedule: isolated invocation; no transport schedule
```

The `\/` spelling is independently noncanonical JSON/JCS while `-0` violates
the numeric profile. The frozen error law therefore selects `ERR_JSON`
(precedence 50) before `ERR_NUMBER` (precedence 70). All ten single-byte
deletions remove the mismatch.

The first frozen closure that exposed the class was
`json-noncanonical-beats-range` with raw
`b'{"b":1,"a":99999999999999999999}\n'`; the 10-byte array above is the
minimized replay.

## Contract-expected / accepted bytes

```text
exit: 2
stderr: empty
stdout length: 338
stdout SHA-256: 9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2
stdout:
{"errors":[{"code":"ERR_JSON","message":"Invalid JSON or trailing bytes.","pointer":"","precedence":50}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"121508D748E28E6D0A7CF3B2903AA979ADFB45E8D6A58D2929236C32AAC3C99C","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

Accepted generations 0.2 and 0.3 each reproduced this tuple byte-identically
twice.

## Oracle-actual bytes before correction

```text
selected error: ERR_NUMBER
pointer: /1
precedence: 70
stdout length: 350
stdout SHA-256: 93C2453AF50154DFD49BA54D2BE91CA8562B2FBFA3C26BBC75A116D5F122EA58
stdout:
{"errors":[{"code":"ERR_NUMBER","message":"Number violates the safe integer model.","pointer":"/1","precedence":70}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"C493C741A987886DB32B8508A41B341B900D815FB1FB35FD3B7AC08E2B2DC6E8","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

Root cause: the oracle returned its recorded bad-number finding before checking
whether another part of the physical payload differed from canonical JCS. A
correction must compare canonical bytes while preserving invalid number
lexemes for that comparison, so `[-0]\n` remains `ERR_NUMBER` but
`["\\/",-0]\n` selects `ERR_JSON`.

## Environment and determinism

```text
OS: Windows-11-10.0.26200-SP0
Python: CPython 3.12.10 [MSC v.1943 64 bit (AMD64)]
Executable: C:\Users\james\AppData\Local\Python\pythoncore-3.12-64\python.exe
Accepted generations: 0.2 and 0.3
Runs per generation: 2
All four accepted runs: exit 2, empty stderr, stdout SHA 9543AAFC...67C2
Wall-clock or random input: none
Network: none
Resource anomaly: none observed
```

R-ORACLE-4 stopped at frozen closure 21; remaining closures and the adjacent
matrix are unexecuted. Correction custody belongs to F-ORACLE-5, followed by a
new fresh refuter.
