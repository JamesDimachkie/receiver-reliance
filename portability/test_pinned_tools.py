"""Pin the two properties that make pinned tool resolution adoptable.

    python -B portability/test_pinned_tools.py

The first property is why this change is safe to land at all: with no pinned
directory configured, the resolved argv is byte-identical to what every existing
receipt was produced under, so no pinned digest moves. The second is that when a
directory IS configured, resolution never silently falls back to `PATH` — a lane
that reported the guarantee while using an ambient tool would be worse than one
that never claimed it.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pinned_tools  # noqa: E402


class DefaultIsUnchanged(unittest.TestCase):
    """No configuration means byte-identical argv, which is what protects receipts."""

    def setUp(self) -> None:
        self._saved = os.environ.pop(pinned_tools.TOOL_DIR_ENV, None)

    def tearDown(self) -> None:
        if self._saved is not None:
            os.environ[pinned_tools.TOOL_DIR_ENV] = self._saved
        else:
            os.environ.pop(pinned_tools.TOOL_DIR_ENV, None)

    def test_git_is_the_bare_name(self) -> None:
        self.assertEqual(pinned_tools.git(), "git")

    def test_docker_is_the_bare_name(self) -> None:
        self.assertEqual(pinned_tools.docker(), "docker")

    def test_tool_dir_is_none(self) -> None:
        self.assertIsNone(pinned_tools.tool_dir())

    def test_provenance_says_ambient_and_keeps_the_caveat(self) -> None:
        record = pinned_tools.provenance()
        self.assertEqual(record["resolution"], "AMBIENT_PATH")
        self.assertIsNone(record["tool_dir"])
        self.assertIn("does not prove the host was sound", record["caveat"])


class PinnedResolution(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = os.environ.get(pinned_tools.TOOL_DIR_ENV)
        self._temp = tempfile.TemporaryDirectory()
        self.directory = pathlib.Path(self._temp.name)
        os.environ[pinned_tools.TOOL_DIR_ENV] = str(self.directory)

    def tearDown(self) -> None:
        if self._saved is not None:
            os.environ[pinned_tools.TOOL_DIR_ENV] = self._saved
        else:
            os.environ.pop(pinned_tools.TOOL_DIR_ENV, None)
        self._temp.cleanup()

    def _plant(self, name: str) -> pathlib.Path:
        suffix = ".exe" if sys.platform == "win32" else ""
        path = self.directory / f"{name}{suffix}"
        path.write_bytes(b"")
        return path

    def test_resolves_to_an_absolute_path_inside_the_pinned_directory(self) -> None:
        planted = self._plant("git")
        resolved = pinned_tools.git()
        self.assertTrue(pathlib.Path(resolved).is_absolute())
        self.assertEqual(pathlib.Path(resolved), planted.resolve())

    def test_absent_tool_is_an_error_and_never_falls_back_to_path(self) -> None:
        """The property that makes the guarantee real rather than advertised."""
        with self.assertRaises(RuntimeError) as caught:
            pinned_tools.git()
        message = str(caught.exception)
        self.assertIn("not found in the pinned tool directory", message)
        self.assertIn("does not fall back to PATH", message)

    def test_nonexistent_directory_is_an_error(self) -> None:
        os.environ[pinned_tools.TOOL_DIR_ENV] = str(self.directory / "absent")
        with self.assertRaises(RuntimeError) as caught:
            pinned_tools.git()
        self.assertIn("not a directory", str(caught.exception))

    def test_provenance_reports_the_pinned_directory(self) -> None:
        record = pinned_tools.provenance()
        self.assertEqual(record["resolution"], "PINNED_DIRECTORY")
        self.assertEqual(record["tool_dir"], str(self.directory))


class NoReceiptSurfaceIsTouched(unittest.TestCase):
    def test_module_writes_nothing_and_adds_no_receipt_field(self) -> None:
        """provenance() exists for prose, not for a byte-pinned receipt."""
        source = (HERE / "pinned_tools.py").read_text(encoding="utf-8")
        for forbidden in ("open(", "write_text", "write_bytes", "json.dump"):
            self.assertNotIn(forbidden, source, f"{forbidden} would give this module a write surface")


class AdoptionIsReal(unittest.TestCase):
    """A control that no consumer calls is not a control.

    csf_d5b39499, csf_16f2cc06 and csf_211167ec all name bare ``git``/``docker``
    resolution in evidence harnesses.  pinned_tools was landed to close them and
    then called from nowhere, so all three stayed live at the call sites while the
    module and its own tests were green.  These cases fail if any harness goes
    back to a bare name.
    """

    ADOPTED = (
        "portability/verify_hygiene.py",
        "portability/run_local_expanded_gate.py",
        "portability/concurrency/ladder.py",
        "portability/matrix/receipt.py",
        "portability/sandbox/run_sandbox.py",
    )

    def test_every_evidence_harness_imports_the_module(self) -> None:
        for relative in self.ADOPTED:
            with self.subTest(module=relative):
                source = (REPO / relative).read_text(encoding="utf-8")
                self.assertIn("import pinned_tools", source)

    def test_no_harness_invokes_a_bare_tool_name(self) -> None:
        bare = re.compile(r"\[\s*\"(git|docker)\"\s*,")
        for relative in self.ADOPTED:
            with self.subTest(module=relative):
                source = (REPO / relative).read_text(encoding="utf-8")
                self.assertEqual(
                    bare.findall(source),
                    [],
                    f"{relative} still builds an argv from a bare tool name",
                )

    def test_unset_default_keeps_argv_byte_identical(self) -> None:
        """The property that made adoption possible without moving a receipt."""
        saved = os.environ.pop(pinned_tools.TOOL_DIR_ENV, None)
        try:
            self.assertEqual(pinned_tools.git(), "git")
            self.assertEqual(pinned_tools.docker(), "docker")
        finally:
            if saved is not None:
                os.environ[pinned_tools.TOOL_DIR_ENV] = saved


if __name__ == "__main__":
    unittest.main(verbosity=2)
