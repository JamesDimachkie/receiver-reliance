"""Conformance harness for the composed 0.3 implementation.

The accepted 0.2 suite remains intact: semantic (112 byte-exact I/O),
competence (370 mutation relations), wrapper (112 pairs / 224 arms), negative
(10), metamorphic (4), and error_law (78 deterministic closures: 55
parse-layer/limit/canonicality cases, 19 fixture-derived joint-pool,
class-precedence, and family/output-cap cases spanning core,
echo-majority, and wrapper paths, and 4 transcript-evaluator
strictness/totality guards).  The supplemental 0.3 suite adds 12 semantic
entries, 53 competence cases, 24 wrapper arms, 10 negative cases, and 8
metamorphic cases.  Default execution is in-process; --subprocess drives the
pinned CPython 3.12.4 toolchain through the fixed ABI.

Exit 0 only when every executed check passes.
"""

from __future__ import annotations

import argparse
import base64
import copy
import json
import pathlib
import subprocess
import sys
from typing import Any

_MODULE_DIR = pathlib.Path(__file__).resolve().parent
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

import b1_capabilities as b1  # noqa: E402
import pcb_runner  # noqa: E402

BASELINE = _MODULE_DIR.parent
GATE_ROOT = BASELINE.parent
SEMANTIC_PACK_0_2 = BASELINE / "fixtures" / "PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json"
WRAPPER_PACK_0_2 = BASELINE / "fixtures" / "B1_WRAPPER_PARITY_FIXTURE_PACK_0_2.json"
SEMANTIC_PACK_0_3 = (
    GATE_ROOT / "supplemental-0_3" / "fixtures" / "B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json"
)
WRAPPER_PACK_0_3 = (
    GATE_ROOT / "supplemental-0_3" / "fixtures" / "B1_SUPPLEMENTAL_WRAPPER_PARITY_FIXTURE_PACK_0_3.json"
)
TOOLCHAIN = BASELINE / "toolchain" / "python.exe"


class Failure:
    def __init__(self, section: str, case_id: str, detail: str) -> None:
        self.section = section
        self.case_id = case_id
        self.detail = detail

    def __str__(self) -> str:
        return f"[{self.section}] {self.case_id}: {self.detail}"


def execute(raw: bytes, use_subprocess: bool) -> tuple[bytes, int]:
    if use_subprocess:
        proc = subprocess.run(
            [str(TOOLCHAIN), "-I", "-B", str(_MODULE_DIR / "pcb_runner.py"), "execute"],
            input=raw,
            capture_output=True,
            cwd=str(BASELINE),
            check=False,
        )
        if proc.stderr:
            raise RuntimeError(f"nonempty stderr: {proc.stderr[:200]!r}")
        return proc.stdout, proc.returncode
    response, exit_code = pcb_runner._execute(raw)
    return b1.jcs_bytes(response) + b"\n", exit_code


def resolve(document: Any, pointer: str) -> Any:
    node = document
    if pointer == "":
        return node
    for encoded in pointer.lstrip("/").split("/"):
        token = encoded.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def assign(document: Any, pointer: str, value: Any) -> None:
    tokens = [t.replace("~1", "/").replace("~0", "~") for t in pointer.lstrip("/").split("/")]
    node = document
    for token in tokens[:-1]:
        node = node[int(token)] if isinstance(node, list) else node[token]
    last = tokens[-1]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value


def recompute_digests(request: dict[str, Any], recompute: list[str], case: dict[str, Any], failures: list[Failure], cid: str) -> None:
    if "inner_request_raw_sha256" in recompute:
        digest = b1.sha256_upper(b1.jcs_bytes(request["inner_request"]) + b"\n")
        expected = case["mutation"].get("recomputed_inner_request_raw_sha256")
        if expected is not None and digest != expected:
            failures.append(Failure("competence", cid, f"recomputed inner_request digest {digest} != pinned {expected}"))
        request["inner_request_raw_sha256"] = digest
    if "inner_input_sha256" in recompute:
        digest = b1.sha256_upper(b1.jcs_bytes(request["inner_request"]["input"]))
        expected = case["mutation"].get("recomputed_inner_input_sha256")
        if expected is not None and digest != expected:
            failures.append(Failure("competence", cid, f"recomputed inner_input digest {digest} != pinned {expected}"))
        request["inner_input_sha256"] = digest


def run_semantic(pack: dict[str, Any], use_subprocess: bool, failures: list[Failure]) -> int:
    count = 0
    for entry in pack["entries"]:
        cid = entry["entry_id"]
        raw = base64.b64decode(entry["semantic_request_jcs_lf_base64"])
        if b1.sha256_upper(raw) != entry["semantic_request_raw_sha256"]:
            failures.append(Failure("semantic", cid, "fixture request digest mismatch"))
            continue
        expected = base64.b64decode(entry["expected_response_jcs_lf_base64"])
        if b1.sha256_upper(expected) != entry["expected_response_raw_sha256"]:
            failures.append(Failure("semantic", cid, "fixture expected-response digest mismatch"))
            continue
        actual, exit_code = execute(raw, use_subprocess)
        count += 1
        if actual != expected:
            failures.append(Failure("semantic", cid, diff_json(expected, actual)))
            continue
        expected_exit = json.loads(expected)["exit_code"]
        if exit_code != expected_exit:
            failures.append(Failure("semantic", cid, f"exit {exit_code} != {expected_exit}"))
    return count


def diff_json(expected_raw: bytes, actual_raw: bytes) -> str:
    try:
        expected = json.loads(expected_raw)
        actual = json.loads(actual_raw)
    except ValueError:
        return f"undecodable output: {actual_raw[:160]!r}"
    notes = []
    keys = sorted(set(expected) | set(actual)) if isinstance(expected, dict) and isinstance(actual, dict) else []
    for key in keys:
        if expected.get(key) != actual.get(key):
            notes.append(f"{key}: expected {json.dumps(expected.get(key))[:130]} actual {json.dumps(actual.get(key))[:130]}")
    return "; ".join(notes) or f"bytes differ: {actual_raw[:120]!r}"


