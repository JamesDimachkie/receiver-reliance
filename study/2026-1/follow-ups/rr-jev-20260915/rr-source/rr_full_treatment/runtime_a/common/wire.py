"""Canonical wire primitives and strict parser for treatment-v6."""

from __future__ import annotations

import hashlib
import json
import struct
import unicodedata
from typing import Any

INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1
ZERO64 = "0" * 64

STAGE_ORDER = {
    name: index
    for index, name in enumerate(
        (
            "INTERNAL",
            "PYTHON_TYPE",
            "ADMISSION",
            "WIRE_UNICODE",
            "JSON",
            "VALUE_UNICODE",
            "CANONICAL",
            "CLOSED_SCHEMA",
            "MODULE_SEMANTICS",
        )
    )
}

CODE_ORDER = {
    "INTERNAL": ("BOUNDARY_EXCEPTION",),
    "PYTHON_TYPE": ("ARGUMENT_TYPE",),
    "ADMISSION": (
        "COMMON_OVERSIZE",
        "STATE_OVERSIZE",
        "DEPTH_LIMIT",
        "COLLECTION_LIMIT",
        "STRING_LIMIT",
    ),
    "WIRE_UNICODE": ("UTF8", "BOM"),
    "JSON": ("SYNTAX", "DUPLICATE_KEY", "INTEGER_RANGE", "FLOAT_FORBIDDEN"),
    "VALUE_UNICODE": ("SURROGATE", "NFC"),
    "CANONICAL": ("NONCANONICAL",),
    "CLOSED_SCHEMA": (
        "UNKNOWN_FIELD",
        "MISSING_FIELD",
        "FIELD_TYPE",
        "FIELD_VALUE",
        "CROSS_FIELD",
    ),
    # diagnostic_authority.code_order_by_stage declares this stage too.  No Fault is built at it
    # today, but leaving it out made Fault.key a partial function over a declared stage.
    "MODULE_SEMANTICS": (
        "U_TRANSPARENT",
        "S_COMPONENT_UNRESOLVED",
        "S_THRESHOLD_CLEAR",
        "S_THRESHOLD_REACHED",
        "R_DERIVATION_UNRESOLVED",
        "R_ENGINE_CONCLUSIVE",
        "R_ENGINE_UNRESOLVED",
        "R_LINEAGE_CONCLUSIVE",
        "R_LINEAGE_UNRESOLVED",
        "R_ACCEPTANCE_APPLICABLE",
        "R_ACCEPTANCE_INAPPLICABLE",
        "R_ACCEPTANCE_CONFLICT",
        "R_ACCEPTANCE_UNKNOWN",
    ),
}


class Fault:
    """One authority-ordered diagnostic, without exception side effects."""

    __slots__ = ("stage", "code", "pointer", "occurrence", "document", "own_type_gate")

    def __init__(
        self,
        stage: str,
        code: str,
        pointer: str = "",
        occurrence: int = 0,
        document: str = "COMMON",
        own_type_gate: bool = False,
    ) -> None:
        self.stage = stage
        self.code = code
        self.pointer = pointer
        self.occurrence = occurrence
        self.document = document
        # True only when this fault is the value's own type/oneOf gate at its own pointer.
        # diagnostic_authority.atomic_target_projection binds ARRAY_ITEM_INCOMPATIBLE to the
        # parent array pointer, so the array-items walk re-points exactly these faults and
        # clears the marker so an outer array never re-points a nested one.
        self.own_type_gate = own_type_gate

    def key(self) -> tuple[int, int, int, bytes, int]:
        codes = CODE_ORDER[self.stage]
        return (
            STAGE_ORDER[self.stage],
            codes.index(self.code),
            0 if self.document == "COMMON" else 1,
            self.pointer.encode("utf-8"),
            self.occurrence,
        )


class _DuplicateKey(Exception):
    __slots__ = ("key", "occurrence")

    def __init__(self, key: str, occurrence: int) -> None:
        self.key = key
        self.occurrence = occurrence


class _IntegerRange(Exception):
    pass


class _FloatForbidden(Exception):
    pass


def frame(value: bytes) -> bytes:
    return struct.pack(">Q", len(value)) + value


