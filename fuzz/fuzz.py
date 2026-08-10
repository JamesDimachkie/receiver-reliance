#!/usr/bin/env python3
"""Deterministic grammar-aware and byte-mutational fuzzer for pcb_runner.

The default seed is intentionally recorded in source.  Every input is sent
through two fresh one-shot subprocesses; this harness never calls the runner's
private in-process entry point.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable


DEFAULT_SEED = 0x0B10F042
DEFAULT_CASES = 256
DEFAULT_BUDGET_SECONDS = 300.0
CI_CASE_TIMEOUT_SECONDS = 3.0
CI_BUDGET_SECONDS = 45.0
MAX_CASES = 100_000
CORPUS_FORMAT = "RR-FUZZ-CORPUS-0.1"
MAX_CORPUS_BYTES = 64 * 1024 * 1024

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
IMPL = REPO / "baseline-run" / "implementation-output-0.3"
RUNNER = IMPL / "pcb_runner.py"
if str(IMPL) not in sys.path:
    sys.path.insert(0, str(IMPL))

import b1_capabilities as b1  # noqa: E402


@dataclass(frozen=True)
class SeedInput:
    source: str
    raw: bytes


@dataclass(frozen=True)
class FuzzCase:
    case_id: str
    strategy: str
    source: str
    seed: int | None
    index: int
    raw: bytes


@dataclass(frozen=True)
class Observation:
    returncode: int
    stdout: bytes
    stderr: bytes


class FuzzConfigurationError(ValueError):
    """The requested fuzz plan or replay corpus is invalid."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def _jcs_ordered(value: Any) -> Any:
    """Independent JCS ordering for the contract's integer-only profile."""
    if isinstance(value, dict):
        return {
            key: _jcs_ordered(value[key])
            for key in sorted(value, key=lambda item: item.encode("utf-16-be"))
        }
    if isinstance(value, list):
        return [_jcs_ordered(item) for item in value]
    return value


