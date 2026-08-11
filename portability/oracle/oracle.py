"""Clean-room receiver-reliance portability oracle.

This module deliberately does not import or execute the accepted implementation.
Its evidence boundary is documented in PROVENANCE.md.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from itertools import permutations
from pathlib import Path
from typing import Iterable, Mapping, Sequence


ZERO64 = "0" * 64
ZERO_REQUEST_ID = "RUN_" + "0" * 24
REQUEST_ID_RE = re.compile(r"^RUN_[A-F0-9]{24}$")
SAFE_INTEGER_MAX = 9_007_199_254_740_991
MAX_INPUT_BYTES = 16_777_216
MAX_MEMBERS_OR_ITEMS = 100_000
MAX_NESTING = 128

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

DECLARED_FORMATS = {
    "B1-SEMANTIC-DECISION-REQUEST-0.2": (
        "decision_input",
        "format_version",
        "inner_input_sha256",
        "inner_request",
        "inner_request_raw_sha256",
        "obligation_id",
        "operation_handle",
        "request_id",
    ),
    "B1-WRAPPER-SEMANTIC-REQUEST-0.2": (
        "attention_card",
        "budget",
        "clarification_state",
        "configuration",
        "format_version",
        "operation_handle",
        "pause_state",
        "request_id",
        "semantic_request",
    ),
}


class OracleError(Exception):
    """Base class for deterministic oracle failures."""


class ParseFault(OracleError):
    pass


class DuplicateFound(OracleError):
    pass


class JCSFault(OracleError):
    pass


class OutsideFixture(OracleError):
    pass


@dataclass(frozen=True)
class JNumber:
    lexeme: str

    @property
    def valid_safe_integer(self) -> bool:
        # Do not convert the lexeme with int().  CPython deliberately limits
        # decimal-string conversions (normally to 4,300 digits), and that
        # ambient host setting must not change an oracle classification.
        lexeme = self.lexeme
        if lexeme == "-0":
            return False
        digits = lexeme[1:] if lexeme.startswith("-") else lexeme
        if not digits or any(char < "0" or char > "9" for char in digits):
            return False
        if digits == "0":
            return not lexeme.startswith("-")
        if digits.startswith("0"):
            return False
        maximum = str(SAFE_INTEGER_MAX)
        return len(digits) < len(maximum) or (len(digits) == len(maximum) and digits <= maximum)


def _safe_int_decimal(value: int) -> str:
    """Serialize a programmatic safe integer without the host digit cap."""

    if value < -SAFE_INTEGER_MAX or value > SAFE_INTEGER_MAX:
        raise JCSFault("integer is outside the safe integer model")
    if value == 0:
        return "0"
    negative = value < 0
    remaining = -value if negative else value
    digits: list[str] = []
    while remaining:
        remaining, digit = divmod(remaining, 10)
        digits.append(chr(ord("0") + digit))
    if negative:
        digits.append("-")
    return "".join(reversed(digits))


@dataclass(frozen=True)
class JObject:
    pairs: tuple[tuple[str, object], ...]


@dataclass(frozen=True)
class Classification:
    code: str | None
    pointer: str
    request_id: str
    value: object | None
    canonical_payload: bytes | None
    limit_hit: bool


def sha256_upper(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _utf16_units(text: str) -> tuple[int, ...]:
    units: list[int] = []
    for char in text:
        cp = ord(char)
        if 0xD800 <= cp <= 0xDFFF:
            raise JCSFault("lone surrogate")
        if cp <= 0xFFFF:
            units.append(cp)
        else:
            cp -= 0x10000
            units.extend((0xD800 + (cp >> 10), 0xDC00 + (cp & 0x3FF)))
    return tuple(units)


def utf16_sort_key(text: str) -> tuple[int, ...]:
    """Return RFC 8785's locale-independent unsigned UTF-16 sort key."""

    return _utf16_units(text)


_SHORT_ESCAPES = {
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
    '"': '\\"',
    "\\": "\\\\",
}


