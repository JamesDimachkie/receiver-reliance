"""Focused regressions for wrapper wire and pre-execution hardening."""

from __future__ import annotations

import base64
import copy
import json
from pathlib import Path
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from rr2 import (  # noqa: E402
    MAX_JSON_DEPTH,
    MAX_JSON_MEMBERS,
    MAX_JSON_NODES,
    MAX_RAW_BYTES,
    ZERO64,
    Implementation,
    jcs,
    sha256_upper,
    validate,
)


WRAPPER_PACK = ROOT / "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_WRAPPER_PARITY_FIXTURE_PACK_0_3.json"


def _duplicate_prefix(raw: bytes, name: str, value_raw: bytes) -> bytes:
    if not raw.startswith(b"{"):
        raise ValueError("expected object wire value")
    return b'{"' + name.encode("ascii") + b'":' + value_raw + b"," + raw[1:]


def _oversize(raw: bytes) -> bytes:
    padding = MAX_RAW_BYTES + 1 - len(raw)
    if padding < 1 or not raw.endswith(b"\n"):
        raise ValueError("invalid oversize source")
    return raw[:-1] + (b" " * padding) + b"\n"


def _rebind_transcript(
    transcript: dict[str, Any],
    request_raw: bytes,
    response_raw: bytes,
) -> dict[str, Any]:
    rebound = copy.deepcopy(transcript)
    rebound["request_raw_sha256"] = sha256_upper(request_raw)
    rebound["response_raw_sha256"] = sha256_upper(response_raw)
    rebound["record_sha256"] = ZERO64
    rebound["record_sha256"] = sha256_upper(jcs(rebound))
    return rebound


def _valid_wrapper_error(
    impl: Implementation,
    response: Any,
    expected_pointer: str,
) -> bool:
    try:
        if (
            not isinstance(response, dict)
            or response["ok"] is not False
            or response["result"] != "INCOMPLETE"
            or response["exit_code"] != 2
            or response["output"] is not None
            or len(response["errors"]) != 1
            or response["errors"][0]["code"] != "ERR_SCHEMA"
            or response["errors"][0]["pointer"] != expected_pointer
        ):
            return False
        sealed = dict(response)
        expected_seal = sealed["response_sha256"]
        sealed["response_sha256"] = ZERO64
        if sha256_upper(jcs(sealed)) != expected_seal:
            return False
        schema = impl.contracts.supp["schemas"]["wrapper_configuration_response_schema"]
        return validate(
            response,
            schema,
            impl.contracts,
            current_root=impl.contracts.supp,
        ) is None
    except Exception:
        return False


