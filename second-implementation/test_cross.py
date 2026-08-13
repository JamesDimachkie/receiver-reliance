from __future__ import annotations

import base64
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from coverage_campaign import REQUIRED_STEERING_CODE_OBJECTS, steering_requirements  # noqa: E402
from process_harness import run_candidate_cli  # noqa: E402
from raw_preflight_cases import raw_cases  # noqa: E402
from rr2 import AUTHORITY_PATHS, Contracts, Implementation, jcs, pointer_get, sha256_upper  # noqa: E402


SEMANTIC_PACKS = [
    ROOT / "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json",
    ROOT / "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
]
WRAPPER_PACKS = [
    ROOT / "baseline-run/fixtures/B1_WRAPPER_PARITY_FIXTURE_PACK_0_2.json",
    ROOT / "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_WRAPPER_PARITY_FIXTURE_PACK_0_3.json",
]
DESCRIPTOR_ONLY = {
    "SATISFY_REQUIRED_SET_KEEP_ASKING_ACCOUNTED",
    "SATISFY_REQUIRED_SET_KEEP_ASKING_UNACCOUNTED",
    "REASK_ANSWERED_QUERY_IGNORING_INGESTED_ANSWER",
    "ADMIT_TOP_RANKED_INCOMPATIBLE_RECORD",
    "SHIFT_INTENT_TUPLE_KEEP_STALE_SELECTION",
    "ADD_INCOMPATIBLE_DISTRACTORS_COHERENTLY_EXCLUDED",
    "ABSORB_DISTRACTOR_INTO_SELECTION",
}


