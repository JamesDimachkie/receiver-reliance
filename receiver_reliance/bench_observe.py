"""Where the observability seam's measured claims come from.

Two halves, kept apart because they have different standing. The split is the
one `deployment/derive_admission_numbers.py` makes for the admission profile,
and for the same reason: a derived number and a measured number may not be read
the same way.

`--corpus` is DERIVED. It rebuilds the 136-request corpus the seam's rationale
is measured over, out of committed bytes and nothing else: the 112 semantic
fixtures of the 0.2 pack, the 12 of the 0.3 pack, the three published
`examples/`, and nine protocol-error requests declared literally below. Same
bytes in, same corpus out, on any host. `--check` fails on drift from the
composition this file declares, so the corpus cannot quietly stop being the one
the prose names.

`--measure` is MEASURED, on the caller's host, and generalizes to nothing. It
re-derives two numbers the README and the package docstring quote:

  * how many of the 136 requests a length proxy under-charges at p50, against
    `charge_ms` below -- the design-phase affine proxy, published here and
    nowhere else. Nothing in the decision path prices anything: the shipped
    length control is `deployment/admission.py`, which bounds bytes and states
    in `deployment/README.md` that it is not a cost control. The proxy exists
    to be wrong in public.
  * what the instrumented path costs per decision, and what that is as a
    fraction of a decision on the same host.

The overhead half is measured by isolating components rather than by timing
`decide_audited_observed` against `decide_audited`, and the reason is a
measurement fact rather than a preference: the added work is on the order of a
microsecond and a decision is on the order of three milliseconds, so run-to-run
noise on the decision swamps the difference by three orders of magnitude. A
paired A/B at that ratio reports noise. The instrumented path adds exactly
three `time.perf_counter_ns` reads, two `time.process_time_ns` reads, and one
record build plus one guarded observer call -- readable in
`decide_audited_observed` above it -- so each is timed on its own and summed.
The sum is what this reports, and it is an estimate of the seam's cost, not a
stopwatch on it. `--measure` prints the components so the sum can be checked
rather than believed.

    python -B receiver_reliance/bench_observe.py --corpus
    python -B receiver_reliance/bench_observe.py --corpus --check
    python -B receiver_reliance/bench_observe.py --measure

`--corpus --check` is deterministic and runs in the re-verification battery.
`--measure` measures on your host, so it stays hand-run, exactly as
`derive_admission_numbers.py --cost` does.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import platform
import statistics
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

PACKS = (
    ("SEM02", "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json"),
    ("SEM03", "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json"),
)

EXAMPLES = (
    "handoff-clean.json",
    "handoff-inconsistent.json",
    "handoff-unchecked-revocation.json",
)

#: One request per protocol-error code reachable without a payload too large to
#: commit. `ERR_LIMIT` is reached by nesting depth rather than by 16 MB of
#: bytes. Written as literal bytes rather than as encoded source text so the
#: file is readable in any editor and the BOM and lone-surrogate cases cannot be
#: normalized away by one.
PROTOCOL_CASES: tuple[tuple[str, bytes], ...] = (
    ("PROTO-bom", b"\xef\xbb\xbf{}\n"),
    ("PROTO-duplicate-key", b'{"a":1,"a":2}\n'),
    ("PROTO-empty", b""),
    ("PROTO-json-trailing", b"{} {}\n"),
    ("PROTO-limit-nesting", b"[" * 200 + b"]" * 200 + b"\n"),
    ("PROTO-nfc", b'{"a":"A\xcc\x8a"}\n'),
    ("PROTO-number", b'{"a":9007199254740993}\n'),
    ("PROTO-schema", b'{"decision_input":{},"obligation_id":"OBL-01"}\n'),
    ("PROTO-utf8", b'{"a":"\xff\xfe"}\n'),
)

#: What `--corpus --check` holds the rebuilt corpus to. These are counts of
#: committed things, so they move only when the committed things move, and a
#: move that is not also a documentation edit is the drift this arm is for.
DECLARED_CASES = 136
DECLARED_COMPOSITION = {
    "EXAMPLE": 3,
    "PROTO": 9,
    "SEM02": 112,
    "SEM03": 12,
}


def charge_ms(request_bytes: int) -> float:
    """The design-phase length proxy, fitted 2026-08-19 and frozen here.

    A per-request quota is useless against an engine whose cost varies by three
    orders of magnitude across contract-legal requests of similar length, so the
    natural repair is to denominate the quota in milliseconds and price a
    request by the one thing a receiver knows before it parses: how long it is.
    This is that pricing, affine in length, with a floor for the small-input
    case -- fitted above the measured shapes at both ends, so it was built to
    over-charge everything.

    It is a pure function of a length and it is not a control. Nothing imports
    it; the decision path prices nothing. It is published so that the count
    `--measure` reports is recomputable rather than asserted, and the two
    constants are design-phase values from one host: refitting them on another
    host would change the count, which is the same caveat every measured number
    in this repository carries.
    """
    return 0.10 + 1.20 * (request_bytes / 1024.0)


# --------------------------------------------------------------------------
# derived half


def corpus() -> list[tuple[str, bytes]]:
    """The 136 requests, sorted by case id, from committed bytes only."""
    cases: list[tuple[str, bytes]] = []
    for prefix, relative in PACKS:
        pack = json.loads((REPO / relative).read_text(encoding="utf-8"))
        for entry in pack["entries"]:
            cases.append(
                (
                    "%s:%s" % (prefix, entry["entry_id"]),
                    base64.b64decode(
                        entry["semantic_request_jcs_lf_base64"].encode("ascii"),
                        validate=True,
                    ),
                )
            )
    for name in EXAMPLES:
        cases.append(("EXAMPLE:%s" % name, (REPO / "examples" / name).read_bytes()))
    cases.extend(PROTOCOL_CASES)
    cases.sort(key=lambda item: item[0])
    identifiers = [case_id for case_id, _raw in cases]
    if len(set(identifiers)) != len(identifiers):
        raise SystemExit("corpus case ids are not unique")
    return cases


def composition(cases: list[tuple[str, bytes]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case_id, _raw in cases:
        # Fixture and example ids are `PREFIX:rest`; the protocol cases are
        # `PROTO-name`, which is the design-phase spelling and is kept so the
        # ids in this corpus are the ids the measurement was taken under.
        prefix = case_id.split(":", 1)[0].split("-", 1)[0]
        counts[prefix] = counts.get(prefix, 0) + 1
    return dict(sorted(counts.items()))


def corpus_sha256(cases: list[tuple[str, bytes]]) -> str:
    """A digest over the ids and the bytes, so a silent substitution is visible."""
    digest = hashlib.sha256()
    for case_id, raw in cases:
        digest.update(case_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(raw)
        digest.update(b"\0")
    return digest.hexdigest().upper()


def run_corpus(check: bool) -> int:
    cases = corpus()
    sizes = sorted(len(raw) for _id, raw in cases)
    print("corpus: cases=%d bytes_total=%d" % (len(cases), sum(sizes)))
    print(
        "  composition: %s"
        % json.dumps(composition(cases), separators=(",", ":"), sort_keys=True)
    )
    print(
        "  request bytes: min=%d p50=%d max=%d"
        % (sizes[0], sizes[len(sizes) // 2], sizes[-1])
    )
    print("  corpus_sha256=%s" % corpus_sha256(cases))
    if not check:
        return 0
    failures: list[str] = []
    if len(cases) != DECLARED_CASES:
        failures.append(
            "DECLARED_CASES=%d but the committed bytes rebuild %d"
            % (DECLARED_CASES, len(cases))
        )
    observed = composition(cases)
    if observed != DECLARED_COMPOSITION:
        failures.append(
            "DECLARED_COMPOSITION=%s but the committed bytes rebuild %s"
            % (
                json.dumps(DECLARED_COMPOSITION, separators=(",", ":"), sort_keys=True),
                json.dumps(observed, separators=(",", ":"), sort_keys=True),
            )
        )
    for line in failures:
        print("MISMATCH: %s" % line)
    print("CORPUS CHECK: failures=%d" % len(failures))
    return 1 if failures else 0


# --------------------------------------------------------------------------
# measured half


def _host() -> str:
    return "%s %s %s %s %s %s" % (
        platform.python_implementation(),
        platform.python_version(),
        platform.system(),
        platform.release(),
        platform.version(),
        platform.machine(),
    )


def _per_call_ns(call, iterations: int, repetitions: int = 7) -> float:
    """Best per-iteration time over whole loops -- the floor, not the average.

    The minimum is the estimator because everything a competing process, a
    frequency change or a cache miss adds is positive: the smallest observation
    is the one least contaminated by work that is not the subject.
    """
    best = None
    for _ in range(repetitions):
        start = time.perf_counter_ns()
        for _ in range(iterations):
            call()
        elapsed = (time.perf_counter_ns() - start) / iterations
        if best is None or elapsed < best:
            best = elapsed
    return float(best)


def measure_undercharge(cases: list[tuple[str, bytes]], rounds: int) -> dict:
    """Decide every request `rounds` times, interleaved, and price each at p50.

    Interleaved rather than warm-looped per case: a per-case inner loop measures
    a request whose data is already hot and reports a cost no receiver sees. The
    round order is the corpus order, so every case meets the same cache.
    """
    import receiver_reliance as rr

    samples: dict[str, list[int]] = {case_id: [] for case_id, _raw in cases}
    for _ in range(rounds):
        for case_id, raw in cases:
            start = time.perf_counter_ns()
            rr.decide_audited(raw)
            samples[case_id].append(time.perf_counter_ns() - start)

    rows = []
    for case_id, raw in cases:
        p50 = statistics.median(samples[case_id]) / 1e6
        charged = charge_ms(len(raw))
        rows.append((p50 / charged, p50, charged, len(raw), case_id))
    rows.sort(reverse=True)
    under = [row for row in rows if row[0] > 1.0]
    # The count above is steeply host-dependent, and this is why: most of the
    # corpus sits near the line, so a host a quarter faster or slower moves
    # tens of cases across it. Reporting the crowd with the count keeps the
    # count from being read as a property of the artifact.
    near = [row for row in rows if 0.75 <= row[0] <= 1.25]
    # The one number here that does NOT move with the host. Every ratio scales
    # with host speed, so the count, the worst ratio and the totals all do --
    # but their SPREAD does not: scaling every measured cost by the same factor
    # leaves max/min where it was. This is what "a length proxy mis-prices this
    # corpus" means as a claim a second host can hold this one to.
    fixtures = [row for row in rows if row[4].startswith(("SEM02:", "SEM03:"))]
    semantic = [row[1] for row in fixtures]
    return {
        "rows": rows,
        "under": under,
        "near": near,
        "total": len(rows),
        "worst_ratio": rows[0][0],
        "spread_fixtures": fixtures[0][0] / fixtures[-1][0],
        "spread_corpus": rows[0][0] / rows[-1][0],
        "corpus_p50_ms": statistics.median([row[1] for row in rows]),
        "semantic_p50_ms": statistics.median(semantic),
        "real_total_ms": sum(row[1] for row in rows),
        "charged_total_ms": sum(row[2] for row in rows),
    }


def measure_overhead(iterations: int) -> dict:
    """Time each component the instrumented path adds, then sum them."""
    import receiver_reliance as rr

    perf_counter_ns = time.perf_counter_ns
    process_time_ns = time.process_time_ns
    observation = rr.DecisionObservation(
        decision_class="VALID",
        exit_code=0,
        request_bytes=1234,
        response_bytes=None,
        ingest_ns=100,
        decide_ns=200,
        serialize_ns=None,
        wall_ns=300,
        cpu_ns=0,
    )
    fields = tuple(observation)

    def null_observer(_observation: object) -> None:
        return None

    def build_and_notify() -> None:
        try:
            null_observer(rr.DecisionObservation(*fields))
        except BaseException:
            return

    empty = _per_call_ns(lambda: None, iterations)
    wall_clock = _per_call_ns(lambda: perf_counter_ns(), iterations) - empty
    cpu_clock = _per_call_ns(lambda: process_time_ns(), iterations) - empty
    record = _per_call_ns(build_and_notify, iterations) - empty
    return {
        "loop_ns": empty,
        "perf_counter_ns": wall_clock,
        "process_time_ns": cpu_clock,
        "record_ns": record,
        "instrumented_ns": 3 * wall_clock + 2 * cpu_clock + record,
    }


def measure_passthrough(iterations: int, repetitions: int = 15) -> dict:
    """What `observer=None` costs: one identity test, and nothing else.

    Isolated against a same-shape two-argument function that forwards to the
    same stub and omits only the identity test, so the frame, the call and the
    return are common to both sides and the difference is the branch. The stub
    stands in for the engine because a three-millisecond decision on both sides
    would bury a twenty-nanosecond difference; `decide_audited` is rebound for
    the duration and restored in the `finally`.

    The two sides are timed alternately inside each repetition rather than as
    two separate best-of-N runs, because the subject is smaller than the drift
    between two runs -- an unpaired difference of two minima taken minutes
    apart is as likely to come out negative as positive, which is a way of
    reporting nothing. This returns the paired deltas' median and their range,
    and the caller prints the range: a range that contains zero is this
    method saying it cannot resolve the branch, and that is the honest result
    to publish rather than the midpoint of noise.
    """
    import receiver_reliance as rr

    request = (REPO / "examples" / "handoff-clean.json").read_bytes()
    envelope = rr.decide_audited(request)
    real = rr.decide_audited

    def stub(_request: object) -> dict:
        return envelope

    def same_shape(request: object, observer: object = None) -> dict:
        return stub(request)

    observed = rr.decide_audited_observed
    rr.decide_audited = stub
    try:
        for _ in range(5000):
            observed(request, None)
            same_shape(request, None)
        deltas: list[float] = []
        for _ in range(repetitions):
            without = _per_call_ns(lambda: same_shape(request, None), iterations, 1)
            with_test = _per_call_ns(lambda: observed(request, None), iterations, 1)
            deltas.append(with_test - without)
    finally:
        rr.decide_audited = real
    return {
        "median_ns": statistics.median(deltas),
        "low_ns": min(deltas),
        "high_ns": max(deltas),
        "repetitions": len(deltas),
        "resolved": min(deltas) > 0.0,
    }


def run_measure(rounds: int, iterations: int) -> int:
    cases = corpus()
    print("host: %s" % _host())
    print(
        "corpus: cases=%d corpus_sha256=%s (rebuilt from committed bytes; "
        "--corpus prints its composition)" % (len(cases), corpus_sha256(cases))
    )
    print()

    charge = measure_undercharge(cases, rounds)
    print(
        "=== length proxy vs measured cost, %d rounds interleaved over %d requests ==="
        % (rounds, charge["total"])
    )
    print("proxy: charge_ms(n) = 0.10 + 1.20 * (n / 1024)   [design-phase, frozen]")
    print(
        "UNDER-CHARGED at p50: %d of %d   worst ratio %.2fx"
        % (len(charge["under"]), charge["total"], charge["worst_ratio"])
    )
    print(
        "  read that count as host-conditional, not as a constant: %d of %d "
        "requests price within 0.75x-1.25x of the line, so a host a quarter "
        "faster or slower moves tens of them across it -- and so does the worst "
        "ratio, which scales with the host too."
        % (len(charge["near"]), charge["total"])
    )
    print(
        "MIS-PRICING SPREAD (host-invariant): %.2fx across the 124 semantic "
        "fixtures, %.2fx across all %d. Every ratio above scales with host "
        "speed; their spread does not, so this is the number a second host can "
        "hold this one to."
        % (charge["spread_fixtures"], charge["spread_corpus"], charge["total"])
    )
    print(
        "corpus totals: measured p50 %.1f ms vs charged %.1f ms "
        "-> the proxy's budget covers %.2fx the corpus"
        % (
            charge["real_total_ms"],
            charge["charged_total_ms"],
            charge["charged_total_ms"] / charge["real_total_ms"],
        )
    )
    print()
    print("%9s %9s %8s %7s  case" % ("ratio", "p50_ms", "charge", "bytes"))
    for ratio, p50, charged, size, case_id in charge["rows"][:8]:
        print("%9.3f %9.3f %8.3f %7d  %s" % (ratio, p50, charged, size, case_id[:52]))
    print()

    overhead = measure_overhead(iterations)
    passthrough = measure_passthrough(iterations)
    decision_ns = charge["semantic_p50_ms"] * 1e6
    print("=== seam overhead, components isolated over %d iterations ===" % iterations)
    print("  bare loop iteration        %8.1f ns  (subtracted from each below)" % overhead["loop_ns"])
    print("  time.perf_counter_ns()     %8.1f ns  x3 on the instrumented path" % overhead["perf_counter_ns"])
    print("  time.process_time_ns()     %8.1f ns  x2" % overhead["process_time_ns"])
    print("  record build + guarded call%8.1f ns  x1" % overhead["record_ns"])
    print("  INSTRUMENTED PATH          %8.1f ns  = 3 wall + 2 cpu + record" % overhead["instrumented_ns"])
    print(
        "  PASSTHROUGH (observer=None)%8.1f ns  = the identity test alone, "
        "paired median over %d repetitions, range %.1f to %.1f ns%s"
        % (
            passthrough["median_ns"],
            passthrough["repetitions"],
            passthrough["low_ns"],
            passthrough["high_ns"],
            "" if passthrough["resolved"] else "  -- RANGE CONTAINS ZERO",
        )
    )
    if not passthrough["resolved"]:
        print(
            "    unresolved: this method cannot separate one identity test from "
            "the call it forwards to. Report the branch, not a number."
        )
    print()
    print(
        "median decision on this host: %.3f ms over the 124 semantic fixtures "
        "(%.3f ms over all %d, protocol errors included)"
        % (charge["semantic_p50_ms"], charge["corpus_p50_ms"], charge["total"])
    )
    print(
        "instrumented path is %.4f%% of that decision"
        % (100.0 * overhead["instrumented_ns"] / decision_ns)
    )
    print()
    print(
        "One host, one run. The overhead figure is a sum of isolated "
        "components, not a stopwatch on the whole path: a paired A/B cannot "
        "resolve a microsecond against a millisecond decision, which is the "
        "same reason the passthrough range above is reported instead of a "
        "midpoint. The observer's own work is the host's and is in none of "
        "these numbers."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="derive the observability corpus, or measure the seam on this host"
    )
    parser.add_argument("--corpus", action="store_true", help="rebuild the 136-request corpus")
    parser.add_argument("--check", action="store_true", help="with --corpus: fail on drift")
    parser.add_argument("--measure", action="store_true", help="measure under-charge and overhead")
    parser.add_argument("--rounds", type=int, default=15, help="decisions per request (--measure)")
    parser.add_argument("--iterations", type=int, default=200_000, help="component loop length (--measure)")
    args = parser.parse_args(argv)
    if not args.corpus and not args.measure:
        parser.error("choose --corpus or --measure")
    status = 0
    if args.corpus:
        status |= run_corpus(args.check)
    if args.measure:
        status |= run_measure(args.rounds, args.iterations)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