def apply_competence_mutation(
    request: dict[str, Any],
    mutation: dict[str, Any],
    entries: dict[str, dict[str, Any]],
) -> None:
    """Apply one sealed competence mutation to a semantic request.

    The named 0.3 family operations are fixture-harness instructions, not
    runtime shortcuts: they construct mutated requests, which the runner then
    classifies solely through the frozen predicate tables.
    """
    operation = mutation.get("operation", "")
    if operation == "RENAME_NONAUTHORITATIVE_METADATA_ONLY":
        return
    if operation == "EXCHANGE_AUTHORITATIVE_FACTS_KEEP_LABELS_FIXED":
        target = entries[mutation["target_facts_entry_id"]]
        target_request = json.loads(base64.b64decode(target["semantic_request_jcs_lf_base64"]))
        assign(request, "/decision_input/facts", resolve(target_request, "/decision_input/facts"))
        return

    facts = request["decision_input"]["facts"]
    if operation == "SATISFY_REQUIRED_SET_KEEP_ASKING_ACCOUNTED":
        facts["present_fact_ids"] = ["FACT_R1", "FACT_R2"]
        facts["unresolved_required_fact_ids"] = []
        facts["affordable_covering_query_id"] = None
        facts["unnecessary_query_count"] = 1
        return
    if operation == "SATISFY_REQUIRED_SET_KEEP_ASKING_UNACCOUNTED":
        facts["present_fact_ids"] = ["FACT_R1", "FACT_R2"]
        facts["unresolved_required_fact_ids"] = []
        facts["affordable_covering_query_id"] = None
        return
    if operation == "REASK_ANSWERED_QUERY_IGNORING_INGESTED_ANSWER":
        facts["required_fact_ids"] = ["FACT_R1", "FACT_R2", "FACT_R3"]
        facts["answer_receipts"] = [{
            "query_id": "QRY_A",
            "answered_fact_id": "FACT_R2",
            "receipt_sha256": "A3F1" + "0" * 4 + "B" * 56,
        }]
        facts["answered_fact_ids"] = ["FACT_R2"]
        facts["unresolved_required_fact_ids"] = ["FACT_R3"]
        facts["affordable_covering_query_id"] = "QRY_B"
        facts["asked_query_id"] = "QRY_A"
        facts["asked_addressee_id"] = "ADDR_A"
        facts["asked_query_cost"] = 2
        facts["asked_query_target_fact_id"] = "FACT_R2"
        return
    if operation == "ADMIT_TOP_RANKED_INCOMPATIBLE_RECORD":
        facts["selected_record_ids"] = ["REC_LURE", "REC_A", "REC_B"]
        facts["excluded_records"] = []
        facts["excluded_record_ids"] = []
        return
    if operation == "SHIFT_INTENT_TUPLE_KEEP_STALE_SELECTION":
        facts["intent_purpose_id"] = "PURPOSE_B"
        facts["intent_episode_id"] = "EPISODE_002"
        facts["intent_scope_ref"] = "SCOPE_B"
        facts["intent_version_sha256"] = "D" * 63 + "2"
        facts["compatibility_verdicts"] = [
            {"record_id": "REC_A", "compatible": False},
            {"record_id": "REC_LURE", "compatible": True},
            {"record_id": "REC_B", "compatible": False},
        ]
        facts["compatible_record_ids"] = ["REC_LURE"]
        facts["incompatible_record_ids"] = ["REC_A", "REC_B"]
        facts["excluded_records"] = [
            {"record_id": "REC_LURE", "exclusion_reason": "INTENT_INCOMPATIBLE"}
        ]
        facts["excluded_record_ids"] = ["REC_LURE"]
        facts["misreasoned_excluded_record_ids"] = ["REC_LURE"]
        return
    if operation in (
        "ADD_INCOMPATIBLE_DISTRACTORS_COHERENTLY_EXCLUDED",
        "ABSORB_DISTRACTOR_INTO_SELECTION",
    ):
        digest = "A" * 62 + "55"
        facts["candidate_pool"] = copy.deepcopy(facts["candidate_pool"]) + [
            {
                "record_id": "REC_D1",
                "episode_id": "EPISODE_003",
                "purpose_id": "PURPOSE_C",
                "scope_ref": "SCOPE_C",
                "action_class": "ACTION_CLASS_B",
                "version_sha256": digest,
                "similarity_rank": 4,
            },
            {
                "record_id": "REC_D2",
                "episode_id": "EPISODE_004",
                "purpose_id": "PURPOSE_D",
                "scope_ref": "SCOPE_D",
                "action_class": "ACTION_CLASS_B",
                "version_sha256": digest,
                "similarity_rank": 5,
            },
        ]
        facts["pool_record_ids"] = ["REC_A", "REC_LURE", "REC_B", "REC_D1", "REC_D2"]
        facts["compatibility_verdicts"] = copy.deepcopy(facts["compatibility_verdicts"]) + [
            {"record_id": "REC_D1", "compatible": False},
            {"record_id": "REC_D2", "compatible": False},
        ]
        facts["incompatible_record_ids"] = ["REC_LURE", "REC_D1", "REC_D2"]
        facts["excluded_records"] = [
            {"record_id": "REC_LURE", "exclusion_reason": "INTENT_INCOMPATIBLE"},
            {"record_id": "REC_D1", "exclusion_reason": "INTENT_INCOMPATIBLE"},
            {"record_id": "REC_D2", "exclusion_reason": "INTENT_INCOMPATIBLE"},
        ]
        facts["excluded_record_ids"] = ["REC_LURE", "REC_D1", "REC_D2"]
        if operation == "ABSORB_DISTRACTOR_INTO_SELECTION":
            facts["selected_record_ids"] = ["REC_A", "REC_B", "REC_D1"]
            facts["excluded_records"] = [
                {"record_id": "REC_LURE", "exclusion_reason": "INTENT_INCOMPATIBLE"},
                {"record_id": "REC_D2", "exclusion_reason": "INTENT_INCOMPATIBLE"},
            ]
            facts["excluded_record_ids"] = ["REC_LURE", "REC_D2"]
        return

    before = mutation.get("before")
    if before is not None and resolve(request, mutation["pointer"]) != before:
        raise ValueError("mutation precondition mismatch")
    assign(request, mutation["pointer"], mutation["after"])


