"""Regression suite for the grounded 0.4 layer.

Checks, in order:
  1. PARITY  - decide() reproduces every frozen semantic fixture response
              byte-for-byte across both packs (the layer changes nothing
              about the sealed surface).
  2. TRACE   - decide_audited() never diverges from the sealed class, and
              every non-VALID audited fixture decision carries a nonempty
              witness trace.
  3. BINDING - two requests with different fact profiles can no longer share
              an audit seal (the external review's OBL-08 probe, re-run
              against the audited surface).
  4. CLOSURE - the review's OBL-30 probes (inverted verdicts; stale selected
              set) classify as defects on the audited surface, while the
              clean fixture stays VALID with zero closure findings.

Exit 0 with 'failures=0' on success.
"""
from __future__ import annotations

import base64
import copy
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import rr_api  # noqa: E402
from rr_api import b1  # noqa: E402

failures = 0
checks = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures, checks
    checks += 1
    if not ok:
        failures += 1
        print(f"FAIL {name} {detail}")


def load_pack(rel: str) -> dict:
    return json.load(open(REPO / rel, encoding="utf-8"))


PACKS = [
    "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json",
    "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
]

# 1. PARITY + 2. TRACE over every semantic fixture entry
for rel in PACKS:
    pack = load_pack(rel)
    for entry in pack["entries"]:
        raw = base64.b64decode(entry["semantic_request_jcs_lf_base64"])
        expected = base64.b64decode(entry["expected_response_jcs_lf_base64"])
        response, _exit = rr_api.decide(raw)
        got = b1.jcs_bytes(response) + b"\n"
        check(f"parity:{entry['entry_id']}", got == expected)
        audited = rr_api.decide_audited(raw)
        sealed = b1.jcs_bytes(audited["sealed_response"]) + b"\n"
        check(f"audit-parity:{entry['entry_id']}", sealed == expected)
        seal_ok = audited["audit_sha256"] == b1.self_zero_sha256(audited, "audit_sha256")
        check(f"audit-seal:{entry['entry_id']}", seal_ok)
        if audited["sealed_response"].get("ok"):
            sealed_class = audited["sealed_response"]["output"]["result_object"]["behavior_class"]
            if sealed_class != "VALID":
                check(
                    f"witness-nonempty:{entry['entry_id']}",
                    bool(audited["audit"]["matched_class_witness"]),
                )
            frozen_closures = [
                f for f in audited["audit"]["closure_findings"] if f.get("fired")
            ]
            if sealed_class == "VALID" and entry["entry_id"].startswith("SEMFX") and "OBL-30" not in entry["entry_id"]:
                check(
                    f"closure-quiet:{entry['entry_id']}",
                    audited["audited_behavior_class"] == "VALID",
                    str(frozen_closures),
                )

# 3. BINDING: the OBL-08 substitution probe against the audited surface
pack02 = load_pack(PACKS[0])
e08 = next(e for e in pack02["entries"] if "OBL-08-IO" in e["entry_id"])
r08 = json.loads(base64.b64decode(e08["semantic_request_jcs_lf_base64"]).decode())
mut08 = copy.deepcopy(r08)
mut08["decision_input"]["facts"]["actor_id"] = "ACTOR_TOTALLY_DIFFERENT"
mut08["decision_input"]["facts"]["capability_id"] = "CAPABILITY_NUKE_PROD"
a_base = rr_api.decide_audited(r08)
a_mut = rr_api.decide_audited(mut08)
check(
    "binding:different-facts-different-audit-seal",
    a_base["audit_sha256"] != a_mut["audit_sha256"],
)
check(
    "binding:different-facts-different-input-digest",
    a_base["audit"]["decision_input_sha256"] != a_mut["audit"]["decision_input_sha256"],
)
check(
    "binding:sealed-receipts-still-identical-documenting-frozen-gap",
    a_base["sealed_response"]["receipt_sha256"] == a_mut["sealed_response"]["receipt_sha256"],
)

# 4. CLOSURE: the review's OBL-30 probes
pack03 = load_pack(PACKS[1])
e30 = next(e for e in pack03["entries"] if "OBL-30-IO" in e["entry_id"])
r30 = json.loads(base64.b64decode(e30["semantic_request_jcs_lf_base64"]).decode())

clean = rr_api.decide_audited(r30)
check("closure:clean-io-stays-valid", clean["audited_behavior_class"] == "VALID")
check(
    "closure:clean-io-zero-findings",
    not [f for f in clean["audit"]["closure_findings"] if f.get("fired")],
)

inverted = copy.deepcopy(r30)
for row in inverted["decision_input"]["facts"]["compatibility_verdicts"]:
    row["compatible"] = not row["compatible"]
