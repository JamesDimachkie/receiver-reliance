"""Grounded 0.4 layer: library API + audited decisions over the frozen engine.

Fixes, additively (zero sealed 0.2/0.3 bytes change), the external review's
confirmed defect classes:

  F3  Ordinary decision receipts do not bind the decision input.
      -> decide_audited() emits an audit extension sealing
         request_raw_sha256 + decision_input_sha256 + the sealed response's
         receipt into one self-zero-sealed object. Materially different
         fact profiles can no longer share an audit seal.
  F5  Semantic failures are poorly auditable (trace computed then dropped).
      -> the audit extension carries the per-class fired map, the matched
         predicate's minimal witness trace (operators + resolved pointers),
         and derived record references.
  F2  (sharpest instances) OBL-30 accepts caller bookkeeping that
      contradicts the caller's own supplied facts.
      -> closures_0_4.json adds tighten-only closure predicates evaluated
         AFTER the frozen table: a closure can turn VALID into a defect
         class, never the reverse. The frozen sealed response is preserved
         verbatim; the 0.4 surface's verdict is `audited_behavior_class`.

The frozen engine remains the single classification authority for the 0.2/0.3
surface: the sealed response embedded in every audited result is byte-identical
to what the frozen runner emits.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

_HERE = pathlib.Path(__file__).resolve().parent
_IMPL3 = _HERE.parent / "baseline-run" / "implementation-output-0.3"
if str(_IMPL3) not in sys.path:
    sys.path.insert(0, str(_IMPL3))

import b1_capabilities as b1  # noqa: E402
import pcb_runner  # noqa: E402

AUDIT_FORMAT = "B1-AUDITED-DECISION-0.4"

with open(_HERE / "closures_0_4.json", encoding="utf-8") as _fh:
    _CLOSURES: dict[str, list[dict]] = json.load(_fh)["closures_by_obligation"]

_CLASS_ORDER = ("MALFORMED_OR_BOUNDARY", "BINDING_OR_CONFLICT", "OMISSION_OR_INCOMPLETE")


def decide(request: dict[str, Any] | bytes) -> tuple[dict[str, Any], int]:
    """Run one request through the frozen engine in-process.

    Accepts a request object or exact wire bytes; returns (response, exit_code)
    with the response byte-identical (via JCS) to the frozen stdio runner's.
    """
    raw = request if isinstance(request, bytes) else b1.jcs_bytes(request) + b"\n"
    return pcb_runner._execute(raw)


# --- closure-predicate evaluation (0.4 additions to the frozen DSL) --------


def _jcs_set(items: list[Any]) -> set[bytes]:
    return {b1.jcs_bytes(item) for item in items}


def _eval_closure_atomic(node: dict[str, Any], doc: Any) -> bool:
    op = node["op"]
    get = lambda path: b1.resolve_input_pointer(doc, path)
    if op == "PROJECTION_NE":
        # {rows_path, key, flag, flag_value, set_path}: true when the set of
        # row[key] for rows whose row[flag] == flag_value differs from the
        # set at set_path — i.e. a supplied projection contradicts the rows
        # it claims to project.
        rows = get(node["rows_path"])
        projected = {
            b1.jcs_bytes(row[node["key"]])
            for row in rows
            if b1._strict_equal(row[node["flag"]], node["flag_value"])
        }
        return projected != _jcs_set(get(node["set_path"]))
    if op == "DERIVED_DIFF_NE":
        # {base_path, subtract_paths, equals_path}: true when
        # set(base) - union(subtractions) differs from the supplied set at
        # equals_path — i.e. supplied bookkeeping contradicts its derivation.
        derived = _jcs_set(get(node["base_path"]))
        for path in node["subtract_paths"]:
            derived -= _jcs_set(get(path))
        return derived != _jcs_set(get(node["equals_path"]))
    # Fall through to the frozen evaluator for every accepted operator, so
    # closures may reuse the frozen vocabulary.
    return b1._eval_atomic(node, doc)


def _eval_closure(node: dict[str, Any], doc: Any) -> bool:
    if "all" in node:
        return all(_eval_closure(child, doc) for child in node["all"])
    if "any" in node:
        return any(_eval_closure(child, doc) for child in node["any"])
    if "not" in node:
        return not _eval_closure(node["not"], doc)
    return _eval_closure_atomic(node, doc)


def closure_findings(obligation_id: str, decision_input: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    for row in _CLOSURES.get(obligation_id, []):
        try:
            fired = _eval_closure(row["predicate"], decision_input)
        except (b1.EvaluatorError, KeyError, TypeError) as err:
            fired = False
            findings.append(
                {"closure_id": row["closure_id"], "fired": False, "evaluator_error": str(err)[:200]}
            )
            continue
        if fired:
            findings.append(
                {
                    "closure_id": row["closure_id"],
                    "fired": True,
                    "tightens_to": row["tightens_to"],
                    "statement": row["statement"],
                }
            )
    return findings


# --- witness tracing over the frozen predicate table -----------------------


def _trace(node: dict[str, Any], doc: Any, out: list[dict[str, Any]]) -> bool:
    """Evaluate exactly like the frozen eval_predicate while recording the
    minimal witness: for `any`, the first true child's atoms; for `all`, every
    child's; for `not`, the child's. Truth values match b1.eval_predicate by
    construction (same operators, same order, same short-circuiting)."""
    if "all" in node:
        collected: list[dict[str, Any]] = []
        for child in node["all"]:
            if not _trace(child, doc, collected):
                return False
        out.extend(collected)
        return True
    if "any" in node:
        for child in node["any"]:
            branch: list[dict[str, Any]] = []
            if _trace(child, doc, branch):
                out.extend(branch)
                return True
        return False
    if "not" in node:
        branch: list[dict[str, Any]] = []
        result = not _trace(node["not"], doc, branch)
        if result:
            out.append({"op": "not", "of": node["not"].get("op", "compound")})
        return result
    fired = b1._eval_atomic(node, doc)
    if fired:
        pointers = sorted(
            {
                value
                for key, value in node.items()
                if isinstance(value, str) and value.startswith("/")
            }
            | {
                item
                for key, value in node.items()
                if isinstance(value, list)
                for item in value
                if isinstance(item, str) and item.startswith("/")
            }
        )
        out.append({"op": node["op"], "pointers": pointers})
    return fired


def derive_record_references(facts: Any, prefix: str = "") -> list[str]:
    """Deterministic extraction of record identifiers actually present in the
    fact profile: string leaves whose key names a record id (contains
    'record_id' or is 'exact_reference'), and string items of arrays whose
    key ends with '_record_ids'. Sorted, deduplicated, capped at 64."""
    found: set[str] = set()

    def walk(node: Any, key: str) -> None:
        if isinstance(node, dict):
            for child_key, child in node.items():
                walk(child, child_key)
        elif isinstance(node, list):
            if key.endswith("_record_ids") or key == "pool_record_ids":
                found.update(x for x in node if isinstance(x, str))
            else:
                for item in node:
                    walk(item, key)
        elif isinstance(node, str):
            if "record_id" in key or key == "exact_reference":
                found.add(node)

    walk(facts, "")
    return sorted(found)[:64]


def decide_audited(request: dict[str, Any] | bytes) -> dict[str, Any]:
    """Frozen decision + input-bound, trace-carrying audit extension."""
    raw = request if isinstance(request, bytes) else b1.jcs_bytes(request) + b"\n"
    response, exit_code = pcb_runner._execute(raw)
    audited: dict[str, Any] = {
        "format_version": AUDIT_FORMAT,
        "sealed_response": response,
        "exit_code": exit_code,
        "audit": None,
        "audited_behavior_class": None,
        "audit_sha256": b1.ZERO64,
    }
    audit: dict[str, Any] = {
        "request_raw_sha256": b1.sha256_upper(raw),
        "engine_generation": "composed-0.3-frozen",
    }
    if response.get("ok"):
        parsed = json.loads(raw.decode("utf-8"))
        semantic = parsed["semantic_request"] if "semantic_request" in parsed else parsed
        decision_input = semantic["decision_input"]
        obligation_id = semantic["obligation_id"]
        operation_handle = semantic["operation_handle"]
        audit["decision_input_sha256"] = b1.sha256_upper(b1.jcs_bytes(decision_input))
        behavior, fired_map = b1.classify(operation_handle, decision_input)
        output = response.get("output") or {}
        sealed_class = (
            (output.get("result_object") or {}).get("behavior_class")
            or (output.get("payload") or {}).get("behavior_class")
        )
        if behavior != sealed_class:  # defense in depth; must never happen
            raise RuntimeError("trace classification diverged from sealed response")
        witness: list[dict[str, Any]] = []
        if behavior != "VALID":
            _trace(b1.decision_table()[operation_handle][behavior], decision_input, witness)
        audit["first_match_predicates"] = fired_map
        audit["matched_class_witness"] = witness
        audit["record_references"] = derive_record_references(decision_input.get("facts"))
        findings = closure_findings(obligation_id, decision_input)
        audit["closure_findings"] = findings
        tightened = [f["tightens_to"] for f in findings if f.get("fired")]
        if behavior == "VALID" and tightened:
            final = min(tightened, key=_CLASS_ORDER.index)
        else:
            final = behavior
        audited["audited_behavior_class"] = final
    else:
        audit["decision_input_sha256"] = None
        audit["errors"] = response.get("errors")
        audited["audited_behavior_class"] = "PROTOCOL_ERROR"
    audited["audit"] = audit
    audited["audit_sha256"] = b1.self_zero_sha256(audited, "audit_sha256")
    return audited
