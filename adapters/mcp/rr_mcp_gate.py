"""rr-mcp-gate — receiver-reliance as an MCP server.

A stdio MCP server that puts a deterministic, auditable reliance decision in
front of records an agent receives. Any stack that speaks MCP can call it.

Pipeline, per checked record::

    MCP tool-call result
        -> mappers/                (shape mapper: native evidence + fact profile)
        -> adapters/preflight      (READY | REJECTED_INVALID | INSUFFICIENT_EVIDENCE)
        -> receiver_reliance.decide_audited   (only when READY)
        -> verify_audit_seal       (the returned envelope is checked, not trusted)
        -> compact verdict + sealed audit line in the JSONL audit log

Tools:
  ``rr_gate_check``    classify one received record; append the full audited
                       decision to the audit log; return a compact verdict.
  ``rr_gate_batch``    classify a LIST of received records in one wire call.
                       Each item runs the identical per-record pipeline —
                       independent decision, own audit line, own
                       content-addressed id; order preserved; a failing item
                       is reported at its index and never affects siblings.
                       Wire-level cost reduction only: nothing about the
                       decisions themselves is batched or shared.
  ``rr_gate_explain``  given a decision id from the log, re-verify that logged
                       envelope's seal and return the witness trace, the
                       predicates that fired, and the frozen decision-table row
                       that produced the class.

Posture: **OBSERVE by default** — classify and log, never block. ENFORCE exists
(``RR_MCP_GATE_ENFORCE=1``) and ships off. Enforcement policy is the host's
(HOST_OBLIGATIONS H1-H6 stay with the host in both postures).

Claim discipline: classification and sealed-audit value only. No efficacy,
security, or behavioral-improvement claim; ``READY`` is eligibility, never a
pass; a ``VALID`` class is a classification, never an authorization. See
README.md, which inherits ``TRUST_MODEL.md`` exactly.

Runtime: local stdio only. No network calls, no secrets, no clock inside any
sealed object (the audit log's ``logged_at_unix`` is a host observation recorded
outside the seal).
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import time
from typing import Any

sys.dont_write_bytecode = True

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import rr_bridge  # noqa: E402
from mappers import mcp_tool_result  # noqa: E402

SERVER_NAME = "rr-mcp-gate"
SERVER_VERSION = "0.2.0"

# Admission bound for rr_gate_batch, mirroring the bounded-ingest posture every
# other peripheral surface carries (ADOPTION A4): an unbounded array on the one
# wire a host's client writes to would be the only unbounded thing here.
BATCH_MAX_ITEMS = 64
LATEST_PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

VERDICT_NO_FINDING = "NO_FINDING"
VERDICT_HOLD = "HOLD"
VERDICT_ABSTAIN = "ABSTAIN"


def audit_log_path() -> pathlib.Path:
    """Where audited decisions are appended. Never inside the repository tree.

    The log is host evidence, not artifact evidence: it records what a particular
    host relied on and when. Defaulting it into the checkout would mix the two
    and make a working tree dirty just by answering a call, so the default is the
    host's own temporary directory and any real deployment sets
    ``RR_MCP_GATE_AUDIT_LOG`` to somewhere it retains (H5).
    """
    override = os.environ.get("RR_MCP_GATE_AUDIT_LOG")
    if override:
        return pathlib.Path(override)
    return pathlib.Path(tempfile.gettempdir()) / "rr_mcp_audit.jsonl"


def enforce_enabled() -> bool:
    return os.environ.get("RR_MCP_GATE_ENFORCE") == "1"


# --- reason lines ----------------------------------------------------------
# Each line restates the frozen predicate that matched, in the contract's own
# terms. Nothing is inferred beyond the decision-table row; the full witness
# trace and the predicate source itself are available from rr_gate_explain.
_REASONS: dict[tuple[str, str], str] = {
    ("OBL-02", "EQ"): (
        "the relied-on reference is the floating alias LATEST, not an exact "
        "record identity"
    ),
    ("OBL-02", "ABSENT"): "no exact reference was bound for the record relied on",
    ("OBL-02", "NOT_FUNCTIONAL_BY"): (
        "the delivered version map is not a function: one record identity carries "
        "two different revision digests"
    ),
    ("OBL-02", "NOT_MEMBER_BY_KEY"): (
        "the relied-on reference is not present in the delivered version set"
    ),
}


def _engine_reason(obligation_id: str, behavior_class: str, witness: list[Any]) -> str:
    """One line per audited class. All six are handled, and none falls through.

    ``audited_behavior_class`` is a closed six-value set and TRUST_MODEL.md
    requires a consumer switching on it to handle all six. Four come from the
    frozen law; ``AUDIT_INCOMPLETE`` and ``PROTOCOL_ERROR`` come from the audited
    surface and mean 'not judged', which is why neither may read as a finding.
    """
    if behavior_class == "VALID":
        return f"no {obligation_id} finding on the supplied facts"
    if behavior_class == "AUDIT_INCOMPLETE":
        return (
            "a closure evaluator errored, so a VALID class could not be certified; "
            "this is not a finding about the record"
        )
    if behavior_class == "PROTOCOL_ERROR":
        return (
            "the request never reached classification, so no decision was made "
            "about this record; held rather than passed"
        )
    ops = [node.get("op") for node in witness if isinstance(node, dict)]
    for op in ops:
        line = _REASONS.get((obligation_id, op))
        if line:
            return line
    return f"{obligation_id} classified {behavior_class}; see rr_gate_explain"


# --- the gate --------------------------------------------------------------


def gate_check(arguments: Any) -> dict[str, Any]:
    """Map -> preflight -> (if READY) decide_audited. Returns (verdict, audit record)."""
    mapping = mcp_tool_result.map_tool_result(arguments)
    result = rr_bridge.preflight(mapping.record, mapping.fact_profile)
    preflight_dict = result.as_dict()

    audited: dict[str, Any] | None = None
    behavior_class: str | None = None
    decision_input_sha256: str | None = None
    audit_sha256: str | None = None
    seal_verified: bool | None = None

    if result.status == rr_bridge.READY and mapping.fact_profile is not None:
        request = rr_bridge.build_request(
            mapping.obligation_id,
            mapping.fact_profile["facts"],
            mapping.fact_profile["native_evidence_sha256"],
        )
        audited = rr_bridge.decide_audited(request)
        behavior_class = audited.get("audited_behavior_class")
        audit_sha256 = audited.get("audit_sha256")
        decision_input_sha256 = (audited.get("audit") or {}).get("decision_input_sha256")
        witness = (audited.get("audit") or {}).get("matched_class_witness") or []
        # Check the envelope rather than trusting it. verify_audit_seal is total
        # and recomputes the self-zero seal over the envelope's own bytes, so an
        # envelope corrupted between production and use cannot be reported as a
        # decision. What True proves is integrity, never provenance: nothing here
        # is signed (TRUST_MODEL.md), so this detects corruption and tampering,
        # and authenticates nobody.
        seal_verified = rr_bridge.verify_audit_seal(audited)
        stage = "ENGINE"
        if not seal_verified:
            verdict = VERDICT_HOLD
            reason = (
                "the audited envelope's own seal did not recompute; the decision "
                "is not reportable and is held rather than passed"
            )
        else:
            verdict = VERDICT_NO_FINDING if behavior_class == "VALID" else VERDICT_HOLD
            reason = _engine_reason(mapping.obligation_id, behavior_class, witness)
    elif result.status == rr_bridge.REJECTED_INVALID:
        stage = "PREFLIGHT"
        verdict = VERDICT_HOLD
        reason = _preflight_reason(result)
    else:
        stage = "PREFLIGHT"
        verdict = VERDICT_ABSTAIN
        reason = _preflight_reason(result)

    decision_id = _decision_id(mapping, preflight_dict, audit_sha256)
    enforced = enforce_enabled()
    verdict_object = {
        "decision_id": decision_id,
        "stage": stage,
        "verdict": verdict,
        "obligation_id": mapping.obligation_id,
        "preflight_status": result.status,
        "audited_behavior_class": behavior_class,
        "reason": reason,
        "audit_sha256": audit_sha256,
        "audit_format": (audited or {}).get("format_version"),
        "seal_verified": seal_verified,
        "decision_input_sha256": decision_input_sha256,
        "native_evidence_sha256": preflight_dict["native_evidence_sha256"],
        "preflight_issue_codes": [issue["code"] for issue in preflight_dict["issues"]],
        "mapper_notes": list(mapping.notes),
        "posture": "ENFORCE" if enforced else "OBSERVE",
        "enforcement_action": "BLOCK" if (enforced and verdict == VERDICT_HOLD) else "NONE",
        "audit_log": str(audit_log_path()),
    }

    audit_record = {
        "format_version": "RR-MCP-GATE-AUDIT-1",
        "decision_id": decision_id,
        "logged_at_unix": int(time.time()),
        "server": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "posture": verdict_object["posture"],
        "verdict": verdict_object,
        "mapping": mapping.as_dict(),
        "preflight": preflight_dict,
        "audited_decision": audited,
        "reliance_context": _reliance_context(arguments),
    }
    _append_audit(audit_record)
    return verdict_object


def _preflight_reason(result: Any) -> str:
    """Use the preflight's own message. No restatement, no inference."""
    if result.issues:
        issue = result.issues[0]
        return f"{issue.code}: {issue.message}"
    return f"preflight returned {result.status} with no issue detail"


