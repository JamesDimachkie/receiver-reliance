"""Pure candidate workloads; no model, runtime, treatment, host, or I/O dependencies.

Tasks: ``sum`` and ``selection``. Topologies: ``direct``, ``chain``, ``fork``.
Domains: ``development`` and ``evaluation``; indices are exactly 0..255.
``truth`` and ``parse_answer`` return a record: {"answer": int | list[str]}.
``canonical_encode`` encodes that record as canonical UTF-8 bytes, without LF.
``nodes`` returns fresh topologically ordered plan records. The source ID is
``SOURCE``; receiver_messages takes a plan's string ``id`` and a dictionary
mapping precisely its declared parent IDs to actual bytes/text or parsed records.

This is workload development, not a freeze, qualified instrument or study result.
Strict parsing validates an ID's grammar, not membership/eligibility in a world;
an otherwise well-formed wrong answer remains a semantic error for the oracle.
"""
from __future__ import annotations

import hashlib
import json
import re


TASKS = ("sum", "selection")
TOPOLOGIES = ("direct", "chain", "fork")
DOMAINS = ("development", "evaluation")
GROUPS = ("A", "B", "C", "D")
SCHEMA = "RR_BENIGN_WORKLOAD_CANDIDATE_V1"
MAX_ANSWER_BYTES = 8192
_ITEM_ID = re.compile(r"[ABCD]0[1-5]\Z", flags=re.ASCII)


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


class _Stream:
    """Version-independent SHA-256 counter stream; never global random state."""

    def __init__(self, seed: bytes):
        self.seed = seed
        self.counter = 0

    def below(self, stop: int) -> int:
        if type(stop) is not int or stop <= 0 or stop > (1 << 256):
            raise ValueError("Invalid stream bound")
        space = 1 << 256
        limit = space - space % stop
        while True:
            block = hashlib.sha256(
                self.seed + self.counter.to_bytes(16, "big")).digest()
            self.counter += 1
            value = int.from_bytes(block, "big")
            if value < limit:
                return value % stop


def _dimensions(task: str, topology: str, index: int, domain: str) -> None:
    if task not in TASKS or topology not in TOPOLOGIES or domain not in DOMAINS:
        raise ValueError("Unknown task, topology, or domain")
    if type(index) is not int or not 0 <= index < 256:
        raise ValueError("World index must be an integer in 0..255")


def make_world(task: str, topology: str, index: int, domain: str) -> dict:
    """Derive every original group from an explicitly domain-separated stream."""
    _dimensions(task, topology, index, domain)
    seed = hashlib.sha256(_json_bytes(
        [SCHEMA, domain, task, topology, index])).digest()
    stream = _Stream(seed)
    groups = {}
    for group in GROUPS:
        count = 3 + stream.below(3)
        if task == "sum":
            groups[group] = [1 + stream.below(40) for _ in range(count)]
        else:
            groups[group] = [
                {"id": f"{group}{i + 1:02d}",
                 "grade": ("A", "B", "C")[stream.below(3)],
                 "count": 1 + stream.below(7)}
                for i in range(count)
            ]
    return {"schema": SCHEMA, "task": task, "topology": topology,
            "index": index, "domain": domain, "groups": groups}


def _validate_world(world: dict) -> None:
    expected = {"schema", "task", "topology", "index", "domain", "groups"}
    if type(world) is not dict or set(world) != expected or world["schema"] != SCHEMA:
        raise ValueError("Invalid world record")
    _dimensions(world["task"], world["topology"], world["index"], world["domain"])
    groups = world["groups"]
    if type(groups) is not dict or set(groups) != set(GROUPS):
        raise ValueError("Exactly groups A/B/C/D are required")
    for group in GROUPS:
        records = groups[group]
        if type(records) is not list or not 3 <= len(records) <= 5:
            raise ValueError("Each original group needs 3..5 entries")
        if world["task"] == "sum":
            if any(type(value) is not int or not 1 <= value <= 40 for value in records):
                raise ValueError("Original summands must be integers in 1..40")
        else:
            for i, record in enumerate(records):
                if type(record) is not dict or set(record) != {"id", "grade", "count"}:
                    raise ValueError("Invalid item record")
                if record["id"] != f"{group}{i + 1:02d}" or record["grade"] not in ("A", "B", "C"):
                    raise ValueError("Invalid item ID or grade")
                if type(record["count"]) is not int or not 1 <= record["count"] <= 7:
                    raise ValueError("Item count must be an integer in 1..7")


