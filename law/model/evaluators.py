"""Executable operator semantics, taken from the shipped engines.

The frozen predicate vocabulary is specified in prose inside the contract
(``predicate_language.atomic_operators``).  Re-implementing 38 operators from
that prose would put a hand-written interpretation between the sealed rows and
every result in this report — exactly the "fake proof" failure mode.

Instead the two *independent* shipped implementations are imported as the
executable definition of the vocabulary and cross-checked against each other on
every single evaluation.  A disagreement is a hard error of the checker, not a
finding, and aborts the run.

See model/ASSUMPTIONS.md A1 for what this does and does not license.
"""

from __future__ import annotations

from typing import Any

from . import sources


class EvaluatorDivergence(RuntimeError):
    pass


class Evaluators:
    def __init__(self) -> None:
        self.primary = sources.load_module("evaluator_primary")
        self.second = sources.load_module("evaluator_second")
        self.closure_engine = sources.load_module("closure_engine_0_4")
        self.evaluations = 0
        self.divergences: list[dict[str, Any]] = []
        self.errors_primary = 0

    def eval_predicate(self, node: dict[str, Any], document: dict[str, Any]) -> bool | None:
        """Evaluate one predicate.  ``None`` means "evaluator error".

        The contract permits later class predicates to be non-total on inputs an
        earlier class already resolved (BASE64_SHA256_NE is the documented
        case), so an evaluator error is a legitimate outcome that the caller
        must handle, not a checker failure.
        """
        self.evaluations += 1
        a = self._one(self.primary.eval_predicate, node, document)
        b = self._one(self.second.evaluate_predicate, node, document)
        if a != b:
            record = {"node": node, "document": document, "primary": a, "second": b}
            self.divergences.append(record)
            raise EvaluatorDivergence(f"shipped evaluators disagree: {a!r} vs {b!r} on {node!r}")
        if a is None:
            self.errors_primary += 1
        return a

    @staticmethod
    def _one(fn, node, document) -> bool | None:
        try:
            return bool(fn(node, document))
        except Exception:
            return None

    # -- the precedence chain ---------------------------------------------
    def classify(self, law, operation, document: dict[str, Any]) -> tuple[str, dict[str, bool | None]]:
        """First match in frozen precedence order; VALID when none fires.

        Predicates after the first match are NOT evaluated, per the contract's
        own note that later rows may be partial on already-resolved inputs.
        """
        fired: dict[str, bool | None] = {}
        for cls in law.defect_precedence:
            value = self.eval_predicate(operation.class_predicates[cls], document)
            fired[cls] = value
            if value is True:
                return cls, fired
        return "VALID", fired

    # -- closure layer -----------------------------------------------------
    def eval_closure(self, predicate: dict[str, Any], document: dict[str, Any]) -> bool | None:
        """Closure predicates use the frozen vocabulary plus PROJECTION_NE and
        DERIVED_DIFF_NE, whose semantics live in ``grounded-0_4/rr_api.py``."""
        self.evaluations += 1
        fn = getattr(self.closure_engine, "_eval_closure", None)
        if fn is None:  # pragma: no cover - guards against an rr_api rename
            raise RuntimeError("rr_api exports no closure predicate evaluator")
        try:
            return bool(fn(predicate, document))
        except Exception:
            return None
