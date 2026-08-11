"""Frozen finite model M for receiver-reliance portability validation."""

__all__ = ["build_receipt"]


def build_receipt():
    """Lazily import the explorer so ``python -m`` has a clean module start."""
    from .explorer import build_receipt as _build_receipt

    return _build_receipt()
