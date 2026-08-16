"""Focused regressions for wrapper wire and pre-execution hardening."""

from __future__ import annotations

import base64
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
from unittest import mock


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import rr2  # noqa: E402
import verify_artifacts  # noqa: E402
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
FROZEN_RUNNER = (
    ROOT / "baseline-run" / "implementation-output-0.3" / "pcb_runner.py"
)


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

    deep_semantic = b"[" * 10_000 + b"0" + b"]" * 10_000 + b"\n"
    value, parser, error_code, pointer = rr2._decode_bounded_raw_value(  # noqa: SLF001
        deep_semantic,
        defer_limits=True,
    )
    if value is not None or parser is None or parser.max_depth != MAX_JSON_DEPTH + 1 or (error_code, pointer) != ("ERR_SCHEMA", ""):
        failures.append("semantic-depth-allocation-bound")
    open_semantic = b"[" * 10_000
    _, _, error_code, pointer = rr2._decode_bounded_raw_value(  # noqa: SLF001
        open_semantic,
        defer_limits=True,
    )
    if (error_code, pointer) != ("ERR_JSON", ""):
        failures.append("semantic-depth-truncation-precedence")

    format_version = b"B1-SEMANTIC-DECISION-REQUEST-0.2"
    post_limit_request_id = b"RUN_0123456789ABCDEF01234567"
    post_limit_root_tail = b'","request_id":"' + post_limit_request_id + b'","x":'
    closed_deep_value = b"[" * 129 + b"0" + b"]" * 129
    precedence_witnesses = {
        "mismatched-container-types": (
            b'{"format_version":"'
            + format_version
            + b'","x":'
            + b"[" * 129
            + b"0"
            + b"]" * 128
            + b"}}\n"
        ),
        "format-version-outside-root": (
            b'{"x":{"deep":'
            + closed_deep_value
            + b',"format_version":"'
            + format_version
            + b'"}}\n'
        ),
        "trailing-bytes": (
            b'{"format_version":"'
            + format_version
            + b'","x":'
            + closed_deep_value
            + b"}0\n"
        ),
        "missing-terminal-lf": (
            b'{"format_version":"'
            + format_version
            + b'","x":'
            + closed_deep_value
            + b"}"
        ),
    }
    for name, raw in precedence_witnesses.items():
        frozen = subprocess.run(
            [sys.executable, "-I", "-B", str(FROZEN_RUNNER), "execute"],
            input=raw,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=120,
        )
        actual_exit, actual_raw = rr2.execute(raw)
        if frozen.stderr:
            failures.append("frozen-precedence-stderr:" + name)
        elif (actual_exit, actual_raw) != (frozen.returncode, frozen.stdout):
            failures.append("frozen-precedence-parity:" + name)

    post_limit_witnesses = {
        "duplicate-key": (
            b'{"format_version":"'
            + format_version
            + post_limit_root_tail
            + closed_deep_value
            + b',"y":0,"y":1}\n',
            ("ERR_DUPLICATE_KEY", ""),
        ),
        "fractional-number": (
            b'{"format_version":"'
            + format_version
            + post_limit_root_tail
            + closed_deep_value
            + b',"y":1.5}\n',
            ("ERR_NUMBER", "/y"),
        ),
        "negative-zero": (
            b'{"format_version":"'
            + format_version
            + post_limit_root_tail
            + closed_deep_value
            + b',"y":-0}\n',
            ("ERR_NUMBER", "/y"),
        ),
        "non-nfc-string": (
            b'{"format_version":"'
            + format_version
            + post_limit_root_tail
            + closed_deep_value
            + b',"y":"e\xcc\x81"}\n',
            ("ERR_NFC", "/y"),
        ),
        "escaped-format-version-key": (
            b'{"\\u0066ormat_version":"'
            + format_version
            + post_limit_root_tail
            + closed_deep_value
            + b"}\n",
            ("ERR_JSON", ""),
        ),
        "unknown-format-version": (
            b'{"format_version":"B1-UNKNOWN-0.2'
            + post_limit_root_tail
            + closed_deep_value
            + b"}\n",
            ("ERR_SCHEMA", "/format_version"),
        ),
        "non-string-format-version": (
            b'{"format_version":0,"request_id":"'
            + post_limit_request_id
            + b'","x":'
            + closed_deep_value
            + b"}\n",
            ("ERR_SCHEMA", "/format_version"),
        ),
        "known-format-version-control": (
            b'{"format_version":"'
            + format_version
            + post_limit_root_tail
            + closed_deep_value
            + b"}\n",
            ("ERR_SCHEMA", ""),
        ),
    }
    for name, (lf_raw, lf_law) in post_limit_witnesses.items():
        for framing, raw, law in (
            ("lf", lf_raw, lf_law),
            ("unframed", lf_raw[:-1], ("ERR_DUPLICATE_KEY", "") if name == "duplicate-key" else ("ERR_JSON", "")),
        ):
            frozen = subprocess.run(
                [sys.executable, "-I", "-B", str(FROZEN_RUNNER), "execute"],
                input=raw,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=120,
            )
            try:
                frozen_error = json.loads(frozen.stdout)["errors"][0]
            except (KeyError, IndexError, json.JSONDecodeError):
                failures.append(f"frozen-post-limit-envelope:{name}:{framing}")
                continue
            if frozen.stderr or (frozen_error["code"], frozen_error["pointer"]) != law:
                failures.append(f"frozen-post-limit-law:{name}:{framing}")
                continue
            actual_exit, actual_raw = rr2.execute(raw)
            if (actual_exit, actual_raw) != (frozen.returncode, frozen.stdout):
                failures.append(f"frozen-post-limit-parity:{name}:{framing}")

    long_key = "k" * 2_000
    amplified = ('{"' + long_key + '":[' + ",".join("1.5" for _ in range(2_000)) + "]}").encode("utf-8")
    pointer_parser = rr2.StrictParser(amplified.decode("utf-8"), enforce_limits=True)
    pointer_parser.parse()
    if pointer_parser.number_pointer != "/" + long_key + "/0" or hasattr(pointer_parser, "number_pointers"):
        failures.append("number-pointer-retention")

    long_pointer = "/" + "p" * 241
    _, bounded_raw = impl.error_response("ERR_SCHEMA", long_pointer)
    bounded_error = json.loads(bounded_raw)["errors"][0]
    if (bounded_error["code"], bounded_error["pointer"]) != ("ERR_LIMIT", ""):
        failures.append("core-error-pointer-cap")
    bounded_wrapper = impl.wrapper_error_response("ERR_SCHEMA", long_pointer, b1_request)
    if (bounded_wrapper["errors"][0]["code"], bounded_wrapper["errors"][0]["pointer"]) != ("ERR_LIMIT", ""):
        failures.append("wrapper-error-pointer-cap")

    recursion_limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(80)
        edges = [{"from": str(index), "to": str(index + 1)} for index in range(200)]
        cyclic = rr2.evaluate_atom(
            {"op": "NOT_ACYCLIC", "path": "/edges", "from": "from", "to": "to"},
            {"edges": edges},
        )
        if cyclic:
            failures.append("iterative-acyclic-chain")
        edges.append({"from": "200", "to": "0"})
        if not rr2.evaluate_atom(
            {"op": "NOT_ACYCLIC", "path": "/edges", "from": "from", "to": "to"},
            {"edges": edges},
        ):
            failures.append("iterative-acyclic-cycle")
    except RecursionError:
        failures.append("iterative-acyclic-recursion")
    finally:
        sys.setrecursionlimit(recursion_limit)

    expected_wrapper = impl.execute_wrapper(b1_request)
    completed = subprocess.run(
        [sys.executable, "-I", "-B", str(HERE / "cli.py"), "execute"],
        input=jcs(b1_request) + b"\n",
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=120,
    )
    if (
        completed.returncode != expected_wrapper["exit_code"]
        or completed.stdout != jcs(expected_wrapper) + b"\n"
        or completed.stderr
    ):
        failures.append("wrapper-cli-parity")

    original_default = rr2._DEFAULT  # noqa: SLF001
    rr2._DEFAULT = None  # noqa: SLF001
    try:
        with mock.patch.object(rr2, "Implementation", side_effect=ValueError("bootstrap")):
            code, bootstrap_raw = rr2.execute(b"\n")
        bootstrap_error = json.loads(bootstrap_raw)["errors"][0]
        if code != 2 or (bootstrap_error["code"], bootstrap_error["pointer"]) != ("ERR_INTERNAL", ""):
            failures.append("authority-bootstrap-totality")
    finally:
        rr2._DEFAULT = original_default  # noqa: SLF001

    malicious_author = {
        "candidate_files": [
            {"path": "../../outside", "raw_sha256": "A" * 64},
        ]
    }
    original_bounded_read = verify_artifacts._read_regular_bounded  # noqa: SLF001

    def guarded_receipt_read(path: Path, expected_length: int | None) -> bytes:
        if path == verify_artifacts.AUTHOR_RECEIPT:
            return json.dumps(malicious_author, separators=(",", ":")).encode("utf-8")
        if path in {verify_artifacts.PREFLIGHT_RECEIPT, verify_artifacts.COVERAGE_RECEIPT}:
            return original_bounded_read(path, expected_length)
        raise AssertionError("invalid receipt path was dereferenced")

    try:
        with mock.patch.object(
            verify_artifacts,
            "_read_regular_bounded",
            side_effect=guarded_receipt_read,
        ):
            verify_artifacts._verify_receipts([], None)  # noqa: SLF001
    except AssertionError:
        failures.append("invalid-author-path-dereferenced")

    with tempfile.TemporaryDirectory(prefix="rr2-authority-bound-") as temp:
        oversized = Path(temp) / "authority.json"
        with oversized.open("wb") as stream:
            stream.truncate(rr2.MAX_AUTHORITY_BYTES + 1)
        try:
            rr2._read_regular_bounded(oversized, None)  # noqa: SLF001
        except ValueError:
            pass
        else:
            failures.append("oversized-authority-read")

    result = {
        "direct_wrapper_negative": len(invalid_requests),
        "failures": len(failures),
        "post_limit_precedence_regressions": len(post_limit_witnesses) * 2,
        "raw_wrapper_negative": len(raw_cases),
        "w4_security_regressions": 15,
        "wrapper_binding_positive": 1,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    for failure in failures:
        print(failure)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
