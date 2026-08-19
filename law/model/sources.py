"""Pinned, digest-recorded loading of the sealed contract bytes.

Every artifact this model reasons about is read once, hashed with SHA-256, and
recorded.  Nothing downstream may consult the repository except through here.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

def _walk_up_to_checkout() -> Path:
    """Locate the checkout from this file's own position, never an absolute pin.

    ``law/model/sources.py`` sits two directories below the repository root, but
    the lane must also run from a staging copy, so the anchor is a file only a
    checkout has rather than a fixed depth.  ``RR_REPO_ROOT`` overrides it.
    """

    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "grounded-0_4" / "rr_api.py").is_file():
            return parent
    raise SystemExit(
        "rr-formal-verify-law: cannot locate a receiver-reliance checkout "
        "(no grounded-0_4/rr_api.py above this file); set RR_REPO_ROOT"
    )


def repo_root() -> Path:
    override = os.environ.get("RR_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return _walk_up_to_checkout()


# Logical name -> repository-relative path.  These are the ONLY files the model
# is permitted to read.
SOURCE_PATHS: dict[str, str] = {
    "contract_0_2": "baseline-run/control/B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json",
    "matrix_0_1": "baseline-run/control/B1_CAPABILITY_MATRIX_0_1.json",
    "contract_0_3": "supplemental-0_3/control/B1_SUPPLEMENTAL_COMPARATOR_CONTRACT_0_3.json",
    "matrix_0_3": "supplemental-0_3/control/B1_COMPOSED_CAPABILITY_MATRIX_0_3.json",
    "closures_0_4": "grounded-0_4/closures_0_4.json",
    "authority_register_0_4": "grounded-0_4/authority_register_0_4.json",
    # Operator semantics (see model/ASSUMPTIONS.md A1): the two independent
    # shipped evaluators, used as the executable definition of the frozen
    # predicate vocabulary and as a differential oracle against each other.
    "evaluator_primary": "baseline-run/implementation-output-0.2/b1_capabilities.py",
    "evaluator_second": "second-implementation/rr2.py",
    # Closure-operator semantics (PROJECTION_NE / DERIVED_DIFF_NE) and the
    # sealed end-to-end composition (frozen table then closure layer).
    "closure_engine_0_4": "grounded-0_4/rr_api.py",
    # Sealed fixture packs, used ONLY as a source of well-formed request
    # envelopes (see model/ASSUMPTIONS.md A5).  No expected output is read.
    "fixtures_0_2": "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json",
    "fixtures_0_3": "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
}


@dataclass(frozen=True)
class Source:
    name: str
    relpath: str
    abspath: str
    sha256: str
    byte_length: int


_CACHE: dict[str, tuple[Source, bytes]] = {}


def _read(name: str) -> tuple[Source, bytes]:
    if name in _CACHE:
        return _CACHE[name]
    rel = SOURCE_PATHS[name]
    path = (repo_root() / rel).resolve()
    raw = path.read_bytes()
    src = Source(
        name=name,
        relpath=rel,
        abspath=str(path),
        sha256=hashlib.sha256(raw).hexdigest().upper(),
        byte_length=len(raw),
    )
    _CACHE[name] = (src, raw)
    return _CACHE[name]


def load_json(name: str) -> Any:
    src, raw = _read(name)
    return json.loads(raw.decode("utf-8"))


def load_module(name: str):
    """Import a shipped source file as an isolated module (no package side effects)."""
    src, _ = _read(name)
    modname = f"_rrformal_{name}"
    if modname in sys.modules:
        return sys.modules[modname]
    spec = importlib.util.spec_from_file_location(modname, src.abspath)
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def digest_manifest() -> list[dict[str, Any]]:
    """Every source actually touched this run, with its SHA-256, sorted by name."""
    out = []
    for name in sorted(_CACHE):
        src = _CACHE[name][0]
        out.append(
            {
                "name": src.name,
                "path": src.relpath,
                "sha256": src.sha256,
                "byte_length": src.byte_length,
            }
        )
    return out


def load_all() -> None:
    """Force-read every declared source so the manifest is complete and stable."""
    for name in SOURCE_PATHS:
        _read(name)
