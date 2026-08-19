"""Prove the four receipt writers stop publishing the operator's home directory.

    python -B portability/test_receipt_redaction.py

ERRATA E15 discloses fifty-two tracked files that record the maintainer's home
directory. All fifty-two are frozen or recorded evidence, so disclosure is the
only treatment available to them. This suite covers the other half: the writers
that would keep producing new instances.

Two things are checked, and the second is the one that matters. The first is
that the shared redactor does what it says. The second is that each writer
routes its own write boundary through it -- the failure this repository names
twice is a control that exists and is not in the decision path, and a redactor
that four writers do not call is exactly that.

Every fake home in this file is assembled from fragments, never written
literally, so this file does not become an instance of what the E15 gate
searches for. The gate's own compiled pattern is imported rather than restated,
because a copied pattern can agree with a leak the real gate would catch.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
for _entry in (str(HERE), str(REPO / "perf"), str(REPO / "perf" / "sidecar"),
               str(REPO / "portability" / "concurrency"), str(REPO / "portability" / "matrix")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import pinned_tools  # noqa: E402
import receipt_paths  # noqa: E402
import test_home_path_disclosure as e15  # noqa: E402  (the gate's own pattern)

# Assembled, never written literally: an account-shaped fake home that the E15
# pattern matches, in a file the E15 gate must keep reporting as clean.
_DRIVE = "C:" + chr(92)
_USERS = "Users"
_ACCOUNT = "j" + "ames"
FAKE_HOME = _DRIVE + _USERS + chr(92) + _ACCOUNT


def _writers_under_a_fake_home(home: str):
    """Patch the redactor's notion of home for the duration of one write."""
    return mock.patch.object(receipt_paths, "home", lambda: home)


class TheRedactorItself(unittest.TestCase):
    def test_prefix_goes_and_structure_below_it_stays(self) -> None:
        value = FAKE_HOME + chr(92) + "AppData" + chr(92) + "python.exe"
        redacted = receipt_paths.redact(value, base=FAKE_HOME)
        self.assertEqual(
            redacted, receipt_paths.HOME_MARKER + chr(92) + "AppData" + chr(92) + "python.exe"
        )

    def test_both_separator_spellings_are_matched(self) -> None:
        forward = FAKE_HOME.replace(chr(92), "/") + "/Temp/run.json"
        self.assertNotIn(_ACCOUNT, receipt_paths.redact(forward, base=FAKE_HOME))

    def test_case_differences_are_matched(self) -> None:
        """The E15 pattern is case-insensitive, so a case-sensitive redactor
        would report a guarantee the gate then falsifies."""
        shouted = FAKE_HOME.upper() + chr(92) + "Temp"
        self.assertNotIn(_ACCOUNT.upper(), receipt_paths.redact(shouted, base=FAKE_HOME))

    def test_non_strings_pass_through_unchanged(self) -> None:
        for value in (1, 1.5, None, True):
            self.assertIs(receipt_paths.redact(value, base=FAKE_HOME), value)

    def test_tree_redacts_values_and_keys(self) -> None:
        tree = {
            "argv": [FAKE_HOME + chr(92) + "python.exe", "-B"],
            FAKE_HOME: {"nested": (FAKE_HOME + "/x",)},
            "count": 3,
        }
        redacted = receipt_paths.redact_tree(tree, base=FAKE_HOME)
        self.assertNotIn(_ACCOUNT, json.dumps(redacted, default=list))
        self.assertEqual(redacted["count"], 3)
        self.assertIn(receipt_paths.HOME_MARKER, redacted)

    def test_a_key_collision_is_an_error_not_a_lost_field(self) -> None:
        with self.assertRaises(ValueError):
            receipt_paths.redact_tree(
                {FAKE_HOME: 1, receipt_paths.HOME_MARKER: 2}, base=FAKE_HOME
            )