def _jcs_bytes(value: Any) -> bytes:
    return json.dumps(
        _jcs_ordered(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=False,
    ).encode("utf-8")


def _self_zero_sha256(value: dict[str, Any], field: str) -> str:
    candidate = dict(value)
    candidate[field] = "0" * 64
    return _sha256(_jcs_bytes(candidate))


def _parse_seed(value: str) -> int:
    try:
        parsed = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seed must be an integer (decimal or 0x-prefixed)") from exc
    if not 0 <= parsed <= (1 << 64) - 1:
        raise argparse.ArgumentTypeError("seed must fit in an unsigned 64-bit integer")
    return parsed


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if not 1 <= parsed <= MAX_CASES:
        raise argparse.ArgumentTypeError(f"must be between 1 and {MAX_CASES}")
    return parsed


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not 0.0 < parsed <= 86_400.0:
        raise argparse.ArgumentTypeError("must be greater than zero and at most 86400")
    return parsed


def _repo_local_path(value: str, *, must_exist: bool) -> pathlib.Path:
    path = pathlib.Path(value)
    if not path.is_absolute():
        path = pathlib.Path.cwd() / path
    path = path.resolve()
    try:
        path.relative_to(REPO)
    except ValueError as exc:
        raise FuzzConfigurationError(f"corpus paths must stay inside the repository: {path}") from exc
    if must_exist and not path.is_file():
        raise FuzzConfigurationError(f"replay corpus does not exist: {path}")
    return path


def _load_fixture_inputs() -> tuple[list[SeedInput], list[SeedInput]]:
    semantic: list[SeedInput] = []
    wrappers: list[SeedInput] = []
    semantic_paths = (
        REPO / "baseline-run" / "fixtures" / "PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json",
        REPO / "supplemental-0_3" / "fixtures" / "B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
    )
    wrapper_paths = (
        REPO / "baseline-run" / "fixtures" / "B1_WRAPPER_PARITY_FIXTURE_PACK_0_2.json",
        REPO / "supplemental-0_3" / "fixtures" / "B1_SUPPLEMENTAL_WRAPPER_PARITY_FIXTURE_PACK_0_3.json",
    )
    for path in semantic_paths:
        pack = json.loads(path.read_text(encoding="utf-8"))
        for entry in pack["entries"]:
            semantic.append(
                SeedInput(
                    f"{path.name}:{entry['entry_id']}",
                    base64.b64decode(entry["semantic_request_jcs_lf_base64"], validate=True),
                )
            )
    for path in wrapper_paths:
        pack = json.loads(path.read_text(encoding="utf-8"))
        for pair in pack["pairs"]:
            for arm_key in ("b1_arm", "b1_attention_arm"):
                arm = pair[arm_key]
                wrappers.append(
                    SeedInput(
                        f"{path.name}:{pair['core_entry_id']}:{pair['pair_id']}:{arm_key}",
                        base64.b64decode(arm["request_jcs_lf_base64"], validate=True),
                    )
                )
    if not semantic or not wrappers:
        raise FuzzConfigurationError("fixture seed pools are unexpectedly empty")
    return semantic, wrappers


def _as_object(seed: SeedInput) -> dict[str, Any]:
    value = json.loads(seed.raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise FuzzConfigurationError(f"fixture seed is not an object: {seed.source}")
    return value


def _wire(value: Any) -> bytes:
    return _jcs_bytes(value) + b"\n"


def _choose(rng: random.Random, seeds: list[SeedInput]) -> SeedInput:
    return seeds[rng.randrange(len(seeds))]


def _choose_fixture_class(
    rng: random.Random, seeds: list[SeedInput], *, valid: bool
) -> SeedInput:
    matching = [seed for seed in seeds if ("-IO-" in seed.source) is valid]
    if not matching:
        raise FuzzConfigurationError("fixture pool has no matching semantic class")
    return _choose(rng, matching)


def _fixture_core_valid(
    rng: random.Random, semantic: list[SeedInput], _: list[SeedInput]
) -> tuple[bytes, str]:
    seed = _choose_fixture_class(rng, semantic, valid=True)
    return seed.raw, seed.source


def _fixture_core_defect(
    rng: random.Random, semantic: list[SeedInput], _: list[SeedInput]
) -> tuple[bytes, str]:
    seed = _choose_fixture_class(rng, semantic, valid=False)
    return seed.raw, seed.source


def _fixture_wrapper_valid(
    rng: random.Random, _: list[SeedInput], wrappers: list[SeedInput]
) -> tuple[bytes, str]:
    seed = _choose_fixture_class(rng, wrappers, valid=True)
    return seed.raw, seed.source


def _fixture_wrapper_defect(
    rng: random.Random, _: list[SeedInput], wrappers: list[SeedInput]
) -> tuple[bytes, str]:
    seed = _choose_fixture_class(rng, wrappers, valid=False)
    return seed.raw, seed.source


def _grammar_drop_required(
    rng: random.Random, semantic: list[SeedInput], wrappers: list[SeedInput]
) -> tuple[bytes, str]:
    pool = semantic if rng.randrange(2) == 0 else wrappers
    seed = _choose(rng, pool)
    obj = _as_object(seed)
    candidates = [
        key
        for key in ("request_id", "operation_handle", "decision_input", "semantic_request", "format_version")
        if key in obj
    ]
    del obj[candidates[rng.randrange(len(candidates))]]
    return _wire(obj), seed.source


def _grammar_wrong_type(
    rng: random.Random, semantic: list[SeedInput], wrappers: list[SeedInput]
) -> tuple[bytes, str]:
    pool = semantic if rng.randrange(2) == 0 else wrappers
    seed = _choose(rng, pool)
    obj = _as_object(seed)
    candidates = [key for key in ("request_id", "operation_handle", "budget", "decision_input") if key in obj]
    key = candidates[rng.randrange(len(candidates))]
    wrong_values: tuple[Any, ...] = (None, True, [], {}, -1)
    obj[key] = wrong_values[rng.randrange(len(wrong_values))]
    return _wire(obj), seed.source


def _grammar_unknown_member(
    rng: random.Random, semantic: list[SeedInput], wrappers: list[SeedInput]
) -> tuple[bytes, str]:
    pool = semantic if rng.randrange(2) == 0 else wrappers
    seed = _choose(rng, pool)
    obj = _as_object(seed)
    obj["_fuzz_unknown"] = {"token": rng.randrange(1 << 16)}
    return _wire(obj), seed.source


def _grammar_binding_mismatch(
    rng: random.Random, semantic: list[SeedInput], _: list[SeedInput]
) -> tuple[bytes, str]:
    seed = _choose(rng, semantic)
    obj = _as_object(seed)
    current = obj["request_id"]
    replacement = "RUN_" + ("F" * 24 if current != "RUN_" + "F" * 24 else "E" * 24)
    obj["request_id"] = replacement
    return _wire(obj), seed.source


def _grammar_fact_shape(
    rng: random.Random, semantic: list[SeedInput], wrappers: list[SeedInput]
) -> tuple[bytes, str]:
    pool = semantic if rng.randrange(2) == 0 else wrappers
    seed = _choose(rng, pool)
    obj = _as_object(seed)
    semantic_obj = obj.get("semantic_request", obj)
    facts = semantic_obj.get("decision_input", {}).get("facts")
    if isinstance(facts, dict):
        facts["_fuzz_schema_probe"] = [rng.randrange(8), None]
    else:
        semantic_obj["decision_input"] = {"facts": {"_fuzz_schema_probe": True}}
    return _wire(obj), seed.source


def _utf8_edges(
    rng: random.Random, semantic: list[SeedInput], wrappers: list[SeedInput]
) -> tuple[bytes, str]:
    pool = semantic if rng.randrange(2) == 0 else wrappers
    seed = _choose(rng, pool)
    obj = _as_object(seed)
    obj["_fuzz_utf8_edges"] = "\u0080\u07ff\u0800￿\U00010000\U0010ffff"
    return _wire(obj), seed.source


def _bom(rng: random.Random, semantic: list[SeedInput], _: list[SeedInput]) -> tuple[bytes, str]:
    seed = _choose(rng, semantic)
    return b"\xef\xbb\xbf" + seed.raw, seed.source


def _invalid_utf8(
    rng: random.Random, semantic: list[SeedInput], _: list[SeedInput]
) -> tuple[bytes, str]:
    seed = _choose(rng, semantic)
    invalid = (b"\x80", b"\xc0\xaf", b"\xed\xa0\x80", b"\xf5\x80\x80\x80")
    payload = seed.raw[:-1]
    position = rng.randrange(len(payload) + 1)
    return payload[:position] + invalid[rng.randrange(len(invalid))] + payload[position:] + b"\n", seed.source


def _lone_surrogate(
    _: random.Random, __: list[SeedInput], ___: list[SeedInput]
) -> tuple[bytes, str]:
    raw = b'{"format_version":"B1-SEMANTIC-DECISION-REQUEST-0.2","x":"\\ud800"}\n'
    return raw, "synthetic:lone-surrogate-escape"


def _duplicate_key(
    _: random.Random, __: list[SeedInput], ___: list[SeedInput]
) -> tuple[bytes, str]:
    raw = (
        b'{"format_version":"B1-SEMANTIC-DECISION-REQUEST-0.2",'
        b'"format_version":"B1-SEMANTIC-DECISION-REQUEST-0.2"}\n'
    )
    return raw, "synthetic:duplicate-root-key"


def _deep_nesting(
    _: random.Random, __: list[SeedInput], ___: list[SeedInput]
) -> tuple[bytes, str]:
    depth = b1.MAX_NESTING + 2
    return b"[" * depth + b"0" + b"]" * depth + b"\n", f"synthetic:array-depth-{depth}"


def _deep_known_envelope(
    rng: random.Random, __: list[SeedInput], ___: list[SeedInput]
) -> tuple[bytes, str]:
    depth = b1.MAX_NESTING + 2
    format_version = (
        b1.CORE_REQUEST_FORMAT if rng.randrange(2) == 0 else b1.WRAPPER_REQUEST_FORMAT
    ).encode("ascii")
    raw = (
        b'{"format_version":"'
        + format_version
        + b'","request_id":"RUN_000000000000000000000001","x":'
        + b"[" * depth
        + b"0"
        + b"]" * depth
        + b"}\n"
    )
    return raw, f"synthetic:known-envelope-depth-{depth}"


def _huge_integer(
    rng: random.Random, __: list[SeedInput], ___: list[SeedInput]
) -> tuple[bytes, str]:
    digits = 5_000 + rng.randrange(33)
    raw = (
        b'{"format_version":"B1-SEMANTIC-DECISION-REQUEST-0.2","x":'
        + b"9" * digits
        + b"}\n"
    )
    return raw, f"synthetic:integer-digits-{digits}"


def _nfc_key(_: random.Random, __: list[SeedInput], ___: list[SeedInput]) -> tuple[bytes, str]:
    return '{"é":0}\n'.encode("utf-8"), "synthetic:nfd-key"


def _nfc_value(_: random.Random, __: list[SeedInput], ___: list[SeedInput]) -> tuple[bytes, str]:
    return '{"a":"é"}\n'.encode("utf-8"), "synthetic:nfd-value"


def _noncanonical_whitespace(
    rng: random.Random, semantic: list[SeedInput], _: list[SeedInput]
) -> tuple[bytes, str]:
    seed = _choose(rng, semantic)
    return seed.raw[:1] + b" " + seed.raw[1:], seed.source


def _missing_lf(
    rng: random.Random, semantic: list[SeedInput], wrappers: list[SeedInput]
) -> tuple[bytes, str]:
    seed = _choose(rng, semantic if rng.randrange(2) == 0 else wrappers)
    return seed.raw[:-1], seed.source


def _crlf(
    rng: random.Random, semantic: list[SeedInput], wrappers: list[SeedInput]
) -> tuple[bytes, str]:
    seed = _choose(rng, semantic if rng.randrange(2) == 0 else wrappers)
    return seed.raw[:-1] + b"\r\n", seed.source


def _trailing_bytes(
    rng: random.Random, semantic: list[SeedInput], _: list[SeedInput]
) -> tuple[bytes, str]:
    seed = _choose(rng, semantic)
    return seed.raw + b"x", seed.source


def _truncate(
    rng: random.Random, semantic: list[SeedInput], wrappers: list[SeedInput]
) -> tuple[bytes, str]:
    seed = _choose(rng, semantic if rng.randrange(2) == 0 else wrappers)
    cut = rng.randint(1, min(32, len(seed.raw)))
    return seed.raw[:-cut], seed.source


def _bit_flip(
    rng: random.Random, semantic: list[SeedInput], wrappers: list[SeedInput]
) -> tuple[bytes, str]:
    seed = _choose(rng, semantic if rng.randrange(2) == 0 else wrappers)
    raw = bytearray(seed.raw)
    position = rng.randrange(len(raw))
    raw[position] ^= 1 << rng.randrange(8)
    return bytes(raw), seed.source


def _byte_insert(
    rng: random.Random, semantic: list[SeedInput], wrappers: list[SeedInput]
) -> tuple[bytes, str]:
    seed = _choose(rng, semantic if rng.randrange(2) == 0 else wrappers)
    position = rng.randrange(len(seed.raw) + 1)
    token = (b"\x00", b"\xff", b"{}", b"[]", b'"', b",", b"\n")[rng.randrange(7)]
    return seed.raw[:position] + token + seed.raw[position:], seed.source


def _byte_delete(
    rng: random.Random, semantic: list[SeedInput], wrappers: list[SeedInput]
) -> tuple[bytes, str]:
    seed = _choose(rng, semantic if rng.randrange(2) == 0 else wrappers)
    start = rng.randrange(len(seed.raw))
    width = rng.randint(1, min(8, len(seed.raw) - start))
    return seed.raw[:start] + seed.raw[start + width :], seed.source


def _byte_splice(
    rng: random.Random, semantic: list[SeedInput], wrappers: list[SeedInput]
) -> tuple[bytes, str]:
    left = _choose(rng, semantic)
    right = _choose(rng, wrappers)
    left_at = rng.randrange(len(left.raw) + 1)
    right_at = rng.randrange(len(right.raw) + 1)
    return left.raw[:left_at] + right.raw[right_at:], f"{left.source}|{right.source}"


def _root_scalar(
    rng: random.Random, _: list[SeedInput], __: list[SeedInput]
) -> tuple[bytes, str]:
    choices: tuple[Any, ...] = (None, True, False, 0, -1, "receiver", [], [0])
    return _wire(choices[rng.randrange(len(choices))]), "synthetic:root-scalar"


def _empty_input(
    _: random.Random, __: list[SeedInput], ___: list[SeedInput]
) -> tuple[bytes, str]:
    return b"", "synthetic:empty"


def _random_json(rng: random.Random, depth: int) -> Any:
    atoms: tuple[Any, ...] = (None, True, False, 0, -1, 1, "", "fuzz", "Ω", "U0001f642")
    if depth <= 0 or rng.randrange(4) == 0:
        return atoms[rng.randrange(len(atoms))]
    if rng.randrange(2) == 0:
        return [_random_json(rng, depth - 1) for _ in range(rng.randrange(5))]
    return {
        f"fuzz_{index}_{rng.randrange(1 << 16):04X}": _random_json(rng, depth - 1)
        for index in range(rng.randrange(5))
    }


def _random_grammar(
    rng: random.Random, _: list[SeedInput], __: list[SeedInput]
) -> tuple[bytes, str]:
    return _wire(_random_json(rng, 6)), "synthetic:bounded-json-grammar"


Strategy = Callable[[random.Random, list[SeedInput], list[SeedInput]], tuple[bytes, str]]

STRATEGIES: dict[str, Strategy] = {
    "fixture_core_valid": _fixture_core_valid,
    "fixture_core_defect": _fixture_core_defect,
    "fixture_wrapper_valid": _fixture_wrapper_valid,
    "fixture_wrapper_defect": _fixture_wrapper_defect,
    "grammar_drop_required": _grammar_drop_required,
    "grammar_wrong_type": _grammar_wrong_type,
    "grammar_unknown_member": _grammar_unknown_member,
    "grammar_binding_mismatch": _grammar_binding_mismatch,
    "grammar_fact_shape": _grammar_fact_shape,
    "utf8_edges": _utf8_edges,
    "bom": _bom,
    "invalid_utf8": _invalid_utf8,
    "lone_surrogate": _lone_surrogate,
    "duplicate_key": _duplicate_key,
    "deep_nesting": _deep_nesting,
    "deep_known_envelope": _deep_known_envelope,
    "huge_integer": _huge_integer,
    "nfc_key": _nfc_key,
    "nfc_value": _nfc_value,
    "noncanonical_whitespace": _noncanonical_whitespace,
    "missing_lf": _missing_lf,
    "crlf": _crlf,
    "trailing_bytes": _trailing_bytes,
    "truncate": _truncate,
    "bit_flip": _bit_flip,
    "byte_insert": _byte_insert,
    "byte_delete": _byte_delete,
    "byte_splice": _byte_splice,
    "root_scalar": _root_scalar,
    "empty_input": _empty_input,
    "random_grammar": _random_grammar,
}


def _make_case(seed: int, index: int, strategy: str, raw: bytes, source: str) -> FuzzCase:
    digest = _sha256(raw)
    case_id = f"S{seed:016X}-C{index:06d}-{strategy}-{digest[:12]}"
    return FuzzCase(case_id, strategy, source, seed, index, raw)


def generate_cases(seed: int, count: int, strategies: list[str]) -> list[FuzzCase]:
    semantic, wrappers = _load_fixture_inputs()
    rng = random.Random(seed)
    cases: list[FuzzCase] = []
    for index in range(count):
        strategy = strategies[index % len(strategies)]
        raw, source = STRATEGIES[strategy](rng, semantic, wrappers)
        cases.append(_make_case(seed, index, strategy, raw, source))
    return cases


def _corpus_record(case: FuzzCase) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "format_version": CORPUS_FORMAT,
        "index": case.index,
        "input_base64": base64.b64encode(case.raw).decode("ascii"),
        "input_sha256": _sha256(case.raw),
        "seed": case.seed,
        "source": case.source,
        "strategy": case.strategy,
    }


def write_corpus(path: pathlib.Path, cases: Iterable[FuzzCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        json.dumps(_corpus_record(case), ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        for case in cases
    ]
    path.write_text("".join(record + "\n" for record in records), encoding="utf-8", newline="\n")


def load_corpus(path: pathlib.Path) -> list[FuzzCase]:
    if path.stat().st_size > MAX_CORPUS_BYTES:
        raise FuzzConfigurationError(f"replay corpus exceeds {MAX_CORPUS_BYTES} bytes: {path}")
    cases: list[FuzzCase] = []
    seen_ids: set[str] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.endswith("\n") or line.endswith("\r\n"):
                raise FuzzConfigurationError(f"corpus line {line_number} is not LF-terminated")
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise FuzzConfigurationError(f"invalid corpus JSON on line {line_number}: {exc}") from exc
            if not isinstance(record, dict) or record.get("format_version") != CORPUS_FORMAT:
                raise FuzzConfigurationError(f"invalid corpus record on line {line_number}")
            expected_keys = {
                "case_id",
                "format_version",
                "index",
                "input_base64",
                "input_sha256",
                "seed",
                "source",
                "strategy",
            }
            if set(record) != expected_keys:
                raise FuzzConfigurationError(f"unexpected corpus fields on line {line_number}")
            try:
                case_id = record["case_id"]
                strategy = record["strategy"]
                source = record["source"]
                index = record["index"]
                seed = record["seed"]
                raw = base64.b64decode(record["input_base64"], validate=True)
                expected_digest = record["input_sha256"]
            except (KeyError, TypeError, ValueError) as exc:
                raise FuzzConfigurationError(f"malformed corpus record on line {line_number}") from exc
            if (
                not isinstance(case_id, str)
                or not isinstance(strategy, str)
                or not isinstance(source, str)
                or not isinstance(index, int)
                or isinstance(index, bool)
                or (seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)))
                or not isinstance(expected_digest, str)
            ):
                raise FuzzConfigurationError(f"wrong corpus field type on line {line_number}")
            if index < 0 or (seed is not None and not 0 <= seed <= (1 << 64) - 1):
                raise FuzzConfigurationError(f"out-of-range corpus field on line {line_number}")
            if len(raw) > b1.MAX_INPUT_BYTES + 1:
                raise FuzzConfigurationError(f"corpus input is over the bounded replay cap on line {line_number}")
            if case_id in seen_ids:
                raise FuzzConfigurationError(f"duplicate corpus case_id on line {line_number}: {case_id}")
            if _sha256(raw) != expected_digest:
                raise FuzzConfigurationError(f"corpus digest mismatch on line {line_number}: {case_id}")
            seen_ids.add(case_id)
            cases.append(FuzzCase(case_id, strategy, source, seed, index, raw))
            if len(cases) > MAX_CASES:
                raise FuzzConfigurationError(f"corpus contains more than {MAX_CASES} cases")
    if not cases:
        raise FuzzConfigurationError(f"replay corpus is empty: {path}")
    return cases


def _select_cases(cases: list[FuzzCase], selectors: list[str]) -> list[FuzzCase]:
    if not selectors:
        return cases
    selected: list[FuzzCase] = []
    seen: set[str] = set()
    for selector in selectors:
        if selector.isdecimal():
            matches = [case for case in cases if case.index == int(selector)]
        else:
            matches = [case for case in cases if case.case_id == selector]
        if not matches:
            raise FuzzConfigurationError(f"case selector matched nothing: {selector}")
        for case in matches:
            if case.case_id not in seen:
                selected.append(case)
                seen.add(case.case_id)
    return selected


def _run_once(raw: bytes, timeout_seconds: float) -> Observation:
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-B", str(RUNNER), "execute"],
            input=raw,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=REPO,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"runner timed out after {timeout_seconds:.3f}s") from exc
    return Observation(completed.returncode, completed.stdout, completed.stderr)