def _answer_record(record: dict, task: str) -> dict:
    if task not in TASKS or type(record) is not dict or set(record) != {"answer"}:
        raise ValueError("Exactly one answer field and a known task are required")
    answer = record["answer"]
    if task == "sum":
        if type(answer) is not int:
            raise ValueError("Sum answer must be an integer, never bool or float")
        return {"answer": answer}
    if type(answer) is not list or any(
            type(item) is not str or _ITEM_ID.fullmatch(item) is None for item in answer):
        raise ValueError("Selection answer must be a list of IDs A01..D05")
    if answer != sorted(set(answer)):
        raise ValueError("Selection IDs must already be sorted and unique")
    return {"answer": list(answer)}


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    record = {}
    for key, value in pairs:
        if key in record:
            raise ValueError("Duplicate JSON key")
        record[key] = value
    return record


def _reject_number(token: str) -> None:
    raise ValueError("Only integer JSON numbers are permitted")


def parse_answer(text: str | bytes, task: str) -> dict:
    """Strict JSON parsing; no fences, extraction, repairs, coercion or sorting.

    Ordinary JSON surrounding whitespace is accepted. Floats, nonfinite numbers,
    duplicate keys (including escaped duplicates), extras, bools and bad ID syntax
    fail. Negative integer sums remain well-formed but generally incorrect.
    """
    if type(text) is bytes:
        if len(text) > MAX_ANSWER_BYTES:
            raise ValueError("Answer is too long")
        try:
            text = text.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ValueError("Answer is not UTF-8") from error
    if type(text) is not str:
        raise ValueError("Answer must be text or bytes")
    try:
        if len(text.encode("utf-8", errors="strict")) > MAX_ANSWER_BYTES:
            raise ValueError("Answer is too long")
    except UnicodeEncodeError as error:
        raise ValueError("Answer contains invalid Unicode") from error
    try:
        record = json.loads(text, object_pairs_hook=_unique_object,
                            parse_float=_reject_number, parse_constant=_reject_number)
    except (json.JSONDecodeError, RecursionError) as error:
        raise ValueError("Answer is not one valid JSON record") from error
    return _answer_record(record, task)


def canonical_encode(record: dict, task: str) -> bytes:
    """Canonical exact answer bytes; a parsed valid record is required."""
    encoded = _json_bytes(_answer_record(record, task))
    if len(encoded) > MAX_ANSWER_BYTES:
        raise ValueError("Answer is too long")
    return encoded


def nodes(world: dict) -> list[dict]:
    """Fresh receiver plans in execution order; parent order is normative."""
    _validate_world(world)
    if world["topology"] == "direct":
        return [{"id": "R1", "parents": ["SOURCE"], "groups": ["B", "C", "D"], "combine": "extend"}]
    if world["topology"] == "chain":
        return [{"id": "R1", "parents": ["SOURCE"], "groups": ["B"], "combine": "extend"},
                {"id": "R2", "parents": ["R1"], "groups": ["C"], "combine": "extend"},
                {"id": "R3", "parents": ["R2"], "groups": ["D"], "combine": "extend"}]
    return [{"id": "R1", "parents": ["SOURCE"], "groups": ["B"], "combine": "extend"},
            {"id": "R2", "parents": ["R1"], "groups": ["C"], "combine": "extend"},
            {"id": "R3", "parents": ["R1"], "groups": ["D"], "combine": "extend"},
            {"id": "R4", "parents": ["R2", "R3", "R1"], "groups": [], "combine": "join"}]


def _plan(world: dict, node: str) -> dict:
    for plan in nodes(world):
        if plan["id"] == node:
            return plan
    raise ValueError("Unknown receiver node")


def source_messages(world: dict) -> list[dict[str, str]]:
    """The source sees group A only; no world identity, answer or later group."""
    _validate_world(world)
    if world["task"] == "sum":
        instruction = 'Add all integers in group A. Return only {"answer":INTEGER}, without explanation.'
    else:
        instruction = ('Select IDs from group A with grade exactly "A" and count >= 4. '
                       'Return only {"answer":[IDs]}, sorted lexicographically and unique, without explanation.')
    return [{"role": "system", "content": instruction},
            {"role": "user", "content": _json_bytes({"groups": {"A": world["groups"]["A"]}}).decode("utf-8")}]


def _parent_text(value: bytes | str | dict, task: str) -> str:
    if type(value) is dict:
        return canonical_encode(value, task).decode("utf-8")
    parse_answer(value, task)
    return value.decode("utf-8") if type(value) is bytes else value


