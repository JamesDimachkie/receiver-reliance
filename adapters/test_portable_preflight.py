"""Stdlib regressions for the shipping WP1 portable fallback."""

from __future__ import annotations

import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import adapters
from adapters.portable_preflight import (
    FACT_PROFILE_FORMAT_VERSION,
    INSUFFICIENT_EVIDENCE,
    READY,
    REJECTED_INVALID,
    RESULT_FORMAT_VERSION,
    RESULT_STATUSES,
    preflight,
    process_jsonl,
)

HASH_A = "A" * 64


def ref_record(**overrides):
    row = {
        "record_id": "REC_REF",
        "family": "REF",
        "native": {"referenced_record": "authority.md", "claimed_sha256": HASH_A},
        "observations": {"referenced_record_found": True, "observed_sha256": HASH_A},
    }
    row.update(overrides)
    return row


def lifecycle_timestamps(*timestamps):
    return {
        "record_id": "REC_LIFE",
        "family": "LIFECYCLE",
        "native": {"status": "closed"},
        "observations": {"lifecycle_event_timestamps": list(timestamps)},
    }


class TaxonomyTests(unittest.TestCase):
    def test_taxonomy_is_closed_and_versioned(self):
        self.assertEqual(RESULT_FORMAT_VERSION, "RR-PORTABLE-PREFLIGHT-1")
        self.assertEqual(
            RESULT_STATUSES,
            {READY, REJECTED_INVALID, INSUFFICIENT_EVIDENCE},
        )

    def test_ref_alias_contradiction_is_invalid_detection_class(self):
        record = ref_record(
            native={
                "claimed_path": "archive/authority.md",
                "referenced_record": "authority.md",
                "claimed_sha256": None,
            },
            observations={
                "referenced_record_found": False,
                "found_at_archived_location": True,
                "observed_sha256": HASH_A,
            },
        )
        result = preflight(record)
        self.assertEqual(result.status, REJECTED_INVALID)
        self.assertEqual(result.issues[0].code, "PREFLIGHT_REF_ALIAS_CONTRADICTION")

    def test_equal_or_decreasing_timestamps_are_invalid_before_applicability(self):
        for values in ((10, 10), (11, 10)):
            with self.subTest(values=values):
                result = preflight(lifecycle_timestamps(*values))
                self.assertEqual(result.status, REJECTED_INVALID)
                self.assertEqual(
                    result.issues[0].code,
                    "PREFLIGHT_LIFECYCLE_NONINCREASING",
                )

    def test_untyped_noncontradictory_lifecycle_is_insufficient(self):
        result = preflight(lifecycle_timestamps(10, 20))
        self.assertEqual(result.status, INSUFFICIENT_EVIDENCE)
        self.assertEqual(result.issues[0].code, "PREFLIGHT_LIFECYCLE_UNTYPED")
        self.assertFalse(result.ready)

    def test_ready_is_eligibility_not_an_engine_pass(self):
        result = preflight(ref_record())
        self.assertEqual(result.status, READY)
        self.assertTrue(result.ready)
        self.assertFalse(hasattr(result, "pass"))
        self.assertFalse(hasattr(result, "behavior_class"))


class FactProfileTests(unittest.TestCase):
    def _profile(self, record):
        evidence = preflight(record)
        self.assertEqual(evidence.status, READY)
        return {
            "format_version": FACT_PROFILE_FORMAT_VERSION,
            "record_id": record["record_id"],
            "obligation_id": "OBL-02",
            "native_evidence_sha256": evidence.native_evidence_sha256,
            "facts": {
                "exact_reference": "authority.md",
                "record_versions": [
                    {"record_id": "authority.md", "revision_sha256": HASH_A},
                    {"record_id": "authority.md", "revision_sha256": HASH_A},
                ],
            },
            "derivations": {
                "exact_reference": [
                    "/native/claimed_path",
                    "/native/referenced_record",
                ],
                "record_versions": [
                    "/native/claimed_sha256",
                    "/observations/referenced_record_found",
                    "/observations/observed_sha256",
                ],
            },
            "fabricated_fields": [],
        }

    def test_exact_host_profile_is_ready(self):
        record = ref_record()
        result = preflight(record, self._profile(record))
        self.assertEqual(result.status, READY)
        self.assertTrue(result.profile_checked)

    def test_stale_or_tampered_profile_is_invalid(self):
        record = ref_record()
        profile = self._profile(record)
        profile["native_evidence_sha256"] = "B" * 64
        profile["facts"]["exact_reference"] = "other.md"
        result = preflight(record, profile)
        self.assertEqual(result.status, REJECTED_INVALID)
        self.assertEqual(
            {problem.code for problem in result.issues},
            {
                "PREFLIGHT_PROFILE_EVIDENCE_MISMATCH",
                "PREFLIGHT_PROFILE_FACT_MISMATCH",
            },
        )


