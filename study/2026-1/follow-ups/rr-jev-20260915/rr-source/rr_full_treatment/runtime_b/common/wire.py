"""canonical_wire: framing, canonical serialisations and domain-separated hashes.

Every construction here is transcribed from the authority's ``canonical_wire``
object and from nothing else.
"""

import base64
import hashlib
import json
import unicodedata

# canonical_wire.limits
LIMIT_COMMON_BYTES = 1048576
LIMIT_STATE_BYTES = 262144
LIMIT_DEPTH = 24
LIMIT_COLLECTION_MEMBERS = 4096
LIMIT_STRING_UTF8_BYTES = 65536

INT64_MIN = -9223372036854775808
INT64_MAX = 9223372036854775807

ZERO64 = "0" * 64

_B64_ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
)


def frame(payload: bytes) -> bytes:
    """canonical_wire.frame: UINT64BE(byte_length) || bytes."""
    return len(payload).to_bytes(8, "big") + payload


def sha256_upper(payload: bytes) -> str:
    """canonical_wire.sha256: uppercase 64-hex SHA-256."""
    return hashlib.sha256(payload).hexdigest().upper()


def jcs(value) -> bytes:
    """canonical_wire.jcs / common_state_jcs.

    UTF-8 JSON, object keys sorted by Unicode scalar value, ``,``/``:``
    separators only, no ASCII escaping beyond the required JSON escapes, no BOM
    and no LF.  Floats and non-finite values are forbidden; the caller is
    responsible for having admitted the value.
    """
    return _dump(value, ensure_ascii=False)


def cj6(value) -> bytes:
    """canonical_wire.registry_row_encoding: the ASCII-escaped sibling of jcs."""
    return _dump(value, ensure_ascii=True)


def _dump(value, *, ensure_ascii: bool) -> bytes:
    _reject_inadmissible(value)
    text = json.dumps(
        value,
        ensure_ascii=ensure_ascii,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        check_circular=False,
    )
    return text.encode("utf-8", "surrogatepass")


def _reject_inadmissible(value) -> None:
    stack = [value]
    while stack:
        node = stack.pop()
        if node is None or isinstance(node, str):
            continue
        if isinstance(node, bool):
            continue
        if isinstance(node, int):
            if not INT64_MIN <= node <= INT64_MAX:
                raise ValueError("integer outside signed-int64")
            continue
        if isinstance(node, float):
            raise ValueError("float is forbidden")
        if isinstance(node, list):
            stack.extend(node)
            continue
        if isinstance(node, dict):
            for key, member in node.items():
                if not isinstance(key, str):
                    raise ValueError("non-string object key")
                stack.append(member)
            continue
        raise ValueError("value outside the admitted JSON domain")


def dh6(domain: str, value) -> str:
    """canonical_wire.domain_hash.

    ``DH6(D,X) = UPPERHEX(SHA256(ASCII(D) || 00 || UINT64BE(len(CJ6(X))) || CJ6(X)))``
    """
    encoded = cj6(value)
    return sha256_upper(
        domain.encode("ascii") + b"\x00" + frame(encoded)
    )


def bdh6(domain: str, payload: bytes) -> str:
    """canonical_wire.binary_domain_hash.

    ``BDH6(D,B) = UPPERHEX(SHA256(ASCII(D) || 00 || UINT64BE(len(B)) || B))``
    """
    return sha256_upper(domain.encode("ascii") + b"\x00" + frame(payload))


def stream_root(domain: str, rows) -> str:
    """canonical_wire.stream_root over committed ordered rows."""
    digest = hashlib.sha256()
    digest.update(domain.encode("ascii"))
    digest.update(b"\x00")
    for row in rows:
        digest.update(frame(cj6(row)))
    return digest.hexdigest().upper()


def unsigned_decimal_string(number: int) -> str:
    """canonical_wire.unsigned_decimal_string: ``0|[1-9][0-9]*``."""
    if number < 0:
        raise ValueError("unsigned decimal string is nonnegative")
    return str(number)


def is_canonical_base64(text: str) -> bool:
    """canonical_wire.base64: RFC4648 standard alphabet, padding required, round-trips."""
    if not isinstance(text, str) or len(text) % 4 != 0:
        return False
    body = text
    pad = 0
    while body.endswith("="):
        body = body[:-1]
        pad += 1
    if pad > 2:
        return False
    if any(character not in _B64_ALPHABET for character in body):
        return False
    if pad and (len(body) % 4) not in (2, 3):
        return False
    if pad == 0 and len(body) % 4 == 1:
        return False
    try:
        raw = b64decode_strict(text)
    except ValueError:
        return False
    return b64encode(raw) == text


def b64decode_strict(text: str) -> bytes:
    if not isinstance(text, str) or len(text) % 4 != 0:
        raise ValueError("not canonical base64")
    try:
        raw = base64.b64decode(text.encode("ascii"), validate=True)
    except Exception as exc:  # narrow: binascii.Error / UnicodeEncodeError
        raise ValueError("not canonical base64") from exc
    if base64.b64encode(raw).decode("ascii") != text:
        raise ValueError("not canonical base64")
    return raw


def b64encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def is_nfc(text: str) -> bool:
    """True when ``text`` is already in Unicode Normalization Form C."""
    try:
        return unicodedata.normalize("NFC", text) == text
    except (TypeError, ValueError):
        return False


def has_surrogate(text: str) -> bool:
    """True when ``text`` carries any UTF-16 surrogate code point."""
    return any(0xD800 <= ord(character) <= 0xDFFF for character in text)