def run_competence(pack: dict[str, Any], use_subprocess: bool, failures: list[Failure]) -> int:
    entries = {entry["entry_id"]: entry for entry in pack["entries"]}
    count = 0
    for case in pack["competence_cases"]:
        cid = f'{case["rule_id"]}/{case["base_entry_id"]}'
        base = entries[case["base_entry_id"]]
        request = json.loads(base64.b64decode(base["semantic_request_jcs_lf_base64"]))
        mutation = case["mutation"]
        try:
            apply_competence_mutation(request, mutation, entries)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            failures.append(Failure("competence", cid, str(exc)))
            continue
        recompute_digests(request, mutation.get("recompute", []), case, failures, cid)
        raw = b1.jcs_bytes(request) + b"\n"
        actual, exit_code = execute(raw, use_subprocess)
        count += 1
        relation = case.get("required_relation")
        expected_sha = case.get("expected_response_raw_sha256")
        actual_sha = b1.sha256_upper(actual)
        actual_obj = json.loads(actual)
        if relation in (
            "BYTE_IDENTICAL",
            "SEMANTIC_CLASS_TRANSITION",
            "OUTPUT_FOLLOWS_FACTS",
            "RESPONSE_BYTES_IDENTICAL_UNDER_DISTRACTOR_ADDITION",
        ):
            if expected_sha is not None and actual_sha != expected_sha:
                failures.append(Failure("competence", cid, f"{relation}: response digest {actual_sha} != {expected_sha}; {summ(actual_obj)}"))
                continue
            expected_class = case.get("expected_behavior_class")
            if expected_class is not None:
                got = ((actual_obj.get("output") or {}).get("result_object") or {}).get("behavior_class")
                if got != expected_class:
                    failures.append(Failure("competence", cid, f"class {got} != {expected_class}"))
        elif relation == "ERR_SCHEMA_NO_CLASSIFICATION" or relation is None:
            if expected_sha is not None:
                if actual_sha != expected_sha:
                    failures.append(Failure("competence", cid, f"error digest {actual_sha} != {expected_sha}; {summ(actual_obj)}"))
                    continue
            errors = actual_obj.get("errors") or []
            if actual_obj.get("output") is not None or not errors or errors[0].get("code") != "ERR_SCHEMA" or exit_code != 2:
                failures.append(Failure("competence", cid, f"expected ERR_SCHEMA/no output/exit2, got {summ(actual_obj)} exit {exit_code}"))
        else:
            failures.append(Failure("competence", cid, f"unknown relation {relation}"))
    return count


def summ(obj: dict[str, Any]) -> str:
    errors = obj.get("errors") or []
    if errors:
        return f"errors[0]={errors[0].get('code')}@{errors[0].get('pointer')!r}"
    ro = ((obj.get("output") or {}).get("result_object")) or ((obj.get("output") or {}).get("payload")) or {}
    return f"class={ro.get('behavior_class')} conclusion={ro.get('conclusion')}"


def wrapper_normalized_projection(response: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in response.items() if k not in ("configuration", "response_sha256")}


def run_wrapper(pack: dict[str, Any], use_subprocess: bool, failures: list[Failure]) -> int:
    count = 0
    for pair in pack["pairs"]:
        pid = pair["pair_id"]
        arm_requests = {}
        for arm_name in ("b1_arm", "b1_attention_arm"):
            arm = pair[arm_name]
            cid = f"{pid}/{arm_name}"
            request_raw = base64.b64decode(arm["request_jcs_lf_base64"])
            response_raw = base64.b64decode(arm["response_jcs_lf_base64"])
            if b1.sha256_upper(request_raw) != arm["request_raw_sha256"]:
                failures.append(Failure("wrapper", cid, "fixture request digest mismatch"))
                continue
            if b1.sha256_upper(response_raw) != arm["response_raw_sha256"]:
                failures.append(Failure("wrapper", cid, "fixture response digest mismatch"))
                continue
            actual, exit_code = execute(request_raw, use_subprocess)
            count += 1
            if actual != response_raw:
                failures.append(Failure("wrapper", cid, diff_json(response_raw, actual)))
                continue
            expected_exit = json.loads(response_raw)["exit_code"]
            if exit_code != expected_exit:
                failures.append(Failure("wrapper", cid, f"exit {exit_code} != {expected_exit}"))
                continue
            ok, _ = b1.validate_wrapper_transcript_binding(request_raw, actual, arm["transcript"])
            if not ok:
                failures.append(Failure("wrapper", cid, "transcript binding evaluator rejected recorded triple"))
                continue
            response_obj = json.loads(actual)
            normalized = b1.sha256_upper(b1.jcs_bytes(wrapper_normalized_projection(response_obj)))
            if normalized != arm["normalized_output_sha256"]:
                failures.append(Failure("wrapper", cid, f"normalized output digest {normalized} != {arm['normalized_output_sha256']}"))
            arm_requests[arm_name] = json.loads(request_raw)
        if len(arm_requests) == 2:
            left = b1.jcs_bytes(b1.shared_wrapper_request_projection(arm_requests["b1_arm"]))
            right = b1.jcs_bytes(b1.shared_wrapper_request_projection(arm_requests["b1_attention_arm"]))
            if left != right:
                failures.append(Failure("wrapper", pid, "sole-delta violation: shared projections differ"))
            if pair["b1_arm"]["normalized_output_sha256"] != pair["b1_attention_arm"]["normalized_output_sha256"]:
                failures.append(Failure("wrapper", pid, "arm normalized outputs differ"))
    return count


