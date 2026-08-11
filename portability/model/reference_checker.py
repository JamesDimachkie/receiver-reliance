"""Retained-state reference for checking the streaming parser explorer.

This checker intentionally keeps every reachable state and its multiplicity
until completion.  It is too memory-heavy for the full N=48 run and is not the
production enumeration path; its purpose is to falsify layer-release errors at
smaller bounds with a separately structured reachability store.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib

from .domain import LF_TOKEN, MAX_REQUEST_BYTES, NON_LF_TOKENS
from .parser_model import (
    INITIAL_STATE,
    ParseExploration,
    ParseState,
    pack_state,
    terminal_class,
    transition,
)


def explore_parser_retained(max_request_bytes: int) -> ParseExploration:
    """Enumerate a bounded prefix lattice without releasing old layers."""
    if not 0 <= max_request_bytes <= MAX_REQUEST_BYTES:
        raise ValueError(f"max_request_bytes must be in [0, {MAX_REQUEST_BYTES}]")

    all_ways: dict[ParseState, int] = {INITIAL_STATE: 1}
    states_at_length: list[set[ParseState]] = [set() for _ in range(max_request_bytes + 1)]
    states_at_length[0].add(INITIAL_STATE)
    transitions = 0
    terminal_transitions = 0
    excluded_edges = 0
    excluded_trace_prefixes = 0
    classes: dict[str, dict[str, int]] = defaultdict(
        lambda: {"quotient_terminals": 0, "symbolic_traces": 0}
    )

    for length, layer_states in enumerate(states_at_length):
        packed_order = {pack_state(state): state for state in layer_states}
        if len(packed_order) != len(layer_states):
            raise AssertionError("packed parser state collision")
        for state in (packed_order[key] for key in sorted(packed_order)):
            state_ways = all_ways[state]
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
                if nxt.byte_length <= state.byte_length:
                    raise AssertionError("parser transition did not strictly increase byte_length")
                transitions += 1
                all_ways[nxt] = all_ways.get(nxt, 0) + state_ways
                states_at_length[nxt.byte_length].add(nxt)

    material_hasher = hashlib.sha256()
    for length_states in states_at_length:
        packed_order = {pack_state(state): state for state in length_states}
        if len(packed_order) != len(length_states):
            raise AssertionError("packed parser state collision")
        for state in (packed_order[key] for key in sorted(packed_order)):
            material_hasher.update(repr(state).encode("utf-8"))
            material_hasher.update(b"\n")

    return ParseExploration(
        states=len(all_ways),
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
