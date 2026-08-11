# F-SANDBOX-005 — non-object Docker version probe escapes receipt emission

Status: **RESOLVED locally.** Correction retained; final focused suite green.

The mocked `docker version --format '{{json .}}'` probe exited 0 with stdout
`[]`, SHA-256
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`,
and empty stderr. `json.loads` returned a list, after which an unconditional
`.get` raised `AttributeError`. The host emitted no canonical receipt.

The correction parses the untrusted probe behind an explicit shape boundary
before any member access. Invalid UTF-8/JSON, every non-object root, a missing
or non-object `Server`, a missing or non-string `Server.Os`, and a missing or
non-object `Client` now produce the existing fully bound
`INFRA_UNAVAILABLE` receipt with exit 2 and probe hashes. A valid non-Linux
server retains the same bounded infrastructure classification; a
case-normalized Linux server still reaches the image build.

Mocked main-flow regressions cover the minimized list, `null`, string and
number roots, malformed bytes, missing and wrong `Server`/`Server.Os` shapes,
and valid Linux/non-Linux neighbors. The F-SANDBOX-003 inner-PASS and
F-SANDBOX-004 finite-number hardening remains exercised by the complete suite.
