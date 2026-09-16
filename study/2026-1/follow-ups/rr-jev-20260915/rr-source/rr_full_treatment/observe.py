"""Independent wire/call-binding observation; imports no treatment or comparator.

This verifies the captured invocation and witness construction. It deliberately
does not convert a valid witness into evidence that the underlying assertions
are true or that the candidate's decision rule is scientifically useful.
"""
import base64
import hashlib
import json


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _hash(value):
    return hashlib.sha256(value).hexdigest().upper()


def _frame(value):
    return len(value).to_bytes(8, "big") + value


def verify(common, state, receipt, *, expected_package, expected_arm):
    if receipt["package"] != expected_package or receipt["arm"] != expected_arm:
        raise ValueError("Worker's reported package or arm differs from the controller request")
    output = base64.b64decode(receipt["output_b64"], validate=True)
    decision = json.loads(output)
    expected_fields = {"code", "disposition", "format", "input_digest", "occurrence", "pointer",
                       "reason", "remediation", "stage", "witness_digest"}
    if set(decision) != expected_fields or _canonical(decision) != output:
        raise ValueError("Decision is not the canonical ten-field document")
    if receipt["common_sha256"] != _hash(common) or receipt["state_sha256"] != _hash(state):
        raise ValueError("Worker invocation input identity differs from capture")
    if receipt["output_sha256"] != _hash(output) or receipt["observed"] is not True:
        raise ValueError("Missing exact output observation")
    arm = receipt["arm"]
    module = "S" if arm in ("S1", "S4") else arm
    if module not in ("U", "S", "R"):
        raise ValueError("Unregistered arm")
    entrypoint = ("DECIDE_" + module).encode("ascii")
    input_hash = _hash(b"RR-STUDY-TREATMENT-INPUT-5\0" + _frame(entrypoint) + _frame(common) + _frame(state))
    if input_hash != decision["input_digest"]:
        raise ValueError("Decision does not bind the actual COMMON/state bytes")
    constructors = receipt["constructions"]
    if len(constructors) != 1 or constructors[0]["output_sha256"] != _hash(output):
        raise ValueError("Missing or ambiguous decision construction")
    evidence = constructors[0]["evidence"]
    for key in ("code", "occurrence", "pointer", "stage"):
        if evidence[key] != decision[key]:
            raise ValueError("Observed evidence differs from the returned decision")
    if evidence["module"] not in (module, "PUBLIC_BOUNDARY"):
        raise ValueError("Witness module does not match the invoked arm")
    witness = _hash(b"RR-STUDY-TREATMENT-WITNESS-5\0" + _frame(entrypoint) + bytes.fromhex(input_hash)
                    + _frame(decision["disposition"].encode("ascii")) + _frame(decision["reason"].encode("ascii"))
                    + _frame(decision["remediation"].encode("ascii")) + _frame(_canonical(evidence)))
    if witness != decision["witness_digest"]:
        raise ValueError("Witness differs from the actually observed construction")
    imported = receipt["runtime_imports"]
    prefix = "rr_full_treatment.runtime_" + receipt["package"]
    if any(not name.startswith(prefix + ".") and name != prefix for name in imported):
        raise ValueError("More than one candidate package was imported")
    for other in {"u", "s", "r"} - {module.lower()}:
        if prefix + "." + other in imported:
            raise ValueError("Another arm was imported into the decision process")
    calls = receipt["engine_calls"]
    reached = module == "R" and (decision["code"].startswith(("R_ENGINE_", "R_LINEAGE_", "R_ACCEPTANCE_")))
    if len(calls) != int(reached):
        raise ValueError("Actual engine call count disagrees with reached pipeline stage")
    use_hash = engine_hash = None
    if calls:
        raw_request = base64.b64decode(calls[0]["request_b64"], validate=True)
        if _hash(raw_request) != calls[0]["request_sha256"]:
            raise ValueError("Observed engine request hash differs")
        request = json.loads(raw_request)
        document = json.loads(common)
        if request["decision_input"]["facts"] != document["guard_observation_facts"]:
            raise ValueError("Actual engine call used different guard observations")
        if request["inner_request"]["input"] != document["a2_raw_shared_bundle"]:
            raise ValueError("Actual engine call used a different receiver bundle")
        use_hash = _hash(_canonical(document["a2_raw_shared_bundle"]["use_records"][0]))
        engine_hash = _hash(_canonical(calls[0]["returned_envelope"]) + b"\n")
        if decision["code"].startswith("R_ACCEPTANCE_"):
            semantic = evidence["semantic_evidence"]
            if semantic["recorded_use_sha256"] != use_hash or semantic["engine_output_sha256"] != engine_hash:
                raise ValueError("Acceptance witness used stale use or engine evidence")
    return {"status": "EXACT_INVOCATION_OBSERVED", "common_sha256": _hash(common), "state_sha256": _hash(state),
            "output_sha256": _hash(output), "actual_engine_call_count": len(calls),
            "recorded_use_sha256": use_hash, "engine_output_sha256": engine_hash}
