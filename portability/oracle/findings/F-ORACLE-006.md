# F-ORACLE-006 — root-scalar schema closure is unroutable

Status: **RESOLVED in the current oracle.** This was a credible independent-
oracle coverage defect; the accepted implementation was unchanged. Found by
R-ORACLE-5A at frozen closure 31/57 on 2026-08-10.

## Deletion-minimized replay

```text
raw repr: b'0\n'
raw hex: 300a
raw length: 2
raw SHA-256: 9A271F2A916B0B6EE6CECB2426F0B3206EF074578BE55D9BC94F6F3FE3AB86AA
schedule: isolated invocation; no transport schedule
```

The record is strict UTF-8, LF-framed, canonical JSON, NFC, and within the
number model. It is not an object, so the frozen dispatch/schema closure
selects root-level `ERR_SCHEMA`.

Both accepted generations reproduced this tuple twice:

```text
exit: 2
stderr: empty
stdout length: 335
stdout SHA-256: BAA52EC96ED84A513C18D3FFCB10BC8B4A7E3B5D8FF8C3061B06708178629EAA
stdout:
{"errors":[{"code":"ERR_SCHEMA","message":"Request does not validate.","pointer":"","precedence":80}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"33524008D41EE8D3DBC9EAB632101EE74A59FC1FD103F4C28EF2F920F3880BF7","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

The oracle parse classifier instead reports `ok:true` and
`FixtureOracle.expected_record` raises outside-fixture:

```text
oracle CLI exit: 2
oracle stdout: empty
oracle stdout SHA-256: E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855
oracle stderr SHA-256: EF877DF1E6DD709C8157720EDADA43A08DC5F76172776617E1325DC9AF9801C6
```

Deleting either byte removes the mismatch: `b'\n'` is the already-correct
empty-input closure and `b'0'` is the already-correct missing-LF JSON closure.

The first unminimized frozen witness was a 200,004-byte root array that must
select root `ERR_SCHEMA` before item/resource limit. The 2-byte scalar proves
the underlying missing routing law without the resource dimension.

The correction adds only the independently specified routing required by the
declared finite model: non-object roots select `ERR_SCHEMA` at the empty
pointer, without claiming full schema evaluation. R-ORACLE-5A stopped before
closures 32–57; the later clean refutations completed the required
post-correction coverage, as indexed in [`../STATUS.md`](../STATUS.md).
