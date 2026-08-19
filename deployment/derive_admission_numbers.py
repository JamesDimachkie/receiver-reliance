"""Where every number in `deployment/README.md` and `admission.py` comes from.

Two halves, kept apart because they have different standing.

`--extent` is DERIVED. It reads the two published contracts and computes, for
every `decision_input_schema/oneOf` branch, the largest wire request its
declared `maxItems`/`maxLength`/`const`/`enum` permit, and the largest
structural-token count. Same bytes in, same numbers out, on any host. `--check`
compares the two maxima against the constants `admission.py` publishes and exits
nonzero on drift, so the module cannot quietly disagree with the contracts it
claims to summarize.

`--cost` is MEASURED, and generalizes to nothing. It builds five adversarial
shapes from a published fixture, fits each to a byte bound, and times the
audited decision. It reports the worst of the five, which is a lower bound on
the worst possible: a shape nobody tried here may cost more. It ships so an
operator can re-run it on their own host instead of trusting a table written on
someone else's, which is the only reading `TRUST_MODEL.md` allows of any harness
measurement anyway.

    python -B deployment/derive_admission_numbers.py --extent
    python -B deployment/derive_admission_numbers.py --extent --check
    python -B deployment/derive_admission_numbers.py --cost
"""
from __future__ import annotations

