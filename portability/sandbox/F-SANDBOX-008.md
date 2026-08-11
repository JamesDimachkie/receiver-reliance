# F-SANDBOX-008 — effective entrypoint was recorded but not enforced

Status: **RESOLVED locally.** Correction retained; final focused suite green.

An otherwise valid selected Docker config replaced the image entrypoint with
`["/bin/sh","-c","emit-forged-pass"]`. The host recorded that value but
`_assert_inspect` did not compare it, so a process other than the expanded gate
could emit a structurally complete forged inner PASS receipt and reach host
`PASS`/exit 0.

The pre-correction selected-config witness is 764 canonical bytes with
SHA-256
`3b00ca00e9cb36c69a5f566b840f8e2ff7300f16d3b1a4d33734220d3b044972`.
The complete synthetic inner receipt accepted by the former mocked flow has
SHA-256
`eb926d64f89077a1b73000b1c144c5a73a64ccce531273152967ddd20acc4f55`.

The correction binds one execution contract across the Dockerfile, printed
create plan, and selected effective config. The Dockerfile now declares the
exact exec-form entrypoint
`["python","-B","/repo/portability/sandbox/expanded_gate.py"]` plus `CMD []`;
the create command ends at the image and supplies no command override; and the
plan records both expected fields. Before start, the host now requires
`Config.Entrypoint` to equal that exact three-string array and `Config.Cmd` to
equal the exact empty array.

Direct and full mocked host-flow regressions reject the minimized shell
witness, string form, extra arguments, missing fields, wrong container types,
an inherited base-image command, and nonempty/string/missing/wrongly typed
commands. In each full-flow case, rejection occurs as
`SANDBOX_SETUP_FAILURE`/exit 1 before the forged inner receipt is admitted.
The exact valid neighbor remains accepted.