def _reliance_context(arguments: Any) -> dict[str, Any]:
    """Labels and intent only. Result payload content is never recorded."""
    if not isinstance(arguments, dict):
        return {}
    call = arguments.get("call") if isinstance(arguments.get("call"), dict) else {}
    reliance = (
        arguments.get("reliance") if isinstance(arguments.get("reliance"), dict) else {}
    )
    return {
        "server": call.get("server"),
        "tool": call.get("tool"),
        "intent": reliance.get("intent"),
        "description": reliance.get("description"),
    }


def _decision_id(mapping: Any, preflight_dict: dict[str, Any], audit_sha256: str | None) -> str:
    """Content-addressed: identical evidence yields an identical decision id."""
    seed = {
        "mapper_id": mcp_tool_result.MAPPER_ID,
        "record": mapping.record,
        "preflight_status": preflight_dict["status"],
        "audit_sha256": audit_sha256,
    }
    return "RRD_" + rr_bridge.evidence_sha256(seed)[:24]


def _append_audit(record: dict[str, Any]) -> None:
    path = audit_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")


def gate_batch(arguments: Any) -> dict[str, Any]:
    """Classify a list of records in one wire call.

    Batching exists to cut the caller's per-record wire and loop cost: for an
    agent host, each tool call is a full model turn, so per-record gating puts
    the loop turn — not the decision — on the critical path, N times per
    handoff. It changes nothing about any decision: each item runs the
    same ``gate_check`` pipeline independently — its own preflight, its own
    audited decision, its own seal verification, its own audit line, its own
    content-addressed decision id. Order is preserved and results carry their
    input index. A failing item is reported at its index with the exception
    text and never suppresses or alters a sibling's decision (there is no
    shared state between items beyond the append-only log).
    """
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object carrying a checks array")
    checks = arguments.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("checks must be a nonempty array of rr_gate_check argument objects")
    if len(checks) > BATCH_MAX_ITEMS:
        raise ValueError(
            f"checks carries {len(checks)} items; the admission bound is {BATCH_MAX_ITEMS}"
        )
    items: list[dict[str, Any]] = []
    counts = {VERDICT_NO_FINDING: 0, VERDICT_HOLD: 0, VERDICT_ABSTAIN: 0}
    errors = 0
    any_block = False
    for index, check_arguments in enumerate(checks):
        try:
            verdict = gate_check(check_arguments)
        except Exception as exc:  # isolate the item; siblings still get decisions
            errors += 1
            items.append({"index": index, "error": f"{type(exc).__name__}: {exc}"})
            continue
        counts[verdict["verdict"]] += 1
        any_block = any_block or verdict["enforcement_action"] == "BLOCK"
        items.append({"index": index, **verdict})
    enforced = enforce_enabled()
    return {
        "items": items,
        "summary": {
            "items": len(checks),
            "no_finding": counts[VERDICT_NO_FINDING],
            "hold": counts[VERDICT_HOLD],
            "abstain": counts[VERDICT_ABSTAIN],
            "errors": errors,
        },
        "posture": "ENFORCE" if enforced else "OBSERVE",
        # Fail-closed under enforcement: an item that never reached a decision
        # is "not judged", which may not read as a pass (TRUST_MODEL.md).
        "enforcement_action": "BLOCK" if (enforced and (any_block or errors)) else "NONE",
    }


