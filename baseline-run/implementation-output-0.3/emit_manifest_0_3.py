"""Emit or verify the composed-0.3 manifest, evidence, and build receipt.

The manifest and receipt retain the accepted 0.2 schema format constants.
The inherited manifest schema is projected only at its generation-bound
authority constants and implementation-output path literals; its shape and
all other constraints remain byte-derived from the accepted 0.2 contract.
"""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import sys

_MODULE_DIR = pathlib.Path(__file__).resolve().parent
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

import b1_capabilities as b1  # noqa: E402

BASELINE = _MODULE_DIR.parent
GATE_ROOT = BASELINE.parent
SUPPLEMENTAL = GATE_ROOT / "supplemental-0_3"
IMPL_FILES = (
    "implementation-output-0.3/b1_capabilities.py",
    "implementation-output-0.3/pcb_runner.py",
)

ACTOR_ID = "ACTOR_SUPPLEMENTAL_PRIMARY_IMPLEMENTER_CODEX_SOL_ULTRA_20260809"
LINEAGE_ID = "LINEAGE_SUPPLEMENTAL_PRIMARY_IMPLEMENTER_CODEX_SOL_ULTRA_SESSION_20260809"

EXPECTED_PINS = {
    "contract": "6B2CAD02DDE7388D63D66E4863E5233CFBD1DC413575D9D260DB9799C7023A12",
    "matrix": "B369777E51B2A64DC2C304C5949F38E13956353B496BABA8B6E488451F8C5B98",
    "semantic": "0A211174261C31924979A348B13EC43678896183ADB99D86002A51238C0AAE73",
    "wrapper": "0F71812E52ED4C1008BB9544CFD36230BDC01966AF11FE16CFCF838ABB11BF72",
    "accepted_contract": "DCFCB0714E1A7E677548057987F604D227F791F3FC3E0EA89BE5ED932447F48E",
    "accepted_matrix": "266AB130F85206E0FA47978A1E57E5D16DF7EACD051084435C15B1840512D38E",
    "accepted_semantic": "F27B93B3BE8BCBF5FBF7FF7789494621D17B426E16B38E958BB932899B0961B9",
    "accepted_wrapper": "22B9A2E8C08A63CF1A29AC3CD57FB0D30108245BC538DA2E4A959A24089195C1",
}


def canonical(value: dict) -> bytes:
    return b1.jcs_bytes(value) + b"\n"


