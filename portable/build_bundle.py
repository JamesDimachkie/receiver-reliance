"""Build a byte-deterministic, uncompressed portable ZIP from verified bytes."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import pathlib
import sys
import tempfile
import zipfile


HERE = pathlib.Path(__file__).resolve().parent
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def _load_verifier():
    spec = importlib.util.spec_from_file_location(
        "portable_build_bundle_verifier",
        HERE / "verify_bundle.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_verifier = _load_verifier()


def _file_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def build(output: pathlib.Path) -> str:
    _, snapshot, failures = _verifier.verify_snapshot()
    if failures or snapshot is None:
        raise ValueError("bundle verification failed: " + "; ".join(failures))
    contents = dict(snapshot.files)
    special = {
        "portable/MANIFEST.json": snapshot.manifest_raw,
        "portable/inventory.json": snapshot.inventory_raw,
    }
    for relative, raw in special.items():
        if relative in contents and contents[relative] != raw:
            raise ValueError(f"snapshot path collision: {relative}")
        contents[relative] = raw
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_STORED,
        strict_timestamps=True,
    ) as archive:
        for relative in sorted(contents):
            info = zipfile.ZipInfo(relative, FIXED_TIME)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, contents[relative])
    return _file_sha256(output)


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
            identical = first.stat().st_size == second.stat().st_size and first_sha == second_sha
            if identical:
                # Digest equality is necessary, never sufficient: retain the
                # exact byte comparison the check always made, streamed in
                # bounded chunks (no-weakening law).
                with first.open("rb") as fa, second.open("rb") as fb:
                    while identical:
                        ca = fa.read(1 << 20)
                        cb = fb.read(1 << 20)
                        if ca != cb:
                            identical = False
                        if not ca:
                            break
            if not identical:
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
