"""Structural analysis of frozen predicate trees.

A predicate is exactly one object containing one of ``all`` / ``any`` / ``not``
/ ``op`` (contract: ``predicate_language.node_forms``).  This module walks that
structure without interpreting any operator: it recovers the disjunct
decomposition, the RFC 6901 pointers a node reads (its *support*), and the
literals a node mentions.

Path detection is structural, not a transcribed per-operator table: in this
contract every pointer is an RFC 6901 pointer into ``decision_input`` and every
literal is a JSON value that is not a pointer.  ``pointer_literal_ambiguity``
turns that into a machine-checked invariant instead of an assumption.
"""

from __future__ import annotations

from typing import Any, Iterator

COMBINATORS = ("all", "any", "not")

# Keys whose value is a list of RFC 6901 pointers.
PATH_LIST_KEYS = ("paths", "subtract_paths")
# Keys whose value is a list of JSON literals.
LITERAL_LIST_KEYS = ("values",)
# Keys naming a member *inside* an object item (not a pointer into the input).
OBJECT_FIELD_KEYS = ("key", "from", "to", "start", "end", "flag")


def is_atom(node: dict[str, Any]) -> bool:
    return "op" in node


def children(node: dict[str, Any]) -> list[dict[str, Any]]:
    if "all" in node:
        return list(node["all"])
    if "any" in node:
        return list(node["any"])
    if "not" in node:
        return [node["not"]]
    return []


def walk(node: dict[str, Any], trail: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
    yield trail or ".", node
    if "all" in node:
        for i, c in enumerate(node["all"]):
            yield from walk(c, f"{trail}all[{i}]")
    elif "any" in node:
        for i, c in enumerate(node["any"]):
            yield from walk(c, f"{trail}any[{i}]")
    elif "not" in node:
        yield from walk(node["not"], f"{trail}not")


def atoms(node: dict[str, Any]) -> list[dict[str, Any]]:
    return [n for _, n in walk(node) if is_atom(n)]


def disjuncts(node: dict[str, Any], trail: str = "") -> list[tuple[str, dict[str, Any]]]:
    """Top-level alternatives, flattening nested ``any`` nodes.

    A class predicate that is a single conjunction or a single atom yields
    exactly one disjunct: the row itself.  A row of the form ``{"any": [...]}``
    yields one entry per alternative, recursively through nested ``any``.
    """
    if "any" in node:
        out: list[tuple[str, dict[str, Any]]] = []
        for i, child in enumerate(node["any"]):
            out.extend(disjuncts(child, f"{trail}any[{i}]."))
        return out
    return [(trail.rstrip(".") or "<row>", node)]


def _is_pointer(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("/")


def node_pointers(node: dict[str, Any]) -> set[str]:
    """RFC 6901 pointers read by ONE atomic node."""
    out: set[str] = set()
    if not is_atom(node):
        return out
    for key, value in node.items():
        if key == "op":
            continue
        if key in PATH_LIST_KEYS:
            out.update(v for v in value if _is_pointer(v))
        elif key in LITERAL_LIST_KEYS:
            continue
        elif _is_pointer(value):
            out.add(value)
    return out


def pointers(node: dict[str, Any]) -> set[str]:
    """Every pointer read anywhere beneath ``node``."""
    out: set[str] = set()
    for _, n in walk(node):
        out |= node_pointers(n)
    return out


def literals(node: dict[str, Any]) -> list[Any]:
    """Every JSON literal mentioned anywhere beneath ``node``."""
    out: list[Any] = []
    for _, n in walk(node):
        if not is_atom(n):
            continue
        for key, value in n.items():
            if key == "op" or key in PATH_LIST_KEYS or key in OBJECT_FIELD_KEYS:
                continue
            if key in LITERAL_LIST_KEYS:
                out.extend(value)
            elif not _is_pointer(value):
                out.append(value)
    return out


def object_member_names(node: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for _, n in walk(node):
        if not is_atom(n):
            continue
        for key in OBJECT_FIELD_KEYS:
            if key in n and isinstance(n[key], str):
                out.add(n[key])
        # NOT_FUNCTIONAL_BY uses `value` as an object member name.
        if n["op"] == "NOT_FUNCTIONAL_BY" and isinstance(n.get("value"), str):
            out.add(n["value"])
    return out


def support_fields(node: dict[str, Any], facts_prefix: str = "/facts/") -> set[str]:
    """Top-level ``facts`` members the node reads."""
    out = set()
    for ptr in pointers(node):
        if ptr.startswith(facts_prefix):
            out.add(ptr[len(facts_prefix) :].split("/")[0])
    return out


def pointer_literal_ambiguity(node: dict[str, Any]) -> list[dict[str, Any]]:
    """Any place where the structural pointer/literal split could be wrong.

    Two failure shapes are reported:
      * a string *literal* that begins with ``/`` (would be misread as a path);
      * a *pointer* that does not begin with ``/facts/`` (outside the modelled
        fact document, so the support analysis would be incomplete).
    An empty list means the structural rule is exact for this predicate.
    """
    problems: list[dict[str, Any]] = []
    for trail, n in walk(node):
        if not is_atom(n):
            continue
        for ptr in node_pointers(n):
            if not ptr.startswith("/facts/"):
                problems.append({"trail": trail, "op": n["op"], "pointer": ptr, "why": "pointer outside /facts/"})
        for key, value in n.items():
            if key == "op" or key in PATH_LIST_KEYS or key in OBJECT_FIELD_KEYS:
                continue
            vals = value if key in LITERAL_LIST_KEYS else [value]
            if key == "value" and n["op"] == "NOT_FUNCTIONAL_BY":
                continue
            for v in vals:
                if isinstance(v, str) and v.startswith("/") and key in LITERAL_LIST_KEYS:
                    problems.append(
                        {"trail": trail, "op": n["op"], "key": key, "why": "literal looks like a pointer"}
                    )
    return problems
