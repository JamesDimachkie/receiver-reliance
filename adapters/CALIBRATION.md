# Portable calibration playbook

Calibration asks two ordered questions before any engine request:

1. Does the native evidence contradict itself or the supplied fact profile?
2. If not, does the record contain the host semantics the selected obligation
   claims to judge?

The order matters. A contradiction is `REJECTED_INVALID` detection even when
other semantics are unavailable. Missing semantics are
`INSUFFICIENT_EVIDENCE` abstention. Neither category is a pass. `READY` only
means the bounded preflight found no such blocker; it is not an engine
decision.

## Write an observable native precondition

Every mapping needs a predicate over raw native claims and observations. It
must not depend on an expected verdict, truth label, local filesystem lookup,
operating-system path rules, current directory, environment variable, network
call, or mutable runner.

| mapping | invalid evidence checked first | sufficient native evidence |
|---|---|---|
| REF / OBL-02 | conflicting exact aliases; presence/content or current/archive contradictions; malformed digests | one exact reference identity and one coherent location/content observation |
| SCOPE / OBL-03 | malformed path testimony; absent commit plus changed paths | complete claimed paths plus coherent commit lookup and changed paths when found |
| SUPERSEDE / OBL-15 | malformed digest, ordinal, citer lists, or chronology | corrected bytes, citer identities, and chronology for every citer |
| LIFECYCLE / OBL-17 | duplicate sequence, equal/decreasing timestamps, conflicting typed/untyped views, or impossible typed order | exactly one typed `EFFECTIVE` followed by one terminal typed `ACKNOWLEDGMENT` in strict sequence and time |

Noncontradictory lifecycle timestamps are not acknowledgment evidence. They
remain `INSUFFICIENT_EVIDENCE` until explicit event types exist.

## Calibrate with paired accounting

1. Pin native corpus bytes and keep adjudicated truth in a separate file.
2. Run preflight on native records before joining truth. Runtime code must not
   receive or inspect truth labels.
3. Count `READY`, `REJECTED_INVALID`, and `INSUFFICIENT_EVIDENCE` separately.
4. For `READY` rows, measure engine behavior only in a pinned offline harness.
   Do not present that mutable harness as fallback functionality.
5. Report clean pass, new false hold, invalid detection, ready-row engine
   detection/miss, and insufficient evidence as disjoint categories.
6. Fail calibration if any insufficient row is counted as pass or detection,
   any invalid row is counted as pass, or a defect moves into insufficiency.
7. Add each contradiction and semantic absence as its own regression before
   changing the predicate.

The recorded forced arm produced 133 false holds among 390 clean records
(34.1%) while detecting 18/18 defects. The portable fallback produces 0 new
false holds and 18/18 total detection: five stale REF alias/path conflicts and
three non-increasing lifecycle records are `REJECTED_INVALID`; ten other
defects remain `READY` and are detected by the accepted core in the bounded
measurement. The 208 untyped, noncontradictory lifecycle rows are
`INSUFFICIENT_EVIDENCE`; none is defective in the pinned truth join.

## Symptoms and responses

- Repeated `REJECTED_INVALID` at one pointer: fix the native observation or
  profile binding; do not retry applicability against contradictory bytes.
- Repeated `INSUFFICIENT_EVIDENCE`: add an atomic native observation for the
  missing concept; schema-compatible defaults are not evidence.
- A profile digest mismatch: discard the profile and regenerate it from the
  exact current observation.
- A profile fact or derivation mismatch: the host mapping drifted from the
  calibrated evidence. Repair it before invocation.
- A formerly detected defect becomes insufficient: the native precondition
  is too narrow. Roll it back and add the defect as a regression.
- A path behaves differently across hosts: remove local path interpretation;
  portable preflight treats paths as opaque, case-sensitive strings.

## Promotion gate for another mapping

Do not extend the fallback rule set until the mapping has an observable
native precondition, contradiction-before-applicability ordering, a closed
host profile shape, field-level evidence bindings, stale/partial/adversarial
tests, at least one sufficient clean case and sufficient defect, and a paired
receipt that keeps invalid and insufficient results separate. This does not
revive the stood-down general adapter.
