"""receiver_reliance — library API over the frozen engine + grounded 0.4 layer.

Supported mode: editable install from a repo checkout (`pip install -e .`),
or any sys.path arrangement where this package sits beside `grounded-0_4/`
and `baseline-run/`. The heavy lifting lives in `grounded-0_4/rr_api.py`;
this package is the stable import surface:

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

import importlib.util
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parent.parent
_RR_API = _REPO / "grounded-0_4" / "rr_api.py"
if not _RR_API.is_file():
    raise ImportError(
        "receiver_reliance requires a repo checkout: grounded-0_4/rr_api.py "
        f"not found beside the package (looked at {_RR_API})"
    )
_spec = importlib.util.spec_from_file_location("receiver_reliance._rr_api", _RR_API)
_module = importlib.util.module_from_spec(_spec)
sys.modules["receiver_reliance._rr_api"] = _module
_spec.loader.exec_module(_module)

decide_audited = _module.decide_audited
closure_findings = _module.closure_findings
derive_record_references = _module.derive_record_references
AUDIT_FORMAT = _module.AUDIT_FORMAT

__all__ = [
    "decide_audited",
    "closure_findings",
    "derive_record_references",
    "AUDIT_FORMAT",
]
__version__ = "1.2.0.dev0"
