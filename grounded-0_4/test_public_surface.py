"""Public-surface regressions: the supported decision API binds facts and closures.

Pins the 2026-08-16 hardening (deep-scan csf_abbd6848 / csf_0479d1a9):

  1. WITHDRAWAL — the package exports no bare `decide`; frozen execution is
     reachable only as the explicitly non-evidentiary conformance surface.
  2. FACT BINDING — audited decisions over materially different facts never
     share a `decision_input_sha256` (the bare route's receipts did).
  3. CLOSURE AUTHORITY — an OBL-30 request with inverted
     `compatibility_verdicts` classifies as a defect on the supported
     surface even though the frozen engine seals VALID for the same bytes.

Run: py -3.12 -B grounded-0_4/test_public_surface.py
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "grounded-0_4"))

CHECKS = 0


def check(name: str, cond: bool) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        raise AssertionError(name)


def load_pack() -> dict:
    pack = REPO / "baseline-run" / "fixtures" / "PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json"
    return json.loads(pack.read_text(encoding="utf-8"))


def load_pack03() -> dict:
    pack = REPO / "supplemental-0_3" / "fixtures" / "B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json"
    return json.loads(pack.read_text(encoding="utf-8"))


def entry_for(pack: dict, obligation_id: str, kind: str = "-IO-") -> dict:
    for e in pack["entries"]:
        if e["obligation_id"] == obligation_id and kind in e["entry_id"]:
            return copy.deepcopy(e["semantic_request"])
    raise AssertionError(f"no {kind} entry for {obligation_id}")


def main() -> int:
    import receiver_reliance as rr

    # --- 1. withdrawal ------------------------------------------------------
    check("no top-level decide attribute", not hasattr(rr, "decide"))
    check("decide absent from __all__", "decide" not in rr.__all__)
    check("decide_audited exported", "decide_audited" in rr.__all__)
    from receiver_reliance import conformance

    pkg_api = sys.modules["receiver_reliance._rr_api"]
    check(
        "conformance.execute is the renamed frozen executor",
        conformance.execute is pkg_api.conformance_execute,
    )
    check(
        "rr_api exports no bare decide",
        not hasattr(pkg_api, "decide"),
    )

    pack = load_pack()

    # --- 2. fact binding on the supported surface ---------------------------
    base = entry_for(pack, "OBL-26")
    variant = copy.deepcopy(base)
    variant["decision_input"]["facts"]["invocation_nonce"] = "NONCE_PUBLIC_SURFACE_VARIANT"
    a = rr.decide_audited(base)
    b = rr.decide_audited(variant)
    check(
        "different facts => different audited input seals",
        a["audit"]["decision_input_sha256"] != b["audit"]["decision_input_sha256"],
    )

    # --- 3. closure authority on the supported surface ----------------------
    pack03 = load_pack03()
    obl30 = copy.deepcopy(
        next(e for e in pack03["entries"] if "OBL-30-IO" in e["entry_id"])["semantic_request"]
    )
    facts = obl30["decision_input"]["facts"]
    verdicts = facts.get("compatibility_verdicts")
    check("OBL-30 fixture carries compatibility_verdicts rows", isinstance(verdicts, list) and verdicts)
    for row in verdicts:
        check("verdict row carries a boolean", isinstance(row.get("compatible"), bool))
        row["compatible"] = not row["compatible"]
    audited = rr.decide_audited(obl30)
    sealed_class = (
        (audited["sealed_response"].get("output") or {}).get("result_object") or {}
    ).get("behavior_class")
    audited_class = audited["audited_behavior_class"]
    check("frozen engine still seals VALID for contradicted bookkeeping", sealed_class == "VALID")
    check(
        "supported surface tightens inverted verdicts to a defect class",
        audited_class == "BINDING_OR_CONFLICT",
    )
    fired = [f for f in audited["audit"]["closure_findings"] if f.get("fired")]
    check("at least one OBL-30 closure fired", len(fired) >= 1)

    print(f"PUBLIC-SURFACE PASS: {CHECKS} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
