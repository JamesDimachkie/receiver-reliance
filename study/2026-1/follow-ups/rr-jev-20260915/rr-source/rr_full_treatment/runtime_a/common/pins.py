"""Accepted-dependency pin verification.

``accepted_dependencies.accepted_source_files`` of the frozen semantic authority pins the five
accepted source files by exact byte length and SHA-256, and the claim's stop condition is
"identity/pin mismatch stops the implementation".  This module carries those five rows as authority
constants -- the same status as ``s.COMPONENT_POLICY_SHA256``, and not a registry oracle -- and
verifies them from disk.

An arm calls :func:`verify` at import time, before it imports its accepted dependency, so a
mismatch stops the implementation by refusing the import.  Verification never runs inside
``decide``: the seam must not touch the filesystem (``candidate_runtime_forbidden``).

``conform.py`` re-reads ``accepted_dependencies`` from the authority text and checks that the table
below is byte-identical to it, so the embedded constants cannot drift from the frozen authority.
"""

from __future__ import annotations

import hashlib
import pathlib

from .wire import cj6, frame

# accepted_dependencies.accepted_source_files, verbatim and in the authority's listed order.
ACCEPTED_SOURCE_FILES: tuple[dict[str, object], ...] = (
    {
        "byte_length": 19819,
        "path": "receiver_reliance/__init__.py",
        "sha256": "635804FA4767D69FC6466736423AA68697B95FF37C618074B17DB54F8830C2EE",
    },
    {
        "byte_length": 2326,
        "path": "receiver_reliance/engine_manifest.json",
        "sha256": "336775BACF9AFB944418DDB9B10B3B07D93A2B96B557263A4FFD26BD84C77585",
    },
    {
        "byte_length": 337,
        "path": "rr_s_all_kernel/__init__.py",
        "sha256": "052E4896C1DE0B49535DB942939E88AA8EFB4B78A088792FDAF96FF026BCEAF3",
    },
    {
        "byte_length": 14416,
        "path": "rr_full_treatment/static_kernel.py",
        "sha256": "3A71AE69E98E2247197D0505E28AD3719BC9061E6F0F33B1FC19A150159B11D0",
    },
    {
        "byte_length": 6314,
        "path": "rr_s_all_qualification/import_graph.py",
        "sha256": "BFFBF2942789C223B987A070A7E398D98E81D6703180DC992415D89F7D0724DB",
    },
)

# accepted_dependencies.accepted_source_files_root and its declared law.
ACCEPTED_SOURCE_FILES_ROOT = "0B80DFB9310BB6B5F3129D1917D6B0C8B4BC1173A9AB620707DE087E0A3DC3BA"
ACCEPTED_SOURCE_FILES_ROOT_DOMAIN = "RR-TRT3/ACCEPTED-SOURCE-PINS/1"

# The accepted source files the arms actually import.
KERNEL_PINS = ("rr_s_all_kernel/__init__.py", "rr_full_treatment/static_kernel.py")
RECEIVER_PINS = ("receiver_reliance/__init__.py", "receiver_reliance/engine_manifest.json")

_BY_PATH = {str(row["path"]): row for row in ACCEPTED_SOURCE_FILES}
_TREE_ROOT = pathlib.Path(__file__).resolve().parents[3]


class AcceptedDependencyPinError(Exception):
    """An accepted source file does not match its authority pin."""


def accepted_source_files_root() -> str:
    """Recompute accepted_source_files_root from the embedded rows under the declared law."""
    digest = hashlib.sha256()
    digest.update(ACCEPTED_SOURCE_FILES_ROOT_DOMAIN.encode("ascii"))
    digest.update(b"\0")
    for row in ACCEPTED_SOURCE_FILES:
        digest.update(frame(cj6(row)))
    return digest.hexdigest().upper()


if accepted_source_files_root() != ACCEPTED_SOURCE_FILES_ROOT:
    raise AcceptedDependencyPinError(
        "embedded accepted_source_files table does not reproduce accepted_source_files_root"
    )


def verify(paths: tuple[str, ...]) -> None:
    """Verify each named accepted source file against its authority pin, or refuse."""
    for path in paths:
        row = _BY_PATH.get(path)
        if row is None:
            raise AcceptedDependencyPinError("no authority pin for " + path)
        target = _TREE_ROOT.joinpath(*path.split("/"))
        try:
            raw = target.read_bytes()
        except OSError as exc:
            raise AcceptedDependencyPinError("accepted source file unreadable: " + path) from exc
        if len(raw) != row["byte_length"]:
            raise AcceptedDependencyPinError(
                "accepted source pin byte_length mismatch for %s: pinned %d, found %d"
                % (path, row["byte_length"], len(raw))
            )
        found = hashlib.sha256(raw).hexdigest().upper()
        if found != row["sha256"]:
            raise AcceptedDependencyPinError(
                "accepted source pin sha256 mismatch for %s: pinned %s, found %s"
                % (path, row["sha256"], found)
            )


__all__ = (
    "ACCEPTED_SOURCE_FILES",
    "ACCEPTED_SOURCE_FILES_ROOT",
    "AcceptedDependencyPinError",
    "KERNEL_PINS",
    "RECEIVER_PINS",
    "accepted_source_files_root",
    "verify",
)
