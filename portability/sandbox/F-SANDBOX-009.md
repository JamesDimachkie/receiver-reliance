# F-SANDBOX-009 — configured entrypoint can disagree with actual process

Status: corrected by fresh F-SANDBOX-9; awaiting fresh refutation.

The exact mocked container inspect retained the expected
`Config.Entrypoint` and `Config.Cmd=[]`, but supplied these root execution
fields:

```json
{"Path":"/bin/sh","Args":["-c","emit-forged-pass"]}
```

The complete canonical inspect witness is 801 bytes with SHA-256
`78abdfa49c34795b091889d09af270edf4511d79e1d0858f5b6c0682387f4786`.
The former selected projection discarded both root fields, so the host could
start that process and accept a structurally complete forged inner PASS whose
SHA-256 is
`eb926d64f89077a1b73000b1c144c5a73a64ccce531273152967ddd20acc4f55`.

Docker Engine's container-inspect response exposes the process executable as
top-level `Path` and its arguments as top-level `Args`, separately from the
container `Config` object. The official Engine API example demonstrates that
distinction: <https://docs.docker.com/reference/api/engine/version/v1.24/#tag/Container/operation/ContainerInspect>.

The correction binds all three representations. The Dockerfile and selected
`Config` remain fixed to exec-form entrypoint
`["python","-B","/repo/portability/sandbox/expanded_gate.py"]` plus an
empty command; the printed plan now records the expected root `path` and
`args`; and the inspected root must be exactly `Path="python"` and
`Args=["-B","/repo/portability/sandbox/expanded_gate.py"]`. Missing, null,
string/list type confusion, extra, reordered, case-mutated, path-mutated, and
flag-mutated forms are rejected before start in both direct and full mocked
host-flow regressions. Prior F-SANDBOX-003 through F-SANDBOX-008 controls
remain in the complete suite.
