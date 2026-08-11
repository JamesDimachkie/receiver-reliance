# F-SANDBOX-016 — process `HOSTNAME` value was not observed

Status: **RESOLVED locally.** Correction retained; final focused suite green.

The expanded gate required kernel `os.uname().nodename="rr-sandbox"` but
recorded only process environment names. With the actual process environment
mutated to `HOSTNAME=evil-host`, the former `verify_boundary` still returned a
passing boundary. A complete canonical inner PASS using that boundary was
7,603 bytes with SHA-256
`1ef46f205ff58e4f64892ee06db32db833b9529fb135bd16f1468eb3515671f4`;
the host reconciled its kernel hostname and environment-name set while never
observing the process variable's value.

The correction reads `HOSTNAME` before any repository command and requires it
to be the exact string `rr-sandbox`, matching the kernel nodename. The inner
receipt and deterministic projection retain only this single known,
non-secret environment value as `boundary.environment_hostname`; no other
environment values are exposed. Strict inner validation rejects a missing,
null, non-string, case-mutated, whitespace-mutated, or different value.

The host now retains only the already allowlist-validated `Config.Env`
`HOSTNAME` value and reconciles one exact chain before PASS: kernel nodename,
process `HOSTNAME`, inspected `Config.Hostname`, inspected `Config.Env`, the
pinned environment declaration, and the printed plan. Direct boundary,
canonical inner-receipt, and complete mocked host-flow regressions exercise
the minimized mutation and all declared invalid shape/value classes.
