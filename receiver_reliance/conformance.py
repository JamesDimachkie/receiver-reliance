"""receiver_reliance.conformance — frozen-engine reproduction, NOT decisions.

``execute(request)`` runs one request through the frozen engine in-process
and returns ``(response, exit_code)`` byte-faithful to the stdio runner.
Its sealed response binds no decision facts (ERRATA E2) and applies no 0.4
closure (E5): a bare sealed receipt proves only that a decision of that
class was sealed under that request id. This namespace exists so the
conformance suites, perf harnesses, and ports can reproduce frozen
behavior; it is explicitly non-evidentiary. Every supported evidentiary
decision goes through ``receiver_reliance.decide_audited``.
"""
from __future__ import annotations

import sys

_module = sys.modules["receiver_reliance._rr_api"]

execute = _module.conformance_execute

__all__ = ["execute"]
