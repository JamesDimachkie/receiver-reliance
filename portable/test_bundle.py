"""Adversarial tests for portable manifest and archive verification."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

# Isolated mode (-I), used by the portable gate, drops the script directory
# from sys.path, so add it back before importing the sibling verifier.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_bundle


def _write_manifest(root: pathlib.Path, rows: list[dict[str, object]]) -> pathlib.Path:
    portable = root / "portable"
    portable.mkdir(parents=True, exist_ok=True)
    inventory_raw = b'{"files":[{"path":"payload.txt","role":"runtime"}],"format_version":"RR-PORTABLE-INVENTORY-1"}\n'
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
            self.assertTrue(any("duplicate JSON member" in failure for failure in failures), failures)

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