def _validate_observation(observation: Observation) -> list[str]:
    errors: list[str] = []
    if observation.returncode not in {0, 1, 2, 3}:
        errors.append(f"process exit code {observation.returncode} is outside {{0,1,2,3}}")
    if observation.stderr:
        errors.append(f"stderr is nonempty ({len(observation.stderr)} bytes; uncaught exception suspected)")
    if len(observation.stdout) > b1.MAX_OUTPUT_BYTES:
        errors.append(f"stdout exceeds {b1.MAX_OUTPUT_BYTES} bytes")
    if not observation.stdout.endswith(b"\n"):
        errors.append("stdout is not LF-terminated")
        return errors
    payload = observation.stdout[:-1]
    try:
        response = json.loads(payload.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"stdout is not one strict UTF-8 JSON value: {exc}")
        return errors
    if not isinstance(response, dict):
        errors.append("response root is not an object")
        return errors
    try:
        canonical = _jcs_bytes(response) + b"\n"
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        errors.append(f"response cannot be JCS-encoded: {exc}")
        return errors
    if observation.stdout != canonical:
        errors.append("stdout is not exactly one JCS response plus LF")

    format_version = response.get("format_version")
    if format_version == b1.CORE_RESPONSE_FORMAT:
        schema_errors = b1.validate_core_response(response)
        seal_field = "receipt_sha256"
    elif format_version == b1.WRAPPER_RESPONSE_FORMAT:
        schema_errors = b1.validate_wrapper_response(response)
        seal_field = "response_sha256"
    else:
        errors.append(f"unknown response format_version: {format_version!r}")
        return errors
    if schema_errors:
        errors.append(f"response schema errors: {schema_errors[:5]}")

    response_exit = response.get("exit_code")
    if response_exit not in {0, 1, 2, 3}:
        errors.append(f"response exit_code {response_exit!r} is outside {{0,1,2,3}}")
    elif response_exit != observation.returncode:
        errors.append(
            f"process exit code {observation.returncode} disagrees with response exit_code {response_exit}"
        )

    if response.get("ok") is True:
        if response.get("errors") != [] or not isinstance(response.get("output"), dict):
            errors.append("successful response is not success-shaped")
        if response_exit not in {0, 1}:
            errors.append("successful response exit_code is not 0 or 1")
    elif response.get("ok") is False:
        protocol_errors = response.get("errors")
        protocol_error = protocol_errors[0] if isinstance(protocol_errors, list) and len(protocol_errors) == 1 else None
        if (
            not isinstance(protocol_error, dict)
            or protocol_error.get("code") not in b1.ERRORS
            or response.get("output") is not None
            or response.get("result") != "INCOMPLETE"
            or response_exit not in {2, 3}
        ):
            errors.append("error response is not protocol-error-shaped")
    else:
        errors.append("response ok field is not boolean")

    supplied_seal = response.get(seal_field)
    try:
        expected_seal = _self_zero_sha256(response, seal_field)
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        errors.append(f"self-zero seal cannot be recomputed: {exc}")
    else:
        if supplied_seal != expected_seal:
            errors.append(f"{seal_field} fails the self-zero rule")
    return errors


