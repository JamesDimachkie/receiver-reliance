"""Transparent U arm."""

from __future__ import annotations

from .common.admission import admit_pair
from .common.result import boundary_exception, decision_bytes

ENTRYPOINT = "DECIDE_U"
MODULE = "U"


def decide(canonical_common_bytes: bytes, canonical_module_state_bytes: bytes) -> bytes:
    try:
        _common, _state, refusal, _refetch = admit_pair(
            ENTRYPOINT,
            MODULE,
            "STATE_U",
            canonical_common_bytes,
            canonical_module_state_bytes,
        )
        if refusal is not None:
            return refusal
        return decision_bytes(
            ENTRYPOINT,
            MODULE,
            canonical_common_bytes,
            canonical_module_state_bytes,
            "U_TRANSPARENT",
            "MODULE_SEMANTICS",
            semantic_evidence={"transparent": True},
        )
    except BaseException:
        return boundary_exception(ENTRYPOINT, canonical_common_bytes, canonical_module_state_bytes)


decide_u = decide

__all__ = ("decide", "decide_u")
