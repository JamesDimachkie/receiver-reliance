"""One bounded ingest law for harnesses that read bytes they did not produce.

Intake 10 cluster C2 recorded that the core carries a single strict total ingest
law while peripheral loaders each canonicalize on their own terms, and that the
remainder becomes blocking at the first external consumer
(`orchestration/robustness/INTAKE_10_SCAN_DISPOSITIONS.md`, `TRUST_MODEL.md`).
This module is that shared law for the verification harnesses.

The law has two halves and they are deliberately separate, because measurement
showed they behave differently against bytes this repository already publishes:

**Safety** — duplicate object keys, non-finite constants, lone surrogates, and
the core's nesting and member bounds. These are what a sender who is adversarial
to the receiver's tooling actually exploits: a duplicate key silently changes
which value a verifier reads, `NaN` propagates into comparisons that then
succeed, a lone surrogate breaks any downstream re-encode. All 69 receipts under
`portability/receipts/`, `perf/receipts/` and `second-implementation/receipts/`
satisfy this half, so requiring it rejects nothing already published.

**Framing** — exactly one trailing LF, no BOM, no CR, NFC. This is a format
property, not a safety property, and three published receipts deliberately carry
CRLF: `.gitattributes` is `* -text` and `verify_hygiene` admits their carriage
returns byte-exactly rather than normalizing them. Requiring framing everywhere
would therefore reject already-pinned bytes, so `framing_problems` is offered
separately and applied only where the format is actually guaranteed.

The bounds are read from the frozen core rather than restated here. A module that
copies `MAX_NESTING` is free to drift from the authority it claims to share, which
is the defect this module exists to remove.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import unicodedata
from typing import Any

REPO = pathlib.Path(__file__).resolve().parent.parent
_CORE = REPO / "baseline-run" / "implementation-output-0.3" / "b1_capabilities.py"


def _load_core():
    """Load the frozen core so its bounds are the ones enforced here."""
    if "rr_strict_ingest_core" in sys.modules:
        return sys.modules["rr_strict_ingest_core"]
    if not _CORE.is_file():
        raise RuntimeError(f"frozen core absent: {_CORE}")
    spec = importlib.util.spec_from_file_location("rr_strict_ingest_core", _CORE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["rr_strict_ingest_core"] = module
    spec.loader.exec_module(module)
    return module


_core = _load_core()

#: Nesting and member ceilings, taken from the frozen core, never restated.
MAX_NESTING: int = _core.MAX_NESTING
MAX_MEMBERS_OR_ITEMS: int = _core.MAX_MEMBERS_OR_ITEMS


class IngestError(ValueError):
    """Raised for any input the shared law refuses. Never a bare exception.

    Harnesses previously surfaced malformed input as JSONDecodeError,
    RecursionError, or silent acceptance depending on which defect it carried.
    One error type means a caller can fail closed on all of them.
    """


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    for key, _ in pairs:
        if key in seen:
            raise IngestError(f"duplicate object key: {key!r}")
        seen.add(key)
    return dict(pairs)


def _reject_constant(text: str) -> None:
    raise IngestError(f"non-finite JSON constant: {text}")


def _walk_bounds(value: Any, depth: int, pointer: str) -> None:
    if depth > MAX_NESTING:
        raise IngestError(f"nesting deeper than {MAX_NESTING} at {pointer or '/'}")
    if isinstance(value, dict):
        if len(value) > MAX_MEMBERS_OR_ITEMS:
            raise IngestError(f"more than {MAX_MEMBERS_OR_ITEMS} members at {pointer or '/'}")
        for key, item in value.items():
            _walk_bounds(item, depth + 1, f"{pointer}/{key}")
    elif isinstance(value, list):
        if len(value) > MAX_MEMBERS_OR_ITEMS:
            raise IngestError(f"more than {MAX_MEMBERS_OR_ITEMS} items at {pointer or '/'}")
        for index, item in enumerate(value):
            _walk_bounds(item, depth + 1, f"{pointer}/{index}")
    elif isinstance(value, str):
        for character in value:
            if 0xD800 <= ord(character) <= 0xDFFF:
                raise IngestError(f"lone surrogate in string at {pointer or '/'}")


def load_safe(raw: bytes, *, label: str = "input") -> Any:
    """Parse bytes under the safety half. Raises IngestError, never anything else.

    Bounds are checked iteratively-by-recursion over the parsed value rather than
    during the scan, so the ceiling is enforced even when CPython's own parser
    would have accepted the shape.
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise IngestError(f"{label}: bytes required, got {type(raw).__name__}")
    try:
        text = bytes(raw).decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise IngestError(f"{label}: not valid UTF-8: {exc}") from exc
    try:
        value = json.loads(
            text, object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant
        )
    except IngestError:
        raise
    except RecursionError as exc:
        raise IngestError(f"{label}: nesting exceeded the parser's own limit") from exc
    except json.JSONDecodeError as exc:
        raise IngestError(f"{label}: invalid JSON: {exc}") from exc
    try:
        _walk_bounds(value, 0, "")
    except RecursionError as exc:
        raise IngestError(f"{label}: nesting deeper than {MAX_NESTING}") from exc
    except IngestError as exc:
        raise IngestError(f"{label}: {exc}") from exc
    return value


def framing_problems(raw: bytes) -> list[str]:
    """The format half, returned rather than raised.

    Callers decide whether framing applies: it does for bytes this repository
    generates, and it does not for the three published receipts that deliberately
    carry CRLF under `* -text`.
    """
    problems: list[str] = []
    if raw.startswith(b"\xef\xbb\xbf"):
        problems.append("leading BOM")
    if b"\r" in raw:
        problems.append("carriage return")
    if not raw.endswith(b"\n"):
        problems.append("no trailing LF")
    elif raw.endswith(b"\n\n"):
        problems.append("more than one trailing LF")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError:
        problems.append("not valid UTF-8")
        return problems
    if unicodedata.normalize("NFC", text) != text:
        problems.append("not NFC")
    return problems


def load_canonical(raw: bytes, *, label: str = "input") -> Any:
    """Both halves, for bytes whose format this repository itself guarantees."""
    problems = framing_problems(raw)
    if problems:
        raise IngestError(f"{label}: framing: {', '.join(problems)}")
    return load_safe(raw, label=label)