def gate_explain(arguments: Any) -> dict[str, Any]:
    """Return the witness trace and the predicate that fired for a logged decision."""
    decision_id = arguments.get("decision_id") if isinstance(arguments, dict) else None
    if not isinstance(decision_id, str) or not decision_id:
        raise ValueError("decision_id is required and must be a nonempty string")
    path = audit_log_path()
    if not path.is_file():
        raise ValueError(f"no audit log at {path}")
    found: dict[str, Any] | None = None
    occurrences = 0
    # The log is bytes on disk that this process did not produce, so it is read
    # under the shared bounded ingest law rather than by a bare json.loads: a
    # duplicate key in an appended line would otherwise silently decide which
    # value this explanation reports (ADOPTION A4, portability/strict_ingest.py).
    with path.open("rb") as stream:
        for raw in stream:
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = rr_bridge.strict_ingest.load_safe(raw, label=path.name)
            except (rr_bridge.strict_ingest.IngestError, ValueError):
                continue
            if isinstance(row, dict) and row.get("decision_id") == decision_id:
                found = row
                occurrences += 1
    if found is None:
        raise ValueError(f"decision_id {decision_id} not found in {path}")

    audited = found.get("audited_decision") or {}
    audit = audited.get("audit") or {}
    behavior_class = audited.get("audited_behavior_class")
    obligation_id = found["verdict"].get("obligation_id")
    explanation: dict[str, Any] = {
        "decision_id": decision_id,
        "occurrences_in_log": occurrences,
        "verdict": found["verdict"]["verdict"],
        "stage": found["verdict"]["stage"],
        "obligation_id": obligation_id,
        "preflight": {
            "status": found["preflight"]["status"],
            "issues": found["preflight"]["issues"],
        },
        "mapper": {
            "mapper_id": found["mapping"]["mapper_id"],
            "family": found["mapping"]["family"],
            "mapped": found["mapping"]["mapped"],
            "notes": found["mapping"]["notes"],
            "native_evidence": found["mapping"]["record"],
        },
    }
    if audited:
        explanation["engine"] = {
            "audit_format": audited.get("format_version"),
            "audited_behavior_class": behavior_class,
            "audit_sha256": audited.get("audit_sha256"),
            # Re-verified here, from the bytes just read back off disk, rather
            # than replayed from what the writer recorded at decision time. A log
            # line edited after the fact reports False.
            "seal_verified": rr_bridge.verify_audit_seal(audited),
            "decision_input_sha256": audit.get("decision_input_sha256"),
            "first_match_predicates": audit.get("first_match_predicates"),
            "matched_class_witness": audit.get("matched_class_witness"),
            "closure_findings": audit.get("closure_findings"),
            "record_references": audit.get("record_references"),
            "governing_authorities": audit.get("governing_authorities"),
            "predicate_source": (
                rr_bridge.predicate_source(
                    obligation_id, behavior_class, audit.get("governing_authorities")
                )
                if obligation_id and behavior_class
                else None
            ),
        }
    else:
        explanation["engine"] = None
        explanation["engine_not_invoked_because"] = found["preflight"]["status"]
    return explanation