class OneImplementation(unittest.TestCase):
    """Recomputed from the tree, because a hand-kept list is not a control.

    ADOPTION A5 was reopened twice for the same shape: a guard that could not
    see its own subject. This enumerates tracked sources and fails if a second
    home-directory redactor appears anywhere.
    """

    def _tracked_python(self) -> list[str]:
        out = subprocess.run(
            [pinned_tools.git(), "-C", str(REPO), "ls-files", "-z", "*.py"],
            capture_output=True,
            check=True,
        ).stdout
        return [chunk.decode("utf-8") for chunk in out.split(b"\0") if chunk]

    def test_only_one_file_resolves_the_home_directory(self) -> None:
        # Scope: production sources only. A ``test_*.py`` file is excluded by
        # rule, with the reason stated rather than left implicit -- those files
        # name the probe in order to assert on it, and asserting on a name
        # redacts nothing. The narrowing is real: a future writer named
        # ``test_*.py`` would not be seen here.
        probe = "Path.home()"
        offenders = [
            relative
            for relative in self._tracked_python()
            if not pathlib.PurePosixPath(relative).name.startswith("test_")
            and probe in (REPO / relative).read_text(encoding="utf-8", errors="ignore")
            and relative != "portability/receipt_paths.py"
        ]
        self.assertEqual(
            offenders,
            [],
            "a second home-directory redactor exists; route it through "
            "portability/receipt_paths.py instead",
        )

    def test_every_receipt_writer_routes_through_the_shared_module(self) -> None:
        for relative in (
            "perf/profile.py",
            "perf/sidecar/_evidence.py",
            "portability/concurrency/ladder.py",
            "portability/matrix/receipt.py",
            "portability/run_local_expanded_gate.py",
        ):
            with self.subTest(writer=relative):
                source = (REPO / relative).read_text(encoding="utf-8")
                self.assertIn("import receipt_paths", source)
                self.assertIn("receipt_paths.redact", source)


class WritersProduceCleanReceipts(unittest.TestCase):
    """The behaviour, at each writer's real write boundary."""

    def _assert_clean(self, raw: bytes, label: str) -> None:
        text = raw.decode("utf-8", errors="ignore")
        self.assertIsNone(
            e15.HOME_PATH.search(text),
            f"{label} still records a maintainer home-directory path",
        )
        self.assertIn(receipt_paths.HOME_MARKER, text, f"{label} recorded no redaction")

    def test_wp5_receipt_writer(self) -> None:
        import _evidence

        receipt = {
            "schema": "receiver-reliance/test-only",
            "runtime": {"executable": FAKE_HOME + chr(92) + "python.exe"},
            "command": [FAKE_HOME + chr(92) + "python.exe", "-I", "-B"],
            "execution_input_manifest": {
                "current_process": {
                    "executed_argv": [FAKE_HOME + "/python.exe"],
                    "pycache_prefix": FAKE_HOME + chr(92) + "Temp" + chr(92) + "pycache",
                }
            },
        }
        with tempfile.TemporaryDirectory(prefix="rr-redaction-") as temporary:
            root = pathlib.Path(temporary)
            destination = root / "perf" / "receipts" / "robustness" / "probe.json"
            with mock.patch.object(_evidence, "REPO", root), _writers_under_a_fake_home(FAKE_HOME):
                _evidence.write_new_receipt(destination, receipt)
            self._assert_clean(destination.read_bytes(), "the WP5 receipt writer")

    def test_profile_writer(self) -> None:
        import profile as profiler

        with _writers_under_a_fake_home(FAKE_HOME):
            encoded = profiler.encode_profile(
                {"system": {"executable": FAKE_HOME + chr(92) + "python.exe"}}
            )
        self._assert_clean(encoded.encode("utf-8"), "the profiler")

    def test_concurrency_ladder_writer(self) -> None:
        import ladder

        with tempfile.TemporaryDirectory(prefix="rr-redaction-") as temporary:
            destination = pathlib.Path(temporary) / "ladder.json"
            with _writers_under_a_fake_home(FAKE_HOME):
                ladder._write_receipt(
                    destination,
                    {
                        "runtime": {"executable": FAKE_HOME + chr(92) + "python.exe"},
                        "stop": {"traceback": 'File "' + FAKE_HOME + '/repo/x.py", line 1'},
                    },
                )
            self._assert_clean(destination.read_bytes(), "the concurrency ladder")

    def test_matrix_receipt_writer(self) -> None:
        import receipt as matrix_receipt

        with tempfile.TemporaryDirectory(prefix="rr-redaction-") as temporary:
            destination = pathlib.Path(temporary) / "matrix.json"
            with _writers_under_a_fake_home(FAKE_HOME):
                matrix_receipt._write_json(
                    destination,
                    {
                        "environment": {"runtime": {"executable": FAKE_HOME + chr(92) + "python.exe"}},
                        "commands": [{"argv": [FAKE_HOME + chr(92) + "python.exe", "-B"]}],
                    },
                )
            self._assert_clean(destination.read_bytes(), "the matrix receipt writer")

    def test_expanded_gate_writer_kept_its_behaviour(self) -> None:
        import run_local_expanded_gate as gate

        with _writers_under_a_fake_home(FAKE_HOME):
            redacted = gate._redact(FAKE_HOME + chr(92) + "python.exe")
        self.assertEqual(redacted, gate.HOME_MARKER + chr(92) + "python.exe")

    def test_matrix_redaction_inherits_the_writer_depth_bound(self) -> None:
        """A second traversal would have broken the writer it was meant to serve.

        The matrix writer is deliberately non-recursive and rejects a document
        past its own nesting bound with a ValueError. Redacting a copied tree
        first hit a RecursionError before that bound applied, turning a bounded
        rejection into an unbounded failure -- caught by
        ``portability/matrix/test_receipt.py``. Redaction moved to the keys and
        string leaves of that traversal, so both properties hold together: the
        bound still fires, and a string below it is still redacted.
        """
        import receipt as matrix_receipt

        hostile: object = 0
        for _ in range(2994):
            hostile = [hostile]
        with self.assertRaisesRegex(ValueError, "finite writer domain"):
            matrix_receipt._canonical_json(hostile)

        nested: object = FAKE_HOME + chr(92) + "python.exe"
        for _ in range(matrix_receipt.MAX_JSON_NESTING_DEPTH - 1):
            nested = [nested]
        with _writers_under_a_fake_home(FAKE_HOME):
            encoded = matrix_receipt._canonical_json(nested)
        self.assertIsNone(e15.HOME_PATH.search(encoded))
        self.assertIn(receipt_paths.HOME_MARKER, encoded)

    def test_a_redacted_temporary_root_is_still_an_absolute_root(self) -> None:
        """The matrix validator must accept what the matrix writer now writes.

        On a host whose temporary directory is under the home directory the
        recorded root begins with the marker, which is neither drive-absolute
        nor separator-absolute. Admitting it is a real widening, so it is pinned
        here together with the case it must still reject.
        """
        import receipt as matrix_receipt

        self.assertTrue(
            matrix_receipt._is_absolute_or_redacted(
                receipt_paths.HOME_MARKER + chr(92) + "AppData" + chr(92) + "Temp"
            )
        )
        self.assertFalse(matrix_receipt._is_absolute_or_redacted("relative" + chr(92) + "temp"))


