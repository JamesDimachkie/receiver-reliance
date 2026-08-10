"""receiver_reliance — library API over the frozen engine + grounded 0.4 layer.

Supported mode: editable install from a repo checkout (`pip install -e .`),
or any sys.path arrangement where this package sits beside `grounded-0_4/`
and `baseline-run/`. The heavy lifting lives in `grounded-0_4/rr_api.py`;
this package is the stable import surface:

    from receiver_reliance import decide, decide_audited

`decide(request)` returns the frozen engine's (response, exit_code),
byte-faithful to the stdio runner. `decide_audited(request)` returns the
grounded 0.4 audited decision (input-bound seal, witness trace, closure
findings). See HOST_OBLIGATIONS.md for what remains the host's job.
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

decide = _module.decide
decide_audited = _module.decide_audited
closure_findings = _module.closure_findings
derive_record_references = _module.derive_record_references
AUDIT_FORMAT = _module.AUDIT_FORMAT

__all__ = [
    "decide",
    "decide_audited",
    "closure_findings",
    "derive_record_references",
    "AUDIT_FORMAT",
]
__version__ = "1.2.0.dev0"
