"""Bounded parse/batch transport product automaton for finite model M."""
from __future__ import annotations

import itertools
import math
import base64
import hashlib
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from .domain import MAX_CALLERS, MAX_CHUNK_SPLITS_COMPLETE, MAX_WRITE_SPLITS

RECORD_KINDS = ("VALID_CORE", "ERR_JSON", "OVERSIZE_DRAIN")


@dataclass(frozen=True, slots=True)
class RecordShape:
    name: str
    request_bytes: int
    response_bytes: int
    token_boundaries: tuple[int, ...]
    oversize_threshold: int | None = None
    request_sha256: str | None = None


_REPO = Path(__file__).resolve().parents[2]
_VALID_ENTRY_ID = "SEMFX-OBL-24-IO-9B6734B80BFFF9D7"


def _json_token_boundaries(raw: bytes) -> tuple[int, ...]:
    """Return starts/ends of every lexical token, plus the physical LF edge."""
    points = {0, len(raw)}
    limit = len(raw) - int(raw.endswith(b"\n"))
    i = 0
    punctuation = b"{}[]:,"
    delimiters = b"{}[]:,\r\n\t "
    while i < limit:
        if raw[i] in punctuation:
            points.update((i, i + 1))
            i += 1
        elif raw[i] == 0x22:
            start = i
            i += 1
            escaped = False
            while i < limit:
                byte = raw[i]
                i += 1
                if escaped:
                    escaped = False
                elif byte == 0x5C:
                    escaped = True
                elif byte == 0x22:
                    break
            points.update((start, i))
        elif raw[i] in b" \t\r\n":
            i += 1
        else:
            start = i
            while i < limit and raw[i] not in delimiters:
                i += 1
            points.update((start, i))
    if raw.endswith(b"\n"):
        points.update((len(raw) - 1, len(raw)))
    return tuple(sorted(points))


def _valid_core_shape() -> RecordShape:
    path = _REPO / "baseline-run" / "fixtures" / "PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json"
    pack = json.loads(path.read_text(encoding="utf-8"))
    entry = next(item for item in pack["entries"] if item["entry_id"] == _VALID_ENTRY_ID)
    raw = base64.b64decode(entry["semantic_request_jcs_lf_base64"], validate=True)
    return RecordShape(
        "VALID_CORE",
        len(raw),
        1082,
        _json_token_boundaries(raw),
        request_sha256=hashlib.sha256(raw).hexdigest().upper(),
    )


_ERR_JSON_RAW = b'{"a":}\n'
RECORD_SHAPES = {
    "VALID_CORE": _valid_core_shape(),
    "ERR_JSON": RecordShape(
        "ERR_JSON",
        len(_ERR_JSON_RAW),
        812,
        _json_token_boundaries(_ERR_JSON_RAW),
        request_sha256=hashlib.sha256(_ERR_JSON_RAW).hexdigest().upper(),
    ),
    # Threshold-relative quotient.  The real threshold is exercised by the
    # RO1/RO2 closure, not silently replaced by this compact representative.
    "OVERSIZE_DRAIN": RecordShape("OVERSIZE_DRAIN", 18, 840, (16, 17, 18), 16),
}


def split_partition_count(length: int, boundary_points: tuple[int, ...], max_splits: int) -> dict[str, int]:
    interior = max(0, length - 1)
    complete = sum(math.comb(interior, k) for k in range(max_splits + 1))
    adjacent: set[int] = set()
    for point in boundary_points:
        for candidate in (point - 1, point, point + 1):
            if 1 <= candidate < length:
                adjacent.add(candidate)
    size3 = math.comb(len(adjacent), 3) if len(adjacent) >= 3 else 0
    return {
        "length": length,
        "interior_points": interior,
        "sets_size_le_2": complete,
        "boundary_candidate_points": len(adjacent),
        "boundary_sets_size_3": size3,
        "total": complete + size3,
    }


@dataclass(frozen=True, slots=True)
class LocalState:
    record: int
    phase: str


PHASE_ORDER = {
    "READ": 0,
    "AFTER_READ": 1,
    "READ_PAUSED": 2,
    "READ_RESUMED": 3,
    "CLASSIFY": 4,
    "AFTER_CLASSIFY": 5,
    "WRITE_PAUSED": 6,
    "WRITE_RESUMED": 7,
    "WRITE": 8,
    "AFTER_WRITE": 9,
    "FLUSH_PAUSED": 10,
    "FLUSH_RESUMED": 11,
    "FLUSH": 12,
    "DONE": 13,
}


def local_edges(state: LocalState, requests: int) -> tuple[tuple[str, LocalState], ...]:
    record, phase = state.record, state.phase
    if phase == "DONE":
        return ()
    if phase == "READ":
        return (("read", LocalState(record, "AFTER_READ")),)
    if phase == "AFTER_READ":
        return (
            ("classify", LocalState(record, "CLASSIFY")),
            ("pause:after_read", LocalState(record, "READ_PAUSED")),
        )
    if phase == "READ_PAUSED":
        return (("resume:after_read", LocalState(record, "READ_RESUMED")),)
    if phase == "READ_RESUMED":
        return (("classify", LocalState(record, "CLASSIFY")),)
    if phase == "CLASSIFY":
        return (("classified", LocalState(record, "AFTER_CLASSIFY")),)
    if phase == "AFTER_CLASSIFY":
        return (
            ("write", LocalState(record, "WRITE")),
            ("pause:before_write", LocalState(record, "WRITE_PAUSED")),
        )
    if phase == "WRITE_PAUSED":
        return (("resume:before_write", LocalState(record, "WRITE_RESUMED")),)
    if phase == "WRITE_RESUMED":
        return (("write", LocalState(record, "WRITE")),)
    if phase == "WRITE":
        return (("written", LocalState(record, "AFTER_WRITE")),)
    if phase == "AFTER_WRITE":
        return (
            ("flush", LocalState(record, "FLUSH")),
            ("pause:before_flush", LocalState(record, "FLUSH_PAUSED")),
        )
    if phase == "FLUSH_PAUSED":
        return (("resume:before_flush", LocalState(record, "FLUSH_RESUMED")),)
    if phase == "FLUSH_RESUMED":
        return (("flush", LocalState(record, "FLUSH")),)
    if phase == "FLUSH":
        return ((
            "flushed",
            LocalState(record + 1, "DONE" if record + 1 == requests else "READ"),
        ),)
    raise AssertionError(phase)


