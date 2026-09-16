"""Pure-Python Ed25519 verification, used only by the conformance runner.

``synthetic_host_abi_kat`` commits a real Ed25519 signature over the exact framed
unsigned host manifest, and ``self_audit_laws`` names it explicitly.  Verifying
it therefore needs a real signature check, not a recorded verdict, and this
module is that check: RFC 8032 Ed25519 (SHA-512, curve25519 in Edwards form) with
no third-party dependency.

This module is never imported by an arm.  It is conformance-runner code only.
"""

import hashlib

_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _sha512(payload):
    return hashlib.sha512(payload).digest()


def _x_recover(y):
    xx = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P)
    x = pow(xx, (_P + 3) // 8, _P)
    if (x * x - xx) % _P != 0:
        x = (x * _I) % _P
    if x % 2 != 0:
        x = _P - x
    return x


_BY = (4 * pow(5, _P - 2, _P)) % _P
_BX = _x_recover(_BY)
_B = (_BX % _P, _BY % _P, 1, (_BX * _BY) % _P)


def _add(point, other):
    x1, y1, z1, t1 = point
    x2, y2, z2, t2 = other
    a = ((y1 - x1) * (y2 - x2)) % _P
    b = ((y1 + x1) * (y2 + x2)) % _P
    c = (2 * t1 * t2 * _D) % _P
    d = (2 * z1 * z2) % _P
    e = b - a
    f = d - c
    g = d + c
    h = b + a
    return ((e * f) % _P, (g * h) % _P, (f * g) % _P, (e * h) % _P)


def _mul(point, scalar):
    result = (0, 1, 1, 0)
    while scalar > 0:
        if scalar & 1:
            result = _add(result, point)
        point = _add(point, point)
        scalar >>= 1
    return result


def _equal(point, other):
    x1, y1, z1, _ = point
    x2, y2, z2, _ = other
    if (x1 * z2 - x2 * z1) % _P != 0:
        return False
    return (y1 * z2 - y2 * z1) % _P == 0


def _decode_int(raw):
    return int.from_bytes(raw, "little")


def _decode_point(raw):
    if len(raw) != 32:
        raise ValueError("point is not 32 bytes")
    value = _decode_int(raw)
    y = value & ((1 << 255) - 1)
    sign = value >> 255
    if y >= _P:
        raise ValueError("point y is out of range")
    x = _x_recover(y)
    if x & 1 != sign:
        x = _P - x
    point = (x, y, 1, (x * y) % _P)
    if not _on_curve(point):
        raise ValueError("point is not on the curve")
    return point


def _on_curve(point):
    x, y, z, t = point
    if (z * t - x * y) % _P != 0:
        return False
    left = (y * y - x * x) * z * z % _P
    right = (z * z * z * z + _D * x * x * y * y) % _P
    return (left - right) % _P == 0


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """RFC 8032 Ed25519 verification.  Total: any malformed input returns False."""
    try:
        if len(signature) != 64 or len(public_key) != 32:
            return False
        point_a = _decode_point(public_key)
        point_r = _decode_point(signature[:32])
        scalar = _decode_int(signature[32:])
        if scalar >= _L:
            return False
        challenge = (
            _decode_int(_sha512(signature[:32] + public_key + message)) % _L
        )
        left = _mul(_B, scalar)
        right = _add(point_r, _mul(point_a, challenge))
        return _equal(left, right)
    except (ValueError, OverflowError, TypeError):
        return False
