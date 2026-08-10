"""Regression and throughput gate for the persistent audited NDJSON path.

The functional suite covers every exact request/response fixture in both
sealed generations (semantic entries and both wrapper arms), malformed-line
continuation, mixed ordering and repeats, LF/stderr discipline, clean EOF,
and equality with isolated batch processes.  ``--perf`` additionally runs a
paired three-sample amortized-throughput gate over the same 124 semantic
requests used by ``perf/PROFILE_BASELINE.md``.
"""
from __future__ import annotations

import argparse
import base64
import importlib.util
import io
import json
import pathlib
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
RUNNER = HERE / "rr_batch.py"
sys.path.insert(0, str(HERE))

import rr_api  # noqa: E402
import rr_batch  # noqa: E402


@dataclass(frozen=True)
class Fixture:
    fixture_id: str
    raw: bytes
    sealed_expected: bytes
    family: str


failures = 0
checks = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global checks, failures
    checks += 1
    if not ok:
        failures += 1
        print(f"FAIL {name} {detail}")


def load_json(relative: str) -> dict:
    with open(REPO / relative, encoding="utf-8") as handle:
        return json.load(handle)


def load_fixtures() -> list[Fixture]:
    fixtures: list[Fixture] = []
    semantic_packs = (
        (
            "baseline",
            "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json",
        ),
        (
            "supplemental",
            "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
        ),
    )
    for generation, relative in semantic_packs:
        for entry in load_json(relative)["entries"]:
            fixtures.append(
                Fixture(
                    entry["entry_id"],
                    base64.b64decode(entry["semantic_request_jcs_lf_base64"]),
                    base64.b64decode(entry["expected_response_jcs_lf_base64"]),
                    f"{generation}-semantic",
                )
            )

    wrapper_packs = (
        (
            "baseline",
            "baseline-run/fixtures/B1_WRAPPER_PARITY_FIXTURE_PACK_0_2.json",
        ),
        (
            "supplemental",
            "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_WRAPPER_PARITY_FIXTURE_PACK_0_3.json",
        ),
    )
    for generation, relative in wrapper_packs:
        for pair in load_json(relative)["pairs"]:
            for arm_name in ("b1_arm", "b1_attention_arm"):
                arm = pair[arm_name]
                fixtures.append(
                    Fixture(
                        f"{pair['pair_id']}:{arm_name}",
                        base64.b64decode(arm["request_jcs_lf_base64"]),
                        base64.b64decode(arm["response_jcs_lf_base64"]),
                        f"{generation}-wrapper",
                    )
                )
    return fixtures


def audited_bytes(raw: bytes) -> bytes:
    return rr_api.b1.jcs_bytes(rr_api.decide_audited(raw)) + b"\n"