# --- MCP tool descriptors --------------------------------------------------

_CHECK_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "call": {
            "type": "object",
            "description": "What the caller asked for, and what the result claims to be.",
            "properties": {
                "server": {"type": "string", "description": "Label of the upstream MCP server."},
                "tool": {"type": "string", "description": "Label of the upstream tool."},
                "record_reference": {
                    "type": "object",
                    "properties": {
                        "requested": {
                            "type": "string",
                            "description": "The exact record identity the caller intends to rely on.",
                        },
                        "returned": {
                            "type": "string",
                            "description": "The record identity the result declares it carries. Never defaulted.",
                        },
                        "declared_revision_sha256": {
                            "type": "string",
                            "description": "Uppercase SHA-256 the result declares for the record revision.",
                        },
                        "revision_digest_domain": {
                            "type": "string",
                            "description": (
                                "canonical-json:<RFC 6901 pointer> naming the bytes the declared "
                                "digest covers. Required with declared_revision_sha256; an unbound "
                                "claim is dropped and disclosed, never compared across domains."
                            ),
                        },
                    },
                },
            },
            "required": ["record_reference"],
        },
        "result": {
            "type": "object",
            "description": "The MCP CallToolResult being relied on, verbatim.",
        },
        "reliance": {
            "type": "object",
            "description": "Minimal intent context. Logged; never classified.",
            "properties": {
                "intent": {"type": "string"},
                "description": {"type": "string"},
            },
        },
    },
    "required": ["call", "result"],
}

