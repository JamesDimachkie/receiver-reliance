"""Accepted-dependency pin verification.

``accepted_dependencies`` binds five accepted source files and eleven
engine-manifest rows by exact byte length and SHA-256.  This module proves those
pins against the worktree *before* an arm imports the dependency they describe,
and refuses on any mismatch.

Where this runs, and why not inside ``decide``
----------------------------------------------
``architecture.candidate_runtime_forbidden`` forbids the candidate runtime from
touching the filesystem.  ``verify_at_import`` therefore runs exactly once, at
module-import time of the arm that carries an accepted dependency, strictly
before that dependency is imported, and it records what it proved.  Every later
``decide`` call runs ``assert_verified`` instead, which re-asserts the recorded
proof and the identity of the module objects that were verified, and reaches no
file.  See the determinability note in the implementation report.

``a2schema`` embeds the accepted A2 projection schema so that a decide call needs
no file at all; ``verify_at_import`` additionally proves the embedded bytes equal
the accepted file on disk.
"""

import hashlib
import json
import os

from . import a2_schema_data
from . import a2schema
from . import authority_data

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class PinMismatch(Exception):
    """An accepted dependency does not match its authority pin."""


class _Record:
    __slots__ = ("verified", "rows", "modules")

    def __init__(self):
        self.verified = False
        self.rows = ()
        self.modules = {}


_STATE = _Record()


def _read(relative):
    path = os.path.join(ROOT, *relative.split("/"))
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError as error:
        raise PinMismatch("accepted file is unreadable: " + relative) from error


def _check_rows(rows, label):
    proved = []
    for row in rows:
        raw = _read(row["path"])
        if len(raw) != row["byte_length"]:
            raise PinMismatch(
                label + " byte length differs: " + row["path"]
            )
        digest = hashlib.sha256(raw).hexdigest().upper()
        if digest != row["sha256"]:
            raise PinMismatch(label + " SHA-256 differs: " + row["path"])
        proved.append((row["path"], row["byte_length"], digest))
    return proved


def verify_at_import():
    """Prove every accepted pin against the worktree.  Idempotent."""
    if _STATE.verified:
        return _STATE.rows

    proved = _check_rows(authority_data.ACCEPTED_SOURCE_FILES, "accepted source file")
    proved += _check_rows(
        authority_data.ENGINE_MANIFEST_EXACT_ROWS, "engine manifest row"
    )

    # The engine manifest must declare the pinned digest and the identical rows.
    manifest = json.loads(
        _read("receiver_reliance/engine_manifest.json").decode("utf-8")
    )
    if manifest.get("manifest_sha256") != authority_data.ENGINE_MANIFEST_DECLARED_SHA256:
        raise PinMismatch("engine manifest declares an unpinned digest")
    declared = {
        (row["path"], row["byte_length"], row["sha256"]) for row in manifest["files"]
    }
    expected = {
        (row["path"], row["byte_length"], row["sha256"])
        for row in authority_data.ENGINE_MANIFEST_EXACT_ROWS
    }
    if declared != expected:
        raise PinMismatch("engine manifest rows differ from the authority rows")

    # The embedded A2 schema must be the accepted file, byte for byte.
    if a2schema.SCHEMA_BYTES != _read(a2_schema_data.A2_SCHEMA_PATH):
        raise PinMismatch("embedded A2 schema differs from the accepted file")

    _STATE.rows = tuple(proved)
    _STATE.verified = True
    return _STATE.rows


def bind_module(name, module, expected_relative_path):
    """Record that ``module`` is the verified file, and prove it now."""
    verify_at_import()
    actual = getattr(module, "__file__", None)
    if actual is None:
        raise PinMismatch("accepted module has no file identity: " + name)
    expected = os.path.join(ROOT, *expected_relative_path.split("/"))
    if os.path.normcase(os.path.abspath(actual)) != os.path.normcase(expected):
        raise PinMismatch("accepted module was imported from an unpinned path: " + name)
    _STATE.modules[name] = module


def assert_verified(*names):
    """Re-assert the recorded proof at use time.  Reaches no file."""
    if not _STATE.verified:
        raise PinMismatch("accepted dependency pins were never verified")
    if len(_STATE.rows) != len(authority_data.ACCEPTED_SOURCE_FILES) + len(
        authority_data.ENGINE_MANIFEST_EXACT_ROWS
    ):
        raise PinMismatch("the recorded pin proof is incomplete")
    for name in names:
        if name not in _STATE.modules:
            raise PinMismatch("accepted dependency was never bound: " + name)


def proof_rows():
    """The (path, byte_length, sha256) triples proved at import."""
    return _STATE.rows
