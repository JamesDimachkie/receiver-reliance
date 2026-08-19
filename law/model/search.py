"""Witness search over the finite abstraction.

Two search modes, and the distinction between them is the whole epistemic
story:

* ``exhaustive`` — the Cartesian product of the candidate lists of every field
  the goal reads is small enough to enumerate completely.  A negative result is
  then a real non-existence result *over the abstraction*, and when every one
  of those fields is additionally ``exhaustive`` (its candidate list IS its
  complete schema domain) it is a non-existence result over the full schema
  domain, because predicate evaluation reads nothing else.

* ``bounded`` — the product is too large, so a deterministic seeded local
  search is used.  A negative result then means only "not found within
  budget", never "unsatisfiable".

Positives are never heuristic: a witness is accepted only when ``jsonschema``
validates the assembled document against the sealed ``decision_input_schema``
branch and both shipped evaluators agree the goal holds.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass
from typing import Any, Callable

# (probe, expected, fields the probe reads).  The third element is what makes
# the local search goal-directed: when a sub-goal is unmet, only the fields it
# actually reads are worth mutating.
Goal = list[tuple[Callable[[dict[str, Any]], Any], Any, tuple[str, ...]]]

PRODUCT_CAP = 400_000
LOCAL_RESTARTS = 20
LOCAL_STEPS = 700


@dataclass
class SearchResult:
    found: bool
    facts: dict[str, Any] | None
    mode: str  # "exhaustive" | "bounded"
    complete_over_schema: bool
    examined: int
    support: list[str]


class Solver:
    def __init__(self, law, operation, domain, evaluators) -> None:
        self.law = law
        self.op = operation
        self.dom = domain
        self.ev = evaluators

    # -- goal helpers ------------------------------------------------------
    def node_goal(self, node: dict[str, Any], expected: bool):
        from . import predicates as _P

        def probe(doc: dict[str, Any]):
            return self.ev.eval_predicate(node, doc)

        return (probe, expected, tuple(sorted(_P.support_fields(node))))

    def class_goal(self, class_name: str):
        def probe(doc: dict[str, Any]):
            return self.ev.classify(self.law, self.op, doc)[0]

        return (probe, class_name, tuple(sorted(self.dom.specs)))

    # -- evaluation --------------------------------------------------------
    def _score(self, facts: dict[str, Any], goal: Goal) -> int:
        # Schema validity is guaranteed by construction: every candidate value
        # was validated against its own field schema, and `facts` schemas in
        # this contract are flat objects with no cross-field constraints (a
        # machine-checked invariant, see verify_law.py structural phase).  Every
        # ACCEPTED witness is still re-validated against the sealed
        # decision_input_schema branch by `verify_witness`.
        doc = self.dom.document(facts)
        hits = 0
        for probe, expected, _fields in goal:
            try:
                if probe(doc) == expected:
                    hits += 1
            except Exception:
                pass
        return hits

    def _unmet_fields(self, facts: dict[str, Any], goal: Goal) -> list[str]:
        doc = self.dom.document(facts)
        out: list[str] = []
        for probe, expected, fields in goal:
            try:
                met = probe(doc) == expected
            except Exception:
                met = False
            if not met:
                out.extend(fields)
        return out

    # -- search ------------------------------------------------------------
    def solve(self, goal: Goal, support: set[str], seed: int, base: dict[str, Any] | None = None,
              effort: int = 1) -> SearchResult:
        fields = sorted(support & set(self.dom.specs))
        base_facts = dict(base if base is not None else self.dom.default)
        need = len(goal)

        size = 1
        for f in fields:
            size *= max(1, len(self.dom.specs[f].candidates))
            if size > PRODUCT_CAP:
                break
        if size <= PRODUCT_CAP:
            return self._exhaustive(goal, fields, base_facts, need)
        return self._local(goal, fields, base_facts, need, seed, effort)

    def _exhaustive(self, goal: Goal, fields: list[str], base: dict[str, Any], need: int) -> SearchResult:
        pools = [self.dom.specs[f].candidates for f in fields]
        examined = 0
        for combo in itertools.product(*pools) if fields else [()]:
            examined += 1
            facts = dict(base)
            for f, v in zip(fields, combo):
                facts[f] = v
            if self._score(facts, goal) == need:
                return SearchResult(True, facts, "exhaustive", self._complete(fields), examined, fields)
        return SearchResult(False, None, "exhaustive", self._complete(fields), examined, fields)

    def _complete(self, fields: list[str]) -> bool:
        return all(self.dom.specs[f].exhaustive for f in fields)

    def verify_witness(self, facts: dict[str, Any], goal: Goal) -> tuple[bool, dict[str, Any]]:
        """Re-check an accepted witness the expensive way: full schema
        validation against the sealed branch, then every goal re-evaluated."""
        doc = self.dom.document(facts)
        if not self.dom.is_schema_valid(doc):
            return False, doc
        for probe, expected, _fields in goal:
            if probe(doc) != expected:
                return False, doc
        return True, doc

    def _local(self, goal: Goal, fields: list[str], base: dict[str, Any], need: int, seed: int,
               effort: int = 1) -> SearchResult:
        rng = random.Random(seed)
        fieldset = set(fields)
        examined = 0
        best_facts, best = None, -1
        for restart in range(LOCAL_RESTARTS * effort):
            facts = dict(base)
            if restart:
                for f in fields:
                    facts[f] = rng.choice(self.dom.specs[f].candidates)
            cur = self._score(facts, goal)
            examined += 1
            if cur == need:
                return SearchResult(True, facts, "bounded", False, examined, fields)
            for _ in range(LOCAL_STEPS):
                if not fields:
                    break
                # Goal-directed: mutate a field that some UNMET sub-goal reads.
                hot = [f for f in self._unmet_fields(facts, goal) if f in fieldset]
                f = rng.choice(hot) if hot else rng.choice(fields)
                cands = self.dom.specs[f].candidates
                original = facts[f]
                # Min-conflicts move: score every value of this field, then move
                # to a best-scoring one with random tie-breaking.  Ties matter --
                # these goals have wide plateaus (making the target row true
                # often turns a higher-precedence row true at the same time), and
                # a strict-improvement rule stalls on them permanently.
                scored: list[tuple[int, int]] = []
                for i, value in enumerate(cands):
                    facts[f] = value
                    s = self._score(facts, goal)
                    examined += 1
                    if s == need:
                        return SearchResult(True, dict(facts), "bounded", False, examined, fields)
                    scored.append((s, i))
                top = max(s for s, _ in scored)
                if top < cur:
                    facts[f] = original
                else:
                    facts[f] = cands[rng.choice([i for s, i in scored if s == top])]
                    cur = top
                if rng.random() < 0.10:  # random walk, to leave deep basins
                    g = rng.choice(fields)
                    facts[g] = rng.choice(self.dom.specs[g].candidates)
                    cur = self._score(facts, goal)
                    examined += 1
                if cur > best:
                    best, best_facts = cur, dict(facts)
        return SearchResult(False, None, "bounded", False, examined, fields)
