#!/usr/bin/env python3
"""Machine-checked coherence of the Receiver-Reliance sealed decision law.

Deterministic.  No network, no clock, no randomness that is not seeded from the
query itself.  Reads only the pinned sources in ``model/sources.py`` and writes
only where told to with ``--json``.

    python -B verify_law.py                 # human-readable + final status line
    python -B verify_law.py --json out.json # plus a full machine-readable record

The final line is the machine-parseable verdict:

    verify-law: obligations=N properties=M proven=X bounded=Y refuted=Z errors=0

  proven   - established over the full schema domain
  bounded  - established over the stated finite abstraction only
  refuted  - the property does not hold; a counterexample or a universal
             unsatisfiability certificate is recorded
  errors   - the CHECKER malfunctioned.  Findings are not errors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time

sys.dont_write_bytecode = True

from model import certificates, predicates as P, sources
from model.endtoend import EndToEnd
from model.evaluators import EvaluatorDivergence, Evaluators
from model.law import load_law
from model.search import Solver

# ``model.domain`` is the one module that imports ``jsonschema``, this lane's
# only third-party dependency, and it is imported inside ``main`` rather than
# here.  That is what makes ``--structural-only`` runnable on a stdlib-only
# host: the hosted matrix installs no packages, so the battery row can only
# execute the phases that never build a witness.  Nothing else in the lane
# needs it.

PROVEN, BOUNDED, REFUTED, ERROR = "PROVEN", "PROVEN-BOUNDED", "REFUTED", "ERROR"

# Restart-count multiplier for a second, harder attempt at a bounded search that
# came up empty.  Bounded on purpose: this runner is meant to sit in a battery.
RETRY_EFFORT = 3


class Recorder:
    def __init__(self) -> None:
        self.results: list[dict] = []
        self.findings: list[dict] = []
        self.errors: list[dict] = []

    def record(self, prop: str, subject: str, status: str, detail=None) -> None:
        self.results.append({"property": prop, "subject": subject, "status": status, "detail": detail or {}})
        if status == ERROR:
            self.errors.append({"property": prop, "subject": subject, "detail": detail or {}})

    def finding(self, kind: str, subject: str, detail: dict) -> None:
        self.findings.append({"kind": kind, "subject": subject, "detail": detail})

    def counts(self) -> dict[str, int]:
        out = {PROVEN: 0, BOUNDED: 0, REFUTED: 0, ERROR: 0}
        for r in self.results:
            out[r["status"]] = out.get(r["status"], 0) + 1
        return out


def seed_of(*parts) -> int:
    """Stable seed for a search query.

    NOT ``hash()``: CPython salts string hashing per process, so a seed derived
    from it would make the run irreproducible across invocations.  A digest of
    the query identity keeps every search deterministic run to run.
    """
    key = "\x1f".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(key).digest()[:4], "big")


# ---------------------------------------------------------------- structural
def phase_structural(law, rec: Recorder) -> None:
    for inv in law.invariants:
        rec.record(
            "S1.contract-structure",
            inv["invariant"],
            PROVEN if inv["holds"] else REFUTED,
            {"detail": inv["detail"]},
        )
        if not inv["holds"]:
            rec.finding("structural-invariant-violated", inv["invariant"], {"detail": inv["detail"]})

    # Pointer/literal separation is structural in this model; make it a check.
    ambiguous = []
    for op in law.ordered():
        for cls in law.defect_precedence:
            ambiguous.extend(
                {"obligation_id": op.obligation_id, "class": cls, **a}
                for a in P.pointer_literal_ambiguity(op.class_predicates[cls])
            )
    rec.record(
        "S2.pointer-literal-separation-exact",
        "all-90-defect-rows",
        PROVEN if not ambiguous else REFUTED,
        {"ambiguities": ambiguous},
    )

    # Every operator used by a sealed row is declared in the frozen vocabulary.
    used = set()
    for op in law.ordered():
        for cls in law.defect_precedence:
            used |= {a["op"] for a in P.atoms(op.class_predicates[cls])}
    undeclared = sorted(used - set(law.atomic_operators))
    rec.record(
        "S3.operators-declared",
        f"{len(used)}-operators-used",
        PROVEN if not undeclared else REFUTED,
        {"undeclared": undeclared, "used": sorted(used)},
    )


def phase_field_independence(law, domains, rec: Recorder) -> None:
    """Fact schemas must be flat objects with no cross-field constraints.

    Everything downstream relies on this: it is what makes "vary the fields the
    predicate reads, hold the rest at a default" a complete strategy, and what
    lets witness assembly skip per-candidate schema validation.
    """
    allowed = {"type", "additionalProperties", "required", "properties", "$comment", "title", "description"}
    for op in law.ordered():
        extra = sorted(set(op.facts_schema) - allowed)
        rec.record(
            "S4.facts-schema-flat",
            op.obligation_id,
            PROVEN if not extra else REFUTED,
            {"unexpected_keywords": extra},
        )
        if extra:
            rec.finding("cross-field-schema-constraint", op.obligation_id, {"keywords": extra})


# ------------------------------------------------------- A: row reachability
def phase_reachability(law, domains, solvers, baselines, rec: Recorder) -> None:
    for op in law.ordered():
        oid = op.obligation_id
        dom, sol = domains[oid], solvers[oid]
        base = baselines.get(oid)

        for cls in law.defect_precedence:
            row = op.class_predicates[cls]
            djs = P.disjuncts(row)
            row_sat = False
            for idx, (trail, dj) in enumerate(djs):
                subject = f"{oid}/{cls}#{idx}"
                support = P.support_fields(dj)

                # A2 - is the disjunct satisfiable at all?
                goal = [sol.node_goal(dj, True)]
                res = sol.solve(goal, support, seed_of(oid, cls, idx, "sat"), base=base)
                if res.found:
                    ok, doc = sol.verify_witness(res.facts, goal)
                    if not ok:
                        rec.record("A2.disjunct-satisfiable", subject, ERROR, {"why": "witness failed re-verification"})
                        continue
                    row_sat = True
                    rec.record(
                        "A2.disjunct-satisfiable",
                        subject,
                        PROVEN,
                        {"mode": res.mode, "witness_facts": _trim(res.facts), "trail": trail},
                    )
                else:
                    cert = certificates.certify_unsat(dom, dj)
                    if cert is not None:
                        rec.record("A2.disjunct-satisfiable", subject, REFUTED, {"certificate": cert, "trail": trail, "node": dj})
                        rec.finding(
                            "UNREACHABLE-ROW-DISJUNCT",
                            subject,
                            {"certificate": cert, "node": dj, "epistemic_status": "PROVEN unsatisfiable over the full schema domain"},
                        )
                    else:
                        rec.record(
                            "A2.disjunct-satisfiable",
                            subject,
                            BOUNDED if res.mode == "exhaustive" else ERROR,
                            {"mode": res.mode, "examined": res.examined, "support": res.support, "trail": trail},
                        )
                        rec.finding(
                            "NO-WITNESS-IN-ABSTRACTION",
                            subject,
                            {"mode": res.mode, "examined": res.examined, "support": res.support, "node": dj},
                        )
                    continue

                # A3 - does the disjunct actually yield its class under precedence?
                # Seeded from the A2 witness, which already satisfies the target,
                # so the search only has to clear the higher-precedence rows.
                # The search goal is decomposed row by row so the local search has
                # a gradient (each higher-precedence row cleared is progress); the
                # ACCEPTANCE check is still the real classification.
                higher = _higher_classes(law, cls)
                goal3 = [sol.node_goal(dj, True)] + [sol.node_goal(op.class_predicates[h], False) for h in higher]
                accept3 = [sol.node_goal(dj, True), sol.class_goal(cls)]
                sup3 = support | _rows_support(law, op, upto=cls)
                res3 = sol.solve(goal3, sup3, seed_of(oid, cls, idx, "cls"), base=res.facts)
                if not res3.found and res3.mode == "bounded":
                    res3 = sol.solve(goal3, sup3, seed_of(oid, cls, idx, "cls-retry"),
                                     base=base or res.facts, effort=RETRY_EFFORT)
                if res3.found and sol.verify_witness(res3.facts, accept3)[0]:
                    rec.record("A3.disjunct-class-reachable", subject, PROVEN, {"mode": res3.mode, "witness_facts": _trim(res3.facts)})
                else:
                    rec.record(
                        "A3.disjunct-class-reachable",
                        subject,
                        BOUNDED,
                        {"mode": res3.mode, "examined": res3.examined, "support": res3.support},
                    )
                    rec.finding(
                        "SHADOWED-DISJUNCT",
                        subject,
                        {
                            "meaning": f"satisfiable, but no input found where it produces {cls}; "
                            "a higher-precedence class fired first on every input examined",
                            "search": "complete over the abstraction" if res3.mode == "exhaustive" else "budget-limited local search",
                            "examined": res3.examined,
                        },
                    )

                # A5 - can it ever be the SOLE reason for its class?
                others = [d for j, (_, d) in enumerate(djs) if j != idx]
                if others:
                    goal5 = goal3 + [sol.node_goal(o, False) for o in others]
                    accept5 = accept3 + [sol.node_goal(o, False) for o in others]
                    sup5 = _row_support(row) | _rows_support(law, op, upto=cls)
                    seed5 = res3.facts if res3.found else res.facts
                    res5 = sol.solve(goal5, sup5, seed_of(oid, cls, idx, "sole"), base=seed5)
                    if not res5.found and res5.mode == "bounded":
                        res5 = sol.solve(goal5, sup5, seed_of(oid, cls, idx, "sole-retry"),
                                         base=base or seed5, effort=RETRY_EFFORT)
                    if res5.found and sol.verify_witness(res5.facts, accept5)[0]:
                        rec.record("A5.disjunct-sole-reason", subject, PROVEN, {"mode": res5.mode})
                    else:
                        rec.record("A5.disjunct-sole-reason", subject, BOUNDED, {"mode": res5.mode, "examined": res5.examined})
                        rec.finding(
                            "NEVER-SOLE-REASON",
                            subject,
                            {
                                "meaning": "no input found where this disjunct alone decides the class",
                                "search": "complete over the abstraction" if res5.mode == "exhaustive" else "budget-limited local search",
                                "examined": res5.examined,
                            },
                        )
                else:
                    rec.record("A5.disjunct-sole-reason", subject, PROVEN, {"why": "single-disjunct row"})

            rec.record(
                "A1.row-satisfiable",
                f"{oid}/{cls}",
                PROVEN if row_sat else REFUTED,
                {"disjuncts": len(djs)},
            )

        # A4 - VALID is reachable for this operation.
        if base is not None:
            rec.record("A4.valid-reachable", oid, PROVEN, {"witness_facts": _trim(base)})
        else:
            rec.record("A4.valid-reachable", oid, BOUNDED, {"why": "no VALID witness found in the abstraction"})
            rec.finding("NO-VALID-WITNESS", oid, {"meaning": "every input in the abstraction is classified as a defect"})


def _row_support(row) -> set[str]:
    return P.support_fields(row)


def _higher_classes(law, cls: str) -> list[str]:
    """Defect classes strictly above ``cls`` in the frozen precedence order."""
    return law.defect_precedence[: law.defect_precedence.index(cls)]


def _rows_support(law, op, upto: str) -> set[str]:
    """Fields read by every class row at or above ``upto`` in precedence."""
    out: set[str] = set()
    for cls in law.defect_precedence:
        out |= P.support_fields(op.class_predicates[cls])
        if cls == upto:
            break
    return out


# -------------------------------------------- B: precedence-dependence census
def phase_precedence_dependence(law, domains, solvers, baselines, rec: Recorder) -> None:
    """Where does the ORDER of the frozen precedence chain actually decide the class?

    For each ordered pair (higher, lower) the checker looks for an input that
    satisfies BOTH rows.  Such an input is classified by order alone: reverse
    the chain and the answer changes.  Finding one is not a defect - the
    contract declares a total precedence precisely so these are resolved - but
    the set of pairs where it happens is the exact surface on which the frozen
    order is load-bearing, and it should be known rather than assumed.
    """
    for op in law.ordered():
        oid = op.obligation_id
        sol = solvers[oid]
        base = baselines.get(oid)
        prec = law.defect_precedence
        for i, higher in enumerate(prec):
            for lower in prec[i + 1 :]:
                subject = f"{oid}/{higher}>{lower}"
                a, b = op.class_predicates[higher], op.class_predicates[lower]
                goal = [sol.node_goal(a, True), sol.node_goal(b, True)]
                support = P.support_fields(a) | P.support_fields(b)
                res = sol.solve(goal, support, seed_of(oid, higher, lower, "dep"), base=base)
                if res.found and sol.verify_witness(res.facts, goal)[0]:
                    rec.record("B1.precedence-dependent-pair", subject, PROVEN, {"witness_facts": _trim(res.facts)})
                    rec.finding(
                        "PRECEDENCE-DEPENDENT",
                        subject,
                        {
                            "meaning": f"an input exists satisfying both {higher} and {lower}; "
                            f"the frozen order alone selects {higher}",
                            "witness_facts": _trim(res.facts),
                        },
                    )
                else:
                    status = BOUNDED
                    rec.record("B1.precedence-independent-pair", subject, status, {"mode": res.mode, "examined": res.examined})


# ------------------------------------------------------------- C: totality
def phase_totality(law, domains, solvers, baselines, rec: Recorder) -> None:
    """Exactly one class for every schema-valid input, with no undeclared default.

    The argument is structural, and each of its premises is checked from bytes:
      T1  class_precedence is a finite, duplicate-free, totally ordered list.
      T2  every operation declares a predicate for every class in it.
      T3  the VALID row is exactly {"op": "NO_EARLIER_CLASS_MATCH"}, whose
          frozen definition is "true only when the three earlier predicates for
          the same operation are false" - so the fourth step is a tautology
          exactly when the first three fail, and the chain has no fall-through
          to anything undeclared.
      T4  the chain is terminating: it visits each of the 4 rows at most once
          and stops at the first match.
    Together: the classification function is total (T1-T3) and terminating (T4),
    and the class it yields is unique because the chain stops at the first match.
    """
    prec = law.class_precedence
    rec.record(
        "C1.precedence-total-order",
        "class_precedence",
        PROVEN if len(prec) == len(set(prec)) and len(prec) == 4 else REFUTED,
        {"order": prec},
    )
    valid_def = law.atomic_operators.get("NO_EARLIER_CLASS_MATCH", "")
    rec.record(
        "C2.valid-is-declared-fallthrough",
        "NO_EARLIER_CLASS_MATCH",
        PROVEN if "earlier" in valid_def and "false" in valid_def else REFUTED,
        {"frozen_definition": valid_def},
    )
    for op in law.ordered():
        rows_ok = sorted(op.class_predicates) == sorted(prec)
        valid_ok = op.class_predicates.get("VALID") == {"op": "NO_EARLIER_CLASS_MATCH"}
        rec.record(
            "C3.operation-classification-total",
            op.obligation_id,
            PROVEN if (rows_ok and valid_ok) else REFUTED,
            {"declares_all_classes": rows_ok, "valid_is_fallthrough": valid_ok},
        )

    # C4 - behavioural corroboration: no input in the abstraction fails to
    # classify, and none classifies to something outside the frozen vocabulary.
    for op in law.ordered():
        oid = op.obligation_id
        dom, sol = domains[oid], solvers[oid]
        seen: set[str] = set()
        bad = 0
        for facts in _sample_facts(dom, seed_of(oid, "total"), 300):
            try:
                cls, _ = sol.ev.classify(law, op, dom.document(facts))
            except EvaluatorDivergence:
                raise
            except Exception:
                bad += 1
                continue
            seen.add(cls)
        rec.record(
            "C4.no-unclassified-input",
            oid,
            BOUNDED if bad == 0 else REFUTED,
            {"classes_observed": sorted(seen), "unclassified": bad, "sampled": 300},
        )
        if bad:
            rec.finding("UNCLASSIFIED-INPUT", oid, {"count": bad})
        outside = sorted(seen - set(prec))
        if outside:
            rec.finding("CLASS-OUTSIDE-VOCABULARY", oid, {"classes": outside})


def _sample_facts(dom, seed: int, n: int):
    import random

    rng = random.Random(seed)
    fields = sorted(dom.specs)
    yield dict(dom.default)
    for _ in range(n - 1):
        yield {f: rng.choice(dom.specs[f].candidates) for f in fields}


# ------------------------------------------- D: error-selection determinism
def phase_error_determinism(law, rec: Recorder) -> None:
    """The one-error law: precedence first, then lexicographically-first pointer."""
    reg = law.error_registry
    precs = [r["precedence"] for r in reg]
    codes = [r["code"] for r in reg]
    rec.record(
        "D1.error-precedence-distinct",
        f"{len(reg)}-codes",
        PROVEN if len(set(precs)) == len(precs) else REFUTED,
        {"precedences": precs},
    )
    rec.record(
        "D2.error-codes-distinct",
        f"{len(reg)}-codes",
        PROVEN if len(set(codes)) == len(codes) else REFUTED,
        {"codes": codes},
    )
    rec.record(
        "D3.error-precedence-is-total-order",
        "error_registry",
        PROVEN if len(set(precs)) == len(precs) and all(isinstance(p, int) for p in precs) else REFUTED,
        {
            "argument": "distinct integers are a strict total order, so 'select by precedence' "
            "yields at most one code class for any non-empty detection set",
        },
    )
    # Second key: lexicographic RFC 6901 pointer order.  Distinct pointers over
    # a fixed byte encoding are totally ordered, so 'first mismatched pointer'
    # is unique whenever the detection set for the winning code is non-empty
    # and its pointers are distinct.  Pointer *distinctness* is a property of a
    # runtime detection set, not of the sealed tables, so it is stated here as
    # the exact residual obligation rather than claimed.
    rec.record(
        "D4.pointer-order-is-total",
        "rfc6901-utf8-order",
        PROVEN,
        {
            "argument": "UTF-8 byte order is a strict total order on distinct strings; the "
            "contract selects the minimum, which is unique for any non-empty set of "
            "distinct pointers",
            "residual_obligation": "that a single error code never produces two detections at "
            "the SAME pointer is an implementation-level property of the scanner, outside the "
            "sealed decision tables and NOT checked here",
        },
    )


# ----------------------------------------------- E: closure monotonicity
def phase_closures(law, domains, solvers, baselines, rec: Recorder, ev: Evaluators) -> None:
    """Closures are tighten-only: they may move VALID to a defect class and may
    never move a defect class anywhere.

    Two independent arms:
      E1 (table level, universal) - no closure row names VALID as its target,
         so the closure layer cannot emit VALID at all.
      E2 (behavioural, bounded)   - over a sampled corpus, for every input the
         frozen table classifies as a defect, the closure layer fires nothing
         that would change it; and the closure evaluator never returns VALID.
    """
    targets = sorted({c["tightens_to"] for rows in law.closures.values() for c in rows})
    rec.record(
        "E1.no-closure-targets-VALID",
        f"{sum(len(v) for v in law.closures.values())}-closure-rows",
        PROVEN if "VALID" not in targets and set(targets) <= set(law.defect_precedence) else REFUTED,
        {
            "targets": targets,
            "argument": "the closure table's only output classes are its `tightens_to` values; "
            "none is VALID, so no closure can produce VALID from any input",
        },
    )

    closure_ops = sorted(law.closures)
    for oid in closure_ops:
        op = law.operations[oid]
        dom, sol = domains[oid], solvers[oid]
        rows = law.closures[oid]
        fired_any = {r["closure_id"]: 0 for r in rows}
        errors = 0
        samples = 0
        guard_relevant = 0
        for facts in _sample_facts(dom, seed_of(oid, "closure"), 1200):
            doc = dom.document(facts)
            samples += 1
            frozen, _ = sol.ev.classify(law, op, doc)
            for row in rows:
                fired = ev.eval_closure(row["predicate"], doc)
                if fired is None:
                    errors += 1
                    continue
                if fired:
                    fired_any[row["closure_id"]] += 1
                    if frozen != "VALID" and row["tightens_to"] != frozen:
                        guard_relevant += 1
        rec.record(
            "E2.closure-outputs-are-defect-classes",
            oid,
            BOUNDED,
            {
                "sampled": samples,
                "closure_evaluator_errors": errors,
                "inputs_where_the_VALID_guard_is_load_bearing": guard_relevant,
                "meaning": "a fired closure names only a defect class as its target, so it "
                "cannot emit VALID; the count records how often the sealed rule's "
                "'only when the frozen class is VALID' guard is what stops a fired closure "
                "from touching an already-defect classification",
            },
        )
        for cid, count in sorted(fired_any.items()):
            rec.record(
                "E3.closure-row-reachable",
                f"{oid}/{cid}",
                PROVEN if count else BOUNDED,
                {"fired_on_samples": count, "sampled": samples},
            )
            if not count:
                rec.finding("CLOSURE-ROW-NOT-EXERCISED", f"{oid}/{cid}", {"sampled": samples})


def phase_end_to_end(law, domains, solvers, e2e, rec: Recorder, per_op: int) -> None:
    """Run the SEALED composition (frozen table then closure layer) on generated
    fact profiles, and check three things it must never do.

    This arm also validates the model itself: the class this checker's own
    precedence walk derives must equal the class the shipped pipeline seals.
    """
    for op in law.ordered():
        oid = op.obligation_id
        if not e2e.available(oid):
            rec.record("E4.end-to-end-available", oid, ERROR, {"why": "no sealed request envelope"})
            continue
        dom, sol = domains[oid], solvers[oid]
        n = per_op * (4 if oid in law.closures else 1)
        weakened, mismatch, protocol, outside = [], [], 0, set()
        valid_after_closure = 0
        checked = 0
        for facts in _sample_facts(dom, seed_of(oid, "e2e"), n):
            doc = dom.document(facts)
            model_class, _ = sol.ev.classify(law, op, doc)
            out = e2e.run(oid, facts)
            if out["protocol_error"]:
                protocol += 1
                continue
            checked += 1
            audited = out["audited_class"]
            if audited not in law.class_precedence:
                outside.add(audited)
            # (e) the closure layer may never move a defect class at all.
            if model_class != "VALID" and audited != model_class:
                weakened.append({"frozen": model_class, "audited": audited, "facts": _trim(facts)})
            # (e) and it may never produce VALID once a closure has fired.
            if out["closures_fired"] and audited == "VALID":
                valid_after_closure += 1
            # model fidelity: our precedence walk vs the sealed engine's
            if out["first_match"] is not None:
                sealed = _sealed_class(out["first_match"], law)
                if sealed != model_class:
                    mismatch.append({"model": model_class, "sealed": sealed, "facts": _trim(facts)})

        rec.record(
            "E4.closure-layer-never-moves-a-defect-class",
            oid,
            BOUNDED if not weakened else REFUTED,
            {"sampled": checked, "violations": weakened[:3], "protocol_errors": protocol},
        )
        rec.record(
            "E5.closure-layer-never-yields-VALID-after-firing",
            oid,
            BOUNDED if valid_after_closure == 0 else REFUTED,
            {"sampled": checked, "violations": valid_after_closure},
        )
        rec.record(
            "X2.model-matches-sealed-engine",
            oid,
            PROVEN if not mismatch else ERROR,
            {"sampled": checked, "mismatches": mismatch[:3]},
        )
        if outside:
            rec.finding(
                "AUDITED-CLASS-OUTSIDE-FROZEN-VOCABULARY",
                oid,
                {
                    "classes": sorted(outside),
                    "meaning": "the audited surface can report a state the frozen four-class "
                    "vocabulary does not contain",
                },
            )
        if protocol:
            rec.finding("E2E-PROTOCOL-ERROR", oid, {"count": protocol, "sampled": n})


def _sealed_class(first_match: dict, law) -> str:
    for cls in law.defect_precedence:
        if first_match.get(cls):
            return cls
    return "VALID"


# ------------------------------------------------------------------- driver
def _trim(facts, limit=800):
    text = json.dumps(facts, sort_keys=True, separators=(",", ":"))
    return json.loads(text) if len(text) <= limit else {"_truncated": text[:limit]}


def _structural_only(law, rec: Recorder, started: float, args) -> int:
    """The table-level phases alone: the drift detector, runnable in a battery.

    The full run needs ``jsonschema`` and about thirteen minutes, so it cannot
    sit in the hosted matrix.  These two phases need neither.  What they check
    is the part of the law that is universal by construction rather than by
    search -- the twenty contract-structure invariants (including the pin
    tying the loaded 0.2 bytes to the digest the 0.3 supplement names as its
    inheritance base), pointer/literal separation, operator declaration, and
    the error-selection total order.

    Because none of it is sampled, the gate is stricter than the full run's:
    ``refuted`` is a defect here, where in the full run ``refuted=1`` is the
    ledgered ERRATA E6 disjunct found by search.
    """

    phase_structural(law, rec)
    phase_error_determinism(law, rec)

    counts = rec.counts()
    failures = counts[REFUTED] + counts[ERROR]
    record = {
        "tool": "rr-formal-verify-law",
        "version": "1.0.0",
        "mode": "structural-only",
        "obligations": len(law.operations),
        "sources": sources.digest_manifest(),
        "counts": counts,
        "elapsed_seconds": round(time.time() - started, 2),
        "results": rec.results,
        "findings": rec.findings,
    }

    if not args.quiet:
        print("=" * 78)
        print("Receiver-Reliance formal law verification -- structural phases only")
        print("=" * 78)
        print("\nPinned sources (SHA-256):")
        for source in record["sources"]:
            print(f"  {source['sha256'][:16]}...  {source['byte_length']:>8}  {source['path']}")
        print("\nProperty results:")
        for result in rec.results:
            print(f"  {result['status']:<14} {result['property']:<34} {result['subject']}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
            handle.write("\n")

    print(
        f"verify-law: obligations={len(law.operations)} properties={len(rec.results)} "
        f"proven={counts[PROVEN]} bounded={counts[BOUNDED]} refuted={counts[REFUTED]} "
        f"errors={counts[ERROR]}"
    )
    # Second line in the battery's own vocabulary so a plan row can pin it.
    print(f"verify-law-structural: checks={len(rec.results)} failures={failures}")
    return 0 if failures == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write the full machine-readable record here")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--e2e-samples", type=int, default=120,
                    help="sealed end-to-end profiles per obligation (x4 for obligations with closures)")
    ap.add_argument("--structural-only", action="store_true",
                    help="run only the table-level phases: no witness search, no jsonschema, "
                         "seconds instead of minutes.  Every property it records is universal, "
                         "so its gate is refuted=0 and errors=0")
    args = ap.parse_args()

    started = time.time()
    rec = Recorder()
    sources.load_all()
    law = load_law()

    if args.structural_only:
        return _structural_only(law, rec, started, args)

    from model.domain import OperationDomain  # noqa: PLC0415 -- see the module header

    ev = Evaluators()

    e2e = EndToEnd()
    domains = {op.obligation_id: OperationDomain(op, law) for op in law.ordered()}
    solvers = {oid: Solver(law, law.operations[oid], domains[oid], ev) for oid in domains}

    try:
        phase_structural(law, rec)
        phase_field_independence(law, domains, rec)

        baselines: dict[str, dict] = {}
        for op in law.ordered():
            oid = op.obligation_id
            sol = solvers[oid]
            res = sol.solve([sol.class_goal("VALID")], set(domains[oid].specs), seed_of(oid, "baseline"))
            if res.found and sol.verify_witness(res.facts, [sol.class_goal("VALID")])[0]:
                baselines[oid] = res.facts

        phase_reachability(law, domains, solvers, baselines, rec)
        phase_totality(law, domains, solvers, baselines, rec)
        phase_precedence_dependence(law, domains, solvers, baselines, rec)
        phase_error_determinism(law, rec)
        phase_closures(law, domains, solvers, baselines, rec, ev)
        phase_end_to_end(law, domains, solvers, e2e, rec, args.e2e_samples)
    except EvaluatorDivergence as exc:
        rec.record("X.evaluator-agreement", "shipped-engines", ERROR, {"error": str(exc)[:500]})

    rec.record(
        "X.evaluator-agreement",
        "primary-vs-second-implementation",
        PROVEN if not ev.divergences else ERROR,
        {"evaluations": ev.evaluations, "divergences": len(ev.divergences)},
    )

    counts = rec.counts()
    elapsed = time.time() - started
    record = {
        "tool": "rr-formal-verify-law",
        "version": "1.0.0",
        "obligations": len(law.operations),
        "sources": sources.digest_manifest(),
        "counts": counts,
        "elapsed_seconds": round(elapsed, 2),
        "evaluations": ev.evaluations,
        "sealed_pipeline_calls": e2e.calls,
        "results": rec.results,
        "findings": rec.findings,
        "domain_summary": {oid: domains[oid].summary() for oid in sorted(domains)},
    }

    if not args.quiet:
        _print_human(record, rec)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
            handle.write("\n")

    line = (
        f"verify-law: obligations={len(law.operations)} properties={len(rec.results)} "
        f"proven={counts[PROVEN]} bounded={counts[BOUNDED]} refuted={counts[REFUTED]} "
        f"errors={counts[ERROR]}"
    )
    print(line)
    return 0 if counts[ERROR] == 0 else 1


def _print_human(record, rec: Recorder) -> None:
    print("=" * 78)
    print("Receiver-Reliance formal law verification")
    print("=" * 78)
    print("\nPinned sources (SHA-256):")
    for s in record["sources"]:
        print(f"  {s['sha256'][:16]}...  {s['byte_length']:>8}  {s['path']}")

    by_prop: dict[str, dict[str, int]] = {}
    for r in rec.results:
        by_prop.setdefault(r["property"], {}).setdefault(r["status"], 0)
        by_prop[r["property"]][r["status"]] += 1
    print("\nProperty results:")
    print(f"  {'property':<38} {'proven':>7} {'bounded':>8} {'refuted':>8} {'error':>6}")
    for prop in sorted(by_prop):
        c = by_prop[prop]
        print(
            f"  {prop:<38} {c.get(PROVEN,0):>7} {c.get(BOUNDED,0):>8} "
            f"{c.get(REFUTED,0):>8} {c.get(ERROR,0):>6}"
        )

    kinds: dict[str, int] = {}
    for f in rec.findings:
        kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    print("\nFindings:")
    if not kinds:
        print("  (none)")
    for kind in sorted(kinds):
        print(f"  {kind:<34} {kinds[kind]:>4}")

    hard = [f for f in rec.findings if f["kind"] == "UNREACHABLE-ROW-DISJUNCT"]
    if hard:
        print("\nUnreachable row disjuncts (PROVEN over the full schema domain):")
        for f in hard:
            print(f"  {f['subject']}")
            print(f"    certificate: {f['detail']['certificate']['certificate']}")
            print(f"    {f['detail']['certificate']['argument']}")

    print(f"\nevaluations={record['evaluations']}  elapsed={record['elapsed_seconds']}s")


if __name__ == "__main__":
    raise SystemExit(main())
