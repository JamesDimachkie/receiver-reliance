#!/usr/bin/env python3
"""Exact equivalence and work-reduction checks for the single-pass audit.

The legacy oracle below is the pre-O3 ``decide_audited`` algorithm: run the
frozen engine, classify again, then trace the selected predicate separately.
The production path must remain JCS-byte-identical to that oracle over every
semantic fixture, a deterministic generated fuzz corpus, and generated
``exact_reference`` cases.

Generated cases use the recorded seeds below.  ``--benchmark`` additionally
runs paired/interleaved observational timing; it has no flaky speed assertion.
"""
from __future__ import annotations

import argparse
import base64
import copy
import gc
import importlib.util
import json
import pathlib
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
FUZZ_PATH = REPO / "fuzz" / "fuzz.py"
PACKS = (
    REPO / "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json",
    REPO / "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
)
FUZZ_SEED = 0x0B10F042
FUZZ_CASES = 256
REFERENCE_SEED = 0x5EED0A03
REFERENCE_CASES = 128
BENCHMARK_REPETITIONS = 11
BENCHMARK_INNER_LOOPS = 3
MAX_FAILURE_DETAILS = 20

sys.path.insert(0, str(HERE))
import rr_api  # noqa: E402
from rr_api import b1, pcb_runner  # noqa: E402


checks = 0
failure_count = 0
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global checks, failure_count
    checks += 1
    if not condition:
        failure_count += 1
        if len(failures) < MAX_FAILURE_DETAILS:
            suffix = f" -- {detail}" if detail else ""
            failures.append(f"FAIL {name}{suffix}")


def load_semantic_fixtures() -> list[tuple[str, bytes, bytes, dict[str, Any]]]:
    fixtures: list[tuple[str, bytes, bytes, dict[str, Any]]] = []
    for path in PACKS:
        pack = json.loads(path.read_text(encoding="utf-8"))
        for entry in pack["entries"]:
            raw = base64.b64decode(entry["semantic_request_jcs_lf_base64"], validate=True)
            expected = base64.b64decode(
                entry["expected_response_jcs_lf_base64"], validate=True
            )
            fixtures.append((entry["entry_id"], raw, expected, entry["semantic_request"]))
    fixtures.sort(key=lambda item: item[0].encode("utf-8"))
    if len(fixtures) != 124:
        raise RuntimeError(f"expected 124 semantic fixtures, got {len(fixtures)}")
    return fixtures


