"""Deterministic raw-totality cases shared by the author and black-box gates."""

from __future__ import annotations

from typing import Iterator, NamedTuple


MAX_RAW_BYTES = 16_777_216


class RawCase(NamedTuple):
    family: str
    name: str
    raw: bytes
    expected_code: str
    expected_pointer: str


def _sized(prefix: bytes, suffix: bytes, size: int) -> bytes:
    padding = size - len(prefix) - len(suffix)
    if padding < 0:
        raise ValueError("prefix and suffix exceed requested size")
    return prefix + (b" " * padding) + suffix


def raw_cases() -> Iterator[RawCase]:
    # These depths cover the declared limit boundary, the historical
    # CPython recursion witness, and explicit-stack depths two orders of
    # magnitude beyond the host call-stack range.
    for depth in (127, 128, 129, 498, 1_000, 10_000):
        suffix = str(depth)
        yield RawCase("deep", f"array-open-{suffix}", b"[" * depth, "ERR_JSON", "")
        yield RawCase("deep", f"array-balanced-{suffix}", b"[" * depth + b"0" + b"]" * depth + b"\n", "ERR_SCHEMA", "")
        yield RawCase("deep", f"object-open-{suffix}", b'{"a":' * depth, "ERR_JSON", "")
        yield RawCase("deep", f"object-balanced-{suffix}", b'{"a":' * depth + b"0" + b"}" * depth + b"\n", "ERR_SCHEMA", "/format_version")
        yield RawCase("deep", f"mixed-open-{suffix}", b'[{"a":' * depth, "ERR_JSON", "")
        yield RawCase("deep", f"mixed-balanced-{suffix}", b'[{"a":' * depth + b"0" + b"}]" * depth + b"\n", "ERR_SCHEMA", "")

    # Every host-conversion boundary is crossed by integer, fraction,
    # exponent, sign, framing, leading-zero, and nested-pointer shapes.  No
    # case constructor performs an integer/float/Decimal conversion on the
    # generated token.
    for digits in (4_299, 4_300, 4_301, 10_000, 100_000, 1_000_000):
        suffix = str(digits)
        token = b"1" * digits
        yield RawCase("number", f"positive-lf-{suffix}", token + b"\n", "ERR_NUMBER", "")
        yield RawCase("number", f"positive-no-lf-{suffix}", token, "ERR_JSON", "")
        yield RawCase("number", f"negative-lf-{suffix}", b"-" + token + b"\n", "ERR_NUMBER", "")
        yield RawCase("number", f"negative-no-lf-{suffix}", b"-" + token, "ERR_JSON", "")
        yield RawCase("number", f"fraction-integer-lf-{suffix}", token + b".0\n", "ERR_NUMBER", "")
        yield RawCase("number", f"fraction-integer-no-lf-{suffix}", token + b".0", "ERR_JSON", "")
        yield RawCase("number", f"fraction-digits-lf-{suffix}", b"0." + token + b"\n", "ERR_NUMBER", "")
        yield RawCase("number", f"exponent-plus-lf-{suffix}", b"1e+" + token + b"\n", "ERR_NUMBER", "")
        yield RawCase("number", f"exponent-minus-lf-{suffix}", b"1e-" + token + b"\n", "ERR_NUMBER", "")
        yield RawCase("number", f"exponent-no-lf-{suffix}", b"1e" + token, "ERR_JSON", "")
        yield RawCase("number", f"leading-zero-lf-{suffix}", b"0" + token + b"\n", "ERR_JSON", "")
        yield RawCase("number", f"negative-leading-zero-lf-{suffix}", b"-0" + token + b"\n", "ERR_JSON", "")
        yield RawCase("number", f"array-number-lf-{suffix}", b"[" + token + b"]\n", "ERR_NUMBER", "/0")
        yield RawCase("number", f"object-number-lf-{suffix}", b'{"n":' + token + b"}\n", "ERR_NUMBER", "/n")

    # At the exact raw-byte ceiling, earlier lexical faults still win.  One
    # byte over the ceiling, ERR_LIMIT deterministically preempts them.
    for name, prefix, exact_code in (
        ("invalid-utf8", b"\xff", "ERR_UTF8"),
        ("bom", b"\xef\xbb\xbf", "ERR_BOM"),
        ("duplicate", b'{"a":0,"a":1}', "ERR_DUPLICATE_KEY"),
    ):
        yield RawCase("size", f"{name}-at-limit", _sized(prefix, b"\n", MAX_RAW_BYTES), exact_code, "")
        yield RawCase("size", f"{name}-over-limit", _sized(prefix, b"\n", MAX_RAW_BYTES + 1), "ERR_LIMIT", "")

    yield RawCase("size", "string-at-limit", b'"' + b"a" * (MAX_RAW_BYTES - 3) + b'"\n', "ERR_SCHEMA", "")
    yield RawCase("size", "string-over-limit", b'"' + b"a" * (MAX_RAW_BYTES - 2) + b'"\n', "ERR_LIMIT", "")
    yield RawCase("size", "number-at-limit", b"1" * (MAX_RAW_BYTES - 1) + b"\n", "ERR_NUMBER", "")
    yield RawCase("size", "number-over-limit", b"1" * MAX_RAW_BYTES + b"\n", "ERR_LIMIT", "")
    yield RawCase("size", "number-no-lf-at-limit", b"1" * MAX_RAW_BYTES, "ERR_JSON", "")
    yield RawCase("size", "number-no-lf-over-limit", b"1" * (MAX_RAW_BYTES + 1), "ERR_LIMIT", "")
