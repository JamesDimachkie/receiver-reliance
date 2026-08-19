#!/usr/bin/env python3
"""Mutation-test the frozen decision table against its own conformance suite.

WHY THIS EXISTS. Every other verifier in this repository establishes that an
implementation matches the contract's bytes. None establishes that the
contract's predicates are the right predicates, or even that the fixture suite
exercises them. The 370 competence mutations in the semantic pack mutate FACT
PROFILES to kill implementations that pattern-match on metadata; nothing has
ever mutated THE TABLE.

The question this answers, per predicate atom:

    if I break this atom, does any fixture notice?

An atom no mutation kills is one of two things, and both are findings:
  - a FIXTURE gap -- the predicate is real and nothing tests it, so a
    reimplementation could omit it and still pass 907 checks;
  - a TABLE gap -- the predicate is inert, and deleting it would change no
    classification of any input the suite can express.

This is the standard technique for "are my tests any good", pointed at the law
instead of at the implementation. It does not establish that the thirty
operations are the RIGHT thirty -- no mutation test can. It establishes which
parts of the law the published evidence actually constrains, which is the
denominator the artifact has never published.

WHAT IT DOES NOT TOUCH. Frozen bytes are never mutated in place. Every mutation
is staged into an OS temporary directory, exactly as
`grounded-0_4/test_authority_legibility.py` already does for register drift. The
repository copy is read-only throughout.

TWO ARMS PER ATOM, because they ask different questions:

  reachable  the whole class predicate is replaced with one that ALWAYS fires.
             A surviving atom means no fixture distinguishes this operation's
             class at all -- the strongest possible signal of an untested row.

  specific   the atom's own path is repointed at a sentinel that no fact profile
             contains, so the operator evaluates against missing data. A
             surviving atom means the suite exercises the class but not this
             atom's particular condition.

An atom is KILLED if either arm makes the suite fail, and the arms are reported
separately because "the row is untested" and "the condition is untested" are
different defects with different repairs.

USAGE
    python -B baseline-run/verify_predicate_coverage.py --sample 8
    python -B baseline-run/verify_predicate_coverage.py --full --json out.json
    python -B baseline-run/verify_predicate_coverage.py --atom OBL-01/MALFORMED_OR_BOUNDARY

The final line is machine-parseable:
    predicate-coverage: atoms=<n> killed=<n> survived=<n> arms=<n> failures=<n>

Exit 0 when every enumerated atom was killed by at least one arm. Exit 1 on any
survivor, because a survivor is exactly the finding this program exists to
surface -- it is not a warning.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
CONTRACT_REL = pathlib.PurePosixPath("control/B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json")
RUNNER_REL = pathlib.PurePosixPath("implementation-output-0.2/run_conformance_0_2.py")

# Trees the 0.2 runner reads. Copied wholesale so the staged contract is the only
# thing that differs from the repository.
STAGED_TREES = ("baseline-run", "access", "supplemental-0_3")

# A JSON pointer no fact profile contains. Repointing an atom here makes its
# operator evaluate against missing data.
SENTINEL = "/facts/__rr_predicate_coverage_sentinel__"

# `ABSENT` over a path nothing supplies is unconditionally true, so this is the
# always-fires predicate. It is expressed in the contract's own vocabulary
# rather than a synthetic operator, so the staged contract stays schema-valid.
ALWAYS_FIRES = {"op": "ABSENT", "path": SENTINEL}

# A pointer is any string value that starts with "/". The frozen vocabulary
# spells pointers under thirteen different key names -- path, paths, left,
# right, value_path, collection_path, lower, upper, current, prior,
# boolean_path, enum_path, and sometimes value -- and `value` is a pointer in
# OUTSIDE_HALF_OPEN and a literal in EQ. Discriminating on the leading slash is
# the only rule that holds across all of them, so this enumerates by shape
# rather than by a key allowlist that would silently skip operators.
def load_table(root: pathlib.Path) -> list[dict]:
    contract = json.loads((root / CONTRACT_REL).read_text(encoding="utf-8"))
    return contract["semantic_decision_contract"]["operation_decision_table"]


def _is_pointer(value: object) -> bool:
    return isinstance(value, str) and value.startswith("/")


DEFECT_CLASSES = (
    "MALFORMED_OR_BOUNDARY",
    "BINDING_OR_CONFLICT",
    "OMISSION_OR_INCOMPLETE",
)


def _walk(node: object, route: list, out: list) -> None:
    """Collect every leaf atom, descending through `any` / `all` combinators.

    An earlier revision of this program keyed on a top-level "op" and therefore
    skipped all 23 compound class predicates and every atom inside them. The
    combinators are where the granularity lives, so they are traversed.
    """
    if isinstance(node, dict):
        for combinator in ("any", "all"):
            if isinstance(node.get(combinator), list):
                for index, child in enumerate(node[combinator]):
                    _walk(child, route + [combinator, index], out)
                return
        if "op" in node:
            pointers = sorted(k for k, v in node.items() if _is_pointer(v))
            lists = sorted(
                k for k, v in node.items()
                if isinstance(v, list) and any(_is_pointer(x) for x in v)
            )
            out.append({"route": route, "op": node["op"],
                        "pointer_keys": pointers, "pointer_list_keys": lists})


def enumerate_atoms(table: list[dict]) -> list[dict]:
    """Every leaf predicate atom in the table, with the route to reach it.

    VALID is skipped: it is `NO_EARLIER_CLASS_MATCH` in every row, defined as the
    negation of the three earlier classes, so it carries no condition of its own.
    """
    atoms: list[dict] = []
    for row_index, row in enumerate(table):
        for cls in DEFECT_CLASSES:
            predicate = row["class_predicates"].get(cls)
            if not isinstance(predicate, dict):
                continue
            leaves: list = []
            _walk(predicate, [], leaves)
            for leaf in leaves:
                suffix = "".join(
                    f"[{part}]" if isinstance(part, int) else f".{part}"
                    for part in leaf["route"]
                )
                atoms.append({
                    "id": f"{row['obligation_id']}/{cls}{suffix}",
                    "obligation_id": row["obligation_id"],
                    "operation_handle": row["operation_handle"],
                    "class": cls,
                    "op": leaf["op"],
                    "route": leaf["route"],
                    "pointer_keys": leaf["pointer_keys"],
                    "pointer_list_keys": leaf["pointer_list_keys"],
                    "compound": bool(leaf["route"]),
                    "row_index": row_index,
                })
    return atoms


def _resolve(predicate: dict, route: list) -> dict:
    node = predicate
    for part in route:
        node = node[part]
    return node


def stage(destination: pathlib.Path) -> None:
    for tree in STAGED_TREES:
        shutil.copytree(REPO / tree, destination / tree)


def apply_mutation(root: pathlib.Path, atom: dict, arm: str) -> bool:
    """Write the mutated contract into a staged copy. False if the arm is inapplicable."""
    contract_path = root / "baseline-run" / CONTRACT_REL
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    row = contract["semantic_decision_contract"]["operation_decision_table"][atom["row_index"]]

    if arm == "reachable":
        # Replace the WHOLE class predicate, compound or not, so the class fires
        # for every input. A survivor here means no fixture distinguishes this
        # operation's class at all.
        row["class_predicates"][atom["class"]] = dict(ALWAYS_FIRES)
    elif arm == "specific":
        if not (atom["pointer_keys"] or atom["pointer_list_keys"]):
            return False
        leaf = _resolve(row["class_predicates"][atom["class"]], atom["route"])
        for key in atom["pointer_keys"]:
            leaf[key] = SENTINEL
        for key in atom["pointer_list_keys"]:
            leaf[key] = [SENTINEL if _is_pointer(v) else v for v in leaf[key]]
    else:
        raise ValueError(f"unknown arm: {arm}")

    contract_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8"
    )
    return True


def run_suite(root: pathlib.Path, timeout: float) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "-B", str(root / "baseline-run" / RUNNER_REL)],
        cwd=root / "baseline-run",
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    tail = (result.stdout + result.stderr).strip().splitlines()
    return result.returncode, (tail[-1][:120] if tail else "")


def probe(atom: dict, arm: str, timeout: float) -> dict | None:
    with tempfile.TemporaryDirectory(prefix="rr-predicate-") as raw:
        root = pathlib.Path(raw)
        stage(root)
        if not apply_mutation(root, atom, arm):
            return None
        started = time.time()
        code, summary = run_suite(root, timeout)
        return {
            "arm": arm,
            "killed": code != 0,
            "exit_code": code,
            "summary": summary,
            "seconds": round(time.time() - started, 2),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--full", action="store_true", help="every enumerated atom")
    scope.add_argument("--sample", type=int, metavar="N",
                       help="first N atoms, deterministic (enumeration order)")
    scope.add_argument("--atom", metavar="ID", help="one atom, e.g. OBL-01/MALFORMED_OR_BOUNDARY")
    parser.add_argument("--json", metavar="PATH", help="write the per-atom record here")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    atoms = enumerate_atoms(load_table(REPO / "baseline-run"))
    if args.atom:
        atoms = [a for a in atoms if a["id"] == args.atom]
        if not atoms:
            print(f"predicate-coverage: no atom with id {args.atom!r}", file=sys.stderr)
            return 2
    elif args.sample:
        atoms = atoms[: args.sample]
    elif not args.full:
        atoms = atoms[:4]
        if not args.quiet:
            print("predicate-coverage: no scope given; probing the first 4 atoms. "
                  "Use --full for the whole table.")

    records: list[dict] = []
    killed = survived = arms_run = failures = 0

    # The reachable arm replaces the WHOLE class predicate, so it is identical for
    # every atom inside one compound. Probe it once per (row, class) and reuse,
    # or a 3-atom compound pays for the same run three times.
    reachable_cache: dict = {}

    for index, atom in enumerate(atoms, start=1):
        results = []
        for arm in ("reachable", "specific"):
            key = (atom["row_index"], atom["class"])
            if arm == "reachable" and key in reachable_cache:
                cached = reachable_cache[key]
                if cached is not None:
                    results.append({**cached, "reused": True})
                    arms_run += 1
                continue
            try:
                outcome = probe(atom, arm, args.timeout)
            except subprocess.TimeoutExpired:
                outcome = {"arm": arm, "killed": False, "exit_code": None,
                           "summary": "TIMEOUT", "seconds": args.timeout}
                failures += 1
            if arm == "reachable":
                reachable_cache[(atom["row_index"], atom["class"])] = outcome
            if outcome is not None:
                results.append(outcome)
                arms_run += 1
        was_killed = any(r["killed"] for r in results)
        killed += was_killed
        survived += not was_killed
        records.append({**atom, "killed": was_killed, "arms": results})
        if not args.quiet:
            marks = " ".join(
                f"{r['arm']}={'kill' if r['killed'] else 'SURVIVE'}" for r in results
            )
            print(f"  [{index:3}/{len(atoms)}] {atom['id']:38} {atom['op']:32} {marks}")

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(
                {
                    "format_version": "RR-PREDICATE-COVERAGE-1",
                    "atoms": len(atoms),
                    "killed": killed,
                    "survived": survived,
                    "records": records,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    if survived and not args.quiet:
        print("\nSurvivors -- no fixture distinguishes these atoms:")
        for record in records:
            if not record["killed"]:
                print(f"  {record['id']:38} {record['op']}")

    print(
        f"predicate-coverage: atoms={len(atoms)} killed={killed} "
        f"survived={survived} arms={arms_run} failures={failures}"
    )
    return 1 if (survived or failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
