"""Wire admission: size, UTF-8/BOM, strict JSON, value Unicode, canonical form.

The stages implemented here are ADMISSION, WIRE_UNICODE, JSON, VALUE_UNICODE and
CANONICAL of ``diagnostic_authority.stage_order``.  Every fault this module finds
is *recorded*, never thrown: ``fault_selection`` collects all faults whose
prerequisites were reached and takes the minimum, so a stage that can still be
evaluated is still evaluated.  Only a JSON syntax error and an invalid UTF-8
octet truly stop the document, because after either there is no parsed value to
inspect.
"""

from . import faults as fault_mod
from . import wire

_WHITESPACE = b" \t\n\r"
_BOM = b"\xef\xbb\xbf"
_STRUCTURAL_ESCAPES = {
    0x22: '"',
    0x5C: "\\",
    0x2F: "/",
    0x62: "\b",
    0x66: "\f",
    0x6E: "\n",
    0x72: "\r",
    0x74: "\t",
}
_NONFINITE_TOKENS = (b"NaN", b"-Infinity", b"Infinity")


class _Syntax(Exception):
    """Internal control flow for an unrecoverable JSON syntax error."""

    def __init__(self, offset):
        super().__init__(offset)
        self.offset = offset


class Admitted:
    """The outcome of admitting one document."""

    __slots__ = ("value", "parsed", "faults")

    def __init__(self, value, parsed, found):
        self.value = value
        self.parsed = parsed
        self.faults = found


def admit(raw, document_id):
    """Run every reachable pre-schema stage over one document's exact bytes."""
    found = []
    oversize_code = "COMMON_OVERSIZE" if document_id == "COMMON" else "STATE_OVERSIZE"
    limit = (
        wire.LIMIT_COMMON_BYTES
        if document_id == "COMMON"
        else wire.LIMIT_STATE_BYTES
    )
    if len(raw) > limit:
        found.append(fault_mod.Fault("ADMISSION", oversize_code, document_id, "", 0))

    if raw.startswith(_BOM):
        found.append(fault_mod.Fault("WIRE_UNICODE", "BOM", document_id, "", 0))
    utf8_offset = _first_invalid_utf8_offset(raw)
    if utf8_offset is not None:
        found.append(
            fault_mod.Fault("WIRE_UNICODE", "UTF8", document_id, "", utf8_offset)
        )
        return Admitted(None, False, found)

    parser = _Parser(raw, document_id, found)
    try:
        value = parser.parse()
    except _Syntax as syntax:
        found.append(fault_mod.Fault("JSON", "SYNTAX", document_id, "", syntax.offset))
        return Admitted(None, False, found)

    _structural_limits(value, document_id, found)
    _value_unicode(value, document_id, found)
    _canonical(value, raw, document_id, found)
    return Admitted(value, True, found)


def _first_invalid_utf8_offset(raw):
    """Byte offset of the first octet that is not part of a valid UTF-8 scalar."""
    try:
        raw.decode("utf-8")
        return None
    except UnicodeDecodeError as error:
        return error.start


