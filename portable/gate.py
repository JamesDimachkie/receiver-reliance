"""Offline, platform-neutral gate over the exact portable bundle bytes."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys


def _load_verify_bundle():
    # Path-bound import: the verifier is always the file beside this gate,
    # never an ambient same-name module, and the gate survives isolated-mode
    # spawning that strips the script directory from sys.path.
    here = pathlib.Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("portable_verify_bundle", here / "verify_bundle.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verify = _load_verify_bundle().verify


ROOT = pathlib.Path(__file__).resolve().parent.parent
COMMANDS = (
    ("portable-manifest", ("portable/build_manifest.py", "--check"), 60),
    ("portable-manifest-tests", ("portable/test_bundle.py",), 120),
    ("portable-cli-tests", ("portable/test_cli.py",), 300),
    ("portable-preflight", ("adapters/test_portable_preflight.py",), 300),
    ("independent-runtime", ("second-implementation/test_cross.py",), 1200),
    ("raw-boundary-preflight", ("second-implementation/bounded_preflight.py",), 1200),
    ("sidecar-transport", ("perf/sidecar/test_sidecar.py",), 600),
    ("sidecar-receipts", ("perf/sidecar/verify_receipts.py",), 300),
)


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def _summary(command_id: str, stdout: bytes, stderr: bytes) -> bool:
    text = stdout.decode("utf-8", "replace")
    error_text = stderr.decode("utf-8", "replace")
    if command_id == "portable-manifest":
        return "drift=0" in text
    if command_id == "portable-manifest-tests":
        return "portable bundle tests: tests=" in text and "failures=0" in text
    if command_id == "portable-cli-tests":
        return "portable CLI tests: tests=" in text and "failures=0" in text
    if command_id == "portable-preflight":
        return "Ran " in error_text and "OK" in error_text
    if command_id == "independent-runtime":
        return "second-implementation counts=" in text and "failures=0" in text
    if command_id == "raw-boundary-preflight":
        try:
            row = json.loads(text.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            return False
        return row.get("status") == "PASS" and row.get("divergence_count") == 0
    if command_id == "sidecar-transport":
        return "sidecar parity: checks=" in text and "failures=0" in text
    if command_id == "sidecar-receipts":
        return "wp5 receipt verification: checks=" in text and "failures=0" in text
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-only", action="store_true")
    args = parser.parse_args()
    _, manifest_failures = verify()
    if manifest_failures:
        for failure in manifest_failures:
            print(f"FAIL portable-manifest {failure}")
        print(f"portable gate: checks=1 failures={len(manifest_failures)}")
        return 1
    if args.manifest_only:
        print("portable gate: checks=1 failures=0")
        return 0
    failures = 0
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    for command_id, tail, timeout in COMMANDS:
        argv = (sys.executable, "-I", "-B", *tail)
        try:
            completed = subprocess.run(
                argv,
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
            if completed.returncode != 0 or not _summary(command_id, completed.stdout, completed.stderr):
                failures += 1
                print(
                    f"FAIL {command_id} exit={completed.returncode} "
                    f"stdout_sha256={_digest(completed.stdout)} "
                    f"stderr_sha256={_digest(completed.stderr)}"
                )
        except subprocess.TimeoutExpired as exc:
            failures += 1
            print(
                f"FAIL {command_id} timeout={timeout} "
                f"stdout_sha256={_digest(exc.stdout or b'')} "
                f"stderr_sha256={_digest(exc.stderr or b'')}"
            )
    print(f"portable gate: checks={len(COMMANDS) + 1} failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