_CHECK_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "decision_id": {"type": "string"},
        "stage": {"type": "string", "enum": ["PREFLIGHT", "ENGINE"]},
        "verdict": {"type": "string", "enum": [VERDICT_NO_FINDING, VERDICT_HOLD, VERDICT_ABSTAIN]},
        "obligation_id": {"type": ["string", "null"]},
        "preflight_status": {"type": "string"},
        "audited_behavior_class": {"type": ["string", "null"]},
        "reason": {"type": "string"},
        "audit_sha256": {"type": ["string", "null"]},
        "decision_input_sha256": {"type": ["string", "null"]},
        "native_evidence_sha256": {"type": ["string", "null"]},
        "preflight_issue_codes": {"type": "array", "items": {"type": "string"}},
        "mapper_notes": {"type": "array", "items": {"type": "string"}},
        "posture": {"type": "string", "enum": ["OBSERVE", "ENFORCE"]},
        "enforcement_action": {"type": "string", "enum": ["NONE", "BLOCK"]},
        "audit_log": {"type": "string"},
    },
    "required": ["decision_id", "stage", "verdict", "reason", "posture"],
}

_BATCH_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "checks": {
            "type": "array",
            "description": (
                "rr_gate_check argument objects, one per record relied on. "
                f"Order is preserved in the result. At most {BATCH_MAX_ITEMS} items."
            ),
            "items": _CHECK_INPUT_SCHEMA,
            "minItems": 1,
            "maxItems": BATCH_MAX_ITEMS,
        }
    },
    "required": ["checks"],
}

_BATCH_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "description": (
                "One entry per input, in input order, carrying its input index. "
                "Either a full rr_gate_check verdict object, or {index, error} when "
                "that item's pipeline raised — an errored item was not judged and "
                "must not be read as a pass."
            ),
            "items": {"type": "object", "required": ["index"]},
        },
        "summary": {
            "type": "object",
            "properties": {
                "items": {"type": "integer"},
                "no_finding": {"type": "integer"},
                "hold": {"type": "integer"},
                "abstain": {"type": "integer"},
                "errors": {"type": "integer"},
            },
            "required": ["items", "no_finding", "hold", "abstain", "errors"],
        },
        "posture": {"type": "string", "enum": ["OBSERVE", "ENFORCE"]},
        "enforcement_action": {"type": "string", "enum": ["NONE", "BLOCK"]},
    },
    "required": ["items", "summary", "posture", "enforcement_action"],
}