class _Parser:
    """Recursive-descent strict JSON parser over exact bytes.

    Byte offsets are exact because the parser never leaves the byte domain; the
    input has already been proven valid UTF-8, so every string slice decodes.
    """

    def __init__(self, raw, document_id, found):
        self.raw = raw
        self.length = len(raw)
        self.document_id = document_id
        self.found = found
        self.index = 0
        self.depth = 0
        self.depth_reported = False
        self.collection_reported = False
        self.string_reported = False

    # -- driver ---------------------------------------------------------
    def parse(self):
        self._skip_whitespace()
        value = self._value("")
        self._skip_whitespace()
        if self.index != self.length:
            raise _Syntax(self.index)
        return value

    def _skip_whitespace(self):
        while self.index < self.length and self.raw[self.index] in _WHITESPACE:
            self.index += 1

    def _peek(self):
        if self.index >= self.length:
            raise _Syntax(self.index)
        return self.raw[self.index]

    def _record(self, stage, code, pointer, occurrence):
        self.found.append(
            fault_mod.Fault(stage, code, self.document_id, pointer, occurrence)
        )

    def _enter(self):
        self.depth += 1

    def _leave(self):
        self.depth -= 1

    def _note_collection(self, members):
        # T-10: limits inspect the completed value, never a parsed prefix.
        pass

    # -- values ---------------------------------------------------------
    def _value(self, pointer):
        character = self._peek()
        if character == 0x7B:  # {
            return self._object(pointer)
        if character == 0x5B:  # [
            return self._array(pointer)
        if character == 0x22:  # "
            return self._string()
        if character == 0x74 and self.raw[self.index : self.index + 4] == b"true":
            self.index += 4
            return True
        if character == 0x66 and self.raw[self.index : self.index + 5] == b"false":
            self.index += 5
            return False
        if character == 0x6E and self.raw[self.index : self.index + 4] == b"null":
            self.index += 4
            return None
        return self._number()

    def _object(self, pointer):
        self.index += 1
        self._enter()
        result = {}
        seen = {}
        self._skip_whitespace()
        if self.index < self.length and self.raw[self.index] == 0x7D:
            self.index += 1
            self._leave()
            return result
        members = 0
        while True:
            self._skip_whitespace()
            if self._peek() != 0x22:
                raise _Syntax(self.index)
            key = self._string()
            self._skip_whitespace()
            if self._peek() != 0x3A:
                raise _Syntax(self.index)
            self.index += 1
            self._skip_whitespace()
            child_pointer = pointer + "/" + fault_mod.pointer_escape(key)
            value = self._value(child_pointer)
            members += 1
            if key in seen:
                self._record("JSON", "DUPLICATE_KEY", child_pointer, seen[key])
                seen[key] += 1
            else:
                seen[key] = 1
            result[key] = value
            self._note_collection(members)
            self._skip_whitespace()
            if self.index >= self.length:
                raise _Syntax(self.index)
            if self.raw[self.index] == 0x2C:
                self.index += 1
                continue
            if self.raw[self.index] == 0x7D:
                self.index += 1
                self._leave()
                return result
            raise _Syntax(self.index)

    def _array(self, pointer):
        self.index += 1
        self._enter()
        result = []
        self._skip_whitespace()
        if self.index < self.length and self.raw[self.index] == 0x5D:
            self.index += 1
            self._leave()
            return result
        while True:
            self._skip_whitespace()
            child_pointer = pointer + "/" + str(len(result))
            result.append(self._value(child_pointer))
            self._note_collection(len(result))
            self._skip_whitespace()
            if self.index >= self.length:
                raise _Syntax(self.index)
            if self.raw[self.index] == 0x2C:
                self.index += 1
                continue
            if self.raw[self.index] == 0x5D:
                self.index += 1
                self._leave()
                return result
            raise _Syntax(self.index)

    def _string(self):
        opening_quote = self.index
        self.index += 1
        pieces = []
        chunk_start = self.index
        while True:
            if self.index >= self.length:
                raise _Syntax(opening_quote)
            octet = self.raw[self.index]
            if octet == 0x22:
                pieces.append(self.raw[chunk_start : self.index].decode("utf-8"))
                self.index += 1
                break
            if octet == 0x5C:
                pieces.append(self.raw[chunk_start : self.index].decode("utf-8"))
                self.index += 1
                if self.index >= self.length:
                    raise _Syntax(opening_quote)
                pieces.append(self._escape())
                chunk_start = self.index
                continue
            if octet < 0x20:
                raise _Syntax(self.index)
            self.index += 1
        text = "".join(pieces)
        return text

    def _escape(self):
        if self.index >= self.length:
            raise _Syntax(self.index)
        octet = self.raw[self.index]
        if octet in _STRUCTURAL_ESCAPES:
            self.index += 1
            return _STRUCTURAL_ESCAPES[octet]
        if octet != 0x75:  # u
            raise _Syntax(self.index)
        self.index += 1
        return chr(self._hex4())

    def _hex4(self):
        if self.index + 4 > self.length:
            raise _Syntax(self.index)
        digits = self.raw[self.index : self.index + 4]
        for octet in digits:
            if not (
                0x30 <= octet <= 0x39
                or 0x41 <= octet <= 0x46
                or 0x61 <= octet <= 0x66
            ):
                raise _Syntax(self.index)
        code = int(digits.decode("ascii"), 16)
        self.index += 4
        return code

    def _number(self):
        start = self.index
        for token in _NONFINITE_TOKENS:
            if self.raw[self.index : self.index + len(token)] == token:
                self.index += len(token)
                self._record("JSON", "FLOAT_FORBIDDEN", "", start)
                return 0
        index = self.index
        if index < self.length and self.raw[index] == 0x2D:
            index += 1
        digits_start = index
        while index < self.length and 0x30 <= self.raw[index] <= 0x39:
            index += 1
        if index == digits_start:
            raise _Syntax(start)
        integer_end = index
        is_float = False
        if index < self.length and self.raw[index] == 0x2E:
            is_float = True
            index += 1
            fraction_start = index
            while index < self.length and 0x30 <= self.raw[index] <= 0x39:
                index += 1
            if index == fraction_start:
                raise _Syntax(index)
        if index < self.length and self.raw[index] in (0x65, 0x45):
            is_float = True
            index += 1
            if index < self.length and self.raw[index] in (0x2B, 0x2D):
                index += 1
            exponent_start = index
            while index < self.length and 0x30 <= self.raw[index] <= 0x39:
                index += 1
            if index == exponent_start:
                raise _Syntax(index)
        text = self.raw[start:integer_end].decode("ascii")
        body = text[1:] if text.startswith("-") else text
        if len(body) > 1 and body[0] == "0":
            raise _Syntax(start)
        self.index = index
        if is_float:
            self._record("JSON", "FLOAT_FORBIDDEN", "", start)
            return 0
        number = int(text)
        if not wire.INT64_MIN <= number <= wire.INT64_MAX:
            self._record("JSON", "INTEGER_RANGE", "", start)
            return 0
        return number