def _jcs_string(text: str) -> str:
    _utf16_units(text)
    out = ['"']
    for char in text:
        cp = ord(char)
        if char in _SHORT_ESCAPES:
            out.append(_SHORT_ESCAPES[char])
        elif cp <= 0x1F:
            out.append(f"\\u{cp:04x}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _object_pairs(value: object) -> tuple[tuple[str, object], ...]:
    if isinstance(value, JObject):
        return value.pairs
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise JCSFault("object member name is not a string")
        return tuple(value.items())
    raise JCSFault("not an object")


def jcs_dumps(value: object) -> str:
    """Serialize the integer-only contract domain using independent JCS rules.

    An explicit work stack is used instead of Python recursion.  Raw records
    may legitimately exceed the interpreter's call-stack depth before the
    contract's own nesting limit is adjudicated, and lower-precedence resource
    errors must not turn into ``ERR_JSON`` merely because of that host detail.
    """

    output: list[str] = []
    work: list[tuple[str, object]] = [("value", value)]
    while work:
        kind, item = work.pop()
        if kind == "text":
            output.append(str(item))
            continue
        if item is None:
            output.append("null")
        elif item is True:
            output.append("true")
        elif item is False:
            output.append("false")
        elif isinstance(item, str):
            output.append(_jcs_string(item))
        elif isinstance(item, JNumber):
            # Invalid numeric-profile lexemes are held stable so another
            # independent canonical-byte defect can still win at precedence
            # 50 (F-ORACLE-005).  A valid raw integer lexeme is already its
            # canonical decimal spelling; retaining it also avoids the host's
            # ambient decimal-string conversion cap (F-ORACLE-013).
            output.append(item.lexeme)
        elif isinstance(item, int):
            output.append(_safe_int_decimal(item))
        elif isinstance(item, float):
            raise JCSFault("floating-point values are outside this contract domain")
        elif isinstance(item, (list, tuple)):
            work.append(("text", "]"))
            for index in range(len(item) - 1, -1, -1):
                work.append(("value", item[index]))
                if index:
                    work.append(("text", ","))
            work.append(("text", "["))
        elif isinstance(item, (dict, JObject)):
            pairs = sorted(_object_pairs(item), key=lambda pair: utf16_sort_key(pair[0]))
            work.append(("text", "}"))
            for index in range(len(pairs) - 1, -1, -1):
                key, child = pairs[index]
                work.append(("value", child))
                work.append(("text", ":"))
                work.append(("text", _jcs_string(key)))
                if index:
                    work.append(("text", ","))
            work.append(("text", "{"))
        else:
            raise JCSFault(f"unsupported value type: {type(item).__name__}")
    return "".join(output)


def jcs_bytes(value: object) -> bytes:
    return jcs_dumps(value).encode("utf-8")


def self_zero_digest(value: Mapping[str, object], field: str) -> str:
    clone = copy.deepcopy(dict(value))
    if field not in clone:
        raise OracleError(f"missing self-zero field: {field}")
    clone[field] = ZERO64
    return sha256_upper(jcs_bytes(clone))


class StrictParser:
    """Small iterative JSON parser preserving numeric lexemes and pairs."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.index = 0
        self.limit_hit = False

    def parse(self) -> object:
        missing = object()
        root: object = missing
        stack: list[dict[str, object]] = []

        def accept(value: object) -> None:
            nonlocal root
            if not stack:
                root = value
                return
            frame = stack[-1]
            if frame["state"] != "await_value":
                raise AssertionError("parser value accepted outside a value position")
            if frame["kind"] == "array":
                items = frame["items"]
                assert isinstance(items, list)
                items.append(value)
                if len(items) > MAX_MEMBERS_OR_ITEMS:
                    self.limit_hit = True
            else:
                pairs = frame["pairs"]
                key = frame["pending_key"]
                assert isinstance(pairs, list) and isinstance(key, str)
                pairs.append((key, value))
                frame["pending_key"] = None
                if len(pairs) > MAX_MEMBERS_OR_ITEMS:
                    self.limit_hit = True
            frame["state"] = "after_value"

        def start_value() -> None:
            self._skip_ws()
            if self.index >= len(self.text):
                raise ParseFault("missing value")
            char = self.text[self.index]
            if char == "[":
                self.index += 1
                if len(stack) + 1 > MAX_NESTING:
                    self.limit_hit = True
                stack.append({"kind": "array", "items": [], "state": "first"})
                return
            if char == "{":
                self.index += 1
                if len(stack) + 1 > MAX_NESTING:
                    self.limit_hit = True
                stack.append(
                    {
                        "kind": "object",
                        "pairs": [],
                        "pending_key": None,
                        "seen": set(),
                        "state": "first_key",
                    }
                )
                return
            if char == '"':
                accept(self._string())
                return
            if char == "t" and self.text.startswith("true", self.index):
                self.index += 4
                accept(True)
                return
            if char == "f" and self.text.startswith("false", self.index):
                self.index += 5
                accept(False)
                return
            if char == "n" and self.text.startswith("null", self.index):
                self.index += 4
                accept(None)
                return
            if char == "-" or "0" <= char <= "9":
                accept(self._number())
                return
            raise ParseFault("invalid value")

        def close_frame() -> None:
            frame = stack.pop()
            if frame["kind"] == "array":
                value = frame["items"]
                assert isinstance(value, list)
                accept(value)
            else:
                pairs = frame["pairs"]
                assert isinstance(pairs, list)
                accept(JObject(tuple(pairs)))

        start_value()
        while root is missing:
            if not stack:
                raise AssertionError("parser lost the root value")
            frame = stack[-1]
            self._skip_ws()
            state = frame["state"]
            if frame["kind"] == "array":
                if state == "first":
                    if self.index < len(self.text) and self.text[self.index] == "]":
                        self.index += 1
                        close_frame()
                    else:
                        frame["state"] = "await_value"
                        start_value()
                elif state == "need_value":
                    frame["state"] = "await_value"
                    start_value()
                elif state == "after_value":
                    if self.index >= len(self.text):
                        raise ParseFault("unterminated array")
                    char = self.text[self.index]
                    self.index += 1
                    if char == "]":
                        close_frame()
                    elif char == ",":
                        frame["state"] = "need_value"
                    else:
                        raise ParseFault("comma required")
                else:
                    # An awaiting parent cannot be top-of-stack unless its
                    # child was a scalar, in which case accept() changed it.
                    raise AssertionError("array parser state is inconsistent")
            else:
                if state in ("first_key", "need_key"):
                    if state == "first_key" and self.index < len(self.text) and self.text[self.index] == "}":
                        self.index += 1
                        close_frame()
                        continue
                    if self.index >= len(self.text) or self.text[self.index] != '"':
                        raise ParseFault("object member name required")
                    key = self._string()
                    seen = frame["seen"]
                    assert isinstance(seen, set)
                    if key in seen:
                        raise DuplicateFound(key)
                    seen.add(key)
                    frame["pending_key"] = key
                    frame["state"] = "colon"
                elif state == "colon":
                    if self.index >= len(self.text) or self.text[self.index] != ":":
                        raise ParseFault("colon required")
                    self.index += 1
                    frame["state"] = "need_value"
                elif state == "need_value":
                    frame["state"] = "await_value"
                    start_value()
                elif state == "after_value":
                    if self.index >= len(self.text):
                        raise ParseFault("unterminated object")
                    char = self.text[self.index]
                    self.index += 1
                    if char == "}":
                        close_frame()
                    elif char == ",":
                        frame["state"] = "need_key"
                    else:
                        raise ParseFault("comma required")
                else:
                    raise AssertionError("object parser state is inconsistent")

        self._skip_ws()
        if self.index != len(self.text):
            raise ParseFault("trailing data")
        return root

    def _skip_ws(self) -> None:
        while self.index < len(self.text) and self.text[self.index] in " \t\r\n":
            self.index += 1

    def _string(self) -> str:
        self.index += 1
        units: list[str] = []
        while self.index < len(self.text):
            char = self.text[self.index]
            self.index += 1
            if char == '"':
                return _combine_surrogates(units)
            if char == "\\":
                if self.index >= len(self.text):
                    raise ParseFault("incomplete escape")
                esc = self.text[self.index]
                self.index += 1
                if esc in '"\\/':
                    units.append(esc)
                elif esc == "b":
                    units.append("\b")
                elif esc == "f":
                    units.append("\f")
                elif esc == "n":
                    units.append("\n")
                elif esc == "r":
                    units.append("\r")
                elif esc == "t":
                    units.append("\t")
                elif esc == "u":
                    if self.index + 4 > len(self.text):
                        raise ParseFault("incomplete unicode escape")
                    digits = self.text[self.index : self.index + 4]
                    if not re.fullmatch(r"[0-9A-Fa-f]{4}", digits):
                        raise ParseFault("invalid unicode escape")
                    self.index += 4
                    units.append(chr(int(digits, 16)))
                else:
                    raise ParseFault("invalid escape")
            else:
                if ord(char) < 0x20:
                    raise ParseFault("unescaped control")
                units.append(char)
        raise ParseFault("unterminated string")

    def _number(self) -> JNumber:
        # Scan the JSON number grammar directly.  Besides avoiding an
        # input-sized temporary tail slice, this ensures that no decimal
        # lexeme is ever passed through int(str), whose host-configurable cap
        # is unrelated to the frozen contract limits.
        start = self.index
        if self.text[self.index] == "-":
            self.index += 1
            if self.index >= len(self.text):
                raise ParseFault("invalid number")

        if self.text[self.index] == "0":
            self.index += 1
        elif "1" <= self.text[self.index] <= "9":
            self.index += 1
            while self.index < len(self.text) and "0" <= self.text[self.index] <= "9":
                self.index += 1
        else:
            raise ParseFault("invalid number")

        if self.index < len(self.text) and self.text[self.index] == ".":
            self.index += 1
            fraction_start = self.index
            while self.index < len(self.text) and "0" <= self.text[self.index] <= "9":
                self.index += 1
            if self.index == fraction_start:
                raise ParseFault("invalid number")

        if self.index < len(self.text) and self.text[self.index] in "eE":
            self.index += 1
            if self.index < len(self.text) and self.text[self.index] in "+-":
                self.index += 1
            exponent_start = self.index
            while self.index < len(self.text) and "0" <= self.text[self.index] <= "9":
                self.index += 1
            if self.index == exponent_start:
                raise ParseFault("invalid number")

        return JNumber(self.text[start : self.index])


def _combine_surrogates(units: Sequence[str]) -> str:
    out: list[str] = []
    index = 0
    while index < len(units):
        cp = ord(units[index])
        if 0xD800 <= cp <= 0xDBFF and index + 1 < len(units):
            low = ord(units[index + 1])
            if 0xDC00 <= low <= 0xDFFF:
                out.append(chr(0x10000 + ((cp - 0xD800) << 10) + low - 0xDC00))
                index += 2
                continue
        out.append(units[index])
        index += 1
    return "".join(out)


def _pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _walk(value: object, pointer: str = "") -> Iterable[tuple[str, object]]:
    stack = [(pointer, value)]
    while stack:
        current_pointer, current = stack.pop()
        yield current_pointer, current
        if isinstance(current, JObject):
            for key, item in reversed(current.pairs):
                child = current_pointer + "/" + _pointer_token(key)
                stack.append((child, item))
                stack.append((child, key))
        elif isinstance(current, list):
            for index in range(len(current) - 1, -1, -1):
                stack.append((current_pointer + "/" + str(index), current[index]))


def _object_as_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, JObject):
        return None
    return dict(value.pairs)


def _request_id(value: object) -> str:
    obj = _object_as_dict(value)
    candidate = obj.get("request_id") if obj is not None else None
    return candidate if isinstance(candidate, str) and REQUEST_ID_RE.fullmatch(candidate) else ZERO_REQUEST_ID


def _schema_error(value: object) -> str | None:
    obj = _object_as_dict(value)
    if obj is None:
        return ""
    format_version = obj.get("format_version")
    if not isinstance(format_version, str) or format_version not in DECLARED_FORMATS:
        return "/format_version"
    missing = [name for name in DECLARED_FORMATS[format_version] if name not in obj]
    if missing:
        # A JSON-Schema `required` failure is located at the object that lacks
        # the member, not at a child instance location that does not exist.
        # Both declared request envelopes are rooted at this object, so every
        # top-level required-member absence has the empty instance pointer.
        return ""
    if not isinstance(obj.get("request_id"), str) or not REQUEST_ID_RE.fullmatch(str(obj["request_id"])):
        # Unlike a missing member, a present value that violates its member
        # schema has that member's instance location.
        return "/request_id"
    return None


def classify_record(raw: bytes) -> Classification:
    """Classify the independent raw ABI layer without consulting fixture outputs."""

    if raw in (b"", b"\n"):
        return Classification("ERR_EMPTY_INPUT", "", ZERO_REQUEST_ID, None, None, False)
    # The frozen host boundary rejects an oversized physical record before
    # decoding it.  Apart from matching that precedence, this guard is what
    # keeps classification bounded: no UTF-8 text, parser state, or canonical
    # payload proportional to an over-limit record is constructed.
    if len(raw) > MAX_INPUT_BYTES:
        return Classification("ERR_LIMIT", "", ZERO_REQUEST_ID, None, None, True)
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return Classification("ERR_UTF8", "", ZERO_REQUEST_ID, None, None, len(raw) > MAX_INPUT_BYTES)
    if raw.startswith(b"\xef\xbb\xbf"):
        return Classification("ERR_BOM", "", ZERO_REQUEST_ID, None, None, len(raw) > MAX_INPUT_BYTES)

    framed = text.endswith("\n")
    payload_text = text[:-1] if framed else text
    parser = StrictParser(payload_text)
    try:
        value = parser.parse()
    except DuplicateFound:
        return Classification("ERR_DUPLICATE_KEY", "", ZERO_REQUEST_ID, None, None, len(raw) > MAX_INPUT_BYTES)
    except (ParseFault, RecursionError):
        return Classification("ERR_JSON", "", ZERO_REQUEST_ID, None, None, len(raw) > MAX_INPUT_BYTES)

    request_id = _request_id(value)
    try:
        canonical = jcs_bytes(value)
    except JCSFault:
        return Classification("ERR_JSON", "", request_id, value, None, parser.limit_hit or len(raw) > MAX_INPUT_BYTES)
    try:
        payload_bytes = payload_text.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        return Classification("ERR_JSON", "", request_id, value, None, parser.limit_hit or len(raw) > MAX_INPUT_BYTES)
    if not framed or canonical != payload_bytes:
        return Classification("ERR_JSON", "", request_id, value, canonical, parser.limit_hit or len(raw) > MAX_INPUT_BYTES)

    nfc_pointers = [pointer for pointer, item in _walk(value) if isinstance(item, str) and unicodedata.normalize("NFC", item) != item]
    if nfc_pointers:
        pointer = min(nfc_pointers, key=lambda p: p.encode("utf-8"))
        return Classification("ERR_NFC", pointer, request_id, value, canonical, parser.limit_hit or len(raw) > MAX_INPUT_BYTES)

    number_pointers = [pointer for pointer, item in _walk(value) if isinstance(item, JNumber) and not item.valid_safe_integer]
    if number_pointers:
        pointer = min(number_pointers, key=lambda p: p.encode("utf-8"))
        return Classification("ERR_NUMBER", pointer, request_id, value, canonical, parser.limit_hit or len(raw) > MAX_INPUT_BYTES)

    schema_pointer = _schema_error(value)
    if schema_pointer is not None:
        return Classification("ERR_SCHEMA", schema_pointer, request_id, value, canonical, parser.limit_hit or len(raw) > MAX_INPUT_BYTES)
    if parser.limit_hit or len(raw) > MAX_INPUT_BYTES:
        return Classification("ERR_LIMIT", "", request_id, value, canonical, True)
    return Classification(None, "", request_id, value, canonical, False)


def error_response(code: str, pointer: str = "", request_id: str = ZERO_REQUEST_ID) -> bytes:
    message, precedence = ERRORS[code]
    exit_code = 3 if code == "ERR_INTERNAL" else 2
    response = {
        "errors": [{"code": code, "message": message, "pointer": pointer, "precedence": precedence}],
        "exit_code": exit_code,
        "format_version": "PCB-RUNNER-RESPONSE-0.2",
        "ok": False,
        "output": None,
        "receipt_sha256": ZERO64,
        "request_id": request_id,
        "result": "INCOMPLETE",
    }
    response["receipt_sha256"] = self_zero_digest(response, "receipt_sha256")
    return jcs_bytes(response) + b"\n"


REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_SPECS = (
    (
        "baseline_semantic",
        "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json",
        "F27B93B3BE8BCBF5FBF7FF7789494621D17B426E16B38E958BB932899B0961B9",
        "semantic",
    ),
    (
        "baseline_wrapper",
        "baseline-run/fixtures/B1_WRAPPER_PARITY_FIXTURE_PACK_0_2.json",
        "22B9A2E8C08A63CF1A29AC3CD57FB0D30108245BC538DA2E4A959A24089195C1",
        "wrapper",
    ),
    (
        "supplemental_semantic",
        "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
        "0A211174261C31924979A348B13EC43678896183ADB99D86002A51238C0AAE73",
        "semantic",
    ),
    (
        "supplemental_wrapper",
        "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_WRAPPER_PARITY_FIXTURE_PACK_0_3.json",
        "0F71812E52ED4C1008BB9544CFD36230BDC01966AF11FE16CFCF838ABB11BF72",
        "wrapper",
    ),
)


class FixtureOracle:
    """Exact expected-byte lookup derived only from four frozen fixture packs."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = REPO_ROOT if repo_root is None else Path(repo_root)
        self.records: dict[bytes, bytes] = {}
        self.record_sources: dict[bytes, str] = {}
        self.pack_receipts: list[dict[str, object]] = []
        self.semantic_records = 0
        self.wrapper_records = 0
        self._load_all()

    def _load_all(self) -> None:
        for name, relative, expected_raw_hash, kind in PACK_SPECS:
            path = self.repo_root / relative
            raw = path.read_bytes()
            actual_raw_hash = sha256_upper(raw)
            if actual_raw_hash != expected_raw_hash:
                raise OracleError(f"{name}: raw SHA-256 mismatch")
            pack = json.loads(raw.decode("utf-8"))
            if self_zero_digest(pack, "pack_sha256") != pack["pack_sha256"]:
                raise OracleError(f"{name}: pack self-zero seal mismatch")
            before = len(self.records)
            if kind == "semantic":
                count = self._load_semantic(name, pack)
                self.semantic_records += count
            else:
                count = self._load_wrapper(name, pack)
                self.wrapper_records += count
            self.pack_receipts.append(
                {
                    "kind": kind,
                    "name": name,
                    "pack_sha256": pack["pack_sha256"],
                    "raw_sha256": actual_raw_hash,
                    "records": count,
                    "unique_records_added": len(self.records) - before,
                }
            )

    def _add_record(self, request: bytes, response: bytes, source: str) -> None:
        existing = self.records.get(request)
        if existing is not None and existing != response:
            raise OracleError(f"conflicting expected response for {source}")
        self.records[request] = response
        self.record_sources.setdefault(request, source)

    @staticmethod
    def _decode_bound(encoded: str, digest: str, label: str) -> bytes:
        raw = base64.b64decode(encoded, validate=True)
        if sha256_upper(raw) != digest:
            raise OracleError(f"{label}: raw digest mismatch")
        return raw

    @staticmethod
    def _verify_response_seal(response: Mapping[str, object], field: str) -> None:
        if self_zero_digest(response, field) != response[field]:
            raise OracleError(f"response {field} self-zero mismatch")

    @staticmethod
    def _verify_case_seals(pack: Mapping[str, object]) -> None:
        collections = (
            ("competence_cases", "case_sha256"),
            ("negative_cases", "negative_case_sha256"),
            ("metamorphic_cases", "metamorphic_case_sha256"),
        )
        for collection, field in collections:
            for case in pack.get(collection, []):
                if field in case and self_zero_digest(case, field) != case[field]:
                    raise OracleError(f"{collection}: {field} self-zero mismatch")

    def _load_semantic(self, name: str, pack: Mapping[str, object]) -> int:
        entries = pack["entries"]
        if len(entries) != pack["entry_count"]:
            raise OracleError(f"{name}: entry count mismatch")
        self._verify_case_seals(pack)
        for entry in entries:
            if self_zero_digest(entry, "entry_sha256") != entry["entry_sha256"]:
                raise OracleError(f"{name}: entry self-zero mismatch")
            request = self._decode_bound(
                entry["semantic_request_jcs_lf_base64"], entry["semantic_request_raw_sha256"], f"{name} request"
            )
            response = self._decode_bound(
                entry["expected_response_jcs_lf_base64"], entry["expected_response_raw_sha256"], f"{name} response"
            )
            if request != jcs_bytes(entry["semantic_request"]) + b"\n":
                raise OracleError(f"{name}: request is not independent JCS+LF")
            if response != jcs_bytes(entry["expected_response"]) + b"\n":
                raise OracleError(f"{name}: response is not independent JCS+LF")
            self._verify_response_seal(entry["expected_response"], "receipt_sha256")
            self._add_record(request, response, f"{name}:{entry['entry_id']}")
        return len(entries)

    def _load_wrapper(self, name: str, pack: Mapping[str, object]) -> int:
        pairs = pack["pairs"]
        if len(pairs) != pack["pair_count"]:
            raise OracleError(f"{name}: pair count mismatch")
        self._verify_case_seals(pack)
        count = 0
        for pair in pairs:
            if self_zero_digest(pair, "pair_sha256") != pair["pair_sha256"]:
                raise OracleError(f"{name}: pair self-zero mismatch")
            for arm_name in ("b1_arm", "b1_attention_arm"):
                arm = pair[arm_name]
                request = self._decode_bound(
                    arm["request_jcs_lf_base64"], arm["request_raw_sha256"], f"{name} {arm_name} request"
                )
                response = self._decode_bound(
                    arm["response_jcs_lf_base64"], arm["response_raw_sha256"], f"{name} {arm_name} response"
                )
                if request != jcs_bytes(arm["wrapper_request"]) + b"\n":
                    raise OracleError(f"{name}: wrapper request is not independent JCS+LF")
                if response != jcs_bytes(arm["wrapper_response"]) + b"\n":
                    raise OracleError(f"{name}: wrapper response is not independent JCS+LF")
                self._verify_response_seal(arm["wrapper_response"], "response_sha256")
                transcript = arm["transcript"]
                if self_zero_digest(transcript, "record_sha256") != transcript["record_sha256"]:
                    raise OracleError(f"{name}: wrapper transcript self-zero mismatch")
                card = arm["wrapper_request"].get("attention_card")
                if card is not None and self_zero_digest(card, "card_sha256") != card["card_sha256"]:
                    raise OracleError(f"{name}: attention-card self-zero mismatch")
                normalized = dict(arm["wrapper_response"])
                normalized.pop("configuration")
                normalized.pop("response_sha256")
                if sha256_upper(jcs_bytes(normalized)) != arm["normalized_output_sha256"]:
                    raise OracleError(f"{name}: normalized response digest mismatch")
                self._add_record(request, response, f"{name}:{pair['pair_id']}:{arm_name}")
                count += 1
        return count

    def expected_record(self, raw: bytes) -> bytes:
        classification = classify_record(raw)
        if classification.code is not None:
            return error_response(classification.code, classification.pointer, classification.request_id)
        try:
            return self.records[raw]
        except KeyError as exc:
            raise OutsideFixture("valid record is outside the four frozen fixture packs") from exc

    def validation_receipt(self) -> dict[str, object]:
        bindings = [
            {"request_sha256": sha256_upper(request), "response_sha256": sha256_upper(response)}
            for request, response in sorted(self.records.items(), key=lambda item: sha256_upper(item[0]))
        ]
        return {
            "fixture_binding_sha256": sha256_upper(jcs_bytes(bindings)),
            "pack_receipts": self.pack_receipts,
            "semantic_records": self.semantic_records,
            "status": "PASS",
            "total_unique_records": len(self.records),
            "wrapper_records": self.wrapper_records,
        }


def relation_physical_line_equality(records: Sequence[bytes], oracle: FixtureOracle) -> bool:
    isolated = [oracle.expected_record(record) for record in records]
    batch = b"".join(oracle.expected_record(record) for record in records)
    return batch == b"".join(isolated)


def relation_input_partition_invariance(raw: bytes, partitions: Sequence[bytes], oracle: FixtureOracle) -> bool:
    return b"".join(partitions) == raw and oracle.expected_record(b"".join(partitions)) == oracle.expected_record(raw)


def relation_request_sequence_permutation(records: Sequence[bytes], oracle: FixtureOracle) -> bool:
    expected = {sha256_upper(record): oracle.expected_record(record) for record in records}
    for order in permutations(records):
        for record, response in zip(order, (oracle.expected_record(item) for item in order)):
            if response != expected[sha256_upper(record)]:
                return False
    return True


def relation_concurrency_vs_isolated(tagged_records: Sequence[tuple[str, bytes]], oracle: FixtureOracle) -> bool:
    isolated = {tag: oracle.expected_record(record) for tag, record in tagged_records}
    interleaved = {tag: oracle.expected_record(record) for tag, record in reversed(tagged_records)}
    return isolated == interleaved


def relation_oversize_drain_next_record(oversize: bytes, next_record: bytes, oracle: FixtureOracle) -> bool:
    first = classify_record(oversize)
    if first.code != "ERR_LIMIT":
        return False
    after_drain = oracle.expected_record(next_record)
    isolated = oracle.expected_record(next_record)
    return after_drain == isolated


def relation_deterministic_replay(observations: Mapping[str, Sequence[bytes]]) -> bool:
    """Compare supplied process/platform observations; this function performs no I/O."""

    flattened = [item for runs in observations.values() for item in runs]
    return bool(flattened) and all(item == flattened[0] for item in flattened)


def _emit_record(raw: bytes) -> int:
    classification = classify_record(raw)
    if classification.code is not None:
        output = error_response(classification.code, classification.pointer, classification.request_id)
        sys.stdout.buffer.write(output)
        return 3 if classification.code == "ERR_INTERNAL" else 2
    oracle = FixtureOracle()
    try:
        output = oracle.expected_record(raw)
    except OutsideFixture as exc:
        sys.stderr.write(str(exc) + "\n")
        return 3
    sys.stdout.buffer.write(output)
    return int(json.loads(output)["exit_code"])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-fixtures")
    hex_parser = sub.add_parser("classify-hex")
    hex_parser.add_argument("hex")
    b64_parser = sub.add_parser("expected-base64")
    b64_parser.add_argument("base64")
    args = parser.parse_args(argv)

    if args.command == "validate-fixtures":
        receipt = FixtureOracle().validation_receipt()
        sys.stdout.buffer.write(jcs_bytes(receipt) + b"\n")
        return 0
    if args.command == "classify-hex":
        try:
            raw = bytes.fromhex(args.hex)
        except ValueError as exc:
            parser.error(str(exc))
        return _emit_record(raw)
    if args.command == "expected-base64":
        try:
            raw = base64.b64decode(args.base64, validate=True)
        except ValueError as exc:
            parser.error(str(exc))
        return _emit_record(raw)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
