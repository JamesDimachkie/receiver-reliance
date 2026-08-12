"""receiver_reliance — library API over the frozen engine + grounded 0.4 layer.

Supported mode: editable install from a repo checkout (`pip install -e .`),
or any sys.path arrangement where this package sits beside `grounded-0_4/`
and `baseline-run/`. The heavy lifting lives in `grounded-0_4/rr_api.py`;
this package is the stable import surface:

    from receiver_reliance import decide, decide_audited

`decide(request)` returns the frozen engine's (response, exit_code),
byte-faithful to the stdio runner. `decide_audited(request)` returns the
grounded audited decision (input-bound seal, governing-policy digests,
witness trace, closure findings, truncation-disclosed record references).

The two surfaces are tiers, not peers: `decide` is the SEALED CONFORMANCE
surface — it binds no decision facts (ERRATA E2) and applies no 0.4 closure
(E5), so a bare sealed receipt proves only that a decision of that class
was sealed under that request id. Any host that needs auditable evidence of
WHAT was decided must use `decide_audited` or record full transcripts
(HOST_OBLIGATIONS.md H5). See TRUST_MODEL.md for what each seal proves.
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
