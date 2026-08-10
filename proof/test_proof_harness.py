"""Portable regression and end-to-end tests for the synthetic proof corpus.

No test randomness is used.  Corpus generation is keyed by the recorded seed
``synthetic_corpus.SEED == 0x20260810``.  The workspace extractor is never
imported or executed by this suite.
"""
from __future__ import annotations

import contextlib
import ast
import fnmatch
import io
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import arm_b1
import arm_baseline
import synthetic_corpus as synthetic


HERE = pathlib.Path(__file__).resolve().parent
EXPECTED_DEFECTS = {
    "lifecycle_order_violation",
    "missing_reference_target",
    "pin_hash_mismatch",
    "recorded_use_outside_declared_scope",
    "reliance_on_superseded_version",
    "stale_reference_path",
    "unknown_result_commit",
}


def extractor_mechanics() -> tuple[object, object, object]:
    """Compile only the extractor's three pure mechanics, never its top level.

    Importing ``extract_corpus.py`` would traverse the operator workspace, so
    this test parses the file and evaluates only the side-effect-free regex,
    function, expression, and blame loop that implement the pinned rules.
    """
    path = HERE / "extract_corpus.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    commit_re = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "COMMIT_RE" for target in node.targets)
    )
    scope_function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "path_in_scope"
    )
    commit_expression = next(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "commit_tokens" for target in node.targets)
    )
    blame_loop = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name)
        and node.target.id == "name"
        and isinstance(node.iter, ast.Name)
        and node.iter.id == "citers_of_invalidated"
    )

    namespace = {"fnmatch": fnmatch, "re": re}
    mechanics = ast.fix_missing_locations(ast.Module([commit_re, scope_function], type_ignores=[]))
    exec(compile(mechanics, str(path), "exec"), namespace)
    commit_code = compile(
        ast.fix_missing_locations(ast.Expression(commit_expression)), str(path), "eval"
    )

    def extracted_commit_tokens(result_text: str) -> list[str]:
        return eval(commit_code, namespace, {"result_text": result_text})

    blame_code = compile(
        ast.fix_missing_locations(
            ast.Module(
                [
                    ast.Assign(
                        targets=[ast.Name(id="sole_reliance", ctx=ast.Store())],
                        value=ast.List(elts=[], ctx=ast.Load()),
                    ),
                    blame_loop,
                ],
                type_ignores=[],
            )
        ),
        str(path),
        "exec",
    )
    return namespace["path_in_scope"], extracted_commit_tokens, blame_code


