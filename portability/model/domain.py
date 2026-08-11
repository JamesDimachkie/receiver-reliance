"""Frozen bounds and symbols for finite model M.

This module is deliberately data-only.  Changing any value here changes the
declared model and therefore invalidates an existing receipt.
"""
from __future__ import annotations

from dataclasses import dataclass

MODEL_ID = "RR-PORTABILITY-M-20260810"
MAX_REQUEST_BYTES = 48
MAX_DEPTH = 6
MAX_DUPLICATES_PER_OBJECT = 3
MAX_CALLERS = 2
MAX_REQUESTS_PER_STREAM = 3
COMPLETE_SCHEDULER_REQUESTS = 2
MAX_CHUNK_SPLITS_COMPLETE = 2
MAX_WRITE_SPLITS = 2
R3_SCHEDULE_SEED = 0x5252334D


@dataclass(frozen=True, slots=True)
class Token:
    """One concrete expansion of a symbol in the twelve-symbol alphabet."""

    symbol: str
    variant: str
    raw: bytes
    key_id: int | None = None
    key_rank: int | None = None
    is_repeat_a: bool = False
    is_non_nfc: bool = False
    is_lone_surrogate: bool = False

    @property
    def label(self) -> str:
        return self.symbol if self.variant == "plain" else f"{self.symbol}:{self.variant}"


# The base alphabet has exactly twelve symbols.  KEY_B carries the frozen
# variant flag; expanding that flag produces three concrete transition labels
# without adding a thirteenth base symbol.
BASE_ALPHABET = (
    "LBRACE",
    "RBRACE",
    "LBRACKET",
    "RBRACKET",
    "COLON",
    "COMMA",
    "LF",
    "KEY_A",
    "KEY_A_REPEAT",
    "KEY_B",
    "INT_1",
    "GARBAGE_FF",
)

TOKENS = (
    Token("LBRACE", "plain", b"{"),
    Token("RBRACE", "plain", b"}"),
    Token("LBRACKET", "plain", b"["),
    Token("RBRACKET", "plain", b"]"),
    Token("COLON", "plain", b":"),
    Token("COMMA", "plain", b","),
    Token("LF", "plain", b"\n"),
    Token("KEY_A", "plain", b'"a"', key_id=0, key_rank=0),
    Token(
        "KEY_A_REPEAT",
        "plain",
        b'"a"',
        key_id=0,
        key_rank=0,
        is_repeat_a=True,
    ),
    Token("KEY_B", "plain", b'"b"', key_id=1, key_rank=1),
    Token(
        "KEY_B",
        "non_nfc",
        '"e\u0301"'.encode("utf-8"),
        key_id=2,
        key_rank=2,
        is_non_nfc=True,
    ),
    Token(
        "KEY_B",
        "lone_surrogate",
        b'"\\ud800"',
        key_id=3,
        key_rank=None,
        is_lone_surrogate=True,
    ),
    Token("INT_1", "plain", b"1"),
    Token("GARBAGE_FF", "plain", b"\xff"),
)

NON_LF_TOKENS = tuple(token for token in TOKENS if token.symbol != "LF")
LF_TOKEN = next(token for token in TOKENS if token.symbol == "LF")

assert len(BASE_ALPHABET) == 12
assert {token.symbol for token in TOKENS} == set(BASE_ALPHABET)


ASSUMPTIONS = (
    "A request is a symbolic token trace terminated by LF or by final EOF; zero-byte EOF is clean stream shutdown, not a record.",
    "KEY_A_REPEAT is selected only while consuming raw key a after the same object has already seen decoded a; every other parser phase selects KEY_A, so their identical raw spelling is represented exactly once per state.",
    "KEY_B has exactly three flag values: plain, non_nfc, and lone_surrogate.",
    "Each KEY_B flag value has its own decoded member identity: plain b, decomposed e-acute, and lone surrogate; only an identical repeated variant is a duplicate.",
    "The parse quotient retains every fact that can change the selected parse-layer terminal class under the frozen precedence chain.",
    "Transport partitions preserve bytes and record boundaries; split positions inside one read or write phase are bisimilar and are counted with exact combinatorial multiplicity.",
    "Oversize transport is a threshold-relative automaton; the actual 16,777,216-byte boundary is pinned by the RO1/RO2 closure replay.",
    "Each scheduled pause has a mandatory matching resume, so recorded fairness excludes infinite pause executions.",
)

SYMMETRY_REDUCTIONS = (
    "Parser prefixes with equal byte length, control state, stack frames, duplicate fact, NFC fact, and canonicality fact are merged; future terminal classification is congruent on those fields.",
    "Concrete traces reaching a merged parser state are retained as an exact arbitrary-precision multiplicity, not discarded.",
    "KEY_A versus KEY_A_REPEAT duplicate spellings are canonicalized before parser dispatch by object-local phase and seen-key state, including invalid and DONE phases.",
    "Read split locations within the same record phase and write split locations within the same response phase are position-renaming symmetries; all subsets are counted exactly while one structural transition graph is explored.",
    "Caller identities are not quotient-swapped: ordered caller state is retained for P=2.",
)

EXCLUSIONS = (
    "Lexemes outside the frozen alphabet, except the explicitly named historical closure replays.",
    "Requests longer than 48 expanded bytes in the parse lattice, nesting deeper than 6, or more than 3 duplicate members in one object.",
    "More than two callers; these belong to the concurrency ladder.",
    "Complete scheduler enumeration for three-record streams; only the committed seeded adversarial R=3 schedules are included.",
    "Unfair infinite schedules, wall-clock timing, operating-system buffering, signals, process lifecycle, and resource exhaustion; live and concurrency harnesses own those surfaces.",
    "The semantic decision table after parse success; PARSE_OK is a parse-layer terminal, not a claim that the request is behavior-class VALID.",
    "Independent expected bytes, future blinded worlds, research oracle/gold, and rendering.",
)