_EXPLAIN_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "decision_id": {
            "type": "string",
            "description": "A decision id returned by rr_gate_check.",
        }
    },
    "required": ["decision_id"],
}

TOOLS = [
    {
        "name": "rr_gate_check",
        "title": "Check a received record before relying on it",
        "description": (
            "Classify one MCP tool-call result the caller intends to rely on as a record. "
            "Runs the receiver-reliance three-state preflight, then (only when READY) the "
            "audited decision engine, and appends the full audited decision to a local "
            "JSONL audit log. Returns preflight status or audited class, the obligation "
            "judged, a one-line reason, and the audit seal digest. Observe-only by default: "
            "it classifies and logs, it does not block. It is not an authorization, not a "
            "security control, and carries no efficacy claim; an abstention "
            "(INSUFFICIENT_EVIDENCE) means the record does not carry the obligation's "
            "semantics and is a designed outcome, not a failure."
        ),
        "inputSchema": _CHECK_INPUT_SCHEMA,
        "outputSchema": _CHECK_OUTPUT_SCHEMA,
    },
    {
        "name": "rr_gate_batch",
        "title": "Check a list of received records before relying on them",
        "description": (
            "Classify a list of MCP tool-call results in one call. Each item runs the "
            "identical per-record pipeline as rr_gate_check — independent preflight, "
            "independent audited decision, its own audit line and content-addressed "
            "decision id; order is preserved, and a failing item is reported at its "
            "index without affecting siblings. Batching reduces the caller's per-record "
            "wire and loop cost; it changes nothing about any decision. Bounded at "
            f"{BATCH_MAX_ITEMS} items per call. Observe-only by default, same as "
            "rr_gate_check; the same non-claims apply."
        ),
        "inputSchema": _BATCH_INPUT_SCHEMA,
        "outputSchema": _BATCH_OUTPUT_SCHEMA,
    },
    {
        "name": "rr_gate_explain",
        "title": "Explain a prior gate decision",
        "description": (
            "Given a decision id from rr_gate_check, return what fired: the preflight "
            "issues, the mapper's native evidence, the matched-predicate witness trace, "
            "the per-class first-match map, closure findings, the governing authority "
            "digests, and the frozen decision-table predicate that produced the class."
        ),
        "inputSchema": _EXPLAIN_INPUT_SCHEMA,
    },
]

INSTRUCTIONS = (
    "Call rr_gate_check on a tool result before relying on it as a record — or "
    "rr_gate_batch to check several in one call (identical per-record decisions; "
    "wire-level batching only). The verdict is a classification, not an authorization: "
    "NO_FINDING means the engine found no defect on the obligation checked, HOLD names "
    "a detected defect, ABSTAIN means the record does not carry that obligation's "
    "semantics. Enforcement, state truthfulness, atomicity, derivation, input binding, "
    "and effects remain the host's obligations (HOST_OBLIGATIONS H1-H6)."
)


# --- JSON-RPC / MCP transport ---------------------------------------------


def _negotiate(requested: Any) -> str:
    if isinstance(requested, str) and requested in SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return LATEST_PROTOCOL_VERSION


def _tool_result(payload: dict[str, Any], is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=1, sort_keys=True)}],
        "structuredContent": payload,
        "isError": is_error,
    }


