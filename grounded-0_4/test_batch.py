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
import hashlib
import importlib.util
import io
import json
import pathlib
import random
import statistics
import subprocess
import sys
import time
import tracemalloc
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


def make_line(total_length: int, pattern: bytes, terminated: bool) -> bytes:
    body_length = total_length - (1 if terminated else 0)
    if body_length < 0 or not pattern or b"\n" in pattern:
        raise ValueError("invalid deterministic line recipe")
    body = (pattern * (body_length // len(pattern) + 1))[:body_length]
    return body + (b"\n" if terminated else b"")


class RepeatingLineSource:
    """Generate one arbitrarily long physical line without retaining it."""

    def __init__(self, content_length: int, terminated: bool) -> None:
        self.remaining = content_length
        self.newline_pending = terminated
        self.max_requested = 0
        self.calls = 0

    def readline(self, size: int = -1) -> bytes:
        if size < 0:
            raise AssertionError("batch reader attempted an unbounded readline")
        self.calls += 1
        self.max_requested = max(self.max_requested, size)
        if self.remaining:
            count = min(size, self.remaining)
            self.remaining -= count
            chunk = b"x" * count
            if self.remaining == 0 and self.newline_pending and count < size:
                self.newline_pending = False
                chunk += b"\n"
            return chunk
        if self.newline_pending:
            self.newline_pending = False
            return b"\n"
        return b""


def repeated_line_digest(content_length: int, terminated: bool) -> str:
    digest = hashlib.sha256()
    block = b"x" * rr_batch._READ_CHUNK_BYTES
    remaining = content_length
    while remaining:
        count = min(len(block), remaining)
        digest.update(block[:count])
        remaining -= count
    if terminated:
        digest.update(b"\n")
    return digest.hexdigest().upper()


def transport_regression_gate() -> tuple[int, int]:
    """Pin the two RO1 transport findings and broader boundary properties."""

    class ShortWriteSink:
        def __init__(self) -> None:
            self.data = bytearray()
            self.calls = 0
            self.flush_offsets: list[int] = []
            self.plan = (1, 2, 3, 5, 8, 13, 21, 34)

        def write(self, data: bytes | memoryview) -> int:
            count = min(len(data), self.plan[self.calls % len(self.plan)])
            self.calls += 1
            self.data.extend(data[:count])
            return count

        def flush(self) -> None:
            self.flush_offsets.append(len(self.data))

    short_requests = [b"\n", b"{}\r\n"]
    short_expected = [audited_bytes(raw) for raw in short_requests]
    short_sink = ShortWriteSink()
    short_exit = rr_batch.serve(io.BytesIO(b"".join(short_requests)), short_sink)
    check("ro1:short-write:exit-zero", short_exit == 0, str(short_exit))
    check("ro1:short-write:multiple-calls", short_sink.calls > len(short_requests), str(short_sink.calls))
    check("ro1:short-write:full-bytes", bytes(short_sink.data) == b"".join(short_expected))
    check(
        "ro1:short-write:flush-after-each-complete-response",
        short_sink.flush_offsets == [len(short_expected[0]), sum(map(len, short_expected))],
        repr(short_sink.flush_offsets),
    )
    check(
        "ro1:short-write:full-lf-framing",
        bytes(short_sink.data).splitlines(keepends=True) == short_expected,
    )

    class NoProgressSink:
        def __init__(self, result: int | None) -> None:
            self.result = result
            self.flushes = 0

        def write(self, _data: bytes | memoryview) -> int | None:
            return self.result

        def flush(self) -> None:
            self.flushes += 1

    for label, result in (("zero", 0), ("none", None)):
        sink = NoProgressSink(result)
        try:
            rr_batch.serve(io.BytesIO(b"\n"), sink)
        except BlockingIOError as error:
            check(f"ro1:{label}-write:raises", "made no progress" in str(error), str(error))
        except Exception as error:  # noqa: BLE001 - wrong exception is a regression
            check(f"ro1:{label}-write:raises", False, repr(error))
        else:
            check(f"ro1:{label}-write:raises", False, "no exception")
        check(f"ro1:{label}-write:no-flush", sink.flushes == 0, str(sink.flushes))

    class FailingSink:
        def __init__(self) -> None:
            self.data = bytearray()
            self.calls = 0
            self.flushes = 0

        def write(self, data: bytes | memoryview) -> int:
            self.calls += 1
            if self.calls == 1:
                self.data.extend(data[:17])
                return 17
            raise OSError("deliberate-sink-failure")

        def flush(self) -> None:
            self.flushes += 1

    failing_sink = FailingSink()
    failure_expected = audited_bytes(b"\n")
    try:
        rr_batch.serve(io.BytesIO(b"\n"), failing_sink)
    except OSError as error:
        check("ro1:raised-write:propagates", str(error) == "deliberate-sink-failure", str(error))
    except Exception as error:  # noqa: BLE001 - wrong exception is a regression
        check("ro1:raised-write:propagates", False, repr(error))
    else:
        check("ro1:raised-write:propagates", False, "no exception")
    check("ro1:raised-write:prefix-honored", bytes(failing_sink.data) == failure_expected[:17])
    check("ro1:raised-write:no-flush", failing_sink.flushes == 0, str(failing_sink.flushes))

    class InvalidCountSink(NoProgressSink):
        def write(self, data: bytes | memoryview) -> int:
            return len(data) + 1

    invalid_sink = InvalidCountSink(1)
    try:
        rr_batch.serve(io.BytesIO(b"\n"), invalid_sink)
    except OSError as error:
        check("ro1:overcount-write:raises", "invalid byte count" in str(error), str(error))
    except Exception as error:  # noqa: BLE001 - wrong exception is a regression
        check("ro1:overcount-write:raises", False, repr(error))
    else:
        check("ro1:overcount-write:raises", False, "no exception")
    check("ro1:overcount-write:no-flush", invalid_sink.flushes == 0, str(invalid_sink.flushes))

    maximum = rr_api.b1.MAX_INPUT_BYTES
    seed = 0x524F32
    rng = random.Random(seed)
    deltas = [1, 2, 3, 17, 255, 256, 257, rr_batch._READ_CHUNK_BYTES - 1,
              rr_batch._READ_CHUNK_BYTES, rr_batch._READ_CHUNK_BYTES + 1,
              1_048_583, 2_097_169]
    deltas.extend(rng.randrange(1, 1_500_000) for _ in range(8))
    patterns = (b"x", b"\xff\x00{}", b"\r ", b'{"format_version":"B1-WRAPPER-SEMANTIC-REQUEST-0.2"}')
    overlimit_cases = 0
    for index, delta in enumerate(deltas):
        terminated = index % 2 == 0
        raw = make_line(maximum + delta, patterns[index % len(patterns)], terminated)
        expected = audited_bytes(raw)
        sink = io.BytesIO()
        actual_exit = rr_batch.serve(io.BytesIO(raw), sink)
        actual = sink.getvalue()
        check(f"ro1:overlimit:{index}:length", len(raw) == maximum + delta, str(len(raw)))
        check(f"ro1:overlimit:{index}:exit-zero", actual_exit == 0, str(actual_exit))
        check(f"ro1:overlimit:{index}:one-shot-parity", actual == expected)
        check(f"ro1:overlimit:{index}:lf-framing", actual.endswith(b"\n") and b"\r" not in actual)
        parsed = json.loads(actual)
        check(
            f"ro1:overlimit:{index}:full-raw-digest",
            parsed["audit"]["request_raw_sha256"] == hashlib.sha256(raw).hexdigest().upper(),
        )
        overlimit_cases += 1

    # Pin both sides of the exact boundary.  The in-bound cases must take the
    # ordinary audited path even though they are as large as the frozen cap.
    for index, terminated in enumerate((False, True)):
        raw = make_line(maximum, b"z", terminated)
        sink = io.BytesIO()
        actual_exit = rr_batch.serve(io.BytesIO(raw), sink)
        check(f"ro1:boundary:{index}:exit-zero", actual_exit == 0, str(actual_exit))
        check(f"ro1:boundary:{index}:one-shot-parity", sink.getvalue() == audited_bytes(raw))

    # An oversized terminated line must be drained as exactly one record so
    # subsequent ordinary, empty, and oversized records remain aligned.
    over_a = make_line(maximum + 333, b"A", True)
    ordinary = b"{}\n"
    over_b = make_line(maximum + 777, b"\xffB", True)
    alignment_stream = over_a + ordinary + over_b + b"\n"
    alignment_expected = b"".join(audited_bytes(raw) for raw in (over_a, ordinary, over_b, b"\n"))
    alignment_sink = io.BytesIO()
    alignment_exit = rr_batch.serve(io.BytesIO(alignment_stream), alignment_sink)
    check("ro1:alignment:exit-zero", alignment_exit == 0, str(alignment_exit))
    check("ro1:alignment:four-responses", len(alignment_sink.getvalue().splitlines()) == 4)
    check("ro1:alignment:one-shot-parity", alignment_sink.getvalue() == alignment_expected)

    # Peak retained memory is bounded by the frozen cap even when physical
    # line length scales from roughly 2x to 8x that cap.  The source generates
    # bytes incrementally, so the measurement cannot hide a prebuilt line.
    memory_peaks: list[int] = []
    peak_limit = maximum + 8 * rr_batch._READ_CHUNK_BYTES
    for multiplier, extra, terminated in ((2, 17, False), (8, 31, True)):
        content_length = maximum * multiplier + extra
        expected_digest = repeated_line_digest(content_length, terminated)
        source = RepeatingLineSource(content_length, terminated)
        sink = io.BytesIO()
        tracemalloc.start()
        memory_exit = rr_batch.serve(source, sink)
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        memory_peaks.append(peak)
        parsed = json.loads(sink.getvalue())
        check(f"ro1:memory:{multiplier}x:exit-zero", memory_exit == 0, str(memory_exit))
        check(f"ro1:memory:{multiplier}x:bounded-read", source.max_requested == rr_batch._READ_CHUNK_BYTES)
        check(f"ro1:memory:{multiplier}x:raw-digest", parsed["audit"]["request_raw_sha256"] == expected_digest)
        check(f"ro1:memory:{multiplier}x:peak-bounded", peak <= peak_limit, f"peak={peak} limit={peak_limit}")
        overlimit_cases += 1
    check(
        "ro1:memory:not-line-scaled",
        abs(memory_peaks[1] - memory_peaks[0]) <= 2 * rr_batch._READ_CHUNK_BYTES,
        repr(memory_peaks),
    )
    print(
        f"batch transport: seed=0x{seed:X} overlimit_cases={overlimit_cases} "
        f"peak_memory_bytes={max(memory_peaks)} peaks={','.join(map(str, memory_peaks))}"
    )
    return overlimit_cases, max(memory_peaks)


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
    overlimit_count, peak_memory = transport_regression_gate()
    if args.perf:
        performance_gate(semantic_raw)
    print(
        f"batch regression: fixtures={fixture_count} semantic={semantic_count} "
        f"fuzz={fuzz_count} fuzz_fast={fuzz_fast} fuzz_special={fuzz_special} "
        f"overlimit={overlimit_count} peak_memory_bytes={peak_memory} "
        f"checks={checks} failures={failures} perf={'on' if args.perf else 'off'}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
