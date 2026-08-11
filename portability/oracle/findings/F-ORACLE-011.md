# F-ORACLE-011 — missing required member is a root-schema failure

Status before correction: credible independent-oracle pointer defect; accepted
implementation unchanged. Found by the fresh clean-room refutation at shared
frozen closure 34 on 2026-08-10.

## Deletion-minimized replay

```text
raw repr:   b'{"format_version":"B1-SEMANTIC-DECISION-REQUEST-0.2"}\n'
raw hex:    7b22666f726d61745f76657273696f6e223a2242312d53454d414e5449432d4445434953494f4e2d524551554553542d302e32227d0a
raw length: 54
raw SHA-256: 2860035C36C06F93A0C922177E799C3042C5E79566C89F8689998DDBCCAA7C37
schedule: isolated invocation; no transport schedule
```

The format dispatch is declared, but the root request object omits every other
required member. A JSON-Schema `required` failure is located at the containing
instance object; the absent child has no instance location. The deterministic
runtime rule then selects the lexicographically smallest detected pointer at
the same precedence. Here all missing-member violations therefore share the
empty root pointer.

All 54 single-byte deletions removed the mismatch in the supplied refuter
evidence.

## Contract-expected / accepted bytes

Both accepted generations reproduced the same tuple twice:

```text
exit: 2
stderr: empty
stdout length: 335
stdout SHA-256: BAA52EC96ED84A513C18D3FFCB10BC8B4A7E3B5D8FF8C3061B06708178629EAA
stdout:
{"errors":[{"code":"ERR_SCHEMA","message":"Request does not validate.","pointer":"","precedence":80}],"exit_code":2,"format_version":"PCB-RUNNER-RESPONSE-0.2","ok":false,"output":null,"receipt_sha256":"33524008D41EE8D3DBC9EAB632101EE74A59FC1FD103F4C28EF2F920F3880BF7","request_id":"RUN_000000000000000000000000","result":"INCOMPLETE"}\n
```

## Rejected oracle behavior

The clean oracle incorrectly invented the absent path `/decision_input`,
emitting 350 stdout bytes with SHA-256
`120BD0E780572D4E7A7290E5C89724FC77B269A83115EE1FE2971F975DEA9916`.
It selected the UTF-8-smallest name among missing properties rather than the
instance location at which the `required` keyword failed.

The narrow correction returns the empty pointer for a missing top-level
required member after successful declared-format dispatch. It preserves
`/format_version` for missing or undeclared dispatch and `/request_id` for a
present request ID that violates its member schema. Regressions cover every
nonempty missing-member combination for both declared formats and the member
limit boundary. This does not add or claim full nested JSON-Schema evaluation.

This correction author did not execute the accepted implementation. The
accepted-result tuple and deletion-minimization facts above are adjudicated
finding evidence supplied by the fresh refuter.
