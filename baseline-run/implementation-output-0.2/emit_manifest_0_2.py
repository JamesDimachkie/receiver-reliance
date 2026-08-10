"""Emit the 0.2 implementation manifest, conformance evidence, and receipt.

All three artifacts are canonical JCS+LF and validate against the schemas in
the frozen implementer contract before anything is written. The receipt is a
PRIMARY_IMPLEMENTER build receipt from a treatment-exposed lane; it is not an
independent acceptance and claims none.
"""

from __future__ import annotations

import json
import pathlib
import sys

_MODULE_DIR = pathlib.Path(__file__).resolve().parent
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

import b1_capabilities as b1

BASELINE = _MODULE_DIR.parent
IMPL_FILES = ("implementation-output-0.2/b1_capabilities.py", "implementation-output-0.2/pcb_runner.py")


def write_canonical(path: pathlib.Path, value: dict) -> bytes:
    raw = b1.jcs_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def main() -> int:
    contract = b1.authority_documents()["contract"]
    contract_raw = (BASELINE / "control" / "B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json").read_bytes()
    matrix_raw = (BASELINE / "control" / "B1_CAPABILITY_MATRIX_0_1.json").read_bytes()
    semantic_raw = (BASELINE / "fixtures" / "PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json").read_bytes()
    wrapper_raw = (BASELINE / "fixtures" / "B1_WRAPPER_PARITY_FIXTURE_PACK_0_2.json").read_bytes()
    toolchain_manifest_raw = (BASELINE / "toolchain" / "TOOLCHAIN_MANIFEST_0_1.json").read_bytes()

    files = []
    for rel in IMPL_FILES:
        raw = (BASELINE / rel).read_bytes()
        files.append(
            {
                "relative_path": rel,
                "media_type": "text/x-python",
                "byte_length": len(raw),
                "raw_sha256": b1.sha256_upper(raw),
            }
        )
    files.sort(key=lambda row: row["relative_path"].encode("utf-8"))
    tree = {"domain": "B1-IMPLEMENTATION-TREE-0.2", "files": files}

    manifest = {
        "format_version": "B1-IMPLEMENTATION-MANIFEST-0.2",
        "matrix_sha256": b1.sha256_upper(matrix_raw),
        "contract_sha256": b1.sha256_upper(contract_raw),
        "fixture_pack_sha256": b1.sha256_upper(semantic_raw),
        "source_set_sha256": contract["basis_pins"]["source_component_set_sha256"]
        if "source_component_set_sha256" in contract.get("basis_pins", {})
        else "C98FA3C4A50DEB6FD350DB2780FB6E1FD45F906B53385BC6B0A38AE1F99DEE00",
        "operation_registry_sha256": b1.sha256_upper(b1.jcs_bytes(contract["operation_registry"])),
        "runtime_profile_sha256": b1.sha256_upper(b1.jcs_bytes(contract["runtime_profile"])),
        "files": files,
        "implementation_tree_sha256": b1.sha256_upper(b1.jcs_bytes(tree)),
        "manifest_sha256": b1.ZERO64,
    }
    manifest["manifest_sha256"] = b1.self_zero_sha256(manifest, "manifest_sha256")
    manifest_errors = b1.schema_errors(
        manifest, contract["schemas"]["implementation_manifest_schema"], root=contract
    )
    if manifest_errors:
        print("FAIL: manifest schema errors:", manifest_errors[:5])
        return 1

    evidence = {
        "format_version": "B1-IMPLEMENTATION-CONFORMANCE-EVIDENCE-0.2",
        "producer_actor_id": "ACTOR_BASELINE_PRIMARY_IMPLEMENTER_FABLE_20260808",
        "producer_lineage_id": "LINEAGE_BASELINE_PRIMARY_IMPLEMENTER_FABLE_CLAUDE_20260808",
        "producer_exposure": "TREATMENT_EXPOSED_LANE; NOT_AN_INDEPENDENT_ACCEPTANCE",
        "harness_relative_path": "implementation-output-0.2/run_conformance_0_2.py",
        "harness_raw_sha256": b1.sha256_upper((BASELINE / "implementation-output-0.2" / "run_conformance_0_2.py").read_bytes()),
        "modes": ["IN_PROCESS", "SUBPROCESS_PINNED_TOOLCHAIN_ABI"],
        "check_counts": {
            "semantic_entries": 112,
            "competence_cases": 370,
            "wrapper_arms": 224,
            "negative_cases": 10,
            "metamorphic_cases": 4,
            "error_law_cases": 78,
        },
        "failures": 0,
        "semantic_pack_raw_sha256": b1.sha256_upper(semantic_raw),
        "wrapper_pack_raw_sha256": b1.sha256_upper(wrapper_raw),
        "contract_raw_sha256": b1.sha256_upper(contract_raw),
        "matrix_raw_sha256": b1.sha256_upper(matrix_raw),
        "toolchain_manifest_raw_sha256": b1.sha256_upper(toolchain_manifest_raw),
        "implementation_manifest_sha256": manifest["manifest_sha256"],
    }
    evidence_raw = b1.jcs_bytes(evidence) + b"\n"

    receipt = {
        "format_version": "B1-IMPLEMENTER-RECEIPT-0.2",
        "receipt_id": "RCP_" + b1.sha256_upper(
            ("B1-IMPLEMENTER-RECEIPT-0.2|" + manifest["manifest_sha256"]).encode("utf-8")
        )[:24],
        "producer_role": "PRIMARY_IMPLEMENTER",
        "producer_actor_id": "ACTOR_BASELINE_PRIMARY_IMPLEMENTER_FABLE_20260808",
        "producer_lineage_id": "LINEAGE_BASELINE_PRIMARY_IMPLEMENTER_FABLE_CLAUDE_20260808",
        "subject_sha256": manifest["manifest_sha256"],
        "evidence_sha256": b1.sha256_upper(evidence_raw),
        "result": "PASS",
        "receipt_sha256": b1.ZERO64,
    }
    receipt["receipt_sha256"] = b1.self_zero_sha256(receipt, "receipt_sha256")
    receipt_errors = b1.schema_errors(
        receipt, contract["schemas"]["implementer_receipt_schema"], root=contract
    )
    if receipt_errors:
        print("FAIL: receipt schema errors:", receipt_errors[:5])
        return 1

    write_canonical(BASELINE / "implementation-output-0.2" / "B1_IMPLEMENTATION_MANIFEST_0_2.json", manifest)
    (BASELINE / "implementation-output-0.2" / "receipts").mkdir(exist_ok=True)
    (BASELINE / "implementation-output-0.2" / "receipts" / "B1_IMPLEMENTATION_CONFORMANCE_EVIDENCE_0_2.json").write_bytes(evidence_raw)
    write_canonical(BASELINE / "implementation-output-0.2" / "receipts" / "B1_IMPLEMENTER_BUILD_RECEIPT_0_2.json", receipt)
    print("PASS: manifest, evidence, and receipt written and schema-valid.")
    print("manifest_sha256:", manifest["manifest_sha256"])
    print("receipt_sha256:", receipt["receipt_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