def load_fuzz_module() -> Any:
    spec = importlib.util.spec_from_file_location("rr_o3_fuzz_harness", FUZZ_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load fuzz harness: {FUZZ_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def legacy_decide_audited(request: dict[str, Any] | bytes) -> dict[str, Any]:
    """Pre-O3 audited algorithm, retained only as an equivalence oracle."""
    raw = request if isinstance(request, bytes) else b1.jcs_bytes(request) + b"\n"
    response, exit_code = pcb_runner._execute(raw)
    audited: dict[str, Any] = {
        "format_version": rr_api.AUDIT_FORMAT,
        "sealed_response": response,
        "exit_code": exit_code,
        "audit": None,
        "audited_behavior_class": None,
        "audit_sha256": b1.ZERO64,
    }
    audit: dict[str, Any] = {
        "request_raw_sha256": b1.sha256_upper(raw),
        "engine_generation": "composed-0.3-frozen",
        "governing_authorities": dict(rr_api.GOVERNING_AUTHORITIES),
    }
    if response.get("ok"):
        parsed = json.loads(raw.decode("utf-8"))
        semantic = parsed["semantic_request"] if "semantic_request" in parsed else parsed
        decision_input = semantic["decision_input"]
        obligation_id = semantic["obligation_id"]
        operation_handle = semantic["operation_handle"]
        audit["decision_input_sha256"] = b1.sha256_upper(b1.jcs_bytes(decision_input))
        behavior, fired_map = b1.classify(operation_handle, decision_input)
        output = response.get("output") or {}
        sealed_class = (
            (output.get("result_object") or {}).get("behavior_class")
            or (output.get("payload") or {}).get("behavior_class")
        )
        if behavior != sealed_class:
            raise RuntimeError("trace classification diverged from sealed response")
        witness: list[dict[str, Any]] = []
        if behavior != "VALID":
            rr_api._trace(
                b1.decision_table()[operation_handle][behavior], decision_input, witness
            )
        audit["first_match_predicates"] = fired_map
        audit["matched_class_witness"] = witness
        legacy_refs, legacy_truncated = rr_api._derive_record_references_full(
            decision_input.get("facts")
        )
        audit["record_references"] = legacy_refs
        audit["record_references_truncated"] = legacy_truncated
        findings = rr_api.closure_findings(obligation_id, decision_input)
        audit["closure_findings"] = findings
        tightened = [finding["tightens_to"] for finding in findings if finding.get("fired")]
        if behavior == "VALID" and any(
            "evaluator_error" in finding for finding in findings
        ):
            final = "AUDIT_INCOMPLETE"
        elif behavior == "VALID" and tightened:
            final = min(tightened, key=rr_api._CLASS_ORDER.index)
        else:
            final = behavior
        audited["audited_behavior_class"] = final
    else:
        audit["decision_input_sha256"] = None
        audit["errors"] = response.get("errors")
        audited["audited_behavior_class"] = "PROTOCOL_ERROR"
    audited["audit"] = audit
    audited["audit_sha256"] = b1.self_zero_sha256(audited, "audit_sha256")
    return audited


def exact_equal(name: str, raw: dict[str, Any] | bytes) -> None:
    optimized = rr_api.decide_audited(raw)
    legacy = legacy_decide_audited(raw)
    optimized_bytes = b1.jcs_bytes(optimized)
    legacy_bytes = b1.jcs_bytes(legacy)
    check(name, optimized_bytes == legacy_bytes, b1.sha256_upper(optimized_bytes))


def check_sealed_class_mismatch_defense(
    fixtures: list[tuple[str, bytes, bytes, dict[str, Any]]],
) -> None:
    """A forged frozen class must still fail the audit cross-check."""
    examples: dict[str, bytes] = {}
    for _entry_id, raw, _expected, _request in fixtures:
        response, _exit_code = pcb_runner._execute(raw)
        if not response.get("ok"):
            continue
        output = response.get("output") or {}
        behavior = (
            (output.get("result_object") or {}).get("behavior_class")
            or (output.get("payload") or {}).get("behavior_class")
        )
        examples.setdefault(behavior, raw)
    scenarios = (
        ("MALFORMED_OR_BOUNDARY", "VALID"),
        ("VALID", "OMISSION_OR_INCOMPLETE"),
    )
    original_execute = pcb_runner._execute
    for actual, forged in scenarios:
        raw = examples[actual]

        def forged_execute(request_raw: bytes) -> tuple[dict[str, Any], int]:
            response, exit_code = original_execute(request_raw)
            response = copy.deepcopy(response)
            output = response["output"]
            result_object = output.get("result_object") or output.get("payload")
            result_object["behavior_class"] = forged
            return response, exit_code

        pcb_runner._execute = forged_execute
        try:
            try:
                rr_api.decide_audited(raw)
            except RuntimeError as err:
                check(
                    f"defense:{actual}-as-{forged}",
                    str(err) == "trace classification diverged from sealed response",
                    str(err),
                )
            else:
                check(f"defense:{actual}-as-{forged}", False, "did not raise")
        finally:
            pcb_runner._execute = original_execute


def atomic_call_count(call: Callable[[], Any]) -> int:
    original = b1._eval_atomic
    count = 0

    def counted(node: dict[str, Any], doc: Any) -> bool:
        nonlocal count
        count += 1
        return original(node, doc)

    b1._eval_atomic = counted
    try:
        call()
    finally:
        b1._eval_atomic = original
    return count


def generated_reference_facts() -> list[tuple[dict[str, Any], list[str]]]:
    rng = random.Random(REFERENCE_SEED)
    cases: list[tuple[dict[str, Any], list[str]]] = []
    for index in range(REFERENCE_CASES):
        legitimate = f"REC_EXACT_{index:03d}_记录"
        marker = f"REC_MARKER_{rng.randrange(1 << 24):06X}"
        pairs: list[tuple[str, Any]] = [
            ("not_exact_reference_backup", f"DECOY_TOP_{index:03d}"),
            ("untrusted_exact_reference_note", f"DECOY_NOTE_{index:03d}"),
            ("linked_record_id", marker),
        ]
        expected = [marker]
        if index % 3:
            pairs.append(("exact_reference", legitimate))
            expected.append(legitimate)
        rng.shuffle(pairs)
        facts = dict(pairs)
        facts["nested"] = {
            "exact_reference_suffix": f"DECOY_NESTED_{index:03d}",
            "plain": "IGNORE",
        }
        cases.append((facts, sorted(expected)))
    return cases


def run_equivalence() -> list[tuple[str, bytes, bytes, dict[str, Any]]]:
    fixtures = load_semantic_fixtures()

    # Every accepted semantic request and frozen response byte.
    for entry_id, raw, expected, request in fixtures:
        optimized = rr_api.decide_audited(raw)
        legacy = legacy_decide_audited(raw)
        check(
            f"fixture:{entry_id}:whole-audit",
            b1.jcs_bytes(optimized) == b1.jcs_bytes(legacy),
        )
        check(
            f"fixture:{entry_id}:sealed-response",
            b1.jcs_bytes(optimized["sealed_response"]) + b"\n" == expected,
        )
        check(
            f"fixture:{entry_id}:dict-input",
            b1.jcs_bytes(rr_api.decide_audited(request))
            == b1.jcs_bytes(legacy_decide_audited(request)),
        )

    check_sealed_class_mismatch_defense(fixtures)

    # The committed deterministic strategy corpus: generated, never workspace-derived.
    fuzz = load_fuzz_module()
    fuzz_cases = fuzz.generate_cases(FUZZ_SEED, FUZZ_CASES, list(fuzz.STRATEGIES))
    for case in fuzz_cases:
        exact_equal(f"fuzz:{case.case_id}", case.raw)

    # The exact-key F1 behavior plus input-order and decoy coverage.
    for index, (facts, expected) in enumerate(generated_reference_facts()):
        actual = rr_api.derive_record_references(facts)
        check(f"reference:{index}:exact-decoys", actual == expected, str(actual))
        reversed_facts = dict(reversed(list(facts.items())))
        check(
            f"reference:{index}:input-order",
            rr_api.derive_record_references(reversed_facts) == expected,
        )

    # Valid OBL-02 requests with generated exact references exercise the audit field.
    _, _, _, obl02 = next(item for item in fixtures if "OBL-02-IO" in item[0])
    for index in range(64):
        request = copy.deepcopy(obl02)
        reference = f"REC_GENERATED_{index:03d}"
        request["decision_input"]["facts"]["exact_reference"] = reference
        exact_equal(f"exact-reference-request:{index}", request)
        audited = rr_api.decide_audited(request)
        check(
            f"exact-reference-request:{index}:derived",
            reference in audited["audit"]["record_references"],
        )

    # Count frozen + audit predicate atoms: optimized can only remove work.
    reduced_cases = 0
    saved_atoms = 0
    for entry_id, raw, _expected, _request in fixtures:
        legacy_count = atomic_call_count(lambda raw=raw: legacy_decide_audited(raw))
        optimized_count = atomic_call_count(lambda raw=raw: rr_api.decide_audited(raw))
        check(
            f"work:{entry_id}:nonincreasing",
            optimized_count <= legacy_count,
            f"optimized={optimized_count} legacy={legacy_count}",
        )
        if optimized_count < legacy_count:
            reduced_cases += 1
            saved_atoms += legacy_count - optimized_count
    check("work:some-fixtures-reduced", reduced_cases > 0, str(reduced_cases))
    check("work:atomic-calls-saved", saved_atoms > 0, str(saved_atoms))
    print(
        "single-pass work reduction: "
        f"reduced_fixtures={reduced_cases}/{len(fixtures)} atomic_calls_saved={saved_atoms}"
    )

    # Local state only: interleaving and threads must reproduce sequential bytes.
    concurrency_raw = [item[1] for item in fixtures[::4]]
    sequential = [b1.jcs_bytes(rr_api.decide_audited(raw)) for raw in concurrency_raw]
    with ThreadPoolExecutor(max_workers=8) as pool:
        concurrent = list(
            pool.map(lambda raw: b1.jcs_bytes(rr_api.decide_audited(raw)), concurrency_raw)
        )
    check("stateless:threaded-equality", concurrent == sequential)
    reverse = {
        b1.sha256_upper(raw): b1.jcs_bytes(rr_api.decide_audited(raw))
        for raw in reversed(concurrency_raw)
    }
    check(
        "stateless:reverse-interleave",
        all(reverse[b1.sha256_upper(raw)] == expected for raw, expected in zip(concurrency_raw, sequential)),
    )

    return fixtures


def run_benchmark(fixtures: list[tuple[str, bytes, bytes, dict[str, Any]]]) -> None:
    raws = [item[1] for item in fixtures]
    for raw in raws:
        legacy_decide_audited(raw)
        rr_api.decide_audited(raw)

    legacy_samples: list[float] = []
    optimized_samples: list[float] = []
    ratios: list[float] = []
    gc_enabled = gc.isenabled()
    gc.disable()
    try:
        for repetition in range(BENCHMARK_REPETITIONS):
            gc.collect()
            legacy_ns = 0
            optimized_ns = 0
            for index, raw in enumerate(raws):
                for inner_loop in range(BENCHMARK_INNER_LOOPS):
                    order = (legacy_decide_audited, rr_api.decide_audited)
                    if (repetition + index + inner_loop) % 2:
                        order = tuple(reversed(order))
                    for call in order:
                        started = time.perf_counter_ns()
                        call(raw)
                        elapsed = time.perf_counter_ns() - started
                        if call is legacy_decide_audited:
                            legacy_ns += elapsed
                        else:
                            optimized_ns += elapsed
            divisor = len(raws) * BENCHMARK_INNER_LOOPS * 1_000_000
            legacy_ms = legacy_ns / divisor
            optimized_ms = optimized_ns / divisor
            legacy_samples.append(legacy_ms)
            optimized_samples.append(optimized_ms)
            ratios.append(optimized_ms / legacy_ms)
    finally:
        if gc_enabled:
            gc.enable()

    print(
        "benchmark legacy_ms="
        + json.dumps([round(value, 6) for value in legacy_samples])
    )
    print(
        "benchmark optimized_ms="
        + json.dumps([round(value, 6) for value in optimized_samples])
    )
    print("benchmark optimized_over_legacy=" + json.dumps([round(value, 6) for value in ratios]))
    print(
        "benchmark medians "
        f"legacy_ms={statistics.median(legacy_samples):.6f} "
        f"optimized_ms={statistics.median(optimized_samples):.6f} "
        f"ratio={statistics.median(ratios):.6f} "
        f"repetitions={BENCHMARK_REPETITIONS} inner_loops={BENCHMARK_INNER_LOOPS} "
        "note=paired-interleaved-observational"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help=(
            f"also run {BENCHMARK_REPETITIONS} paired/interleaved timing repetitions "
            f"with {BENCHMARK_INNER_LOOPS} inner loops"
        ),
    )
    args = parser.parse_args()
    fixtures = run_equivalence()
    for failure in failures:
        print(failure)
    if failure_count > MAX_FAILURE_DETAILS:
        print(f"FAIL ... {failure_count - MAX_FAILURE_DETAILS} additional details omitted")
    print(
        "single-pass audit equivalence: "
        f"checks={checks} failures={failure_count} "
        f"fixtures={len(fixtures)} fuzz={FUZZ_CASES} "
        f"reference_seed=0x{REFERENCE_SEED:08X} reference_cases={REFERENCE_CASES}"
    )
    if failure_count:
        return 1
    if args.benchmark:
        run_benchmark(fixtures)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