def load_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class SyntheticCorpusTests(unittest.TestCase):
    def test_checked_in_bytes_match_recorded_seed(self) -> None:
        records, truths = synthetic.build(synthetic.SEED)
        self.assertEqual(synthetic.SEED, 0x20260810)
        self.assertEqual(
            (HERE / "corpus.synthetic.jsonl").read_bytes(),
            synthetic.render_jsonl(records),
        )
        self.assertEqual(
            (HERE / "truth.synthetic.jsonl").read_bytes(),
            synthetic.render_jsonl(truths),
        )

    def test_cli_regeneration_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rr-synthetic-") as tmp:
            root = pathlib.Path(tmp)
            first = root / "first"
            second = root / "second"
            for output in (first, second):
                proc = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(HERE / "synthetic_corpus.py"),
                        "--output-dir",
                        str(output),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
            for name in ("corpus.synthetic.jsonl", "truth.synthetic.jsonl"):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
                self.assertEqual((first / name).read_bytes(), (HERE / name).read_bytes())

    def test_schema_families_and_truth_separation(self) -> None:
        records, truths = synthetic.build()
        self.assertEqual(len(records), 14)
        self.assertEqual(len(truths), len(records))
        self.assertEqual(len({row["record_id"] for row in records}), len(records))
        self.assertEqual({row["family"] for row in records}, set(synthetic.FAMILIES))
        self.assertEqual(
            {defect for row in truths for defect in row["defect_types"]},
            EXPECTED_DEFECTS,
        )

        truth_by_id = {row["record_id"]: row for row in truths}
        forbidden = {"defective", "defect_types", "provenance", "hold", "behavior_class"}

        def keys(value: object) -> set[str]:
            if isinstance(value, dict):
                return set(value) | {key for child in value.values() for key in keys(child)}
            if isinstance(value, list):
                return {key for child in value for key in keys(child)}
            return set()

        for row in records:
            self.assertEqual(set(row), {"record_id", "family", "native", "observations"})
            self.assertTrue(forbidden.isdisjoint(keys(row)))
            self.assertIn(row["record_id"], truth_by_id)
        for row in truths:
            self.assertEqual(
                set(row), {"record_id", "provenance", "defect_types", "defective"}
            )

        for family in synthetic.FAMILIES:
            family_truth = [
                truth_by_id[row["record_id"]]
                for row in records
                if row["family"] == family
            ]
            self.assertTrue(any(row["defective"] for row in family_truth), family)
            self.assertTrue(any(not row["defective"] for row in family_truth), family)

    def test_recursive_glob_scope_membership_regression(self) -> None:
        extracted_scope, _, _ = extractor_mechanics()
        for check in (synthetic.path_in_scope, extracted_scope):
            self.assertTrue(check("dir/file.txt", ["dir/**"]))
            self.assertTrue(check("dir/nested/file.txt", ["dir/**"]))
            self.assertFalse(check("directory/file.txt", ["dir/**"]))
            self.assertFalse(check("other/file.txt", ["dir/**"]))

    def test_supersession_blame_requires_temporal_eligibility(self) -> None:
        epochs = {"before.md": 99, "at.md": 100, "after.md": 101, "current.md": 101}
        blamed = synthetic.supersession_blame(
            100,
            ["before.md", "at.md", "after.md", "current.md"],
            ["current.md"],
            epochs,
        )
        self.assertNotIn("before.md", blamed)
        self.assertNotIn("current.md", blamed)
        self.assertEqual(blamed, ["after.md", "at.md"])

        _, _, blame_code = extractor_mechanics()
        namespace = {
            "citers_of_invalidated": ["before.md", "at.md", "after.md", "current.md"],
            "citers_of_any_later": ["current.md"],
            "doc_added": epochs,
            "corrected_epoch": 100,
        }
        exec(blame_code, namespace)
        self.assertEqual(sorted(namespace["sole_reliance"]), blamed)

    def test_commit_tokens_require_at_least_one_hex_letter(self) -> None:
        self.assertEqual(synthetic.commit_tokens("dates 20260810 and 1234567"), [])
        self.assertEqual(synthetic.commit_tokens("commit deadbee"), ["deadbee"])
        self.assertEqual(synthetic.commit_tokens("commit 12ab567"), ["12ab567"])
        self.assertEqual(synthetic.commit_tokens("not-hex 123456g"), [])

        _, extracted_commit_tokens, _ = extractor_mechanics()
        self.assertEqual(
            extracted_commit_tokens("dates 20260810 and 1234567"),
            [],
        )
        self.assertEqual(extracted_commit_tokens("commit deadbee"), ["deadbee"])


class PortableHarnessTests(unittest.TestCase):
    def test_both_arms_and_scorer_run_without_touching_workspace_outputs(self) -> None:
        protected = {
            path: path.read_bytes()
            for path in (HERE / "RESULTS.md", HERE / "results.json")
            if path.exists()
        }
        with tempfile.TemporaryDirectory(prefix="rr-proof-harness-") as tmp:
            run_dir = pathlib.Path(tmp)
            records, truths = synthetic.build()
            (run_dir / "corpus.jsonl").write_bytes(synthetic.render_jsonl(records))
            (run_dir / "truth.jsonl").write_bytes(synthetic.render_jsonl(truths))

            baseline_here = arm_baseline.HERE
            b1_here = arm_b1.HERE
            argv = sys.argv[:]
            calibrated = arm_b1.CALIBRATED
            try:
                arm_baseline.HERE = run_dir
                arm_b1.HERE = run_dir
                with contextlib.redirect_stdout(io.StringIO()):
                    arm_baseline.main()
                    sys.argv = [str(HERE / "arm_b1.py")]
                    arm_b1.main()
                    sys.argv = [str(HERE / "arm_b1.py"), "--calibrated"]
                    arm_b1.main()
            finally:
                arm_baseline.HERE = baseline_here
                arm_b1.HERE = b1_here
                arm_b1.CALIBRATED = calibrated
                sys.argv = argv

            shutil.copyfile(HERE / "score.py", run_dir / "score.py")
            score = subprocess.run(
                [sys.executable, "-B", str(run_dir / "score.py")],
                cwd=run_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(score.returncode, 0, score.stderr)
            results = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(
                results["overall"]["baseline"],
                {
                    "n": 14,
                    "tp": 6,
                    "fp": 0,
                    "fn": 1,
                    "tn": 7,
                    "detection_rate": 0.8571,
                    "false_hold_rate": 0.0,
                },
            )
            self.assertEqual(results["overall"]["b1"]["tp"], 7)
            self.assertEqual(results["overall"]["b1"]["fn"], 0)
            self.assertEqual(results["overall"]["b1"]["fp"], 1)
            self.assertEqual(results["overall"]["b1_calibrated"]["tp"], 7)
            self.assertEqual(results["overall"]["b1_calibrated"]["fn"], 0)
            self.assertEqual(results["overall"]["b1_calibrated"]["fp"], 0)

        for path, before in protected.items():
            self.assertEqual(path.read_bytes(), before, f"workspace output changed: {path}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
