"""Seeded stdlib property tests for the grounded 0.4 contract surface.

The recorded seed is 0x5EED8785.  All generators are bounded, deterministic,
network-free, and limited to the contract's integer-only, NFC JSON profile.
"""
from __future__ import annotations

import copy
import json
import pathlib
import random
import sys
from collections.abc import Callable
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rr_api  # noqa: E402
from rr_api import b1  # noqa: E402

pcb_runner = rr_api.pcb_runner

SEED = 0x5EED8785
RNG = random.Random(SEED)
TARGET_CASES = {
    "jcs_idempotence": 128,
    "parse_profile_agreement": 129,
    "pointer_roundtrip": 128,
    "precedence_short_circuit": 3,
    "self_zero_seal": 96,
    "strict_equal": 96,
    "utf16_member_order": 65,
}

failures = 0
checks = 0
cases = {name: 0 for name in TARGET_CASES}


def check(name: str, condition: bool, detail: str = "") -> None:
    global checks, failures
    checks += 1
    if not condition:
        failures += 1
        suffix = f" detail={detail[:240]}" if detail else ""
        print(f"FAIL {name}{suffix}")


def record_case(property_name: str) -> None:
    cases[property_name] += 1


def expect_evaluator_error(name: str, call: Callable[[], Any]) -> None:
    try:
        call()
    except b1.EvaluatorError:
        check(name, True)
    except Exception as err:  # a different exception is a contract failure
        check(name, False, f"wrong exception {type(err).__name__}: {err}")
    else:
        check(name, False, "EvaluatorError was not raised")


_TEXT_ALPHABET = (
    "a",
    "Z",
    "0",
    " ",
    "~",
    "/",
    '"',
    "\\",
    "\n",
    "\t",
    "é",
    "Ω",
    "中",
    "😀",
)


def random_text(max_length: int = 10) -> str:
    return "".join(RNG.choice(_TEXT_ALPHABET) for _ in range(RNG.randrange(max_length + 1)))


def random_scalar() -> Any:
    choice = RNG.randrange(6)
    if choice == 0:
        return None
    if choice == 1:
        return bool(RNG.getrandbits(1))
    if choice == 2:
        return RNG.randint(b1.SAFE_INTEGER_MIN, b1.SAFE_INTEGER_MAX)
    if choice == 3:
        return RNG.randint(-10_000, 10_000)
    return random_text()


def random_json(depth: int = 0) -> Any:
    if depth >= 4 or RNG.random() < 0.42:
        return random_scalar()
    if RNG.random() < 0.48:
        return [random_json(depth + 1) for _ in range(RNG.randrange(5))]

    items: list[tuple[str, Any]] = []
    for index in range(RNG.randrange(5)):
        # The suffix makes keys unique without constraining the Unicode prefix.
        key = f"{random_text(6)}#{index}-{RNG.randrange(1_000_000)}"
        items.append((key, random_json(depth + 1)))
    RNG.shuffle(items)
    return dict(items)


def reverse_object_insertion(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: reverse_object_insertion(child)
            for key, child in reversed(list(value.items()))
        }
    if isinstance(value, list):
        return [reverse_object_insertion(child) for child in value]
    return value


def property_jcs_idempotence() -> None:
    property_name = "jcs_idempotence"
    for index in range(TARGET_CASES[property_name]):
        value = random_json()
        canonical = b1.jcs_bytes(value)
        reparsed = json.loads(canonical.decode("utf-8"))
        check(
            f"jcs:{index}:roundtrip-value",
            b1._strict_equal(reparsed, value),
            canonical.decode("utf-8", errors="replace"),
        )
        check(f"jcs:{index}:idempotent", b1.jcs_bytes(reparsed) == canonical)
        check(
            f"jcs:{index}:insertion-independent",
            b1.jcs_bytes(reverse_object_insertion(value)) == canonical,
        )
        record_case(property_name)


