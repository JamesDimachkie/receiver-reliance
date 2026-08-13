"""Black-box contract tests for the stable portable CLI."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "portable" / "cli.py"
SECOND_CLI = ROOT / "second-implementation" / "cli.py"


def run(mode: str, raw: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-I", "-B", str(CLI), mode],
        input=raw,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=120,
    )


class PortableCliTests(unittest.TestCase):
    def test_usage_is_stable_and_nonzero(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(CLI)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 64)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr,
            b"usage: python -B portable/cli.py {verify|doctor|preflight|decide|sidecar}\n",
        )

    def test_verify_and_doctor_bind_the_manifest(self) -> None:
        verified = run("verify")
        self.assertEqual(verified.returncode, 0, (verified.stdout, verified.stderr))
        doctor = run("doctor")
        self.assertEqual(doctor.returncode, 0, (doctor.stdout, doctor.stderr))
        row = json.loads(doctor.stdout)
        manifest = json.loads((ROOT / "portable" / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(row["status"], "READY")
        self.assertEqual(row["bundle_version"], "0.1.0-rc.1")
        self.assertEqual(row["manifest_sha256"], manifest["manifest_sha256"])
        self.assertGreater(row["bundle_files"], 0)

    def test_preflight_has_closed_jsonl_behavior(self) -> None:
        record = {
            "family": "REF",
            "native": {"claimed_sha256": "A" * 64, "referenced_record": "a"},
            "observations": {"observed_sha256": "A" * 64, "referenced_record_found": True},
            "record_id": "REC_PORTABLE_CLI",
        }
        result = run("preflight", (json.dumps(record, separators=(",", ":")) + "\n").encode())
        self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
        self.assertEqual(json.loads(result.stdout)["status"], "READY")

    def test_decide_is_byte_exact_with_candidate_cli(self) -> None:
        raw = b""
        portable = run("decide", raw)
        direct = subprocess.run(
            [sys.executable, "-I", "-B", str(SECOND_CLI), "execute"],
            input=raw,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=120,
        )
        self.assertEqual(
            (portable.returncode, portable.stdout, portable.stderr),
            (direct.returncode, direct.stdout, direct.stderr),
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PortableCliTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"portable CLI tests: tests={result.testsRun} failures={len(result.failures) + len(result.errors)}")
    raise SystemExit(0 if result.wasSuccessful() else 1)