class TheGateStillSeesThisFile(unittest.TestCase):
    def test_this_file_is_not_itself_an_instance(self) -> None:
        """A suite about home-path leakage that leaks one is worse than none."""
        source = pathlib.Path(__file__).read_text(encoding="utf-8")
        self.assertIsNone(e15.HOME_PATH.search(source))

    def test_the_shared_module_is_not_itself_an_instance(self) -> None:
        source = (REPO / "portability" / "receipt_paths.py").read_text(encoding="utf-8")
        self.assertIsNone(e15.HOME_PATH.search(source))


class HomelessEnvironmentIsIdentity(unittest.TestCase):
    """The hosted-Windows failure shape: no USERPROFILE means no redaction,
    never an exception.  All six hosted Windows normative cells failed on
    Path.home() raising inside scrubbed matrix children before this arm
    existed; POSIX cells never saw it because expanduser falls back to the
    pwd database there."""

    def test_no_home_variables_means_identity_not_raise(self) -> None:
        saved = {
            name: os.environ.pop(name, None)
            for name in ("USERPROFILE", "HOMEDRIVE", "HOMEPATH", "HOME")
        }
        try:
            resolved = receipt_paths.home()
            probe = {"path": 'C:\\Users\\someone\\repo\\file.py', "n": 1}
            out = receipt_paths.redact_tree(probe)
            if resolved == "":
                self.assertEqual(out, probe)
            else:
                # A platform that still resolves a home (POSIX pwd fallback)
                # must simply not raise; identity is not required there.
                self.assertIsInstance(out, dict)
        finally:
            for name, value in saved.items():
                if value is not None:
                    os.environ[name] = value


if __name__ == "__main__":
    unittest.main(verbosity=2)
