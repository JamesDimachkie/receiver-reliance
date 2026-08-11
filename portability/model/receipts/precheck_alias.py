"""Phase-2c alias-exclusivity precheck, deepened past the declared N=16 bound.

The check logic is a verbatim port of
``test_model.py::ModelStructureTests.test_bounded_reachable_states_have_one_label_per_physical_alias``
(declared domain: exhaustive reachable quotient states of finite model M for
expanded request prefixes up to 16 bytes, every raw token expansion group, LF
excluded because LF is a terminal action rather than a parser transition).  The
only changes are that ``bound`` became a parameter, the ``unittest`` assertions
became plain assertions, and a wall-clock / peak-working-set budget can abort a
deeper extension without touching the mandatory floor.

Property checked at every reachable state, for the one raw-expansion alias group
(``"a"`` -> {KEY_A, KEY_A_REPEAT}): exactly one of the two symbolic labels is
admissible, and every rejected label has no transition out of that state.

Authored additively for the post-F-MODEL-003 N=48 enumeration.  Run from the
repository root:
    python -B portability/model/receipts/precheck_alias.py 16 18 20 22 24
"""
from __future__ import annotations

import pathlib
import sys
import time
from collections import defaultdict

REPO = pathlib.Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from portability.model.domain import TOKENS
from portability.model.parser_model import (
    INITIAL_STATE,
    token_label_is_admissible,
    transition,
)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _wsmem import peak_working_set_bytes  # noqa: E402

TIME_BUDGET_SECONDS = 600.0
MEMORY_BUDGET_BYTES = 4 * 1024**3


class Aborted(Exception):
    def __init__(self, reason: str, layer: int) -> None:
        super().__init__(reason)
        self.reason = reason
        self.layer = layer


def run_bound(bound: int, deadline: float | None) -> dict[str, object]:
    by_raw: dict[bytes, list] = defaultdict(list)
    for item in TOKENS:
        if item.symbol != "LF":
            by_raw[item.raw].append(item)
    alias_groups = [items for items in by_raw.values() if len(items) > 1]
    assert len(alias_groups) == 1, alias_groups
    assert [item.label for item in alias_groups[0]] == ["KEY_A", "KEY_A_REPEAT"]

    started = time.monotonic()
    layers = [set() for _ in range(bound + 1)]
    layers[0].add(INITIAL_STATE)
    seen = set()
    checked_alias_contexts = 0
    rejected_edges_confirmed_none = 0
    reached_layer = 0
    aborted: str | None = None

    try:
        for length, states in enumerate(layers):
            reached_layer = length
            if deadline is not None and time.monotonic() > deadline:
                raise Aborted("wall-clock budget", length)
            peak = peak_working_set_bytes()
            if peak is not None and peak > MEMORY_BUDGET_BYTES:
                raise Aborted("peak-working-set budget", length)
            for state in states:
                seen.add(state)
                for items in by_raw.values():
                    raw = items[0].raw
                    if length + len(raw) > bound:
                        continue
                    admitted = [
                        item for item in items if token_label_is_admissible(state, item)
                    ]
                    if len(items) > 1:
                        checked_alias_contexts += 1
                        assert len(admitted) == 1, (
                            state,
                            [item.label for item in admitted],
                        )
                        for rejected in set(items) - set(admitted):
                            assert transition(state, rejected) is None, (
                                state,
                                rejected.label,
                            )
                            rejected_edges_confirmed_none += 1
                    for item in admitted:
                        nxt = transition(state, item)
                        if nxt is not None:
                            layers[nxt.byte_length].add(nxt)
    except Aborted as exc:
        aborted = f"{exc.reason} at layer {exc.layer}"

    elapsed = time.monotonic() - started
    result: dict[str, object] = {
        "bound": bound,
        "aborted": aborted,
        "reachable_states_seen": len(seen),
        "alias_contexts_checked": checked_alias_contexts,
        "rejected_alias_edges_confirmed_none": rejected_edges_confirmed_none,
        "layers_completed": reached_layer if aborted else bound,
        "elapsed_seconds": round(elapsed, 3),
        "peak_working_set_bytes": peak_working_set_bytes(),
    }
    if aborted is None:
        # Same two floor assertions the declared N=16 test makes.
        assert len(seen) > 1000, len(seen)
        assert checked_alias_contexts > 1000, checked_alias_contexts
    return result


def main(argv: list[str]) -> int:
    bounds = [int(item) for item in argv[1:]] or [16]
    overall_started = time.monotonic()
    worst = 0
    for bound in bounds:
        # The declared N=16 floor is mandatory and runs without a deadline;
        # every deeper extension shares one 10-minute budget.
        deadline = None if bound <= 16 else overall_started + TIME_BUDGET_SECONDS
        try:
            result = run_bound(bound, deadline)
        except AssertionError as exc:
            print(f"ALIAS_CHECK FAIL bound={bound} assertion={exc}")
            return 1
        verdict = "ABORTED" if result["aborted"] else "PASS"
        peak = result["peak_working_set_bytes"]
        peak_text = "unavailable" if peak is None else f"{peak / 1024**2:.1f}MiB"
        print(
            f"ALIAS_CHECK {verdict} bound={bound} "
            f"reachable_states={result['reachable_states_seen']} "
            f"alias_contexts_checked={result['alias_contexts_checked']} "
            f"rejected_edges_none={result['rejected_alias_edges_confirmed_none']} "
            f"layers_completed={result['layers_completed']} "
            f"elapsed_seconds={result['elapsed_seconds']} "
            f"peak_working_set={peak_text}"
            + (f" abort_reason=\"{result['aborted']}\"" if result["aborted"] else "")
        )
        if result["aborted"]:
            print(f"ALIAS_CHECK_DEEPEST_COMPLETE bound={worst}")
            return 0
        worst = bound
    print(f"ALIAS_CHECK_DEEPEST_COMPLETE bound={worst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
