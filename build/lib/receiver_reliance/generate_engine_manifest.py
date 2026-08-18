"""Generate and check the engine manifest the package verifies at import.

The package's decision surface is a thin wrapper over engine files that live in
the repository, not in the package directory. That is deliberate: the repository
is the single authority, and several of those files are frozen release bytes
pinned by other verification surfaces. But it leaves the wrapper trusting
whatever happens to sit beside it, so an incomplete checkout, a partially applied
patch, or a distribution assembled from the wrong tree imports without complaint.

This writes `engine_manifest.json`: the exact byte length and SHA-256 of every
file the runtime import path reads, sealed with the same self-zero digest idiom
the rest of the repository uses. `receiver_reliance/__init__.py` verifies it on
import, so an installed copy proves it holds the same bytes the repository
publishes rather than merely claiming to.

    python -B receiver_reliance/generate_engine_manifest.py            # write
    python -B receiver_reliance/generate_engine_manifest.py --check    # verify

`--check` exits 1 if the regenerated manifest differs from the committed one, so
CI and the documented re-verification list catch an unrecorded engine change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
MANIFEST_PATH = HERE / "engine_manifest.json"
FORMAT_VERSION = "RR-ENGINE-MANIFEST-1"
ZERO64 = "0" * 64

# Every file the runtime import path reads, relative to the repository root.
#
# This list was DERIVED, not written: an audit hook recorded every path opened
# under the repository root while importing the package and calling
# decide_audited once. A hand-written list built from reading the import
# statements missed four of these, including two large control documents
# b1_capabilities.authority_documents() reads and the composed capability
# matrix, so the manifest it produced verified 302 KB of an engine that is
# really 1.18 MB. test_engine_manifest.py re-derives the closure the same way
# and fails if this tuple drifts from it.
#
# __pycache__ entries are deliberately absent: they are interpreter artifacts
# whose presence depends on -B, not engine bytes.
ENGINE_FILES = (
    "access/A2_SHARED_DOMAIN_VOCABULARY_BASELINE_PROJECTION_0_1.schema.json",
    "access/SANITIZED_PRIMARY_BASELINE_IMPLEMENTER_PACKET_0_1.json",
    "baseline-run/control/B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json",
    "baseline-run/implementation-output-0.3/b1_capabilities.py",
    "baseline-run/implementation-output-0.3/pcb_runner.py",
    "grounded-0_4/authority_register_0_4.json",
    "grounded-0_4/authority_surface.py",
    "grounded-0_4/closures_0_4.json",
    "grounded-0_4/rr_api.py",
    "supplemental-0_3/control/B1_COMPOSED_CAPABILITY_MATRIX_0_3.json",
    "supplemental-0_3/control/B1_SUPPLEMENTAL_COMPARATOR_CONTRACT_0_3.json",
)


def jcs(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def self_zero(value: dict, field: str) -> str:
    probe = json.loads(json.dumps(value))
    probe[field] = ZERO64
    return sha256_hex(jcs(probe))


def build(root: pathlib.Path) -> dict:
    files = []
    for relative in ENGINE_FILES:
        path = root.joinpath(*relative.split("/"))
        if not path.is_file():
            raise SystemExit(f"engine file absent: {relative}")
        raw = path.read_bytes()
        files.append(
            {"path": relative, "byte_length": len(raw), "sha256": sha256_hex(raw)}
        )
    manifest = {
        "format_version": FORMAT_VERSION,
        "file_count": len(files),
        "files": files,
        "total_byte_length": sum(item["byte_length"] for item in files),
        "manifest_sha256": ZERO64,
    }
    manifest["manifest_sha256"] = self_zero(manifest, "manifest_sha256")
    return manifest


STAGE_ROOT = HERE / "_engine"


def stage(manifest: dict, root: pathlib.Path) -> int:
    """Copy the engine into the package for a self-contained distribution.

    The repository remains the authority. This produces a derived copy whose only
    claim is that it matches the manifest, which the import-time check enforces
    wherever the copy ends up. Each file is verified after writing, so a staging
    run that silently truncated something fails here rather than shipping.
    """
    written = 0
    for record in manifest["files"]:
        source = REPO.joinpath(*record["path"].split("/"))
        target = STAGE_ROOT.joinpath(*record["path"].split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = source.read_bytes()
        target.write_bytes(raw)
        check = target.read_bytes()
        if len(check) != record["byte_length"] or sha256_hex(check) != record["sha256"]:
            raise SystemExit(f"staged copy does not match the manifest: {record['path']}")
        written += 1
    print(
        "staged %d engine files into %s (%d bytes); the manifest governs both copies"
        % (written, STAGE_ROOT.relative_to(REPO).as_posix(), manifest["total_byte_length"])
    )
    return 0


def verify_stage(manifest: dict) -> int:
    if not STAGE_ROOT.is_dir():
        print(f"no staged engine at {STAGE_ROOT}; run --stage before building a distribution")
        return 1
    expected = {record["path"] for record in manifest["files"]}
    found = {
        path.relative_to(STAGE_ROOT).as_posix()
        for path in STAGE_ROOT.rglob("*")
        if path.is_file()
    }
    if found != expected:
        print("staged tree census mismatch")
        print("  missing:", sorted(expected - found) or "none")
        print("  extra:  ", sorted(found - expected) or "none")
        return 1
    for record in manifest["files"]:
        raw = STAGE_ROOT.joinpath(*record["path"].split("/")).read_bytes()
        if len(raw) != record["byte_length"] or sha256_hex(raw) != record["sha256"]:
            print(f"staged engine drift: {record['path']}")
            return 1
    print("staged engine matches the manifest: %d files, %d bytes" % (manifest["file_count"], manifest["total_byte_length"]))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed manifest matches the engine bytes; do not write",
    )
    parser.add_argument(
        "--stage",
        action="store_true",
        help="copy the engine into receiver_reliance/_engine/ for a self-contained build",
    )
    parser.add_argument(
        "--verify-stage",
        action="store_true",
        help="verify an already-staged receiver_reliance/_engine/ against the manifest",
    )
    args = parser.parse_args(argv)
    manifest = build(REPO)
    rendered = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    if args.stage:
        return stage(manifest, REPO)
    if args.verify_stage:
        return verify_stage(manifest)

    if args.check:
        if not MANIFEST_PATH.is_file():
            print("engine manifest absent; run without --check to write it")
            return 1
        committed = MANIFEST_PATH.read_text(encoding="utf-8")
        if committed != rendered:
            print("engine manifest drift: regenerated bytes differ from the committed manifest")
            return 1
        print(
            "engine manifest: exact generated bytes; %d files, %d bytes, manifest_sha256=%s"
            % (manifest["file_count"], manifest["total_byte_length"], manifest["manifest_sha256"])
        )
        return 0

    MANIFEST_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    print(
        "wrote %s: %d files, %d bytes, manifest_sha256=%s"
        % (
            MANIFEST_PATH.name,
            manifest["file_count"],
            manifest["total_byte_length"],
            manifest["manifest_sha256"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