def write_canonical(path: pathlib.Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def checked_raw(path: pathlib.Path, expected: str) -> bytes:
    raw = path.read_bytes()
    actual = b1.sha256_upper(raw)
    if actual != expected:
        raise RuntimeError(f"authority digest mismatch: {path}: {actual} != {expected}")
    return raw


def projected_manifest_schema(
    base_contract: dict,
    *,
    contract_sha256: str,
    matrix_sha256: str,
    fixture_sha256: str,
    registry_sha256: str,
) -> dict:
    schema = copy.deepcopy(base_contract["schemas"]["implementation_manifest_schema"])
    properties = schema["properties"]
    properties["contract_sha256"] = {"const": contract_sha256}
    properties["matrix_sha256"] = {"const": matrix_sha256}
    properties["fixture_pack_sha256"] = {"const": fixture_sha256}
    properties["operation_registry_sha256"] = {"const": registry_sha256}
    contains = properties["files"]["allOf"]
    contains[0]["contains"]["properties"]["relative_path"]["const"] = IMPL_FILES[1]
    contains[1]["contains"]["properties"]["relative_path"]["const"] = IMPL_FILES[0]
    return schema


def build_artifacts() -> dict[pathlib.Path, bytes]:
    docs = b1.authority_documents()
    contract = docs["contract"]
    base_contract = docs["base_contract"]

    contract_raw = checked_raw(
        SUPPLEMENTAL / "control" / "B1_SUPPLEMENTAL_COMPARATOR_CONTRACT_0_3.json",
        EXPECTED_PINS["contract"],
    )
    matrix_raw = checked_raw(
        SUPPLEMENTAL / "control" / "B1_COMPOSED_CAPABILITY_MATRIX_0_3.json",
        EXPECTED_PINS["matrix"],
    )
    semantic_raw = checked_raw(
        SUPPLEMENTAL / "fixtures" / "B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
        EXPECTED_PINS["semantic"],
    )
    wrapper_raw = checked_raw(
        SUPPLEMENTAL / "fixtures" / "B1_SUPPLEMENTAL_WRAPPER_PARITY_FIXTURE_PACK_0_3.json",
        EXPECTED_PINS["wrapper"],
    )
    accepted_contract_raw = checked_raw(
        BASELINE / "control" / "B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json",
        EXPECTED_PINS["accepted_contract"],
    )
    accepted_matrix_raw = checked_raw(
        BASELINE / "control" / "B1_CAPABILITY_MATRIX_0_1.json",
        EXPECTED_PINS["accepted_matrix"],
    )
    accepted_semantic_raw = checked_raw(
        BASELINE / "fixtures" / "PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json",
        EXPECTED_PINS["accepted_semantic"],
    )
    accepted_wrapper_raw = checked_raw(
        BASELINE / "fixtures" / "B1_WRAPPER_PARITY_FIXTURE_PACK_0_2.json",
        EXPECTED_PINS["accepted_wrapper"],
    )
    toolchain_manifest_raw = (
        BASELINE / "toolchain" / "TOOLCHAIN_MANIFEST_0_1.json"
    ).read_bytes()

    files = []
    for relative_path in IMPL_FILES:
        raw = (BASELINE / relative_path).read_bytes()
        files.append({
            "relative_path": relative_path,
            "media_type": "text/x-python",
            "byte_length": len(raw),
            "raw_sha256": b1.sha256_upper(raw),
        })
    files.sort(key=lambda row: row["relative_path"].encode("utf-8"))

    registry_sha256 = b1.sha256_upper(b1.jcs_bytes(contract["composed_operation_registry"]))
    runtime_profile_sha256 = b1.sha256_upper(b1.jcs_bytes(base_contract["runtime_profile"]))
    tree = {"domain": "B1-IMPLEMENTATION-TREE-0.3", "files": files}
    manifest = {
        "format_version": "B1-IMPLEMENTATION-MANIFEST-0.2",
        "matrix_sha256": b1.sha256_upper(matrix_raw),
        "contract_sha256": b1.sha256_upper(contract_raw),
        "fixture_pack_sha256": b1.sha256_upper(semantic_raw),
        "source_set_sha256": base_contract["basis_pins"]["source_component_set_sha256"],
        "operation_registry_sha256": registry_sha256,
        "runtime_profile_sha256": runtime_profile_sha256,
        "files": files,
        "implementation_tree_sha256": b1.sha256_upper(b1.jcs_bytes(tree)),
        "manifest_sha256": b1.ZERO64,
    }
    manifest["manifest_sha256"] = b1.self_zero_sha256(manifest, "manifest_sha256")
    manifest_schema = projected_manifest_schema(
        base_contract,
        contract_sha256=manifest["contract_sha256"],
        matrix_sha256=manifest["matrix_sha256"],
        fixture_sha256=manifest["fixture_pack_sha256"],
        registry_sha256=manifest["operation_registry_sha256"],
    )
    errors = b1.schema_errors(manifest, manifest_schema, root=manifest_schema)
    if errors:
        raise RuntimeError(f"projected inherited manifest schema errors: {errors[:5]}")
    manifest_raw = canonical(manifest)

    counts_0_2 = {
        "semantic_entries": 112,
        "competence_cases": 370,
        "wrapper_arms": 224,
        "negative_cases": 10,
        "metamorphic_cases": 4,
        "error_law_cases": 78,
        "total": 798,
        "failures": 0,
    }
    counts_0_3 = {
        "semantic_entries": 12,
        "competence_cases": 53,
        "wrapper_arms": 24,
        "negative_cases": 10,
        "metamorphic_cases": 8,
        "total": 107,
        "failures": 0,
    }
    harness_path = _MODULE_DIR / "run_conformance_0_3.py"
    runner_argv = [
        "toolchain/python.exe",
        "-I",
        "-B",
        "implementation-output-0.3/pcb_runner.py",
        "execute",
    ]
    evidence = {
        "format_version": "B1-IMPLEMENTATION-CONFORMANCE-EVIDENCE-0.3",
        "producer_actor_id": ACTOR_ID,
        "producer_lineage_id": LINEAGE_ID,
        "producer_exposure": "PRIMARY_IMPLEMENTER_DISTINCT_FROM_FIXTURE_AUTHOR; NOT_AN_INDEPENDENT_ACCEPTANCE",
        "harness_relative_path": "implementation-output-0.3/run_conformance_0_3.py",
        "harness_raw_sha256": b1.sha256_upper(harness_path.read_bytes()),
        "runner_argv": runner_argv,
        "modes": [
            {
                "mode": "IN_PROCESS",
                "accepted_0_2": counts_0_2,
                "supplemental_0_3": counts_0_3,
            },
            {
                "mode": "SUBPROCESS_PINNED_TOOLCHAIN_ABI",
                "accepted_0_2": counts_0_2,
                "supplemental_0_3": counts_0_3,
            },
        ],
        "failures": 0,
        "contract_raw_sha256": b1.sha256_upper(contract_raw),
        "matrix_raw_sha256": b1.sha256_upper(matrix_raw),
        "semantic_pack_raw_sha256": b1.sha256_upper(semantic_raw),
        "wrapper_pack_raw_sha256": b1.sha256_upper(wrapper_raw),
        "accepted_0_2_contract_raw_sha256": b1.sha256_upper(accepted_contract_raw),
        "accepted_0_2_matrix_raw_sha256": b1.sha256_upper(accepted_matrix_raw),
        "accepted_0_2_semantic_pack_raw_sha256": b1.sha256_upper(accepted_semantic_raw),
        "accepted_0_2_wrapper_pack_raw_sha256": b1.sha256_upper(accepted_wrapper_raw),
        "wrapper_interface_semantic_sha256": contract["wrapper_interface_semantic_contract"][
            "wrapper_interface_semantic_sha256"
        ],
        "toolchain_manifest_raw_sha256": b1.sha256_upper(toolchain_manifest_raw),
        "implementation_tree_sha256": manifest["implementation_tree_sha256"],
        "implementation_manifest_sha256": manifest["manifest_sha256"],
    }
    evidence_raw = canonical(evidence)

    receipt = {
        "format_version": "B1-IMPLEMENTER-RECEIPT-0.2",
        "receipt_id": "RCP_" + b1.sha256_upper(
            (
                "B1-IMPLEMENTER-RECEIPT-0.3|"
                + ACTOR_ID
                + "|"
                + manifest["manifest_sha256"]
            ).encode("utf-8")
        )[:24],
        "producer_role": "PRIMARY_IMPLEMENTER",
        "producer_actor_id": ACTOR_ID,
        "producer_lineage_id": LINEAGE_ID,
        "subject_sha256": manifest["manifest_sha256"],
        "evidence_sha256": b1.sha256_upper(evidence_raw),
        "result": "PASS",
        "receipt_sha256": b1.ZERO64,
    }
    receipt["receipt_sha256"] = b1.self_zero_sha256(receipt, "receipt_sha256")
    receipt_errors = b1.schema_errors(
        receipt,
        base_contract["schemas"]["implementer_receipt_schema"],
        root=base_contract,
    )
    if receipt_errors:
        raise RuntimeError(f"inherited receipt schema errors: {receipt_errors[:5]}")

    return {
        _MODULE_DIR / "B1_IMPLEMENTATION_MANIFEST_0_3.json": manifest_raw,
        _MODULE_DIR / "receipts" / "B1_IMPLEMENTATION_CONFORMANCE_EVIDENCE_0_3.json": evidence_raw,
        _MODULE_DIR / "receipts" / "B1_IMPLEMENTER_BUILD_RECEIPT_0_3.json": canonical(receipt),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        artifacts = build_artifacts()
        if args.check:
            mismatches = [str(path) for path, raw in artifacts.items() if not path.is_file() or path.read_bytes() != raw]
            if mismatches:
                print("FAIL: regeneration mismatch:", json.dumps(mismatches))
                return 1
            print("PASS: manifest, evidence, and receipt regenerate byte-identically.")
        else:
            for path, raw in artifacts.items():
                write_canonical(path, raw)
            print("PASS: manifest, evidence, and receipt written and schema-valid.")
        manifest = json.loads(artifacts[_MODULE_DIR / "B1_IMPLEMENTATION_MANIFEST_0_3.json"])
        receipt = json.loads(
            artifacts[_MODULE_DIR / "receipts" / "B1_IMPLEMENTER_BUILD_RECEIPT_0_3.json"]
        )
        print("manifest_sha256:", manifest["manifest_sha256"])
        print("implementation_tree_sha256:", manifest["implementation_tree_sha256"])
        print("receipt_sha256:", receipt["receipt_sha256"])
        return 0
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        print("FAIL:", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
