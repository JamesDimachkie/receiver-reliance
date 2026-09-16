"""The fault record and ``diagnostic_authority.fault_selection``."""

from . import vocab


class Fault:
    """One reached diagnostic observation.

    ``document_id`` is the document the fault was observed in; the selection key
    projects it through ``diagnostic_authority.document_projection``.
    """

    __slots__ = ("stage", "code", "document_id", "pointer", "occurrence")

    def __init__(self, stage, code, document_id, pointer="", occurrence=0):
        if stage not in vocab.CODE_ORDER_BY_STAGE:
            raise ValueError("unknown stage")
        if code not in vocab.CODE_ORDER_BY_STAGE[stage]:
            raise ValueError("unknown code for stage")
        if not isinstance(pointer, str):
            raise ValueError("nonstring pointer")
        if not isinstance(occurrence, int) or isinstance(occurrence, bool):
            raise ValueError("non-signed-int64 occurrence")
        if occurrence < 0 or occurrence > 9223372036854775807:
            raise ValueError("negative or oversize occurrence")
        self.stage = stage
        self.code = code
        self.document_id = document_id
        self.pointer = pointer
        self.occurrence = occurrence

    def key(self):
        """The selection tuple [stage,code,document,pointer_utf8,occurrence]."""
        return (
            vocab.stage_index(self.stage),
            vocab.code_index(self.stage, self.code),
            vocab.document_index(self.document_id),
            self.pointer.encode("utf-8", "surrogatepass"),
            self.occurrence,
        )

    def __repr__(self):
        return (
            f"Fault({self.stage},{self.code},{self.document_id},"
            f"{self.pointer!r},{self.occurrence})"
        )


def select(faults):
    """``diagnostic_authority.fault_selection``: the minimum selection tuple.

    A proper UTF-8 prefix sorts before its extension because Python compares
    ``bytes`` lexicographically and a shorter equal prefix compares less.
    """
    if not faults:
        return None
    return min(faults, key=Fault.key)


def pointer_escape(token: str) -> str:
    """RFC6901 reference-token escaping."""
    return token.replace("~", "~0").replace("/", "~1")


def pointer_parent(pointer: str) -> str:
    """RFC6901 parent of a nonempty pointer."""
    if pointer == "":
        raise ValueError("the empty pointer has no parent")
    return pointer[: pointer.rindex("/")]
