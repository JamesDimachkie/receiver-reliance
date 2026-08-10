"""Contract lint — the anti-recurrence gate for the external review's
confirmed defect classes. Run in CI (--gate) and locally (--report).

What it makes structurally impossible to reintroduce silently:

  L1  UNDECLARED INERT FIELDS (review finding: engine validates
      caller-provided conclusions; 24 required fields never referenced).
      Every schema-required fact field of every operation must appear in
      authority_register_0_4.json, and the register must agree with the
      predicate tables in BOTH directions: 'semantic' entries must really
      be referenced by a value-comparing predicate; fields that are not
      must carry a disclosed status and rationale. A new operation whose
      schema demands fields its predicates ignore fails CI unless its
      author registers the non-authority explicitly.

  L2  WIRE-FORMAT COLLISIONS (review finding: 0.2 and 0.3 advertise the
      same request format with incompatible surfaces). Every distinct
      generation surface must declare a distinct request format string;
      the one recorded collision is grandfathered by name and referenced
      to ERRATA.md — any new duplicate fails CI.

  L3  CLOSURE DIRECTION (0.4 design law): every closure predicate must
      tighten to a defect class; a closure that could weaken or reclassify
      toward VALID fails CI.

Exit 0 when gate passes; nonzero with a finding list otherwise.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "baseline-run" / "implementation-output-0.3"))
import b1_capabilities as b1  # noqa: E402

PRESENCE_OPS = {"ABSENT", "PRESENT", "ANY_ABSENT", "ANY_NULL"}
PATH_KEYS = (
    "path", "left", "right", "paths", "value_path", "collection_path",
    "base64_path", "digest_path", "boolean_path", "enum_path", "current",
    "prior", "lower", "upper",
)
VALUE_IS_PATH = {"OUTSIDE_HALF_OPEN"}
DEFECT_CLASSES = {"MALFORMED_OR_BOUNDARY", "BINDING_OR_CONFLICT", "OMISSION_OR_INCOMPLETE"}


def collect_refs(node, refs: set[str], presence_only: set[str]) -> None:
    if not isinstance(node, dict):
        return
    if "all" in node or "any" in node:
        for child in node.get("all", []) + node.get("any", []):
            collect_refs(child, refs, presence_only)
        return
    if "not" in node:
        collect_refs(node["not"], refs, presence_only)
        return
    op = node.get("op")
    here: list[str] = []
    for key in PATH_KEYS:
        if key in node:
            value = node[key]
            if isinstance(value, list):
                here.extend(x for x in value if isinstance(x, str) and x.startswith("/"))
            elif isinstance(value, str) and value.startswith("/"):
                here.append(value)
    if op in VALUE_IS_PATH and isinstance(node.get("value"), str) and node["value"].startswith("/"):
        here.append(node["value"])
    for pointer in here:
        refs.add(pointer)
        if op in PRESENCE_OPS:
            presence_only.add(pointer)


def top_field(pointer: str) -> str | None:
    parts = pointer.split("/")
    return parts[2] if len(parts) >= 3 and parts[1] == "facts" else None


def main() -> int:
    gate = "--gate" in sys.argv
    findings: list[str] = []
    docs = b1.authority_documents()
    register = json.load(open(HERE / "authority_register_0_4.json", encoding="utf-8"))
    closures = json.load(open(HERE / "closures_0_4.json", encoding="utf-8"))

    table: dict[str, dict] = {}
    for row in docs["base_contract"]["semantic_decision_contract"]["operation_decision_table"]:
        table[row["operation_handle"]] = row
    for row in docs["contract"]["semantic_decision_contract_supplement"][
        "supplemental_operation_decision_table"
    ]:
        table[row["operation_handle"]] = row

    di_schema = docs["contract"]["schemas"]["decision_input_schema"]
    branches = di_schema.get("oneOf") or di_schema.get("anyOf") or []
    required_by_ob: dict[str, list[str]] = {}
    for branch in branches:
        props = branch.get("properties", {})
        ob = props.get("obligation_id", {}).get("const")
        if ob:
            required_by_ob[ob] = list(props.get("facts", {}).get("required", []))

    reg_by_ob = {op["obligation_id"]: {f["field"]: f for f in op["fields"]} for op in register["operations"]}

    # L1 both directions
    for handle, row in sorted(table.items()):
        ob = row["obligation_id"]
        refs: set[str] = set()
        presence: set[str] = set()
        for predicate in row["class_predicates"].values():
            collect_refs(predicate, refs, presence)
        semantic_fields = {top_field(p) for p in refs - presence} - {None}
        referenced_fields = {top_field(p) for p in refs} - {None}
        reg = reg_by_ob.get(ob)
        if reg is None:
            findings.append(f"L1: {ob} has no authority-register entry")
            continue
        for field in required_by_ob.get(ob, []):
            entry = reg.get(field)
            if entry is None:
                findings.append(f"L1: {ob}.{field} required by schema but absent from register")
                continue
            if entry["status"] == "semantic" and field not in semantic_fields:
                findings.append(
                    f"L1: {ob}.{field} registered semantic but no value-comparing predicate references it"
                )
            if entry["status"] != "semantic" and field in semantic_fields:
                findings.append(
                    f"L1: {ob}.{field} registered {entry['status']} but predicates DO reference it semantically (stale register)"
                )
            if entry["status"].startswith("inert") and field in referenced_fields:
                findings.append(
                    f"L1: {ob}.{field} registered inert but predicates reference it (stale register)"
                )
        for field in reg:
            if field not in required_by_ob.get(ob, []):
                findings.append(f"L1: {ob}.{field} in register but not schema-required (stale register)")

    # L2 wire-format uniqueness with grandfathered erratum
    surfaces = {
        "accepted-0.2": "B1-SEMANTIC-DECISION-REQUEST-0.2",
        "composed-0.3": b1.CORE_REQUEST_FORMAT,
    }
    grandfathered = {
        (row["format"], tuple(sorted(row["generations"])))
        for row in register.get("grandfathered_wire_format_collisions", [])
    }
    seen: dict[str, list[str]] = {}
    for generation, fmt in surfaces.items():
        seen.setdefault(fmt, []).append(generation)
    for fmt, generations in seen.items():
        if len(generations) > 1 and (fmt, tuple(sorted(generations))) not in grandfathered:
            findings.append(f"L2: wire format {fmt!r} shared by {generations} without a grandfathered erratum")

    # L3 closures tighten-only
    for ob, rows in closures["closures_by_obligation"].items():
        for row in rows:
            if row.get("tightens_to") not in DEFECT_CLASSES:
                findings.append(f"L3: closure {row.get('closure_id')} tightens_to {row.get('tightens_to')!r} (must be a defect class)")

    # Report
    from collections import Counter
    statuses = Counter(
        f["status"] for op in register["operations"] for f in op["fields"]
    )
    print(f"authority ledger: {dict(sorted(statuses.items()))} of {sum(statuses.values())} required fields")
    if findings:
        for finding in findings:
            print(finding)
        print(f"lint: {len(findings)} findings")
        return 1 if gate else 0
    print("lint: 0 findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
