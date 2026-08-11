"""Explicit-state parser quotient for finite model M."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
import hashlib
from typing import Callable, Iterable

from .domain import (
    LF_TOKEN,
    MAX_DEPTH,
    MAX_DUPLICATES_PER_OBJECT,
    MAX_REQUEST_BYTES,
    NON_LF_TOKENS,
    Token,
)


@dataclass(frozen=True, slots=True)
class ObjectFrame:
    seen_mask: int = 0
    duplicate_count: int = 0
    last_key_rank: int | None = None


@dataclass(frozen=True, slots=True)
class ArrayFrame:
    marker: int = 0


Frame = ObjectFrame | ArrayFrame


@dataclass(frozen=True, slots=True)
class ParseState:
    byte_length: int
    expect: str
    stack: tuple[Frame, ...] = ()
    duplicate_seen: bool = False
    non_nfc_seen: bool = False
    canonical_violation: bool = False


INITIAL_STATE = ParseState(0, "VALUE")

_EXPECT_CODES = {
    name: code
    for code, name in enumerate(
        (
            "VALUE",
            "INVALID_UTF8",
            "INVALID_JSON",
            "DONE",
            "FIRST_ITEM",
            "FIRST_KEY",
            "NEXT_KEY",
            "COLON",
            "AFTER",
        )
    )
}
_EXPECT_NAMES = tuple(_EXPECT_CODES)


def pack_state(state: ParseState) -> int:
    """Losslessly pack all non-length quotient fields into one integer."""
    if len(state.stack) > MAX_DEPTH:
        raise ValueError("state depth exceeds model bound")
    packed = _EXPECT_CODES[state.expect]
    packed |= int(state.duplicate_seen) << 4
    packed |= int(state.non_nfc_seen) << 5
    packed |= int(state.canonical_violation) << 6
    packed |= len(state.stack) << 7
    shift = 10
    for frame in state.stack:
        if isinstance(frame, ArrayFrame):
            frame_code = 0
        else:
            if not 0 <= frame.seen_mask <= 0xF:
                raise ValueError("seen-key mask exceeds packed width")
            if not 0 <= frame.duplicate_count <= MAX_DUPLICATES_PER_OBJECT:
                raise ValueError("duplicate count exceeds packed width")
            rank_code = 0 if frame.last_key_rank is None else frame.last_key_rank + 1
            if not 0 <= rank_code <= 3:
                raise ValueError("key rank exceeds packed width")
            frame_code = (
                1
                | (frame.seen_mask << 1)
                | (frame.duplicate_count << 5)
                | (rank_code << 7)
            )
        packed |= frame_code << shift
        shift += 9
    return packed


def unpack_state(packed: int, byte_length: int) -> ParseState:
    """Inverse of :func:`pack_state` for one known byte-length layer."""
    expect_code = packed & 0xF
    if expect_code >= len(_EXPECT_NAMES):
        raise ValueError("unknown packed parser phase")
    depth = (packed >> 7) & 0x7
    if depth > MAX_DEPTH:
        raise ValueError("packed state depth exceeds model bound")
    stack: list[Frame] = []
    shift = 10
    for _ in range(depth):
        frame_code = (packed >> shift) & 0x1FF
        shift += 9
        if frame_code == 0:
            stack.append(ArrayFrame())
            continue
        if not frame_code & 1:
            raise ValueError("invalid packed frame type")
        rank_code = (frame_code >> 7) & 0x3
        stack.append(
            ObjectFrame(
                seen_mask=(frame_code >> 1) & 0xF,
                duplicate_count=(frame_code >> 5) & 0x3,
                last_key_rank=None if rank_code == 0 else rank_code - 1,
            )
        )
    if packed >> shift:
        raise ValueError("nonzero bits above packed parser state")
    return ParseState(
        byte_length=byte_length,
        expect=_EXPECT_NAMES[expect_code],
        stack=tuple(stack),
        duplicate_seen=bool((packed >> 4) & 1),
        non_nfc_seen=bool((packed >> 5) & 1),
        canonical_violation=bool((packed >> 6) & 1),
    )


def _invalid(state: ParseState, token: Token) -> ParseState:
    if token.symbol == "GARBAGE_FF":
        expect = "INVALID_UTF8"
    elif state.expect == "INVALID_UTF8":
        expect = "INVALID_UTF8"
    else:
        expect = "INVALID_JSON"
    return ParseState(
        state.byte_length,
        expect,
        (),
        state.duplicate_seen,
        False,
        False,
    )


def _normalize(state: ParseState) -> ParseState:
    """Erase history proven irrelevant to every future terminal.

    Duplicate precedence outranks JSON/NFC, while canonical JSON failure
    outranks NFC.  Once either fact is permanent, object key ordering history
    cannot affect a future result.  Seen-key masks and duplicate counters stay
    intact because they enforce K and allow a later duplicate to outrank JSON.
    """
    if not (state.duplicate_seen or state.canonical_violation):
        return state
    normalized_stack = tuple(
        replace(frame, last_key_rank=None) if isinstance(frame, ObjectFrame) else frame
        for frame in state.stack
    )
    return replace(
        state,
        stack=normalized_stack,
        non_nfc_seen=False,
        canonical_violation=False if state.duplicate_seen else state.canonical_violation,
    )


def _finish_value(state: ParseState) -> ParseState:
    return replace(state, expect="AFTER" if state.stack else "DONE")


def _consume_value(state: ParseState, token: Token) -> ParseState | None:
    if token.symbol == "LBRACE":
        if len(state.stack) >= MAX_DEPTH:
            return None
        return replace(state, expect="FIRST_KEY", stack=state.stack + (ObjectFrame(),))
    if token.symbol == "LBRACKET":
        if len(state.stack) >= MAX_DEPTH:
            return None
        return replace(state, expect="FIRST_ITEM", stack=state.stack + (ArrayFrame(),))
    if token.symbol == "INT_1":
        return _finish_value(state)
    if token.symbol in ("KEY_A", "KEY_B") and not token.is_repeat_a:
        state = replace(
            state,
            non_nfc_seen=state.non_nfc_seen or token.is_non_nfc,
            canonical_violation=state.canonical_violation or token.is_lone_surrogate,
        )
        return _finish_value(state)
    return _invalid(state, token)


def _consume_key(state: ParseState, token: Token) -> ParseState | None:
    frame = state.stack[-1]
    assert isinstance(frame, ObjectFrame)
    if token.symbol not in ("KEY_A", "KEY_A_REPEAT", "KEY_B"):
        return _invalid(state, token)

    bit = 1 << int(token.key_id)
    seen = bool(frame.seen_mask & bit)
    # The two a labels have identical bytes.  Their admissibility rule is the
    # canonical labeling symmetry: KEY_A first, KEY_A_REPEAT thereafter.
    if token.symbol == "KEY_A" and seen:
        return None
    if token.is_repeat_a and not seen:
        return None

    duplicate_count = frame.duplicate_count + int(seen)
    if duplicate_count > MAX_DUPLICATES_PER_OBJECT:
        return None
    bad_order = (
        token.key_rank is not None
        and frame.last_key_rank is not None
        and token.key_rank < frame.last_key_rank
    )
    updated = ObjectFrame(
        seen_mask=frame.seen_mask | bit,
        duplicate_count=duplicate_count,
        last_key_rank=token.key_rank if token.key_rank is not None else frame.last_key_rank,
    )
    return replace(
        state,
        expect="COLON",
        stack=state.stack[:-1] + (updated,),
        duplicate_seen=state.duplicate_seen or seen,
        non_nfc_seen=state.non_nfc_seen or token.is_non_nfc,
        canonical_violation=state.canonical_violation or token.is_lone_surrogate or bad_order,
    )


def token_label_is_admissible(state: ParseState, token: Token) -> bool:
    """Choose exactly one symbolic label for each physical token spelling.

    ``KEY_A`` and ``KEY_A_REPEAT`` intentionally have the same raw expansion.
    The repeat label exists only to retain the object-local duplicate fact: it
    is selected while consuming an object key after that same object has
    already seen decoded key ``a``. Every other parser phase, including
    permanent invalid and DONE states, selects the ordinary ``KEY_A`` label.

    Keeping this decision ahead of parser branch dispatch prevents one
    physical byte trace from acquiring two symbolic paths and potentially two
    terminal classes.
    """
    if token.symbol not in ("KEY_A", "KEY_A_REPEAT"):
        return True
    repeat_context = False
    if state.expect in ("FIRST_KEY", "NEXT_KEY") and state.stack:
        frame = state.stack[-1]
        repeat_context = isinstance(frame, ObjectFrame) and bool(frame.seen_mask & 1)
    return token.is_repeat_a == repeat_context


def transition(state: ParseState, token: Token) -> ParseState | None:
    """Return the next quotient state, or None when the edge leaves M."""
    if token.symbol == "LF":
        raise ValueError("LF is a terminal action, not a parser-state transition")
    if state.byte_length + len(token.raw) > MAX_REQUEST_BYTES:
        return None
    if not token_label_is_admissible(state, token):
        return None
    if token.symbol == "GARBAGE_FF" or state.expect in ("INVALID_JSON", "INVALID_UTF8", "DONE"):
        result = _invalid(state, token)
    elif state.expect == "VALUE":
        result = _consume_value(state, token)
    elif state.expect == "FIRST_ITEM":
        if token.symbol == "RBRACKET":
            result = _finish_value(replace(state, stack=state.stack[:-1]))
        else:
            result = _consume_value(replace(state, expect="VALUE"), token)
    elif state.expect in ("FIRST_KEY", "NEXT_KEY"):
        if state.expect == "FIRST_KEY" and token.symbol == "RBRACE":
            result = _finish_value(replace(state, stack=state.stack[:-1]))
        else:
            result = _consume_key(state, token)
    elif state.expect == "COLON":
        result = replace(state, expect="VALUE") if token.symbol == "COLON" else _invalid(state, token)
    elif state.expect == "AFTER":
        frame = state.stack[-1]
        if isinstance(frame, ObjectFrame):
            if token.symbol == "COMMA":
                result = replace(state, expect="NEXT_KEY")
            elif token.symbol == "RBRACE":
                result = _finish_value(replace(state, stack=state.stack[:-1]))
            else:
                result = _invalid(state, token)
        else:
            if token.symbol == "COMMA":
                result = replace(state, expect="VALUE")
            elif token.symbol == "RBRACKET":
                result = _finish_value(replace(state, stack=state.stack[:-1]))
            else:
                result = _invalid(state, token)
    else:  # pragma: no cover - construction invariant
        raise AssertionError(state.expect)
    if result is None:
        return None
    return _normalize(replace(result, byte_length=state.byte_length + len(token.raw)))


def terminal_class(state: ParseState, framed_lf: bool) -> str:
    """Selected parse-layer terminal under the frozen precedence chain."""
    if state.expect == "INVALID_UTF8":
        return "ERR_UTF8"
    if state.duplicate_seen:
        return "ERR_DUPLICATE_KEY"
    if not framed_lf:
        return "ERR_JSON"
    if state.byte_length == 0:
        return "ERR_EMPTY_INPUT"
    if state.expect != "DONE" or state.canonical_violation:
        return "ERR_JSON"
    if state.non_nfc_seen:
        return "ERR_NFC"
    return "PARSE_OK"


@dataclass(slots=True)
class ParseExploration:
    states: int
    transitions: int
    terminal_transitions: int
    symbolic_terminal_traces: int
    excluded_edges: int
    excluded_trace_prefixes: int
    terminal_classes: dict[str, dict[str, int]]
    representative_hex: dict[str, str]
    quotient_material_sha256: str


def explore_parser(
    max_request_bytes: int = MAX_REQUEST_BYTES,
    progress: Callable[[int, int, int], None] | None = None,
) -> ParseExploration:
    """Enumerate every reachable quotient state and exact trace multiplicity."""
    if not 0 <= max_request_bytes <= MAX_REQUEST_BYTES:
        raise ValueError(f"max_request_bytes must be in [0, {MAX_REQUEST_BYTES}]")
    # Every transition strictly increases byte_length, so a completed length
    # layer can never be reached again.  Retaining all prior layers in one
    # global map made the corrected quotient page heavily at N=48 without
    # contributing to either reachability or multiplicity.  Keep only the
    # unprocessed per-length maps and release each one after hashing it.
    ways_by_length: list[dict[int, int]] = [
        {} for _ in range(max_request_bytes + 1)
    ]
    ways_by_length[0][pack_state(INITIAL_STATE)] = 1
    state_count = 0
    transitions = 0
    terminal_transitions = 0
    excluded_edges = 0
    excluded_trace_prefixes = 0
    classes: dict[str, dict[str, int]] = defaultdict(lambda: {"quotient_terminals": 0, "symbolic_traces": 0})
    material_hasher = hashlib.sha256()

    for length in range(max_request_bytes + 1):
        layer = ways_by_length[length]
        state_count += len(layer)
        for packed_state in sorted(layer):
            state = unpack_state(packed_state, length)
            state_ways = layer[packed_state]
            material_hasher.update(repr(state).encode("utf-8"))
            material_hasher.update(b"\n")
            if length > 0:
                cls = terminal_class(state, False)
                terminal_transitions += 1
                classes[cls]["quotient_terminals"] += 1
                classes[cls]["symbolic_traces"] += state_ways
            if length + len(LF_TOKEN.raw) <= max_request_bytes:
                cls = terminal_class(state, True)
                terminal_transitions += 1
                classes[cls]["quotient_terminals"] += 1
                classes[cls]["symbolic_traces"] += state_ways
            for token in NON_LF_TOKENS:
                if state.byte_length + len(token.raw) > max_request_bytes:
                    excluded_edges += 1
                    excluded_trace_prefixes += state_ways
                    continue
                nxt = transition(state, token)
                if nxt is None:
                    excluded_edges += 1
                    excluded_trace_prefixes += state_ways
                    continue
                transitions += 1
                if nxt.byte_length <= state.byte_length:
                    raise AssertionError("parser transition did not strictly increase byte_length")
                target_layer = ways_by_length[nxt.byte_length]
                packed_next = pack_state(nxt)
                target_layer[packed_next] = target_layer.get(packed_next, 0) + state_ways
        ways_by_length[length] = {}
        if progress is not None:
            progress(length, state_count, transitions)

    return ParseExploration(
        states=state_count,
        transitions=transitions,
        terminal_transitions=terminal_transitions,
        symbolic_terminal_traces=sum(item["symbolic_traces"] for item in classes.values()),
        excluded_edges=excluded_edges,
        excluded_trace_prefixes=excluded_trace_prefixes,
        terminal_classes=dict(sorted(classes.items())),
        representative_hex={
            "ERR_DUPLICATE_KEY": b'{"a":1,"a"\n'.hex(),
            "ERR_EMPTY_INPUT": b"\n".hex(),
            "ERR_JSON": b"}\n".hex(),
            "ERR_NFC": '"e\u0301"\n'.encode("utf-8").hex(),
            "ERR_UTF8": b"\xff\n".hex(),
            "PARSE_OK": b"1\n".hex(),
        },
        quotient_material_sha256=material_hasher.hexdigest().upper(),
    )


def replay_tokens(tokens: Iterable[Token], framed_lf: bool) -> str:
    state = INITIAL_STATE
    for token in tokens:
        if token.symbol == "LF":
            raise ValueError("pass framed_lf=True instead of including LF")
        nxt = transition(state, token)
        if nxt is None:
            raise ValueError("trace is outside M")
        state = nxt
    return terminal_class(state, framed_lf)
