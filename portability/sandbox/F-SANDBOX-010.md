# F-SANDBOX-010 — inspected container identity was not bound to create

Status: **RESOLVED locally.** Correction retained; final focused suite green.

The exact mocked host flow let `docker create` return the lowercase container
identifier `a` repeated 64 times while container inspect returned an otherwise
valid object whose root `Id` was `b` repeated 64 times. The selected inspect
projection discarded `Id`, so the host accepted that object's hardening and
execution fields, started the create-side identifier, and admitted a complete
forged inner PASS receipt.

The canonical inspect witness is 898 bytes with SHA-256
`dbd52a5cd753d37069fd33525ae3899a758c6fd3c9420eb4dccef8118a008f8f`.
The admitted inner receipt has SHA-256
`eb926d64f89077a1b73000b1c144c5a73a64ccce531273152967ddd20acc4f55`.

The correction validates Docker create output before assigning it as a
container handle. It permits one lowercase 64-hex identifier with no
identifier whitespace and only the CLI's optional single LF or CRLF line
terminator. Container inspect's root `Id` is retained in the selected
projection and must be the exact create-side identifier before start. The
same unchanged identifier is used for inspect, attached start, and forced
cleanup. Missing, null, wrongly typed, case-mutated, prefixed, short, long,
whitespace-mutated, and different inspect IDs are rejected before start;
malformed create output is rejected before inspect or cleanup.

Direct and full mocked-flow regressions reproduce the exact witness, exercise
every declared invalid class, prove that mismatched inspect identity cannot
reach start, and prove the valid neighbor uses one identical identifier for
inspect, start, and remove. F-SANDBOX-003 through F-SANDBOX-009 controls remain
in the complete suite.
