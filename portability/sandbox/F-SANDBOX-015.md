# F-SANDBOX-015 — configured hostname was not retained or enforced

Status: **RESOLVED locally.** Correction retained; final focused suite green.

The create plan already supplied both `--hostname rr-sandbox` and
`HOSTNAME=rr-sandbox`, but the selected container-inspect projection discarded
`Config.Hostname`. An inspect object with no `Hostname` member was accepted
through host `PASS`; its canonical form is 1,449 bytes with SHA-256
`5ea68d807d00e0b2f368124b09bc6d14b23d303fb84b11331a3b220590944c14`.
Adding the wrong value `"Hostname":"evil-host"` was likewise accepted; that
canonical object is 1,472 bytes with SHA-256
`c2e2f2be8315f61bd835cc500283ab1f41cbbb6733699cf669a41112af35ad27`.
Thus the configured UTS hostname could diverge from the declared plan and the
pinned process environment without preventing a full PASS.

The correction defines one exact hostname identity, `rr-sandbox`, across the
printed plan, Docker create arguments, pinned `HOSTNAME` value, retained
`Config.Hostname`, and host-side inspect assertion. The inner expanded gate now
records the kernel UTS-namespace nodename from `os.uname().nodename`, requires
that observation to equal `rr-sandbox` before running any repository command,
includes it in the inner boundary receipt and stable projection, and the host
reconciles it to the inspected config after strict receipt validation.

Direct and complete mocked host-flow regressions preserve both exact witnesses
and reject missing, null, boolean, numeric, array, object, empty, case-mutated,
whitespace-mutated, and different inspect values before `docker start`. Inner
receipt regressions reject the same value classes as
`INVALID_CONTAINER_RECEIPT`; a focused boundary test proves the kernel
nodename observation accepts the exact value and rejects `evil-host`. Previous
F-SANDBOX-003 through F-SANDBOX-014 witnesses remain preserved as historical
byte/hash fixtures.
