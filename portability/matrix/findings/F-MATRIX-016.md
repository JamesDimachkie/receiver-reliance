# F-MATRIX-016 — response-era pins in the live schedules and the envelope auditor

Status: **RESOLVED in the commit carrying this finding; the first green
`main` portability run after it supersedes the red run below.**

After F-MATRIX-015 cleared the pre-run pin layer, portability run
`31768000671`-era re-run `31768000667` (`5f9fbde`) progressed into the
matrix command list and failed one stratum deeper, on two harnesses that
bind the accepted implementation's response bytes and had never met the
robustness tree — neither the branch battery nor the program's local
terminal battery ran them:

- `portability/live/schedules/*.ndjson` pin exact response read ranges.
  The 0.4.1 audit format (`f08fa34`: governing-authority digests, closure
  fail-closed, truncation disclosure) grew the single-record response from
  812 to 1,212 bytes and the multi-record buffering response from 106,372
  to 158,772 bytes, so every non-disruptive schedule read an era-sized
  prefix and `LiveTransportTests.setUpClass` failed closed with
  `delayed_flush.ndjson/pipe: live bytes differ from isolated bytes`
  before any live test ran. `test_live.py` also asserted the 812-byte
  response length directly. A plain full-read subprocess run is
  byte-identical to the isolated computation — the divergence was entirely
  the pinned read windows;
- `portability/concurrency/ladder.py` pins the audited envelope format
  version (`AUDITED_FORMAT_VERSION = "B1-AUDITED-DECISION-0.4"`). The
  0.4.1 envelope keeps the frozen six-field top-level surface, so the
  independent auditor rejected every real envelope on the version string
  alone, cascading eight of fifteen ladder tests (targeted corruption
  tests saw `audited_envelope_version` instead of their intended
  rejection kinds).

Resolution: the six schedule read ranges re-pinned to the measured 0.4.1
response sizes (five at 1,212; buffering at 158,772), the direct length
assertion moved to 1,212, and the auditor's version pin moved to
`B1-AUDITED-DECISION-0.4.1` — its frozen field surface, seal recompute,
and oracle projection hold unchanged over the 0.4.1 envelope. Synthetic
control-protocol fixtures that use 812 as an arbitrary payload size are
untouched.

Same class as F-MATRIX-013/014/015: pinned bindings to program-era truths
must migrate in the same change that moves the truths. The verification
gap that let two red runs happen sequentially is also closed here: this
repair ran the complete 18-command focused profile locally — matrix 48,
model 17, oracle 35, live 33, concurrency 15 plus the smoke driver
(status=PASS), sandbox 77, portable gate untouched by manifest check,
`verify_receipts` 193/0, `HYGIENE_PASS` 980/2 with custody 12/12, and the
grounded/lint/properties/adversarial/proof/fuzz counts already
hosted-confirmed on these bytes by robustness-verification run
`31765740175`.
