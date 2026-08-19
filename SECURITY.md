# Reporting a defect

This repository is a research artifact, not a product, and it makes no security
claim — [TRUST_MODEL.md](TRUST_MODEL.md) states canonically what its seals and
receipts do and do not prove, and [ERRATA.md](ERRATA.md) lists the defects
already known and how each is enforced. Read both before reporting: a
substantial share of what looks like a vulnerability here is recorded, bounded,
and deliberate.

## What is in scope

The parser and decision paths that consume untrusted wire bytes
(`grounded-0_4/`, the frozen engines under `baseline-run/`), the preflight in
`adapters/`, the sidecar transport in `perf/sidecar/`, the bundle verifier in
`portable/`, and the custody verifiers in `portability/`. A report that a
verifier reports green over bytes it never checked is the most valuable kind
here; `ERRATA.md` E13 is one we found ourselves, and
`portability/verify_live.py` exists because of it.

Out of scope, because they are declared rather than defended: the trust root is
the authenticated repository commit, nothing is signed, and an in-repo digest is
drift detection rather than authentication. The harness boundary is likewise a
recorded caveat — a forged `git` earlier on `PATH` makes `verify_hygiene` report
`HYGIENE_PASS` over a planted modification, which is demonstrated in
TRUST_MODEL.md rather than fixed.

## How to report

Use GitHub. For anything you would rather not post publicly, the
repository's **Security** tab has *Report a vulnerability*, which is private to
the maintainer. If that option is not showing for you, open an ordinary issue
saying only that you have something to report privately and asking for a
channel — do not put the detail in it. Everything else: open an issue. There is
no security mailing list and no PGP key.

Include the commit you tested, the exact command, and the observed output. A
reproduction from a clean clone is worth more than a description, and this
repository is built so that one is possible for everything in scope above.
Three exceptions are already ledgered and are not oversights: the `proof/` arm
scripts need an operator-only extractor (`WITHHELD.md`), the sealed
subprocess-ABI conformance mode pins a Windows interpreter that is not
distributed ([ADOPTION.md](ADOPTION.md)), and every verifier that shells `git` for
custody or provenance — `verify_hygiene.py`, `test_home_path_disclosure.py`,
`run_local_expanded_gate.py`, and the concurrency, matrix and sandbox harnesses
— needs a real clone rather than an unpacked archive.

## What to expect

One maintainer, no team, no on-call rotation, and **no bounty** — there is no
money in this. A realistic acknowledgement window is a few days, not hours.
Fixes land as ordinary public commits with the finding recorded in `ERRATA.md`
or a `findings/` entry, under the same claim discipline as everything else: what
was verified, at which bytes, and what remains open. There is no embargo
process, because there are no deployments to protect — `TRUST_MODEL.md` records
a verified census of **zero external consumers**. If that changes, this page
changes with it.
