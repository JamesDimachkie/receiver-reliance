# F-MATRIX-012 — runnable absence receipts were not source-bound

Status: **RESOLVED locally.** The focused suite rejects missing SHA, dirty
checkout, and wrong-SHA runnable `INFRA_UNAVAILABLE` artifacts.

## Minimized evidence

The summary path applied source binding only to executed outcomes. A runnable
normative target could therefore report `INFRA_UNAVAILABLE` with a stale or
dirty checkout and still satisfy the structural absence rules. Such an
artifact could not prove that the requested revision was the one whose setup
was unavailable.

## Correction

Every runnable outcome, including a legitimate setup or capability absence,
must now bind `git.clean=true`, a present workflow SHA, and equality between
the observed and expected commit SHA. Runtime/environment binding remains
limited to commands that actually executed because absence receipts have no
runtime execution to attest.

## Validation

The existing explicit-setup-unavailable regression now starts from an
internally consistent clean synthetic receipt, then separately removes the
workflow SHA, marks the checkout dirty, and changes the workflow SHA. Each
mutation makes the summary exit 1 and the normative target fail.
