"""End-to-end evaluation through the sealed composition.

``rr_api.decide_audited`` is the shipped composition of the frozen decision
table with the 0.4 closure layer.  Running it on generated fact profiles gives
the closure-monotonicity property (e) as an observation of the real pipeline
rather than a restatement of the rule.

A request envelope carries more than the decision input (an inner packet
request plus two digests over it).  Those parts are irrelevant to the decision
law but must be well formed, so one envelope per obligation is lifted from the
sealed fixture packs and its ``decision_input.facts`` is replaced.  The
envelope digests bind the inner packet request, which is never modified, so the
substitution keeps the request valid.  Only the request half of a fixture entry
is ever read - never ``expected_response`` or any recorded class.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from . import sources

_ENTRY = re.compile(r"^SEMFX-(OBL-\d\d)-IO-")


class EndToEnd:
    def __init__(self) -> None:
        self.api = sources.load_module("closure_engine_0_4")
        self.templates: dict[str, dict[str, Any]] = {}
        for name in ("fixtures_0_2", "fixtures_0_3"):
            pack = sources.load_json(name)
            for entry in pack["entries"]:
                match = _ENTRY.match(entry["entry_id"])
                if match and match.group(1) not in self.templates:
                    self.templates[match.group(1)] = _decode_request(entry)
        self.calls = 0

    def available(self, obligation_id: str) -> bool:
        return obligation_id in self.templates

    def run(self, obligation_id: str, facts: dict[str, Any]) -> dict[str, Any]:
        """Return the sealed pipeline's view of one fact profile."""
        request = copy.deepcopy(self.templates[obligation_id])
        request["decision_input"]["facts"] = copy.deepcopy(facts)
        self.calls += 1
        result = self.api.decide_audited(request)
        audit = result.get("audit") or {}
        findings = audit.get("closure_findings") or []
        return {
            "audited_class": result.get("audited_behavior_class"),
            "first_match": audit.get("first_match_predicates"),
            "closures_fired": [f["closure_id"] for f in findings if f.get("fired")],
            "closure_errors": [f["closure_id"] for f in findings if "evaluator_error" in f],
            "protocol_error": result.get("audited_behavior_class") == "PROTOCOL_ERROR",
        }


def _decode_request(entry: dict[str, Any]) -> dict[str, Any]:
    import base64
    import json

    return json.loads(base64.b64decode(entry["semantic_request_jcs_lf_base64"]))
