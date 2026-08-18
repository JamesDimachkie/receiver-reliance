"""receiver_reliance — library API over the frozen engine + grounded 0.4 layer.

Supported layouts: an editable install from a repo checkout (`pip install
-e .`), any sys.path arrangement where this package sits beside
`grounded-0_4/` and `baseline-run/`, or a self-contained distribution that
carries those engine files under `receiver_reliance/_engine/`. Whichever
layout is found, import verifies every engine file against
`engine_manifest.json` by byte length and SHA-256 before executing any of
them, and refuses to import on drift -- so an installed copy proves it holds
the bytes the repository publishes rather than asserting it. Regenerate or
verify that manifest with `python -B
receiver_reliance/generate_engine_manifest.py [--check]`.

The heavy lifting lives in `grounded-0_4/rr_api.py`; this package is the
stable import surface:

    from receiver_reliance import decide_audited

`decide_audited(request)` is the ONE supported evidentiary decision API: it
returns the grounded audited decision (input-bound seal, governing-policy
digests, witness trace, closure findings, truncation-disclosed record
references). There is no supported bare-decision route: the former
top-level `decide` export returned sealed responses that bind no decision
facts (ERRATA E2) and bypass the 0.4 closures (E5), so it was withdrawn
from the supported surface (deep-scan findings csf_abbd6848 /
csf_0479d1a9, 2026-08-16). Frozen-engine execution for conformance
reproduction lives in `receiver_reliance.conformance` under an explicitly
non-evidentiary name. See TRUST_MODEL.md for what each seal proves and
HOST_OBLIGATIONS.md H5 for the host's transcript duty.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
_ENGINE_ENTRY = "grounded-0_4/rr_api.py"


def _engine_root() -> pathlib.Path:
    """The directory the engine files are relative to, in either layout."""
    for candidate in (_HERE.parent, _HERE / "_engine"):
        if candidate.joinpath(*_ENGINE_ENTRY.split("/")).is_file():
            return candidate
    raise ImportError(
        "receiver_reliance cannot locate its engine: expected "
        f"{_ENGINE_ENTRY} either beside the package (repo checkout, looked at "
        f"{_HERE.parent}) or bundled at {_HERE / '_engine'}"
    )


def _verify_engine(root: pathlib.Path) -> dict:
    """Refuse to import an engine whose bytes are not the published ones.

    The package is the surface a third party uses, so a partial checkout or a
    distribution built from the wrong tree has to fail here rather than produce
    decisions from unknown code.
    """
    manifest_path = _HERE / "engine_manifest.json"
    if not manifest_path.is_file():
        raise ImportError(f"receiver_reliance engine manifest absent: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("files")
    if not isinstance(records, list) or len(records) != manifest.get("file_count"):
        raise ImportError("receiver_reliance engine manifest is malformed")
    for record in records:
        path = root.joinpath(*record["path"].split("/"))
        if not path.is_file():
            raise ImportError(
                f"receiver_reliance engine file absent: {record['path']} (looked at {path})"
            )
        raw = path.read_bytes()
        if len(raw) != record["byte_length"] or hashlib.sha256(raw).hexdigest().upper() != record["sha256"]:
            raise ImportError(
                "receiver_reliance engine drift: "
                f"{record['path']} does not match engine_manifest.json "
                f"(expected {record['byte_length']} bytes / {record['sha256']}, "
                f"found {len(raw)} bytes / {hashlib.sha256(raw).hexdigest().upper()})"
            )
    return manifest


_REPO = _engine_root()
ENGINE_MANIFEST = _verify_engine(_REPO)
_RR_API = _REPO.joinpath(*_ENGINE_ENTRY.split("/"))
_spec = importlib.util.spec_from_file_location("receiver_reliance._rr_api", _RR_API)
_module = importlib.util.module_from_spec(_spec)
sys.modules["receiver_reliance._rr_api"] = _module
_spec.loader.exec_module(_module)

decide_audited = _module.decide_audited
closure_findings = _module.closure_findings
derive_record_references = _module.derive_record_references
AUDIT_FORMAT = _module.AUDIT_FORMAT

ENGINE_MANIFEST_SHA256 = ENGINE_MANIFEST["manifest_sha256"]

__all__ = [
    "decide_audited",
    "closure_findings",
    "derive_record_references",
    "AUDIT_FORMAT",
    "ENGINE_MANIFEST_SHA256",
]
__version__ = "1.2.0.dev0"
