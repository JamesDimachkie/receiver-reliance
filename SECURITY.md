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
here; `ERRATA.md` E13 and E14 are two we found ourselves, and
`portability/verify_live.py` exists because of them.

Out of scope, because they are declared rather than defended: the trust root is
the authenticated repository commit, nothing is signed, and an in-repo digest is
drift detection rather than authentication. The harness boundary is likewise a
recorded caveat — a forged `git` earlier on `PATH` makes `verify_hygiene` report
`HYGIENE_PASS` over a planted modification, which is demonstrated in
TRUST_MODEL.md rather than fixed.

## How to report

Use GitHub. If the report should not be public, send it through the
repository's **Security** tab (*Report a vulnerability*), which is private to
the maintainer; otherwise open an issue. Both reach the same person.

Include the commit you tested, the exact command, and the observed output. A
reproduction from a clean clone is worth more than a description, and this
repository is built so that one is always possible.

## What to expect

One maintainer, no team, no on-call rotation, and **no bounty** — there is no
money in this. A realistic acknowledgement window is a few days, not hours.
Fixes land as ordinary public commits with the finding recorded in `ERRATA.md`
or a `findings/` entry, under the same claim discipline as everything else: what
was verified, at which bytes, and what remains open. There is no embargo
process, because there are no deployments to protect — `TRUST_MODEL.md` records
a verified census of **zero external consumers**. If that changes, this page
changes with it.