def _structural_limits(value, document_id, found):
    """Successor T-10: these prerequisites exist only after complete parsing."""
    pending = [(value, 1)]
    codes = set()
    while pending:
        item, level = pending.pop()
        if isinstance(item, (dict, list)):
            if level > wire.LIMIT_DEPTH:
                codes.add(("DEPTH_LIMIT", wire.LIMIT_DEPTH))
                continue
            if len(item) > wire.LIMIT_COLLECTION_MEMBERS:
                codes.add(("COLLECTION_LIMIT", wire.LIMIT_COLLECTION_MEMBERS))
            if isinstance(item, dict):
                pending.extend((key, level + 1) for key in item)
                pending.extend((member, level + 1) for member in item.values())
            else:
                pending.extend((member, level + 1) for member in item)
        elif isinstance(item, str) and len(item.encode("utf-8", "surrogatepass")) > wire.LIMIT_STRING_UTF8_BYTES:
            codes.add(("STRING_LIMIT", wire.LIMIT_STRING_UTF8_BYTES))
    for code, limit in sorted(codes):
        found.append(fault_mod.Fault("ADMISSION", code, document_id, "", limit))


def _value_unicode(value, document_id, found):
    """VALUE_UNICODE: lone surrogates and non-NFC text, keys included."""
    surrogate = False
    nonnfc = False
    stack = [value]
    while stack:
        node = stack.pop()
        if isinstance(node, str):
            if wire.has_surrogate(node):
                surrogate = True
            elif not wire.is_nfc(node):
                nonnfc = True
        elif isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, dict):
            for key, member in node.items():
                if wire.has_surrogate(key):
                    surrogate = True
                elif not wire.is_nfc(key):
                    nonnfc = True
                stack.append(member)
    if surrogate:
        found.append(fault_mod.Fault("VALUE_UNICODE", "SURROGATE", document_id, "", 0))
    if nonnfc:
        found.append(fault_mod.Fault("VALUE_UNICODE", "NFC", document_id, "", 0))


def _canonical(value, raw, document_id, found):
    """CANONICAL: the document must already be its own canonical serialisation."""
    for entry in found:
        if entry.document_id == document_id and entry.stage in (
            "JSON",
            "VALUE_UNICODE",
        ):
            return
    try:
        rendered = wire.jcs(value)
    except ValueError:
        return
    if rendered != raw:
        found.append(fault_mod.Fault("CANONICAL", "NONCANONICAL", document_id, "", 0))
