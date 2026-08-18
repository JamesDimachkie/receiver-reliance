"""Deterministic B1/B1-ATTENTION capability implementation, composed 0.3.

Classification is interpreted at runtime from the frozen
accepted-0.2 and supplemental-0.3 decision tables; nothing here branches on
fixture labels or provenance metadata.  The supplemental contract's own raw
SHA-256 is supplied externally at review and is deliberately not embedded
(contract resolver rule).  Every inherited authority needed at runtime is
verified against the exact digest and byte length pinned by that contract.
No network, subprocess, clock, randomness, or ambient-environment dependency.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import pathlib
import re
import unicodedata
from functools import lru_cache
from typing import Any

ZERO64 = "0" * 64
SAFE_INTEGER_MIN = -9007199254740991
SAFE_INTEGER_MAX = 9007199254740991
MAX_INPUT_BYTES = 16777216
MAX_OUTPUT_BYTES = 16777216
# Structural limits pinned by the basis packet's runtime limits
# (SANITIZED_PRIMARY_BASELINE_IMPLEMENTER_PACKET_0_1.json: nesting 128,
# members_or_items 100000). They compete at ERR_LIMIT precedence 90 and
# never suppress the schema walk.
MAX_NESTING = 128
MAX_MEMBERS_OR_ITEMS = 100000

CORE_REQUEST_FORMAT = "B1-SEMANTIC-DECISION-REQUEST-0.2"
CORE_RESPONSE_FORMAT = "PCB-RUNNER-RESPONSE-0.2"
WRAPPER_REQUEST_FORMAT = "B1-WRAPPER-SEMANTIC-REQUEST-0.2"
WRAPPER_RESPONSE_FORMAT = "B1-WRAPPER-SEMANTIC-RESPONSE-0.2"
EFFECT_DOMAIN = "B1-SEMANTIC-EFFECT-RECEIPT-0.2"

REQUEST_ID_RE = re.compile(r"RUN_[A-F0-9]{24}")

ERRORS = {
    "ERR_EMPTY_INPUT": ("Input is absent or empty.", 10),
    "ERR_UTF8": ("Input is not strict UTF-8.", 20),
    "ERR_BOM": ("UTF-8 BOM is forbidden.", 30),
    "ERR_DUPLICATE_KEY": ("Duplicate JSON object key.", 40),
    "ERR_JSON": ("Invalid JSON or trailing bytes.", 50),
    "ERR_NFC": ("String is not Unicode NFC.", 60),
    "ERR_NUMBER": ("Number violates the safe integer model.", 70),
    "ERR_SCHEMA": ("Request does not validate.", 80),
    "ERR_LIMIT": ("A deterministic resource limit was exceeded.", 90),
    "ERR_INTERNAL": ("A deterministic internal failure occurred.", 100),
}

CLASS_PRECEDENCE = ("MALFORMED_OR_BOUNDARY", "BINDING_OR_CONFLICT", "OMISSION_OR_INCOMPLETE")

RESULT_CONTRACT = {
    "VALID": {"result": "PASS", "status": "PASS", "conclusion": "SATISFIED", "exit_code": 0},
    "MALFORMED_OR_BOUNDARY": {"result": "FAIL", "status": "FAIL", "conclusion": "VIOLATED", "exit_code": 1},
    "BINDING_OR_CONFLICT": {"result": "FAIL", "status": "FAIL", "conclusion": "VIOLATED", "exit_code": 1},
    "OMISSION_OR_INCOMPLETE": {"result": "FAIL", "status": "FAIL", "conclusion": "UNRESOLVED", "exit_code": 1},
}


class AuthorityError(RuntimeError):
    pass


class EvaluatorError(RuntimeError):
    pass


def _jcs_ordered(value: Any) -> Any:
    if isinstance(value, dict):
        # RFC 8785 orders members by UTF-16 code units, not Unicode code points.
        return {
            key: _jcs_ordered(value[key])
            for key in sorted(value, key=lambda item: item.encode("utf-16-be"))
        }
    if isinstance(value, list):
        return [_jcs_ordered(item) for item in value]
    return value


def jcs_bytes(value: Any) -> bytes:
    """Canonical JSON for this integer-only, NFC contract profile."""
    return json.dumps(
        _jcs_ordered(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=False,
    ).encode("utf-8")


def sha256_upper(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def self_zero_sha256(value: dict[str, Any], field: str) -> str:
    candidate = dict(value)
    candidate[field] = ZERO64
    return sha256_upper(jcs_bytes(candidate))


def _baseline_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def authority_documents() -> dict[str, dict[str, Any]]:
    baseline = _baseline_root()
    gate_root = baseline.parent
    supplemental_root = gate_root / "supplemental-0_3"
    contract_raw = (
        supplemental_root / "control" / "B1_SUPPLEMENTAL_COMPARATOR_CONTRACT_0_3.json"
    ).read_bytes()
    contract = json.loads(contract_raw.decode("utf-8"))
    if not isinstance(contract, dict):
        raise AuthorityError("supplemental contract is not an object")

    base_pin = contract["generation_basis"]["accepted_0_2"]["contract"]
    base_contract_raw = (
        baseline / "control" / "B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json"
    ).read_bytes()
    if (
        len(base_contract_raw) != base_pin["byte_length"]
        or sha256_upper(base_contract_raw) != base_pin["raw_sha256"]
    ):
        raise AuthorityError("accepted 0.2 contract digest mismatch")
    base_contract = json.loads(base_contract_raw.decode("utf-8"))
    if not isinstance(base_contract, dict):
        raise AuthorityError("accepted 0.2 contract is not an object")

    matrix_pin = contract["composed_matrix_reference"]
    matrix_raw = (
        supplemental_root / "control" / "B1_COMPOSED_CAPABILITY_MATRIX_0_3.json"
    ).read_bytes()
    if (
        len(matrix_raw) != matrix_pin["byte_length"]
        or sha256_upper(matrix_raw) != matrix_pin["raw_sha256"]
    ):
        raise AuthorityError("composed matrix digest mismatch")

    resources = contract["content_addressed_schema_resolver"]["resources"]
    pins = {row["uri"]: row for row in resources if "raw_sha256" in row}
    packet_uri = next(uri for uri in pins if uri.startswith("urn:sha256:"))
    packet_pin = pins[packet_uri]
    projection_pin = pins["urn:primary-capability-baseline:shared-domain-projection:0.1"]
    packet_raw = (gate_root / "access" / "SANITIZED_PRIMARY_BASELINE_IMPLEMENTER_PACKET_0_1.json").read_bytes()
    projection_raw = (
        gate_root / "access" / "A2_SHARED_DOMAIN_VOCABULARY_BASELINE_PROJECTION_0_1.schema.json"
    ).read_bytes()
    if len(packet_raw) != packet_pin["byte_length"] or sha256_upper(packet_raw) != packet_pin["raw_sha256"]:
        raise AuthorityError("sanitized packet digest mismatch")
    if (
        len(projection_raw) != projection_pin["byte_length"]
        or sha256_upper(projection_raw) != projection_pin["raw_sha256"]
    ):
        raise AuthorityError("shared projection digest mismatch")
    return {
        "contract": contract,
        "base_contract": base_contract,
        "matrix": json.loads(matrix_raw.decode("utf-8")),
        "packet": json.loads(packet_raw.decode("utf-8")),
        "projection": json.loads(projection_raw.decode("utf-8")),
        "packet_uri": {"uri": packet_uri},
    }


@lru_cache(maxsize=1)
def operation_registry() -> dict[str, str]:
    rows = authority_documents()["contract"]["composed_operation_registry"]
    mapping = {row["operation_handle"]: row["obligation_id"] for row in rows}
    if len(mapping) != len(rows):
        raise AuthorityError("operation registry is not unique")
    return mapping


@lru_cache(maxsize=1)
def decision_table() -> dict[str, dict[str, Any]]:
    docs = authority_documents()
    table = list(
        docs["base_contract"]["semantic_decision_contract"]["operation_decision_table"]
    )
    table.extend(
        docs["contract"]["semantic_decision_contract_supplement"][
            "supplemental_operation_decision_table"
        ]
    )
    return {row["operation_handle"]: row["class_predicates"] for row in table}


@lru_cache(maxsize=1)
def effect_rules() -> dict[str, dict[str, Any]]:
    return authority_documents()["base_contract"]["semantic_decision_contract"]["effect_receipt_contract"][
        "operation_field_rules"
    ]


def _pointer(parent: str, token: str | int) -> str:
    text = str(token).replace("~", "~0").replace("/", "~1")
    return parent + "/" + text


def _strict_equal(left: Any, right: Any) -> bool:
    # JSON equality, recursive, with the boolean/integer distinction preserved
    # at every depth (JCS bytes are a faithful equality witness).
    return jcs_bytes(left) == jcs_bytes(right)


def _resolve_json_pointer(document: Any, fragment: str) -> Any:
    if fragment in ("", "#"):
        return document
    if not fragment.startswith("#/"):
        raise AuthorityError("unsupported schema fragment")
    node = document
    for encoded in fragment[2:].split("/"):
        token = encoded.replace("~1", "/").replace("~0", "~")
        node = node[token]
    return node


def _resolve_ref(ref: str, root: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    docs = authority_documents()
    contract = docs["contract"]
    packet_uri = docs["packet_uri"]["uri"]
    if ref == "urn:b1:semantic-decision-request:0.3":
        return contract["schemas"]["request_schema"], contract
    if ref == "urn:b1:semantic-decision-input:0.3":
        return contract["schemas"]["decision_input_schema"], contract
    if ref == "urn:b1:composed-inner-request:0.3":
        return contract["schemas"]["inner_request_schema_composed"]["schema"], contract
    if ref == "urn:b1:composed-inner-response:0.3":
        return contract["schemas"]["inner_response_schema_composed"]["schema"], contract
    if ref == packet_uri:
        return docs["packet"], docs["packet"]
    if ref.startswith(packet_uri + "#"):
        return _resolve_json_pointer(docs["packet"], "#" + ref.split("#", 1)[1]), docs["packet"]
    if ref == "urn:primary-capability-baseline:shared-domain-projection:0.1":
        return docs["projection"], docs["projection"]
    if ref.startswith("urn:primary-capability-baseline:shared-domain-projection:0.1#"):
        return _resolve_json_pointer(docs["projection"], "#" + ref.split("#", 1)[1]), docs["projection"]
    if ref.startswith("#"):
        return _resolve_json_pointer(root, ref), root
    raise AuthorityError("unlisted schema reference")


DATE_TIME_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)


def _is_type(instance: Any, schema_type: str) -> bool:
    return {
        "object": isinstance(instance, dict),
        "array": isinstance(instance, list),
        "string": isinstance(instance, str),
        "integer": isinstance(instance, int) and not isinstance(instance, bool),
        "number": isinstance(instance, int) and not isinstance(instance, bool),
        "boolean": isinstance(instance, bool),
        "null": instance is None,
    }.get(schema_type, False)


def schema_errors(
    instance: Any,
    schema: dict[str, Any],
    *,
    root: dict[str, Any] | None = None,
    pointer: str = "",
) -> list[str]:
    """Validate the closed Draft 2020-12 keyword subset used by the seals."""
    if root is None:
        root = schema
    errors: list[str] = []

    if "$ref" in schema:
        target, target_root = _resolve_ref(schema["$ref"], root)
        errors.extend(schema_errors(instance, target, root=target_root, pointer=pointer))

    if "const" in schema and not _strict_equal(instance, schema["const"]):
        errors.append(pointer)
    if "enum" in schema and not any(_strict_equal(instance, item) for item in schema["enum"]):
        errors.append(pointer)

    schema_type = schema.get("type")
    if schema_type is not None:
        allowed = [schema_type] if isinstance(schema_type, str) else schema_type
        if not any(_is_type(instance, item) for item in allowed):
            errors.append(pointer)
            return sorted(set(errors), key=lambda p: p.encode("utf-8"))

    if "oneOf" in schema:
        matches = [
            not schema_errors(instance, sub, root=root, pointer=pointer)
            for sub in schema["oneOf"]
        ]
        if sum(matches) != 1:
            errors.append(pointer)
    if "anyOf" in schema:
        if not any(not schema_errors(instance, sub, root=root, pointer=pointer) for sub in schema["anyOf"]):
            errors.append(pointer)
    for sub in schema.get("allOf", []):
        errors.extend(schema_errors(instance, sub, root=root, pointer=pointer))
    if "if" in schema and not schema_errors(instance, schema["if"], root=root, pointer=pointer):
        if "then" in schema:
            errors.extend(schema_errors(instance, schema["then"], root=root, pointer=pointer))
    elif "else" in schema:
        errors.extend(schema_errors(instance, schema["else"], root=root, pointer=pointer))

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(_pointer(pointer, key))
        properties = schema.get("properties", {})
        for key in sorted(instance, key=lambda item: item.encode("utf-8")):
            child_pointer = _pointer(pointer, key)
            if key in properties:
                errors.extend(
                    schema_errors(instance[key], properties[key], root=root, pointer=child_pointer)
                )
            elif schema.get("additionalProperties") is False:
                errors.append(child_pointer)
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(
                    schema_errors(
                        instance[key],
                        schema["additionalProperties"],
                        root=root,
                        pointer=child_pointer,
                    )
                )
        if "propertyNames" in schema:
            for key in sorted(instance, key=lambda item: item.encode("utf-8")):
                errors.extend(
                    schema_errors(key, schema["propertyNames"], root=root, pointer=_pointer(pointer, key))
                )

    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            errors.append(pointer)
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(pointer)
        if schema.get("uniqueItems"):
            seen: set[bytes] = set()
            for index, item in enumerate(instance):
                marker = jcs_bytes(item)
                if marker in seen:
                    errors.append(_pointer(pointer, index))
                seen.add(marker)
        prefix_items = schema.get("prefixItems", [])
        for index, sub in enumerate(prefix_items):
            if index < len(instance):
                errors.extend(
                    schema_errors(instance[index], sub, root=root, pointer=_pointer(pointer, index))
                )
        if isinstance(schema.get("items"), dict):
            start = len(prefix_items) if prefix_items else 0
            for index in range(start, len(instance)):
                errors.extend(
                    schema_errors(
                        instance[index], schema["items"], root=root, pointer=_pointer(pointer, index)
                    )
                )
        if "contains" in schema:
            count = sum(
                not schema_errors(item, schema["contains"], root=root, pointer="")
                for item in instance
            )
            if count < schema.get("minContains", 1) or count > schema.get("maxContains", len(instance)):
                errors.append(pointer)

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            errors.append(pointer)
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(pointer)
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(pointer)
        if schema.get("format") == "date-time" and DATE_TIME_RE.fullmatch(instance) is None:
            errors.append(pointer)

    if isinstance(instance, int) and not isinstance(instance, bool):
        if instance < schema.get("minimum", instance):
            errors.append(pointer)
        if instance > schema.get("maximum", instance):
            errors.append(pointer)

    return sorted(set(errors), key=lambda p: p.encode("utf-8"))


def validate_core_request(request: Any) -> list[str]:
    contract = authority_documents()["contract"]
    return schema_errors(request, contract["schemas"]["request_schema"], root=contract)


def validate_wrapper_request(request: Any) -> list[str]:
    contract = authority_documents()["contract"]
    return schema_errors(request, contract["schemas"]["wrapper_configuration_request_schema"], root=contract)


def validate_wrapper_response(response: Any) -> list[str]:
    contract = authority_documents()["contract"]
    return schema_errors(response, contract["schemas"]["wrapper_configuration_response_schema"], root=contract)


def validate_core_response(response: Any) -> list[str]:
    contract = authority_documents()["contract"]
    schema = contract["schemas"]["inner_response_schema_composed"]["schema"]
    return schema_errors(response, schema, root=contract)


# --- predicate evaluation -------------------------------------------------


def resolve_input_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise EvaluatorError(f"invalid pointer: {pointer}")
    node = document
    for encoded in pointer[1:].split("/"):
        token = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            if token not in node:
                raise EvaluatorError(f"missing path: {pointer}")
            node = node[token]
        elif isinstance(node, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", token) or int(token) >= len(node):
                raise EvaluatorError(f"missing path: {pointer}")
            node = node[int(token)]
        else:
            raise EvaluatorError(f"missing path: {pointer}")
    return node


def _jcs_set(items: list[Any]) -> set[bytes]:
    return {jcs_bytes(item) for item in items}


def _strict_base64_failure(value: Any) -> bool:
    if not isinstance(value, str) or not value.isascii():
        return True
    if re.fullmatch(r"[A-Za-z0-9+/]*={0,2}", value) is None or len(value) % 4 != 0:
        return True
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return True
    return base64.b64encode(decoded).decode("ascii") != value


def strict_base64_decode(value: str) -> bytes:
    if _strict_base64_failure(value):
        raise EvaluatorError("strict base64 decode failure past precedence")
    return base64.b64decode(value, validate=True)


def _eval_atomic(node: dict[str, Any], doc: Any) -> bool:
    op = node["op"]
    get = lambda path: resolve_input_pointer(doc, path)

    if op == "ABSENT":
        return get(node["path"]) is None
    if op == "PRESENT":
        return get(node["path"]) is not None
    if op in ("EQ", "NE"):
        if "path" in node:
            left = get(node["path"])
            right = node["value"] if "value" in node else get(node["right"])
        else:
            left, right = get(node["left"]), get(node["right"])
        equal = _strict_equal(left, right)
        return equal if op == "EQ" else not equal
    if op == "EQUAL_NON_NULL":
        left, right = get(node["left"]), get(node["right"])
        return left is not None and right is not None and _strict_equal(left, right)
    if op == "EMPTY":
        return len(get(node["path"])) == 0
    if op == "NOT_UNIQUE":
        items = get(node["path"])
        return len(_jcs_set(items)) != len(items)
    if op == "NOT_CONTAINS_ALL":
        have = _jcs_set(get(node["path"]))
        return any(jcs_bytes(value) not in have for value in node["values"])
    if op == "MEMBER":
        return jcs_bytes(get(node["value_path"])) in _jcs_set(get(node["collection_path"]))
    if op == "NOT_MEMBER":
        return jcs_bytes(get(node["value_path"])) not in _jcs_set(get(node["collection_path"]))
    if op == "MEMBER_VALUE":
        return jcs_bytes(get(node["path"])) in _jcs_set(node["values"])
    if op == "NOT_MEMBER_VALUE":
        return jcs_bytes(node["value"]) not in _jcs_set(get(node["collection_path"]))
    if op == "NOT_SUBSET":
        return not _jcs_set(get(node["left"])) <= _jcs_set(get(node["right"]))
    if op == "NOT_SUBSET_VALUES":
        return not _jcs_set(get(node["path"])) <= _jcs_set(node["values"])
    if op == "NOT_SET_EQ":
        return _jcs_set(get(node["left"])) != _jcs_set(get(node["right"]))
    if op == "INTERSECTS":
        return bool(_jcs_set(get(node["left"])) & _jcs_set(get(node["right"])))
    if op == "ANY_ABSENT":
        return any(get(path) is None for path in node["paths"])
    if op == "ANY_NULL":
        return any(item is None for item in get(node["path"]))
    if op == "NOT_PAIRWISE_DISTINCT_NON_NULL":
        values = [get(path) for path in node["paths"]]
        markers = [jcs_bytes(value) for value in values if value is not None]
        return len(set(markers)) != len(markers)
    if op == "LE":
        return get(node["left"]) <= get(node["right"])
    if op == "GE":
        return get(node["left"]) >= get(node["right"])
    if op == "LT_VALUE":
        return get(node["path"]) < node["value"]
    if op == "LE_VALUE":
        return get(node["path"]) <= node["value"]
    if op == "GT_VALUE":
        return get(node["path"]) > node["value"]
    if op == "NE_VALUE":
        return not _strict_equal(get(node["path"]), node["value"])
    if op == "OUTSIDE_HALF_OPEN":
        value = get(node["value"])
        return value < get(node["lower"]) or value >= get(node["upper"])
    if op == "NOT_STRICTLY_INCREASING":
        items = get(node["path"])
        if len(items) == 0:
            return True
        return any(items[i + 1] <= items[i] for i in range(len(items) - 1))
    if op == "COUNT_NE_PATH":
        return len(get(node["left"])) != len(get(node["right"]))
    if op == "NOT_FUNCTIONAL_BY":
        rows = get(node["path"])
        seen: dict[bytes, bytes] = {}
        for row in rows:
            key = jcs_bytes(row[node["key"]])
            value = jcs_bytes(row[node["value"]])
            if key in seen and seen[key] != value:
                return True
            seen[key] = value
        return False
    if op == "NOT_MEMBER_BY_KEY":
        target = jcs_bytes(get(node["value_path"]))
        return all(jcs_bytes(row[node["key"]]) != target for row in get(node["collection_path"]))
    if op == "ANY_NONPOSITIVE_SPAN":
        return any(row[node["end"]] <= row[node["start"]] for row in get(node["path"]))
    if op == "HAS_SELF_LOOP":
        return any(
            _strict_equal(edge[node["from"]], edge[node["to"]]) for edge in get(node["path"])
        )
    if op == "NOT_ACYCLIC":
        edges = get(node["path"])
        graph: dict[bytes, set[bytes]] = {}
        indegree: dict[bytes, int] = {}
        for edge in edges:
            src = jcs_bytes(edge[node["from"]])
            dst = jcs_bytes(edge[node["to"]])
            graph.setdefault(src, set())
            indegree.setdefault(src, indegree.get(src, 0))
            if dst not in graph.setdefault(src, set()):
                pass
            if dst not in graph[src]:
                graph[src].add(dst)
                indegree[dst] = indegree.get(dst, 0) + 1
            graph.setdefault(dst, set())
            indegree.setdefault(dst, indegree.get(dst, 0))
        queue = sorted(node_ for node_, deg in indegree.items() if deg == 0)
        removed = 0
        while queue:
            current = queue.pop()
            removed += 1
            for nxt in graph[current]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)
        return removed != len(indegree)
    if op == "NOT_NEXT_SEQUENCE":
        current = get(node["current"])
        prior = get(node["prior"])
        if prior is None:
            return not _strict_equal(current, node["initial"])
        return current != prior + 1
    if op == "NOT_ALL_EQUAL_PATH":
        target = jcs_bytes(get(node["value_path"]))
        return any(jcs_bytes(item) != target for item in get(node["collection_path"]))
    if op == "NOT_BOOLEAN_EQ_ENUM":
        boolean = get(node["boolean_path"])
        return boolean is not (_strict_equal(get(node["enum_path"]), node["true_value"]))
    if op == "ANY_PRESENT_STRICT_BASE64_DECODE_FAILURE":
        for path in node["paths"]:
            value = get(path)
            if value is None:
                continue
            if _strict_base64_failure(value):
                return True
        return False
    if op == "BASE64_SHA256_NE":
        raw = strict_base64_decode(get(node["base64_path"]))
        return sha256_upper(raw) != get(node["digest_path"])
    raise EvaluatorError(f"unknown operator: {op}")


def eval_predicate(node: dict[str, Any], doc: Any) -> bool:
    if "all" in node:
        return all(eval_predicate(child, doc) for child in node["all"])
    if "any" in node:
        return any(eval_predicate(child, doc) for child in node["any"])
    if "not" in node:
        return not eval_predicate(node["not"], doc)
    return _eval_atomic(node, doc)


def classify(operation_handle: str, decision_input: dict[str, Any]) -> tuple[str, dict[str, bool]]:
    """Evaluate the frozen class predicates strictly in precedence order and
    STOP at the first match. Later predicates may legitimately be non-total
    on requests an earlier class already resolved — e.g. BASE64_SHA256_NE is
    an evaluator error unless "malformed/absence precedence must already
    have resolved the request" — so evaluating them after a match leaks
    evaluator errors the contract says cannot occur (round-7 finding
    R7-DIV-001)."""
    predicates = decision_table()[operation_handle]
    first_match: dict[str, bool] = {}
    matched: str | None = None
    for class_name in CLASS_PRECEDENCE:
        if matched is None:
            fired = eval_predicate(predicates[class_name], decision_input)
            first_match[class_name] = fired
            if fired:
                matched = class_name
        else:
            first_match[class_name] = False
    return matched or "VALID", first_match


# --- parse-profile scanning -------------------------------------------------


_JSON_STRING_TOKEN = re.compile(r'"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"')
_JSON_NUMBER_TOKEN = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_JSON_INTEGER_FORM = re.compile(r"-?(?:0|[1-9][0-9]*)")
_JSON_WHITESPACE = " \t\n\r"


def scan_parse_profile(payload: str) -> dict[str, Any]:
    """Iterative strict scan of one JSON payload for the packet parse
    profile: NFC and number-model violations at their RFC6901 pointers,
    duplicate keys, canonical-byte violations (inter-token whitespace,
    member order, string escaping, unrepresentable Unicode, trailing
    content), and the packet's structural limits. No recursion anywhere,
    so detection survives nesting the tree parser cannot, and hook-level
    findings carry exact pointers (round-7 findings R7-DIV-002/003).
    complete=False marks a shape this scanner could not finish; detections
    gathered before that point remain valid and the tree parser owns the
    syntax verdict."""
    result: dict[str, Any] = {
        "nfc": [],
        "number": [],
        "duplicate": False,
        "canonical": False,
        "limit": False,
        "nesting_exceeded": False,
        "complete": False,
    }

    def check_string(token: str) -> str | None:
        """Decode one string token and record canonical-escaping violations;
        NFC judgment stays with the caller, which knows the right pointer."""
        try:
            decoded = json.loads(token)
        except ValueError:
            return None
        try:
            if json.dumps(decoded, ensure_ascii=False) != token:
                result["canonical"] = True
        except ValueError:
            result["canonical"] = True
        return decoded

    def check_number(token: str, pointer: str) -> None:
        if not _JSON_INTEGER_FORM.fullmatch(token) or token == "-0":
            result["number"].append(pointer)
            return
        digits = token.lstrip("-")
        if len(digits) > 17 or not SAFE_INTEGER_MIN <= int(token) <= SAFE_INTEGER_MAX:
            result["number"].append(pointer)

    n = len(payload)
    i = 0
    # Frames: ["obj", base_pointer, prev_key_utf16 | None, seen_keys, count]
    #      or ["arr", base_pointer, next_index]
    stack: list[list[Any]] = []
    pointer = ""
    state = "value"
    pending_key_pointer = ""
    while True:
        while i < n and payload[i] in _JSON_WHITESPACE:
            result["canonical"] = True
            i += 1
        if state == "after" and not stack:
            state = "done"
        if i >= n:
            if state == "done":
                result["complete"] = True
            return result
        ch = payload[i]
        if state == "done":
            return result  # trailing content: the tree parser owns ERR_JSON
        if state == "value":
            if ch == '"':
                match = _JSON_STRING_TOKEN.match(payload, i)
                if match is None:
                    return result
                decoded = check_string(match.group())
                if decoded is None:
                    return result
                if unicodedata.normalize("NFC", decoded) != decoded:
                    result["nfc"].append(pointer)
                i = match.end()
                state = "after"
            elif ch == "{":
                if len(stack) + 1 > MAX_NESTING:
                    result["limit"] = True
                    result["nesting_exceeded"] = True
                stack.append(["obj", pointer, None, set(), 0])
                i += 1
                state = "first_key"
            elif ch == "[":
                if len(stack) + 1 > MAX_NESTING:
                    result["limit"] = True
                    result["nesting_exceeded"] = True
                stack.append(["arr", pointer, 0])
                i += 1
                state = "first_item"
            elif payload.startswith("true", i):
                i += 4
                state = "after"
            elif payload.startswith("false", i):
                i += 5
                state = "after"
            elif payload.startswith("null", i):
                i += 4
                state = "after"
            elif payload.startswith("NaN", i):
                result["number"].append(pointer)
                i += 3
                state = "after"
            elif payload.startswith("Infinity", i):
                result["number"].append(pointer)
                i += 8
                state = "after"
            elif payload.startswith("-Infinity", i):
                result["number"].append(pointer)
                i += 9
                state = "after"
            else:
                match = _JSON_NUMBER_TOKEN.match(payload, i)
                if match is None or match.end() == i:
                    return result
                check_number(match.group(), pointer)
                i = match.end()
                state = "after"
        elif state in ("first_key", "next_key"):
            frame = stack[-1]
            if ch == "}" and state == "first_key":
                stack.pop()
                i += 1
                state = "after"
                continue
            if ch != '"':
                return result
            match = _JSON_STRING_TOKEN.match(payload, i)
            if match is None:
                return result
            decoded = check_string(match.group())
            if decoded is None:
                return result
            child_pointer = _pointer(frame[1], decoded)
            if unicodedata.normalize("NFC", decoded) != decoded:
                result["nfc"].append(child_pointer)
            try:
                encoded = decoded.encode("utf-16-be")
            except UnicodeEncodeError:
                result["canonical"] = True
                encoded = None
            if decoded in frame[3]:
                result["duplicate"] = True
            frame[3].add(decoded)
            if encoded is not None:
                if frame[2] is not None and encoded < frame[2]:
                    result["canonical"] = True
                frame[2] = encoded
            frame[4] += 1
            if frame[4] > MAX_MEMBERS_OR_ITEMS:
                result["limit"] = True
            pending_key_pointer = child_pointer
            i = match.end()
            state = "colon"
        elif state == "colon":
            if ch != ":":
                return result
            pointer = pending_key_pointer
            i += 1
            state = "value"
        elif state == "first_item":
            frame = stack[-1]
            if ch == "]":
                stack.pop()
                i += 1
                state = "after"
            else:
                pointer = _pointer(frame[1], frame[2])
                state = "value"
                continue
        elif state == "after":
            frame = stack[-1]
            if frame[0] == "obj":
                if ch == ",":
                    i += 1
                    state = "next_key"
                elif ch == "}":
                    stack.pop()
                    i += 1
                else:
                    return result
            else:
                frame[2] += 1
                if frame[2] > MAX_MEMBERS_OR_ITEMS:
                    result["limit"] = True
                if ch == ",":
                    i += 1
                    pointer = _pointer(frame[1], frame[2])
                    state = "value"
                elif ch == "]":
                    stack.pop()
                    i += 1
                else:
                    return result
        else:  # pragma: no cover - unreachable state
            return result


# --- envelope binding -----------------------------------------------------


def _registry_majority_row(
    bound_fields: tuple[tuple[str, Any, str], ...],
    preferred_operation: Any = None,
) -> tuple[str, str] | None:
    """Registry row that the most bound echo fields agree on.

    The accepted fixture pack completes the envelope-binding prose this way:
    when the five echo fields disagree, the deviant MINORITY fields are
    blamed at their own leaf pointers (the SEM-COMP-05 outer-operation
    mutation pins '/operation_handle'), so a majority consensus — not the
    outer field alone — anchors the judgment. Where the pack is silent (an
    exact tie), the tie prefers the outer operation_handle's row, honoring
    the contract's "resolve operation_handle through operation_registry"
    in the only configuration the pack leaves free
    (terminal round-5 finding B1-IMPL-FINAL2-DIV-004, adjudicated)."""
    registry = operation_registry()
    best_row: tuple[str, str] | None = None
    best_score = -1

    def row_score(operation_handle: str, obligation_id: str) -> int:
        return sum(
            1
            for _, value, kind in bound_fields
            if value == (operation_handle if kind == "operation" else obligation_id)
        )

    for operation_handle in sorted(registry, key=lambda item: item.encode("utf-8")):
        obligation_id = registry[operation_handle]
        score = row_score(operation_handle, obligation_id)
        if score > best_score:
            best_score = score
            best_row = (operation_handle, obligation_id)
    if isinstance(preferred_operation, str) and preferred_operation in registry:
        preferred = (preferred_operation, registry[preferred_operation])
        if preferred != best_row and row_score(*preferred) == best_score:
            best_row = preferred
    return best_row


def envelope_binding_errors(request: dict[str, Any]) -> list[str]:
    """Return mismatched binding pointers, UTF-8 sorted (ERR_SCHEMA).

    The operation/obligation fields are judged against the registry row
    from _registry_majority_row (majority of the five bound echo fields,
    ties preferring the outer operation_handle's row), so the reported
    pointer names the inconsistent field rather than every echo of the
    disagreement (SEM-COMP-05: lexicographically first mismatched pointer).
    """
    mismatches: list[str] = []
    inner = request["inner_request"]
    decision_input = request["decision_input"]
    if inner.get("request_id") != request["request_id"]:
        mismatches.append("/inner_request/request_id")
    bound_fields = (
        ("/operation_handle", request["operation_handle"], "operation"),
        ("/obligation_id", request["obligation_id"], "obligation"),
        ("/decision_input/operation_handle", decision_input.get("operation_handle"), "operation"),
        ("/decision_input/obligation_id", decision_input.get("obligation_id"), "obligation"),
        ("/inner_request/operation_handle", inner.get("operation_handle"), "operation"),
    )
    best_row = _registry_majority_row(bound_fields, request["operation_handle"])
    if best_row is None:
        mismatches.extend(pointer for pointer, _, _ in bound_fields)
    else:
        for pointer, value, kind in bound_fields:
            expected = best_row[0] if kind == "operation" else best_row[1]
            if value != expected:
                mismatches.append(pointer)
    inner_raw = sha256_upper(jcs_bytes(inner) + b"\n")
    if request["inner_request_raw_sha256"] != inner_raw:
        mismatches.append("/inner_request_raw_sha256")
    inner_input = sha256_upper(jcs_bytes(inner["input"]))
    if request["inner_input_sha256"] != inner_input:
        mismatches.append("/inner_input_sha256")
    return sorted(set(mismatches), key=lambda p: p.encode("utf-8"))


def selector_repaired_request(request: dict[str, Any]) -> dict[str, Any] | None:
    """Deep copy of a core request with the five registry-bound echo fields
    set to the majority registry row (ties preferring the outer
    operation_handle's row) — exactly the inconsistency that
    envelope_binding_errors blames at leaf level removed, nothing else
    changed. A combinator-site schema failure that persists on the repaired
    copy is an independent violation, not an echo of the binding finding."""
    try:
        repaired = json.loads(jcs_bytes(request).decode("utf-8"))
    except (TypeError, ValueError, UnicodeError, RecursionError):
        return None
    if not isinstance(repaired, dict):
        return None
    inner = repaired.get("inner_request")
    decision_input = repaired.get("decision_input")
    bound_fields = (
        ("/operation_handle", repaired.get("operation_handle"), "operation"),
        ("/obligation_id", repaired.get("obligation_id"), "obligation"),
        (
            "/decision_input/operation_handle",
            decision_input.get("operation_handle") if isinstance(decision_input, dict) else None,
            "operation",
        ),
        (
            "/decision_input/obligation_id",
            decision_input.get("obligation_id") if isinstance(decision_input, dict) else None,
            "obligation",
        ),
        (
            "/inner_request/operation_handle",
            inner.get("operation_handle") if isinstance(inner, dict) else None,
            "operation",
        ),
    )
    row = _registry_majority_row(bound_fields, repaired.get("operation_handle"))
    if row is None:
        return None
    operation_handle, obligation_id = row
    repaired["operation_handle"] = operation_handle
    repaired["obligation_id"] = obligation_id
    if isinstance(inner, dict):
        inner["operation_handle"] = operation_handle
    if isinstance(decision_input, dict):
        decision_input["operation_handle"] = operation_handle
        decision_input["obligation_id"] = obligation_id
    return repaired


# --- response construction ------------------------------------------------


def _effect_receipt(request: dict[str, Any], behavior_class: str) -> str | None:
    obligation_id = request["obligation_id"]
    rules = effect_rules()
    if behavior_class != "VALID" or obligation_id not in rules:
        return None
    rule = rules[obligation_id]
    decision_input = request["decision_input"]
    fields: dict[str, Any] = {}
    for derivation in rule["field_derivations"]:
        value = resolve_input_pointer(decision_input, derivation["source_path"])
        if derivation["transform"] == "IDENTITY":
            fields[derivation["target_key"]] = value
        elif derivation["transform"] == "STRICT_BASE64_DECODE_SHA256_UPPER":
            fields[derivation["target_key"]] = sha256_upper(strict_base64_decode(value))
        else:
            raise EvaluatorError(f"unknown transform: {derivation['transform']}")
    preimage = {
        "domain": EFFECT_DOMAIN,
        "operation_handle": request["operation_handle"],
        "obligation_id": obligation_id,
        "request_id": request["request_id"],
        "decision_input_sha256": sha256_upper(jcs_bytes(decision_input)),
        "operation_fields_object": fields,
    }
    contract = authority_documents()["base_contract"]
    preimage_schema = contract["semantic_decision_contract"]["effect_receipt_contract"][
        "preimage_object_schema"
    ]
    if schema_errors(preimage, preimage_schema, root=contract):
        raise EvaluatorError("effect receipt preimage does not validate")
    if schema_errors(fields, rule["closed_schema"], root=contract):
        raise EvaluatorError("effect receipt fields do not validate")
    return sha256_upper(jcs_bytes(preimage))


def _semantic_output(request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    behavior_class, _ = classify(request["operation_handle"], request["decision_input"])
    mapped = RESULT_CONTRACT[behavior_class]
    unresolved = (
        [f"{request['obligation_id']}: authoritative semantic basis is absent or inconsistent"]
        if behavior_class == "OMISSION_OR_INCOMPLETE"
        else []
    )
    output = {
        "operation_handle": request["operation_handle"],
        "obligation_id": request["obligation_id"],
        "status": mapped["status"],
        "result_object": {"behavior_class": behavior_class, "conclusion": mapped["conclusion"]},
        "record_references": [],
        "unresolved_reasons": unresolved,
        "effect_receipt_sha256": _effect_receipt(request, behavior_class),
    }
    return output, mapped


def build_core_response(request: dict[str, Any]) -> dict[str, Any]:
    output, mapped = _semantic_output(request)
    response = {
        "format_version": CORE_RESPONSE_FORMAT,
        "request_id": request["request_id"],
        "ok": True,
        "result": mapped["result"],
        "errors": [],
        "output": output,
        "exit_code": mapped["exit_code"],
        "receipt_sha256": ZERO64,
    }
    response["receipt_sha256"] = self_zero_sha256(response, "receipt_sha256")
    return response


def build_wrapper_response(request: dict[str, Any]) -> dict[str, Any]:
    semantic = request["semantic_request"]
    output, mapped = _semantic_output(semantic)
    response = {
        "format_version": WRAPPER_RESPONSE_FORMAT,
        "request_id": request["request_id"],
        "configuration": request["configuration"],
        "operation_handle": request["operation_handle"],
        "obligation_id": output["obligation_id"],
        "ok": True,
        "result": mapped["result"],
        "errors": [],
        "output": {
            "payload": output["result_object"],
            "record_refs": output["record_references"],
            "unresolved_reasons": output["unresolved_reasons"],
            "effect_receipt_sha256": output["effect_receipt_sha256"],
        },
        "exit_code": mapped["exit_code"],
        "response_sha256": ZERO64,
    }
    response["response_sha256"] = self_zero_sha256(response, "response_sha256")
    return response


def error_object(code: str, pointer: str = "") -> dict[str, Any]:
    message, precedence = ERRORS[code]
    return {"code": code, "pointer": pointer, "message": message, "precedence": precedence}


def build_core_error_response(code: str, pointer: str = "", request_id: str | None = None) -> dict[str, Any]:
    response = {
        "format_version": CORE_RESPONSE_FORMAT,
        "request_id": request_id or "RUN_000000000000000000000000",
        "ok": False,
        "result": "INCOMPLETE",
        "errors": [error_object(code, pointer)],
        "output": None,
        "exit_code": 3 if code == "ERR_INTERNAL" else 2,
        "receipt_sha256": ZERO64,
    }
    response["receipt_sha256"] = self_zero_sha256(response, "receipt_sha256")
    return response


def build_wrapper_error_response(
    code: str,
    pointer: str,
    request: dict[str, Any] | None,
) -> dict[str, Any]:
    request = request if isinstance(request, dict) else {}
    operation = request.get("operation_handle")
    registry = operation_registry()
    # isinstance guards first: schema-invalid selector values may be
    # unhashable (e.g. a list), and hashing them here would throw the very
    # internal error this builder exists to avoid (round-9 R9-DIV-001).
    if not isinstance(operation, str) or operation not in registry:
        operation = min(registry, key=lambda item: item.encode("utf-8"))
    configuration = request.get("configuration")
    if not isinstance(configuration, str) or configuration not in {"B1", "B1-ATTENTION"}:
        configuration = "B1"
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or REQUEST_ID_RE.fullmatch(request_id) is None:
        request_id = "RUN_000000000000000000000000"
    response = {
        "format_version": WRAPPER_RESPONSE_FORMAT,
        "request_id": request_id,
        "configuration": configuration,
        "operation_handle": operation,
        "obligation_id": registry[operation],
        "ok": False,
        "result": "INCOMPLETE",
        "errors": [error_object(code, pointer)],
        "output": None,
        "exit_code": 3 if code == "ERR_INTERNAL" else 2,
        "response_sha256": ZERO64,
    }
    response["response_sha256"] = self_zero_sha256(response, "response_sha256")
    return response


# --- wrapper transcript binding (contract evaluator steps) ----------------


def card_binding_valid(request: dict[str, Any]) -> bool:
    if request.get("configuration") == "B1":
        return request.get("attention_card") is None
    if request.get("configuration") != "B1-ATTENTION":
        return False
    card = request.get("attention_card")
    if not isinstance(card, dict) or "card_sha256" not in card:
        return False
    return card["card_sha256"] == self_zero_sha256(card, "card_sha256")


def _strict_wire_value(raw: bytes) -> Any | None:
    """Decode one recorded wire artifact under the strict parse profile.

    The wrapper transcript evaluator's first step requires the exact
    request/response bytes to be STRICT UTF-8 JSON; a permissive decode
    accepted duplicate-key smuggling and leaked RecursionError on deep
    bytes (round-7 finding R7-DIV-004). Returns None whenever the bytes
    are anything but one canonical, profile-clean JSON value plus LF."""
    if not raw or len(raw) > MAX_INPUT_BYTES:
        return None
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None
    if raw.startswith(b"\xef\xbb\xbf") or not text.endswith("\n"):
        return None
    payload = text[:-1]
    scan = scan_parse_profile(payload)
    if (
        scan["duplicate"]
        or scan["canonical"]
        or not scan["complete"]
        or scan["nfc"]
        or scan["number"]
        or scan["limit"]
    ):
        return None
    try:
        return json.loads(payload)
    except (ValueError, RecursionError):
        return None


def validate_wrapper_transcript_binding(
    request_raw: bytes,
    response_raw: bytes,
    transcript: dict[str, Any],
) -> tuple[bool, str | None]:
    request = _strict_wire_value(request_raw)
    response = _strict_wire_value(response_raw)
    if not isinstance(request, dict) or not isinstance(response, dict):
        return False, "ERR_SCHEMA"
    if validate_wrapper_request(request) or validate_wrapper_response(response):
        return False, "ERR_SCHEMA"
    semantic = request["semantic_request"]
    if validate_core_request(semantic) or envelope_binding_errors(semantic):
        return False, "ERR_SCHEMA"
    contract = authority_documents()["contract"]
    if schema_errors(transcript, contract["schemas"]["wrapper_transcript_schema"], root=contract):
        return False, None
    operation = request["operation_handle"]
    obligation = operation_registry().get(operation)
    if (
        transcript["request_id"] != response["request_id"]
        or response["request_id"] != request["request_id"]
        or request["request_id"] != semantic["request_id"]
    ):
        return False, None
    if transcript["configuration"] != response["configuration"] or response["configuration"] != request["configuration"]:
        return False, None
    if (
        transcript["operation_handle"] != response["operation_handle"]
        or response["operation_handle"] != operation
        or operation != semantic["operation_handle"]
    ):
        return False, None
    if obligation is None or transcript["obligation_id"] != response["obligation_id"] or response["obligation_id"] != obligation:
        return False, None
    if response["response_sha256"] != self_zero_sha256(response, "response_sha256"):
        return False, None
    if transcript["normalized_response_sha256"] != response["response_sha256"]:
        return False, None
    if not card_binding_valid(request):
        return False, None
    expected_card = None if request["configuration"] == "B1" else request["attention_card"]["card_sha256"]
    if transcript["attention_card_sha256"] != expected_card:
        return False, None
    if transcript["request_raw_sha256"] != sha256_upper(request_raw):
        return False, None
    if transcript["response_raw_sha256"] != sha256_upper(response_raw):
        return False, None
    if transcript["record_sha256"] != self_zero_sha256(transcript, "record_sha256"):
        return False, None
    return True, None


def shared_wrapper_request_projection(request: dict[str, Any]) -> dict[str, Any]:
    projection = dict(request)
    projection.pop("configuration", None)
    projection.pop("attention_card", None)
    return projection
