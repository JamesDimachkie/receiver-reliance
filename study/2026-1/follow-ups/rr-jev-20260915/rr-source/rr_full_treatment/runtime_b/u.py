"""Arm U -- the transparent arm.

``architecture.arm_isolation``: U imports common code only.  It imports neither
``rr_s_all_kernel`` nor ``receiver_reliance``, and neither of the other two arms.

``u_semantics``: "After common and U state admission, emit
U_TRANSPARENT/PASS/ALLOW with semantic_evidence {transparent:true}.  U does not
construct S input, R derivation, accepted-engine request, or inspect semantic
values beyond shared schema admission."
"""

from .common import seam

ENTRYPOINT = "DECIDE_U"


def _evaluate(canonical_common_value, canonical_module_state_value):
    """U inspects no semantic value beyond the shared schema admission."""
    del canonical_common_value, canonical_module_state_value
    return "U_TRANSPARENT", {"transparent": True}


_SEMANTICS = seam.Semantics(ENTRYPOINT, _evaluate)


def decide(canonical_common_bytes: bytes, canonical_module_state_bytes: bytes) -> bytes:
    """The production entrypoint DECIDE_U."""
    return seam.decide(
        _SEMANTICS, canonical_common_bytes, canonical_module_state_bytes
    )


decide_u = decide