def main() -> int:
    pack = json.loads(WRAPPER_PACK.read_bytes())
    pair = pack["pairs"][0]
    impl = Implementation(ROOT)
    failures: list[str] = []

    b1_request = copy.deepcopy(pair["b1_arm"]["wrapper_request"])
    attention_request = copy.deepcopy(pair["b1_attention_arm"]["wrapper_request"])
    other_operation = next(
        operation
        for operation in impl.contracts.registry
        if operation != b1_request["operation_handle"]
    )
    other_request_id = "RUN_" + "F" * 24
    if other_request_id == b1_request["request_id"]:
        other_request_id = "RUN_" + "E" * 24

    invalid_requests: list[tuple[str, dict[str, Any], str]] = []

    malformed = copy.deepcopy(b1_request)
    del malformed["request_id"]
    invalid_requests.append(("missing-outer-request-id", malformed, "/request_id"))

    malformed = copy.deepcopy(b1_request)
    malformed["request_id"] = other_request_id
    invalid_requests.append(
        ("mismatched-outer-inner-request-id", malformed, "/semantic_request/request_id")
    )

    malformed = copy.deepcopy(b1_request)
    malformed["operation_handle"] = other_operation
    invalid_requests.append(
        ("mismatched-outer-inner-operation", malformed, "/semantic_request/operation_handle")
    )

    malformed = copy.deepcopy(b1_request)
    malformed["configuration"] = "INVALID"
    invalid_requests.append(("invalid-configuration", malformed, "/configuration"))

    malformed = copy.deepcopy(b1_request)
    malformed["budget"] = 0
    invalid_requests.append(("invalid-budget", malformed, "/budget"))

    malformed = copy.deepcopy(b1_request)
    malformed["pause_state"] = "INVALID"
    invalid_requests.append(("invalid-pause-state", malformed, "/pause_state"))

    malformed = copy.deepcopy(b1_request)
    malformed["clarification_state"] = "INVALID"
    invalid_requests.append(
        ("invalid-clarification-state", malformed, "/clarification_state")
    )

    malformed = copy.deepcopy(b1_request)
    malformed["extra"] = True
    invalid_requests.append(("extra-wrapper-member", malformed, "/extra"))

    malformed = copy.deepcopy(attention_request)
    card = malformed["attention_card"]
    card["card_sha256"] = (
        "A" * 64 if card["card_sha256"] == ZERO64 else ZERO64
    )
    invalid_requests.append(
        ("tampered-attention-card-seal", malformed, "/attention_card/card_sha256")
    )

    original_execute_bytes = impl.execute_bytes

    def forbidden_execute_bytes(_raw: bytes) -> tuple[int, bytes]:
        raise AssertionError("semantic execution preceded wrapper validation")

    impl.execute_bytes = forbidden_execute_bytes  # type: ignore[method-assign]
    try:
        for name, request, pointer in invalid_requests:
            try:
                response = impl.execute_wrapper(request)
            except Exception as error:
                failures.append(f"wrapper-request-raised:{name}:{type(error).__name__}")
                continue
            if not _valid_wrapper_error(impl, response, pointer):
                failures.append("wrapper-request-error:" + name)
    finally:
        impl.execute_bytes = original_execute_bytes  # type: ignore[method-assign]

    arm = pair["b1_arm"]
    request_raw = base64.b64decode(arm["request_jcs_lf_base64"])
    response_raw = base64.b64decode(arm["response_jcs_lf_base64"])
    transcript = arm["transcript"]

    if not impl.validate_wrapper_binding(request_raw, response_raw, transcript):
        failures.append("wrapper-binding-positive-control")

    deep_value = (
        b"[" * MAX_JSON_DEPTH
        + b"0"
        + b"]" * MAX_JSON_DEPTH
    )
    node_value = b"[" + (b"0," * MAX_JSON_NODES) + b"0]"
    member_value = (
        b"{"
        + b",".join(
            f'"k{index:06d}":0'.encode("ascii")
            for index in range(MAX_JSON_MEMBERS + 1)
        )
        + b"}"
    )
    response_configuration = json.dumps(
        arm["wrapper_response"]["configuration"],
        separators=(",", ":"),
    ).encode("ascii")

    raw_cases = [
        (
            "request-duplicate-member",
            _duplicate_prefix(request_raw, "attention_card", b"null"),
            response_raw,
        ),
        (
            "response-duplicate-member",
            request_raw,
            _duplicate_prefix(response_raw, "configuration", response_configuration),
        ),
        (
            "request-noncanonical-whitespace",
            request_raw[:1] + b" " + request_raw[1:],
            response_raw,
        ),
        (
            "response-noncanonical-whitespace",
            request_raw,
            response_raw[:1] + b" " + response_raw[1:],
        ),
        ("request-missing-lf", request_raw[:-1], response_raw),
        ("response-missing-lf", request_raw, response_raw[:-1]),
        ("request-oversize", _oversize(request_raw), response_raw),
        ("response-oversize", request_raw, _oversize(response_raw)),
        (
            "request-over-depth",
            _duplicate_prefix(request_raw, "attention_card", deep_value),
            response_raw,
        ),
        (
            "response-over-depth",
            request_raw,
            _duplicate_prefix(response_raw, "configuration", deep_value),
        ),
        (
            "request-over-node",
            _duplicate_prefix(request_raw, "attention_card", node_value),
            response_raw,
        ),
        (
            "response-over-node",
            request_raw,
            _duplicate_prefix(response_raw, "configuration", node_value),
        ),
        (
            "request-over-member",
            _duplicate_prefix(request_raw, "attention_card", member_value),
            response_raw,
        ),
    ]

    for name, mutated_request_raw, mutated_response_raw in raw_cases:
        rebound = _rebind_transcript(
            transcript,
            mutated_request_raw,
            mutated_response_raw,
        )
        try:
            accepted = impl.validate_wrapper_binding(
                mutated_request_raw,
                mutated_response_raw,
                rebound,
            )
        except Exception as error:
            failures.append(f"wrapper-raw-raised:{name}:{type(error).__name__}")
            continue
        if accepted:
            failures.append("wrapper-raw-accepted:" + name)

    result = {
        "direct_wrapper_negative": len(invalid_requests),
        "failures": len(failures),
        "raw_wrapper_negative": len(raw_cases),
        "wrapper_binding_positive": 1,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    for failure in failures:
        print(failure)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
