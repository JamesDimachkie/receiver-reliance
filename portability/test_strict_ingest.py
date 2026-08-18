"""Pin the shared bounded-ingest law and its adoption.

    python -B portability/test_strict_ingest.py

Three things are worth pinning here and each has already failed once in this
repository's history or would have:

  * the law's bounds must come FROM the frozen core, not be restated. A module
    that copies MAX_NESTING drifts from the authority it claims to share, which
    is the defect cluster C2 records.
  * the safety half must reject nothing the repository already publishes. That is
    what makes adoption possible at all, and it is a property of the corpus, so it
    can regress when a receipt is added.
  * no ingest site may quietly reappear as a bare json.loads.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import strict_ingest  # noqa: E402


def load_frozen_core():
    path = REPO / "baseline-run" / "implementation-output-0.3" / "b1_capabilities.py"
    spec = importlib.util.spec_from_file_location("frozen_core_for_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BoundsComeFromTheFrozenCore(unittest.TestCase):
    def test_bounds_are_not_restated(self) -> None:
        core = load_frozen_core()
        self.assertEqual(strict_ingest.MAX_NESTING, core.MAX_NESTING)
        self.assertEqual(strict_ingest.MAX_MEMBERS_OR_ITEMS, core.MAX_MEMBERS_OR_ITEMS)

    def test_module_does_not_hardcode_the_numbers(self) -> None:
        """A literal would let this module drift from the core it cites."""
        source = (HERE / "strict_ingest.py").read_text(encoding="utf-8")
        body = source.split('"""', 2)[-1]  # skip the module docstring
        self.assertNotIn("128", body)
        self.assertNotIn("100000", body)


class SafetyHalf(unittest.TestCase):
    def refuses(self, raw: bytes) -> str:
        with self.assertRaises(strict_ingest.IngestError) as caught:
            strict_ingest.load_safe(raw)
        return str(caught.exception)

    def test_duplicate_object_key(self) -> None:
        self.assertIn("duplicate object key", self.refuses(b'{"a":1,"a":2}\n'))

    def test_non_finite_constants(self) -> None:
        for raw in (b'{"a": NaN}\n', b'{"a": Infinity}\n', b'{"a": -Infinity}\n'):
            self.assertIn("non-finite", self.refuses(raw))

    def test_lone_surrogate(self) -> None:
        self.assertIn("lone surrogate", self.refuses(b'{"a": "\\ud800"}\n'))

    def test_nesting_past_the_core_bound(self) -> None:
        depth = strict_ingest.MAX_NESTING + 40
        raw = b"{" + b'"n":{' * (depth - 1) + b"}" * (depth - 1) + b"}\n"
        self.assertIn("nesting deeper than", self.refuses(raw))

    def test_members_past_the_core_bound(self) -> None:
        count = strict_ingest.MAX_MEMBERS_OR_ITEMS + 1
        raw = ("[" + ",".join("0" for _ in range(count)) + "]\n").encode("ascii")
        self.assertIn("items", self.refuses(raw))

    def test_invalid_utf8(self) -> None:
        self.assertIn("not valid UTF-8", self.refuses(b'{"a": "\xff"}\n'))

    def test_syntax_failures_are_ingest_errors_not_json_errors(self) -> None:
        """One error type, so a caller can fail closed on every malformation."""
        for raw in (b"", b'{"a":1} junk\n', b"{\n", b"[1,]\n"):
            self.refuses(raw)

    def test_valid_input_is_accepted_unchanged(self) -> None:
        self.assertEqual(strict_ingest.load_safe(b'{"a":[1,2],"b":"x"}\n'), {"a": [1, 2], "b": "x"})

    def test_crlf_passes_safety_because_it_is_a_framing_property(self) -> None:
        self.assertEqual(strict_ingest.load_safe(b'{"a":\r\n1}\r\n'), {"a": 1})

    def test_no_other_exception_type_escapes(self) -> None:
        cases = [
            b"", b"{", b'{"a"}', b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":"\\ud800"}',
            b"\xef\xbb\xbf{}", b'{"a": 1} x', b"[1,2,", b"null", b"3",
            b"{" + b'"n":{' * 400 + b"}" * 400 + b"}",
        ]
        for raw in cases:
            with self.subTest(raw=raw[:24]):
                try:
                    strict_ingest.load_safe(raw)
                except strict_ingest.IngestError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    self.fail(f"{type(exc).__name__} escaped the shared law: {exc}")


class FramingHalf(unittest.TestCase):
    def test_clean_bytes_have_no_problems(self) -> None:
        self.assertEqual(strict_ingest.framing_problems(b'{"a":1}\n'), [])

    def test_each_problem_is_named(self) -> None:
        self.assertIn("leading BOM", strict_ingest.framing_problems(b'\xef\xbb\xbf{"a":1}\n'))
        self.assertIn("carriage return", strict_ingest.framing_problems(b'{"a":1}\r\n'))
        self.assertIn("no trailing LF", strict_ingest.framing_problems(b'{"a":1}'))
        self.assertIn("more than one trailing LF", strict_ingest.framing_problems(b'{"a":1}\n\n'))
        self.assertIn("not NFC", strict_ingest.framing_problems('{"e\u0301":1}\n'.encode("utf-8")))

    def test_load_canonical_refuses_what_load_safe_admits(self) -> None:
        """The two halves must be genuinely separate, not the same check twice."""
        crlf = b'{"a":\r\n1}\r\n'
        self.assertEqual(strict_ingest.load_safe(crlf), {"a": 1})
        with self.assertRaises(strict_ingest.IngestError):
            strict_ingest.load_canonical(crlf)


class PublishedCorpusStillPasses(unittest.TestCase):
    """Adoption is only possible because the safety half rejects nothing shipped."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.receipts = sorted(
            list((REPO / "portability" / "receipts").rglob("*.json"))
            + list((REPO / "perf" / "receipts").rglob("*.json"))
            + list((REPO / "second-implementation" / "receipts").rglob("*.json"))
        )

    def test_every_published_receipt_passes_the_safety_half(self) -> None:
        self.assertGreaterEqual(len(self.receipts), 60)
        for path in self.receipts:
            with self.subTest(receipt=path.relative_to(REPO).as_posix()):
                strict_ingest.load_safe(path.read_bytes(), label=path.name)

    def test_some_published_receipts_would_fail_canonical_framing(self) -> None:
        """If this ever becomes zero, the halves can be merged. Until then they cannot."""
        carriage = [
            path.relative_to(REPO).as_posix()
            for path in self.receipts
            if b"\r" in path.read_bytes()
        ]
        self.assertTrue(
            carriage,
            "no published receipt carries CR any more; the safety/framing split may be collapsible",
        )


class AdoptionIsComplete(unittest.TestCase):
    def test_verify_receipts_has_no_unguarded_json_load(self) -> None:
        source = (HERE / "verify_receipts.py").read_text(encoding="utf-8")
        self.assertNotIn("json.loads(", source)
        self.assertIn("strict_ingest.load_safe(", source)

    def test_verify_receipts_reports_its_pinned_check_count(self) -> None:
        """The ingest law rejects nothing this repository publishes.

        The count pinned here was 193 when the strict-ingest law was adopted,
        which was the point of the test: adoption itself moved no number.  The
        F-CONC-004 source-pin gate and the era-scoped hosted row replay later
        added 35 checks deliberately, so the pin migrated with them.  What the
        test still enforces is that every published receipt passes the law with
        zero failures.
        """
        import subprocess

        result = subprocess.run(
            [sys.executable, "-B", str(HERE / "verify_receipts.py")],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("checks=228 failures=0", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