def run_batch(raw_requests: list[bytes], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-I", "-B", str(RUNNER)],
        input=b"".join(raw_requests),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def physical_lines(raw: bytes) -> list[bytes]:
    """Split bytes exactly as ``BinaryIO.readline`` will split them."""
    parts = raw.split(b"\n")
    lines = [part + b"\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def fuzz_parity_gate() -> tuple[int, int, int]:
    """Differential the default seeded fuzz corpus against one-shot audit.

    A byte-fuzz case containing internal LF is multiple requests under the
    NDJSON contract, and an empty byte string is clean EOF.  The expected
    response is therefore computed independently for every physical line,
    not by pretending an unrepresentable one-shot byte string is one record.
    """
    fuzz_path = REPO / "fuzz" / "fuzz.py"
    spec = importlib.util.spec_from_file_location("rr_batch_fuzz_harness", fuzz_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load fuzz harness: {fuzz_path}")
    fuzz = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = fuzz
    spec.loader.exec_module(fuzz)
    cases = fuzz.generate_cases(fuzz.DEFAULT_SEED, fuzz.DEFAULT_CASES, list(fuzz.STRATEGIES))

    fast = [case for case in cases if len(physical_lines(case.raw)) == 1 and case.raw.endswith(b"\n")]
    special = [case for case in cases if case not in fast]
    check("fuzz:default-case-count", len(cases) == 256, str(len(cases)))
    check("fuzz:fast-line-count", len(fast) == 223, str(len(fast)))
    check("fuzz:special-framing-count", len(special) == 33, str(len(special)))

    fast_result = run_batch([case.raw for case in fast])
    fast_expected = b"".join(audited_bytes(case.raw) for case in fast)
    check("fuzz:fast:exit-zero", fast_result.returncode == 0, str(fast_result.returncode))
    check("fuzz:fast:stderr-empty", fast_result.stderr == b"", repr(fast_result.stderr))
    check("fuzz:fast:byte-parity", fast_result.stdout == fast_expected)

    for case in special:
        expected = b"".join(audited_bytes(line) for line in physical_lines(case.raw))
        result = run_batch([case.raw])
        check(f"fuzz:{case.case_id}:exit-zero", result.returncode == 0, str(result.returncode))
        check(f"fuzz:{case.case_id}:stderr-empty", result.stderr == b"", repr(result.stderr))
        check(f"fuzz:{case.case_id}:physical-line-parity", result.stdout == expected)
    return len(cases), len(fast), len(special)


def functional_gate(fixtures: list[Fixture]) -> tuple[int, int, list[bytes]]:
    expected: list[bytes] = []
    family_counts: dict[str, int] = {}
    for fixture in fixtures:
        family_counts[fixture.family] = family_counts.get(fixture.family, 0) + 1
        response, _exit_code = rr_api.decide(fixture.raw)
        sealed = rr_api.b1.jcs_bytes(response) + b"\n"
        check(f"sealed-fixture:{fixture.fixture_id}", sealed == fixture.sealed_expected)
        one_shot = audited_bytes(fixture.raw)
        check(
            f"audited-embeds-fixture:{fixture.fixture_id}",
            rr_api.b1.jcs_bytes(rr_api.decide_audited(fixture.raw)["sealed_response"])
            + b"\n"
            == fixture.sealed_expected,
        )
        expected.append(one_shot)

    check(
        "fixture-counts",
        family_counts
        == {
            "baseline-semantic": 112,
            "baseline-wrapper": 224,
            "supplemental-semantic": 12,
            "supplemental-wrapper": 24,
        },
        repr(family_counts),
    )

    all_result = run_batch([fixture.raw for fixture in fixtures])
    lines = all_result.stdout.splitlines(keepends=True)
    check("all-fixtures:exit-zero", all_result.returncode == 0, str(all_result.returncode))
    check("all-fixtures:stderr-empty", all_result.stderr == b"", repr(all_result.stderr[:500]))
    check("all-fixtures:one-output-per-request", len(lines) == len(fixtures), str(len(lines)))
    for index, fixture in enumerate(fixtures):
        actual = lines[index] if index < len(lines) else b""
        check(f"batch-parity:{fixture.fixture_id}", actual == expected[index])
        check(f"batch-lf:{fixture.fixture_id}", actual.endswith(b"\n") and b"\r" not in actual)
        if actual.endswith(b"\n"):
            try:
                parsed = json.loads(actual[:-1].decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                check(f"batch-json:{fixture.fixture_id}", False, repr(error))
            else:
                check(
                    f"batch-jcs:{fixture.fixture_id}",
                    rr_api.b1.jcs_bytes(parsed) == actual[:-1],
                )

    malformed = [
        b"\n",
        b"{]\n",
        b"{}\r\n",
        b"\xef\xbb\xbf{}\n",
        b"\xff\n",
        b'{"a":1,"a":2}\n',
        b"null\n",
    ]
    malformed_expected = [audited_bytes(raw) for raw in malformed]
    malformed_result = run_batch(malformed)
    malformed_lines = malformed_result.stdout.splitlines(keepends=True)
    check("malformed:exit-zero", malformed_result.returncode == 0, str(malformed_result.returncode))
    check("malformed:stderr-empty", malformed_result.stderr == b"", repr(malformed_result.stderr))
    check("malformed:one-output-each", len(malformed_lines) == len(malformed), str(len(malformed_lines)))
    for index, expected_line in enumerate(malformed_expected):
        actual = malformed_lines[index] if index < len(malformed_lines) else b""
        check(f"malformed:{index}:one-shot-parity", actual == expected_line)
        if actual:
            parsed = json.loads(actual)
            direct = json.loads(expected_line)
            check(f"malformed:{index}:protocol-error", parsed["audited_behavior_class"] == "PROTOCOL_ERROR")
            check(f"malformed:{index}:exit-code-parity", parsed["exit_code"] == direct["exit_code"])

    # An unterminated final line is still one request and preserves the
    # frozen LF-framing error.  It must be isolated because appending another
    # request would, correctly, make both byte sequences one physical line.
    truncated = b"{}"
    truncated_result = run_batch([truncated])
    check("truncated:exit-zero", truncated_result.returncode == 0, str(truncated_result.returncode))
    check("truncated:stderr-empty", truncated_result.stderr == b"", repr(truncated_result.stderr))
    check("truncated:one-shot-parity", truncated_result.stdout == audited_bytes(truncated))

    # Compare a deliberately interleaved stream with separate fresh processes.
    # Invalid requests between repeated valid requests make state leakage and
    # fail-stop behavior observable.
    semantic = [fixture for fixture in fixtures if fixture.family.endswith("semantic")]
    mixed = [semantic[-1].raw, malformed[2], semantic[0].raw, semantic[-1].raw, malformed[0], semantic[0].raw]
    isolated = [run_batch([raw]) for raw in mixed]
    for index, result in enumerate(isolated):
        check(f"isolated:{index}:exit-zero", result.returncode == 0, str(result.returncode))
        check(f"isolated:{index}:stderr-empty", result.stderr == b"", repr(result.stderr))
    mixed_result = run_batch(mixed)
    check("mixed:exit-zero", mixed_result.returncode == 0, str(mixed_result.returncode))
    check("mixed:stderr-empty", mixed_result.stderr == b"", repr(mixed_result.stderr))
    check("mixed:isolated-byte-parity", mixed_result.stdout == b"".join(r.stdout for r in isolated))
    mixed_lines = mixed_result.stdout.splitlines(keepends=True)
    if len(mixed_lines) == len(mixed):
        check("mixed:first-repeat-stateless", mixed_lines[0] == mixed_lines[3])
        check("mixed:second-repeat-stateless", mixed_lines[2] == mixed_lines[5])
    else:
        check("mixed:response-count", False, str(len(mixed_lines)))

    empty_result = run_batch([])
    check("clean-eof:exit-zero", empty_result.returncode == 0, str(empty_result.returncode))
    check("clean-eof:stdout-empty", empty_result.stdout == b"", repr(empty_result.stdout))
    check("clean-eof:stderr-empty", empty_result.stderr == b"", repr(empty_result.stderr))

    class FlushCountingSink(io.BytesIO):
        def __init__(self) -> None:
            super().__init__()
            self.flush_count = 0

        def flush(self) -> None:
            self.flush_count += 1
            super().flush()

    flush_input = [malformed[0], semantic[0].raw]
    flush_sink = FlushCountingSink()
    serve_exit = rr_batch.serve(io.BytesIO(b"".join(flush_input)), flush_sink)
    check("interactive-flush:exit-zero", serve_exit == 0, str(serve_exit))
    check("interactive-flush:per-response", flush_sink.flush_count == len(flush_input), str(flush_sink.flush_count))
    check(
        "interactive-flush:byte-parity",
        flush_sink.getvalue() == b"".join(audited_bytes(raw) for raw in flush_input),
    )

    semantic_raw = [fixture.raw for fixture in fixtures if fixture.family.endswith("semantic")]
    return len(fixtures), len(semantic_raw), semantic_raw


def performance_gate(semantic_raw: list[bytes]) -> tuple[float, float, float]:
    # One untimed run warms the authority cache in the parent and file caches
    # used by fresh children.  Each reported sample remains a new persistent
    # process, so startup is included and amortized over exactly 124 requests.
    for raw in semantic_raw:
        rr_api.decide_audited(raw)
    warm = run_batch(semantic_raw)
    check("perf:warm-parity", warm.stdout == b"".join(audited_bytes(raw) for raw in semantic_raw))

    direct_samples: list[float] = []
    batch_samples: list[float] = []
    expected = warm.stdout
    for repetition in range(3):
        if repetition % 2 == 0:
            start = time.perf_counter_ns()
            for raw in semantic_raw:
                rr_api.decide_audited(raw)
            direct_elapsed = time.perf_counter_ns() - start
            start = time.perf_counter_ns()
            result = run_batch(semantic_raw)
            batch_elapsed = time.perf_counter_ns() - start
        else:
            start = time.perf_counter_ns()
            result = run_batch(semantic_raw)
            batch_elapsed = time.perf_counter_ns() - start
            start = time.perf_counter_ns()
            for raw in semantic_raw:
                rr_api.decide_audited(raw)
            direct_elapsed = time.perf_counter_ns() - start
        check(f"perf:{repetition}:batch-exit", result.returncode == 0, str(result.returncode))
        check(f"perf:{repetition}:batch-stderr", result.stderr == b"", repr(result.stderr))
        check(f"perf:{repetition}:batch-parity", result.stdout == expected)
        direct_samples.append(direct_elapsed / len(semantic_raw) / 1_000_000)
        batch_samples.append(batch_elapsed / len(semantic_raw) / 1_000_000)

    direct_median = statistics.median(direct_samples)
    batch_median = statistics.median(batch_samples)
    ratio = batch_median / direct_median
    check("perf:amortized-at-most-3x-in-process", ratio <= 3.0, f"ratio={ratio:.6f}")
    print(
        "batch perf: "
        f"requests={len(semantic_raw)} repetitions=3 "
        f"in_process_ms={','.join(f'{x:.6f}' for x in direct_samples)} "
        f"batch_ms={','.join(f'{x:.6f}' for x in batch_samples)} "
        f"median_ratio={ratio:.6f}"
    )
    return direct_median, batch_median, ratio


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--perf", action="store_true", help="run the paired <=3x throughput gate")
    args = parser.parse_args()

    fixtures = load_fixtures()
    fixture_count, semantic_count, semantic_raw = functional_gate(fixtures)
    fuzz_count, fuzz_fast, fuzz_special = fuzz_parity_gate()
    if args.perf:
        performance_gate(semantic_raw)
    print(
        f"batch regression: fixtures={fixture_count} semantic={semantic_count} "
        f"fuzz={fuzz_count} fuzz_fast={fuzz_fast} fuzz_special={fuzz_special} "
        f"checks={checks} failures={failures} perf={'on' if args.perf else 'off'}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