import argparse
import copy
import gc
import json
import pathlib
import re
import statistics
import sys
import time
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
for _path in (str(REPO), str(HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

CONTRACTS = {
    "0.2 primary": REPO / "baseline-run/control/B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json",
    "0.3 supplemental": REPO / "supplemental-0_3/control/B1_SUPPLEMENTAL_COMPARATOR_CONTRACT_0_3.json",
}
FIXTURE = REPO / "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json"

#: A pattern restricted to one of these alphabets admits no comma and no
#: character JCS would escape, so such a string costs one byte per character and
#: contributes no structural token.
_ASCII_ALPHABET = re.compile(r"\[A-Za-z0-9\+/\]|\[A-F0-9\]")

_STRUCTURAL = (b",", b"{", b"[")


def _tokens(raw: bytes) -> int:
    return sum(raw.count(token) for token in _STRUCTURAL)


# --------------------------------------------------------------------------
# derived half


def _string_bounds(node: dict[str, Any]) -> tuple[int | None, int | None]:
    if "const" in node:
        encoded = json.dumps(node["const"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return len(encoded), _tokens(encoded)
    if "enum" in node:
        best = (0, 0)
        for value in node["enum"]:
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(encoded) > best[0]:
                best = (len(encoded), _tokens(encoded))
        return best
    length = node.get("maxLength")
    if length is None:
        return None, None
    if _ASCII_ALPHABET.search(node.get("pattern", "")):
        return 2 + length, 0
    # Any code point but CR/LF: JCS escapes a control as \uXXXX (six bytes), and
    # a comma is a legal member of the class, so every position may be one.
    return 2 + 6 * length, length


def _bounds(node: Any) -> tuple[int | None, int | None]:
    if not isinstance(node, dict):
        return None, None
    if "oneOf" in node:
        best = (0, 0)
        for branch in node["oneOf"]:
            size, tokens = _bounds(branch)
            if size is None:
                return None, None
            if size > best[0]:
                best = (size, tokens)
        return best
    kind = node.get("type")
    if "const" in node or "enum" in node or kind == "string":
        return _string_bounds(node)
    if kind == "null":
        return 4, 0
    if kind == "boolean":
        return 5, 0
    if kind in ("integer", "number"):
        return 24, 0
    if kind == "array":
        count = node.get("maxItems")
        if count is None:
            return None, None
        item_size, item_tokens = _bounds(node.get("items", {}))
        if item_size is None:
            return None, None
        return (
            2 + count * item_size + max(count - 1, 0),
            1 + max(count - 1, 0) + count * item_tokens,
        )
    if kind == "object" or "properties" in node:
        properties = node.get("properties", {})
        if node.get("additionalProperties", True) is not False and not properties:
            return None, None
        size, tokens, members = 2, 0, 0
        for name, sub in properties.items():
            sub_size, sub_tokens = _bounds(sub)
            if sub_size is None:
                return None, None
            size += len(json.dumps(name, ensure_ascii=False).encode("utf-8")) + 1 + sub_size
            tokens += sub_tokens
            members += 1
        return size + max(members - 1, 0), tokens + 1 + max(members - 1, 0)
    return None, None


def contract_extent() -> dict[str, list[tuple[int, int, int, str]]]:
    """Per-branch `(bytes, tokens, index, obligation)`, largest first."""
    out: dict[str, list[tuple[int, int, int, str]]] = {}
    for label, path in CONTRACTS.items():
        schema = json.loads(path.read_text(encoding="utf-8"))["schemas"]["decision_input_schema"]
        rows: list[tuple[int, int, int, str]] = []
        for index, branch in enumerate(schema["oneOf"]):
            obligation = branch["properties"]["obligation_id"].get("const", "?")
            size, tokens = _bounds(branch)
            rows.append((size or -1, tokens or -1, index, obligation))
        rows.sort(reverse=True)
        out[label] = rows
    return out


def extent_maxima() -> tuple[int, int]:
    """`(max_request_bytes, max_structural_tokens)` over both contracts."""
    extent = contract_extent()
    return (
        max(row[0] for rows in extent.values() for row in rows),
        max(row[1] for rows in extent.values() for row in rows),
    )


def run_extent(check: bool) -> int:
    extent = contract_extent()
    max_bytes, max_tokens = extent_maxima()
    for label, rows in extent.items():
        print(f"=== {label}: {len(rows)} oneOf branches ===")
        for size, tokens, index, obligation in rows[:5]:
            print(f"  oneOf/{index:<2} {obligation:<7} max_bytes={size:<10} max_tokens={tokens}")
    print(f"CONTRACT EXTENT: max_request_bytes={max_bytes} max_structural_tokens={max_tokens}")
    if not check:
        return 0
    import admission

    failures: list[str] = []
    if max_bytes != admission.CONTRACT_MAX_REQUEST_BYTES:
        failures.append(
            f"CONTRACT_MAX_REQUEST_BYTES={admission.CONTRACT_MAX_REQUEST_BYTES} "
            f"but the contracts derive {max_bytes}"
        )
    if max_tokens != admission.CONTRACT_MAX_STRUCTURAL_TOKENS:
        failures.append(
            f"CONTRACT_MAX_STRUCTURAL_TOKENS={admission.CONTRACT_MAX_STRUCTURAL_TOKENS} "
            f"but the contracts derive {max_tokens}"
        )
    for line in failures:
        print(f"MISMATCH: {line}")
    print(f"EXTENT CHECK: failures={len(failures)}")
    return 1 if failures else 0


# --------------------------------------------------------------------------
# measured half


def legitimate_request() -> dict[str, Any]:
    """The accepted OBL-01 semantic fixture, as a mutable object."""
    entries = json.loads(FIXTURE.read_text(encoding="utf-8"))["entries"]
    for entry in entries:
        if entry["obligation_id"] == "OBL-01" and entry["expected_response"]["ok"]:
            return copy.deepcopy(entry["semantic_request"])
    raise SystemExit("no accepted OBL-01 fixture in the published pack")


def adversarial_shapes(base: dict[str, Any]):
    """Five builders, each taking a size parameter and returning a request."""

    def flat_facts(n: int) -> dict[str, Any]:
        request = copy.deepcopy(base)
        for i in range(n):
            request["decision_input"]["facts"]["z%09d" % i] = 1
        return request

    def decision_input_members(n: int) -> dict[str, Any]:
        request = copy.deepcopy(base)
        for i in range(n):
            request["decision_input"]["z%09d" % i] = 1
        return request

    def root_members(n: int) -> dict[str, Any]:
        request = copy.deepcopy(base)
        for i in range(n):
            request["z%09d" % i] = 1
        return request

    def nested(n: int) -> dict[str, Any]:
        request = copy.deepcopy(base)
        node: dict[str, Any] = {}
        cursor = node
        for _ in range(min(n, 120)):
            cursor["z"] = {}
            cursor = cursor["z"]
        request["decision_input"]["facts"]["deep"] = node
        for i in range(max(0, n - 120)):
            request["decision_input"]["facts"]["z%09d" % i] = 1
        return request

    def object_array(n: int) -> dict[str, Any]:
        request = copy.deepcopy(base)
        request["decision_input"]["facts"]["arr"] = [{"a": i} for i in range(n)]
        return request

    return {
        "flat_facts": flat_facts,
        "decision_input_members": decision_input_members,
        "root_members": root_members,
        "nested": nested,
        "object_array": object_array,
    }


def run_cost() -> int:
    import platform

    import receiver_reliance as rr

    b1 = sys.modules["receiver_reliance._rr_api"].b1

    def wire(request: dict[str, Any]) -> bytes:
        return b1.jcs_bytes(request) + b"\n"

    def milliseconds(raw: bytes, repetitions: int = 3) -> float:
        samples = []
        for _ in range(repetitions):
            gc.collect()
            gc.disable()
            start = time.perf_counter_ns()
            rr.decide_audited(raw)
            end = time.perf_counter_ns()
            gc.enable()
            samples.append((end - start) / 1e6)
        return statistics.median(samples)

    def fit(builder, target: int) -> bytes:
        low, high = 1, 300_000
        while low < high:
            middle = (low + high + 1) // 2
            try:
                fits = len(wire(builder(middle))) <= target
            except Exception:
                fits = False
            if fits:
                low = middle
            else:
                high = middle - 1
        return wire(builder(low))

    base = legitimate_request()
    legitimate = wire(base)
    baseline = milliseconds(legitimate, 9)
    print(
        f"host: {platform.python_implementation()} {platform.python_version()} "
        f"{platform.system()} {platform.release()} {platform.version()} {platform.machine()}"
    )
    print(
        f"legitimate OBL-01 fixture: {len(legitimate)} bytes, "
        f"{_tokens(legitimate)} structural tokens, {baseline:.3f} ms"
    )
    print()
    print(f"{'bound':>9}  {'worst shape':<23}{'bytes':>9}{'ms':>10}{'x legit':>10}")
    for bound in (4096, 8192, 16384, 32768, 262144):
        worst = (0.0, "", 0)
        for name, builder in adversarial_shapes(base).items():
            raw = fit(builder, bound)
            elapsed = milliseconds(raw)
            if elapsed > worst[0]:
                worst = (elapsed, name, len(raw))
        print(
            f"{bound:>9}  {worst[1]:<23}{worst[2]:>9}{worst[0]:>10.2f}"
            f"{worst[0] / baseline:>9.1f}x"
        )
    print()
    print("Worst of these five shapes, on this host. Not a proven maximum.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="derive or measure the admission numbers")
    parser.add_argument("--extent", action="store_true", help="derive the contract extent")
    parser.add_argument("--cost", action="store_true", help="measure admitted adversarial cost")
    parser.add_argument("--check", action="store_true", help="with --extent: fail on drift")
    args = parser.parse_args(argv)
    if not args.extent and not args.cost:
        parser.error("choose --extent or --cost")
    status = 0
    if args.extent:
        status |= run_extent(args.check)
    if args.cost:
        status |= run_cost()
    return status


if __name__ == "__main__":
    raise SystemExit(main())