def utf16_key(key: str) -> bytes:
    return key.encode("utf-16-be")


def canonical_root_keys(value: dict[str, Any]) -> list[str]:
    encoded = b1.jcs_bytes(value)
    return list(json.loads(encoded.decode("utf-8")).keys())


def property_utf16_member_order() -> None:
    property_name = "utf16_member_order"

    # U+10000 is greater by code point but sorts before U+E000 by UTF-16
    # code units (D800 DC00 precedes E000), the RFC 8785 edge most easily
    # missed by native code-point ordering.
    edge_keys = ["\ue000", "\U00010000", "\ufffd", "\U0010ffff"]
    actual = canonical_root_keys({key: index for index, key in enumerate(edge_keys)})
    expected = sorted(edge_keys, key=utf16_key)
    check("utf16:edge:law", actual == expected, f"actual={actual!r} expected={expected!r}")
    check("utf16:edge:astral-before-bmp", actual.index("\U00010000") < actual.index("\ue000"))
    check("utf16:edge:not-codepoint-order", actual != sorted(edge_keys))
    record_case(property_name)

    for index in range(TARGET_CASES[property_name] - 1):
        astral = chr(RNG.randint(0x1F300, 0x1FAFF))
        bmp = chr(RNG.randint(0xE000, 0xF8FF))
        keys = [f"{bmp}:{index}", f"{astral}:{index}", f"a:{index}", f"Ω:{index}"]
        RNG.shuffle(keys)
        actual = canonical_root_keys({key: offset for offset, key in enumerate(keys)})
        expected = sorted(keys, key=utf16_key)
        check(f"utf16:{index}:law", actual == expected, f"actual={actual!r}")
        check(
            f"utf16:{index}:astral-bmp-edge",
            actual.index(f"{astral}:{index}") < actual.index(f"{bmp}:{index}"),
        )
        record_case(property_name)


def property_self_zero_seal() -> None:
    property_name = "self_zero_seal"
    field = "receipt_sha256"
    for index in range(TARGET_CASES[property_name]):
        unsigned = {"case": index, "payload": random_json(), field: b1.ZERO64}
        digest = b1.self_zero_sha256(unsigned, field)
        sealed = dict(unsigned)
        sealed[field] = digest
        check(f"seal:{index}:source-unmodified", unsigned[field] == b1.ZERO64)
        check(f"seal:{index}:shape", len(digest) == 64 and digest == digest.upper())
        check(f"seal:{index}:valid", sealed[field] == b1.self_zero_sha256(sealed, field))

        roundtripped = json.loads(b1.jcs_bytes(sealed).decode("utf-8"))
        check(
            f"seal:{index}:wire-roundtrip",
            roundtripped[field] == b1.self_zero_sha256(roundtripped, field),
        )

        payload_tamper = copy.deepcopy(roundtripped)
        payload_tamper["tamper_marker"] = f"changed-{index}"
        check(
            f"seal:{index}:payload-tamper-rejected",
            payload_tamper[field] != b1.self_zero_sha256(payload_tamper, field),
        )

        seal_tamper = copy.deepcopy(roundtripped)
        replacement = "F" if seal_tamper[field][0] != "F" else "E"
        seal_tamper[field] = replacement + seal_tamper[field][1:]
        check(
            f"seal:{index}:seal-tamper-rejected",
            seal_tamper[field] != b1.self_zero_sha256(seal_tamper, field),
        )
        record_case(property_name)


def unescape_pointer_token(encoded: str) -> str:
    return encoded.replace("~1", "/").replace("~0", "~")


def decode_pointer(pointer: str) -> list[str]:
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise ValueError("not an RFC 6901 pointer")
    return [unescape_pointer_token(token) for token in pointer[1:].split("/")]


def random_pointer_token() -> str:
    return random_text(8)


