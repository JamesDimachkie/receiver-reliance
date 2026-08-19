from __future__ import annotations

import copy
import decimal
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import receipt

REPO = pathlib.Path(__file__).resolve().parents[2]

# Every synthesized receipt binds to this literal commit.  ERRATA E17: a test
# fixture that reads GITHUB_SHA silently agrees with a validator that reads
# GITHUB_SHA, and the pair stays green in both environments while the property
# under test is unbound.
FIXTURE_WORKFLOW_SHA = "a" * 40
FOREIGN_RUN_SHA = "b" * 40


class MatrixPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = receipt._json_load(receipt.DEFAULT_PLAN)

    def test_normative_plan_is_three_by_six_without_scheduling_macos_13(self) -> None:
        entries = receipt._normative_entries(self.plan)
        self.assertEqual(len(entries), 18)
        self.assertEqual(sum(bool(entry["runnable"]) for entry in entries), 15)
        unavailable = [entry for entry in entries if not entry["runnable"]]
        self.assertEqual({entry["runner"] for entry in unavailable}, {"macos-13"})
        self.assertEqual(
            {entry["python_version"] for entry in unavailable},
            {"3.12", "3.13", "3.14"},
        )
        self.assertTrue(all(entry.get("infra_evidence") for entry in unavailable))

    def test_emitted_rows_separate_normative_stress_and_off_contract(self) -> None:
        normative = receipt.matrix_rows(self.plan, "normative_matrix")
        stress = receipt.matrix_rows(self.plan, "stress_matrix")
        self.assertEqual(len(normative), 15)
        self.assertEqual(len(stress), 9)
        self.assertTrue(all(row["classification"] == "normative" for row in normative))
        self.assertEqual({row["classification"] for row in stress}, {"stress", "off_contract"})
        self.assertNotIn("macos-13", {row["runner"] for row in stress})
        intel = [row for row in stress if row["runner"] == "macos-15-intel"]
        self.assertEqual(len(intel), 3)
        self.assertTrue(all("non_substitute" in row["claim_scope"] for row in intel))

    def test_expanded_profile_carries_the_charter_gate_commands(self) -> None:
        """The expanded profile is the hosted mirror of the charter gate.

        It was two performance commands on top of the baseline until the gate
        grew to cover the surfaces the repository had added since: the
        engine-manifest, audit-seal, observability, preflight, MCP-gate and
        admission-profile suites.  ``decision-law-structural`` and
        ``incident-replay-corpus`` are in the charter too but are declared once,
        in ``portability_checks``, where every focused row already runs them --
        a second copy here would be two declarations of one command.
        """
        focused = receipt.profile_commands(self.plan, "focused")
        expanded = receipt.profile_commands(self.plan, "expanded")
        self.assertEqual(len(focused), 42)
        self.assertEqual(len(expanded), 17)
        self.assertEqual(expanded[0]["id"], "accepted-0.2")
        self.assertEqual(
            [item["id"] for item in expanded[9:]],
            [
                "batch-performance-gate",
                "single-pass-benchmark",
                "engine-manifest-tests",
                "audit-seal-tests",
                "observability-tests",
                "portable-preflight-tests",
                "mcp-gate-regression",
                "admission-profile-tests",
            ],
        )
        free_threaded = receipt.profile_commands(self.plan, "free_threaded")
        self.assertEqual(len(free_threaded), 43)
        self.assertEqual(free_threaded[-1]["id"], "free-threaded-concurrency-p-le-8")

    def test_focused_profile_uses_bounded_entrypoints(self) -> None:
        focused = {
            item["id"]: item
            for item in receipt.profile_commands(self.plan, "focused")
        }
        deterministic_test_counts = {
            "matrix-receipt-tests": 60,
            "independent-oracle-tests": 35,
            "concurrency-tests": 15,
        }
        for command_id, count in deterministic_test_counts.items():
            with self.subTest(command_id=command_id):
                self.assertEqual(
                    focused[command_id]["expected"], {"tests": [count]}
                )
        with self.subTest(command_id="portable-bundle-gate"):
            self.assertEqual(
                focused["portable-bundle-gate"]["expected"],
                {"checks": [9], "failures": [0]},
            )
        self.assertNotIn("finite-model-explorer", focused)
        self.assertEqual(
            focused["finite-model-focused-tests"]["argv"],
            ["{python}", "-B", "portability/model/test_model.py"],
        )
        self.assertEqual(
            focused["concurrency-tests"]["argv"],
            ["{python}", "-B", "-m", "portability.concurrency.test_ladder"],
        )
        self.assertNotIn(
            "portability.model.explorer",
            " ".join(focused["finite-model-focused-tests"]["argv"]),
        )
        smoke = focused["concurrency-focused-smoke"]
        self.assertEqual(
            smoke["argv"][-1],
            "portability/concurrency/receipts/matrix-focused-{entry_id}.json",
        )
        free_threaded = receipt.profile_commands(self.plan, "free_threaded")[-1]
        self.assertEqual(
            free_threaded["argv"][-1],
            "portability/concurrency/receipts/matrix-free-threaded-{entry_id}.json",
        )

    def test_corrected_manifest_entrypoints_execute_from_repo_root(self) -> None:
        entry = next(
            item
            for item in receipt._normative_entries(self.plan)
            if item["runner"] == "ubuntu-latest"
            and item["python_version"] == "3.12"
        )
        focused = {
            item["id"]: item
            for item in receipt.profile_commands(self.plan, "focused")
        }
        command_ids = (
            "finite-model-focused-tests",
            "concurrency-tests",
            "concurrency-focused-smoke",
        )
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ)
            environment.pop("PYTHONPATH", None)
            environment["RUNNER_TEMP"] = directory
            for command_id in command_ids:
                spec = focused[command_id]
                with self.subTest(command_id=command_id), mock.patch.dict(
                    os.environ, {"RUNNER_TEMP": directory}
                ):
                    planned_argv = [
                        receipt._expand_argument(item, entry)
                        for item in spec["argv"]
                    ]
                    # Import/argument-parser smoke only.  The receipt runner
                    # schedules each exact command separately; running the
                    # focused suites here as well would duplicate them inside
                    # every hosted row.
                    if command_id == "concurrency-focused-smoke":
                        argv = [*planned_argv[:3], "--help"]
                    else:
                        argv = [*planned_argv, "--help"]
                    completed = subprocess.run(
                        argv,
                        cwd=(receipt.REPO_ROOT / spec["cwd"]).resolve(),
                        env=environment,
                        capture_output=True,
                        check=False,
                        timeout=30,
                    )
                    self.assertEqual(
                        completed.returncode,
                        0,
                        completed.stderr.decode("utf-8", "replace"),
                    )
                    self.assertTrue(completed.stdout or completed.stderr)


class AmbiguousEvidenceIsRefused(unittest.TestCase):
    """Downloaded receipts are hostile input; ambiguity must not resolve."""

    def _load(self, raw: bytes):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "receipt.json"
            path.write_bytes(raw)
            return receipt._json_load(path)

    def test_duplicate_member_is_rejected_not_collapsed(self) -> None:
        # csf_3df8c8b0: default decoding keeps the LAST value, so a sender could
        # make the verifier read an outcome the receipt also contradicts.
        with self.assertRaises(ValueError) as caught:
            self._load(b'{"entry_id":"a","outcome":"FAIL","outcome":"PASS"}')
        self.assertIn("duplicate object key", str(caught.exception))
        self.assertEqual(
            self._load(b'{"entry_id":"a","outcome":"PASS"}')["outcome"], "PASS"
        )

    def test_duplicate_member_is_rejected_at_any_depth(self) -> None:
        with self.assertRaises(ValueError):
            self._load(b'{"a":{"b":[{"git":1,"git":2}]}}')

    def test_flat_structural_node_budget_is_enforced(self) -> None:
        # csf_92622f9b: a wide shallow document under the byte cap decoded fully
        # before any shape validation, with MemoryError as the only backstop.
        wide = (
            b'{"a":['
            + b",".join(b"0" for _ in range(receipt.MAX_JSON_STRUCTURAL_NODES + 2))
            + b"]}"
        )
        self.assertLess(len(wide), receipt.MAX_JSON_INPUT_BYTES)
        with self.assertRaises(ValueError) as caught:
            self._load(wide)
        self.assertIn("structural node count", str(caught.exception))

    def test_real_receipts_stay_well_inside_the_node_budget(self) -> None:
        hosted = REPO / "portability" / "receipts" / "hosted"
        for path in sorted(hosted.glob("receipt-*.json")):
            with self.subTest(receipt=path.name):
                receipt._json_load(path)

    def test_undecodable_count_lines_cannot_authorize(self) -> None:
        # csf_95727c25: replacement decoding let malformed bytes match a count
        # pattern and contribute to an expected total.
        good = b"grounded-0.4 regression: checks=521 failures=0\n"
        forged = b"grounded-0.4 regression: checks=521 \xff\xfe failures=0\n"
        self.assertEqual(receipt.parse_suite_counts(good, b"")["checks"], [521])
        self.assertEqual(receipt.parse_suite_counts(forged, b"")["checks"], [])

    def test_duplicate_count_names_cannot_reach_an_expected_total(self) -> None:
        honest = b'mode=in-process counts={"a": 800} failures=0\n'
        forged = b'mode=in-process counts={"a": 1, "a": 800} failures=0\n'
        self.assertEqual(
            receipt.parse_suite_counts(honest, b"")["count_totals"], [800]
        )
        self.assertEqual(receipt.parse_suite_counts(forged, b"")["count_totals"], [])


