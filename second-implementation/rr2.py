"""Author-separated receiver-reliance implementation.

This module is a standard-library-only interpreter for the public 0.2/0.3
contracts.  It intentionally contains no frozen implementation imports and
no fixture answer table.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Any


ZERO64 = "0" * 64
DEFAULT_REQUEST_ID = "RUN_" + "0" * 24
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
REQUEST_ID_RE = re.compile(r"^RUN_[A-F0-9]{24}$")
SAFE_MIN = -9007199254740991
SAFE_MAX = 9007199254740991
SAFE_ABS_DIGITS = "9007199254740991"
SUPPLEMENTAL_CONTRACT_REL = "supplemental-0_3/control/B1_SUPPLEMENTAL_COMPARATOR_CONTRACT_0_3.json"
PRIMARY_CONTRACT_REL = "baseline-run/control/B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json"
PACKET_REL = "access/SANITIZED_PRIMARY_BASELINE_IMPLEMENTER_PACKET_0_1.json"
PROJECTION_REL = "access/A2_SHARED_DOMAIN_VOCABULARY_BASELINE_PROJECTION_0_1.schema.json"
AUTHORITY_PATHS = (SUPPLEMENTAL_CONTRACT_REL, PRIMARY_CONTRACT_REL, PACKET_REL, PROJECTION_REL)

# This is the one bootstrap pin that cannot be obtained from the supplemental
# contract itself.  It is the external final-contract digest supplied by the
# accepted supplemental fixture receipt.  That receipt declares no contract
# byte length, so the runtime intentionally does not invent one.
SUPPLEMENTAL_CONTRACT_SHA256 = "6B2CAD02DDE7388D63D66E4863E5233CFBD1DC413575D9D260DB9799C7023A12"

PACKET_URI = "urn:sha256:73A4FF4DD8ABA41D0F68414CB754EFCDF9807FAE73354F1959420B16C5F359F3"
PROJECTION_URI = "urn:primary-capability-baseline:shared-domain-projection:0.1"


def _utf16_key(value: str) -> bytes:
    return value.encode("utf-16-be")


def _json_string(value: str) -> str:
    # CPython's encoder uses the RFC 8785 spellings for the integer-only
    # profile admitted by this contract.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def jcs(value: Any) -> bytes:
    output: list[str] = []
    tasks: list[tuple[str, Any]] = [("value", value)]
    while tasks:
        kind, node = tasks.pop()
        if kind == "text":
            output.append(node)
        elif node is None:
            output.append("null")
        elif node is True:
            output.append("true")
        elif node is False:
            output.append("false")
        elif isinstance(node, int) and not isinstance(node, bool):
            output.append(str(node))
        elif isinstance(node, str):
            output.append(_json_string(node))
        elif isinstance(node, list):
            output.append("[")
            tasks.append(("text", "]"))
            for index in range(len(node) - 1, -1, -1):
                tasks.append(("value", node[index]))
                if index:
                    tasks.append(("text", ","))
        elif isinstance(node, dict):
            output.append("{")
            tasks.append(("text", "}"))
            names = sorted(node, key=_utf16_key)
            for index in range(len(names) - 1, -1, -1):
                name = names[index]
                tasks.append(("value", node[name]))
                tasks.append(("text", ":"))
                tasks.append(("text", _json_string(name)))
                if index:
                    tasks.append(("text", ","))
        else:
            raise TypeError(f"not in the integer-only JCS domain: {type(node).__name__}")
    return "".join(output).encode("utf-8")


def sha256_upper(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _pointer_child(parent: Any, token: str) -> tuple[Any, str]:
    return parent, token


def _pointer_text(link: Any) -> str:
    tokens: list[str] = []
    while link is not None:
        link, token = link
        tokens.append(token)
    return "" if not tokens else "/" + "/".join(reversed(tokens))


def pointer_get(root: Any, pointer: str) -> Any:
    node = root
    if pointer == "":
        return node
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


class ParseFault(Exception):
    pass


class DuplicateFault(ParseFault):
    pass


class StrictParser:
    """Small JSON parser that exposes the contract's error layers.

    Duplicate keys are rejected as soon as the second complete member name
    is seen.  This is required even when the second member is truncated.
    """

    def __init__(self, text: str):
        self.text = text
        self.i = 0
        self.number_pointers: list[str] = []
        self.max_depth = 0
        self.member_count = 0

    def parse(self) -> Any:
        missing = object()
        root: Any = missing
        stack: list[dict[str, Any]] = []
        expect_value = True
        value_pointer = None

        def deliver(value: Any) -> None:
            nonlocal root
            if not stack:
                if root is not missing:
                    raise ParseFault
                root = value
                return
            frame = stack[-1]
            if frame["kind"] == "array" and frame["state"] == "value":
                frame["value"].append(value)
                frame["state"] = "comma_or_end"
                return
            if frame["kind"] == "object" and frame["state"] == "value":
                frame["value"][frame["key"]] = value
                frame["state"] = "comma_or_end"
                return
            raise ParseFault

        def close_frame() -> None:
            frame = stack.pop()
            deliver(frame["value"])

        while True:
            if expect_value:
                if self.i >= len(self.text):
                    raise ParseFault
                ch = self.text[self.i]
                if ch == "{":
                    self.i += 1
                    stack.append({"kind": "object", "state": "key_or_end", "value": {}, "seen": set(), "pointer": value_pointer})
                    self.max_depth = max(self.max_depth, len(stack))
                    expect_value = False
                    continue
                if ch == "[":
                    self.i += 1
                    stack.append({"kind": "array", "state": "value_or_end", "value": [], "pointer": value_pointer})
                    self.max_depth = max(self.max_depth, len(stack))
                    expect_value = False
                    continue
                if ch == '"':
                    deliver(self._string())
                elif ch == "t" and self.text.startswith("true", self.i):
                    self.i += 4; deliver(True)
                elif ch == "f" and self.text.startswith("false", self.i):
                    self.i += 5; deliver(False)
                elif ch == "n" and self.text.startswith("null", self.i):
                    self.i += 4; deliver(None)
                elif ch == "-" or "0" <= ch <= "9":
                    deliver(self._number(value_pointer))
                else:
                    raise ParseFault
                expect_value = False
                continue

            if not stack:
                break
            frame = stack[-1]
            state = frame["state"]
            if frame["kind"] == "object":
                if state in {"key_or_end", "key_required"}:
                    if self.i < len(self.text) and self.text[self.i] == "}" and state == "key_or_end":
                        self.i += 1; close_frame(); continue
                    if self.i >= len(self.text) or self.text[self.i] != '"':
                        raise ParseFault
                    key = self._string()
                    if key in frame["seen"]:
                        raise DuplicateFault
                    frame["seen"].add(key)
                    self.member_count += 1
                    frame["key"] = key
                    frame["state"] = "colon"
                    continue
                if state == "colon":
                    if self.i >= len(self.text) or self.text[self.i] != ":":
                        raise ParseFault
                    self.i += 1
                    frame["state"] = "value"
                    value_pointer = _pointer_child(frame["pointer"], pointer_escape(frame["key"]))
                    expect_value = True
                    continue
                if state == "comma_or_end":
                    if self.i < len(self.text) and self.text[self.i] == "}":
                        self.i += 1; close_frame(); continue
                    if self.i >= len(self.text) or self.text[self.i] != ",":
                        raise ParseFault
                    self.i += 1
                    frame["state"] = "key_required"
                    continue
            else:
                if state in {"value_or_end", "value_required"}:
                    if self.i < len(self.text) and self.text[self.i] == "]" and state == "value_or_end":
                        self.i += 1; close_frame(); continue
                    frame["state"] = "value"
                    value_pointer = _pointer_child(frame["pointer"], str(len(frame["value"])))
                    expect_value = True
                    continue
                if state == "comma_or_end":
                    if self.i < len(self.text) and self.text[self.i] == "]":
                        self.i += 1; close_frame(); continue
                    if self.i >= len(self.text) or self.text[self.i] != ",":
                        raise ParseFault
                    self.i += 1
                    frame["state"] = "value_required"
                    continue
            raise ParseFault

        if root is missing:
            raise ParseFault
        value = root
        if self.i != len(self.text):
            raise ParseFault
        return value

    def _string(self) -> str:
        self.i += 1
        chars: list[str] = []
        while self.i < len(self.text):
            ch = self.text[self.i]
            self.i += 1
            if ch == '"':
                return "".join(chars)
            if ord(ch) < 0x20:
                raise ParseFault
            if ch != "\\":
                if 0xD800 <= ord(ch) <= 0xDFFF:
                    raise ParseFault
                chars.append(ch)
                continue
            if self.i >= len(self.text):
                raise ParseFault
            esc = self.text[self.i]
            self.i += 1
            basic = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
            if esc in basic:
                chars.append(basic[esc])
                continue
            if esc != "u" or self.i + 4 > len(self.text):
                raise ParseFault
            token = self.text[self.i:self.i + 4]
            if not re.fullmatch(r"[0-9A-Fa-f]{4}", token):
                raise ParseFault
            self.i += 4
            code = int(token, 16)
            if 0xD800 <= code <= 0xDBFF:
                if not self.text.startswith("\\u", self.i) or self.i + 6 > len(self.text):
                    raise ParseFault
                low_token = self.text[self.i + 2:self.i + 6]
                if not re.fullmatch(r"[0-9A-Fa-f]{4}", low_token):
                    raise ParseFault
                low = int(low_token, 16)
                if not 0xDC00 <= low <= 0xDFFF:
                    raise ParseFault
                self.i += 6
                chars.append(chr(0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)))
            elif 0xDC00 <= code <= 0xDFFF:
                raise ParseFault
            else:
                chars.append(chr(code))
        raise ParseFault

    def _number(self, ptr: Any) -> Any:
        start = self.i
        if self.text[self.i] == "-":
            self.i += 1
            if self.i >= len(self.text):
                raise ParseFault
        if self.text[self.i] == "0":
            self.i += 1
            if self.i < len(self.text) and "0" <= self.text[self.i] <= "9":
                raise ParseFault
        elif "1" <= self.text[self.i] <= "9":
            while self.i < len(self.text) and "0" <= self.text[self.i] <= "9":
                self.i += 1
        else:
            raise ParseFault
        is_fractional = False
        if self.i < len(self.text) and self.text[self.i] == ".":
            is_fractional = True
            self.i += 1
            digit_start = self.i
            while self.i < len(self.text) and "0" <= self.text[self.i] <= "9":
                self.i += 1
            if self.i == digit_start:
                raise ParseFault
        if self.i < len(self.text) and self.text[self.i] in "eE":
            is_fractional = True
            self.i += 1
            if self.i < len(self.text) and self.text[self.i] in "+-":
                self.i += 1
            digit_start = self.i
            while self.i < len(self.text) and "0" <= self.text[self.i] <= "9":
                self.i += 1
            if self.i == digit_start:
                raise ParseFault
        token = self.text[start:self.i]
        if is_fractional or token == "-0":
            self.number_pointers.append(_pointer_text(ptr))
            # Invalid-number precedence is decided after the complete raw JSON
            # grammar is known.  A harmless placeholder lets parsing continue
            # without invoking Decimal on attacker-controlled digit strings.
            return 0
        digits = token[1:] if token.startswith("-") else token
        if len(digits) > len(SAFE_ABS_DIGITS) or (len(digits) == len(SAFE_ABS_DIGITS) and digits > SAFE_ABS_DIGITS):
            self.number_pointers.append(_pointer_text(ptr))
            # Never pass an overlong decimal token to int(); Python's
            # interpreter-configured max-str-digits guard is not contractual.
            return 0
        return int(token)


def _nfc_pointers(node: Any) -> list[str]:
    failures: list[str] = []
    stack = [(node, None)]
    while stack:
        current, current_link = stack.pop()
        if isinstance(current, str):
            if unicodedata.normalize("NFC", current) != current:
                failures.append(_pointer_text(current_link))
        elif isinstance(current, list):
            for index in range(len(current) - 1, -1, -1):
                stack.append((current[index], _pointer_child(current_link, str(index))))
        elif isinstance(current, dict):
            items = list(current.items())
            for name, item in reversed(items):
                child_link = _pointer_child(current_link, pointer_escape(name))
                stack.append((item, child_link))
                stack.append((name, child_link))
    return failures


def _equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if type(left) is not type(right):
        return False
    return left == right


class Contracts:
    def __init__(self, repo_root: Path | None = None):
        self.root = repo_root or Path(__file__).resolve().parents[1]
        # The supplemental contract is authenticated first by its external
        # acceptance digest.  Only those verified bytes may declare the
        # primary-contract, packet, and projection pins.
        self.supp = self._load_pinned(SUPPLEMENTAL_CONTRACT_REL, None, SUPPLEMENTAL_CONTRACT_SHA256)
        accepted_primary = self.supp["generation_basis"]["accepted_0_2"]["contract"]
        primary_length, primary_sha256 = self._declared_pin(
            accepted_primary,
            expected_path="../../baseline-run/control/B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json",
            rel=PRIMARY_CONTRACT_REL,
        )
        packet_length, packet_sha256 = self._resolver_pin(
            PACKET_URI,
            expected_path="../../access/SANITIZED_PRIMARY_BASELINE_IMPLEMENTER_PACKET_0_1.json",
            rel=PACKET_REL,
        )
        projection_length, projection_sha256 = self._resolver_pin(
            PROJECTION_URI,
            expected_path="../../access/A2_SHARED_DOMAIN_VOCABULARY_BASELINE_PROJECTION_0_1.schema.json",
            rel=PROJECTION_REL,
        )
        self.base = self._load_pinned(PRIMARY_CONTRACT_REL, primary_length, primary_sha256)
        self.packet = self._load_pinned(PACKET_REL, packet_length, packet_sha256)
        self.projection = self._load_pinned(PROJECTION_REL, projection_length, projection_sha256)
        self.docs: dict[str, Any] = {
            "urn:sha256:73A4FF4DD8ABA41D0F68414CB754EFCDF9807FAE73354F1959420B16C5F359F3": self.packet,
            "urn:primary-capability-baseline:shared-domain-projection:0.1": self.projection,
            "urn:b1:semantic-decision-input:0.2": self.base["schemas"]["decision_input_schema"],
            "urn:b1:semantic-decision-request:0.2": self.base["schemas"]["request_schema"],
        }
        for owner in (self.base, self.supp):
            for schema in owner.get("schemas", {}).values():
                if isinstance(schema, dict) and schema.get("$id"):
                    self.docs[schema["$id"]] = schema
        self.docs["urn:b1:composed-inner-request:0.3"] = self.supp["schemas"]["inner_request_schema_composed"]["schema"]
        self.docs["urn:b1:composed-inner-response:0.3"] = self.supp["schemas"]["inner_response_schema_composed"]["schema"]
        for doc in (self.base, self.supp, self.packet, self.projection):
            ident = doc.get("$id") if isinstance(doc, dict) else None
            if ident:
                self.docs[ident] = doc
        self.rows: dict[str, dict[str, Any]] = {}
        for row in self.base["semantic_decision_contract"]["operation_decision_table"]:
            self.rows[row["obligation_id"]] = row
        for row in self.supp["semantic_decision_contract_supplement"]["supplemental_operation_decision_table"]:
            self.rows[row["obligation_id"]] = row
        self.registry = {row["operation_handle"]: row["obligation_id"] for row in self.base["operation_registry"]}
        self.registry.update({row["operation_handle"]: row["obligation_id"] for row in self.supp["supplemental_operation_registry"]})

    @staticmethod
    def _declared_pin(declaration: Any, *, expected_path: str, rel: str) -> tuple[int, str]:
        if not isinstance(declaration, dict) or declaration.get("path") != expected_path:
            raise ValueError("authority declaration mismatch: " + rel)
        length = declaration.get("byte_length")
        digest = declaration.get("raw_sha256")
        if not isinstance(length, int) or length < 1 or not isinstance(digest, str) or re.fullmatch(r"[A-F0-9]{64}", digest) is None:
            raise ValueError("authority declaration mismatch: " + rel)
        return length, digest

    def _resolver_pin(self, uri: str, *, expected_path: str, rel: str) -> tuple[int, str]:
        resolver = self.supp.get("content_addressed_schema_resolver")
        if not isinstance(resolver, dict) or resolver.get("unlisted_or_digest_mismatch") != "FAIL_CLOSED":
            raise ValueError("authority declaration mismatch: " + rel)
        matches = [item for item in resolver.get("resources", []) if isinstance(item, dict) and item.get("uri") == uri]
        if len(matches) != 1:
            raise ValueError("authority declaration mismatch: " + rel)
        return self._declared_pin(matches[0], expected_path=expected_path, rel=rel)

    def _load_pinned(self, rel: str, expected_length: int | None, expected_sha256: str) -> Any:
        path = self.root / rel
        raw = path.read_bytes()
        if (expected_length is not None and len(raw) != expected_length) or sha256_upper(raw) != expected_sha256:
            raise ValueError("authority pin mismatch: " + rel)
        return json.loads(raw.decode("utf-8"))

    @staticmethod
    def _at(root: Any, fragment: str) -> Any:
        return pointer_get(root, fragment[1:] if fragment.startswith("#") else fragment)

    def resolve(self, ref: str, current_root: Any) -> tuple[Any, Any]:
        if ref.startswith("#"):
            return self._at(current_root, ref), current_root
        uri, marker, fragment = ref.partition("#")
        root = self.docs.get(uri)
        if root is None:
            # Supplemental schemas use content-addressed aliases.  Locate a
            # uniquely matching $id before failing closed.
            for candidate in (self.base, self.supp, self.packet, self.projection):
                if isinstance(candidate, dict) and candidate.get("$id") == uri:
                    root = candidate
                    break
        if root is None:
            raise KeyError(ref)
        return (self._at(root, "#" + fragment) if marker else root), root


def validate(instance: Any, schema: Any, contracts: Contracts, pointer: str = "", current_root: Any | None = None) -> str | None:
    """Return the first deterministic schema failure pointer, or None."""
    if schema is True:
        return None
    if schema is False:
        return pointer
    if not isinstance(schema, dict):
        return pointer
    if current_root is None:
        current_root = schema
    if "$ref" in schema:
        try:
            target, root = contracts.resolve(schema["$ref"], current_root)
        except (KeyError, TypeError):
            return pointer
        return validate(instance, target, contracts, pointer, root)
    if "allOf" in schema:
        for child in schema["allOf"]:
            failure = validate(instance, child, contracts, pointer, current_root)
            if failure is not None:
                return failure
    if "anyOf" in schema:
        if not any(validate(instance, child, contracts, pointer, current_root) is None for child in schema["anyOf"]):
            return pointer
    if "oneOf" in schema:
        if sum(validate(instance, child, contracts, pointer, current_root) is None for child in schema["oneOf"]) != 1:
            return pointer
    if "not" in schema and validate(instance, schema["not"], contracts, pointer, current_root) is None:
        return pointer
    if "if" in schema:
        branch = "then" if validate(instance, schema["if"], contracts, pointer, current_root) is None else "else"
        if branch in schema:
            failure = validate(instance, schema[branch], contracts, pointer, current_root)
            if failure is not None:
                return failure
    expected = schema.get("type")
    if expected is not None:
        choices = expected if isinstance(expected, list) else [expected]
        actual = (
            "null" if instance is None else
            "boolean" if isinstance(instance, bool) else
            "integer" if isinstance(instance, int) else
            "number" if isinstance(instance, int) and not isinstance(instance, bool) else
            "string" if isinstance(instance, str) else
            "array" if isinstance(instance, list) else
            "object" if isinstance(instance, dict) else "unknown"
        )
        if actual not in choices and not (actual == "integer" and "number" in choices):
            return pointer
    if "const" in schema and not _equal(instance, schema["const"]):
        return pointer
    if "enum" in schema and not any(_equal(instance, item) for item in schema["enum"]):
        return pointer
    if isinstance(instance, dict):
        for required in schema.get("required", []):
            if required not in instance:
                return pointer + "/" + pointer_escape(required)
        props = schema.get("properties", {})
        for name, child in props.items():
            if name in instance:
                failure = validate(instance[name], child, contracts, pointer + "/" + pointer_escape(name), current_root)
                if failure is not None:
                    return failure
        patterns = schema.get("patternProperties", {})
        for name, value in instance.items():
            matched = name in props
            for pattern, child in patterns.items():
                if re.search(pattern, name):
                    matched = True
                    failure = validate(value, child, contracts, pointer + "/" + pointer_escape(name), current_root)
                    if failure is not None:
                        return failure
            if not matched:
                additional = schema.get("additionalProperties", True)
                if additional is False:
                    return pointer + "/" + pointer_escape(name)
                if isinstance(additional, dict):
                    failure = validate(value, additional, contracts, pointer + "/" + pointer_escape(name), current_root)
                    if failure is not None:
                        return failure
        if len(instance) < schema.get("minProperties", 0) or len(instance) > schema.get("maxProperties", 1 << 60):
            return pointer
        for name, dependencies in schema.get("dependentRequired", {}).items():
            if name in instance:
                for dependency in dependencies:
                    if dependency not in instance:
                        return pointer + "/" + pointer_escape(dependency)
        for name, child in schema.get("dependentSchemas", {}).items():
            if name in instance:
                failure = validate(instance, child, contracts, pointer, current_root)
                if failure is not None:
                    return failure
        if "propertyNames" in schema:
            for name in instance:
                failure = validate(name, schema["propertyNames"], contracts, pointer + "/" + pointer_escape(name), current_root)
                if failure is not None:
                    return failure
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0) or len(instance) > schema.get("maxItems", 1 << 60):
            return pointer
        if schema.get("uniqueItems"):
            seen: set[bytes] = set()
            for index, item in enumerate(instance):
                token = jcs(item)
                if token in seen:
                    return pointer + "/" + str(index)
                seen.add(token)
        prefix = schema.get("prefixItems", [])
        for index, child in enumerate(prefix):
            if index < len(instance):
                failure = validate(instance[index], child, contracts, pointer + "/" + str(index), current_root)
                if failure is not None:
                    return failure
        if "items" in schema:
            start = len(prefix)
            for index in range(start, len(instance)):
                failure = validate(instance[index], schema["items"], contracts, pointer + "/" + str(index), current_root)
                if failure is not None:
                    return failure
        if "contains" in schema:
            count = sum(validate(item, schema["contains"], contracts, pointer + "/" + str(index), current_root) is None for index, item in enumerate(instance))
            if count < schema.get("minContains", 1) or count > schema.get("maxContains", 1 << 60):
                return pointer
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0) or len(instance) > schema.get("maxLength", 1 << 60):
            return pointer
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            return pointer
    if isinstance(instance, int) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            return pointer
        if "maximum" in schema and instance > schema["maximum"]:
            return pointer
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            return pointer
        if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
            return pointer
        if "multipleOf" in schema and instance % schema["multipleOf"] != 0:
            return pointer
    return None


def _set_bytes(values: list[Any]) -> set[bytes]:
    return {jcs(value) for value in values}


def evaluate_atom(node: dict[str, Any], facts_root: dict[str, Any]) -> bool:
    op = node["op"]
    get = lambda name: pointer_get(facts_root, node[name])
    if op == "ABSENT": return get("path") is None
    if op == "PRESENT": return get("path") is not None
    if op in {"EQ", "NE"}:
        left = get("path") if "path" in node else get("left")
        right = get("right") if "right" in node else node.get("value")
        result = _equal(left, right)
        return result if op == "EQ" else not result
    if op == "EQUAL_NON_NULL":
        left, right = get("left"), get("right")
        return left is not None and right is not None and _equal(left, right)
    if op == "EMPTY": return len(get("path")) == 0
    if op == "NOT_UNIQUE":
        values = get("path")
        return len(_set_bytes(values)) != len(values)
    if op == "NOT_CONTAINS_ALL": return not set(node["values"]).issubset(set(get("path")))
    if op in {"MEMBER", "NOT_MEMBER"}:
        result = jcs(get("value_path")) in _set_bytes(get("collection_path"))
        return result if op == "MEMBER" else not result
    if op == "MEMBER_VALUE": return get("path") in node["values"]
    if op == "NOT_MEMBER_VALUE": return jcs(node["value"]) not in _set_bytes(get("collection_path"))
    if op == "NOT_SUBSET": return not _set_bytes(get("left")).issubset(_set_bytes(get("right")))
    if op == "NOT_SUBSET_VALUES": return not _set_bytes(get("path")).issubset(_set_bytes(node["values"]))
    if op == "NOT_SET_EQ": return _set_bytes(get("left")) != _set_bytes(get("right"))
    if op == "INTERSECTS": return bool(_set_bytes(get("left")) & _set_bytes(get("right")))
    if op == "ANY_ABSENT": return any(pointer_get(facts_root, path) is None for path in node["paths"])
    if op == "ANY_NULL": return any(value is None for value in get("path"))
    if op == "NOT_PAIRWISE_DISTINCT_NON_NULL":
        values = [pointer_get(facts_root, path) for path in node["paths"]]
        values = [value for value in values if value is not None]
        return len(values) != len(_set_bytes(values))
    if op in {"LE", "GE"}: return get("left") <= get("right") if op == "LE" else get("left") >= get("right")
    if op == "LT_VALUE": return get("path") < node["value"]
    if op == "LE_VALUE": return get("path") <= node["value"]
    if op == "GT_VALUE": return get("path") > node["value"]
    if op == "NE_VALUE": return get("path") != node["value"]
    if op == "OUTSIDE_HALF_OPEN": return get("value") < get("lower") or get("value") >= get("upper")
    if op == "NOT_STRICTLY_INCREASING":
        values = get("path")
        return not values or any(right <= left for left, right in zip(values, values[1:]))
    if op == "COUNT_NE_PATH": return len(get("left")) != len(get("right"))
    if op == "NOT_FUNCTIONAL_BY":
        groups: dict[bytes, bytes] = {}
        for item in get("path"):
            key, value = jcs(item[node["key"]]), jcs(item[node["value"]])
            if key in groups and groups[key] != value: return True
            groups[key] = value
        return False
    if op == "NOT_MEMBER_BY_KEY":
        wanted = jcs(get("value_path"))
        return all(jcs(item[node["key"]]) != wanted for item in get("collection_path"))
    if op == "ANY_NONPOSITIVE_SPAN": return any(item[node["end"]] <= item[node["start"]] for item in get("path"))
    if op == "HAS_SELF_LOOP": return any(_equal(item[node["from"]], item[node["to"]]) for item in get("path"))
    if op == "NOT_ACYCLIC":
        edges = get("path")
        graph: dict[bytes, set[bytes]] = {}
        for edge in edges: graph.setdefault(jcs(edge[node["from"]]), set()).add(jcs(edge[node["to"]]))
        visiting: set[bytes] = set(); done: set[bytes] = set()
        def visit(vertex: bytes) -> bool:
            if vertex in visiting: return True
            if vertex in done: return False
            visiting.add(vertex)
            if any(visit(child) for child in graph.get(vertex, ())): return True
            visiting.remove(vertex); done.add(vertex); return False
        return any(visit(vertex) for vertex in list(graph))
    if op == "NOT_NEXT_SEQUENCE":
        prior, current = get("prior"), get("current")
        return current != (node["initial"] if prior is None else prior + 1)
    if op == "NOT_ALL_EQUAL_PATH":
        expected = get("value_path")
        return any(not _equal(item, expected) for item in get("collection_path"))
    if op == "NOT_BOOLEAN_EQ_ENUM": return get("boolean_path") is not (get("enum_path") == node["true_value"])
    if op == "ANY_PRESENT_STRICT_BASE64_DECODE_FAILURE":
        return any(value is not None and _strict_b64(value) is None for value in (pointer_get(facts_root, path) for path in node["paths"]))
    if op == "BASE64_SHA256_NE":
        raw = _strict_b64(get("base64_path"))
        if raw is None: raise ValueError("base64 precedence violation")
        return sha256_upper(raw) != get("digest_path")
    if op == "NO_EARLIER_CLASS_MATCH": return False
    raise KeyError(f"unknown predicate operator {op}")


def evaluate_predicate(node: dict[str, Any], decision_input: dict[str, Any]) -> bool:
    if "all" in node: return all(evaluate_predicate(child, decision_input) for child in node["all"])
    if "any" in node: return any(evaluate_predicate(child, decision_input) for child in node["any"])
    if "not" in node: return not evaluate_predicate(node["not"], decision_input)
    return evaluate_atom(node, decision_input)


def _strict_b64(value: Any) -> bytes | None:
    if not isinstance(value, str) or not value.isascii() or re.fullmatch(r"(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?", value) is None:
        return None
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None
    return raw if base64.b64encode(raw).decode("ascii") == value else None


def _sealed_response(response: dict[str, Any], field: str) -> dict[str, Any]:
    response[field] = ZERO64
    response[field] = sha256_upper(jcs(response))
    return response


class Implementation:
    def __init__(self, repo_root: Path | None = None):
        self.contracts = Contracts(repo_root)

    def error_response(self, code: str, pointer: str = "", request_id: str = DEFAULT_REQUEST_ID) -> tuple[int, bytes]:
        message, precedence = ERRORS[code]
        response = {
            "errors": [{"code": code, "message": message, "pointer": pointer, "precedence": precedence}],
            "exit_code": 2,
            "format_version": "PCB-RUNNER-RESPONSE-0.2",
            "ok": False,
            "output": None,
            "receipt_sha256": ZERO64,
            "request_id": request_id,
            "result": "INCOMPLETE",
        }
        _sealed_response(response, "receipt_sha256")
        return 2, jcs(response) + b"\n"

    def execute_bytes(self, raw: bytes) -> tuple[int, bytes]:
        try:
            return self._execute_bytes(raw)
        except Exception:
            # The raw ABI is total: unexpected implementation faults are
            # contained in the deterministic internal-error tuple and never
            # escape as a traceback on either the API or CLI surface.
            return self.error_response("ERR_INTERNAL")

    def _execute_bytes(self, raw: bytes) -> tuple[int, bytes]:
        if raw in (b"", b"\n"):
            # Absent-or-empty covers the empty payload with its bare LF
            # terminator; two terminators or any other byte is wire content
            # (F-WP4-007 campaign witness, identity 3606 of the 600-window
            # stream).
            return self.error_response("ERR_EMPTY_INPUT")
        if len(raw) > 16_777_216:
            return self.error_response("ERR_LIMIT")
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return self.error_response("ERR_UTF8")
        if text.startswith("\ufeff"):
            return self.error_response("ERR_BOM")
        json_text = text[:-1] if text.endswith("\n") else text
        parser = StrictParser(json_text)
        try:
            request = parser.parse()
        except DuplicateFault:
            return self.error_response("ERR_DUPLICATE_KEY")
        except ParseFault:
            return self.error_response("ERR_JSON")
        repaired_id = request.get("request_id") if isinstance(request, dict) and isinstance(request.get("request_id"), str) and REQUEST_ID_RE.fullmatch(request["request_id"]) else DEFAULT_REQUEST_ID
        if not text.endswith("\n") or "\r" in text:
            return self.error_response("ERR_JSON", "", repaired_id)
        if parser.number_pointers:
            return self.error_response("ERR_NUMBER", min(parser.number_pointers, key=lambda p: p.encode("utf-8")), repaired_id)
        try:
            canonical = jcs(request)
        except (TypeError, UnicodeError):
            return self.error_response("ERR_JSON", "", repaired_id)
        if canonical != json_text.encode("utf-8"):
            return self.error_response("ERR_JSON", "", repaired_id)
        nfc = _nfc_pointers(request)
        if nfc:
            return self.error_response("ERR_NFC", min(nfc, key=lambda p: p.encode("utf-8")), repaired_id)
        if not isinstance(request, dict):
            return self.error_response("ERR_SCHEMA", "", repaired_id)
        request_id = repaired_id
        # The composed request schema is the authority for all 30 rows.
        schema = self.contracts.supp["schemas"]["request_schema"]
        # The frozen runner performs an explicit format discriminator check
        # before the composed oneOf.  Other missing members are adjudicated
        # by the schema as a whole (and may therefore point at the root).
        if "format_version" not in request:
            return self.error_response("ERR_SCHEMA", "/format_version", request_id)
        if request.get("format_version") != "B1-SEMANTIC-DECISION-REQUEST-0.2":
            return self.error_response("ERR_SCHEMA", "/format_version", request_id)
        if any(name not in request for name in ("operation_handle", "obligation_id", "decision_input")):
            return self.error_response("ERR_SCHEMA", "", request_id)
        if not isinstance(request["decision_input"], dict):
            return self.error_response("ERR_SCHEMA", "", request_id)
        # After the discriminator and core gates, the contract requires one
        # deterministic ERR_SCHEMA at the lexicographically first mismatched
        # pointer: every remaining mismatch pools into one set and the UTF-8
        # minimum is selected, with no stage short-circuiting an earlier
        # pointer out of the pool (F-WP4-007).  Value agreement between the
        # bound copies of operation_handle, obligation_id, and request_id and
        # the two digests belongs to the binding stage at member pointers;
        # the schema stages therefore judge structure on a value-repaired
        # copy so a value mismatch never doubles as a subtree collapse.
        issues = ["/" + pointer_escape(name) for name in schema.get("required", []) if name not in request]
        allowed = set(schema.get("properties", {}))
        issues.extend("/" + pointer_escape(name) for name in request if name not in allowed)
        for name, child_schema in schema.get("properties", {}).items():
            if name in {"decision_input", "inner_request"} or name not in request:
                continue
            try:
                failure = validate(request[name], child_schema, self.contracts, "/" + pointer_escape(name), self.contracts.supp)
            except (KeyError, TypeError, ValueError, UnicodeError):
                failure = None
            if failure is not None:
                issues.append(failure)
        issues.extend(self._decision_input_issues(request, schema))
        inner = request.get("inner_request")
        if "inner_request" in request and not isinstance(inner, dict):
            issues.append("/inner_request")
        if isinstance(inner, dict):
            inner_schema, inner_root = self.contracts.resolve(schema["properties"]["inner_request"]["$ref"], self.contracts.supp)
            issues.extend("/inner_request/" + pointer_escape(name) for name in inner_schema.get("required", []) if name not in inner)
            inner_allowed = set(inner_schema.get("properties", {}))
            issues.extend("/inner_request/" + pointer_escape(name) for name in inner if name not in inner_allowed)
            for name, child_schema in inner_schema.get("properties", {}).items():
                if name == "input" or name not in inner:
                    continue
                try:
                    failure = validate(inner[name], child_schema, self.contracts, "/inner_request/" + pointer_escape(name), inner_root)
                except (KeyError, TypeError, ValueError, UnicodeError):
                    failure = None
                if failure is not None:
                    issues.append(failure)
        try:
            issues.extend(self._binding_failures(request))
        except (KeyError, TypeError, ValueError, UnicodeError):
            pass
        if issues:
            return self.error_response("ERR_SCHEMA", min(issues, key=lambda p: p.encode("utf-8")), request_id)
        if parser.max_depth > 128 or parser.member_count > 100_000:
            return self.error_response("ERR_LIMIT", "", repaired_id)
        try:
            return self._execute_request(request)
        except (KeyError, TypeError, ValueError, UnicodeError):
            return self.error_response("ERR_INTERNAL", "", request_id)

    def _canonical_operation(self, request: dict[str, Any]) -> tuple[Any, Any]:
        # Majority over however many of the three bound copies are present:
        # a missing copy is a schema issue at its own pointer and never
        # blocks deriving the canonical operation from the remaining copies.
        op_values = []
        for holder in (request, request.get("decision_input"), request.get("inner_request")):
            if isinstance(holder, dict) and "operation_handle" in holder:
                op_values.append(holder["operation_handle"])
        if not op_values:
            return None, None
        try:
            canonical_op = max(op_values, key=op_values.count)
            return canonical_op, self.contracts.registry.get(canonical_op)
        except TypeError:
            return None, None

    def _decision_input_issues(self, request: dict[str, Any], schema: dict[str, Any]) -> list[str]:
        # Observed reference semantics for the decision_input subtree: a
        # missing binding-owned member (operation_handle, obligation_id)
        # localizes to its member pointer; a missing or malformed
        # structure-owned member (format_version, facts), an unknown member,
        # or any arm failure of the value-repaired copy collapses to
        # /decision_input.  Binding-owned member VALUES are judged only by
        # the binding stage, so the arm walk runs with those values repaired
        # to the canonical operation context.
        decision = request["decision_input"]
        di_schema, _ = self.contracts.resolve(schema["properties"]["decision_input"]["$ref"], self.contracts.supp)
        arms = di_schema.get("oneOf", [])
        required = set.intersection(*(set(arm.get("required", [])) for arm in arms)) if arms else set()
        allowed = set().union(*(set(arm.get("properties", {})) for arm in arms)) if arms else set()
        issues = []
        for name in sorted(required):
            if name in decision:
                continue
            if name in ("operation_handle", "obligation_id"):
                issues.append("/decision_input/" + pointer_escape(name))
            else:
                issues.append("/decision_input")
        if any(name not in allowed for name in decision):
            issues.append("/decision_input")
        canonical_op, canonical_obligation = self._canonical_operation(request)
        walk = dict(decision)
        if canonical_op is not None and canonical_obligation is not None:
            walk["operation_handle"] = canonical_op
            walk["obligation_id"] = canonical_obligation
        try:
            failure = validate(walk, schema["properties"]["decision_input"], self.contracts, "/decision_input", self.contracts.supp)
        except (KeyError, TypeError, ValueError, UnicodeError):
            failure = None
        if failure is not None:
            issues.append("/decision_input")
        return issues

    def _binding_failures(self, request: dict[str, Any]) -> list[str]:
        # The binding stage evaluates only on structurally complete requests
        # (a missing member is a schema issue at its own pointer, never a
        # binding mismatch); each check is additionally gated on its own
        # members being present, and under the pooled selection law every
        # failing binding pointer is reported, not the first in evaluation
        # order.
        if any(name not in request for name in ("operation_handle", "obligation_id", "inner_input_sha256", "inner_request_raw_sha256", "request_id")):
            return []
        canonical_op, canonical_obligation = self._canonical_operation(request)
        if canonical_obligation is None:
            return []
        decision = request.get("decision_input")
        inner = request.get("inner_request")
        decision = decision if isinstance(decision, dict) else {}
        inner = inner if isinstance(inner, dict) else {}
        failures = []
        def check(holder: dict[str, Any], name: str, expected: Any, pointer: str) -> None:
            if name in holder and holder[name] != expected:
                failures.append(pointer)
        check(request, "operation_handle", canonical_op, "/operation_handle")
        check(decision, "operation_handle", canonical_op, "/decision_input/operation_handle")
        check(inner, "operation_handle", canonical_op, "/inner_request/operation_handle")
        check(request, "obligation_id", canonical_obligation, "/obligation_id")
        check(decision, "obligation_id", canonical_obligation, "/decision_input/obligation_id")
        check(inner, "request_id", request["request_id"], "/inner_request/request_id")
        if "input" in inner:
            try:
                check(request, "inner_input_sha256", sha256_upper(jcs(inner["input"])), "/inner_input_sha256")
            except (TypeError, ValueError, UnicodeError):
                pass
        if inner:
            try:
                check(request, "inner_request_raw_sha256", sha256_upper(jcs(inner) + b"\n"), "/inner_request_raw_sha256")
            except (TypeError, ValueError, UnicodeError):
                pass
        return failures

    def _execute_request(self, request: dict[str, Any]) -> tuple[int, bytes]:
        obligation = request["obligation_id"]
        row = self.contracts.rows[obligation]
        behavior = "VALID"
        for candidate in ("MALFORMED_OR_BOUNDARY", "BINDING_OR_CONFLICT", "OMISSION_OR_INCOMPLETE"):
            if evaluate_predicate(row["class_predicates"][candidate], request["decision_input"]):
                behavior = candidate
                break
        mapping = self.contracts.base["semantic_decision_contract"]["evaluation_result_contract"][behavior]
        effect = self._effect_receipt(request) if behavior == "VALID" else None
        unresolved = [] if behavior != "OMISSION_OR_INCOMPLETE" else [f"{obligation}: authoritative semantic basis is absent or inconsistent"]
        output = {
            "effect_receipt_sha256": effect,
            "obligation_id": obligation,
            "operation_handle": request["operation_handle"],
            "record_references": [],
            "result_object": {"behavior_class": behavior, "conclusion": mapping["conclusion"]},
            "status": mapping["status"],
            "unresolved_reasons": unresolved,
        }
        response = {
            "errors": [],
            "exit_code": mapping["exit_code"],
            "format_version": "PCB-RUNNER-RESPONSE-0.2",
            "ok": True,
            "output": output,
            "receipt_sha256": ZERO64,
            "request_id": request["request_id"],
            "result": mapping["result"],
        }
        _sealed_response(response, "receipt_sha256")
        return mapping["exit_code"], jcs(response) + b"\n"

    def _effect_receipt(self, request: dict[str, Any]) -> str | None:
        obligation = request["obligation_id"]
        rules = self.contracts.base["semantic_decision_contract"]["effect_receipt_contract"]["operation_field_rules"]
        if obligation not in rules:
            return None
        rule = rules[obligation]
        fields: dict[str, Any] = {}
        for derivation in rule["field_derivations"]:
            value = pointer_get(request["decision_input"], derivation["source_path"])
            if derivation["transform"] == "STRICT_BASE64_DECODE_SHA256_UPPER":
                raw = _strict_b64(value)
                if raw is None: raise ValueError("base64")
                value = sha256_upper(raw)
            fields[derivation["target_key"]] = value
        preimage = {
            "domain": "B1-SEMANTIC-EFFECT-RECEIPT-0.2",
            "operation_handle": request["operation_handle"],
            "obligation_id": obligation,
            "request_id": request["request_id"],
            "decision_input_sha256": sha256_upper(jcs(request["decision_input"])),
            "operation_fields_object": fields,
        }
        return sha256_upper(jcs(preimage))

    def execute_wrapper(self, wrapper_request: dict[str, Any]) -> dict[str, Any]:
        raw = jcs(wrapper_request["semantic_request"]) + b"\n"
        _, semantic_raw = self.execute_bytes(raw)
        semantic = json.loads(semantic_raw)
        if not semantic["ok"]:
            raise ValueError("invalid embedded semantic request")
        output = semantic["output"]
        response = {
            "configuration": wrapper_request["configuration"],
            "errors": [],
            "exit_code": semantic["exit_code"],
            "format_version": "B1-WRAPPER-SEMANTIC-RESPONSE-0.2",
            "obligation_id": output["obligation_id"],
            "ok": True,
            "operation_handle": output["operation_handle"],
            "output": {
                "effect_receipt_sha256": output["effect_receipt_sha256"],
                "payload": output["result_object"],
                "record_refs": output["record_references"],
                "unresolved_reasons": output["unresolved_reasons"],
            },
            "request_id": semantic["request_id"],
            "response_sha256": ZERO64,
            "result": semantic["result"],
        }
        _sealed_response(response, "response_sha256")
        return response

    def validate_wrapper_binding(self, request_raw: bytes, response_raw: bytes, transcript: dict[str, Any]) -> bool:
        """Evaluate one wrapper transcript binding under the public steps.

        Cross-arm projection equality is checked by ``wrapper_projection``;
        this method covers every single-arm binding step.
        """
        try:
            request = json.loads(request_raw)
            response = json.loads(response_raw)
            request_schema = self.contracts.supp["schemas"]["wrapper_configuration_request_schema"]
            response_schema = self.contracts.supp["schemas"]["wrapper_configuration_response_schema"]
            transcript_schema = self.contracts.supp["schemas"]["wrapper_transcript_schema"]
            if validate(request, request_schema, self.contracts, current_root=self.contracts.supp) is not None:
                return False
            if validate(response, response_schema, self.contracts, current_root=self.contracts.supp) is not None:
                return False
            if validate(transcript, transcript_schema, self.contracts, current_root=self.contracts.supp) is not None:
                return False
            semantic = request["semantic_request"]
            if self._binding_failures(semantic):
                return False
            if not (transcript["request_id"] == response["request_id"] == request["request_id"] == semantic["request_id"]):
                return False
            if not (transcript["configuration"] == response["configuration"] == request["configuration"]):
                return False
            if not (transcript["operation_handle"] == response["operation_handle"] == request["operation_handle"] == semantic["operation_handle"]):
                return False
            obligation = self.contracts.registry.get(request["operation_handle"])
            if obligation is None or not (transcript["obligation_id"] == response["obligation_id"] == obligation):
                return False
            sealed_response = json.loads(json.dumps(response))
            expected_response_seal = sealed_response["response_sha256"]
            sealed_response["response_sha256"] = ZERO64
            if sha256_upper(jcs(sealed_response)) != expected_response_seal or transcript["normalized_response_sha256"] != expected_response_seal:
                return False
            card = request["attention_card"]
            if request["configuration"] == "B1":
                if card is not None or transcript["attention_card_sha256"] is not None:
                    return False
            else:
                if not isinstance(card, dict):
                    return False
                card_copy = json.loads(json.dumps(card)); expected_card = card_copy["card_sha256"]; card_copy["card_sha256"] = ZERO64
                if sha256_upper(jcs(card_copy)) != expected_card or transcript["attention_card_sha256"] != expected_card:
                    return False
            if transcript["request_raw_sha256"] != sha256_upper(request_raw) or transcript["response_raw_sha256"] != sha256_upper(response_raw):
                return False
            record = json.loads(json.dumps(transcript)); expected_record = record["record_sha256"]; record["record_sha256"] = ZERO64
            if sha256_upper(jcs(record)) != expected_record:
                return False
            return True
        except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            return False

    @staticmethod
    def wrapper_projection(request: dict[str, Any]) -> bytes:
        projected = {key: value for key, value in request.items() if key not in {"configuration", "attention_card"}}
        return jcs(projected)


_DEFAULT: Implementation | None = None


def implementation() -> Implementation:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Implementation()
    return _DEFAULT


def execute(raw: bytes) -> tuple[int, bytes]:
    return implementation().execute_bytes(raw)
