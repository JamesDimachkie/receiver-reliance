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

The 0.4.1 audit format additionally binds the governing policy bytes: every
audited decision carries ``governing_authorities`` (closure-policy, authority-
register, and engine-source digests) inside the sealed audit, so decisions
produced under different policies are distinguishable by seal (ERRATA E8).
A closure evaluator error on a VALID decision yields ``AUDIT_INCOMPLETE``
instead of silently certifying VALID (ERRATA E9); sealed defect classes
stand, because closures only tighten. 0.4 audit objects remain verifiable
by self-zero recomputation under their own recorded format string.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

_HERE = pathlib.Path(__file__).resolve().parent
_IMPL3 = _HERE.parent / "baseline-run" / "implementation-output-0.3"
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_IMPL3) not in sys.path:
    sys.path.insert(0, str(_IMPL3))

from authority_surface import authority_for_operation  # noqa: E402,F401
import b1_capabilities as b1  # noqa: E402
import pcb_runner  # noqa: E402

AUDIT_FORMAT = "B1-AUDITED-DECISION-0.4.1"

with open(_HERE / "closures_0_4.json", encoding="utf-8") as _fh:
    _CLOSURES: dict[str, list[dict]] = json.load(_fh)["closures_by_obligation"]

# The exact bytes that govern every audited decision this process produces.
# Sealing these digests into each audit makes decisions produced under
# different closure policies, authority registers, or engine sources
# distinguishable by seal (ERRATA E8); the repository commit remains the
# trust root that authenticates the digests themselves (TRUST_MODEL.md).
GOVERNING_AUTHORITIES: dict[str, str] = {
    "closure_policy_sha256": b1.sha256_upper((_HERE / "closures_0_4.json").read_bytes()),
    "authority_register_sha256": b1.sha256_upper(
        (_HERE / "authority_register_0_4.json").read_bytes()
    ),
    "engine_capabilities_sha256": b1.sha256_upper(
        (_IMPL3 / "b1_capabilities.py").read_bytes()
    ),
    "engine_runner_sha256": b1.sha256_upper((_IMPL3 / "pcb_runner.py").read_bytes()),
}

_CLASS_ORDER = ("MALFORMED_OR_BOUNDARY", "BINDING_OR_CONFLICT", "OMISSION_OR_INCOMPLETE")


def conformance_execute(request: dict[str, Any] | bytes) -> tuple[dict[str, Any], int]:
    """CONFORMANCE-ONLY frozen-engine execution. Not an evidentiary surface.

    Accepts a request object or exact wire bytes; returns (response, exit_code)
    with the response byte-identical (via JCS) to the frozen stdio runner's.
    The sealed response binds no decision facts (ERRATA E2) and applies no
    0.4 closure (E5): use it to reproduce the frozen suites, never to decide.
    Every supported evidentiary decision goes through ``decide_audited``.
    Formerly exported as ``decide``; that supported route is withdrawn
    (deep-scan findings csf_abbd6848 / csf_0479d1a9, 2026-08-16).
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


def _classify_traced(
    operation_handle: str,
    decision_input: dict[str, Any],
    sealed_class: str,
) -> tuple[str, dict[str, bool], list[dict[str, Any]]]:
    """Classify once while retaining the selected predicate's witness.

    This mirrors ``b1.classify`` precedence and short-circuiting.  The frozen
    response's class identifies the one predicate that needs witness
    instrumentation; preceding predicates still run through the frozen
    evaluator, so an earlier match or a false sealed predicate is detected by
    the existing sealed-class cross-check.  The selected predicate is traced
    instead of first being classified and then evaluated a second time.
    """
    predicates = b1.decision_table()[operation_handle]
    first_match: dict[str, bool] = {}
    matched: str | None = None
    witness: list[dict[str, Any]] = []
    for class_name in _CLASS_ORDER:
        if matched is None:
            if class_name == sealed_class:
                branch: list[dict[str, Any]] = []
                fired = _trace(predicates[class_name], decision_input, branch)
            else:
                branch = []
                fired = b1.eval_predicate(predicates[class_name], decision_input)
            first_match[class_name] = fired
            if fired:
                matched = class_name
                if class_name == sealed_class:
                    witness = branch
        else:
            first_match[class_name] = False
    return matched or "VALID", first_match, witness


def _derive_record_references_full(facts: Any) -> tuple[list[str], bool]:
    """Return (capped references, truncated?) — GEN_0_5 §4.5 semantics.

    ``truncated`` is True exactly when the derived candidate set exceeded the
    64-item output cap, so the cap is disclosed instead of silent (Intake 10
    finding; the 0.5 continuation spec already pins this flag)."""
    refs = derive_record_references(facts)
    return refs, len(refs) == 64 and len(_collect_record_references(facts)) > 64


def _collect_record_references(facts: Any) -> set[str]:
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
    return found


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
        "governing_authorities": dict(GOVERNING_AUTHORITIES),
    }
    if response.get("ok"):
        parsed = json.loads(raw.decode("utf-8"))
        semantic = parsed["semantic_request"] if "semantic_request" in parsed else parsed
        decision_input = semantic["decision_input"]
        obligation_id = semantic["obligation_id"]
        operation_handle = semantic["operation_handle"]
        audit["decision_input_sha256"] = b1.sha256_upper(b1.jcs_bytes(decision_input))
        output = response.get("output") or {}
        sealed_class = (
            (output.get("result_object") or {}).get("behavior_class")
            or (output.get("payload") or {}).get("behavior_class")
        )
        behavior, fired_map, witness = _classify_traced(
            operation_handle, decision_input, sealed_class
        )
        if behavior != sealed_class:  # defense in depth; must never happen
            raise RuntimeError("trace classification diverged from sealed response")
        audit["first_match_predicates"] = fired_map
        audit["matched_class_witness"] = witness
        refs, refs_truncated = _derive_record_references_full(decision_input.get("facts"))
        audit["record_references"] = refs
        audit["record_references_truncated"] = refs_truncated
        findings = closure_findings(obligation_id, decision_input)
        audit["closure_findings"] = findings
        tightened = [f["tightens_to"] for f in findings if f.get("fired")]
        if behavior == "VALID" and any("evaluator_error" in f for f in findings):
            # A VALID class cannot be certified by an incomplete closure
            # pass: an errored closure might have tightened it (ERRATA E9).
            # Sealed defect classes stand — closures only tighten.
            final = "AUDIT_INCOMPLETE"
        elif behavior == "VALID" and tightened:
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