class ReceiptParsingTests(unittest.TestCase):
    @staticmethod
    def _nested_entry_id(arrays: int) -> bytes:
        return b'{"entry_id":' + (b"[" * arrays) + b"0" + (b"]" * arrays) + b"}"

    def test_json_depth_preflight_has_exact_array_boundary(self) -> None:
        at_boundary = self._nested_entry_id(receipt.MAX_JSON_NESTING_DEPTH - 1)
        beyond_boundary = self._nested_entry_id(receipt.MAX_JSON_NESTING_DEPTH)
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "receipt-boundary.json"
            path.write_bytes(at_boundary)
            loaded = receipt._json_load(path)
            value = loaded["entry_id"]
            observed_depth = 0
            while isinstance(value, list):
                self.assertEqual(len(value), 1)
                value = value[0]
                observed_depth += 1
            self.assertEqual(observed_depth, receipt.MAX_JSON_NESTING_DEPTH - 1)
            self.assertEqual(value, 0)

            path.write_bytes(beyond_boundary)
            with self.assertRaisesRegex(ValueError, "structural nesting"):
                receipt._json_load(path)

    def test_exact_f_matrix_009_witness_is_rejected_before_json_recursion(self) -> None:
        raw = self._nested_entry_id(2994)
        self.assertEqual(len(raw), 6002)
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "87692f2a880ebda740fc10ff0ba1fe3135b1e198c939e0d7edbc1d1411845a12",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "receipt-hostile.json"
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "structural nesting") as raised:
                receipt._json_load(path)
        self.assertNotIsInstance(raised.exception, RecursionError)

    def test_json_preflight_distinguishes_strings_and_malformed_neighbors(self) -> None:
        valid = json.dumps({"entry_id": '[{]}"\\'}).encode("utf-8")
        malformed = (
            b'{"entry_id":[}',
            b'{"entry_id":{"a":0]',
            b'{"entry_id":[0]',
            b'{"entry_id":"unterminated}',
        )
        deep_object = (
            b'{"entry_id":'
            + (b'{"a":' * receipt.MAX_JSON_NESTING_DEPTH)
            + b"0"
            + (b"}" * receipt.MAX_JSON_NESTING_DEPTH)
            + b"}"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "receipt-structural.json"
            path.write_bytes(valid)
            self.assertEqual(receipt._json_load(path)["entry_id"], '[{]}"\\')
            for payload in (*malformed, deep_object):
                with self.subTest(payload=payload[:40]):
                    path.write_bytes(payload)
                    with self.assertRaises(ValueError):
                        receipt._json_load(path)

    def test_json_input_size_and_decoder_resource_failures_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "receipt-resource.json"
            path.write_bytes(b" " * (receipt.MAX_JSON_INPUT_BYTES + 1))
            with mock.patch.object(receipt.json, "loads") as decoder:
                with self.assertRaisesRegex(ValueError, "finite input domain"):
                    receipt._json_load(path)
                decoder.assert_not_called()

            path.write_bytes(b'{"entry_id":0}')
            # A RecursionError inside the decoder is bounded by the shared
            # ingest law (ADOPTION A4), which converts it to its own
            # ValueError; a MemoryError propagates to this module's outer
            # resource boundary.  Both stay ValueError -- the property.
            for failure, expected in (
                (RecursionError("synthetic"), "nesting exceeded"),
                (MemoryError("synthetic"), "MemoryError"),
            ):
                with self.subTest(failure=type(failure).__name__):
                    with mock.patch.object(receipt.json, "loads", side_effect=failure):
                        with self.assertRaisesRegex(ValueError, expected):
                            receipt._json_load(path)

    def test_canonical_writer_bounds_depth_without_recursive_failure(self) -> None:
        at_boundary: object = 0
        for _ in range(receipt.MAX_JSON_NESTING_DEPTH):
            at_boundary = [at_boundary]
        self.assertTrue(receipt._canonical_json(at_boundary).startswith("[\n"))

        hostile: object = 0
        for _ in range(2994):
            hostile = [hostile]
        with self.assertRaisesRegex(ValueError, "finite writer domain") as raised:
            receipt._canonical_json(hostile)
        self.assertNotIsInstance(raised.exception, RecursionError)

        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "hostile.json"
            with self.assertRaisesRegex(ValueError, "finite writer domain"):
                receipt._write_json(output, hostile)
            self.assertFalse(output.exists())
            self.assertFalse(output.with_name(output.name + ".tmp").exists())

        cyclic: list[object] = []
        cyclic.append(cyclic)
        with self.assertRaisesRegex(ValueError, "cyclic containers"):
            receipt._canonical_json(cyclic)

    def test_suite_counts_cover_json_counts_unittest_and_fuzz(self) -> None:
        stdout = (
            b'mode=in-process counts={"a": 799, "b": 1} failures=0\n'
            b"grounded: checks=504 failures=0\n"
            b"lint: 0 findings\n"
            b"rr-fuzz: cases=31/31 failures=0\n"
        )
        stderr = b"Ran 7 tests in 0.1s\nOK\n"
        counts = receipt.parse_suite_counts(stdout, stderr)
        self.assertEqual(counts["count_totals"], [800])
        self.assertEqual(counts["checks"], [504])
        self.assertEqual(counts["failures"], [0, 0, 0])
        self.assertEqual(counts["findings"], [0])
        self.assertEqual(counts["tests"], [7])
        self.assertEqual(counts["case_progress"], [[31, 31]])

    def test_suite_count_parser_marks_oversized_decimal_without_crashing(self) -> None:
        huge = b"1" + (b"0" * 10_000)
        counts = receipt.parse_suite_counts(
            b"checks=" + huge + b" cases=" + huge + b"/" + huge,
            b"",
        )
        marker = receipt.MAX_RECEIPT_INTEGER + 1
        self.assertEqual(counts["checks"], [marker])
        self.assertEqual(counts["case_progress"], [[marker, marker]])

    def test_command_records_hashes_exit_elapsed_counts_and_resources(self) -> None:
        spec = {
            "id": "tiny",
            "cwd": ".",
            "argv": ["{python}", "-c", "print('checks=1 failures=0')"],
            "timeout_seconds": 30,
            "expected": {"checks": [1], "failures": [0]},
        }
        entry = {"python_dev_mode": False}
        result = receipt._run_command(spec, entry)
        self.assertEqual(result["exit"], 0)
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["suite_counts"]["checks"], [1])
        self.assertEqual(result["expectation_mismatches"], [])
        self.assertRegex(result["stdout_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(result["stderr_sha256"], r"^[0-9a-f]{64}$")
        self.assertGreaterEqual(result["elapsed_seconds"], 0)
        self.assertIn("children_user_seconds", result["resources"])


class SummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = receipt._json_load(receipt.DEFAULT_PLAN)

    def test_off_contract_compiler_may_be_empty_normative_must_not(self) -> None:
        # F-MATRIX-013: GraalPy and PyPy legitimately report an empty
        # `platform.python_compiler()`; requiring a nonempty compiler string
        # invalidated honest off-contract observation receipts, which the
        # summarizer then downgraded to RECEIPT_MISSING.  The empty string is
        # the honest recorded value for observations; normative receipts keep
        # the nonempty requirement.
        entry = next(
            item
            for item in self.plan["stress"]
            if item["classification"] == "off_contract"
        )
        row = self._successful_pass_row(entry, [])
        environment = row["environment"]
        self.assertIsNone(receipt._environment_validation_error(environment, entry))
        environment["runtime"]["compiler"] = ""
        self.assertIsNone(receipt._environment_validation_error(environment, entry))
        normative_entry = dict(entry, classification="normative")
        self.assertEqual(
            receipt._environment_validation_error(environment, normative_entry),
            "environment runtime compiler must be nonempty",
        )
        environment["runtime"]["compiler"] = None
        self.assertEqual(
            receipt._environment_validation_error(environment, entry),
            "environment runtime compiler must be a string",
        )

    def _write_explicit_setup_unavailable(
        self, root: pathlib.Path, entry: dict[str, object]
    ) -> None:
        path = root / f"receipt-{entry['id']}.json"
        receipt.unavailable_entry(
            self.plan,
            entry,
            path,
            "actions/setup-python could not provide the requested build",
            "runtime_setup_unavailable",
            "steps.setup.outcome=failure",
        )
        # Summary tests synthesize hosted artifacts even when the development
        # worktree is dirty.  Rebind that fixture to one internally consistent
        # clean workflow SHA before validation.  The SHA is a literal, never
        # os.environ["GITHUB_SHA"] -- see FIXTURE_WORKFLOW_SHA.
        row = json.loads(path.read_text(encoding="utf-8"))
        sha = FIXTURE_WORKFLOW_SHA
        row["git"] = {
            "sha": sha,
            "github_sha": sha,
            "clean": True,
            "status_sha256": hashlib.sha256(b"").hexdigest(),
            "status_line_count": 0,
        }
        path.write_text(json.dumps(row), encoding="utf-8")

    def _write_all_runnable_normative(
        self, root: pathlib.Path, omit: str | None = None
    ) -> None:
        for entry in receipt.all_entries(self.plan):
            if (
                entry["classification"] == "normative"
                and entry.get("runnable", True)
                and entry["id"] != omit
            ):
                self._write_explicit_setup_unavailable(root, entry)

    def _successful_pass_row(
        self, entry: dict[str, object], planned: list[dict[str, object]]
    ) -> dict[str, object]:
        row = receipt._base_receipt(self.plan, entry)
        sha = FIXTURE_WORKFLOW_SHA
        empty_hash = hashlib.sha256(b"").hexdigest()
        row["git"] = {
            "sha": sha,
            "github_sha": sha,
            "clean": True,
            "status_sha256": empty_hash,
            "status_line_count": 0,
        }
        environment = row["environment"]
        os_family = entry["os_family"]
        architecture = entry["architecture"]
        environment["os"] = {
            "system": os_family,
            "release": "synthetic-release",
            "kernel_version": "synthetic-kernel",
            "uname": [
                os_family,
                "synthetic-node",
                "synthetic-release",
                "synthetic-kernel",
                architecture,
                architecture,
            ],
        }
        environment["architecture"] = {
            "requested": architecture,
            "machine": architecture,
            "mode": "native",
            "darwin_rosetta": False if os_family == "Darwin" else None,
            "windows_wow64": False,
        }
        implementation = entry["implementation"]
        version = str(entry["python_version"])
        language_version = str(entry.get("python_language_version", version))
        match = re.search(r"(\d+)\.(\d+)", language_version)
        major, minor = (int(match.group(1)), int(match.group(2))) if match else (3, 12)
        runtime = environment["runtime"]
        runtime["implementation"] = implementation
        runtime["version_info"] = [major, minor, 0, "final", 0]
        runtime["full_version"] = f"{major}.{minor}.0 (synthetic)"
        runtime["setup_python_version"] = None
        if entry.get("distribution_release"):
            runtime["setup_python_version"] = (
                f"graalpy{entry['distribution_release']}.2"
            )
        runtime["build_flags"]["Py_GIL_DISABLED"] = 0
        runtime["build_flags"]["Py_DEBUG"] = 0
        runtime["gil_enabled"] = None
        runtime["dev_mode"] = False
        if entry.get("required_capability") == "free_threaded":
            runtime["build_flags"]["Py_GIL_DISABLED"] = 1
            runtime["gil_enabled"] = False
        elif entry.get("required_capability") == "pydebug":
            runtime["build_flags"]["Py_DEBUG"] = 1
        elif entry.get("required_capability") == "dev_mode":
            runtime["dev_mode"] = True
        environment["abi"] = {"word_size_bits": 64, "byte_order": "little"}
        environment["encoding"] = {
            "locale": "C.UTF-8",
            "preferred": "utf-8",
            "filesystem": "utf-8",
            "filesystem_errors": "surrogateescape",
            "default": "utf-8",
            "stdout": "utf-8",
            "stderr": "utf-8",
        }
        row["outcome"] = "PASS"
        row["commands_planned"] = planned
        commands = []
        for spec in planned:
            counts = {
                "count_totals": [],
                "checks": [],
                "failures": [],
                "findings": [],
                "tests": [],
                "case_progress": [],
            }
            expected = copy.deepcopy(spec.get("expected", {}))
            counts.update(copy.deepcopy(expected))
            argv = []
            for template in spec["argv"]:
                if template == "{python}":
                    argv.append(row["environment"]["runtime"]["executable"])
                else:
                    argv.append(
                        template.replace("{temp}", "/runner/temp").replace(
                            "{entry_id}", entry["id"]
                        )
                    )
            commands.append(
                {
                    "id": spec["id"],
                    "argv": argv,
                    "cwd": spec["cwd"],
                    "timeout_seconds": spec["timeout_seconds"],
                    "timed_out": False,
                    "exit": 0,
                    "elapsed_seconds": 0.0,
                    "stdout_sha256": empty_hash,
                    "stderr_sha256": empty_hash,
                    "stdout_bytes": 0,
                    "stderr_bytes": 0,
                    "suite_counts": counts,
                    "expected_counts": expected,
                    "expectation_mismatches": [],
                    "resources": {
                        "children_user_seconds": 0.0,
                        "children_system_seconds": 0.0,
                        "max_rss_kib": None,
                    },
                }
            )
        row["commands"] = commands
        row["suite_counts"] = [
            {"id": command["id"], **command["suite_counts"]}
            for command in commands
        ]
        return row

    def test_missing_scheduled_receipts_fail_closed_but_macos_13_stays_infra(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            output = root / "summary.json"
            exit_code = receipt.summarize(self.plan, root / "missing", output)
            summary = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 1)
        self.assertEqual(len(summary["rows"]), 28)
        self.assertEqual(len(summary["normative_failures"]), 16)
        self.assertTrue(
            all(
                row["outcome"] == "RECEIPT_MISSING"
                for row in summary["rows"]
                if row["requested"]["runner"] != "macos-13"
            )
        )
        macos_13 = [row for row in summary["rows"] if row["requested"]["runner"] == "macos-13"]
        self.assertEqual(len(macos_13), 3)
        self.assertTrue(all(row["outcome"] == "INFRA_UNAVAILABLE" for row in macos_13))
        self.assertTrue(
            all(
                row["infra_proof"]["kind"] == "predeclared_runner_unavailable"
                for row in macos_13
            )
        )
        self.assertTrue(all(row["infra_evidence"] for row in macos_13))
        self.assertTrue(all(len(row["commands_planned"]) == 42 for row in macos_13))

    def test_exact_deep_hostile_receipt_cli_persists_deterministic_red_summary(self) -> None:
        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        raw = b'{"entry_id":' + (b"[" * 2994) + b"0" + (b"]" * 2994) + b"}"
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "87692f2a880ebda740fc10ff0ba1fe3135b1e198c939e0d7edbc1d1411845a12",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            receipts_dir = root / "receipts"
            receipts_dir.mkdir()
            hostile = receipts_dir / f"receipt-{target['id']}.json"
            hostile.write_bytes(raw)
            environment = dict(os.environ)
            environment["RUNNER_TEMP"] = str(root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(receipt.HERE / "receipt.py"),
                    "summarize",
                    "--receipts-dir",
                    str(receipts_dir),
                    "--output-name",
                    "matrix-summary.json",
                    # Explicit, so this subprocess's verdict does not depend on
                    # whether the invoking shell exports GITHUB_SHA (E17).
                    "--workflow-sha",
                    FIXTURE_WORKFLOW_SHA,
                    "--normative-job-result",
                    "success",
                    "--expanded-gate-job-result",
                    "success",
                ],
                cwd=receipt.REPO_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            output = root / "matrix-summary.json"
            self.assertEqual(completed.returncode, 1, completed.stderr)
            self.assertTrue(output.is_file())
            summary_text = output.read_text(encoding="utf-8")
            summary = json.loads(summary_text)
        self.assertIn("receipt_path=", completed.stdout)
        self.assertIn(target["id"], summary["normative_failures"])
        self.assertTrue(
            any("structural nesting" in error for error in summary["errors"])
        )
        self.assertEqual(summary["schema"], receipt.SUMMARY_SCHEMA)

    def test_explicit_setup_unavailable_receipts_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            self._write_all_runnable_normative(root)
            output = root / "summary.json"
            exit_code = receipt.summarize(self.plan, root, output)
            summary = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["normative_failures"], [])
        normative = [
            row for row in summary["rows"] if row["classification"] == "normative"
        ]
        self.assertTrue(all(row["outcome"] == "INFRA_UNAVAILABLE" for row in normative))
        self.assertTrue(all(row["infra_proof"]["evidence"] for row in normative))

        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        mutations = {
            "missing_github_sha": lambda row: row["git"].__setitem__(
                "github_sha", None
            ),
            "dirty_checkout": lambda row: (
                row["git"].__setitem__("clean", False),
                row["git"].__setitem__("status_line_count", 1),
                row["git"].__setitem__("status_sha256", "b" * 64),
            ),
            "wrong_workflow_sha": lambda row: row["git"].__setitem__(
                "github_sha", "b" * 40
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                self._write_all_runnable_normative(root)
                path = root / f"receipt-{target['id']}.json"
                row = json.loads(path.read_text(encoding="utf-8"))
                mutate(row)
                path.write_text(json.dumps(row), encoding="utf-8")
                output = root / "summary.json"
                exit_code = receipt.summarize(self.plan, root, output)
                summary = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(exit_code, 1)
                self.assertIn(target["id"], summary["normative_failures"])

    def test_single_lost_artifact_fails_closed(self) -> None:
        missing = next(
            entry["id"]
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            self._write_all_runnable_normative(root, omit=missing)
            output = root / "summary.json"
            exit_code = receipt.summarize(self.plan, root, output)
            summary = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["normative_failures"], [missing])
        row = next(item for item in summary["rows"] if item["entry_id"] == missing)
        self.assertEqual(row["outcome"], "RECEIPT_MISSING")

    def test_failed_normative_job_result_fails_even_with_infra_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            self._write_all_runnable_normative(root)
            output = root / "summary.json"
            exit_code = receipt.summarize(
                self.plan,
                root,
                output,
                {"normative_matrix": "failure", "expanded_gate": "success"},
            )
            summary = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 1)
        self.assertTrue(
            any("normative_matrix" in error and "failure" in error for error in summary["errors"])
        )

    def test_ambiguous_infra_receipt_without_proof_fails_closed(self) -> None:
        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            self._write_all_runnable_normative(root)
            path = root / f"receipt-{target['id']}.json"
            row = json.loads(path.read_text(encoding="utf-8"))
            row["infra_proof"] = None
            path.write_text(json.dumps(row), encoding="utf-8")
            output = root / "summary.json"
            exit_code = receipt.summarize(self.plan, root, output)
            summary = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["normative_failures"], [target["id"]])
        self.assertTrue(any("lacks an explicit infra_proof" in item for item in summary["errors"]))

    def test_failed_harness_result_cannot_claim_pass(self) -> None:
        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            self._write_all_runnable_normative(root)
            path = root / f"receipt-{target['id']}.json"
            row = self._successful_pass_row(
                target, receipt.planned_commands(self.plan, target)
            )
            row["commands"][0]["exit"] = 1
            path.write_text(json.dumps(row), encoding="utf-8")
            output = root / "summary.json"
            exit_code = receipt.summarize(self.plan, root, output)
            summary = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["normative_failures"], [target["id"]])
        self.assertTrue(any("PASS receipt contains" in item for item in summary["errors"]))

    def test_receipt_supplied_command_manifest_cannot_self_authorize_pass(self) -> None:
        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        canonical = receipt.planned_commands(self.plan, target)
        substituted = [dict(command) for command in canonical]
        substituted[0]["id"] = "substituted-command"
        duplicated = [dict(command) for command in canonical]
        duplicated[1] = dict(duplicated[0])
        variants = {
            "empty": [],
            "reordered": [canonical[1], canonical[0], *canonical[2:]],
            "substituted": substituted,
            "duplicated": duplicated,
            "omitted": canonical[:-1],
        }
        for name, forged_plan in variants.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                self._write_all_runnable_normative(root)
                path = root / f"receipt-{target['id']}.json"
                row = self._successful_pass_row(target, forged_plan)
                path.write_text(json.dumps(row), encoding="utf-8")
                output = root / "summary.json"
                exit_code = receipt.summarize(self.plan, root, output)
                summary = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(summary["normative_failures"], [target["id"]])
            self.assertTrue(
                any("checked-in command manifest" in item for item in summary["errors"])
            )

    def test_canonical_pass_receipt_is_accepted(self) -> None:
        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            self._write_all_runnable_normative(root)
            path = root / f"receipt-{target['id']}.json"
            row = self._successful_pass_row(
                target, receipt.planned_commands(self.plan, target)
            )
            path.write_text(json.dumps(row), encoding="utf-8")
            output = root / "summary.json"
            exit_code = receipt.summarize(self.plan, root, output)
            summary = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["normative_failures"], [])
        self.assertEqual(summary["errors"], [])

    def test_invalid_stress_receipt_is_recorded_but_does_not_gate(self) -> None:
        target = next(
            entry
            for entry in receipt.all_entries(self.plan)
            if entry["classification"] != "normative"
        )
        canonical = self._successful_pass_row(
            target, receipt.planned_commands(self.plan, target)
        )
        canonical["commands"][0]["exit"] = 1
        variants = {
            "invalid_schema": json.dumps(canonical).encode("utf-8"),
            "malformed_json": b"{",
        }
        for name, payload in variants.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                self._write_all_runnable_normative(root)
                path = root / f"receipt-{target['id']}.json"
                path.write_bytes(payload)
                output = root / "summary.json"
                exit_code = receipt.summarize(self.plan, root, output)
                summary = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(summary["normative_failures"], [])
            self.assertEqual(summary["gating_errors"], [])
            self.assertTrue(summary["observation_errors"])
            self.assertEqual(summary["errors"], summary["observation_errors"])
            observed = next(
                row for row in summary["rows"] if row["entry_id"] == target["id"]
            )
            self.assertEqual(observed["outcome"], "RECEIPT_MISSING")

    def test_numeric_validators_are_total_bounded_and_exclude_booleans(self) -> None:
        huge = 10**10_000
        self.assertFalse(receipt._is_nonnegative_number(huge))
        self.assertFalse(receipt._is_nonnegative_number(True))
        self.assertFalse(receipt._is_nonnegative_number(float("inf")))
        self.assertFalse(receipt._is_nonnegative_number(float("nan")))
        self.assertTrue(
            receipt._is_nonnegative_integer(receipt.MAX_RECEIPT_INTEGER)
        )
        self.assertFalse(
            receipt._is_nonnegative_integer(receipt.MAX_RECEIPT_INTEGER + 1)
        )
        self.assertTrue(
            receipt._is_nonnegative_number(receipt.MAX_RECEIPT_SECONDS)
        )
        self.assertFalse(
            receipt._is_nonnegative_number(receipt.MAX_RECEIPT_SECONDS + 1)
        )
        self.assertTrue(
            receipt._is_bounded_integer(
                receipt.MAX_PROCESS_EXIT,
                receipt.MIN_PROCESS_EXIT,
                receipt.MAX_PROCESS_EXIT,
            )
        )
        self.assertFalse(
            receipt._is_bounded_integer(
                receipt.MAX_PROCESS_EXIT + 1,
                receipt.MIN_PROCESS_EXIT,
                receipt.MAX_PROCESS_EXIT,
            )
        )
        self.assertIsNone(
            receipt._version_info_validation_error(
                [
                    receipt.MAX_VERSION_COMPONENT,
                    receipt.MAX_VERSION_COMPONENT,
                    receipt.MAX_VERSION_COMPONENT,
                    "alpha",
                    receipt.MAX_VERSION_COMPONENT,
                ],
                (
                    f"{receipt.MAX_VERSION_COMPONENT}."
                    f"{receipt.MAX_VERSION_COMPONENT}."
                    f"{receipt.MAX_VERSION_COMPONENT}a"
                    f"{receipt.MAX_VERSION_COMPONENT} (boundary)"
                ),
            )
        )
        self.assertIsNotNone(
            receipt._version_info_validation_error(
                [3, 12, 0, "alpha", receipt.MAX_VERSION_COMPONENT + 1],
                "3.12.0a0 (forged)",
            )
        )

    def test_signed_zero_and_underflow_are_rejected_without_losing_tiny_positive(self) -> None:
        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        canonical = self._successful_pass_row(
            target, receipt.planned_commands(self.plan, target)
        )

        def set_elapsed(row: dict[str, object], value: object) -> None:
            row["commands"][0]["elapsed_seconds"] = value

        def set_child_cpu(row: dict[str, object], value: object) -> None:
            row["commands"][0]["resources"]["children_user_seconds"] = value

        invalid = (
            -0.0,
            decimal.Decimal("-0"),
            decimal.Decimal("-0.0"),
            decimal.Decimal("-1e-324"),
        )
        valid = (0, 0.0, decimal.Decimal("0"), decimal.Decimal("1e-324"))
        for field, setter in (("elapsed", set_elapsed), ("child_cpu", set_child_cpu)):
            for value in invalid:
                with self.subTest(field=field, invalid=repr(value)):
                    row = copy.deepcopy(canonical)
                    setter(row, value)
                    self.assertIsNotNone(
                        receipt._receipt_validation_error(row, target, self.plan)
                    )
            for value in valid:
                with self.subTest(field=field, valid=repr(value)):
                    row = copy.deepcopy(canonical)
                    setter(row, value)
                    self.assertIsNone(
                        receipt._receipt_validation_error(row, target, self.plan)
                    )

        self.assertEqual(
            receipt._canonical_json({"tiny": decimal.Decimal("1e-324")}),
            '{\n  "tiny": 1e-324\n}',
        )
        with self.assertRaises(ValueError):
            receipt._canonical_json({"zero": -0.0})

    def test_hostile_numeric_fields_fail_closed_without_validator_exceptions(self) -> None:
        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        canonical = self._successful_pass_row(
            target, receipt.planned_commands(self.plan, target)
        )
        huge = 10**10_000
        mutations = {
            "elapsed_huge_integer": lambda row: row["commands"][0].__setitem__(
                "elapsed_seconds", huge
            ),
            "elapsed_infinite": lambda row: row["commands"][0].__setitem__(
                "elapsed_seconds", float("inf")
            ),
            "elapsed_boolean": lambda row: row["commands"][0].__setitem__(
                "elapsed_seconds", True
            ),
            "byte_count": lambda row: row["commands"][0].__setitem__(
                "stdout_bytes", huge
            ),
            "exit_code": lambda row: row["commands"][0].__setitem__(
                "exit", huge
            ),
            "suite_count": lambda row: row["commands"][0]["suite_counts"].__setitem__(
                "checks", [huge]
            ),
            "cpu_seconds": lambda row: row["commands"][0]["resources"].__setitem__(
                "children_user_seconds", huge
            ),
            "max_rss": lambda row: row["commands"][0]["resources"].__setitem__(
                "max_rss_kib", huge
            ),
            "physical_memory": lambda row: row["environment"]["resources"].__setitem__(
                "physical_memory_bytes", huge
            ),
            "logical_cpu_count": lambda row: row["environment"]["resources"].__setitem__(
                "logical_cpu_count", huge
            ),
            "word_size": lambda row: row["environment"]["abi"].__setitem__(
                "word_size_bits", huge
            ),
            "version_major": lambda row: row["environment"]["runtime"][
                "version_info"
            ].__setitem__(0, huge),
            "version_serial": lambda row: row["environment"]["runtime"][
                "version_info"
            ].__setitem__(4, huge),
            "build_flag_infinite": lambda row: row["environment"]["runtime"][
                "build_flags"
            ].__setitem__("CONFIG_ARGS", float("inf")),
            "git_status_lines": lambda row: row["git"].__setitem__(
                "status_line_count", huge
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                forged = copy.deepcopy(canonical)
                mutate(forged)
                error = receipt._receipt_validation_error(
                    forged, target, self.plan
                )
                self.assertIsNotNone(error)

    def test_finite_numeric_boundary_neighbors_remain_usable(self) -> None:
        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        canonical = self._successful_pass_row(
            target, receipt.planned_commands(self.plan, target)
        )
        command = canonical["commands"][0]
        command["elapsed_seconds"] = (
            command["timeout_seconds"] + receipt.MAX_TIMER_OVERRUN_SECONDS
        )
        command["stdout_bytes"] = receipt.MAX_RECEIPT_INTEGER
        command["stderr_bytes"] = receipt.MAX_RECEIPT_INTEGER
        command["resources"]["children_user_seconds"] = (
            receipt.MAX_RECEIPT_SECONDS
        )
        command["resources"]["children_system_seconds"] = (
            receipt.MAX_RECEIPT_SECONDS
        )
        command["resources"]["max_rss_kib"] = receipt.MAX_RECEIPT_INTEGER
        environment_resources = canonical["environment"]["resources"]
        environment_resources["physical_memory_bytes"] = (
            receipt.MAX_RECEIPT_INTEGER
        )
        environment_resources["disk_total_bytes"] = receipt.MAX_RECEIPT_INTEGER
        environment_resources["disk_free_bytes"] = receipt.MAX_RECEIPT_INTEGER
        self.assertIsNone(
            receipt._receipt_validation_error(canonical, target, self.plan)
        )

        just_over = copy.deepcopy(canonical)
        just_over["commands"][0]["elapsed_seconds"] += 1
        self.assertIsNotNone(
            receipt._receipt_validation_error(just_over, target, self.plan)
        )

    def test_summary_survives_hostile_json_numbers_and_writes_red_result(self) -> None:
        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        canonical = self._successful_pass_row(
            target, receipt.planned_commands(self.plan, target)
        )
        variants = {}
        huge_row = copy.deepcopy(canonical)
        huge_row["commands"][0]["elapsed_seconds"] = 10**309
        variants["huge_integer"] = json.dumps(huge_row)
        encoded = json.dumps(canonical)
        variants["overflowing_float"] = encoded.replace(
            '"elapsed_seconds": 0.0', '"elapsed_seconds": 1e309', 1
        )
        variants["nonstandard_nan"] = encoded.replace(
            '"elapsed_seconds": 0.0', '"elapsed_seconds": NaN', 1
        )

        for name, payload in variants.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                self._write_all_runnable_normative(root)
                path = root / f"receipt-{target['id']}.json"
                path.write_text(payload, encoding="utf-8")
                output = root / "summary.json"
                exit_code = receipt.summarize(self.plan, root, output)
                summary = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertIn(target["id"], summary["normative_failures"])
            self.assertTrue(summary["errors"])

    def test_summary_preserves_numeric_sign_and_exact_tiny_magnitude(self) -> None:
        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        canonical = self._successful_pass_row(
            target, receipt.planned_commands(self.plan, target)
        )
        encoded = json.dumps(canonical)
        fields = ("elapsed_seconds", "children_user_seconds")
        invalid_lexemes = (
            "-0",
            "-0.0",
            "-1e-324",
            "-2.4703282292062327e-324",
            "1e-1000001",
        )

        for field in fields:
            marker = f'"{field}": 0.0'
            self.assertIn(marker, encoded)
            for lexeme in invalid_lexemes:
                with (
                    self.subTest(field=field, invalid=lexeme),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    root = pathlib.Path(directory)
                    self._write_all_runnable_normative(root)
                    path = root / f"receipt-{target['id']}.json"
                    path.write_text(
                        encoded.replace(marker, f'"{field}": {lexeme}', 1),
                        encoding="utf-8",
                    )
                    output = root / "summary.json"
                    exit_code = receipt.summarize(self.plan, root, output)
                    summary = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(exit_code, 1)
                self.assertIn(target["id"], summary["normative_failures"])
                self.assertTrue(summary["errors"])

            for lexeme in ("0", "0.0", "1e-324"):
                with (
                    self.subTest(field=field, valid=lexeme),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    root = pathlib.Path(directory)
                    self._write_all_runnable_normative(root)
                    path = root / f"receipt-{target['id']}.json"
                    path.write_text(
                        encoded.replace(marker, f'"{field}": {lexeme}', 1),
                        encoding="utf-8",
                    )
                    output = root / "summary.json"
                    exit_code = receipt.summarize(self.plan, root, output)
                    summary_text = output.read_text(encoding="utf-8")
                    summary = json.loads(summary_text)
                self.assertEqual(exit_code, 0)
                self.assertEqual(summary["normative_failures"], [])
                self.assertEqual(summary["errors"], [])
                if lexeme == "1e-324":
                    self.assertIn(f'"{field}": 1e-324', summary_text)

    def test_forged_pass_execution_evidence_fails_closed(self) -> None:
        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        canonical = self._successful_pass_row(
            target, receipt.planned_commands(self.plan, target)
        )

        def substitute_temp_path(row: dict[str, object]) -> None:
            command = next(
                item
                for item in row["commands"]
                if item["id"] == "concurrency-focused-smoke"
            )
            command["argv"][-1] = "/runner/temp/substituted.json"

        def drift_deterministic_test_count(row: dict[str, object]) -> None:
            command = next(
                item
                for item in row["commands"]
                if item["id"] == "matrix-receipt-tests"
            )
            expected = command["expected_counts"]["tests"][0]
            command["suite_counts"]["tests"] = [expected + 1]

        mutations = {
            "substituted_interpreter": lambda row: row["commands"][0]["argv"].__setitem__(
                0, "/substituted/python"
            ),
            "substituted_literal_argv": lambda row: row["commands"][0]["argv"].__setitem__(
                1, "-O"
            ),
            "substituted_temp_argv": substitute_temp_path,
            "substituted_cwd": lambda row: row["commands"][0].__setitem__(
                "cwd", "baseline-run"
            ),
            "substituted_timeout": lambda row: row["commands"][0].__setitem__(
                "timeout_seconds", 1
            ),
            "negative_elapsed": lambda row: row["commands"][0].__setitem__(
                "elapsed_seconds", -1.0
            ),
            "malformed_hash": lambda row: row["commands"][0].__setitem__(
                "stdout_sha256", "0" * 63
            ),
            "negative_byte_count": lambda row: row["commands"][0].__setitem__(
                "stdout_bytes", -1
            ),
            "negative_suite_count": lambda row: row["commands"][0][
                "suite_counts"
            ].__setitem__("checks", [-1]),
            "deterministic_test_count_drift": drift_deterministic_test_count,
            "forged_expected_counts": lambda row: row["commands"][0].__setitem__(
                "expected_counts", {"checks": [999]}
            ),
            "forged_mismatch_projection": lambda row: row["commands"][0].__setitem__(
                "expectation_mismatches", ["forged"]
            ),
            "negative_resource": lambda row: row["commands"][0]["resources"].__setitem__(
                "children_user_seconds", -1.0
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                self._write_all_runnable_normative(root)
                row = copy.deepcopy(canonical)
                mutate(row)
                path = root / f"receipt-{target['id']}.json"
                path.write_text(json.dumps(row), encoding="utf-8")
                output = root / "summary.json"
                exit_code = receipt.summarize(self.plan, root, output)
                summary = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(summary["normative_failures"], [target["id"]])
            self.assertTrue(any("invalid receipt" in item for item in summary["errors"]))

    def test_top_level_count_and_environment_aggregates_fail_closed(self) -> None:
        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        canonical = self._successful_pass_row(
            target, receipt.planned_commands(self.plan, target)
        )
        mutations = {
            "top_level_suite_counts": lambda row: row["suite_counts"][0].__setitem__(
                "checks", [999]
            ),
            "negative_git_status_count": lambda row: row["git"].__setitem__(
                "status_line_count", -1
            ),
            "inconsistent_environment_resources": lambda row: row["environment"][
                "resources"
            ].__setitem__(
                "disk_free_bytes", row["environment"]["resources"]["disk_total_bytes"] + 1
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                self._write_all_runnable_normative(root)
                row = copy.deepcopy(canonical)
                mutate(row)
                path = root / f"receipt-{target['id']}.json"
                path.write_text(json.dumps(row), encoding="utf-8")
                output = root / "summary.json"
                exit_code = receipt.summarize(self.plan, root, output)
                summary = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(summary["normative_failures"], [target["id"]])
            self.assertTrue(any("invalid receipt" in item for item in summary["errors"]))

    def test_executed_environment_is_rebound_to_checked_in_normative_row(self) -> None:
        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry["runner"] == "ubuntu-latest"
            and entry["python_version"] == "3.12"
        )
        canonical = self._successful_pass_row(
            target, receipt.planned_commands(self.plan, target)
        )
        self.assertIsNone(receipt._receipt_validation_error(canonical, target, self.plan))

        mutations = {
            "forged_os": lambda row: row["environment"]["os"].__setitem__(
                "system", "Plan9"
            ),
            "forged_implementation": lambda row: row["environment"]["runtime"].__setitem__(
                "implementation", "ForgedPython"
            ),
            "wrong_cpython_minor": lambda row: row["environment"]["runtime"][
                "version_info"
            ].__setitem__(1, 99),
            "contradictory_full_version": lambda row: row["environment"]["runtime"].__setitem__(
                "full_version", "99.99.99 (forged)"
            ),
            "wrong_machine": lambda row: row["environment"]["architecture"].__setitem__(
                "machine", "arm64"
            ),
            "emulated_mode": lambda row: row["environment"]["architecture"].__setitem__(
                "mode", "emulated"
            ),
            "wrong_word_size": lambda row: row["environment"]["abi"].__setitem__(
                "word_size_bits", 32
            ),
            "wrong_byte_order": lambda row: row["environment"]["abi"].__setitem__(
                "byte_order", "big"
            ),
            "wrong_filesystem_encoding": lambda row: row["environment"]["encoding"].__setitem__(
                "filesystem", "cp1252"
            ),
            "missing_github_sha": lambda row: row["git"].__setitem__(
                "github_sha", None
            ),
            "dirty_checkout": lambda row: (
                row["git"].__setitem__("clean", False),
                row["git"].__setitem__("status_line_count", 1),
                row["git"].__setitem__("status_sha256", "b" * 64),
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                forged = copy.deepcopy(canonical)
                mutate(forged)
                error = receipt._receipt_validation_error(forged, target, self.plan)
                self.assertIsNotNone(error)

    def test_native_platform_and_stress_capabilities_are_plan_bound(self) -> None:
        entries = receipt.all_entries(self.plan)
        darwin = next(
            entry
            for entry in entries
            if entry.get("runnable", True) and entry["os_family"] == "Darwin"
        )
        windows = next(
            entry
            for entry in entries
            if entry.get("runnable", True) and entry["os_family"] == "Windows"
        )
        free_threaded = next(
            entry for entry in entries if entry.get("required_capability") == "free_threaded"
        )
        pydebug = next(
            entry for entry in entries if entry.get("required_capability") == "pydebug"
        )
        dev_mode = next(
            entry for entry in entries if entry.get("required_capability") == "dev_mode"
        )
        alternative = next(entry for entry in entries if entry.get("runtime") == "PyPy")

        mutations = (
            (darwin, lambda row: row["environment"]["architecture"].__setitem__(
                "darwin_rosetta", None
            )),
            (windows, lambda row: row["environment"]["architecture"].__setitem__(
                "windows_wow64", True
            )),
            (free_threaded, lambda row: row["environment"]["runtime"]["build_flags"].__setitem__(
                "Py_GIL_DISABLED", 0
            )),
            (free_threaded, lambda row: row["environment"]["runtime"].__setitem__(
                "gil_enabled", True
            )),
            (pydebug, lambda row: row["environment"]["runtime"]["build_flags"].__setitem__(
                "Py_DEBUG", 0
            )),
            (dev_mode, lambda row: row["environment"]["runtime"].__setitem__(
                "dev_mode", False
            )),
            (alternative, lambda row: row["environment"]["runtime"].__setitem__(
                "implementation", "CPython"
            )),
        )
        for entry, mutate in mutations:
            with self.subTest(entry=entry["id"]):
                canonical = self._successful_pass_row(
                    entry, receipt.planned_commands(self.plan, entry)
                )
                self.assertIsNone(
                    receipt._receipt_validation_error(canonical, entry, self.plan)
                )
                forged = copy.deepcopy(canonical)
                mutate(forged)
                self.assertIsNotNone(
                    receipt._receipt_validation_error(forged, entry, self.plan)
                )

    def test_graalpy_distribution_and_language_versions_are_separately_bound(self) -> None:
        entry = next(
            item for item in receipt.all_entries(self.plan)
            if item["id"] == "off-contract-graalpy-24-0-ubuntu-latest-x64"
        )
        self.assertEqual(entry["classification"], "off_contract")
        self.assertEqual(entry["distribution_release"], "24.0")
        self.assertEqual(entry["python_language_version"], "3.10")
        canonical = self._successful_pass_row(
            entry, receipt.planned_commands(self.plan, entry)
        )
        self.assertIsNone(
            receipt._receipt_validation_error(canonical, entry, self.plan)
        )

        for triple in ((99, 99, 7), (3, 8, 7), (3, 14, 7)):
            with self.subTest(language_version=triple):
                forged = copy.deepcopy(canonical)
                runtime = forged["environment"]["runtime"]
                runtime["version_info"][:3] = list(triple)
                runtime["full_version"] = ".".join(map(str, triple)) + " (forged)"
                self.assertIsNotNone(
                    receipt._receipt_validation_error(forged, entry, self.plan)
                )

        for resolved in (None, "graalpy23.1.2", "graalpy24.1.0", "3.10.8"):
            with self.subTest(resolved_setup_version=resolved):
                forged = copy.deepcopy(canonical)
                forged["environment"]["runtime"]["setup_python_version"] = resolved
                self.assertIsNotNone(
                    receipt._receipt_validation_error(forged, entry, self.plan)
                )

        patch_neighbor = copy.deepcopy(canonical)
        patch_neighbor["environment"]["runtime"][
            "setup_python_version"
        ] = "graalpy24.0.999"
        self.assertIsNone(
            receipt._receipt_validation_error(patch_neighbor, entry, self.plan)
        )

    def test_version_info_release_metadata_is_fail_closed_for_all_runtimes(self) -> None:
        entries = [
            next(
                item for item in receipt.all_entries(self.plan)
                if item["implementation"] == implementation
            )
            for implementation in ("CPython", "PyPy", "GraalVM")
        ]
        for entry in entries:
            canonical = self._successful_pass_row(
                entry, receipt.planned_commands(self.plan, entry)
            )
            self.assertIsNone(
                receipt._receipt_validation_error(canonical, entry, self.plan)
            )
            runtime = canonical["environment"]["runtime"]
            base = ".".join(map(str, runtime["version_info"][:3]))

            for releaselevel, serial, suffix in (
                ("alpha", 0, "a0"),
                ("beta", 2, "b2"),
                ("candidate", 1, "rc1"),
            ):
                with self.subTest(
                    implementation=entry["implementation"],
                    releaselevel=releaselevel,
                ):
                    neighbor = copy.deepcopy(canonical)
                    neighbor_runtime = neighbor["environment"]["runtime"]
                    neighbor_runtime["version_info"][3:] = [releaselevel, serial]
                    neighbor_runtime["full_version"] = f"{base}{suffix} (synthetic)"
                    self.assertIsNone(
                        receipt._receipt_validation_error(neighbor, entry, self.plan)
                    )

            mutations = {
                "unknown_releaselevel": lambda value: value["version_info"].__setitem__(
                    3, "forged"
                ),
                "nonscalar_releaselevel": lambda value: value["version_info"].__setitem__(
                    3, ["final"]
                ),
                "negative_serial": lambda value: value["version_info"].__setitem__(
                    4, -1
                ),
                "boolean_serial": lambda value: value["version_info"].__setitem__(
                    4, True
                ),
                "final_nonzero_serial": lambda value: value["version_info"].__setitem__(
                    4, 1
                ),
                "negative_micro": lambda value: value["version_info"].__setitem__(
                    2, -1
                ),
                "boolean_major": lambda value: value["version_info"].__setitem__(
                    0, True
                ),
                "tuple_not_json_array": lambda value: value.__setitem__(
                    "version_info", tuple(value["version_info"])
                ),
                "short_version_info": lambda value: value.__setitem__(
                    "version_info", value["version_info"][:-1]
                ),
                "long_version_info": lambda value: value.__setitem__(
                    "version_info", [*value["version_info"], 0]
                ),
                "prerelease_marker_on_final": lambda value: value.__setitem__(
                    "full_version", f"{base}rc1 (forged)"
                ),
            }
            for name, mutate in mutations.items():
                with self.subTest(
                    implementation=entry["implementation"], mutation=name
                ):
                    forged = copy.deepcopy(canonical)
                    mutate(forged["environment"]["runtime"])
                    self.assertIsNotNone(
                        receipt._receipt_validation_error(forged, entry, self.plan)
                    )

            for releaselevel, serial, displayed in (
                ("alpha", 1, f"{base}a2 (forged)"),
                ("beta", 3, f"{base} (forged)"),
                ("candidate", 4, f"{base}b4 (forged)"),
            ):
                with self.subTest(
                    implementation=entry["implementation"],
                    inconsistent_display=releaselevel,
                ):
                    forged = copy.deepcopy(canonical)
                    forged_runtime = forged["environment"]["runtime"]
                    forged_runtime["version_info"][3:] = [releaselevel, serial]
                    forged_runtime["full_version"] = displayed
                    self.assertIsNotNone(
                        receipt._receipt_validation_error(forged, entry, self.plan)
                    )

    def test_pass_executed_command_order_is_bound_to_manifest(self) -> None:
        target = next(
            entry
            for entry in receipt._normative_entries(self.plan)
            if entry.get("runnable", True)
        )
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            self._write_all_runnable_normative(root)
            path = root / f"receipt-{target['id']}.json"
            row = self._successful_pass_row(
                target, receipt.planned_commands(self.plan, target)
            )
            row["commands"][0], row["commands"][1] = (
                row["commands"][1],
                row["commands"][0],
            )
            row["suite_counts"][0], row["suite_counts"][1] = (
                row["suite_counts"][1],
                row["suite_counts"][0],
            )
            path.write_text(json.dumps(row), encoding="utf-8")
            output = root / "summary.json"
            exit_code = receipt.summarize(self.plan, root, output)
            summary = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["normative_failures"], [target["id"]])
        self.assertTrue(
            any(
                "identities or order" in item or "command id does not match" in item
                for item in summary["errors"]
            )
        )

    def test_executed_infra_receipt_has_all_required_field_groups(self) -> None:
        entry = next(
            item
            for item in receipt._normative_entries(self.plan)
            if item.get("runnable", True)
        )
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "receipt.json"
            exit_code = receipt.unavailable_entry(
                self.plan,
                entry,
                output,
                "local deterministic validation",
                "runtime_setup_unavailable",
                "steps.setup.outcome=failure",
            )
            row = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(row["outcome"], "INFRA_UNAVAILABLE")
        self.assertEqual(len(row["commands_planned"]), 42)
        for field in (
            "git",
            "environment",
            "commands_planned",
            "commands",
            "suite_counts",
            "outcome",
            "reason",
            "infra_proof",
        ):
            self.assertIn(field, row)
        self.assertEqual(row["infra_proof"]["kind"], "runtime_setup_unavailable")

    def test_normative_divergence_fails_summary_but_infra_does_not(self) -> None:
        entry = next(item for item in receipt._normative_entries(self.plan) if item["runnable"])
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            self._write_all_runnable_normative(root)
            path = root / f"receipt-{entry['id']}.json"
            bad = self._successful_pass_row(
                entry, receipt.planned_commands(self.plan, entry)
            )
            bad["outcome"] = "DIVERGENCE"
            bad["reason"] = f"first failing command: {bad['commands'][0]['id']}"
            bad["commands"] = bad["commands"][:1]
            bad["commands"][0]["exit"] = 1
            bad["suite_counts"] = bad["suite_counts"][:1]
            path.write_text(json.dumps(bad), encoding="utf-8")
            output = root / "summary.json"
            exit_code = receipt.summarize(self.plan, root, output)
            summary = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["normative_failures"], [entry["id"]])

    def test_summarize_cli_resolves_the_authority_and_passes_it_down(self) -> None:
        # E17: main() is the one place GITHUB_SHA is read.  This is the end of
        # that wire -- if the CLI stops passing the resolved commit down, or
        # starts accepting an absent or empty one, an arm here goes red.
        cases = (
            (["--workflow-sha", FIXTURE_WORKFLOW_SHA], None, 0),
            (["--workflow-sha", FOREIGN_RUN_SHA], None, 1),
            ([], FIXTURE_WORKFLOW_SHA, 0),
            ([], FOREIGN_RUN_SHA, 1),
            ([], None, 2),
            ([], "", 2),
        )
        for extra, ambient, expected_code in cases:
            with self.subTest(extra=extra, ambient=ambient), \
                    mock.patch.dict(os.environ, {}, clear=False), \
                    tempfile.TemporaryDirectory() as directory:
                os.environ.pop("GITHUB_SHA", None)
                if ambient is not None:
                    os.environ["GITHUB_SHA"] = ambient
                root = pathlib.Path(directory)
                os.environ["RUNNER_TEMP"] = str(root)
                receipts_dir = root / "receipts"
                receipts_dir.mkdir()
                self._write_all_runnable_normative(receipts_dir)
                exit_code = receipt.main(
                    [
                        "summarize",
                        "--receipts-dir",
                        str(receipts_dir),
                        "--output-name",
                        "matrix-summary.json",
                    ]
                    + extra
                )
                self.assertEqual(exit_code, expected_code)
                if expected_code == 2:
                    self.assertFalse((root / "matrix-summary.json").exists())

    def test_summary_binds_every_receipt_to_the_run_it_summarizes(self) -> None:
        # ERRATA E17.  The forgery this clause exists to stop is a receipt
        # retained from an older green run and re-uploaded as this run's
        # artifact.  It is internally consistent -- sha == github_sha, clean
        # checkout, empty status -- so every other git check passes, and an
        # INFRA_UNAVAILABLE outcome then suppresses a normative row that was
        # never executed.  The only thing that catches it is the commit the
        # caller says this summary is about.  Vary the ambient GITHUB_SHA
        # across all three states: if this authority is ever read from the
        # environment again, or dropped from summarize's internal call, one of
        # these six arms goes red.
        for ambient in (None, FIXTURE_WORKFLOW_SHA, FOREIGN_RUN_SHA):
            for authority, expected_code in (
                (FIXTURE_WORKFLOW_SHA, 0),
                (FOREIGN_RUN_SHA, 1),
            ):
                with self.subTest(ambient=ambient, authority=authority), \
                        mock.patch.dict(os.environ, {}, clear=False), \
                        tempfile.TemporaryDirectory() as directory:
                    os.environ.pop("GITHUB_SHA", None)
                    if ambient is not None:
                        os.environ["GITHUB_SHA"] = ambient
                    root = pathlib.Path(directory)
                    self._write_all_runnable_normative(root)
                    output = root / "summary.json"
                    exit_code = receipt.summarize(
                        self.plan, root, output, workflow_sha=authority
                    )
                    summary = json.loads(output.read_text(encoding="utf-8"))
                    self.assertEqual(exit_code, expected_code)
                    if expected_code:
                        self.assertTrue(summary["normative_failures"])
                        self.assertTrue(
                            any(
                                "does not match the expected workflow sha" in error
                                for error in summary["errors"]
                            ),
                            summary["errors"][:3],
                        )
                    else:
                        self.assertEqual(summary["normative_failures"], [])



class WorkflowDefinitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = receipt.REPO_ROOT / ".github" / "workflows" / "portability.yml"
        cls.text = cls.path.read_text(encoding="utf-8")

    def test_authority_boundary_and_triggers(self) -> None:
        self.assertIn("permissions:\n  contents: read\n", self.text)
        self.assertRegex(
            self.text,
            r"(?m)^on:\n  push:\n    branches:\n      - main\n  workflow_dispatch:\n",
        )
        for forbidden in (
            "pull_request:",
            "schedule:",
            "repository_dispatch:",
            "workflow_run:",
            "self-hosted",
            "${{ secrets.",
            "actions/cache",
            "cache:",
            "deployment:",
        ):
            self.assertNotIn(forbidden, self.text)

    def test_actions_are_commit_pinned_and_macos_13_is_not_scheduled(self) -> None:
        uses = re.findall(r"(?m)^\s*uses:\s*([^\s#]+)", self.text)
        self.assertTrue(uses)
        self.assertTrue(all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", item) for item in uses))
        self.assertEqual(
            set(uses),
            {
                "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
                "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
                "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
                "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
            },
        )
        self.assertNotIn("macos-13", self.text)
        self.assertIn("macos-15-intel", receipt.DEFAULT_PLAN.read_text(encoding="utf-8"))

    def test_sandbox_supplements_native_expanded_gate(self) -> None:
        self.assertIn("expanded_gate:", self.text)
        self.assertIn("sandbox:", self.text)
        self.assertIn("portability/sandbox/run_sandbox.py", self.text)

    def test_normative_jobs_and_artifact_transport_fail_closed(self) -> None:
        normative = self.text.split("\n  normative:\n", 1)[1].split("\n  stress:\n", 1)[0]
        expanded = self.text.split("\n  expanded_gate:\n", 1)[1].split("\n  sandbox:\n", 1)[0]
        summary = self.text.split("\n  summarize:\n", 1)[1]
        self.assertNotRegex(normative, r"(?m)^    continue-on-error: true$")
        self.assertNotRegex(expanded, r"(?m)^    continue-on-error: true$")
        self.assertIn("--proof-kind \"runtime_setup_unavailable\"", normative)
        self.assertIn("--proof-kind \"runtime_setup_unavailable\"", expanded)
        self.assertIn("--evidence \"steps.setup.outcome=failure\"", normative)
        self.assertIn("--evidence \"steps.setup.outcome=failure\"", expanded)
        self.assertIn("if-no-files-found: error", normative)
        self.assertIn("if-no-files-found: error", expanded)

        download = summary.split("- name: Download available receipts", 1)[1].split(
            "- name: Separate outcomes", 1
        )[0]
        self.assertNotIn("continue-on-error", download)
        self.assertIn('--normative-job-result "${{ needs.normative.result }}"', summary)
        self.assertIn(
            '--expanded-gate-job-result "${{ needs.expanded_gate.result }}"', summary
        )

    def test_stress_receipts_capture_setup_python_resolved_version(self) -> None:
        stress = self.text.split("\n  stress:\n", 1)[1].split(
            "\n  expanded_gate:\n", 1
        )[0]
        binding = "RR_SETUP_PYTHON_VERSION: ${{ steps.setup.outputs.python-version }}"
        self.assertEqual(stress.count(binding), 2)

    def test_stress_is_observation_only_while_normative_results_gate(self) -> None:
        stress = self.text.split("\n  stress:\n", 1)[1].split(
            "\n  expanded_gate:\n", 1
        )[0]
        summary = self.text.split("\n  summarize:\n", 1)[1]
        self.assertRegex(stress, r"(?m)^    continue-on-error: true$")
        self.assertNotIn("--stress-job-result", summary)
        readme = (receipt.HERE / "README.md").read_text(encoding="utf-8")
        normalized = re.sub(r"\s+", " ", readme)
        self.assertIn("Normative and expanded-gate receipt failures are gating", normalized)
        self.assertIn("Stress and off-contract rows are observation-only", normalized)
        self.assertIn(
            "No efficacy, novelty, security, fuzzing-completeness, "
            "external-standard, or universal-portability claim.",
            normalized,
        )

    def test_sandbox_checkout_fetches_full_history(self) -> None:
        # F-SANDBOX-026: the sandbox host preflight verifies baseline
        # ancestry with `git merge-base --is-ancestor`, which exits 128 in a
        # shallow default checkout because the baseline commit is absent.
        # The sandbox job must therefore check out full history.
        sandbox = self.text.split("\n  sandbox:\n", 1)[1].split(
            "\n  summarize:\n", 1
        )[0]
        self.assertRegex(
            sandbox,
            r"actions/checkout@[0-9a-f]{40}[^\n]*\n"
            r"        with:\n"
            r"(?:          [^\n]*\n)*?"
            r"          fetch-depth: 0\n",
        )


class LocalGateRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if str(receipt.REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(receipt.REPO_ROOT))
        import importlib

        cls.runner = importlib.import_module("portability.run_local_expanded_gate")

    def test_receipt_destination_policy(self) -> None:
        runner = self.runner
        self.assertIsNone(
            runner.receipt_path_error(runner.RECEIPT_ROOT / "fresh-receipt.json")
        )
        outside = pathlib.Path(tempfile.gettempdir()) / "rr-gate-receipt.json"
        self.assertIsNone(runner.receipt_path_error(outside))
        inside = runner.REPO / "portability" / "model" / "receipt.json"
        self.assertIsNotNone(runner.receipt_path_error(inside))
        self.assertIsNotNone(runner.receipt_path_error(runner.REPO / "receipt.json"))

    def test_pass_requires_clean_to_clean_full_run(self) -> None:
        runner = self.runner
        gates = len(runner.expanded_gate.GATES)
        start = {"clean": True, "head": "a" * 40}
        end = {"clean": True, "head": "a" * 40}
        self.assertEqual(runner.receipt_status(0, start, end, gates), "PASS")
        self.assertEqual(runner.receipt_status(1, start, end, gates), "FAIL")
        self.assertEqual(
            runner.receipt_status(0, start, {"clean": False, "head": "a" * 40}, gates),
            "FAIL",
        )
        self.assertEqual(
            runner.receipt_status(0, start, {"clean": True, "head": "b" * 40}, gates),
            "FAIL",
        )
        self.assertEqual(
            runner.receipt_status(0, {"clean": False, "head": "a" * 40}, end, gates),
            "FAIL",
        )
        self.assertEqual(runner.receipt_status(0, start, end, gates - 1), "FAIL")


class RunCurrencyAuthorityTests(unittest.TestCase):
    """ERRATA E17: run currency is an argument, never an ambient variable.

    `_runnable_git_binding_error` used to compare a receipt's recorded sha to
    os.environ["GITHUB_SHA"].  That variable is not an artifact, so the same
    bytes produced different verdicts in different shells: the clause was
    silent everywhere the variable was unset -- every local run, the README's
    third-party command, and every matrix child, because SAFE_ENV_KEYS strips
    it -- and unsatisfiable where it was set against sealed historical
    evidence.  These tests hold the receipt fixed and vary the environment,
    which is the axis the rest of this suite deliberately does not vary.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = receipt._json_load(receipt.DEFAULT_PLAN)

    @staticmethod
    def _clean_git(sha: str) -> dict[str, object]:
        return {
            "sha": sha,
            "github_sha": sha,
            "clean": True,
            "status_sha256": hashlib.sha256(b"").hexdigest(),
            "status_line_count": 0,
        }

    def test_run_currency_authority_has_no_default(self) -> None:
        # Omission must be a TypeError at the call site.  A default would let a
        # future caller drop the authority and stay green.
        with self.assertRaises(TypeError):
            receipt._runnable_git_binding_error(
                self._clean_git(FIXTURE_WORKFLOW_SHA)
            )

    def test_binding_verdict_is_a_function_of_its_argument_only(self) -> None:
        git = self._clean_git(FIXTURE_WORKFLOW_SHA)
        rejection = "runnable receipt sha does not match the expected workflow sha"
        for ambient in (None, FIXTURE_WORKFLOW_SHA, FOREIGN_RUN_SHA):
            with self.subTest(ambient=ambient), \
                    mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("GITHUB_SHA", None)
                if ambient is not None:
                    os.environ["GITHUB_SHA"] = ambient
                self.assertIsNone(
                    receipt._runnable_git_binding_error(git, None)
                )
                self.assertIsNone(
                    receipt._runnable_git_binding_error(git, FIXTURE_WORKFLOW_SHA)
                )
                self.assertEqual(
                    receipt._runnable_git_binding_error(git, FOREIGN_RUN_SHA),
                    rejection,
                )

    def test_hosted_replay_binds_rows_to_the_hosted_run(self) -> None:
        # The committed hosted tree is evidence about HOSTED_HEAD, so that is
        # the commit its rows must name.  This calls the single site that
        # supplies the authority, `verify_receipts._hosted_row_error`, so
        # dropping the argument there turns this red rather than leaving a
        # tautology behind.
        portability_dir = str(REPO / "portability")
        if portability_dir not in sys.path:
            sys.path.insert(0, portability_dir)
        import verify_receipts

        plan = verify_receipts._hosted_era_plan()
        accepted = None
        for path in sorted(verify_receipts.HOSTED_DIR.glob("receipt-*.json")):
            row = json.loads(path.read_text(encoding="utf-8"))
            entry = receipt.find_entry(plan, row.get("entry_id"))
            if not entry.get("runnable", True):
                continue
            if verify_receipts._hosted_row_error(plan, row) is None:
                accepted = row
                break
        self.assertIsNotNone(
            accepted, "no committed runnable hosted row is currently accepted"
        )
        self.assertEqual(accepted["git"]["sha"], verify_receipts.HOSTED_HEAD)
        forged = dict(accepted)
        forged["git"] = {
            **accepted["git"],
            "sha": FOREIGN_RUN_SHA,
            "github_sha": FOREIGN_RUN_SHA,
        }
        self.assertEqual(
            verify_receipts._hosted_row_error(plan, forged),
            "runnable receipt sha does not match the expected workflow sha",
        )

    def test_committed_receipt_verdict_does_not_depend_on_github_sha(self) -> None:
        # The command README gives third parties must return the same verdict
        # in a shell where GITHUB_SHA is set as in one where it is not.  This
        # asserts equality, not success: whether the committed evidence is
        # green is `verify-committed-receipts`' job in the same plan profile.
        verifier = REPO / "portability" / "verify_receipts.py"
        results = {}
        for label, ambient in (("absent", None), ("present", FOREIGN_RUN_SHA)):
            environment = dict(os.environ)
            environment.pop("GITHUB_SHA", None)
            if ambient is not None:
                environment["GITHUB_SHA"] = ambient
            results[label] = subprocess.run(
                [sys.executable, "-B", str(verifier)],
                cwd=REPO,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
        absent, present = results["absent"], results["present"]
        self.assertEqual(
            absent.returncode, present.returncode, present.stdout[-600:]
        )
        self.assertEqual(
            absent.stdout.strip().splitlines()[-1],
            present.stdout.strip().splitlines()[-1],
        )


if __name__ == "__main__":
    unittest.main()
