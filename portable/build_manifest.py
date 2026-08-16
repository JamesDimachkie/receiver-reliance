"""Deterministically derive the portable bundle manifest from its inventory."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import pathlib
import sys
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
INVENTORY = HERE / "inventory.json"
MANIFEST = HERE / "MANIFEST.json"
ZERO64 = "0" * 64


def _load_verifier():
    spec = importlib.util.spec_from_file_location(
        "portable_build_manifest_verifier",
        HERE / "verify_bundle.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_verifier = _load_verifier()
canonical_bytes = _verifier._canonical


def build() -> dict[str, Any]:
    inventory_path = _verifier._candidate(ROOT, "portable/inventory.json")
    inventory_raw = _verifier._read_regular(
        inventory_path,
        _verifier.MAX_INVENTORY_BYTES,
    )
    inventory = _verifier._decode_json(inventory_raw, "inventory")
    declarations = _verifier._inventory_declarations(inventory)
    files: list[dict[str, Any]] = []
    seen_identities: set[tuple[object, ...]] = set()
    total_bytes = 0
    for path_text, role in declarations:
        path = _verifier._candidate(ROOT, path_text)
        identity = _verifier._file_identity(path)
        if identity in seen_identities:
            raise ValueError(f"inventory paths resolve to one file identity: {path_text}")
        seen_identities.add(identity)
        raw = _verifier._read_regular(path, _verifier.MAX_FILE_BYTES)
        total_bytes += len(raw)
        if total_bytes > _verifier.MAX_TOTAL_BYTES:
            raise ValueError("inventory total byte length exceeds bundle limit")
        files.append(
            {
                "byte_length": len(raw),
                "path": path_text,
                "role": role,
                "sha256": hashlib.sha256(raw).hexdigest().upper(),
            }
        )
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
    manifest = build()
    expected = canonical_bytes(manifest)
    if args.check:
        try:
            actual_path = _verifier._candidate(ROOT, "portable/MANIFEST.json")
            actual = _verifier._read_regular(
                actual_path,
                _verifier.MAX_MANIFEST_BYTES,
            )
        except (OSError, ValueError):
            actual = b""
        if actual != expected:
            print("portable manifest: drift")
            return 1
        print(f"portable manifest: files={len(manifest['files'])} drift=0")
        return 0
    MANIFEST.write_bytes(expected)
    print(f"portable manifest: wrote files={len(manifest['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