def load(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def set_pointer(root, pointer: str, value) -> None:
    tokens = [token.replace("~1", "/").replace("~0", "~") for token in pointer[1:].split("/")]
    node = root
    for token in tokens[:-1]:
        node = node[int(token)] if isinstance(node, list) else node[token]
    last = tokens[-1]
    if isinstance(node, list):
        node[int(last)] = copy.deepcopy(value)
    else:
        node[last] = copy.deepcopy(value)


def materialize(case, entries):
    base = entries[case["base_entry_id"]]
    request = copy.deepcopy(base["semantic_request"])
    mutation = case["mutation"]
    operation = mutation.get("operation")
    if operation in DESCRIPTOR_ONLY:
        return None
    if operation == "RENAME_NONAUTHORITATIVE_METADATA_ONLY":
        return request
    if operation == "EXCHANGE_AUTHORITATIVE_FACTS_KEEP_LABELS_FIXED":
        target = entries[mutation["target_facts_entry_id"]]
        request["decision_input"]["facts"] = copy.deepcopy(target["semantic_request"]["decision_input"]["facts"])
        return request
    if "pointer" in mutation and "after" in mutation:
        set_pointer(request, mutation["pointer"], mutation["after"])
    elif operation == "REPLACE_WITH_SCHEMA_VALID_MISMATCH":
        set_pointer(request, mutation["pointer"], mutation["after"])
    else:
        raise AssertionError(f"unmaterialized competence operation: {operation!r}")
    if operation == "RENAME_OPAQUE_LABEL":
        request["inner_request_raw_sha256"] = mutation["recomputed_inner_request_raw_sha256"]
        request["inner_input_sha256"] = mutation["recomputed_inner_input_sha256"]
    return request


def main() -> int:
    impl = Implementation(ROOT)
    failures: list[str] = []
    counts = {
        "semantic": 0,
        "semantic_cli": 0,
        "deep_api": 0,
        "deep_cli": 0,
        "number_totality_api": 0,
        "number_totality_cli": 0,
        "raw_size_precedence_api": 0,
        "raw_size_precedence_cli": 0,
        "authority_pin_mutations": 0,
        "coverage_steering_checks": 0,
        "competence_executed": 0,
        "competence_descriptor_only": 0,
        "metamorphic_records": 0,
        "metamorphic_candidate_executed": 0,
        "metamorphic_descriptor_validated": 0,
        "metamorphic_wrapper_arms_executed": 0,
        "wrapper_arms": 0,
        "wrapper_bindings": 0,
        "wrapper_negative": 0,
        "wrapper_pair_projections": 0,
        "ri_regressions": 0,
        "refuter_probes": 0,
    }

    semantic_packs = [load(path) for path in SEMANTIC_PACKS]
    entries = {entry["entry_id"]: entry for pack in semantic_packs for entry in pack["entries"]}
    competence_by_sha = {case["case_sha256"]: case for pack in semantic_packs for case in pack["competence_cases"]}
    materialized_by_sha = {}
    for pack in semantic_packs:
        for entry in pack["entries"]:
            counts["semantic"] += 1
            raw = base64.b64decode(entry["semantic_request_jcs_lf_base64"])
            expected = base64.b64decode(entry["expected_response_jcs_lf_base64"])
            got = impl.execute_bytes(raw)[1]
            if got != expected:
                failures.append("semantic:" + entry["entry_id"])
            counts["semantic_cli"] += 1
            proc = run_candidate_cli(raw)
            if proc.returncode != entry["expected_response"]["exit_code"] or proc.stdout != expected or proc.stderr:
                failures.append("semantic-cli:" + entry["entry_id"])
        for case in pack["competence_cases"]:
            request = materialize(case, entries)
            materialized_by_sha[case["case_sha256"]] = request
            if request is None:
                counts["competence_descriptor_only"] += 1
                continue
            counts["competence_executed"] += 1
            got = impl.execute_bytes(jcs(request) + b"\n")[1]
            if sha256_upper(got) != case["expected_response_raw_sha256"]:
                failures.append("competence:" + case["case_sha256"])

    wrapper_packs = [load(path) for path in WRAPPER_PACKS]
    pairs_by_entry = {}
    pairs_by_id = {}
    for pack in wrapper_packs:
        for pair in pack["pairs"]:
            pairs_by_entry[pair["core_entry_id"]] = pair
            pairs_by_id[pair["pair_id"]] = pair
            b1 = pair["b1_arm"]
            attention = pair["b1_attention_arm"]
            counts["wrapper_pair_projections"] += 1
            if impl.wrapper_projection(b1["wrapper_request"]) != impl.wrapper_projection(attention["wrapper_request"]):
                failures.append("wrapper-projection:" + pair["pair_id"])
            for name in ("b1_arm", "b1_attention_arm"):
                arm = pair[name]
                counts["wrapper_arms"] += 1
                got = jcs(impl.execute_wrapper(arm["wrapper_request"])) + b"\n"
                expected = base64.b64decode(arm["response_jcs_lf_base64"])
                if got != expected:
                    failures.append("wrapper:" + pair["pair_id"] + ":" + name)
                counts["wrapper_bindings"] += 1
                if not impl.validate_wrapper_binding(
                    base64.b64decode(arm["request_jcs_lf_base64"]),
                    base64.b64decode(arm["response_jcs_lf_base64"]),
                    arm["transcript"],
                ):
                    failures.append("wrapper-binding:" + pair["pair_id"] + ":" + name)
        for case in pack["negative_cases"]:
            counts["wrapper_negative"] += 1
            pair = pairs_by_entry[case["base_entry_id"]]
            bundle = {
                "b1_arm": {
                    "wrapper_request": copy.deepcopy(pair["b1_arm"]["wrapper_request"]),
                    "wrapper_response": copy.deepcopy(pair["b1_arm"]["wrapper_response"]),
                    "transcript": copy.deepcopy(pair["b1_arm"]["transcript"]),
                },
                "b1_attention_arm": {
                    "wrapper_request": copy.deepcopy(pair["b1_attention_arm"]["wrapper_request"]),
                    "wrapper_response": copy.deepcopy(pair["b1_attention_arm"]["wrapper_response"]),
                    "transcript": copy.deepcopy(pair["b1_attention_arm"]["transcript"]),
                },
            }
            mutation = case["mutation"]
            pointer = mutation["pointer"]
            if pointer.startswith("/wrapper_") or pointer.startswith("/transcript"):
                pointer = "/b1_arm" + pointer
            if mutation.get("operation") == "DELETE_MEMBER":
                bundle.pop(pointer[1:])
                accepted = False
            else:
                set_pointer(bundle, pointer, mutation["after"])
                if case["case_name"] == "FROZEN_POOL_ARM_DIVERGENCE":
                    accepted = impl.wrapper_projection(bundle["b1_arm"]["wrapper_request"]) == impl.wrapper_projection(bundle["b1_attention_arm"]["wrapper_request"])
                else:
                    mutated = bundle["b1_arm"]
                    accepted = impl.validate_wrapper_binding(
                        jcs(mutated["wrapper_request"]) + b"\n",
                        jcs(mutated["wrapper_response"]) + b"\n",
                        mutated["transcript"],
                    )
            if accepted:
                failures.append("wrapper-negative:" + case["negative_case_id"])

        for meta in pack["metamorphic_cases"]:
            counts["metamorphic_records"] += 1
            competence = competence_by_sha.get(meta["core_competence_case_sha256"])
            pair = pairs_by_id.get(meta["base_pair_id"])
            if competence is None or pair is None or competence["rule_id"] != meta["core_competence_rule_ref"]:
                failures.append("metamorphic-link:" + meta["metamorphic_case_id"])
                continue
            base_entry = entries[competence["base_entry_id"]]
            base_digest = base_entry["expected_response_raw_sha256"]
            expected_digest = competence["expected_response_raw_sha256"]
            relation = meta["expected_relation"]
            if relation in {"BYTE_IDENTICAL", "RESPONSE_BYTES_IDENTICAL_UNDER_DISTRACTOR_ADDITION"}:
                if expected_digest != base_digest:
                    failures.append("metamorphic-frozen-relation:" + meta["metamorphic_case_id"])
            elif relation in {"CLASS_AND_SEALS_CHANGE", "OUTPUT_FOLLOWS_FACTS"}:
                if expected_digest == base_digest:
                    failures.append("metamorphic-frozen-relation:" + meta["metamorphic_case_id"])
            else:
                failures.append("metamorphic-unknown-relation:" + meta["metamorphic_case_id"])

            request = materialized_by_sha[competence["case_sha256"]]
            if request is None:
                counts["metamorphic_descriptor_validated"] += 1
                expected_object = competence.get("expected_response")
                if expected_object is not None and sha256_upper(jcs(expected_object) + b"\n") != expected_digest:
                    failures.append("metamorphic-descriptor-bytes:" + meta["metamorphic_case_id"])
                continue

            counts["metamorphic_candidate_executed"] += 1
            core_raw = impl.execute_bytes(jcs(request) + b"\n")[1]
            if sha256_upper(core_raw) != expected_digest:
                failures.append("metamorphic-core:" + meta["metamorphic_case_id"])
            core_object = json.loads(core_raw)
            for arm_name in ("b1_arm", "b1_attention_arm"):
                counts["metamorphic_wrapper_arms_executed"] += 1
                wrapper_request = copy.deepcopy(pair[arm_name]["wrapper_request"])
                wrapper_request["semantic_request"] = copy.deepcopy(request)
                wrapper_response = impl.execute_wrapper(wrapper_request)
                base_response = pair[arm_name]["wrapper_response"]
                if relation in {"BYTE_IDENTICAL", "RESPONSE_BYTES_IDENTICAL_UNDER_DISTRACTOR_ADDITION"}:
                    if wrapper_response != base_response:
                        failures.append("metamorphic-wrapper-identical:" + meta["metamorphic_case_id"] + ":" + arm_name)
                else:
                    if wrapper_response["output"]["payload"] == base_response["output"]["payload"] or wrapper_response["response_sha256"] == base_response["response_sha256"]:
                        failures.append("metamorphic-wrapper-change:" + meta["metamorphic_case_id"] + ":" + arm_name)
                if wrapper_response["output"]["payload"] != core_object["output"]["result_object"]:
                    failures.append("metamorphic-wrapper-core:" + meta["metamorphic_case_id"] + ":" + arm_name)

    ri_cases = [
        ("898F487E1FFD5284DB606603F67AD297CDDB19D339CE5DDFD570B28D16D74014", "7b22f0908080223a302c22ee8080223a307d0a", "309E457F8DE3B7970333ABBB017D54BC12507F93E6C833AA9F38130EBC0080CF"),
        ("74E3BA01F245DF1466E43A5DE7DFDAF97588B58EC84BC649A1FE60CF91AFC7D0", "7b22ee8080223a302c22f0908080223a307d0a", "9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2"),
        ("B16AF5D32E117E1E4A4132716A6DFB0621BB990D1BFCCE97A9DF73774D0984F3", "225c7564383030220a", "9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2"),
        ("8BA9AF9592D9FED7D0E9277137B1F224B9BB222AA3E8252C333CA28046140741", "7b225c7564383030223a307d0a", "9543AAFCF326CEE49F67E5106EC886B82BD9176C3E1D5946C4994CFCA9A567C2"),
        ("10779FCB480886B954ACEAE3C495771971BAA338F1A8FE55A48EB68965B4D6FD", "7b22223a302c2222", "6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01"),
        ("293AA0DC593A180913051A897487B774057874E861B66C828AEA380D08F523BD", "7b22223a302c22223a307d0a", "6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01"),
        ("F5EECE3728CC6AFC1FF909758FEF968D8F2EBD0B6F70C5A0B75C6CC47BED4F58", "7b2261223a302c226122", "6D204C049556859C3CBCADCD18E8BE20554D0F6638A31A50168C52E3F2F29C01"),
    ]
    for expected_input_sha, raw_hex, expected_output_sha in ri_cases:
        counts["ri_regressions"] += 1
        raw = bytes.fromhex(raw_hex)
        if sha256_upper(raw) != expected_input_sha or sha256_upper(impl.execute_bytes(raw)[1]) != expected_output_sha:
            failures.append("ri:" + expected_input_sha)

    probes = [
        (b"", "ERR_EMPTY_INPUT", ""),
        (b"\xff\n", "ERR_UTF8", ""),
        (b"\xef\xbb\xbf{}\n", "ERR_BOM", ""),
        (b'{"a":0,"a":1}\n', "ERR_DUPLICATE_KEY", ""),
        (b'{"a":{"x":0,"x":1}}\n', "ERR_DUPLICATE_KEY", ""),
        (b'{"b":0,"a":0}\n', "ERR_JSON", ""),
        (b"1.0\n", "ERR_NUMBER", ""),
        (b"-0\n", "ERR_NUMBER", ""),
        (b"9007199254740992\n", "ERR_NUMBER", ""),
        ('"e\u0301"\n'.encode(), "ERR_NFC", ""),
    ]
    for raw, code, pointer in probes:
        counts["refuter_probes"] += 1
        response = json.loads(impl.execute_bytes(raw)[1])
        error = response["errors"][0]
        if error["code"] != code or error["pointer"] != pointer:
            failures.append("probe:" + raw.hex())

    # Error-precedence regressions discovered by bounded author preflight.
    base_request = copy.deepcopy(entries["SEMFX-OBL-01-IO-638822AAD3E2B835"]["semantic_request"])
    precedence_requests = []
    malformed = copy.deepcopy(base_request); malformed["inner_request"]["format_version"] = "PCB-RUNNER-REQUERT-0.2"
    precedence_requests.append((malformed, "/inner_request/format_version"))
    malformed = copy.deepcopy(base_request); malformed["inner_request"]["input"]["unknown_field"] = 1
    precedence_requests.append((malformed, "/inner_input_sha256"))
    malformed = copy.deepcopy(base_request); malformed["request_id"] = "RUN_" + "A" * 23 + "%"
    precedence_requests.append((malformed, "/inner_request/request_id"))
    malformed = copy.deepcopy(base_request); malformed["inner_inptt_sha256"] = malformed.pop("inner_input_sha256")
    precedence_requests.append((malformed, "/inner_inptt_sha256"))
    for request, pointer in precedence_requests:
        counts["refuter_probes"] += 1
        response = json.loads(impl.execute_bytes(jcs(request) + b"\n")[1])
        error = response["errors"][0]
        if error["code"] != "ERR_SCHEMA" or error["pointer"] != pointer:
            failures.append("precedence-probe:" + pointer)

    family_count_keys = {
        "deep": ("deep_api", "deep_cli"),
        "number": ("number_totality_api", "number_totality_cli"),
        "size": ("raw_size_precedence_api", "raw_size_precedence_cli"),
    }
    for case in raw_cases():
        api_count, cli_count = family_count_keys[case.family]
        counts[api_count] += 1
        api_code, api_raw = impl.execute_bytes(case.raw)
        api_object = json.loads(api_raw)
        error = api_object["errors"][0]
        if api_code != 2 or error["code"] != case.expected_code or error["pointer"] != case.expected_pointer:
            failures.append(case.family + "-api:" + case.name)
        counts[cli_count] += 1
        proc = run_candidate_cli(case.raw)
        if proc.returncode != api_code or proc.stdout != api_raw or proc.stderr:
            failures.append(case.family + "-cli:" + case.name)

    required = set(REQUIRED_STEERING_CODE_OBJECTS)
    missing_monitored, missing_observed = steering_requirements(required, required)
    counts["coverage_steering_checks"] += 1
    if missing_monitored or missing_observed:
        failures.append("coverage-steering-complete-set")
    missing_monitored, missing_observed = steering_requirements({"_execute"}, {"_execute"})
    counts["coverage_steering_checks"] += 1
    if not missing_monitored or not missing_observed:
        failures.append("coverage-steering-execute-only-not-rejected")

    with tempfile.TemporaryDirectory(prefix="rr2-authority-pins-") as temporary:
        authority_root = Path(temporary)
        for relative in AUTHORITY_PATHS:
            target = authority_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        Contracts(authority_root)
        for relative in AUTHORITY_PATHS:
            target = authority_root / relative
            original = target.read_bytes()
            mutated = bytearray(original)
            mutated[0] ^= 1
            target.write_bytes(mutated)
            counts["authority_pin_mutations"] += 1
            try:
                Contracts(authority_root)
            except ValueError as error:
                if str(error) != "authority pin mismatch: " + relative:
                    failures.append("authority-pin-wrong-error:" + relative)
            else:
                failures.append("authority-pin-mutation-accepted:" + relative)
            target.write_bytes(original)

    print("second-implementation counts=" + json.dumps(counts, sort_keys=True, separators=(",", ":")) + f" failures={len(failures)}")
    for failure in failures[:20]:
        print(failure)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