def property_pointer_roundtrip() -> None:
    property_name = "pointer_roundtrip"
    edge_tokens = ["", "~", "/", "~0", "~1", "a~b/c", "é/😀~"]
    saw_tilde_escape = False
    saw_slash_escape = False

    for index in range(TARGET_CASES[property_name]):
        tokens = edge_tokens if index == 0 else [
            random_pointer_token() for _ in range(RNG.randint(1, 5))
        ]
        marker = {"resolved_case": index}
        document: Any = marker
        for token in reversed(tokens):
            document = {token: document}

        pointer = ""
        for token in tokens:
            pointer = b1._pointer(pointer, token)
        saw_tilde_escape |= "~0" in pointer
        saw_slash_escape |= "~1" in pointer

        check(f"pointer:{index}:escape-inverse", decode_pointer(pointer) == tokens)
        check(
            f"pointer:{index}:resolution",
            b1.resolve_input_pointer(document, pointer) is marker,
            pointer,
        )

        array_document = {"rows": [None, marker]}
        array_pointer = b1._pointer(b1._pointer("", "rows"), 1)
        check(
            f"pointer:{index}:array-index",
            b1.resolve_input_pointer(array_document, array_pointer) is marker,
        )
        record_case(property_name)

    check("pointer:exercised-tilde-escape", saw_tilde_escape)
    check("pointer:exercised-slash-escape", saw_slash_escape)
    expect_evaluator_error(
        "pointer:reject-no-leading-slash",
        lambda: b1.resolve_input_pointer({}, "not/a/pointer"),
    )
    expect_evaluator_error(
        "pointer:reject-missing-member",
        lambda: b1.resolve_input_pointer({}, "/missing"),
    )
    expect_evaluator_error(
        "pointer:reject-noncanonical-index",
        lambda: b1.resolve_input_pointer({"rows": [marker]}, "/rows/01"),
    )


def property_strict_equal() -> None:
    property_name = "strict_equal"
    for index in range(TARGET_CASES[property_name]):
        boolean = bool(RNG.getrandbits(1))
        integer = int(boolean)
        left: Any = boolean if index % 2 == 0 else integer
        right: Any = integer if index % 2 == 0 else boolean

        for level in range(RNG.randint(1, 6)):
            context = random_scalar()
            if RNG.getrandbits(1):
                left = {"context": copy.deepcopy(context), f"level_{level}": left}
                right = {"context": copy.deepcopy(context), f"level_{level}": right}
            else:
                left = [copy.deepcopy(context), left, level]
                right = [copy.deepcopy(context), right, level]

        check(f"strict-equal:{index}:python-conflates", left == right)
        check(f"strict-equal:{index}:bool-int-distinct", not b1._strict_equal(left, right))
        check(
            f"strict-equal:{index}:recursive-positive",
            b1._strict_equal(left, copy.deepcopy(left)),
        )
        record_case(property_name)


def clean_scan(scan: dict[str, Any]) -> bool:
    return scan == {
        "nfc": [],
        "number": [],
        "duplicate": False,
        "canonical": False,
        "limit": False,
        "nesting_exceeded": False,
        "complete": True,
    }


def property_parse_profile_agreement() -> None:
    property_name = "parse_profile_agreement"
    for index in range(TARGET_CASES[property_name] - 1):
        expected = random_json()
        raw = b1.jcs_bytes(expected)
        payload = raw.decode("utf-8")
        scan = b1.scan_parse_profile(payload)
        parsed, errors = pcb_runner._parse(raw + b"\n")
        check(f"parse-profile:{index}:scanner-clean", clean_scan(scan), repr(scan))
        check(f"parse-profile:{index}:tree-accepts", errors == [], repr(errors))
        check(
            f"parse-profile:{index}:tree-agrees",
            b1._strict_equal(parsed, expected),
            f"parsed={parsed!r} expected={expected!r}",
        )
        check(f"parse-profile:{index}:tree-recanonicalizes", b1.jcs_bytes(parsed) == raw)
        record_case(property_name)

    # A tree-valid but noncanonical spelling must be found by both paths:
    # the scanner marks canonical-byte failure and _parse pools ERR_JSON.
    noncanonical = '{"a": [1,true]}'
    scan = b1.scan_parse_profile(noncanonical)
    parsed, errors = pcb_runner._parse(noncanonical.encode("utf-8") + b"\n")
    check("parse-profile:negative:scan-complete", scan["complete"])
    check("parse-profile:negative:scanner-rejects", scan["canonical"])
    check("parse-profile:negative:tree-still-builds", parsed == {"a": [1, True]})
    check("parse-profile:negative:parser-rejects", ("ERR_JSON", "") in errors, repr(errors))
    record_case(property_name)


