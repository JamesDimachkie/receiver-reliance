"""Regression suite for the MCP gate: the tool-result mapper and the pipeline.

Checks, in order:
  1. LAW       — every clause of the mapper's derivation law, including the two
                 it is forbidden to break: no fabricated fact values, and
                 ``returned`` is never defaulted to ``requested``.
  2. PREFLIGHT — the mapper's own fact derivation is accepted by the shipped
                 preflight (no PREFLIGHT_PROFILE_FACT_MISMATCH), so drift in this
                 module surfaces as REJECTED_INVALID rather than a bad decision.
  3. PIPELINE  — the three preflight states and the three defect classes the
                 OBL-02 decision table can reach, end to end through gate_check.
  4. POSTURE   — observe-only is the default and never emits a block.
  5. SEAL      — every envelope this gate reports was checked with
                 ``verify_audit_seal``, and a broken seal holds rather than
                 passes. Both arms, because a verifier that cannot go red is
                 decoration.
  6. TOTALITY  — all six values of ``audited_behavior_class`` are handled,
                 not the four the law assigns (TRUST_MODEL.md), and the two
                 the audited surface adds never read as a finding.
  7. INGEST    — the wire and the audit log are read under the shared
                 bounded ingest law, so a duplicate key is refused rather
                 than silently resolved (ADOPTION A4).
  8. AUTHORITY — the predicate ``rr_gate_explain`` shows is bound to the
                 ``governing_authorities`` digest the envelope recorded.

Exit 0 with 'failures=0' on success.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import pathlib
import sys
import tempfile

sys.dont_write_bytecode = True

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Route every audited decision this suite makes to a throwaway log.
_TMP_LOG = pathlib.Path(tempfile.gettempdir()) / "rr_mcp_gate_selftest.jsonl"
os.environ["RR_MCP_GATE_AUDIT_LOG"] = str(_TMP_LOG)
os.environ.pop("RR_MCP_GATE_ENFORCE", None)
if _TMP_LOG.exists():
    _TMP_LOG.unlink()

import rr_bridge  # noqa: E402
import rr_mcp_gate  # noqa: E402
from mappers import mcp_tool_result as M  # noqa: E402

failures = 0
checks = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures, checks
    checks += 1
    if not ok:
        failures += 1
        print(f"FAIL {name} {detail}")


RECORD = {"id": "res://tickets/T-42", "state": "OPEN"}
DOMAIN = "canonical-json:/structuredContent/record"
GOOD = hashlib.sha256(rr_bridge.canonical_json_bytes(RECORD)).hexdigest().upper()
BAD = "0" * 63 + "1"


def result(record=RECORD, revision=GOOD, is_error=False):
    return {
        "isError": is_error,
        "content": [{"type": "text", "text": json.dumps(record, sort_keys=True)}],
        "structuredContent": {"record": record, "revision_sha256": revision},
    }


def payload(reference: dict, res=None) -> dict:
    return {
        "call": {"server": "docs", "tool": "get_record", "record_reference": reference},
        "result": result() if res is None else res,
        "reliance": {"intent": "ACT_ON_RECORD"},
    }


CLEAN_REF = {
    "requested": "res://tickets/T-42",
    "returned": "res://tickets/T-42",
    "declared_revision_sha256": GOOD,
    "revision_digest_domain": DOMAIN,
}

# --- 1. LAW ----------------------------------------------------------------

clean = M.map_tool_result(payload(CLEAN_REF))
check("law:clean-maps", clean.mapped and clean.family == "REF")
check("law:clean-obligation", clean.obligation_id == "OBL-02")
check("law:no-fabrication", clean.fact_profile["fabricated_fields"] == [])
check(
    "law:claimed-path-is-requested",
    clean.record["native"]["claimed_path"] == "res://tickets/T-42",
)
check(
    "law:referenced-record-is-returned",
    clean.record["native"]["referenced_record"] == "res://tickets/T-42",
)
check(
    "law:observed-digest-derived-over-declared-domain",
    clean.record["observations"]["observed_sha256"] == GOOD,
    clean.record["observations"]["observed_sha256"],
)
check("law:found-true-on-success", clean.record["observations"]["referenced_record_found"] is True)
check(
    "law:no-payload-content-in-native-evidence",
    "OPEN" not in json.dumps(clean.record),
    json.dumps(clean.record),
)

no_returned = M.map_tool_result(
    payload({"requested": "res://tickets/T-42"})
)
check(
    "law:returned-never-defaulted-to-requested",
    "referenced_record" not in no_returned.record["native"],
    json.dumps(no_returned.record["native"]),
)
check(
    "law:identity-agreement-disclosed-as-unchecked",
    any(n.startswith("IDENTITY_AGREEMENT_UNCHECKED") for n in no_returned.notes),
    str(no_returned.notes),
)

no_requested = M.map_tool_result(payload({"returned": "res://tickets/T-42"}))
check(
    "law:returned-only-still-maps",
    no_requested.mapped
    and no_requested.fact_profile["facts"]["exact_reference"] == "res://tickets/T-42",
)
check(
    "law:requested-absence-disclosed",
    any(n.startswith("REQUESTED_REFERENCE_ABSENT") for n in no_requested.notes),
)

unbound = M.map_tool_result(
    payload({"requested": "res://tickets/T-42", "declared_revision_sha256": GOOD})
)
check(
    "law:unbound-digest-claim-dropped",
    "claimed_sha256" not in unbound.record["native"],
    json.dumps(unbound.record["native"]),
)
check(
    "law:unbound-digest-claim-disclosed",
    "CLAIM_UNBOUND_DIGEST_DOMAIN" in unbound.notes,
    str(unbound.notes),
)

unresolvable = M.map_tool_result(
    payload(
        {
            "requested": "res://tickets/T-42",
            "declared_revision_sha256": GOOD,
            "revision_digest_domain": "canonical-json:/structuredContent/nope",
        }
    )
)
check(
    "law:unresolvable-domain-drops-claim",
    "claimed_sha256" not in unresolvable.record["native"]
    and "CLAIM_UNBOUND_DIGEST_DOMAIN" in unresolvable.notes,
)

errored = M.map_tool_result(payload(CLEAN_REF, res=result(is_error=True)))
check(
    "law:error-result-is-not-found",
    errored.record["observations"]["referenced_record_found"] is False,
)
check(
    "law:absent-record-carries-no-content-testimony",
    "observed_sha256" not in errored.record["observations"],
)
check(
    "law:absent-record-has-empty-version-set",
    errored.fact_profile["facts"]["record_versions"] == [],
)

for bad_case, label in (
    ({"requested": "res://tickets/T-42", "declared_revision_sha256": "nothex"}, "malformed-digest"),
    ({"requested": 42}, "malformed-requested"),
    ({}, "no-identity"),
):
    mapping = M.map_tool_result(payload(bad_case))
    check(
        f"law:declines-{label}",
        not mapping.mapped and mapping.family == M.FAMILY_UNCLASSIFIED,
        str(mapping.notes),
    )

for missing, label in (
    ({"call": {"record_reference": CLEAN_REF}}, "no-result"),
    ({"result": result()}, "no-call"),
    ("not an object", "not-an-object"),
):
    mapping = M.map_tool_result(missing)
    check(f"law:declines-{label}", not mapping.mapped and mapping.fact_profile is None)

deep = {"a": None}
node = deep
for _ in range(64):  # exceeds the artifact's bounded-JSON depth limit
    node["a"] = {"a": None}
    node = node["a"]
oversize = M.map_tool_result(payload(CLEAN_REF, res={"isError": False, "structuredContent": deep}))
check(
    "law:out-of-bounds-payload-abstains-without-crashing",
    not oversize.mapped and oversize.notes[0].startswith("MAPPER_PAYLOAD_OUT_OF_BOUNDED"),
    str(oversize.notes),
)

check(
    "law:record-id-content-addressed",
    M.map_tool_result(payload(CLEAN_REF)).record["record_id"] == clean.record["record_id"],
)
check(
    "law:record-id-differs-on-different-evidence",
    M.map_tool_result(payload(CLEAN_REF, res=result(revision=BAD))).record["record_id"]
    != clean.record["record_id"],
)

# --- 2. PREFLIGHT cross-check ----------------------------------------------

for label, mapping in (
    ("clean", clean),
    ("no-returned", no_returned),
    ("returned-only", no_requested),
    ("unbound-claim", unbound),
    ("errored", errored),
):
    outcome = rr_bridge.preflight(mapping.record, mapping.fact_profile)
    codes = [issue.code for issue in outcome.issues]
    check(
        f"preflight:{label}-profile-accepted",
        outcome.profile_checked
        and not [c for c in codes if c.startswith("PREFLIGHT_PROFILE_")],
        str(codes),
    )
    check(f"preflight:{label}-ready", outcome.status == rr_bridge.READY, outcome.status)

# a profile the mapper did not derive must be rejected, or the cross-check is decoration
tampered = json.loads(json.dumps(clean.fact_profile))
tampered["facts"]["exact_reference"] = "res://tickets/T-999"
tampered_outcome = rr_bridge.preflight(clean.record, tampered)
check(
    "preflight:tampered-profile-rejected",
    tampered_outcome.status == rr_bridge.REJECTED_INVALID
    and any(i.code == "PREFLIGHT_PROFILE_FACT_MISMATCH" for i in tampered_outcome.issues),
    str([i.code for i in tampered_outcome.issues]),
)

# --- 3. PIPELINE end to end -------------------------------------------------

CASES = [
    ("clean", CLEAN_REF, result(), "NO_FINDING", "READY", "VALID"),
    (
        "identity-swap",
        dict(CLEAN_REF, returned="res://tickets/T-99"),
        result(),
        "HOLD",
        "REJECTED_INVALID",
        None,
    ),
    (
        "digest-drift",
        dict(CLEAN_REF, declared_revision_sha256=BAD),
        result(revision=BAD),
        "HOLD",
        "READY",
        "OMISSION_OR_INCOMPLETE",
    ),
    (
        "floating-reference",
        dict(CLEAN_REF, requested="LATEST", returned="LATEST"),
        result(),
        "HOLD",
        "READY",
        "MALFORMED_OR_BOUNDARY",
    ),
    (
        "tool-errored",
        CLEAN_REF,
        result(is_error=True),
        "HOLD",
        "READY",
        "OMISSION_OR_INCOMPLETE",
    ),
    ("out-of-scope", {}, result(), "ABSTAIN", "INSUFFICIENT_EVIDENCE", None),
]

decision_ids = {}
for label, reference, res, want_verdict, want_preflight, want_class in CASES:
    verdict = rr_mcp_gate.gate_check(payload(reference, res=res))
    decision_ids[label] = verdict["decision_id"]
    check(f"pipeline:{label}-verdict", verdict["verdict"] == want_verdict, verdict["verdict"])
    check(
        f"pipeline:{label}-preflight",
        verdict["preflight_status"] == want_preflight,
        verdict["preflight_status"],
    )
    check(
        f"pipeline:{label}-class",
        verdict["audited_behavior_class"] == want_class,
        str(verdict["audited_behavior_class"]),
    )
    check(f"pipeline:{label}-reason-nonempty", bool(verdict["reason"]))
    if want_class not in (None, "VALID"):
        check(f"pipeline:{label}-sealed", bool(verdict["audit_sha256"]))

# BINDING (HOST_OBLIGATIONS H5): different facts can never share an audit seal.
seals = set()
for label in ("clean", "digest-drift", "floating-reference"):
    line = [
        json.loads(row)
        for row in _TMP_LOG.read_text(encoding="utf-8").splitlines()
        if json.loads(row)["decision_id"] == decision_ids[label]
    ][-1]
    seals.add(line["audited_decision"]["audit_sha256"])
check("pipeline:distinct-facts-distinct-seals", len(seals) == 3, str(len(seals)))

explained = rr_mcp_gate.gate_explain({"decision_id": decision_ids["digest-drift"]})
check(
    "explain:witness-nonempty",
    bool(explained["engine"]["matched_class_witness"]),
    json.dumps(explained["engine"]["matched_class_witness"]),
)
check(
    "explain:predicate-source-returned",
    explained["engine"]["predicate_source"] is not None,
)
check(
    "explain:abstention-names-uninvoked-engine",
    rr_mcp_gate.gate_explain({"decision_id": decision_ids["out-of-scope"]})[
        "engine_not_invoked_because"
    ]
    == "INSUFFICIENT_EVIDENCE",
)
try:
    rr_mcp_gate.gate_explain({"decision_id": "RRD_NOT_A_REAL_DECISION"})
    check("explain:unknown-id-raises", False)
except ValueError:
    check("explain:unknown-id-raises", True)

# --- 4. POSTURE -------------------------------------------------------------

check("posture:observe-is-default", not rr_mcp_gate.enforce_enabled())
verdict = rr_mcp_gate.gate_check(payload(dict(CLEAN_REF, requested="LATEST", returned="LATEST")))
check("posture:hold-does-not-block-in-observe", verdict["enforcement_action"] == "NONE")
check("posture:observe-labelled", verdict["posture"] == "OBSERVE")
os.environ["RR_MCP_GATE_ENFORCE"] = "1"
try:
    enforced = rr_mcp_gate.gate_check(
        payload(dict(CLEAN_REF, requested="LATEST", returned="LATEST"))
    )
    check("posture:enforce-blocks-only-on-hold", enforced["enforcement_action"] == "BLOCK")
    allowed = rr_mcp_gate.gate_check(payload(CLEAN_REF))
    check("posture:enforce-passes-no-finding", allowed["enforcement_action"] == "NONE")
finally:
    os.environ.pop("RR_MCP_GATE_ENFORCE", None)

# --- 5. SEAL: the envelope is checked, not trusted ---------------------------

sealed = rr_mcp_gate.gate_check(payload(CLEAN_REF))
check("seal:reported-verified", sealed["seal_verified"] is True, str(sealed["seal_verified"]))
check(
    "seal:format-is-current",
    sealed["audit_format"] == rr_bridge.AUDIT_FORMAT,
    f"{sealed['audit_format']} != {rr_bridge.AUDIT_FORMAT}",
)
check(
    "seal:no-engine-decision-carries-no-seal-claim",
    rr_mcp_gate.gate_check(payload({}))["seal_verified"] is None,
)

# Negative arm. A verifier that cannot go red proves nothing, so an envelope is
# mutated after sealing and the gate must refuse to report it as a decision.
_real_decide = rr_bridge.decide_audited
try:

    def _forged(request):
        envelope = _real_decide(request)
        envelope["audited_behavior_class"] = "VALID"
        return envelope

    rr_bridge.decide_audited = _forged
    # Distinct facts on purpose: decision ids are content-addressed, so reusing
    # another case's facts would file the tampered envelope under that case's id
    # and the AUTHORITY section below would then read the forgery back.
    forged = rr_mcp_gate.gate_check(
        payload(
            dict(
                CLEAN_REF,
                requested="res://tickets/T-777",
                returned="res://tickets/T-777",
                declared_revision_sha256=BAD,
            ),
            res=result(revision=BAD),
        )
    )
    check(
        "seal:forged-envelope-fails-verification",
        forged["seal_verified"] is False,
        str(forged["seal_verified"]),
    )
    check("seal:forged-envelope-is-held", forged["verdict"] == "HOLD", forged["verdict"])
    check(
        "seal:forged-envelope-never-reads-as-no-finding",
        forged["verdict"] != "NO_FINDING" and "seal" in forged["reason"],
        forged["reason"],
    )
finally:
    rr_bridge.decide_audited = _real_decide
check(
    "seal:verifier-restored",
    rr_mcp_gate.gate_check(payload(CLEAN_REF))["seal_verified"] is True,
)

# --- 6. TOTALITY: six classes, not four -------------------------------------

check(
    "totality:six-declared-classes",
    set(rr_bridge.AUDITED_BEHAVIOR_CLASSES)
    == {
        "VALID",
        "MALFORMED_OR_BOUNDARY",
        "BINDING_OR_CONFLICT",
        "OMISSION_OR_INCOMPLETE",
        "AUDIT_INCOMPLETE",
        "PROTOCOL_ERROR",
    },
    str(rr_bridge.AUDITED_BEHAVIOR_CLASSES),
)
_reasons = {
    cls: rr_mcp_gate._engine_reason("OBL-02", cls, [])
    for cls in rr_bridge.AUDITED_BEHAVIOR_CLASSES
}
check("totality:every-class-has-a-reason", all(_reasons.values()), str(_reasons))
check(
    "totality:reasons-are-distinct",
    len(set(_reasons.values())) == len(rr_bridge.AUDITED_BEHAVIOR_CLASSES),
    str(len(set(_reasons.values()))),
)
for _cls in ("AUDIT_INCOMPLETE", "PROTOCOL_ERROR"):
    check(
        f"totality:{_cls}-does-not-read-as-a-finding",
        "not a finding" in _reasons[_cls] or "no decision was made" in _reasons[_cls],
        _reasons[_cls],
    )

# PROTOCOL_ERROR end to end: the engine re-derives the bound request digests, so
# a request this adapter built wrongly is refused rather than classified. The
# gate must hold it, never pass it.
_real_build = rr_bridge.build_request
try:

    def _broken_build(obligation_id, facts, request_seed):
        request = _real_build(obligation_id, facts, request_seed)
        request["inner_request_raw_sha256"] = "0" * 64
        return request

    rr_bridge.build_request = _broken_build
    refused = rr_mcp_gate.gate_check(payload(CLEAN_REF))
    check(
        "totality:protocol-error-class",
        refused["audited_behavior_class"] == "PROTOCOL_ERROR",
        str(refused["audited_behavior_class"]),
    )
    check("totality:protocol-error-is-held", refused["verdict"] == "HOLD", refused["verdict"])
    check("totality:protocol-error-still-sealed", refused["seal_verified"] is True)
finally:
    rr_bridge.build_request = _real_build

# --- 7. INGEST: one bounded law for bytes this adapter did not produce -------

check(
    "ingest:no-bare-loads-in-the-gate",
    "json.loads(" not in pathlib.Path(rr_mcp_gate.__file__).read_text(encoding="utf-8"),
)
check(
    "ingest:no-bare-loads-in-the-bridge",
    "json.loads(" not in pathlib.Path(rr_bridge.__file__).read_text(encoding="utf-8"),
)

_CLEAN_LINE = b'{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}\n'
_DUPLICATE_LINE = (
    b'{"jsonrpc":"2.0","id":2,"method":"ping","method":"tools/list","params":{}}\n'
)
_source = io.BytesIO(_CLEAN_LINE + _DUPLICATE_LINE)
_sink = io.BytesIO()
rr_mcp_gate.serve(_source, _sink)
_lines = [line for line in _sink.getvalue().splitlines() if line.strip()]
check("ingest:wire-answers-every-line", len(_lines) == 2, str(len(_lines)))
_refusal = rr_bridge.strict_ingest.load_safe(_lines[-1], label="refusal")
check(
    "ingest:duplicate-key-message-refused",
    (_refusal.get("error") or {}).get("code") == -32700,
    str(_refusal),
)

_log = pathlib.Path(str(_TMP_LOG))
_before = _log.read_text(encoding="utf-8")
_log.write_text(
    _before + '{"decision_id":"RRD_X","decision_id":"RRD_X"}\n', encoding="utf-8"
)
try:
    rr_mcp_gate.gate_explain({"decision_id": "RRD_X"})
    check("ingest:duplicate-key-log-line-is-not-resolved", False)
except ValueError:
    check("ingest:duplicate-key-log-line-is-not-resolved", True)
finally:
    _log.write_text(_before, encoding="utf-8")

# --- 8. AUTHORITY: the predicate shown is the one that governed -------------

_drift = rr_mcp_gate.gate_explain({"decision_id": decision_ids["digest-drift"]})
_row = _drift["engine"]["predicate_source"]
check("authority:predicate-returned", _row is not None)
check(
    "authority:bound-to-the-decision",
    _row["authority_binding"] == "matches_decision",
    str(_row["authority_binding"]),
)
check(
    "authority:digest-matches-the-envelope",
    _row["contract_sha256"]
    == _drift["engine"]["governing_authorities"][_row["authority_key"]],
)
check(
    "authority:logged-seal-re-verified",
    _drift["engine"]["seal_verified"] is True,
    str(_drift["engine"]["seal_verified"]),
)
check(
    "authority:unbound-is-not-claimed-as-agreement",
    rr_bridge.predicate_source("OBL-02", "OMISSION_OR_INCOMPLETE")["authority_binding"]
    == "unbound",
)
check(
    "authority:disagreement-is-reported",
    rr_bridge.predicate_source(
        "OBL-02", "OMISSION_OR_INCOMPLETE", {"decision_table_contract_sha256": "0" * 64}
    )["authority_binding"]
    == "differs_from_decision",
)
check(
    "authority:surface-added-classes-have-no-frozen-predicate",
    rr_bridge.predicate_source("OBL-02", "PROTOCOL_ERROR") is None,
)

# --- 9. BATCH: one wire call, N independent decisions ------------------------

check(
    "batch:advertised-in-tools-list",
    [t["name"] for t in rr_mcp_gate.TOOLS]
    == ["rr_gate_check", "rr_gate_batch", "rr_gate_explain"],
    str([t["name"] for t in rr_mcp_gate.TOOLS]),
)

_single_clean = rr_mcp_gate.gate_check(payload(CLEAN_REF))
_lines_before = len(
    [ln for ln in _TMP_LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
)
_batch = rr_mcp_gate.gate_batch(
    {
        "checks": [
            payload(CLEAN_REF),
            payload(dict(CLEAN_REF, returned="res://tickets/T-99")),
            payload({}),
        ]
    }
)
_lines_after = len(
    [ln for ln in _TMP_LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
)
check(
    "batch:order-preserved",
    [item["index"] for item in _batch["items"]] == [0, 1, 2],
    str([item["index"] for item in _batch["items"]]),
)
check(
    "batch:verdicts-match-the-single-call-pipeline",
    [item.get("verdict") for item in _batch["items"]] == ["NO_FINDING", "HOLD", "ABSTAIN"],
    str([item.get("verdict") for item in _batch["items"]]),
)
check(
    "batch:item-decision-id-equals-single-call-id",
    _batch["items"][0]["decision_id"] == _single_clean["decision_id"],
    f"{_batch['items'][0]['decision_id']} != {_single_clean['decision_id']}",
)
check(
    "batch:summary-counts",
    _batch["summary"]
    == {"items": 3, "no_finding": 1, "hold": 1, "abstain": 1, "errors": 0},
    json.dumps(_batch["summary"]),
)
check("batch:observe-posture-never-blocks", _batch["enforcement_action"] == "NONE")
check(
    "batch:every-item-appends-its-own-audit-line",
    _lines_after - _lines_before == 3,
    str(_lines_after - _lines_before),
)

# Per-item isolation: a raising item is reported at its index with the exception
# text and no verdict; siblings still get full decisions. Same monkeypatch
# pattern as the SEAL and TOTALITY negative arms.
_real_map = M.map_tool_result
try:

    def _exploding_map(arguments):
        if (
            isinstance(arguments, dict)
            and (arguments.get("call") or {}).get("tool") == "boom"
        ):
            raise RuntimeError("mapper exploded")
        return _real_map(arguments)

    M.map_tool_result = _exploding_map
    _boom = {
        "call": {"server": "docs", "tool": "boom", "record_reference": dict(CLEAN_REF)},
        "result": result(),
        "reliance": {"intent": "ACT_ON_RECORD"},
    }
    _isolated = rr_mcp_gate.gate_batch(
        {"checks": [payload(CLEAN_REF), _boom, payload({})]}
    )
    check(
        "batch:raising-item-reported-at-its-index",
        "error" in _isolated["items"][1]
        and "mapper exploded" in _isolated["items"][1]["error"]
        and "verdict" not in _isolated["items"][1],
        json.dumps(_isolated["items"][1]),
    )
    check(
        "batch:siblings-unaffected-by-raising-item",
        _isolated["items"][0].get("verdict") == "NO_FINDING"
        and _isolated["items"][2].get("verdict") == "ABSTAIN",
        str([item.get("verdict") for item in _isolated["items"]]),
    )
    check(
        "batch:error-counted-never-classified",
        _isolated["summary"]["errors"] == 1 and _isolated["summary"]["items"] == 3,
        json.dumps(_isolated["summary"]),
    )
    _wire_err = rr_mcp_gate.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 901,
            "method": "tools/call",
            "params": {
                "name": "rr_gate_batch",
                "arguments": {"checks": [payload(CLEAN_REF), _boom]},
            },
        },
        {},
    )
    check(
        "batch:wire-is-loud-when-any-item-was-not-judged",
        _wire_err["result"]["isError"] is True,
        json.dumps(_wire_err["result"].get("isError")),
    )
finally:
    M.map_tool_result = _real_map

_wire_hold = rr_mcp_gate.handle_message(
    {
        "jsonrpc": "2.0",
        "id": 902,
        "method": "tools/call",
        "params": {
            "name": "rr_gate_batch",
            "arguments": {
                "checks": [
                    payload(CLEAN_REF),
                    payload(dict(CLEAN_REF, returned="res://tickets/T-99")),
                ]
            },
        },
    },
    {},
)
check(
    "batch:hold-in-observe-is-a-classification-not-a-wire-error",
    _wire_hold["result"]["isError"] is False,
    str(_wire_hold["result"].get("isError")),
)

for bad, label in (
    ({}, "missing-checks"),
    ({"checks": []}, "empty-checks"),
    ({"checks": "not-a-list"}, "non-array-checks"),
    ("not an object", "non-object-arguments"),
    (
        {"checks": [payload(CLEAN_REF)] * (rr_mcp_gate.BATCH_MAX_ITEMS + 1)},
        "over-admission-bound",
    ),
):
    try:
        rr_mcp_gate.gate_batch(bad)
        check(f"batch:refuses-{label}", False)
    except ValueError:
        check(f"batch:refuses-{label}", True)

_one = rr_mcp_gate.gate_batch({"checks": [payload(CLEAN_REF)]})
check(
    "batch:batch-of-one-equals-single-call",
    _one["items"][0].get("decision_id") == _single_clean["decision_id"]
    and _one["summary"]["items"] == 1,
)

os.environ["RR_MCP_GATE_ENFORCE"] = "1"
try:
    _enforced_batch = rr_mcp_gate.gate_batch(
        {
            "checks": [
                payload(CLEAN_REF),
                payload(dict(CLEAN_REF, returned="res://tickets/T-99")),
            ]
        }
    )
    check(
        "batch:enforce-blocks-when-any-item-holds",
        _enforced_batch["enforcement_action"] == "BLOCK",
        _enforced_batch["enforcement_action"],
    )
    _enforced_clean = rr_mcp_gate.gate_batch({"checks": [payload(CLEAN_REF)]})
    check(
        "batch:enforce-passes-all-no-finding",
        _enforced_clean["enforcement_action"] == "NONE",
        _enforced_clean["enforcement_action"],
    )
finally:
    os.environ.pop("RR_MCP_GATE_ENFORCE", None)

# --- calibration ------------------------------------------------------------

report = rr_bridge.calibrate()
check(
    "calibration:pack-reproduces",
    report["reproduced"] == report["entries"] and not report["mismatches"],
    f"{report['reproduced']}/{report['entries']}",
)

print(f"rr-mcp-gate regression: checks={checks} failures={failures}")
sys.exit(1 if failures else 0)
