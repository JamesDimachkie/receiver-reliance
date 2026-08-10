"""Meta-tests proving the grounded 0.4 contract lint fails closed.

Each case stages the linter and its exact authority inputs in an isolated OS
temporary directory, mutates only that staged copy, and executes the staged
``lint_contract.py --gate`` in a fresh Python process.  The repository's
authoritative files are therefore never modified.

No randomized test data is used; every mutation is fixed and deterministic.
Exit 0 with ``failures=0`` only when the baseline is accepted and every
representative mutation is rejected with its intended lint finding.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent

LINTER = pathlib.Path("grounded-0_4/lint_contract.py")
REGISTER = pathlib.Path("grounded-0_4/authority_register_0_4.json")
CLOSURES = pathlib.Path("grounded-0_4/closures_0_4.json")

# Minimal exact authority set needed by b1_capabilities.authority_documents().
STAGED_FILES = (
    LINTER,
    REGISTER,
    CLOSURES,
    pathlib.Path("baseline-run/implementation-output-0.3/b1_capabilities.py"),
    pathlib.Path("baseline-run/control/B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json"),
    pathlib.Path("supplemental-0_3/control/B1_SUPPLEMENTAL_COMPARATOR_CONTRACT_0_3.json"),
    pathlib.Path("supplemental-0_3/control/B1_COMPOSED_CAPABILITY_MATRIX_0_3.json"),
    pathlib.Path("access/SANITIZED_PRIMARY_BASELINE_IMPLEMENTER_PACKET_0_1.json"),
    pathlib.Path("access/A2_SHARED_DOMAIN_VOCABULARY_BASELINE_PROJECTION_0_1.schema.json"),
)

Mutation = Callable[[pathlib.Path], str]


def read_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise AssertionError(f"expected object in {path}")
    return value


def write_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def stage_repo(target: pathlib.Path) -> None:
    for relative in STAGED_FILES:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / relative, destination)


def mutate_deleted_register_entry(staged: pathlib.Path) -> str:
    path = staged / REGISTER
    register = read_json(path)
    operation = register["operations"][0]
    removed = operation["fields"].pop(0)
    write_json(path, register)
    return (
        f"L1: {operation['obligation_id']}.{removed['field']} required by schema "
        "but absent from register"
    )


def mutate_semantic_to_inert(staged: pathlib.Path) -> str:
    path = staged / REGISTER
    register = read_json(path)
    for operation in register["operations"]:
        for field in operation["fields"]:
            if field["status"] == "semantic":
                field["status"] = "inert_registered_debt"
                write_json(path, register)
                return (
                    f"L1: {operation['obligation_id']}.{field['field']} registered "
                    "inert_registered_debt but predicates DO reference it semantically "
                    "(stale register)"
                )
    raise AssertionError("baseline register has no semantic field to falsify")


def mutate_inert_to_semantic(staged: pathlib.Path) -> str:
    path = staged / REGISTER
    register = read_json(path)
    for operation in register["operations"]:
        for field in operation["fields"]:
            if field["status"].startswith("inert"):
                field["status"] = "semantic"
                write_json(path, register)
                return (
                    f"L1: {operation['obligation_id']}.{field['field']} registered "
                    "semantic but no value-comparing predicate references it"
                )
    raise AssertionError("baseline register has no inert field to falsify")


def mutate_stale_extra_field(staged: pathlib.Path) -> str:
    path = staged / REGISTER
    register = read_json(path)
    operation = register["operations"][0]
    field_name = "synthetic_stale_field"
    operation["fields"].append(
        {
            "field": field_name,
            "status": "inert_registered_debt",
            "rationale": "deterministic lint meta-test mutation",
        }
    )
    write_json(path, register)
    return (
        f"L1: {operation['obligation_id']}.{field_name} in register but not "
        "schema-required (stale register)"
    )


def mutate_duplicate_wire_format(staged: pathlib.Path) -> str:
    path = staged / REGISTER
    register = read_json(path)
    # Expose the present duplicate as an unapproved synthetic collision.
    register["grandfathered_wire_format_collisions"] = []
    write_json(path, register)
    return (
        "L2: wire format 'B1-SEMANTIC-DECISION-REQUEST-0.2' shared by "
        "['accepted-0.2', 'composed-0.3'] without a grandfathered erratum"
    )


def mutate_closure_to_valid(staged: pathlib.Path) -> str:
    path = staged / CLOSURES
    closures = read_json(path)
    obligation, rows = next(iter(closures["closures_by_obligation"].items()))
    if not rows:
        raise AssertionError(f"baseline closure list for {obligation} is empty")
    closure = rows[0]
    closure["tightens_to"] = "VALID"
    write_json(path, closures)
    return (
        f"L3: closure {closure['closure_id']} tightens_to 'VALID' "
        "(must be a defect class)"
    )


CASES: tuple[tuple[str, Mutation | None], ...] = (
    ("baseline-accepted", None),
    ("deleted-register-entry-rejected", mutate_deleted_register_entry),
    ("semantic-to-inert-rejected", mutate_semantic_to_inert),
    ("inert-to-semantic-rejected", mutate_inert_to_semantic),
    ("stale-extra-field-rejected", mutate_stale_extra_field),
    ("duplicate-wire-format-rejected", mutate_duplicate_wire_format),
    ("closure-to-valid-rejected", mutate_closure_to_valid),
)


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory(prefix="rr-lint-gate-") as temporary:
        temp_root = pathlib.Path(temporary)
        for index, (name, mutation) in enumerate(CASES):
            staged = temp_root / f"case-{index}"
            stage_repo(staged)
            expected = "lint: 0 findings" if mutation is None else mutation(staged)
            completed = subprocess.run(
                [sys.executable, "-B", str(staged / LINTER), "--gate"],
                cwd=staged,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )
            output = completed.stdout + completed.stderr
            exit_ok = completed.returncode == 0 if mutation is None else completed.returncode != 0
            finding_ok = expected in output
            if exit_ok and finding_ok:
                print(f"PASS {name}: exit={completed.returncode}; finding={expected}")
            else:
                failures += 1
                print(
                    f"FAIL {name}: exit={completed.returncode}; "
                    f"expected_finding={expected!r}; output={output.strip()!r}"
                )

    print(f"lint-gate meta-test: checks={len(CASES)} failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