class PortabilityAndBoundaryTests(unittest.TestCase):
    def test_all_408_statuses_derive_before_truth_join(self):
        records = [
            json.loads(line)
            for line in (HERE / "fixtures" / "parent_corpus_408.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        statuses = Counter()
        family_statuses = Counter()
        issues = Counter()
        for record in records:
            result = preflight(record)
            statuses[result.status] += 1
            family_statuses[(record["family"], result.status)] += 1
            issues.update(problem.code for problem in result.issues)
        self.assertEqual(
            statuses,
            {READY: 192, REJECTED_INVALID: 8, INSUFFICIENT_EVIDENCE: 208},
        )
        self.assertEqual(family_statuses[("REF", REJECTED_INVALID)], 5)
        self.assertEqual(family_statuses[("LIFECYCLE", REJECTED_INVALID)], 3)
        self.assertEqual(family_statuses[("LIFECYCLE", INSUFFICIENT_EVIDENCE)], 208)
        self.assertEqual(issues["PREFLIGHT_REF_ALIAS_CONTRADICTION"], 5)
        self.assertEqual(issues["PREFLIGHT_LIFECYCLE_NONINCREASING"], 3)
        self.assertEqual(issues["PREFLIGHT_LIFECYCLE_UNTYPED"], 208)

    def test_runtime_source_has_no_truth_or_runner_dependency(self):
        source = (HERE / "portable_preflight.py").read_text(encoding="utf-8")
        tests = pathlib.Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn("parent" + "_truth", source)
        self.assertNotIn("pcb" + "_runner", source)
        self.assertNotIn("reference" + "_host", source)
        self.assertNotIn("outcome" + "_receipt", tests)
        self.assertNotIn("reference" + "_host", tests)
        self.assertNotIn("pcb" + "_runner", tests)

    def test_mutable_runner_replacement_cannot_enter_fallback(self):
        fake_runner = type("FakeRunner", (), {"_execute": lambda *_: ({"ok": True}, 0)})
        baseline = preflight(ref_record()).as_dict()
        with mock.patch.dict(sys.modules, {"pcb" + "_runner": fake_runner}):
            replaced = preflight(ref_record()).as_dict()
        self.assertEqual(replaced, baseline)

    def test_public_api_excludes_stood_down_surfaces(self):
        self.assertEqual(set(adapters.__all__), {
            "FACT_PROFILE_FORMAT_VERSION",
            "INSUFFICIENT_EVIDENCE",
            "READY",
            "REJECTED_INVALID",
            "RESULT_FORMAT_VERSION",
            "RESULT_STATUSES",
            "PreflightIssue",
            "PreflightResult",
            "preflight",
            "process_jsonl",
        })
        for name in (
            "adapt_record",
            "build_engine_request",
            "build_transcript_entry",
            "reconcile_effect_log",
            "SQLiteNonceStore",
        ):
            self.assertFalse(hasattr(adapters, name), name)

    def test_scope_paths_are_opaque_and_not_limited_to_one_os(self):
        record = {
            "record_id": "REC_SCOPE",
            "family": "SCOPE",
            "native": {
                "claimed_paths": [
                    "EXTERNAL ARCHIVE ONLY: C:\\archive\\**",
                    "portable/src/**",
                ],
                "result_commit_named": False,
                "status": "closed",
            },
            "observations": {"commit_found": False, "commit_changed_paths": None},
        }
        self.assertEqual(preflight(record).status, READY)


class JsonlCliTests(unittest.TestCase):
    def test_stream_api_emits_one_versioned_result_per_row(self):
        source = io.StringIO(
            json.dumps(ref_record())
            + "\n"
            + json.dumps(lifecycle_timestamps(10, 20))
            + "\n"
        )
        sink = io.StringIO()
        self.assertEqual(process_jsonl(source, sink), 2)
        rows = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual([row["status"] for row in rows], [READY, INSUFFICIENT_EVIDENCE])
        self.assertTrue(all(row["format_version"] == RESULT_FORMAT_VERSION for row in rows))

    def test_cli_uses_stdio_without_absolute_paths(self):
        completed = subprocess.run(
            [sys.executable, "-B", "adapters/portable_preflight.py"],
            cwd=REPO,
            input=json.dumps(ref_record()) + "\n",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], READY)


class FailClosedBoundaryTests(unittest.TestCase):
    """Regressions for the fail-closed boundary law (F-WP1-010..013)."""

    def _run(self, text):
        sink = io.StringIO()
        code = process_jsonl(io.StringIO(text), sink)
        rows = [json.loads(line) for line in sink.getvalue().splitlines()]
        return code, rows

    def test_empty_or_blank_stream_is_insufficient_not_success(self):
        for text in ("", "\n \n\t\n"):
            with self.subTest(text=repr(text)):
                code, rows = self._run(text)
                self.assertEqual(code, 2)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["status"], INSUFFICIENT_EVIDENCE)
                self.assertEqual(rows[0]["issues"][0]["code"], "PREFLIGHT_STREAM_EMPTY")

    def test_duplicate_object_members_are_rejected_not_last_wins(self):
        code, rows = self._run('{"record_id":"a","record_id":"b"}\n')
        self.assertEqual(code, 2)
        self.assertEqual(rows[0]["status"], REJECTED_INVALID)
        self.assertIn("duplicate object member", rows[0]["issues"][0]["message"])

    def test_nested_duplicate_members_are_rejected(self):
        record = (
            '{"record_id":"r","family":"REF",'
            '"native":{"claimed_sha256":null,"claimed_sha256":null},'
            '"observations":{}}'
        )
        code, rows = self._run(record + "\n")
        self.assertEqual(code, 2)
        self.assertEqual(rows[0]["status"], REJECTED_INVALID)

    def test_parser_resource_errors_become_deterministic_line_results(self):
        # A deeply nested row must yield exactly one deterministic
        # REJECTED_INVALID line and never a crash.  The specific issue code
        # is host-parser-dependent and deliberately NOT asserted: CPython
        # 3.12/3.13 reject this depth in the parser (PREFLIGHT_JSONL_INVALID)
        # while 3.14's parser accepts it and the non-object array is rejected
        # downstream (PREFLIGHT_RECORD_NOT_OBJECT).  The fail-closed invariant
        # is identical across versions; asserting the code would be a
        # host-specific portability claim (F-WP1-011).
        deep = "[" * 4000 + "]" * 4000
        code, rows = self._run(deep + "\n")
        self.assertEqual(code, 2)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], REJECTED_INVALID)
        self.assertTrue(rows[0]["issues"], rows[0])

    def test_newline_free_flood_is_bounded_and_rejected(self):
        code, rows = self._run("x" * (5 * 1024 * 1024))
        self.assertEqual(code, 2)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], REJECTED_INVALID)
        self.assertIn("exceeds", rows[0]["issues"][0]["message"])

    def test_out_of_domain_integers_are_domain_violations(self):
        record = ref_record(
            native={
                "referenced_record": "authority.md",
                "claimed_sha256": None,
                "n": 2**63,
            }
        )
        result = preflight(record)
        self.assertEqual(result.status, REJECTED_INVALID)
        self.assertEqual(result.issues[0].code, "PREFLIGHT_JSON_DOMAIN_INVALID")

    def test_scope_digest_is_injective_across_newline_items(self):
        from adapters.portable_preflight import _scope_hash

        self.assertNotEqual(_scope_hash(["a\nb"]), _scope_hash(["a", "b"]))

    def test_type_strict_equality_distinguishes_bool_from_int(self):
        from adapters.portable_preflight import _strict_equal

        self.assertFalse(_strict_equal(True, 1))
        self.assertFalse(_strict_equal({"a": [True]}, {"a": [1]}))
        self.assertTrue(_strict_equal({"a": [0, "x"]}, {"a": [0, "x"]}))

    def test_precedence_rejected_dominates_insufficient(self):
        record = {
            "record_id": "REC_X",
            "family": "UNKNOWN",
            "native": {},
            "observations": {},
        }
        profile = {
            "format_version": FACT_PROFILE_FORMAT_VERSION,
            "record_id": "OTHER",
            "obligation_id": "OBL-99",
            "native_evidence_sha256": HASH_A,
            "facts": {},
            "derivations": {},
            "fabricated_fields": [],
        }
        result = preflight(record, profile)
        self.assertEqual(result.status, REJECTED_INVALID)
        self.assertTrue(result.profile_checked)
        codes = {issue.code for issue in result.issues}
        self.assertIn("PREFLIGHT_FAMILY_UNCALIBRATED", codes)
        self.assertIn("PREFLIGHT_PROFILE_RECORD_MISMATCH", codes)

    def test_profile_checked_reflects_actual_validation(self):
        result = preflight("not-an-object", {"junk": 1})
        self.assertEqual(result.status, REJECTED_INVALID)
        self.assertFalse(result.profile_checked)

    def test_cli_refuses_identical_input_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "rows.jsonl"
            payload = json.dumps(ref_record()) + "\n"
            path.write_text(payload, encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "adapters/portable_preflight.py",
                    "--input",
                    str(path),
                    "--output",
                    str(path),
                ],
                cwd=REPO,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertIn("must differ", completed.stderr)
            self.assertEqual(path.read_text(encoding="utf-8"), payload)


