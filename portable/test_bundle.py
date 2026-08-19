"""Adversarial tests for portable manifest and archive verification."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

# Isolated mode (-I), used by the portable gate, drops the script directory
# from sys.path, so add it back before importing the sibling verifier.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_bundle
import build_bundle
import gate


def _write_manifest(
    root: pathlib.Path,
    rows: list[dict[str, object]],
    inventory_rows: list[dict[str, object]] | None = None,
) -> pathlib.Path:
    portable = root / "portable"
    portable.mkdir(parents=True, exist_ok=True)
    if inventory_rows is None:
        inventory_rows = [
            {"path": row["path"], "role": row["role"]}
            for row in rows
        ]
    inventory_raw = verify_bundle._canonical(
        {
            "files": inventory_rows,
            "format_version": "RR-PORTABLE-INVENTORY-1",
        }
    )
    (portable / "inventory.json").write_bytes(inventory_raw)
    manifest: dict[str, object] = {
        "files": rows,
        "format_version": "RR-PORTABLE-BUNDLE-MANIFEST-1",
        "inventory_sha256": hashlib.sha256(inventory_raw).hexdigest().upper(),
        "manifest_sha256": verify_bundle.ZERO64,
        "path_contract": "REPOSITORY_RELATIVE_POSIX_NFC_NONSYMLINK",
        "runtime_contract": {
            "implementation": "CPython",
            "python_versions": ["3.12", "3.13", "3.14"],
        },
    }
    manifest["manifest_sha256"] = hashlib.sha256(verify_bundle._canonical(manifest)).hexdigest().upper()
    path = portable / "MANIFEST.json"
    path.write_bytes(verify_bundle._canonical(manifest))
    return path


class PortableBundleTests(unittest.TestCase):
    def test_checked_in_bundle_verifies(self) -> None:
        count, failures = verify_bundle.verify()
        self.assertGreater(count, 0)
        self.assertEqual(failures, [])

    def test_payload_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rr-bundle-test-") as temp:
            root = pathlib.Path(temp)
            payload = root / "payload.txt"
            payload.write_bytes(b"one")
            manifest = _write_manifest(
                root,
                [{
                    "byte_length": 3,
                    "path": "payload.txt",
                    "role": "runtime",
                    "sha256": hashlib.sha256(b"one").hexdigest().upper(),
                }],
                [{"path": "payload.txt", "role": "runtime"}],
            )
            self.assertEqual(verify_bundle.verify(root, manifest)[1], [])
            payload.write_bytes(b"two")
            self.assertIn("payload.txt:sha256", verify_bundle.verify(root, manifest)[1])

    def test_parent_traversal_is_rejected_before_read(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rr-bundle-test-") as temp:
            root = pathlib.Path(temp)
            (root / "payload.txt").write_bytes(b"one")
            manifest = _write_manifest(
                root,
                [{
                    "byte_length": 3,
                    "path": "../payload.txt",
                    "role": "runtime",
                    "sha256": hashlib.sha256(b"one").hexdigest().upper(),
                }],
                [{"path": "payload.txt", "role": "runtime"}],
            )
            failures = verify_bundle.verify(root, manifest)[1]
            self.assertTrue(any("unsafe manifest path" in failure for failure in failures), failures)

    def test_duplicate_json_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rr-bundle-test-") as temp:
            root = pathlib.Path(temp)
            portable = root / "portable"
            portable.mkdir(parents=True)
            (portable / "inventory.json").write_text("{}", encoding="utf-8")
            manifest = portable / "MANIFEST.json"
            manifest.write_text('{"format_version":"x","format_version":"y"}', encoding="utf-8")
            failures = verify_bundle.verify(root, manifest)[1]
            # ADOPTION A4: the shared law owns this dimension now, so the
            # message is the law's rather than a local hook's.
            self.assertTrue(any("duplicate object key" in failure for failure in failures), failures)

    def test_shared_ingest_law_is_the_one_the_frozen_core_bounds(self) -> None:
        # A4: the bundle executes the shared law, never a copy of its numbers.
        self.assertIs(verify_bundle.strict_ingest, gate.strict_ingest)
        core = verify_bundle.strict_ingest.CORE_PATH
        self.assertTrue(core.is_file(), core)
        self.assertEqual(
            core.relative_to(verify_bundle.ROOT).as_posix(),
            "baseline-run/implementation-output-0.3/b1_capabilities.py",
        )
        self.assertEqual(
            verify_bundle.MAX_JSON_DEPTH, verify_bundle.strict_ingest.MAX_NESTING
        )
        declared = {
            row["path"]
            for row in verify_bundle._decode_json(
                (verify_bundle.ROOT / "portable" / "inventory.json").read_bytes(),
                "inventory",
            )["files"]
        }
        # Self-containment: the law AND the frozen core it reads its bounds
        # from are both declared bundle files, so an unpacked bundle resolves
        # the law without a checkout beside it.
        self.assertIn("portability/strict_ingest.py", declared)
        self.assertIn(
            "baseline-run/implementation-output-0.3/b1_capabilities.py", declared
        )

    def test_law_rejections_reach_the_bundle_verifier(self) -> None:
        # Negative arm: every defect the law adds is refused by verify_bundle.
        # This verifier accepted the non-finite, surrogate and over-ceiling
        # cases before A4 phase 2 -- its local hook saw duplicate keys only.
        # Each case must fail, and the control case must still reach the
        # manifest checks, or the law is not in the decision path.
        members = verify_bundle.strict_ingest.MAX_MEMBERS_OR_ITEMS + 1
        cases = [
            (b'{"format_version":NaN}', "non-finite"),
            (b'{"format_version":"\\ud800"}', "lone surrogate"),
            (b'{"format_version":"x","format_version":"y"}', "duplicate object key"),
            # Not a law addition: this file's own strict decode already
            # rejected invalid UTF-8 and still runs first.  Present so the
            # adoption cannot silently weaken it.
            (b'{"format_version":"\xff"}', "UnicodeDecodeError"),
            (
                ("[" + ",".join("0" for _ in range(members)) + "]").encode("ascii"),
                "items",
            ),
        ]
        with tempfile.TemporaryDirectory(prefix="rr-bundle-test-") as temp:
            root = pathlib.Path(temp)
            portable = root / "portable"
            portable.mkdir(parents=True)
            (portable / "inventory.json").write_text("{}", encoding="utf-8")
            manifest = portable / "MANIFEST.json"
            for raw, expected in cases:
                with self.subTest(expected=expected):
                    manifest.write_bytes(raw)
                    count, failures = verify_bundle.verify(root, manifest)
                    self.assertEqual(count, 0)
                    self.assertTrue(
                        any(expected in failure for failure in failures),
                        (expected, failures),
                    )
            # Control: well-formed bytes still get past ingest and fail on the
            # manifest's own terms, so the cases above are not passing merely
            # because everything fails.
            manifest.write_bytes(b'{"format_version":"x"}\n')
            failures = verify_bundle.verify(root, manifest)[1]
            self.assertTrue(
                any("top-level members are not closed" in failure for failure in failures),
                failures,
            )

    def test_cli_refuses_a_bootstrap_law_the_manifest_does_not_declare(self) -> None:
        # Negative arm for the one ordering exception A4 phase 2 introduced.
        # cli.py must execute the shared ingest law before it can read the
        # manifest index, so the law is the single pre-index bootstrap; it is
        # re-checked against its declared row the moment the index exists.
        # Tampering with the law must stop the process at import, and the
        # control below must get PAST that check, so the tamper case cannot be
        # passing because the stripped tree fails for some other reason.
        law = "portability/strict_ingest.py"
        core = "baseline-run/implementation-output-0.3/b1_capabilities.py"
        carried = ("portable/cli.py", "portable/MANIFEST.json", "portable/inventory.json", law, core)
        with tempfile.TemporaryDirectory(prefix="rr-bundle-test-") as temp:
            root = pathlib.Path(temp)
            for relative in carried:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((verify_bundle.ROOT / relative).read_bytes())
            control = subprocess.run(
                [sys.executable, "-I", "-B", str(root / "portable" / "cli.py"), "verify"],
                cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                check=False, timeout=120,
            )
            self.assertNotEqual(control.returncode, 0)
            self.assertNotIn(b"bootstrap module failed byte authentication", control.stderr)
            self.assertIn(b"runtime module is unavailable", control.stderr)
            (root / law).write_bytes((verify_bundle.ROOT / law).read_bytes() + b"\n# tamper\n")
            tampered = subprocess.run(
                [sys.executable, "-I", "-B", str(root / "portable" / "cli.py"), "verify"],
                cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                check=False, timeout=120,
            )
            self.assertNotEqual(tampered.returncode, 0)
            self.assertIn(b"bootstrap module failed byte authentication", tampered.stderr)
            self.assertIn(law.encode("ascii"), tampered.stderr)

    def test_manifest_self_seal_is_required(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rr-bundle-test-") as temp:
            root = pathlib.Path(temp)
            payload = root / "payload.txt"
            payload.write_bytes(b"one")
            manifest = _write_manifest(
                root,
                [{
                    "byte_length": 3,
                    "path": "payload.txt",
                    "role": "runtime",
                    "sha256": hashlib.sha256(b"one").hexdigest().upper(),
                }],
            )
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["runtime_contract"]["python_versions"].append("3.15")
            manifest.write_bytes(verify_bundle._canonical(value))
            failures = verify_bundle.verify(root, manifest)[1]
            self.assertTrue(any("runtime contract" in failure or "self-seal" in failure for failure in failures), failures)

    def test_noncanonical_manifest_bytes_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rr-bundle-test-") as temp:
            root = pathlib.Path(temp)
            payload = root / "payload.txt"
            payload.write_bytes(b"one")
            manifest = _write_manifest(
                root,
                [{
                    "byte_length": 3,
                    "path": "payload.txt",
                    "role": "runtime",
                    "sha256": hashlib.sha256(b"one").hexdigest().upper(),
                }],
            )
            manifest.write_bytes(b" " + manifest.read_bytes())
            failures = verify_bundle.verify(root, manifest)[1]
            self.assertTrue(any("not canonical" in failure for failure in failures), failures)

    def test_deep_manifest_is_a_bounded_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rr-bundle-test-") as temp:
            root = pathlib.Path(temp)
            portable = root / "portable"
            portable.mkdir(parents=True)
            (portable / "inventory.json").write_text("{}", encoding="utf-8")
            manifest = portable / "MANIFEST.json"
            manifest.write_bytes(b"[" * (verify_bundle.MAX_JSON_DEPTH + 1) + b"0" + b"]" * (verify_bundle.MAX_JSON_DEPTH + 1))
            count, failures = verify_bundle.verify(root, manifest)
            self.assertEqual(count, 0)
            self.assertTrue(any("exceeds depth" in failure for failure in failures), failures)

    def test_inventory_and_manifest_declarations_must_match(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rr-bundle-test-") as temp:
            root = pathlib.Path(temp)
            (root / "payload.txt").write_bytes(b"one")
            manifest = _write_manifest(
                root,
                [{
                    "byte_length": 3,
                    "path": "payload.txt",
                    "role": "runtime",
                    "sha256": hashlib.sha256(b"one").hexdigest().upper(),
                }],
                [{"path": "other.txt", "role": "runtime"}],
            )
            failures = verify_bundle.verify(root, manifest)[1]
            self.assertTrue(any("do not match inventory" in failure for failure in failures), failures)

    def test_cross_platform_alias_is_rejected_before_lookup(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rr-bundle-test-") as temp:
            root = pathlib.Path(temp)
            manifest = _write_manifest(
                root,
                [
                    {
                        "byte_length": 0,
                        "path": "payload",
                        "role": "runtime",
                        "sha256": hashlib.sha256(b"").hexdigest().upper(),
                    },
                    {
                        "byte_length": 0,
                        "path": "PAYLOAD",
                        "role": "runtime",
                        "sha256": hashlib.sha256(b"").hexdigest().upper(),
                    },
                ],
            )
            failures = verify_bundle.verify(root, manifest)[1]
            self.assertTrue(any("aliased" in failure for failure in failures), failures)

    def test_distinct_names_cannot_resolve_to_one_file_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rr-bundle-test-") as temp:
            root = pathlib.Path(temp)
            first = root / "first.txt"
            second = root / "second.txt"
            first.write_bytes(b"one")
            try:
                os.link(first, second)
            except OSError as error:
                self.skipTest(f"hard links unavailable: {error}")
            rows = [
                {
                    "byte_length": 3,
                    "path": name,
                    "role": "runtime",
                    "sha256": hashlib.sha256(b"one").hexdigest().upper(),
                }
                for name in ("first.txt", "second.txt")
            ]
            manifest = _write_manifest(root, rows)
            failures = verify_bundle.verify(root, manifest)[1]
            self.assertTrue(any("one file identity" in failure for failure in failures), failures)

    def test_oversized_substitution_is_rejected_from_stat(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rr-bundle-test-") as temp:
            root = pathlib.Path(temp)
            payload = root / "payload.txt"
            with payload.open("wb") as stream:
                stream.truncate(verify_bundle.MAX_FILE_BYTES + 1)
            manifest = _write_manifest(
                root,
                [{
                    "byte_length": 3,
                    "path": "payload.txt",
                    "role": "runtime",
                    "sha256": hashlib.sha256(b"one").hexdigest().upper(),
                }],
            )
            failures = verify_bundle.verify(root, manifest)[1]
            self.assertTrue(any("bounded regular file" in failure for failure in failures), failures)

    def test_archive_builder_consumes_only_the_verified_snapshot(self) -> None:
        snapshot = verify_bundle.BundleSnapshot(
            manifest={},
            manifest_raw=b"manifest-snapshot\n",
            inventory_raw=b"inventory-snapshot\n",
            files=(("payload.txt", b"payload-snapshot"),),
        )
        with tempfile.TemporaryDirectory(prefix="rr-bundle-test-") as temp:
            output = pathlib.Path(temp) / "bundle.zip"
            with mock.patch.object(
                build_bundle._verifier,
                "verify_snapshot",
                return_value=(1, snapshot, []),
            ), mock.patch.object(pathlib.Path, "read_bytes", side_effect=AssertionError("path reopened")):
                build_bundle.build(output)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read("payload.txt"), b"payload-snapshot")
                self.assertEqual(archive.read("portable/MANIFEST.json"), b"manifest-snapshot\n")
                self.assertEqual(archive.read("portable/inventory.json"), b"inventory-snapshot\n")

    def test_gate_rejects_contradictory_or_trailing_output(self) -> None:
        success = b"portable manifest: files=61 drift=0\n"
        self.assertTrue(gate._summary("portable-manifest", success, b""))
        self.assertFalse(
            gate._summary(
                "portable-manifest",
                b"portable manifest: drift=1\n" + success,
                b"",
            )
        )
        raw_row = {
            "candidate_cli_flags": [],
            "candidate_cli_pycache_policy": "bounded",
            "case_names": ["case-1"],
            "divergence_count": 0,
            "executed_cases": 1,
            "family_counts": {"family": 1},
            "first_divergence": None,
            "format_version": "RR2-BOUNDED-RAW-PREFLIGHT-0.2",
            "status": "PASS",
            "stream_sha256": "A" * 64,
            "surfaces_per_case": [],
        }
        raw = (json.dumps(raw_row, separators=(",", ":")) + "\n").encode()
        self.assertTrue(gate._summary("raw-boundary-preflight", raw, b""))
        self.assertFalse(gate._summary("raw-boundary-preflight", b'{"status":"FAIL"}\n' + raw, b""))
        duplicate = raw.replace(b'"status":"PASS"', b'"status":"FAIL","status":"PASS"')
        self.assertFalse(gate._summary("raw-boundary-preflight", duplicate, b""))
        contradictory = dict(raw_row, failure_count=1)
        contradictory_raw = (json.dumps(contradictory, separators=(",", ":")) + "\n").encode()
        self.assertFalse(gate._summary("raw-boundary-preflight", contradictory_raw, b""))
        independent = b'second-implementation counts={"semantic":124} failures=0\n'
        self.assertTrue(gate._summary("independent-runtime", independent, b""))
        self.assertFalse(
            gate._summary(
                "independent-runtime",
                b'second-implementation counts={"semantic":124,"semantic":0} failures=0\n',
                b"",
            )
        )
        unittest_stderr = (
            b"test_one (__main__.PortableBundleTests.test_one) ... ok\n\n"
            b"----------------------------------------------------------------------\n"
            b"Ran 1 test in 0.001s\n\nOK\n"
        )
        self.assertTrue(
            gate._summary(
                "portable-manifest-tests",
                b"portable bundle tests: tests=1 failures=0\n",
                unittest_stderr,
            )
        )
        self.assertFalse(
            gate._summary(
                "portable-manifest-tests",
                b"portable bundle tests: tests=1 failures=0\n",
                b"FAIL: contradictory\n" + unittest_stderr,
            )
        )
        self.assertFalse(
            gate._summary(
                "portable-manifest-tests",
                b"portable bundle tests: tests=1 failures=0\n",
                b"contradictory output\n" + unittest_stderr,
            )
        )
        returncode, stdout, stderr, timed_out, overflow = gate._run_bounded(
            (sys.executable, "-I", "-B", "-c", "import sys; sys.stdout.write('x' * 2048)"),
            verify_bundle.ROOT,
            dict(os.environ),
            5,
            max_output_bytes=1024,
        )
        self.assertIsInstance(returncode, int)
        self.assertEqual(len(stdout), 1025)
        self.assertEqual(stderr, b"")
        self.assertFalse(timed_out)
        self.assertTrue(overflow)

    def test_archive_builder_is_byte_deterministic(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", "portable/build_bundle.py", "--check-deterministic"],
            cwd=verify_bundle.ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=120,
        )
        self.assertEqual(completed.returncode, 0, (completed.stdout, completed.stderr))
        self.assertIn(b"deterministic=1", completed.stdout)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PortableBundleTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"portable bundle tests: tests={result.testsRun} failures={len(result.failures) + len(result.errors)}")
    raise SystemExit(0 if result.wasSuccessful() else 1)
