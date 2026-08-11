"""Phase-2d retained-versus-streaming equivalence at deeper bounds.

The comparison mechanism is the one already sanctioned in the repository:
``portability/model/reference_checker.py::explore_parser_retained`` (a
separately structured, never-released reachability store) diffed field-for-field
against the production streaming path
``portability/model/parser_model.py::explore_parser``.
``test_model.py::ModelStructureTests.test_streaming_explorer_matches_retained_reference``
already runs that diff at declared bounds N in {0, 1, 2, 4, 7, 10, 13, 16}.
This driver only extends the same diff to deeper bounds; it does not define a
new notion of equivalence.

Every field of ``ParseExploration`` is compared via ``dataclasses.asdict``,
which covers states, transitions, terminal_transitions,
symbolic_terminal_traces, excluded_edges, excluded_trace_prefixes, the
per-terminal-class table, representative_hex, and quotient_material_sha256.

Authored additively for the post-F-MODEL-003 N=48 enumeration.  Run from the
repository root:
    python -B portability/model/receipts/precheck_retained.py 18 19 20 ... 28
"""
from __future__ import annotations

import pathlib
import sys
import time
from dataclasses import asdict

REPO = pathlib.Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from portability.model.parser_model import explore_parser
from portability.model.reference_checker import explore_parser_retained

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _wsmem import peak_working_set_bytes  # noqa: E402


def main(argv: list[str]) -> int:
    bounds = [int(item) for item in argv[1:]] or list(range(18, 29))
    failures = 0
    for bound in bounds:
        t0 = time.monotonic()
        streaming = asdict(explore_parser(bound))
        t1 = time.monotonic()
        retained = asdict(explore_parser_retained(bound))
        t2 = time.monotonic()
        identical = streaming == retained
        peak = peak_working_set_bytes()
        peak_text = "unavailable" if peak is None else f"{peak / 1024**2:.1f}MiB"
        print(
            f"RETAINED_VS_STREAMING {'IDENTICAL' if identical else 'DIVERGENT'} "
            f"N={bound} states={streaming['states']} "
            f"transitions={streaming['transitions']} "
            f"terminal_transitions={streaming['terminal_transitions']} "
            f"symbolic_terminal_traces={streaming['symbolic_terminal_traces']} "
            f"excluded_edges={streaming['excluded_edges']} "
            f"excluded_trace_prefixes={streaming['excluded_trace_prefixes']} "
            f"quotient_material_sha256={streaming['quotient_material_sha256']} "
            f"streaming_seconds={t1 - t0:.2f} retained_seconds={t2 - t1:.2f} "
            f"peak_working_set={peak_text}",
            flush=True,
        )
        if not identical:
            failures += 1
            for key in sorted(set(streaming) | set(retained)):
                if streaming.get(key) != retained.get(key):
                    print(
                        f"  FIELD_DIVERGENCE N={bound} field={key} "
                        f"streaming={streaming.get(key)!r} retained={retained.get(key)!r}",
                        flush=True,
                    )
    print(f"RETAINED_VS_STREAMING_SUMMARY bounds={bounds} divergences={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