class TransportDecodeTests(unittest.TestCase):
    """F-WP1-014: an undecodable line is a per-line result, never a crash."""

    def test_invalid_utf8_line_is_a_deterministic_per_line_result(self):
        ready = json.dumps(ref_record()).encode("utf-8")
        stream = io.BytesIO(ready + b"\n" + b'{"bad": "\xff"}' + b"\n" + ready + b"\n")
        sink = io.StringIO()
        self.assertEqual(process_jsonl(stream, sink), 2)
        rows = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual(
            [row["status"] for row in rows], [READY, REJECTED_INVALID, READY]
        )
        issue = rows[1]["issues"][0]
        self.assertEqual(issue["code"], "PREFLIGHT_JSONL_INVALID")
        self.assertIn("line 2: UnicodeDecodeError", issue["message"])

    def test_blank_only_byte_stream_still_reports_insufficient_evidence(self):
        sink = io.StringIO()
        self.assertEqual(process_jsonl(io.BytesIO(b" \n\t\n"), sink), 2)
        rows = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], INSUFFICIENT_EVIDENCE)
        self.assertEqual(rows[0]["issues"][0]["code"], "PREFLIGHT_STREAM_EMPTY")

    def test_cli_invalid_utf8_byte_keeps_valid_row_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp = pathlib.Path(tmp) / "rows.jsonl"
            out = pathlib.Path(tmp) / "out.jsonl"
            ready = json.dumps(ref_record()).encode("utf-8")
            inp.write_bytes(ready + b"\n" + b"\xff\xfe{" + b"\n" + ready + b"\n")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "adapters/portable_preflight.py",
                    "--input",
                    str(inp),
                    "--output",
                    str(out),
                ],
                cwd=REPO,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertEqual(completed.stderr, "")
            rows = [
                json.loads(line)
                for line in out.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                [row["status"] for row in rows], [READY, REJECTED_INVALID, READY]
            )
            codes = {issue["code"] for issue in rows[1]["issues"]}
            self.assertIn("PREFLIGHT_JSONL_INVALID", codes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