ProductState = tuple[LocalState, ...]


@dataclass(slots=True)
class SchedulerExploration:
    callers: int
    requests: int
    states: int
    transitions: int
    terminal_states: int
    concrete_schedule_traces: int
    sequence_assignments: int
    terminal_sequence_schedule_cases: int


def _rank(state: ProductState) -> int:
    return sum(local.record * len(PHASE_ORDER) + PHASE_ORDER[local.phase] for local in state)


def explore_scheduler(callers: int, requests: int) -> SchedulerExploration:
    if not 1 <= callers <= MAX_CALLERS or not 1 <= requests <= 2:
        raise ValueError("complete scheduler domain is P<=2 and R<=2")
    initial = tuple(LocalState(0, "READ") for _ in range(callers))
    queue = deque([initial])
    states = {initial}
    graph: dict[ProductState, list[ProductState]] = defaultdict(list)
    transition_count = 0
    while queue:
        state = queue.popleft()
        for caller, local in enumerate(state):
            for _action, next_local in local_edges(local, requests):
                nxt = state[:caller] + (next_local,) + state[caller + 1 :]
                graph[state].append(nxt)
                transition_count += 1
                if nxt not in states:
                    states.add(nxt)
                    queue.append(nxt)
    ways: dict[ProductState, int] = {initial: 1}
    for state in sorted(states, key=_rank):
        for nxt in graph[state]:
            ways[nxt] = ways.get(nxt, 0) + ways[state]
    terminals = [state for state in states if all(local.phase == "DONE" for local in state)]
    traces = sum(ways[state] for state in terminals)
    assignments = len(RECORD_KINDS) ** (callers * requests)
    return SchedulerExploration(
        callers,
        requests,
        len(states),
        transition_count,
        len(terminals),
        traces,
        assignments,
        traces * assignments,
    )


def partition_receipt() -> dict[str, object]:
    request = {
        name: split_partition_count(shape.request_bytes, shape.token_boundaries, MAX_CHUNK_SPLITS_COMPLETE)
        for name, shape in RECORD_SHAPES.items()
    }
    response = {
        name: split_partition_count(shape.response_bytes, (), MAX_WRITE_SPLITS)
        for name, shape in RECORD_SHAPES.items()
    }
    identities = {
        name: {
            "request_bytes": shape.request_bytes,
            "response_bytes": shape.response_bytes,
            "request_sha256": shape.request_sha256,
            "token_boundary_points": len(shape.token_boundaries),
            "oversize_threshold": shape.oversize_threshold,
        }
        for name, shape in RECORD_SHAPES.items()
    }
    return {"record_identities": identities, "request_partitions_C": request, "response_partitions_W": response}


def materialize_r3_schedule(spec: dict[str, object], seed: str) -> dict[str, object]:
    """Replay one committed R=3 recipe to a deterministic concrete action list."""
    callers = int(spec["callers"])
    records = spec["records"]
    if callers != len(records) or any(len(stream) != 3 for stream in records):
        raise ValueError(f"invalid R=3 record shape: {spec['id']}")
    state: ProductState = tuple(LocalState(0, "READ") for _ in range(callers))
    actions: list[str] = []
    pause_sites = set(spec.get("pause_sites", []))
    serial_order = spec.get("serial_order")
    step = 0
    while not all(local.phase == "DONE" for local in state):
        enabled: list[tuple[int, str, LocalState]] = []
        for caller, local in enumerate(state):
            edges = local_edges(local, 3)
            if not edges:
                continue
            choices = [edge for edge in edges if not edge[0].startswith("pause:")]
            pause = [edge for edge in edges if edge[0] in pause_sites]
            chosen_edges = pause or choices
            for action, nxt in chosen_edges:
                enabled.append((caller, action, nxt))
        if serial_order:
            priority = next(c for c in serial_order if state[c].phase != "DONE")
            enabled = [item for item in enabled if item[0] == priority]
            chosen = enabled[0]
        else:
            material = f"{seed}|{spec['id']}|{step}|{state!r}".encode("utf-8")
            chosen = enabled[int.from_bytes(hashlib.sha256(material).digest()[:8], "big") % len(enabled)]
        caller, action, next_local = chosen
        actions.append(f"c{caller}:{action}:r{state[caller].record}")
        state = state[:caller] + (next_local,) + state[caller + 1 :]
        step += 1
        if step > 256:
            raise AssertionError("R=3 schedule failed to progress")
    raw = "\n".join(actions).encode("ascii")
    return {
        "id": spec["id"],
        "steps": len(actions),
        "action_sha256": hashlib.sha256(raw).hexdigest().upper(),
        "terminal": True,
    }


def all_record_sequences(requests: int) -> tuple[tuple[str, ...], ...]:
    return tuple(itertools.product(RECORD_KINDS, repeat=requests))