def run_negative(pack: dict[str, Any], semantic: dict[str, Any], use_subprocess: bool, failures: list[Failure]) -> int:
    pairs_by_entry = {pair["core_entry_id"]: pair for pair in pack["pairs"]}
    count = 0
    for case in pack["negative_cases"]:
        cid = case["negative_case_id"]
        layer = case["expected_evaluation_layer"]
        mutation = case["mutation"]
        count += 1
        try:
            pair = json.loads(json.dumps(pairs_by_entry[case["base_entry_id"]]))
            if layer == "WRAPPER_PACK_PAIR_CARDINALITY":
                removed = mutation.get("removed_arm") or mutation.get("pointer", "/b1_attention_arm").lstrip("/")
                pair.pop(removed, None)
                if "b1_arm" in pair and "b1_attention_arm" in pair:
                    failures.append(Failure("negative", cid, "missing arm not detected"))
                continue
            # Mutation pointers are rooted at the pair (/b1_arm/..., /b1_attention_arm/...)
            # or at the b1 arm (/wrapper_request/..., /transcript/...).
            pointer = mutation["pointer"]
            if pointer.startswith("/b1_arm") or pointer.startswith("/b1_attention_arm"):
                arm_name = pointer.lstrip("/").split("/")[0]
                arm_pointer = pointer[len("/" + arm_name):]
            else:
                arm_name, arm_pointer = "b1_arm", pointer
            arm = pair[arm_name]
            if mutation.get("operation") == "REORDER_ONE_ARMS_CANDIDATE_QUERY_POOL":
                current = resolve(arm, arm_pointer)
                if mutation.get("before") != list(range(len(current))):
                    failures.append(Failure("negative", cid, f"mutation precondition mismatch at {pointer}"))
                    continue
                assign(arm, arm_pointer, [current[index] for index in mutation["after"]])
            else:
                before = mutation.get("before")
                if before is not None and resolve(arm, arm_pointer) != before:
                    failures.append(Failure("negative", cid, f"mutation precondition mismatch at {pointer}"))
                    continue
                assign(arm, arm_pointer, mutation["after"])
            if layer == "WRAPPER_ARM_PARITY_BYTE_IDENTITY":
                left = b1.jcs_bytes(
                    b1.shared_wrapper_request_projection(pair["b1_arm"]["wrapper_request"])
                )
                right = b1.jcs_bytes(
                    b1.shared_wrapper_request_projection(
                        pair["b1_attention_arm"]["wrapper_request"]
                    )
                )
                if left == right:
                    failures.append(Failure("negative", cid, "arm divergence was not detected"))
                continue
            request_raw = b1.jcs_bytes(arm["wrapper_request"]) + b"\n"
            if "TRANSCRIPT" in layer:
                response_raw = base64.b64decode(arm["response_jcs_lf_base64"])
                ok, _ = b1.validate_wrapper_transcript_binding(request_raw, response_raw, arm["transcript"])
                if ok:
                    failures.append(Failure("negative", cid, f"{case['case_name']}: binding evaluator accepted mutated triple"))
            elif layer == "SEMANTIC_PREDICATE_MALFORMED_OR_BOUNDARY":
                actual, exit_code = execute(request_raw, use_subprocess)
                obj = json.loads(actual)
                got = ((obj.get("output") or {}).get("payload") or {}).get("behavior_class")
                if got != "MALFORMED_OR_BOUNDARY" or exit_code != 1:
                    failures.append(Failure("negative", cid, f"{case['case_name']}: expected MALFORMED_OR_BOUNDARY exit1, got {summ(obj)} exit {exit_code}"))
            else:
                actual, exit_code = execute(request_raw, use_subprocess)
                obj = json.loads(actual)
                errors = obj.get("errors") or []
                if not errors or errors[0].get("code") != "ERR_SCHEMA" or exit_code != 2:
                    failures.append(Failure("negative", cid, f"{case['case_name']}: expected ERR_SCHEMA exit2, got {summ(obj)} exit {exit_code}"))
        except Exception as exc:  # noqa: BLE001 - report as finding, keep sweeping
            failures.append(Failure("negative", cid, f"harness error: {exc}; mutation={json.dumps(mutation)[:220]}"))
    return count


def run_metamorphic(pack: dict[str, Any], semantic: dict[str, Any], use_subprocess: bool, failures: list[Failure]) -> int:
    comp_by_sha = {case["case_sha256"]: case for case in semantic["competence_cases"]}
    entries = {entry["entry_id"]: entry for entry in semantic["entries"]}
    pairs = {pair["pair_id"]: pair for pair in pack["pairs"]}
    count = 0
    for case in pack["metamorphic_cases"]:
        cid = case["metamorphic_case_id"]
        count += 1
        comp = comp_by_sha.get(case["core_competence_case_sha256"])
        if comp is None:
            failures.append(Failure("metamorphic", cid, "referenced competence case not found"))
            continue
        pair = pairs[case["base_pair_id"]]
        relation = case["expected_relation"]
        for arm_name in ("b1_arm", "b1_attention_arm"):
            arm = pair[arm_name]
            request = json.loads(base64.b64decode(arm["request_jcs_lf_base64"]))
            mutation = comp["mutation"]
            sem = request["semantic_request"]
            try:
                apply_competence_mutation(sem, mutation, entries)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                failures.append(Failure("metamorphic", f"{cid}/{arm_name}", str(exc)))
                continue
            for field in mutation.get("recompute", []):
                if field == "inner_request_raw_sha256":
                    sem["inner_request_raw_sha256"] = b1.sha256_upper(
                        b1.jcs_bytes(sem["inner_request"]) + b"\n"
                    )
                if field == "inner_input_sha256":
                    sem["inner_input_sha256"] = b1.sha256_upper(
                        b1.jcs_bytes(sem["inner_request"]["input"])
                    )
            raw = b1.jcs_bytes(request) + b"\n"
            actual, _ = execute(raw, use_subprocess)
            original = base64.b64decode(arm["response_jcs_lf_base64"])
            if relation in (
                "BYTE_IDENTICAL",
                "RESPONSE_BYTES_IDENTICAL_UNDER_DISTRACTOR_ADDITION",
            ):
                if actual != original:
                    failures.append(Failure("metamorphic", f"{cid}/{arm_name}", diff_json(original, actual)))
            else:
                obj = json.loads(actual)
                got = ((obj.get("output") or {}).get("payload") or {}).get("behavior_class")
                expected_class = comp.get("expected_behavior_class")
                if relation == "CLASS_AND_SEALS_CHANGE" and actual == original:
                    failures.append(Failure("metamorphic", f"{cid}/{arm_name}", "response unchanged under semantic mutation"))
                elif expected_class is not None and got != expected_class:
                    failures.append(Failure("metamorphic", f"{cid}/{arm_name}", f"class {got} != {expected_class}"))
    return count


