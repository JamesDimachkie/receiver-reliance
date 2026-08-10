"""Fixed-ABI stdin/stdout runner for the B1 baseline, contract 0.2.

Dispatch: `B1-SEMANTIC-DECISION-REQUEST-0.2` runs the core semantic decision;
`B1-WRAPPER-SEMANTIC-REQUEST-0.2` runs the B1/B1-ATTENTION wrapper. Exactly
one JCS+LF response on stdout, empty stderr, deterministic exit code.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

_MODULE_DIR = pathlib.Path(__file__).resolve().parent
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

import b1_capabilities as b1  # noqa: E402


def _pointer_key(text: str) -> bytes:
    """UTF-8 sort key, total over lone surrogates (surrogatepass). A
    surrogate-bearing pointer can never WIN selection — its presence in any
    key forces a canonical-byte ERR_JSON at precedence 50 — but selection
    must still be able to ORDER it without raising (round-8 finding
    R8-DIV-001)."""
    return text.encode("utf-8", "surrogatepass")


def _guarded_int(literal: str) -> int:
    """The interpreter's integer-digit conversion cap is a number-model
    event the profile scan has already located at its exact pointer
    (round-6 R6-003, round-7 R7-DIV-002); keep the tree build alive with a
    sentinel so selection stays with the ARG_MIN law."""
    try:
        return int(literal)
    except ValueError:
        return 0


def _valid_request_id(value: Any) -> str | None:
    if isinstance(value, str) and re.fullmatch(r"RUN_[A-F0-9]{24}", value):
        return value
    return None


def _protocol_error(
    code: str,
    pointer: str,
    parsed: Any = None,
    wrapper: bool = False,
) -> tuple[dict[str, Any], int]:
    if wrapper:
        response = b1.build_wrapper_error_response(
            code, pointer, parsed if isinstance(parsed, dict) else None
        )
    else:
        request_id = _valid_request_id(parsed.get("request_id")) if isinstance(parsed, dict) else None
        response = b1.build_core_error_response(code, pointer, request_id)
    return response, response["exit_code"]


_STRING_TOKEN = re.compile(r'"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"')
_ENVELOPE_KEYS = ("format_version", "request_id", "operation_handle", "configuration")


class _OverLimit:
    """Marker for an input rejected at the parse layer for exceeding the
    nesting limit. Carries the shallow depth-1 envelope fields used to shape
    its protocol-error response; the winning error code/pointer travel in the
    detected list beside it."""

    __slots__ = ("fields",)

    def __init__(self, fields: dict[str, str]) -> None:
        self.fields = fields


def _read_string_token(payload: str, i: int) -> tuple[str | None, int]:
    """Decode one JSON string beginning at payload[i] == '"'. Returns
    (decoded, index-after-close), or (None, i) if it is not a clean token."""
    match = _STRING_TOKEN.match(payload, i)
    if match is None:
        return None, i
    try:
        return json.loads(match.group()), match.end()
    except ValueError:
        return None, i


def _skip_json_value(payload: str, i: int) -> int:
    """Advance past one JSON value at payload[i] without recursion, matching
    brackets iteratively and honoring string literals, so it is safe on
    structures too deep for the recursive parser."""
    n = len(payload)
    ch = payload[i]
    if ch == '"':
        _, j = _read_string_token(payload, i)
        return j if j > i else n
    if ch in "{[":
        depth = 0
        while i < n:
            c = payload[i]
            if c == '"':
                _, j = _read_string_token(payload, i)
                if j <= i:
                    return n
                i = j
                continue
            if c in "{[":
                depth += 1
            elif c in "}]":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        return n
    while i < n and payload[i] not in ",}] \t\n\r":
        i += 1
    return i


def _shallow_root_and_fields(payload: str) -> tuple[bool, dict[str, str]]:
    """Whether the root is an object, and the depth-1 envelope string fields
    (format_version, request_id, operation_handle, configuration), read
    iteratively so the reader is safe on inputs past the recursive parser's
    reach. Only used to shape a protocol-error envelope for over-limit inputs;
    the winning error code and pointer come from the iterative scan, never
    from here. Anything unreadable is omitted and the error builders supply
    their own defaults."""
    fields: dict[str, str] = {}
    n = len(payload)
    i = 0
    while i < n and payload[i] in " \t\n\r":
        i += 1
    if i >= n or payload[i] != "{":
        return False, fields
    i += 1
    key: str | None = None
    expect_key = True
    while i < n:
        while i < n and payload[i] in " \t\n\r":
            i += 1
        if i >= n:
            break
        ch = payload[i]
        if ch == "}":
            break
        if ch == ",":
            i += 1
            expect_key = True
            key = None
            continue
        if ch == ":":
            i += 1
            expect_key = False
            continue
        if expect_key:
            if ch != '"':
                break
            token, j = _read_string_token(payload, i)
            if token is None:
                break
            key = token
            i = j
        elif ch == '"':
            token, j = _read_string_token(payload, i)
            if token is None:
                break
            if key in _ENVELOPE_KEYS and isinstance(token, str):
                fields[key] = token
            i = j
            key = None
        else:
            # Non-string value for a duplicated envelope key: json.loads keeps
            # the LAST value, so a later non-string occurrence must clear any
            # earlier cached string. This keeps the shallow envelope a faithful
            # last-value mirror of the parser (author-separated review
            # 2026-08-10).
            if key in _ENVELOPE_KEYS:
                fields.pop(key, None)
            i = _skip_json_value(payload, i)
            key = None
            if i >= n:
                break
    return True, fields


def _over_nesting_result(
    payload: str,
    scan: dict[str, Any],
    detected: list[tuple[str, str]],
    framing_error: bool,
) -> tuple[_OverLimit, list[tuple[str, str]]]:
    """Deterministic classification of an input past the 128-level nesting
    limit, from the iterative scan's depth-immune facts alone — no recursive
    parse runs, so the result is a pure function of the bytes. Mirrors the
    completed-parse classification of an over-limit, non-dispatchable value:
    a non-object root fails schema at the root; an object with an unknown or
    absent format_version fails at /format_version; a known-format object
    fails schema at the root. The structural limit and any parse-layer fault
    the scan already found are pooled; precedence then pointer order pick the
    winner."""
    root_is_object, fields = _shallow_root_and_fields(payload)
    pooled = list(detected)
    if not root_is_object:
        pooled.append(("ERR_SCHEMA", ""))
    elif fields.get("format_version") in (
        b1.CORE_REQUEST_FORMAT,
        b1.WRAPPER_REQUEST_FORMAT,
    ):
        pooled.append(("ERR_SCHEMA", ""))
    else:
        pooled.append(("ERR_SCHEMA", "/format_version"))
    pooled.append(("ERR_LIMIT", ""))
    if framing_error or scan["canonical"] or not scan["complete"]:
        pooled.append(("ERR_JSON", ""))
    ordered = sorted(
        set(pooled), key=lambda item: (b1.ERRORS[item[0]][1], _pointer_key(item[1]))
    )
    return _OverLimit(fields), ordered


def _parse(raw: bytes) -> tuple[Any | None, list[tuple[str, str]]]:
    """Return the parsed value and EVERY detected parse-layer error.

    Selection happens later, jointly with any O(1) dispatch-level schema
    detection, by (precedence, UTF-8 pointer). Only the pre-decode gates
    (empty, oversize, UTF-8, BOM) short-circuit: the packet orders them
    before decoding ("Reject input exceeding 16777216 bytes before decode",
    packet parse_rules), and nothing detectable can outrank them. All other
    profile detection comes from b1.scan_parse_profile — iterative and
    pointer-accurate, so it survives nesting the tree parser cannot and
    locates hook-level number violations exactly (round-7 findings
    R7-DIV-002 and R7-DIV-003)."""
    if not raw:
        return None, [("ERR_EMPTY_INPUT", "")]
    if len(raw) > b1.MAX_INPUT_BYTES:
        return None, [("ERR_LIMIT", "")]
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None, [("ERR_UTF8", "")]
    if raw.startswith(b"\xef\xbb\xbf") or text.startswith("﻿"):
        return None, [("ERR_BOM", "")]
    framing_error = not raw.endswith(b"\n")
    payload = text[:-1] if not framing_error else text
    if not payload:
        return None, [("ERR_EMPTY_INPUT", "")]
    scan = b1.scan_parse_profile(payload)
    detected: list[tuple[str, str]] = []
    if scan["duplicate"]:
        detected.append(("ERR_DUPLICATE_KEY", ""))
    if scan["nfc"]:
        detected.append(("ERR_NFC", min(scan["nfc"], key=_pointer_key)))
    if scan["number"]:
        detected.append(("ERR_NUMBER", min(scan["number"], key=_pointer_key)))
    if scan["nesting_exceeded"]:
        # An input past the 128-level nesting limit must never reach the
        # recursive tree parser: the depth at which CPython aborts json.loads
        # (and any recursive canonicalization or schema walk downstream) is
        # interpreter- and platform-specific, which made classification of
        # deep inputs interpreter-dependent. Classify from the iterative
        # scan's depth-immune facts alone — the same fence the wrapper
        # transcript evaluator already applies at _strict_wire_value
        # (round-7 R7-DIV-004), extended to the main parse path.
        return _over_nesting_result(payload, scan, detected, framing_error)
    try:
        value = json.loads(
            payload,
            parse_float=lambda _literal: 0,
            parse_constant=lambda _literal: 0,
            parse_int=_guarded_int,
        )
    except RecursionError:
        # Unreachable by construction: the nesting gate above catches every
        # input deep enough to recurse (MAX_NESTING is far below any CPython
        # abort depth). Kept as defense-in-depth, routed through the SAME
        # deterministic classifier so it cannot reintroduce interpreter
        # dependence.
        return _over_nesting_result(payload, scan, detected, framing_error)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        detected.append(("ERR_JSON", ""))
        if scan["limit"]:
            detected.append(("ERR_LIMIT", ""))
        return None, sorted(
            set(detected), key=lambda item: (b1.ERRORS[item[0]][1], _pointer_key(item[1]))
        )
    if framing_error or scan["canonical"] or not scan["complete"]:
        detected.append(("ERR_JSON", ""))
    if scan["limit"]:
        detected.append(("ERR_LIMIT", ""))
    return value, sorted(set(detected), key=lambda item: (b1.ERRORS[item[0]][1], _pointer_key(item[1])))


_COMBINATOR_SITES = ("", "/decision_input")


def _core_schema_error_pool(request: dict[str, Any]) -> list[str]:
    """Joint ERR_SCHEMA pool: binding mismatches and schema-leaf violations
    reduce together by UTF-8 pointer order. The generic validator reports
    combinator failures at their application sites ("" from the root
    consistency allOf, "/decision_input" from its oneOf). Such a site report
    is an echo of a binding finding ONLY when repairing exactly the
    binding-blamed echo fields (to the majority registry row, ties
    preferring the outer operation_handle's row) makes the site validate; a
    site that still fails on the repaired copy is an independent violation
    and keeps competing under the ARG_MIN law (terminal acceptance finding
    B1-IMPL-DIV-001)."""
    binding: list[str] = []
    try:
        binding = b1.envelope_binding_errors(request)
    except (b1.EvaluatorError, KeyError, TypeError, AttributeError):
        binding = []
    schema = b1.validate_core_request(request)
    if binding and any(pointer in _COMBINATOR_SITES for pointer in schema):
        repaired = b1.selector_repaired_request(request)
        surviving = (
            set(b1.validate_core_request(repaired))
            if repaired is not None
            else set(_COMBINATOR_SITES)
        )
        schema = [
            pointer
            for pointer in schema
            if pointer not in _COMBINATOR_SITES or pointer in surviving
        ]
    return sorted(set(binding) | set(schema), key=_pointer_key)


def _execute(raw: bytes) -> tuple[dict[str, Any], int]:
    parsed, detected = _parse(raw)
    if isinstance(parsed, _OverLimit):
        # Over-nesting: already fully classified from scan facts. Shape the
        # protocol-error response from the shallow envelope fields so its
        # shell (core vs wrapper, echoed request_id) matches what the
        # completed-parse path would emit, deterministically.
        code, pointer = min(
            detected, key=lambda item: (b1.ERRORS[item[0]][1], _pointer_key(item[1]))
        )
        wrapper = parsed.fields.get("format_version") == b1.WRAPPER_REQUEST_FORMAT
        response, exit_code = _protocol_error(code, pointer, parsed.fields, wrapper)
        if len(b1.jcs_bytes(response)) + 1 > b1.MAX_OUTPUT_BYTES:
            response, exit_code = _protocol_error("ERR_LIMIT", "", parsed.fields, wrapper)
        return response, exit_code
    wrapper = isinstance(parsed, dict) and parsed.get("format_version") == b1.WRAPPER_REQUEST_FORMAT
    core = isinstance(parsed, dict) and parsed.get("format_version") == b1.CORE_REQUEST_FORMAT
    try:
        response, exit_code = _dispatch(parsed, detected, core, wrapper)
    except Exception:  # noqa: BLE001 - family context must survive (R9-DIV-001)
        response, exit_code = _protocol_error("ERR_INTERNAL", "", parsed, wrapper)
    if len(b1.jcs_bytes(response)) + 1 > b1.MAX_OUTPUT_BYTES:
        # The output cap keeps the recognized response family and applies in
        # EVERY execution mode, not only the stdout writer (R9-DIV-002/003).
        response, exit_code = _protocol_error("ERR_LIMIT", "", parsed, wrapper)
    return response, exit_code


def _dispatch(
    parsed: Any,
    detected: list[tuple[str, str]],
    core: bool,
    wrapper: bool,
) -> tuple[dict[str, Any], int]:
    # Structural resource limits (precedence 90) never suppress the schema
    # walk: the packet's precedence chain places schema (80) before resource
    # limit, so a dispatchable request pools the limit WITH the full schema
    # evaluation (terminal round-5 finding B1-IMPL-FINAL2-DIV-003). Every
    # other parse-layer error outranks schema and resolves immediately.
    pending_limit = bool(detected) and all(code == "ERR_LIMIT" for code, _ in detected)
    if detected and not (pending_limit and (core or wrapper)):
        # O(1) dispatch-level ERR_SCHEMA detections (wrong root type, unknown
        # format_version) compete with parse-layer errors by precedence.
        if parsed is not None and not isinstance(parsed, dict):
            detected.append(("ERR_SCHEMA", ""))
        elif isinstance(parsed, dict) and parsed.get("format_version") not in (
            b1.CORE_REQUEST_FORMAT,
            b1.WRAPPER_REQUEST_FORMAT,
        ):
            detected.append(("ERR_SCHEMA", "/format_version"))
        code, pointer = min(
            detected, key=lambda item: (b1.ERRORS[item[0]][1], _pointer_key(item[1]))
        )
        return _protocol_error(code, pointer, parsed, wrapper)
    if not isinstance(parsed, dict):
        return _protocol_error("ERR_SCHEMA", "", parsed, False)

    if core:
        pool = _core_schema_error_pool(parsed)
        if pool:
            return _protocol_error("ERR_SCHEMA", pool[0], parsed, False)
        if pending_limit:
            return _protocol_error("ERR_LIMIT", "", parsed, False)
        response = b1.build_core_response(parsed)
        response_errors = b1.validate_core_response(response)
    elif wrapper:
        # The wrapper evaluator validates request.semantic_request against
        # the semantic request schema and applies every envelope binding
        # before wrapper evaluation, so semantic-subtree failures carry the
        # semantic joint pool's pointers under the /semantic_request prefix
        # instead of the wrapper schema's combinator site (terminal round-5
        # finding B1-IMPL-FINAL2-DIV-005).
        joint = list(b1.validate_wrapper_request(parsed))
        semantic = parsed.get("semantic_request")
        if isinstance(semantic, dict):
            joint = [
                pointer
                for pointer in joint
                if pointer != "/semantic_request"
                and not pointer.startswith("/semantic_request/")
            ]
            joint.extend(
                "/semantic_request" + pointer
                for pointer in _core_schema_error_pool(semantic)
            )
            if "request_id" in parsed and semantic.get("request_id") != parsed["request_id"]:
                joint.append("/semantic_request/request_id")
            if (
                "operation_handle" in parsed
                and semantic.get("operation_handle") != parsed["operation_handle"]
            ):
                joint.append("/semantic_request/operation_handle")
        try:
            if not b1.card_binding_valid(parsed):
                joint.append("/attention_card/card_sha256")
        except (b1.EvaluatorError, KeyError, TypeError, AttributeError):
            pass  # a malformed card already carries wrapper-schema leaves
        joint = sorted(set(joint), key=_pointer_key)
        if joint:
            return _protocol_error("ERR_SCHEMA", joint[0], parsed, True)
        if pending_limit:
            return _protocol_error("ERR_LIMIT", "", parsed, True)
        response = b1.build_wrapper_response(parsed)
        response_errors = b1.validate_wrapper_response(response)
    else:
        return _protocol_error("ERR_SCHEMA", "/format_version", parsed, False)

    if response_errors:
        return _protocol_error("ERR_INTERNAL", response_errors[0], parsed, wrapper)
    return response, response["exit_code"]


def main() -> int:
    parsed: Any = None
    wrapper = False
    try:
        if sys.argv[1:] != ["execute"]:
            response, exit_code = _protocol_error("ERR_INTERNAL", "")
        else:
            raw = sys.stdin.buffer.read(b1.MAX_INPUT_BYTES + 1)
            response, exit_code = _execute(raw)
        stdout = b1.jcs_bytes(response) + b"\n"
        if len(stdout) > b1.MAX_OUTPUT_BYTES:
            response, exit_code = _protocol_error("ERR_LIMIT", "", parsed, wrapper)
            stdout = b1.jcs_bytes(response) + b"\n"
    except Exception:
        response, exit_code = _protocol_error("ERR_INTERNAL", "", parsed, wrapper)
        stdout = b1.jcs_bytes(response) + b"\n"
    sys.stdout.buffer.write(stdout)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
