"""The unified 30-operation decision law, assembled from sealed bytes.

Nothing here is transcribed: the class predicates, the class precedence order,
the per-operation ``facts`` schemas, the closure table and the operator
vocabulary are all read out of the pinned sources.  What this module *does* add
is a set of machine-checked structural invariants, so that any drift between
the 0.2 core and the 0.3 composition shows up as a hard failure rather than a
silent modelling error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import sources


@dataclass
class Operation:
    obligation_id: str
    operation_handle: str
    class_predicates: dict[str, Any]
    facts_schema: dict[str, Any]
    input_schema: dict[str, Any]  # full decision_input branch
    origin: str  # "0.2-core" | "0.3-supplemental"


@dataclass
class Law:
    class_precedence: list[str]  # includes VALID last
    defect_precedence: list[str]  # the three defect classes, in order
    operations: dict[str, Operation] = field(default_factory=dict)
    atomic_operators: dict[str, str] = field(default_factory=dict)
    closures: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    error_registry: list[dict[str, Any]] = field(default_factory=list)
    evaluation_result_contract: dict[str, Any] = field(default_factory=dict)
    invariants: list[dict[str, Any]] = field(default_factory=list)

    def ordered(self) -> list[Operation]:
        return [self.operations[k] for k in sorted(self.operations)]


def _check(invariants: list, name: str, ok: bool, detail: str = "") -> None:
    invariants.append({"invariant": name, "holds": bool(ok), "detail": detail})


def load_law() -> Law:
    inv: list[dict[str, Any]] = []

    c2 = sources.load_json("contract_0_2")
    c3 = sources.load_json("contract_0_3")
    closures_doc = sources.load_json("closures_0_4")

    # The 0.3 supplement pins the exact 0.2 contract bytes it inherits from.
    # This ties the file this model loaded to the sealed 0.2/0.3 chain.
    manifest = {s["name"]: s for s in sources.digest_manifest()}
    pinned_base = c3["semantic_decision_contract_supplement"]["inheritance"][
        "base_contract_raw_sha256"
    ]
    _check(
        inv,
        "loaded_0.2_bytes_match_0.3_inheritance_pin",
        manifest["contract_0_2"]["sha256"] == pinned_base,
        f"loaded={manifest['contract_0_2']['sha256']} pinned={pinned_base}",
    )
    pinned_matrix3 = c3["composed_matrix_reference"]
    m3 = sources.load_json("matrix_0_3")  # noqa: F841 - read for digest pinning
    manifest = {s["name"]: s for s in sources.digest_manifest()}
    _check(
        inv,
        "loaded_0.3_matrix_bytes_match_contract_pin",
        manifest["matrix_0_3"]["sha256"] == pinned_matrix3["raw_sha256"]
        and manifest["matrix_0_3"]["byte_length"] == pinned_matrix3["byte_length"],
        f"loaded={manifest['matrix_0_3']['sha256']} pinned={pinned_matrix3['raw_sha256']}",
    )

    sdc = c2["semantic_decision_contract"]
    precedence = list(sdc["class_precedence"])
    _check(inv, "class_precedence.length==4", len(precedence) == 4, str(precedence))
    _check(inv, "class_precedence.VALID_last", precedence[-1] == "VALID", precedence[-1])
    defect_precedence = precedence[:-1]

    law = Law(
        class_precedence=precedence,
        defect_precedence=defect_precedence,
        atomic_operators=dict(sdc["predicate_language"]["atomic_operators"]),
        error_registry=list(c2["error_registry"]),
        evaluation_result_contract=dict(sdc["evaluation_result_contract"]),
    )

    # ---- 0.2 core: 28 operations -----------------------------------------
    reg2 = c2["operation_registry"]
    table2 = sdc["operation_decision_table"]
    branches2 = {
        b["properties"]["obligation_id"]["const"]: b
        for b in c2["schemas"]["decision_input_schema"]["oneOf"]
    }
    _check(inv, "0.2.operation_registry.count==28", len(reg2) == 28, str(len(reg2)))
    _check(inv, "0.2.decision_table.count==28", len(table2) == 28, str(len(table2)))
    _check(inv, "0.2.input_schema.branches==28", len(branches2) == 28, str(len(branches2)))

    handle_by_obl2 = {r["obligation_id"]: r["operation_handle"] for r in reg2}

    # ---- 0.3 composition: +2 operations -----------------------------------
    sup = c3["semantic_decision_contract_supplement"]
    table3 = sup["supplemental_operation_decision_table"]
    reg3 = c3["composed_operation_registry"]
    branches3 = {
        b["properties"]["obligation_id"]["const"]: b
        for b in c3["schemas"]["decision_input_schema"]["oneOf"]
    }
    _check(inv, "0.3.supplemental_table.count==2", len(table3) == 2, str(len(table3)))
    _check(inv, "0.3.composed_registry.count==30", len(reg3) == 30, str(len(reg3)))
    _check(inv, "0.3.input_schema.branches==30", len(branches3) == 30, str(len(branches3)))

    # The composed schema must be a conservative extension of the 0.2 schema for
    # the 28 inherited rows; otherwise the 0.2 rows are not the same law.
    drift = sorted(
        obl for obl, b in branches2.items() if branches3.get(obl) != b
    )
    _check(
        inv,
        "0.3.input_schema.conservative_extension_of_0.2",
        not drift,
        f"drifted={drift}" if drift else "all 28 inherited branches byte-identical after JSON load",
    )

    # 0.3 inherits the 28 accepted rows "unchanged, by reference": no
    # supplemental row may redefine one.
    dup = sorted({r["obligation_id"] for r in table3} & set(handle_by_obl2))
    _check(inv, "0.3.supplement_does_not_redefine_0.2_rows", not dup, f"redefined={dup}")

    handle_by_obl3 = {r["obligation_id"]: r["operation_handle"] for r in reg3}
    mismatch = sorted(
        obl for obl, h in handle_by_obl2.items() if handle_by_obl3.get(obl) != h
    )
    _check(
        inv,
        "0.3.composed_registry_preserves_0.2_handles",
        not mismatch,
        f"mismatched={mismatch}",
    )

    for row in table2:
        obl = row["obligation_id"]
        branch = branches2[obl]
        law.operations[obl] = Operation(
            obligation_id=obl,
            operation_handle=row["operation_handle"],
            class_predicates=row["class_predicates"],
            facts_schema=branch["properties"]["facts"],
            input_schema=branch,
            origin="0.2-core",
        )
    for row in table3:
        obl = row["obligation_id"]
        branch = branches3[obl]
        law.operations[obl] = Operation(
            obligation_id=obl,
            operation_handle=row["operation_handle"],
            class_predicates=row["class_predicates"],
            facts_schema=branch["properties"]["facts"],
            input_schema=branch,
            origin="0.3-supplemental",
        )

    _check(inv, "law.operations==30", len(law.operations) == 30, str(len(law.operations)))

    # Every operation declares exactly the four classes, and the VALID row is
    # the structural fall-through operator.  Both are prerequisites for the
    # totality argument in PROOF_REPORT.md.
    bad_classes = sorted(
        o.obligation_id
        for o in law.operations.values()
        if sorted(o.class_predicates) != sorted(precedence)
    )
    _check(inv, "every_operation_declares_all_four_classes", not bad_classes, str(bad_classes))

    bad_valid = sorted(
        o.obligation_id
        for o in law.operations.values()
        if o.class_predicates.get("VALID") != {"op": "NO_EARLIER_CLASS_MATCH"}
    )
    _check(
        inv,
        "VALID_row_is_exactly_NO_EARLIER_CLASS_MATCH",
        not bad_valid,
        str(bad_valid),
    )

    # Registry <-> table handle agreement (both directions).
    bad_handles = sorted(
        obl
        for obl, op in law.operations.items()
        if handle_by_obl3.get(obl) != op.operation_handle
    )
    _check(inv, "decision_table_handles_match_registry", not bad_handles, str(bad_handles))
    _check(
        inv,
        "operation_handles_unique",
        len({o.operation_handle for o in law.operations.values()}) == 30,
    )

    # ---- closures ---------------------------------------------------------
    law.closures = dict(closures_doc["closures_by_obligation"])
    unknown = sorted(set(law.closures) - set(law.operations))
    _check(inv, "closures_reference_known_operations", not unknown, str(unknown))
    tighten_targets = {
        c["tightens_to"] for rows in law.closures.values() for c in rows
    }
    _check(
        inv,
        "closure_targets_are_defect_classes",
        tighten_targets <= set(defect_precedence),
        str(sorted(tighten_targets)),
    )

    law.invariants = inv
    return law