def receiver_messages(world: dict, node: str, parents: dict) -> list[dict[str, str]]:
    """Use every declared actual parent payload plus this node's increments only.

    Raw valid UTF-8 parent bytes/text retain their exact text, including whitespace.
    Parsed-record inputs use their canonical bytes. No reference truth is consulted.
    """
    plan = _plan(world, node)
    if type(parents) is not dict or set(parents) != set(plan["parents"]):
        raise ValueError("Supply exactly this node's declared parent payloads")
    payloads = [{"id": parent, "payload": _parent_text(parents[parent], world["task"])}
                for parent in plan["parents"]]
    if world["task"] == "sum":
        operation = ('Compute R2.answer + R3.answer - R1.answer. R1 is the shared subtotal. '
                     if plan["combine"] == "join" else
                     "Compute one total: the single parent's integer answer, counted exactly once, "
                     "plus the sum of all integers in all supplied groups. ")
        instruction = operation + 'Return only {"answer":INTEGER}, without explanation.'
    else:
        operation = ('Take the set union of the R2 and R3 answer lists. R1 is supplied as their shared ancestor; '
                     'do not add any extra IDs from R1. ' if plan["combine"] == "join" else
                     'Compute the set union of (1) all IDs already in the single parent\'s answer list '
                     'and (2) IDs from the supplied groups whose grade is exactly "A" and count >= 4. '
                     'Keep every parent ID; do not re-filter parent IDs using the new groups. ')
        instruction = operation + 'Return only {"answer":[IDs]}, sorted lexicographically and unique, without explanation.'
    content = {"parents": payloads, "groups": {group: world["groups"][group] for group in plan["groups"]}}
    return [{"role": "system", "content": instruction},
            {"role": "user", "content": _json_bytes(content).decode("utf-8")}]


def truth(world: dict, node: str = "final") -> dict:
    """Oracle over original groups, independent of parent answers and traversal.

    ``source``/``SOURCE`` names group A. ``final`` names the topology's final
    receiver. This routine does not call nodes, prompts, parsing or encoding.
    """
    _validate_world(world)
    coverage = {
        "direct": {"R1": "ABCD", "final": "ABCD"},
        "chain": {"R1": "AB", "R2": "ABC", "R3": "ABCD", "final": "ABCD"},
        "fork": {"R1": "AB", "R2": "ABC", "R3": "ABD", "R4": "ABCD", "final": "ABCD"},
    }
    if node in ("source", "SOURCE"):
        selected_groups = "A"
    else:
        selected_groups = coverage[world["topology"]].get(node)
        if selected_groups is None:
            raise ValueError("Unknown truth node")
    if world["task"] == "sum":
        total = 0
        for group in selected_groups:
            for value in world["groups"][group]:
                total += value
        return {"answer": total}
    ids = []
    for group in selected_groups:
        for item in world["groups"][group]:
            if item["grade"] == "A" and item["count"] >= 4:
                ids.append(item["id"])
    return {"answer": sorted(ids)}


