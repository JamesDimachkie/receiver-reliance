"""Shared, dependency-free treatment boundary machinery."""

from .admission import admit_pair
from .result import boundary_exception, decision_bytes, presemantic_bytes
from .wire import Fault, cj6, dh6, jcs, stream_root

__all__ = (
    "Fault",
    "admit_pair",
    "boundary_exception",
    "cj6",
    "decision_bytes",
    "dh6",
    "jcs",
    "presemantic_bytes",
    "stream_root",
)