a_inv = rr_api.decide_audited(inverted)
check(
    "closure:inverted-verdicts-now-conflict",
    a_inv["audited_behavior_class"] == "BINDING_OR_CONFLICT",
    a_inv["audited_behavior_class"],
)

stale = copy.deepcopy(r30)
stale["decision_input"]["facts"]["selected_record_ids"] = (
    stale["decision_input"]["facts"]["selected_record_ids"][:1]
)
a_stale = rr_api.decide_audited(stale)
check(
    "closure:stale-selected-now-omission",
    a_stale["audited_behavior_class"] == "OMISSION_OR_INCOMPLETE",
    a_stale["audited_behavior_class"],
)
check(
    "closure:stale-selected-c3-fired",
    any(
        f.get("fired") and f["closure_id"].startswith("OBL-30-C3")
        for f in a_stale["audit"]["closure_findings"]
    ),
)

# record references derived, not hardcoded-empty
check(
    "references:obl30-carries-pool-ids",
    "REC_A" in clean["audit"]["record_references"],
    str(clean["audit"]["record_references"]),
)

# 5. GOVERNANCE - audited decisions identify the exact policy bytes that
#    governed them (ERRATA E8), and an errored closure evaluator can never
#    silently certify VALID (ERRATA E9).
gov = clean["audit"]["governing_authorities"]
check(
    "governance:closed-key-set",
    set(gov)
    == {
        "closure_policy_sha256",
        "authority_register_sha256",
        "engine_capabilities_sha256",
        "engine_runner_sha256",
    },
    str(sorted(gov)),
)
for gov_key, gov_path in (
    ("closure_policy_sha256", HERE / "closures_0_4.json"),
    ("authority_register_sha256", HERE / "authority_register_0_4.json"),
    (
        "engine_capabilities_sha256",
        REPO / "baseline-run" / "implementation-output-0.3" / "b1_capabilities.py",
    ),
    (
        "engine_runner_sha256",
        REPO / "baseline-run" / "implementation-output-0.3" / "pcb_runner.py",
    ),
):
    check(
        f"governance:{gov_key}-matches-disk",
        gov[gov_key] == b1.sha256_upper(gov_path.read_bytes()),
        gov[gov_key],
    )
check("governance:format-bumped", clean["format_version"] == "B1-AUDITED-DECISION-0.4.1")
gov_mut = copy.deepcopy(clean)
gov_mut["audit"]["governing_authorities"]["closure_policy_sha256"] = "0" * 64
check(
    "governance:seal-covers-governing-digests",
    b1.self_zero_sha256(gov_mut, "audit_sha256") != clean["audit_sha256"],
)
_obl30_rows = rr_api._CLOSURES.get("OBL-30", [])
_broken_row = {
    "closure_id": "TEST-BROKEN-EVALUATOR",
    "predicate": {"op": "NO_SUCH_OPERATOR"},
    "tightens_to": "BINDING_OR_CONFLICT",
    "statement": "forced evaluator error for the E9 regression",
}
_obl30_rows.append(_broken_row)
try:
    incomplete = rr_api.decide_audited(r30)
finally:
    _obl30_rows.remove(_broken_row)
check(
    "governance:evaluator-error-fails-closed",
    incomplete["audited_behavior_class"] == "AUDIT_INCOMPLETE",
    incomplete["audited_behavior_class"],
)
check(
    "governance:evaluator-error-recorded",
    any(
        "evaluator_error" in finding
        for finding in incomplete["audit"]["closure_findings"]
    ),
)
check(
    "governance:clean-baseline-unaffected",
    rr_api.decide_audited(r30)["audited_behavior_class"] == "VALID",
)
check(
    "governance:reference-truncation-disclosed-false",
    clean["audit"]["record_references_truncated"] is False,
)
_many = {"pool_record_ids": [f"REC_{i:04d}" for i in range(70)]}
_refs_capped, _refs_flag = rr_api._derive_record_references_full(_many)
check(
    "governance:reference-truncation-caps-at-64-and-flags",
    len(_refs_capped) == 64 and _refs_flag is True,
    f"{len(_refs_capped)} {_refs_flag}",
)
_exact = {"pool_record_ids": [f"REC_{i:04d}" for i in range(64)]}
_refs_capped, _refs_flag = rr_api._derive_record_references_full(_exact)
check(
    "governance:reference-exact-64-not-flagged",
    len(_refs_capped) == 64 and _refs_flag is False,
    f"{len(_refs_capped)} {_refs_flag}",
)

print(f"grounded-0.4 regression: checks={checks} failures={failures}")
sys.exit(1 if failures else 0)