def handle_message(message: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    has_id = "id" in message
    message_id = message.get("id")
    params = message.get("params") or {}

    def ok(result: Any) -> dict[str, Any] | None:
        return {"jsonrpc": "2.0", "id": message_id, "result": result} if has_id else None

    def err(code: int, text: str) -> dict[str, Any] | None:
        return (
            {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": text}}
            if has_id
            else None
        )

    if method == "initialize":
        state["protocol_version"] = _negotiate(params.get("protocolVersion"))
        return ok(
            {
                "protocolVersion": state["protocol_version"],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": INSTRUCTIONS,
            }
        )
    if method in ("notifications/initialized", "initialized"):
        state["initialized"] = True
        return None
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            if name == "rr_gate_check":
                verdict = gate_check(arguments)
                block = verdict["enforcement_action"] == "BLOCK"
                return ok(_tool_result(verdict, is_error=block))
            if name == "rr_gate_batch":
                batch = gate_batch(arguments)
                # Loud on the wire when anything was not judged (an errored item
                # is never a pass) or when enforcement blocks; a HOLD in OBSERVE
                # posture is a classification, not an error, same as rr_gate_check.
                loud = batch["summary"]["errors"] > 0 or batch["enforcement_action"] == "BLOCK"
                return ok(_tool_result(batch, is_error=loud))
            if name == "rr_gate_explain":
                return ok(_tool_result(gate_explain(arguments)))
        except Exception as exc:  # tool failure -> isError result, never a crash
            return ok(
                _tool_result(
                    {"error": f"{type(exc).__name__}: {exc}", "tool": name}, is_error=True
                )
            )
        return err(-32602, f"unknown tool {name!r}")
    if method is None:
        return err(-32600, "not a JSON-RPC request")
    return err(-32601, f"method not found: {method}")


def serve(source: Any = None, sink: Any = None) -> int:
    """One request per physical line, in and out, over binary streams.

    Binary rather than text, and ``strict_ingest.load_safe`` rather than
    ``json.loads``, for the same reason ``rr_batch.serve`` reads bytes: this is
    the surface a host's client writes to, and it is the one place in this
    adapter where the sender is not the artifact. A duplicate key here would
    otherwise silently choose which ``arguments`` object the gate judged. A line
    the law rejects is a per-request parse error, never a stream failure.
    """
    source = source if source is not None else sys.stdin.buffer
    sink = sink if sink is not None else sys.stdout.buffer
    state: dict[str, Any] = {"protocol_version": LATEST_PROTOCOL_VERSION}

    def emit(payload: dict[str, Any]) -> None:
        sink.write(json.dumps(payload).encode("utf-8") + b"\n")
        sink.flush()

    for raw in source:
        raw = raw.strip()
        if not raw:
            continue
        try:
            message = rr_bridge.strict_ingest.load_safe(raw, label="mcp-message")
        except (rr_bridge.strict_ingest.IngestError, ValueError) as exc:
            emit(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"parse error: {exc}"},
                }
            )
            continue
        if not isinstance(message, dict):
            continue
        response = handle_message(message, state)
        if response is not None:
            emit(response)
    return 0


def main(argv: list[str]) -> int:
    if argv[1:2] == ["--calibrate"]:
        report = rr_bridge.calibrate()
        print(
            f"rr-mcp-gate calibration: {report['reproduced']}/{report['entries']} "
            f"pack entries reproduce byte-exactly (pack {report['pack_id']})"
        )
        for entry_id in report["mismatches"]:
            print(f"CALIBRATION MISMATCH {entry_id}")
        return 0 if not report["mismatches"] else 1
    if argv[1:2] == ["--self-test"]:
        report = rr_bridge.calibrate()
        print(f"rr_home={rr_bridge.RR_HOME}")
        print(f"audit_log={audit_log_path()}")
        print(f"posture={'ENFORCE' if enforce_enabled() else 'OBSERVE'}")
        print(f"audit_format={rr_bridge.AUDIT_FORMAT}")
        print(f"calibration={report['reproduced']}/{report['entries']}")
        return 0 if not report["mismatches"] else 1
    return serve()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
