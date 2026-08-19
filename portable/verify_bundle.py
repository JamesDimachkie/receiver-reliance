"""Fail-closed verifier for a receiver-reliance portable bundle."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import stat
import sys
import unicodedata
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
MANIFEST = HERE / "MANIFEST.json"
ZERO64 = "0" * 64
HEX = frozenset("0123456789ABCDEF")
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_INVENTORY_BYTES = 1024 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_FILES = 4096


def _load_shared_law():
    """Load ADOPTION A4's one ingest law from the path the bundle declares.

    Path-bound for the same reason the gate binds this verifier by path: the
    law is always the declared file beside the bundle, never an ambient
    same-name module, and the load survives isolated-mode spawning that strips
    the script directory from sys.path.  The module is cached under a single
    name so the bundle executes one law, not one copy per importer.
    """
    name = "rr_strict_ingest"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "portability" / "strict_ingest.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


strict_ingest = _load_shared_law()

# Read from the shared law, never restated.  The lexical scan below and the
# law's own value-walk measure the same ceiling in two places, so a copied
# literal here is the C2 defect A4 exists to remove.
MAX_JSON_DEPTH = strict_ingest.MAX_NESTING
WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


@dataclass(frozen=True)
class BundleSnapshot:
    manifest: dict[str, Any]
    manifest_raw: bytes
    inventory_raw: bytes
    files: tuple[tuple[str, bytes], ...]


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in HEX for c in value)


def _portable_parts(text: Any, source: str) -> pathlib.PurePosixPath:
    if not isinstance(text, str) or not text:
        raise ValueError(f"{source} path must be a non-empty string")
    if text != unicodedata.normalize("NFC", text) or "\\" in text or ":" in text:
        raise ValueError(f"unsafe {source} path: {text!r}")
    pure = pathlib.PurePosixPath(text)
    if (
        pure.is_absolute()
        or pure.as_posix() != text
        or any(part in ("", ".", "..") for part in pure.parts)
    ):
        raise ValueError(f"unsafe {source} path: {text!r}")
    for part in pure.parts:
        if (
            re.fullmatch(r"[A-Za-z0-9._-]+", part) is None
            or
            part.endswith((" ", "."))
            or any(ord(character) < 0x20 or character in '<>"|?*' for character in part)
            or part.split(".", 1)[0].upper() in WINDOWS_RESERVED
        ):
            raise ValueError(f"nonportable {source} path: {text!r}")
    return pure


def _portable_alias(text: Any, source: str = "manifest") -> str:
    pure = _portable_parts(text, source)
    return "/".join(unicodedata.normalize("NFC", part).casefold() for part in pure.parts)


def _is_linklike(info: os.stat_result) -> bool:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & reparse
    )


def _candidate(root: pathlib.Path, text: Any) -> pathlib.Path:
    pure = _portable_parts(text, "manifest")
    root_resolved = root.resolve(strict=True)
    cursor = root_resolved
    for index, part in enumerate(pure.parts):
        cursor = cursor / part
        info = cursor.lstat()
        if _is_linklike(info):
            raise ValueError(f"manifest path crosses a link or reparse point: {text}")
        if index < len(pure.parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"manifest path ancestor is not a directory: {text}")
    resolved = cursor.resolve(strict=True)
    if os.path.commonpath((str(root_resolved), str(resolved))) != str(root_resolved):
        raise ValueError(f"manifest path escapes repository: {text}")
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise ValueError(f"manifest path is not a regular file: {text}")
    return resolved


def _file_identity(path: pathlib.Path) -> tuple[object, ...]:
    info = path.lstat()
    if _is_linklike(info) or not stat.S_ISREG(info.st_mode):
        raise ValueError(f"path is not a regular non-link file: {path.name}")
    if info.st_ino:
        return (info.st_dev, info.st_ino)
    return ("path", os.path.normcase(str(path.resolve(strict=True))))


def _read_regular(
    path: pathlib.Path,
    max_bytes: int,
    expected_length: int | None = None,
) -> bytes:
    before = path.lstat()
    if (
        _is_linklike(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_size < 0
        or before.st_size > max_bytes
        or (expected_length is not None and before.st_size != expected_length)
    ):
        raise ValueError(f"file is not a bounded regular file: {path.name}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_size != before.st_size
            or opened.st_dev != before.st_dev
            or (before.st_ino and opened.st_ino != before.st_ino)
        ):
            raise ValueError(f"file identity changed before read: {path.name}")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
        if after.st_size != opened.st_size or len(raw) != opened.st_size or len(raw) > max_bytes:
            raise ValueError(f"file changed during bounded read: {path.name}")
        return raw
    finally:
        os.close(descriptor)


def _json_depth_ok(text: str) -> bool:
    stack = bytearray()
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            if len(stack) >= MAX_JSON_DEPTH:
                return False
            stack.append(ord(character))
        elif character in "]}":
            expected = ord("[") if character == "]" else ord("{")
            if not stack or stack.pop() != expected:
                return False
    return not in_string and not escaped and not stack


def _decode_json(raw: bytes, source: str) -> Any:
    """Admit bundle JSON under the shared law, keeping this file's own preflight.

    ADOPTION A4: duplicate keys, non-finite constants, lone surrogates, strict
    UTF-8 and the frozen core's nesting/member ceilings are the shared law's
    (`strict_ingest.load_safe`), which is strictly stronger than the local hook
    it replaced.  The lexical scan stays in front of it because it is stronger
    in a dimension the law does not cover: it bounds depth and rejects
    structurally unbalanced text before the parser allocates anything, the same
    reason the matrix verifier kept its own preflight.  `IngestError` subclasses
    `ValueError`, so every caller's fail-closed contract is unchanged.
    """
    text = raw.decode("utf-8", errors="strict")
    if not _json_depth_ok(text):
        raise ValueError(f"{source} JSON exceeds depth or is structurally unbalanced")
    return strict_ingest.load_safe(raw, label=source)


def _inventory_declarations(inventory: Any) -> list[tuple[str, str]]:
    if not isinstance(inventory, dict) or set(inventory) != {"format_version", "files"}:
        raise ValueError("inventory must contain exactly format_version and files")
    if inventory["format_version"] != "RR-PORTABLE-INVENTORY-1":
        raise ValueError("unsupported inventory format")
    rows = inventory["files"]
    if not isinstance(rows, list) or not rows or len(rows) > MAX_FILES:
        raise ValueError("inventory files must be a bounded non-empty array")
    declarations: list[tuple[str, str]] = []
    seen_paths: set[str] = set()
    seen_aliases: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "role"}:
            raise ValueError("each inventory row must contain exactly path and role")
        text = row["path"]
        role = row["role"]
        alias = _portable_alias(text, "inventory")
        if text in {"portable/MANIFEST.json", "portable/inventory.json"}:
            raise ValueError(f"inventory cannot declare bootstrap path: {text}")
        if text in seen_paths or alias in seen_aliases:
            raise ValueError(f"duplicate or aliased inventory path: {text}")
        if not isinstance(role, str) or not role:
            raise ValueError("inventory role must be a non-empty string")
        seen_paths.add(text)
        seen_aliases.add(alias)
        declarations.append((text, role))
    return sorted(declarations)


def verify_snapshot(
    root: pathlib.Path = ROOT,
    manifest_path: pathlib.Path = MANIFEST,
) -> tuple[int, BundleSnapshot | None, list[str]]:
    failures: list[str] = []
    try:
        root_resolved = root.resolve(strict=True)
        manifest_relative = manifest_path.absolute().relative_to(root.absolute()).as_posix()
        manifest_candidate = _candidate(root_resolved, manifest_relative)
        raw = _read_regular(manifest_candidate, MAX_MANIFEST_BYTES)
        manifest = _decode_json(raw, "manifest")
        if raw != _canonical(manifest):
            raise ValueError("manifest bytes are not canonical")
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

        inventory_candidate = _candidate(root_resolved, "portable/inventory.json")
        inventory_raw = _read_regular(inventory_candidate, MAX_INVENTORY_BYTES)
        if hashlib.sha256(inventory_raw).hexdigest().upper() != manifest["inventory_sha256"]:
            raise ValueError("inventory digest mismatch")
        inventory = _decode_json(inventory_raw, "inventory")
        inventory_declarations = _inventory_declarations(inventory)

        rows = manifest["files"]
        if not isinstance(rows, list) or not rows or len(rows) > MAX_FILES:
            raise ValueError("manifest files must be a bounded non-empty array")
        seen_paths: set[str] = set()
        seen_aliases: set[str] = set()
        previous = ""
        manifest_declarations: list[tuple[str, str]] = []
        total_bytes = 0
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"byte_length", "path", "role", "sha256"}:
                raise ValueError("manifest file row is not closed")
            text = row["path"]
            alias = _portable_alias(text)
            if not isinstance(text, str) or text in seen_paths or alias in seen_aliases or text <= previous:
                raise ValueError("manifest paths are aliased, duplicate, or not strictly sorted")
            seen_paths.add(text)
            seen_aliases.add(alias)
            previous = text
            if not isinstance(row["role"], str) or not row["role"]:
                raise ValueError(f"manifest role is invalid: {text}")
            length = row["byte_length"]
            if (
                not isinstance(length, int)
                or isinstance(length, bool)
                or length < 0
                or length > MAX_FILE_BYTES
            ):
                raise ValueError(f"manifest byte length is invalid: {text}")
            total_bytes += length
            if total_bytes > MAX_TOTAL_BYTES:
                raise ValueError("manifest total byte length exceeds bundle limit")
            if not _sha(row["sha256"]):
                raise ValueError(f"manifest file digest is invalid: {text}")
            manifest_declarations.append((text, row["role"]))
        if manifest_declarations != inventory_declarations:
            raise ValueError("manifest file declarations do not match inventory")

        snapshot_files: list[tuple[str, bytes]] = []
        seen_identities: set[tuple[object, ...]] = set()
        for row in rows:
            text = row["path"]
            path = _candidate(root_resolved, text)
            identity = _file_identity(path)
            if identity in seen_identities:
                raise ValueError(f"manifest paths resolve to one file identity: {text}")
            seen_identities.add(identity)
            content = _read_regular(path, MAX_FILE_BYTES, row["byte_length"])
            if hashlib.sha256(content).hexdigest().upper() != row["sha256"]:
                failures.append(f"{text}:sha256")
            snapshot_files.append((text, content))
        if failures:
            return len(rows), None, failures
        snapshot = BundleSnapshot(
            manifest=manifest,
            manifest_raw=raw,
            inventory_raw=inventory_raw,
            files=tuple(snapshot_files),
        )
        return len(rows), snapshot, []
    except (MemoryError, OSError, RecursionError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return 0, None, [f"manifest:{type(exc).__name__}:{exc}"]


def verify(root: pathlib.Path = ROOT, manifest_path: pathlib.Path = MANIFEST) -> tuple[int, list[str]]:
    count, _, failures = verify_snapshot(root, manifest_path)
    return count, failures


def main() -> int:
    count, failures = verify()
    for failure in failures:
        print(f"FAIL {failure}")
    print(f"portable bundle: files={count} failures={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
