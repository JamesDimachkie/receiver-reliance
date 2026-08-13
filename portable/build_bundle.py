"""Build a byte-deterministic, uncompressed portable ZIP from MANIFEST.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import tempfile
import zipfile
from typing import Any

from verify_bundle import MANIFEST, ROOT, _pairs, verify


FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"), object_pairs_hook=_pairs)


def build(output: pathlib.Path) -> str:
    _, failures = verify()
    if failures:
        raise ValueError("bundle verification failed: " + "; ".join(failures))
    manifest = _load_manifest()
    paths = [row["path"] for row in manifest["files"]]
    paths.append("portable/MANIFEST.json")
    paths = sorted(set(paths))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, strict_timestamps=True) as archive:
        for relative in paths:
            raw = ROOT.joinpath(*pathlib.PurePosixPath(relative).parts).read_bytes()
            info = zipfile.ZipInfo(relative, FIXED_TIME)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    return hashlib.sha256(output.read_bytes()).hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--check-deterministic", action="store_true")
    args = parser.parse_args()
    if not args.output and not args.check_deterministic:
        parser.error("provide --output or --check-deterministic")
    if args.check_deterministic:
        with tempfile.TemporaryDirectory(prefix="rr-portable-") as temp:
            first = pathlib.Path(temp) / "one.zip"
            second = pathlib.Path(temp) / "two.zip"
            first_sha = build(first)
            second_sha = build(second)
            if first.read_bytes() != second.read_bytes() or first_sha != second_sha:
                print("portable archive: deterministic=0")
                return 1
            print(f"portable archive: deterministic=1 sha256={first_sha}")
        if not args.output:
            return 0
    assert args.output is not None
    digest = build(args.output)
    print(f"portable archive: path={args.output} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
