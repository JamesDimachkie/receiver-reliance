# F-ORACLE-008 — canonical object schema routing is missing

Status: **RESOLVED in the current oracle.** This was a credible independent-
oracle coverage defect found by R-ORACLE-7A at frozen closure 32/57. The
accepted implementation was unchanged.

## Deletion-minimal replay

```text
raw repr: b'{}\n'
raw hex: 7b7d0a
raw length: 3
raw SHA-256: CA3D163BAB055381827226140568F3BEF7EAAC187CEBD76878E0B63E9E442356
```

Both accepted generations return `ERR_SCHEMA` at `/format_version`, exit 2,
empty stderr, stdout length 350, stdout SHA-256
`309E457F8DE3B7970333ABBB017D54BC12507F93E6C833AA9F38130EBC0080CF`.
The oracle raises outside-fixture and emits no stdout.

Deleting any one byte yields an input where oracle and both accepted
generations agree on `ERR_JSON`, proving deletion minimality.

F-ORACLE-006 added only non-object root routing. This correction must add the
independently specified O(1) object-dispatch rule needed by the finite model:
a canonical object whose `format_version` is absent or undeclared selects
`ERR_SCHEMA` at `/format_version`. It must not imply full member-schema
evaluation. Closures 33–57 remain unexecuted under the stop rule.