def jcs(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def cj6(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def dh6(domain: str, value: Any) -> str:
    payload = cj6(value)
    preimage = domain.encode("ascii") + b"\0" + struct.pack(">Q", len(payload)) + payload
    return hashlib.sha256(preimage).hexdigest().upper()


def bdh6(domain: str, value: bytes) -> str:
    preimage = domain.encode("ascii") + b"\0" + struct.pack(">Q", len(value)) + value
    return hashlib.sha256(preimage).hexdigest().upper()


def stream_root(domain: str, rows: list[Any]) -> str:
    digest = hashlib.sha256()
    digest.update(domain.encode("ascii"))
    digest.update(b"\0")
    for row in rows:
        encoded = cj6(row)
        digest.update(struct.pack(">Q", len(encoded)))
        digest.update(encoded)
    return digest.hexdigest().upper()


def escape_pointer(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def child_pointer(pointer: str, token: str | int) -> str:
    return pointer + "/" + escape_pointer(str(token))


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    counts: dict[str, int] = {}
    for key, value in pairs:
        occurrence = counts.get(key, 0)
        if occurrence:
            raise _DuplicateKey(key, occurrence)
        counts[key] = occurrence + 1
        result[key] = value
    return result


def _integer(token: str) -> int:
    value = int(token)
    if value < INT64_MIN or value > INT64_MAX:
        raise _IntegerRange()
    return value


def _float(_token: str) -> None:
    raise _FloatForbidden()


def _constant(_token: str) -> None:
    raise _FloatForbidden()


def _value_faults(value: Any, document: str, unicode_stage: bool) -> list[Fault]:
    """Collect every ADMISSION structural fault (and, when the JSON stage raised none,
    every VALUE_UNICODE fault) reachable in the parsed value.

    diagnostic_authority.fault_selection: "Collect all faults whose prerequisites were reached.
    Select the minimum tuple".  The whole value is walked, so a DEPTH_LIMIT deeper in the
    document beats a COLLECTION_LIMIT met earlier, and an ADMISSION fault (stage 2) beats every
    VALUE_UNICODE fault (stage 5) wherever either sits.  A node at the depth limit is not
    descended: nothing below it can carry a smaller tuple.
    """
    faults: list[Fault] = []
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        if depth >= 24 and isinstance(current, (dict, list)):
            faults.append(Fault("ADMISSION", "DEPTH_LIMIT", occurrence=24, document=document))
            continue
        if isinstance(current, dict):
            if len(current) > 4096:
                faults.append(Fault("ADMISSION", "COLLECTION_LIMIT", occurrence=4096, document=document))
            for key in current:
                faults.extend(_string_faults(key, document, unicode_stage))
            for key in sorted(current, reverse=True):
                stack.append((current[key], depth + 1))
        elif isinstance(current, list):
            if len(current) > 4096:
                faults.append(Fault("ADMISSION", "COLLECTION_LIMIT", occurrence=4096, document=document))
            for member in reversed(current):
                stack.append((member, depth + 1))
        elif isinstance(current, str):
            faults.extend(_string_faults(current, document, unicode_stage))
    return faults


def _string_faults(text: str, document: str, unicode_stage: bool) -> list[Fault]:
    faults: list[Fault] = []
    if len(text.encode("utf-8", "surrogatepass")) > 65536:
        faults.append(Fault("ADMISSION", "STRING_LIMIT", occurrence=65536, document=document))
    if unicode_stage:
        if any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
            faults.append(Fault("VALUE_UNICODE", "SURROGATE", document=document))
        if unicodedata.normalize("NFC", text) != text:
            faults.append(Fault("VALUE_UNICODE", "NFC", document=document))
    return faults


def parse_document(raw: bytes, document: str, limit: int) -> tuple[Any | None, Fault | None]:
    if len(raw) > limit:
        code = "COMMON_OVERSIZE" if document == "COMMON" else "STATE_OVERSIZE"
        return None, Fault("ADMISSION", code, document=document)
    # diagnostic_authority.fault_selection: "Collect all faults whose prerequisites were reached.
    # Select the minimum tuple ... A parser-stage fault prevents only later stages for that
    # document."  Both WIRE_UNICODE checks are reached on every document (the BOM test does not
    # prevent the UTF-8 test: they are one stage), so a BOM prefix beside an invalid octet selects
    # UTF8 (code index 0) at that octet's offset.  A WIRE_UNICODE fault prevents the JSON stage
    # and everything after it.
    collected: list[Fault] = []
    if raw.startswith(b"\xef\xbb\xbf"):
        collected.append(Fault("WIRE_UNICODE", "BOM", document=document))
    text = None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        collected.append(Fault("WIRE_UNICODE", "UTF8", occurrence=exc.start, document=document))
    if collected or text is None:
        return None, min(collected, key=Fault.key)
    # Every JSON-stage fault the parser reaches is collected, and the hooks continue parsing
    # (returning a placeholder) so a duplicate key later in the document is still reached and, at
    # code index 1, beats INTEGER_RANGE (2) and FLOAT_FORBIDDEN (3).

    # Declared reading (pair confirmation review L-1): the DUPLICATE_KEY pointer is the full
    # RFC6901 pointer of the duplicated member from the document root ("For schema arrays pointer
    # is RFC6901 with ~0/~1 escaping"; the one registered variant pins `/x` at the root, which
    # both readings reproduce).  The pairs hook carries no path context, so it records every
    # (parent, key, item) edge it builds -- including the members an outer duplicate key later
    # discards from the constructed value -- and the pointer is resolved afterwards by walking
    # those recorded edges from the root (round-2 confirmation review L-1: a parent discarded by
    # an outer duplicate must still resolve to its full pointer).
    duplicates: list[tuple[dict[str, Any], str, int]] = []
    edges: dict[int, list[tuple[str, Any]]] = {}
    built: list[dict[str, Any]] = []

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        counts: dict[str, int] = {}
        for key, item in pairs:
            occurrence = counts.get(key, 0)
            if occurrence:
                duplicates.append((result, key, occurrence))
            counts[key] = occurrence + 1
            result[key] = item
        edges[id(result)] = list(pairs)
        built.append(result)
        return result

    def object_pointers(root: Any) -> dict[int, str]:
        found: dict[int, str] = {}
        stack: list[tuple[Any, str]] = [(root, "")]
        while stack:
            current, pointer = stack.pop()
            if isinstance(current, dict):
                if id(current) in found:
                    continue
                found[id(current)] = pointer
                for key, item in edges.get(id(current), ()):
                    stack.append((item, child_pointer(pointer, key)))
            elif isinstance(current, list):
                for index, item in enumerate(current):
                    stack.append((item, child_pointer(pointer, index)))
        return found

    # Numeric tokens are located by a scan of the raw text outside string literals, so each
    # INTEGER_RANGE / FLOAT_FORBIDDEN fault carries the zero-based byte offset of its token
    # (fault_selection: "For byte-offset diagnostics pointer is empty and occurrence is the zero-based
    # byte offset"; declared convention after the A/B crosscheck).
    def numeric_offsets() -> list[tuple[int, str]]:
        found: list[tuple[int, str]] = []
        in_string = False
        escaped = False
        index = 0
        length = len(text)
        while index < length:
            ch = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                index += 1
                continue
            if ch == '"':
                in_string = True
                index += 1
                continue
            for constant in ("NaN", "Infinity", "-Infinity"):
                if text.startswith(constant, index):
                    found.append((len(text[:index].encode("utf-8")), "FLOAT_FORBIDDEN"))
                    index += len(constant)
                    break
            else:
                constant = None
            if constant is not None:
                continue
            if ch == "-" or ch.isdigit():
                start = index
                while index < length and (text[index].isdigit() or text[index] in "-+.eE"):
                    index += 1
                token = text[start:index]
                byte_offset = len(text[:start].encode("utf-8"))
                if any(mark in token for mark in ".eE"):
                    found.append((byte_offset, "FLOAT_FORBIDDEN"))
                else:
                    try:
                        parsed = int(token)
                    except ValueError:
                        continue
                    if parsed < INT64_MIN or parsed > INT64_MAX:
                        found.append((byte_offset, "INTEGER_RANGE"))
                continue
            index += 1
        return found

    def integer_hook(token: str) -> int:
        parsed = int(token)
        if parsed < INT64_MIN or parsed > INT64_MAX:
            return 0
        return parsed

    def float_hook(_token: str) -> int:
        return 0

    value: Any = None
    syntax = False
    try:
        value = json.loads(
            text,
            object_pairs_hook=pairs_hook,
            parse_int=integer_hook,
            parse_float=float_hook,
            parse_constant=float_hook,
        )
    except json.JSONDecodeError as exc:
        syntax = True
        occurrence = len(text[: exc.pos].encode("utf-8"))
        collected.append(Fault("JSON", "SYNTAX", occurrence=occurrence, document=document))
    for byte_offset, code in numeric_offsets():
        collected.append(Fault("JSON", code, occurrence=byte_offset, document=document))
    if duplicates:
        # After a SYNTAX fault no value exists and SYNTAX (code index 0) wins over every
        # DUPLICATE_KEY (1) in the same document, so an unresolvable parent falls back to the
        # root-relative pointer without affecting the selection.
        parents = {} if syntax else object_pointers(value)
        for parent, key, occurrence in duplicates:
            pointer = child_pointer(parents.get(id(parent), ""), key)
            collected.append(Fault("JSON", "DUPLICATE_KEY", pointer, occurrence, document))
    # The ADMISSION structural checks (stage 2) are reached whenever a value was constructed, so
    # they are collected beside any non-SYNTAX JSON fault and, being an earlier stage, win the
    # minimum; the VALUE_UNICODE stage (5) is later than JSON and is prevented by a JSON fault.
    if not syntax:
        collected.extend(_value_faults(value, document, unicode_stage=not collected))
    if collected:
        return None, min(collected, key=Fault.key)
    try:
        canonical = jcs(value)
    except (TypeError, ValueError, UnicodeError):
        return None, Fault("CANONICAL", "NONCANONICAL", document=document)
    if canonical != raw:
        return None, Fault("CANONICAL", "NONCANONICAL", document=document)
    return value, None


def select_fault(faults: list[Fault]) -> Fault | None:
    return min(faults, key=Fault.key) if faults else None
