"""Deterministically derive the portable bundle manifest from its inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import unicodedata
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
INVENTORY = HERE / "inventory.json"
MANIFEST = HERE / "MANIFEST.json"
ZERO64 = "0" * 64


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def _load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _safe_path(text: Any) -> pathlib.Path:
    if not isinstance(text, str) or not text:
        raise ValueError("inventory path must be a non-empty string")
    if text != unicodedata.normalize("NFC", text) or "\\" in text or ":" in text:
        raise ValueError(f"unsafe inventory path: {text!r}")
    pure = pathlib.PurePosixPath(text)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise ValueError(f"unsafe inventory path: {text!r}")
    return ROOT.joinpath(*pure.parts)


def build() -> dict[str, Any]:
    inventory_raw = INVENTORY.read_bytes()
    inventory = json.loads(inventory_raw.decode("utf-8"), object_pairs_hook=_pairs)
    if not isinstance(inventory, dict) or set(inventory) != {"format_version", "files"}:
        raise ValueError("inventory must contain exactly format_version and files")
    if inventory["format_version"] != "RR-PORTABLE-INVENTORY-1":
        raise ValueError("unsupported inventory format")
    rows = inventory["files"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("inventory files must be a non-empty array")
    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "role"}:
            raise ValueError("each inventory row must contain exactly path and role")
        path_text = row["path"]
        role = row["role"]
        if not isinstance(role, str) or not role:
            raise ValueError("inventory role must be a non-empty string")
        path = _safe_path(path_text)
        if path_text in seen:
            raise ValueError(f"duplicate inventory path: {path_text}")
        seen.add(path_text)
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"inventory path is not a regular nonsymlink file: {path_text}")
        raw = path.read_bytes()
        files.append(
            {
                "byte_length": len(raw),
                "path": path_text,
                "role": role,
                "sha256": hashlib.sha256(raw).hexdigest().upper(),
            }
        )
    files.sort(key=lambda item: item["path"])
    manifest: dict[str, Any] = {
        "files": files,
        "format_version": "RR-PORTABLE-BUNDLE-MANIFEST-1",
        "inventory_sha256": hashlib.sha256(inventory_raw).hexdigest().upper(),
        "manifest_sha256": ZERO64,
        "path_contract": "REPOSITORY_RELATIVE_POSIX_NFC_NONSYMLINK",
        "runtime_contract": {
            "implementation": "CPython",
            "python_versions": ["3.12", "3.13", "3.14"],
        },
    }
    manifest["manifest_sha256"] = hashlib.sha256(canonical_bytes(manifest)).hexdigest().upper()
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = canonical_bytes(build())
    if args.check:
        actual = MANIFEST.read_bytes() if MANIFEST.exists() else b""
        if actual != expected:
            print("portable manifest: drift")
            return 1
        print(f"portable manifest: files={len(build()['files'])} drift=0")
        return 0
    MANIFEST.write_bytes(expected)
    print(f"portable manifest: wrote files={len(build()['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