def self_check() -> dict:
    """Pure exhaustive reservoir/reference checks; no inference or file writes."""
    world_count = receiver_count = parse_checks = 0
    fingerprints = {}
    for task in TASKS:
        for topology in TOPOLOGIES:
            for domain in DOMAINS:
                seen = set()
                for index in range(256):
                    world = make_world(task, topology, index, domain)
                    assert world == make_world(task, topology, index, domain)
                    _validate_world(world)
                    fingerprint = hashlib.sha256(_json_bytes(world["groups"])).hexdigest()
                    assert fingerprint not in seen
                    seen.add(fingerprint)
                    source = source_messages(world)
                    assert json.loads(source[1]["content"]) == {"groups": {"A": world["groups"]["A"]}}
                    if task == "sum":
                        source_value = sum(world["groups"]["A"])
                    else:
                        source_value = sorted(item["id"] for item in world["groups"]["A"]
                                              if item["grade"] == "A" and item["count"] >= 4)
                    payloads = {"SOURCE": canonical_encode({"answer": source_value}, task)}
                    assert parse_answer(payloads["SOURCE"], task) == truth(world, "SOURCE")
                    for plan in nodes(world):
                        actual = {parent: payloads[parent] for parent in plan["parents"]}
                        messages = receiver_messages(world, plan["id"], actual)
                        projection = json.loads(messages[1]["content"])
                        assert projection["parents"] == [{"id": parent, "payload": actual[parent].decode("utf-8")}
                                                         for parent in plan["parents"]]
                        assert projection["groups"] == {group: world["groups"][group] for group in plan["groups"]}
                        previous = {parent: parse_answer(value, task)["answer"] for parent, value in actual.items()}
                        if task == "sum":
                            if plan["combine"] == "join":
                                value = previous["R2"] + previous["R3"] - previous["R1"]
                            else:
                                value = sum(previous.values()) + sum(sum(world["groups"][group]) for group in plan["groups"])
                        else:
                            chosen = ("R2", "R3") if plan["combine"] == "join" else tuple(previous)
                            selected = set(item_id for parent in chosen for item_id in previous[parent])
                            for group in plan["groups"]:
                                selected.update(item["id"] for item in world["groups"][group]
                                                if item["grade"] == "A" and item["count"] >= 4)
                            value = sorted(selected)
                        payloads[plan["id"]] = canonical_encode({"answer": value}, task)
                        assert parse_answer(payloads[plan["id"]], task) == truth(world, plan["id"])
                        receiver_count += 1
                    assert parse_answer(payloads[nodes(world)[-1]["id"]], task) == truth(world)
                    world_count += 1
                fingerprints[(task, topology, domain)] = seen
            assert fingerprints[(task, topology, "development")].isdisjoint(
                fingerprints[(task, topology, "evaluation")])

    bad_cases = [
        ("sum", '{"answer":true}'), ("sum", '{"answer":1.0}'),
        ("sum", '{"answer":1e0}'), ("sum", '{"answer":NaN}'),
        ("sum", '{"answer":Infinity}'), ("sum", '{"answer":"1"}'),
        ("sum", '{"answer":1,"answer":2}'), ("sum", '{"answer":1,"\\u0061nswer":2}'),
        ("sum", '{"answer":1,"rationale":"ok"}'), ("sum", '{}'),
        ("sum", '[1]'), ("sum", '1'), ("sum", '```json\n{"answer":1}\n```'),
        ("sum", '{"answer":1} trailing'), ("sum", '{"answer":1}{"answer":2}'),
        ("sum", '{"answer":01}'), ("sum", '{"answer":+1}'),
        ("sum", b'\xff'), ("sum", b'\xef\xbb\xbf{"answer":1}'),
        ("selection", '{"answer":["A00"]}'), ("selection", '{"answer":["E01"]}'),
        ("selection", '{"answer":["A06"]}'), ("selection", '{"answer":["a01"]}'),
        ("selection", '{"answer":["A01 "]}'), ("selection", '{"answer":[1]}'),
        ("selection", '{"answer":[true]}'), ("selection", '{"answer":["B01","A01"]}'),
        ("selection", '{"answer":["A01","A01"]}'), ("selection", '{"answer":null}'),
    ]
    for task, text in bad_cases:
        try:
            parse_answer(text, task)
        except ValueError:
            parse_checks += 1
        else:
            raise AssertionError(f"Invalid answer was accepted: {text!r}")
    assert parse_answer(' \n{"answer":-7}\t', "sum") == {"answer": -7}
    assert parse_answer('{"answer":[]}', "selection") == {"answer": []}
    assert parse_answer('{"answer":["A01","D05"]}', "selection") == {"answer": ["A01", "D05"]}

    world = make_world("sum", "fork", 0, "development")
    originals = {"R2": b' { "answer" : 11 }\n', "R3": b'{"answer":13}', "R1": b'{"answer":-7}'}
    prompt = json.loads(receiver_messages(world, "R4", originals)[1]["content"])
    assert [entry["id"] for entry in prompt["parents"]] == ["R2", "R3", "R1"]
    assert all(entry["payload"].encode("utf-8") == originals[entry["id"]] for entry in prompt["parents"])
    assert prompt["groups"] == {}
    assert truth(world) == truth(make_world("sum", "fork", 0, "development"))
    for index in (-1, 256, True, 0.0):
        try:
            make_world("sum", "direct", index, "development")
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid reservoir index was accepted")
    return {"worlds_checked": world_count, "reference_receiver_traversals": receiver_count,
            "parse_rejections": parse_checks, "reservoir_size_per_cell": 256,
            "domains_content_disjoint": True, "actual_three_parent_bytes_preserved": True,
            "model_calls": 0, "status": "PURE_SELF_CHECK_PASS"}


if __name__ == "__main__":
    print(json.dumps(self_check(), sort_keys=True))
