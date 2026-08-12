"""Verify the WP1 snapshots and E7 subset row-by-row from pinned parent data."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from typing import Any

try:
    from .preflight import canonical_json_bytes, sha256_upper
except ImportError:
    from preflight import canonical_json_bytes, sha256_upper  # type: ignore

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
PARENT_CORPUS = FIXTURES / "parent_corpus_408.jsonl"
PARENT_TRUTH = FIXTURES / "parent_truth_408.jsonl"
E7_CORPUS = FIXTURES / "e7_lifecycle_corpus.jsonl"
E7_TRUTH = FIXTURES / "e7_lifecycle_truth.jsonl"

PINS = {
    "parent_corpus_raw_sha256": "09B4B05FE26CF46F063EC637C1A4D27B4D5190961756888099F96254C49B334E",
    "parent_truth_raw_sha256": "4FEEF9BE65DD7523849CEE71B5A43EA6F7667710745E71D79C0EE5B054E3E2C7",
    "e7_corpus_raw_sha256": "2F4AB230A1B66852C3D95F21648F0D549261268FE41992C98CC53C6F6811FC8F",
    "e7_truth_raw_sha256": "6790C2268BB95B1559C06A3CBFFE1CF4BF9843C7D3284058EA848C8CE0D73366",
}


def _raw_sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _lines(path: pathlib.Path) -> list[bytes]:
    raw = path.read_bytes()
    if not raw.endswith(b"\n") or b"\r\n" in raw:
        raise RuntimeError(f"fixture is not LF-terminated canonical JSONL: {path}")
    lines = raw.splitlines()
    for number, line in enumerate(lines, 1):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeError(f"row {number} is not a JSON object: {path}")
    return lines


def verify() -> dict[str, Any]:
    paths = {
        "parent_corpus_raw_sha256": PARENT_CORPUS,
        "parent_truth_raw_sha256": PARENT_TRUTH,
        "e7_corpus_raw_sha256": E7_CORPUS,
        "e7_truth_raw_sha256": E7_TRUTH,
    }
    for key, path in paths.items():
        actual = _raw_sha(path)
        if actual != PINS[key]:
            raise RuntimeError(f"raw SHA mismatch for {path}: {actual} != {PINS[key]}")

    corpus_lines = _lines(PARENT_CORPUS)
    truth_lines = _lines(PARENT_TRUTH)
    if len(corpus_lines) != 408 or len(truth_lines) != 408:
        raise RuntimeError("pinned parent snapshots are not 408 rows each")
    corpus = [json.loads(line) for line in corpus_lines]
    truth = [json.loads(line) for line in truth_lines]
    truth_by_id = {row["record_id"]: (row, line) for row, line in zip(truth, truth_lines)}
    if len(truth_by_id) != 408 or {row["record_id"] for row in corpus} != set(truth_by_id):
        raise RuntimeError("parent corpus/truth record identity mismatch")

    expected_e7_corpus = [
        line for row, line in zip(corpus, corpus_lines) if row["family"] == "LIFECYCLE"
    ]
    expected_e7_ids = [
        row["record_id"] for row in corpus if row["family"] == "LIFECYCLE"
    ]
    expected_e7_truth = [truth_by_id[record_id][1] for record_id in expected_e7_ids]
    if _lines(E7_CORPUS) != expected_e7_corpus:
        raise RuntimeError("E7 corpus is not the exact row-ordered LIFECYCLE parent subset")
    if _lines(E7_TRUTH) != expected_e7_truth:
        raise RuntimeError("E7 truth is not the exact parent truth join in corpus row order")

    bindings = []
    for index, (row, raw_line) in enumerate(zip(corpus, corpus_lines)):
        truth_row, truth_raw = truth_by_id[row["record_id"]]
        bindings.append(
            {
                "index": index,
                "record_id": row["record_id"],
                "family": row["family"],
                "corpus_row_sha256": sha256_upper(raw_line),
                "truth_row_sha256": sha256_upper(truth_raw),
                "defective": truth_row["defective"],
            }
        )
    return {
        "parent_rows": len(corpus),
        "e7_rows": len(expected_e7_corpus),
        "row_bindings_sha256": sha256_upper(
            json.dumps(bindings, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ),
        "pins": dict(PINS),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", required=True)
    parser.parse_args()
    result = verify()
    print(
        f"fixture provenance: {result['parent_rows']} parent rows, "
        f"{result['e7_rows']} E7 rows, bindings {result['row_bindings_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
