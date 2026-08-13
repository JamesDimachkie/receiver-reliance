"""Fail-closed verifier for a receiver-reliance portable bundle."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import unicodedata
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
MANIFEST = HERE / "MANIFEST.json"
ZERO64 = "0" * 64
HEX = frozenset("0123456789ABCDEF")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in HEX for c in value)


def _candidate(root: pathlib.Path, text: Any) -> pathlib.Path:
    if not isinstance(text, str) or not text:
        raise ValueError("manifest path must be a non-empty string")
    if text != unicodedata.normalize("NFC", text) or "\\" in text or ":" in text:
        raise ValueError(f"unsafe manifest path: {text!r}")
    pure = pathlib.PurePosixPath(text)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise ValueError(f"unsafe manifest path: {text!r}")
    unresolved = root.joinpath(*pure.parts)
    cursor = root
    for part in pure.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"manifest path crosses a symlink: {text}")
    resolved = unresolved.resolve(strict=True)
    if os.path.commonpath((str(root.resolve()), str(resolved))) != str(root.resolve()):
        raise ValueError(f"manifest path escapes repository: {text}")
    if not resolved.is_file():
        raise ValueError(f"manifest path is not a regular file: {text}")
    return resolved


def verify(root: pathlib.Path = ROOT, manifest_path: pathlib.Path = MANIFEST) -> tuple[int, list[str]]:
    failures: list[str] = []
    try:
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise ValueError("manifest must be a regular nonsymlink file")
        raw = manifest_path.read_bytes()
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("manifest exceeds 4 MiB")
        manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
        required = {
            "files",
            "format_version",
            "inventory_sha256",
            "manifest_sha256",
            "path_contract",
            "runtime_contract",
        }
        if not isinstance(manifest, dict) or set(manifest) != required:
            raise ValueError("manifest top-level members are not closed")
        if manifest["format_version"] != "RR-PORTABLE-BUNDLE-MANIFEST-1":
            raise ValueError("unsupported manifest format")
        if manifest["path_contract"] != "REPOSITORY_RELATIVE_POSIX_NFC_NONSYMLINK":
            raise ValueError("unsupported manifest path contract")
        if manifest["runtime_contract"] != {
            "implementation": "CPython",
            "python_versions": ["3.12", "3.13", "3.14"],
        }:
            raise ValueError("unsupported runtime contract")
        if not _sha(manifest["inventory_sha256"]) or not _sha(manifest["manifest_sha256"]):
            raise ValueError("manifest digests are malformed")
        sealed = dict(manifest)
        expected_seal = sealed["manifest_sha256"]
        sealed["manifest_sha256"] = ZERO64
        actual_seal = hashlib.sha256(_canonical(sealed)).hexdigest().upper()
        if expected_seal != actual_seal:
            raise ValueError("manifest self-seal mismatch")
        inventory_path = root / "portable" / "inventory.json"
        if inventory_path.is_symlink() or not inventory_path.is_file():
            raise ValueError("inventory must be a regular nonsymlink file")
        inventory_raw = inventory_path.read_bytes()
        if hashlib.sha256(inventory_raw).hexdigest().upper() != manifest["inventory_sha256"]:
            raise ValueError("inventory digest mismatch")
        rows = manifest["files"]
        if not isinstance(rows, list) or not rows:
            raise ValueError("manifest files must be a non-empty array")
        seen: set[str] = set()
        previous = ""
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"byte_length", "path", "role", "sha256"}:
                raise ValueError("manifest file row is not closed")
            text = row["path"]
            if not isinstance(text, str) or text in seen or text <= previous:
                raise ValueError("manifest paths are duplicate or not strictly sorted")
            seen.add(text)
            previous = text
            if not isinstance(row["role"], str) or not row["role"]:
                raise ValueError(f"manifest role is invalid: {text}")
            if not isinstance(row["byte_length"], int) or isinstance(row["byte_length"], bool) or row["byte_length"] < 0:
                raise ValueError(f"manifest byte length is invalid: {text}")
            if not _sha(row["sha256"]):
                raise ValueError(f"manifest file digest is invalid: {text}")
            path = _candidate(root, text)
            content = path.read_bytes()
            if len(content) != row["byte_length"]:
                failures.append(f"{text}:byte_length")
            if hashlib.sha256(content).hexdigest().upper() != row["sha256"]:
                failures.append(f"{text}:sha256")
        return len(rows), failures
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return 0, [f"manifest:{type(exc).__name__}:{exc}"]


def main() -> int:
    count, failures = verify()
    for failure in failures:
        print(f"FAIL {failure}")
    print(f"portable bundle: files={count} failures={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