def _validate_case(
    case: FuzzCase, deadline: float, case_timeout: float
) -> tuple[list[str], int | None]:
    observations: list[Observation] = []
    failures: list[str] = []
    for run_number in (1, 2):
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return [f"budget exhausted before run {run_number}"], None
        timeout = min(case_timeout, remaining)
        try:
            observation = _run_once(case.raw, timeout)
        except RuntimeError as exc:
            return [f"run {run_number}: {exc}"], None
        observations.append(observation)
        try:
            messages = _validate_observation(observation)
        except Exception as exc:  # noqa: BLE001 - a validator crash is a harness finding
            messages = [f"harness response validator raised {type(exc).__name__}: {exc}"]
        failures.extend(f"run {run_number}: {message}" for message in messages)
    if observations[0] != observations[1]:
        failures.append("two fresh subprocess runs differ in exit code, stdout, or stderr bytes")
    return failures, observations[0].returncode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic grammar-aware and byte-mutational fuzzing of the one-shot runner."
    )
    parser.add_argument(
        "--seed",
        type=_parse_seed,
        default=DEFAULT_SEED,
        help=f"unsigned 64-bit seed (default: 0x{DEFAULT_SEED:08X})",
    )
    parser.add_argument(
        "--cases",
        type=_positive_int,
        default=None,
        help=f"number of generated/replayed cases (generated default: {DEFAULT_CASES})",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        metavar="INDEX_OR_ID",
        help="run one generated index or exact replay case_id; repeatable",
    )
    parser.add_argument(
        "--strategy",
        action="append",
        choices=tuple(STRATEGIES),
        default=[],
        help="limit generation/replay to a named strategy; repeatable",
    )
    parser.add_argument(
        "--budget-seconds",
        type=_positive_float,
        default=DEFAULT_BUDGET_SECONDS,
        help=f"total wall-clock safety budget (default: {DEFAULT_BUDGET_SECONDS:g})",
    )
    parser.add_argument(
        "--case-timeout-seconds",
        type=_positive_float,
        default=5.0,
        help="timeout for each isolated runner invocation (default: 5)",
    )
    parser.add_argument(
        "--ci-smoke",
        action="store_true",
        help=f"cover every strategy once with a {CI_BUDGET_SECONDS:g}s budget unless overridden",
    )
    parser.add_argument("--replay", metavar="CORPUS_JSONL", help="replay a repo-local JSONL corpus")
    parser.add_argument(
        "--emit-corpus", metavar="CORPUS_JSONL", help="write the selected cases as a repo-local replay corpus"
    )
    parser.add_argument(
        "--failures-out", metavar="CORPUS_JSONL", help="write failing inputs as a repo-local replay corpus"
    )
    parser.add_argument("--list-strategies", action="store_true", help="print strategy names and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.list_strategies:
        print("\n".join(STRATEGIES))
        return 0
    if not RUNNER.is_file():
        print(f"rr-fuzz: configuration error: runner not found: {RUNNER}", file=sys.stderr)
        return 2

    try:
        strategies = list(dict.fromkeys(args.strategy)) if args.strategy else list(STRATEGIES)
        if args.replay:
            replay_path = _repo_local_path(args.replay, must_exist=True)
            cases = load_corpus(replay_path)
            if args.strategy:
                cases = [case for case in cases if case.strategy in strategies]
                if not cases:
                    raise FuzzConfigurationError("strategy filter removed every replay case")
            if args.cases is not None:
                cases = cases[: args.cases]
            source_label = f"replay:{replay_path.relative_to(REPO).as_posix()}"
            seed_label = "replay"
        else:
            case_count = args.cases
            if case_count is None:
                case_count = len(strategies) if args.ci_smoke else DEFAULT_CASES
            numeric_selectors = [int(item) for item in args.case if item.isdecimal()]
            if numeric_selectors:
                case_count = max(case_count, max(numeric_selectors) + 1)
                if case_count > MAX_CASES:
                    raise FuzzConfigurationError(f"selected generated index exceeds {MAX_CASES - 1}")
            cases = generate_cases(args.seed, case_count, strategies)
            source_label = "generated"
            seed_label = f"0x{args.seed:016X}"
        cases = _select_cases(cases, args.case)
        if args.emit_corpus:
            write_corpus(_repo_local_path(args.emit_corpus, must_exist=False), cases)
    except (FuzzConfigurationError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"rr-fuzz: configuration error: {exc}", file=sys.stderr)
        return 2

    budget = min(args.budget_seconds, CI_BUDGET_SECONDS) if args.ci_smoke else args.budget_seconds
    case_timeout = (
        min(args.case_timeout_seconds, CI_CASE_TIMEOUT_SECONDS)
        if args.ci_smoke
        else args.case_timeout_seconds
    )
    deadline = time.monotonic() + budget
    failures: list[tuple[FuzzCase, list[str]]] = []
    strategy_counts: dict[str, int] = {}
    exit_counts: dict[str, int] = {}
    completed = 0
    budget_exhausted = False

    for case in cases:
        if time.monotonic() >= deadline:
            budget_exhausted = True
            break
        case_failures, observed_exit = _validate_case(case, deadline, case_timeout)
        completed += 1
        strategy_counts[case.strategy] = strategy_counts.get(case.strategy, 0) + 1
        if case_failures:
            failures.append((case, case_failures))
            if any(message.startswith("budget exhausted") for message in case_failures):
                budget_exhausted = True
                break
        elif observed_exit is not None:
            exit_key = str(observed_exit)
            exit_counts[exit_key] = exit_counts.get(exit_key, 0) + 1

    if completed < len(cases):
        budget_exhausted = True
    if args.failures_out and failures:
        try:
            write_corpus(
                _repo_local_path(args.failures_out, must_exist=False),
                (case for case, _ in failures),
            )
        except (FuzzConfigurationError, OSError) as exc:
            print(f"rr-fuzz: could not write failures corpus: {exc}", file=sys.stderr)
            return 2

    for case, messages in failures[:20]:
        print(
            f"FAIL {case.case_id} strategy={case.strategy} input_sha256={_sha256(case.raw)} "
            + " | ".join(messages)
        )
    if len(failures) > 20:
        print(f"FAIL ... {len(failures) - 20} additional failing cases omitted")

    verdict = "PASS" if not failures and not budget_exhausted else "FAIL"
    print(
        "rr-fuzz: "
        f"verdict={verdict} cases={completed}/{len(cases)} seed={seed_label} source={source_label} "
        f"failures={len(failures)} budget_exhausted={str(budget_exhausted).lower()}"
    )
    print(f"strategy_counts={json.dumps(strategy_counts, sort_keys=True, separators=(',', ':'))}")
    print(f"exit_counts={json.dumps(exit_counts, sort_keys=True, separators=(',', ':'))}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