def _nfd(text: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFD", text)


def error_law_cases() -> list[tuple[str, bytes, str, str]]:
    """Pairwise error-combination closure for the deterministic error law.

    Law: one error, selected by ARG_MIN(precedence, UTF-8 pointer) over all
    DETECTED errors. Documented exemptions, each basis-pinned: (1) the
    pre-decode gates run in packet order — empty, byte-oversize, UTF-8, BOM
    — before anything else is detectable (packet parse_rules: "Reject input
    exceeding 16777216 bytes before decode"); (2) an undecodable body
    suppresses walk-level detectors (NFC, range, structural limits,
    canonical bytes) but not hook-level flags (duplicate key, number model);
    (3) the full schema walk runs only for dispatchable requests — every
    parse-layer error below precedence 80 outranks every schema error, and
    only the O(1) dispatch detections (non-object root, unknown
    format_version) compete alongside them. Structural resource limits (90)
    are packet-pinned but DO pool with the full schema walk (round-5
    DIV-003), and canonical-byte checking preserves number lexemes verbatim
    so ERR_JSON arises only from violations independent of the number model
    (round-5 DIV-002). Every case below is (name, input, expected_code,
    expected_pointer)."""
    nfd_key = _nfd("é")  # 'e' + U+0301, non-NFC
    big_items = b"[" + (b"0," * 100000) + b"0]\n"  # 100,001 items
    big_dup = b"{" + b",".join(b'"k%06d":0' % i for i in range(100001)) + b"}\n"
    cases: list[tuple[str, bytes, str, str]] = [
        # pre-decode gates (exemption 1)
        ("empty-input", b"", "ERR_EMPTY_INPUT", ""),
        ("lf-only", b"\n", "ERR_EMPTY_INPUT", ""),
        ("oversize-beats-bom", b"\xef\xbb\xbf" + b"0" * b1.MAX_INPUT_BYTES, "ERR_LIMIT", ""),
        ("utf8-beats-bom", b"\xef\xbb\xbf{\xff}\n", "ERR_UTF8", ""),
        ("utf8-beats-dup", b'{"a":1,"a":2,"b":"\xff"}\n', "ERR_UTF8", ""),
        ("bom-beats-dup", "﻿{\"a\":1,\"a\":2}\n".encode(), "ERR_BOM", ""),
        ("bom-beats-json", "﻿{\n".encode(), "ERR_BOM", ""),
        # duplicate key (40) vs everything above it
        ("dup-beats-trailing", b'{"a":1,"a":2}x\n', "ERR_DUPLICATE_KEY", ""),
        ("dup-beats-noLF", b'{"a":1,"a":2}', "ERR_DUPLICATE_KEY", ""),
        ("dup-beats-noncanonical", b'{"b":1,"a":1,"a":2}\n', "ERR_DUPLICATE_KEY", ""),
        ("dup-inner-beats-abort", b'{"x":{"a":1,"a":2},\n', "ERR_DUPLICATE_KEY", ""),
        ("dup-beats-nfc", ('{"a":1,"a":2,"' + nfd_key + '":3}\n').encode(), "ERR_DUPLICATE_KEY", ""),
        ("dup-beats-float", b'{"a":1.0,"a":2}\n', "ERR_DUPLICATE_KEY", ""),
        ("dup-beats-neg-zero", b'{"a":-0,"a":2}\n', "ERR_DUPLICATE_KEY", ""),
        ("dup-beats-schema-root", b'[{"a":1,"a":2}]\n', "ERR_DUPLICATE_KEY", ""),
        ("dup-beats-member-limit", b'{"a":1,"a":2,' + big_dup[1:], "ERR_DUPLICATE_KEY", ""),
        # ERR_JSON (50) vs higher
        ("json-undecodable-beats-nfc", ('{"' + nfd_key + '":1}x\n').encode(), "ERR_JSON", ""),
        ("json-framing-beats-nfc", ('{"' + nfd_key + '":1}').encode(), "ERR_JSON", ""),
        ("json-noncanonical-beats-nfc", ('{"x":"' + nfd_key + '", "a":1}\n').encode(), "ERR_JSON", ""),
        ("json-framing-beats-number", b'{"a":-0}', "ERR_JSON", ""),
        ("json-noncanonical-beats-range", b'{"b":1,"a":99999999999999999999}\n', "ERR_JSON", ""),
        ("json-framing-beats-schema-root", b"[1]", "ERR_JSON", ""),
        ("json-framing-beats-item-limit", big_items[:-1], "ERR_JSON", ""),
        ("json-noncanonical-beats-item-limit", b"[ " + big_items[1:], "ERR_JSON", ""),
        # ERR_NFC (60) vs higher
        ("nfc-beats-float", ('{"' + nfd_key + '":1.0}\n').encode(), "ERR_NFC", "/" + nfd_key),
        ("nfc-beats-schema-root", ('["' + nfd_key + '"]\n').encode(), "ERR_NFC", "/0"),
        ("nfc-tie-lowest-pointer", ('{"' + nfd_key + 'a":1,"' + nfd_key + 'b":2}\n').encode(), "ERR_NFC", "/" + nfd_key + "a"),
        # ERR_NUMBER (70) vs higher — pointered per the ARG_MIN law
        # (round-7 R7-DIV-002: hook-level violations carry exact pointers)
        ("number-beats-schema-root", b"[-0]\n", "ERR_NUMBER", "/0"),
        ("number-range-beats-schema-root", b"[99999999999999999999]\n", "ERR_NUMBER", "/0"),
        ("number-beats-item-limit", b"[-0," + big_items[1:], "ERR_NUMBER", "/0"),
        # ERR_SCHEMA O(1) (80) vs ERR_LIMIT structural (90)
        ("schema-root-beats-item-limit", big_items, "ERR_SCHEMA", ""),
        ("schema-format-beats-member-limit", b'{"format_version":"X",' + big_dup[1:], "ERR_SCHEMA", "/format_version"),
        ("schema-root-beats-nesting-limit", b"[" * 130 + b"0" + b"]" * 130 + b"\n", "ERR_SCHEMA", ""),
        # structural limits pool WITH the full schema walk on dispatchable
        # requests: schema (80) outranks resource limit (90) (round-5 DIV-003)
        ("schema-beats-member-limit-flat",
         (b'{"format_version":"B1-SEMANTIC-DECISION-REQUEST-0.2",' + big_dup[1:]),
         "ERR_SCHEMA", ""),
        ("schema-beats-item-limit-nested",
         b'{"format_version":"B1-SEMANTIC-DECISION-REQUEST-0.2","x":' + big_items[:-1] + b"}\n",
         "ERR_SCHEMA", ""),
        ("schema-beats-nesting-limit",
         b'{"format_version":"B1-SEMANTIC-DECISION-REQUEST-0.2","x":'
         + b'{"a":' * 129 + b"0" + b"}" * 129 + b"}\n",
         "ERR_SCHEMA", ""),
        # ERR_JSON (50) vs ERR_NUMBER (70): canonicality is judged with
        # number lexemes verbatim, so only violations INDEPENDENT of the
        # number model produce ERR_JSON (round-5 DIV-002)
        ("json-keyorder-beats-float", b'{"b":1.0,"a":2}\n', "ERR_JSON", ""),
        ("json-whitespace-beats-negzero", b'{"a": -0}\n', "ERR_JSON", ""),
        ("negzero-alone-stays-number", b'{"a":-0}\n', "ERR_NUMBER", "/a"),
        ("exponent-alone-stays-number", b'{"a":1e0}\n', "ERR_NUMBER", "/a"),
        # round-6 closures: escaped lone-surrogate keys, recursion-abort
        # pooling, and the interpreter integer-digit cap (R6-001/002/003)
        ("surrogate-dup-key-beats-json", b'{"\\ud800":0,"\\ud800":1}\n', "ERR_DUPLICATE_KEY", ""),
        ("surrogate-key-alone-is-json", b'{"\\ud800":0}\n', "ERR_JSON", ""),
        ("json-framing-beats-recursion-limit", b"[" * 5000 + b"0" + b"]" * 5000, "ERR_JSON", ""),
        ("dup-beats-recursion-limit",
         b'[{"a":0,"a":1},' + b"[" * 5000 + b"0" + b"]" * 5000 + b"]\n",
         "ERR_DUPLICATE_KEY", ""),
        ("recursion-limit-alone", b"[" * 5000 + b"0" + b"]" * 5000 + b"\n", "ERR_LIMIT", ""),
        ("int-digit-cap-is-number", b"1" * 5000 + b"\n", "ERR_NUMBER", ""),
        ("int-digit-cap-negative-is-number", b"-" + b"1" * 5000 + b"\n", "ERR_NUMBER", ""),
        # round-7 closures: pointer-accurate hook detections and
        # depth-immune profile scanning (R7-DIV-002/003)
        ("digit-cap-nested-pointer",
         b'{"a":[' + b"1" * 5000 + b'],"format_version":"B1-SEMANTIC-DECISION-REQUEST-0.2"}\n',
         "ERR_NUMBER", "/a/0"),
        ("json-keyorder-beats-recursion-limit",
         b'{"a":{"z":0,"a":1},"b":' + b"[" * 5000 + b"0" + b"]" * 5000 + b"}\n",
         "ERR_JSON", ""),
        ("nfc-beats-recursion-limit",
         b'{"a":{"x":"e\xcc\x81"},"b":' + b"[" * 5000 + b"0" + b"]" * 5000 + b"}\n",
         "ERR_NFC", "/a/x"),
        ("surrogate-beats-recursion-limit",
         b'{"a":"\\ud800","b":' + b"[" * 5000 + b"0" + b"]" * 5000 + b"}\n",
         "ERR_JSON", ""),
        # round-8 closure: pointered detections BENEATH a lone-surrogate key
        # must stay orderable during selection; the canonical ERR_JSON the
        # surrogate forces always wins (R8-DIV-001)
        ("surrogate-key-float-value", b'{"\\ud800":1.0}\n', "ERR_JSON", ""),
        ("surrogate-key-negzero-value", b'{"\\ud800":-0}\n', "ERR_JSON", ""),
        ("surrogate-key-nfd-value", b'{"\\ud800":"e\xcc\x81"}\n', "ERR_JSON", ""),
        ("surrogate-key-dup-float", b'{"\\ud800":1.0,"\\ud800":2.0}\n', "ERR_DUPLICATE_KEY", ""),
    ]
    return cases


def error_pool_cases(
    semantic: dict[str, Any], wrapper: dict[str, Any]
) -> list[tuple[str, bytes, str, str, str | None]]:
    """Schema-x-binding joint-pool closure (terminal acceptance finding
    B1-IMPL-DIV-001): a combinator-site schema error ("" / "/decision_input")
    is suppressed only when it is an echo of the binding-blamed selector
    inconsistency; independent violations compete under ARG_MIN(precedence,
    UTF-8 pointer). Cases mutate one pinned OBL-01 entry; digest fields stay
    valid unless the case changes them. The optional fifth element pins the
    exact expected stdout SHA-256 (error responses depend only on code,
    pointer, and request_id, so cases sharing those share bytes)."""
    entry = next(
        e for e in semantic["entries"] if e["entry_id"] == "SEMFX-OBL-01-IO-638822AAD3E2B835"
    )

    def request() -> dict[str, Any]:
        return json.loads(base64.b64decode(entry["semantic_request_jcs_lf_base64"]))

    def raw_bytes(mutated: dict[str, Any]) -> bytes:
        return b1.jcs_bytes(mutated) + b"\n"

    wrong_digest = "A" * 64
    schema_at_decision_input = "A34EC8A47F088D1EE58343DF1394F01E569DE6900CEBDF5165A070E630479976"
    schema_at_inner_input = "78A130D345003B7080EDE27A92197423BD1B4E52339F0F1D52941760CCE62EDD"

    cases: list[tuple[str, bytes, str, str, str | None]] = []
    r = request()
    r["decision_input"]["facts"]["purpose_ids"] = "PURPOSE_A"
    cases.append(("pool-shape-alone", raw_bytes(r),
                  "ERR_SCHEMA", "/decision_input", schema_at_decision_input))
    r = request()
    r["decision_input"]["facts"]["purpose_ids"] = "PURPOSE_A"
    r["inner_input_sha256"] = b1.ZERO64
    cases.append(("pool-shape-beats-zero-digest", raw_bytes(r),
                  "ERR_SCHEMA", "/decision_input", schema_at_decision_input))
    r = request()
    r["decision_input"]["facts"]["purpose_ids"] = "PURPOSE_A"
    r["inner_input_sha256"] = wrong_digest
    cases.append(("pool-shape-beats-wrong-digest", raw_bytes(r),
                  "ERR_SCHEMA", "/decision_input", schema_at_decision_input))
    r = request()
    r["inner_input_sha256"] = wrong_digest
    cases.append(("pool-digest-alone", raw_bytes(r),
                  "ERR_SCHEMA", "/inner_input_sha256", schema_at_inner_input))
    r = request()
    r["obligation_id"] = "OBL-02"
    cases.append(("pool-correspondence-echo-suppressed", raw_bytes(r),
                  "ERR_SCHEMA", "/obligation_id", None))
    r = request()
    r["decision_input"]["facts"]["purpose_ids"] = "PURPOSE_A"
    r["obligation_id"] = "OBL-02"
    cases.append(("pool-shape-beats-correspondence", raw_bytes(r),
                  "ERR_SCHEMA", "/decision_input", schema_at_decision_input))
    r = request()
    r["obligation_id"] = "OBL-02"
    r["inner_input_sha256"] = wrong_digest
    cases.append(("pool-digest-beats-correspondence", raw_bytes(r),
                  "ERR_SCHEMA", "/inner_input_sha256", schema_at_inner_input))
    r = request()
    r["decision_input"]["obligation_id"] = "OBL-02"
    cases.append(("pool-inner-selector-echo-suppressed", raw_bytes(r),
                  "ERR_SCHEMA", "/decision_input/obligation_id", None))

    # Round-5 DIV-004, adjudicated: the accepted pack pins majority
    # (deviant-blaming) echo judgment — SEM-COMP-05's outer-operation
    # mutation pins '/operation_handle' — so the anchor-on-outer reading is
    # pack-contradicted. Ties, which the pack leaves free, prefer the outer
    # operation_handle's row per the contract's registry-resolution prose.
    registry = b1.operation_registry()
    handle_20 = next(h for h in sorted(registry) if registry[h] == "OBL-20")
    handle_21 = next(h for h in sorted(registry) if registry[h] == "OBL-21")
    entry_19 = next(
        e for e in semantic["entries"] if e["entry_id"] == "SEMFX-OBL-19-IO-90CA7FDF4C31099D"
    )

    def request_19() -> dict[str, Any]:
        return json.loads(base64.b64decode(entry_19["semantic_request_jcs_lf_base64"]))

    r = request_19()
    r["obligation_id"] = "OBL-20"
    r["decision_input"]["obligation_id"] = "OBL-20"
    r["decision_input"]["operation_handle"] = handle_20
    r["inner_request"]["operation_handle"] = handle_20
    r["inner_request_raw_sha256"] = b1.sha256_upper(b1.jcs_bytes(r["inner_request"]) + b"\n")
    cases.append(("pool-four-echoes-moved-di-shape-survives", raw_bytes(r),
                  "ERR_SCHEMA", "/decision_input", None))
    r = request_19()
    r["decision_input"]["operation_handle"] = handle_20
    r["inner_request"]["operation_handle"] = handle_20
    r["inner_request_raw_sha256"] = b1.sha256_upper(b1.jcs_bytes(r["inner_request"]) + b"\n")
    cases.append(("pool-minority-operation-echoes", raw_bytes(r),
                  "ERR_SCHEMA", "/decision_input/operation_handle", None))
    r = request_19()
    r["decision_input"]["operation_handle"] = handle_20
    r["decision_input"]["obligation_id"] = "OBL-20"
    r["inner_request"]["operation_handle"] = handle_21
    r["inner_request_raw_sha256"] = b1.sha256_upper(b1.jcs_bytes(r["inner_request"]) + b"\n")
    cases.append(("pool-tie-prefers-outer-row", raw_bytes(r),
                  "ERR_SCHEMA", "/decision_input/obligation_id", None))

    # Round-5 DIV-005: wrapper semantic-subtree failures carry the semantic
    # joint pool's pointers under the /semantic_request prefix instead of
    # the wrapper schema's combinator site.
    pair = next(
        p for p in wrapper["pairs"] if p["pair_id"] == "WPAIR_3FE57841D5C819EF8542267D"
    )

    def wrapper_request() -> dict[str, Any]:
        return json.loads(base64.b64decode(pair["b1_arm"]["request_jcs_lf_base64"]))

    w = wrapper_request()
    w["semantic_request"]["obligation_id"] = "OBL-20"
    cases.append(("wrapper-pool-selector-echo", raw_bytes(w),
                  "ERR_SCHEMA", "/semantic_request/obligation_id", None))
    w = wrapper_request()
    w["semantic_request"]["obligation_id"] = "OBL-20"
    w["semantic_request"]["!"] = 0
    cases.append(("wrapper-pool-root-extra", raw_bytes(w),
                  "ERR_SCHEMA", "/semantic_request/!", None))
    w = wrapper_request()
    w["semantic_request"]["inner_input_sha256"] = "A" * 64
    cases.append(("wrapper-pool-binding-digest", raw_bytes(w),
                  "ERR_SCHEMA", "/semantic_request/inner_input_sha256", None))

    # Round-7 R7-DIV-001: class evaluation short-circuits at the first
    # match — later predicates never run (their operators may be non-total
    # on requests an earlier class already resolved).
    entry_28 = next(
        e for e in semantic["entries"] if e["entry_id"] == "SEMFX-OBL-28-IO-7D0070B2EFE31FCF"
    )

    def request_28() -> dict[str, Any]:
        return json.loads(base64.b64decode(entry_28["semantic_request_jcs_lf_base64"]))

    def find_base64_path(node: Any) -> str | None:
        if isinstance(node, dict):
            if "base64_path" in node:
                return node["base64_path"]
            for child in node.values():
                found = find_base64_path(child)
                if found is not None:
                    return found
        if isinstance(node, list):
            for child in node:
                found = find_base64_path(child)
                if found is not None:
                    return found
        return None

    b64_path = find_base64_path(b1.decision_table()[request_28()["operation_handle"]])
    r = request_28()
    assign(r["decision_input"], b64_path, "Zh==")
    cases.append(("class-precedence-noncanonical-base64", raw_bytes(r),
                  "CLASS:MALFORMED_OR_BOUNDARY", "",
                  "0EDDECAFD030EA8A7E6F9ACC110F50727C3009261DF13A38E3E4AEB3B766A758"))
    r = request_28()
    assign(r["decision_input"], b64_path, None)
    cases.append(("class-precedence-null-base64", raw_bytes(r),
                  "CLASS:BINDING_OR_CONFLICT", "",
                  "8DBE99869AE4BCFE28E0025C3EDA944D19E17E224AEA8602340686D12DB34217"))

    # Round-9 closures: the recognized response family and the output cap
    # survive every failure path (R9-DIV-001/002/003).
    w = {
        "attention_card": None,
        "budget": 1,
        "clarification_state": "NONE",
        "configuration": "B1",
        "format_version": "B1-WRAPPER-SEMANTIC-REQUEST-0.2",
        "operation_handle": [],
        "pause_state": "READY",
        "request_id": "RUN_000000000000000000000000",
        "semantic_request": {},
    }
    cases.append(("wrapper-family-invalid-selector", raw_bytes(w),
                  "ERR_SCHEMA", "/operation_handle", None))
    giant_wrapper = {
        "!" * 16777158: 0,
        "format_version": "B1-WRAPPER-SEMANTIC-REQUEST-0.2",
    }
    cases.append(("wrapper-family-output-limit", raw_bytes(giant_wrapper),
                  "ERR_LIMIT", "",
                  "3E03950F91E9AFEF7272B88F1A141E759DD0A4B5C7E42FB0B8263CFA738C914C"))
    r = json.loads(base64.b64decode(semantic["entries"][0]["semantic_request_jcs_lf_base64"]))
    r["/" * 8388441] = 0
    cases.append(("core-output-cap-bounded", raw_bytes(r), "ERR_LIMIT", "", None))
    return cases


def run_error_law(
    semantic: dict[str, Any],
    wrapper: dict[str, Any],
    use_subprocess: bool,
    failures: list[Failure],
) -> int:
    count = 0
    all_cases: list[tuple] = list(error_law_cases()) + list(error_pool_cases(semantic, wrapper))
    for case in all_cases:
        name, raw, want_code, want_pointer = case[0], case[1], case[2], case[3]
        want_sha = case[4] if len(case) > 4 else None
        count += 1
        try:
            actual, exit_code = execute(raw, use_subprocess)
            obj = json.loads(actual)
            errors = obj.get("errors") or []
            code = errors[0].get("code") if errors else None
            pointer = errors[0].get("pointer") if errors else None
            receipt_field = "receipt_sha256" if "receipt_sha256" in obj else "response_sha256"
            zeroed = dict(obj)
            zeroed[receipt_field] = "0" * 64
            seal_ok = obj[receipt_field] == b1.sha256_upper(b1.jcs_bytes(zeroed))
            if name.startswith("wrapper-") and obj.get("format_version") != b1.WRAPPER_RESPONSE_FORMAT:
                failures.append(Failure(
                    "error_law", name,
                    f"response family {obj.get('format_version')!r} is not the wrapper family"))
                continue
            if want_code.startswith("CLASS:"):
                # Classified-response expectation (round-7 R7-DIV-001):
                # exit 1, no errors, sealed, exact behavior class.
                want_class = want_code[len("CLASS:"):]
                got_class = ((obj.get("output") or {}).get("result_object") or {}).get("behavior_class")
                if errors or got_class != want_class or exit_code != 1 or not seal_ok:
                    failures.append(Failure(
                        "error_law", name,
                        f"expected class {want_class} exit1 sealed; got {summ(obj)} exit {exit_code} seal_ok={seal_ok}"))
                elif want_sha is not None and b1.sha256_upper(actual) != want_sha:
                    failures.append(Failure(
                        "error_law", name,
                        f"stdout digest {b1.sha256_upper(actual)} != pinned {want_sha}"))
            elif code != want_code or pointer != want_pointer or exit_code != 2 or not seal_ok:
                failures.append(Failure(
                    "error_law", name,
                    f"expected {want_code}@{want_pointer!r} exit2 sealed; got {code}@{pointer!r} exit {exit_code} seal_ok={seal_ok}"))
            elif want_sha is not None and b1.sha256_upper(actual) != want_sha:
                failures.append(Failure(
                    "error_law", name,
                    f"stdout digest {b1.sha256_upper(actual)} != pinned {want_sha}"))
        except Exception as exc:  # noqa: BLE001 - report as finding, keep sweeping
            failures.append(Failure("error_law", name, f"harness error: {exc}"))

    # Round-7 R7-DIV-004 guards: the wrapper transcript-binding evaluator
    # must strict-parse recorded wire bytes (duplicate-key smuggling is a
    # rejection) and stay total on adversarial depth (no leaked exception).
    pair = next(p for p in wrapper["pairs"] if p["pair_id"] == "WPAIR_4A8FA235811D2D684796E573")
    arm = pair["b1_arm"]
    request_raw = base64.b64decode(arm["request_jcs_lf_base64"])
    response_raw = base64.b64decode(arm["response_jcs_lf_base64"])

    def rebound(new_request: bytes, new_response: bytes) -> dict[str, Any]:
        record = json.loads(json.dumps(arm["transcript"]))
        record["request_raw_sha256"] = b1.sha256_upper(new_request)
        record["response_raw_sha256"] = b1.sha256_upper(new_response)
        record["record_sha256"] = b1.self_zero_sha256(record, "record_sha256")
        return record

    deep_bytes = b"[" * 5000 + b"0" + b"]" * 5000 + b"\n"
    guards = [
        ("transcript-strict-dup-request",
         request_raw.replace(b'"budget":', b'"budget":999,"budget":', 1), response_raw),
        ("transcript-strict-dup-response",
         request_raw, response_raw.replace(b'"result":', b'"result":"FAIL","result":', 1)),
        ("transcript-total-deep-request", deep_bytes, response_raw),
        ("transcript-total-deep-response", request_raw, deep_bytes),
    ]
    for name, req_bytes, resp_bytes in guards:
        count += 1
        try:
            ok, _reason = b1.validate_wrapper_transcript_binding(
                req_bytes, resp_bytes, rebound(req_bytes, resp_bytes)
            )
            if ok:
                failures.append(Failure(
                    "error_law", name, "binding evaluator accepted non-strict wire bytes"))
        except Exception as exc:  # noqa: BLE001 - totality is the assertion
            failures.append(Failure(
                "error_law", name, f"binding evaluator leaked {type(exc).__name__}: {exc}"))
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subprocess", action="store_true")
    parser.add_argument("--suite", default="all", choices=["all", "0.2", "0.3"])
    parser.add_argument("--section", default="all",
                        choices=["all", "semantic", "competence", "wrapper", "negative", "metamorphic", "error_law"])
    parser.add_argument("--max-failures", type=int, default=25)
    args = parser.parse_args()

    mode = "subprocess-ABI" if args.subprocess else "in-process"
    suite_specs = []
    if args.suite in ("all", "0.2"):
        suite_specs.append(("0.2", SEMANTIC_PACK_0_2, WRAPPER_PACK_0_2, True))
    if args.suite in ("all", "0.3"):
        suite_specs.append(("0.3", SEMANTIC_PACK_0_3, WRAPPER_PACK_0_3, False))

    failures: list[Failure] = []
    for suite, semantic_path, wrapper_path, include_error_law in suite_specs:
        semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
        wrapper = json.loads(wrapper_path.read_text(encoding="utf-8"))
        suite_failures: list[Failure] = []
        counts: dict[str, int] = {}
        if args.section in ("all", "semantic"):
            counts["semantic"] = run_semantic(semantic, args.subprocess, suite_failures)
        if args.section in ("all", "competence"):
            counts["competence"] = run_competence(semantic, args.subprocess, suite_failures)
        if args.section in ("all", "wrapper"):
            counts["wrapper_arms"] = run_wrapper(wrapper, args.subprocess, suite_failures)
        if args.section in ("all", "negative"):
            counts["negative"] = run_negative(wrapper, semantic, args.subprocess, suite_failures)
        if args.section in ("all", "metamorphic"):
            counts["metamorphic"] = run_metamorphic(
                wrapper, semantic, args.subprocess, suite_failures
            )
        if include_error_law and args.section in ("all", "error_law"):
            counts["error_law"] = run_error_law(
                semantic, wrapper, args.subprocess, suite_failures
            )
        print(
            f"mode={mode} suite={suite} counts={json.dumps(counts, sort_keys=True)} "
            f"total={sum(counts.values())} failures={len(suite_failures)}"
        )
        failures.extend(
            Failure(f"{suite}/{failure.section}", failure.case_id, failure.detail)
            for failure in suite_failures
        )

    for failure in failures[: args.max_failures]:
        print("FAIL", failure)
    if len(failures) > args.max_failures:
        print(f"... and {len(failures) - args.max_failures} more")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