def eq(path: str, value: Any) -> dict[str, Any]:
    return {"op": "EQ", "path": path, "value": value}


def base64_bomb() -> dict[str, Any]:
    return {
        "op": "BASE64_SHA256_NE",
        "base64_path": "/bad_base64",
        "digest_path": "/digest",
    }


def property_precedence_short_circuit() -> None:
    property_name = "precedence_short_circuit"
    class1, class2, class3 = b1.CLASS_PRECEDENCE
    tables = {
        "PROP_FIRST": {
            class1: eq("/first", True),
            class2: base64_bomb(),
            class3: base64_bomb(),
        },
        "PROP_SECOND": {
            class1: eq("/first", True),
            class2: eq("/second", True),
            class3: base64_bomb(),
        },
        "PROP_REACH_BOMB": {
            class1: eq("/first", True),
            class2: eq("/second", True),
            class3: base64_bomb(),
        },
    }
    original_decision_table = b1.decision_table
    b1.decision_table = lambda: tables
    try:
        document = {
            "first": True,
            "second": True,
            "bad_base64": "%",
            "digest": b1.ZERO64,
        }
        behavior, fired = b1.classify("PROP_FIRST", document)
        check("precedence:first:class", behavior == class1, behavior)
        check(
            "precedence:first:later-false",
            fired == {class1: True, class2: False, class3: False},
            repr(fired),
        )
        record_case(property_name)

        document["first"] = False
        behavior, fired = b1.classify("PROP_SECOND", document)
        check("precedence:second:class", behavior == class2, behavior)
        check(
            "precedence:second:later-false",
            fired == {class1: False, class2: True, class3: False},
            repr(fired),
        )
        record_case(property_name)

        document["second"] = False
        expect_evaluator_error(
            "precedence:negative:bomb-reachable-without-match",
            lambda: b1.classify("PROP_REACH_BOMB", document),
        )
        record_case(property_name)
    finally:
        b1.decision_table = original_decision_table


PROPERTIES: tuple[tuple[str, Callable[[], None]], ...] = (
    ("jcs_idempotence", property_jcs_idempotence),
    ("utf16_member_order", property_utf16_member_order),
    ("self_zero_seal", property_self_zero_seal),
    ("pointer_roundtrip", property_pointer_roundtrip),
    ("strict_equal", property_strict_equal),
    ("parse_profile_agreement", property_parse_profile_agreement),
    ("precedence_short_circuit", property_precedence_short_circuit),
)

for property_name, property_test in PROPERTIES:
    try:
        property_test()
    except Exception as err:
        check(
            f"property:{property_name}:uncaught",
            False,
            f"{type(err).__name__}: {err}",
        )
    check(
        f"property:{property_name}:case-count",
        cases[property_name] == TARGET_CASES[property_name],
        f"actual={cases[property_name]} target={TARGET_CASES[property_name]}",
    )

print(
    "grounded-0.4 properties: "
    f"seed=0x{SEED:08X} cases={json.dumps(cases, sort_keys=True)} "
    f"checks={checks} failures={failures}"
)
sys.exit(1 if failures else 0)
