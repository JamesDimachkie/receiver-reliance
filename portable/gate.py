"""Offline, platform-neutral gate over the exact portable bundle bytes."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import pathlib
import re
import subprocess
import sys
import threading


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


_verify_bundle = _load_verify_bundle()
verify = _verify_bundle.verify
# ADOPTION A4: one law, resolved once.  The verifier already binds
# portability/strict_ingest.py by path and caches it under a single module
# name, so the gate reuses that handle rather than resolving the law a second
# way -- there is no second copy to drift.
strict_ingest = _verify_bundle.strict_ingest


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


def _text(raw: bytes) -> str | None:
    if len(raw) > 4 * 1024 * 1024 or b"\x00" in raw:
        return None
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None
    text = text.replace("\r\n", "\n")
    return None if "\r" in text else text


def _one_line(raw: bytes, pattern: str) -> re.Match[str] | None:
    text = _text(raw)
    if text is None or not text.endswith("\n") or text.count("\n") != 1:
        return None
    return re.fullmatch(pattern, text[:-1])


def _unittest_success(raw: bytes, expected_tests: int) -> bool:
    text = _text(raw)
    if text is None:
        return False
    marker = "\n\n----------------------------------------------------------------------\n"
    if text.count(marker) != 1:
        return False
    progress, trailer = text.split(marker)
    progress_lines = progress.splitlines()
    if len(progress_lines) != expected_tests or not all(
        re.fullmatch(
            r"test_[A-Za-z0-9_]+ \(__main__\.[A-Za-z0-9_.]+\) \.\.\. ok",
            line,
        )
        for line in progress_lines
    ):
        return False
    match = re.fullmatch(
        r"Ran ([0-9]+) tests? in [0-9]+(?:\.[0-9]+)?s\n\nOK\n",
        trailer,
    )
    return match is not None and int(match.group(1)) == expected_tests


def _run_bounded(
    argv: tuple[str, ...],
    cwd: pathlib.Path,
    env: dict[str, str],
    timeout: int,
    max_output_bytes: int = 4 * 1024 * 1024,
) -> tuple[int, bytes, bytes, bool, bool]:
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    overflow = threading.Event()

    def drain(name: str, stream) -> None:
        try:
            while chunk := stream.read(64 * 1024):
                buffer = buffers[name]
                remaining = max_output_bytes + 1 - len(buffer)
                if remaining > 0:
                    buffer.extend(chunk[:remaining])
                if len(buffer) > max_output_bytes:
                    overflow.set()
                    try:
                        process.kill()
                    except OSError:
                        pass
                    return
        except OSError:
            overflow.set()
            try:
                process.kill()
            except OSError:
                pass
        finally:
            stream.close()

    assert process.stdout is not None and process.stderr is not None
    threads = [
        threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True),
    ]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait()
    for thread in threads:
        thread.join()
    return (
        process.returncode,
        bytes(buffers["stdout"]),
        bytes(buffers["stderr"]),
        timed_out,
        overflow.is_set(),
    )


def _summary(command_id: str, stdout: bytes, stderr: bytes) -> bool:
    if command_id == "portable-manifest":
        return stderr == b"" and _one_line(stdout, r"portable manifest: files=[1-9][0-9]* drift=0") is not None
    if command_id == "portable-manifest-tests":
        match = _one_line(stdout, r"portable bundle tests: tests=([1-9][0-9]*) failures=0")
        return match is not None and _unittest_success(stderr, int(match.group(1)))
    if command_id == "portable-cli-tests":
        match = _one_line(stdout, r"portable CLI tests: tests=([1-9][0-9]*) failures=0")
        return match is not None and _unittest_success(stderr, int(match.group(1)))
    if command_id == "portable-preflight":
        text = _text(stderr)
        match = re.search(r"\n-+\nRan ([1-9][0-9]*) tests? in [0-9.]+s\n\nOK\n\Z", text or "")
        return stdout == b"" and match is not None and _unittest_success(stderr, int(match.group(1)))
    if command_id == "independent-runtime":
        text = _text(stdout)
        prefix = "second-implementation counts="
        suffix = " failures=0\n"
        if stderr != b"" or text is None or not text.startswith(prefix) or not text.endswith(suffix):
            return False
        try:
            # ADOPTION A4: subprocess stdout is bytes this gate did not
            # produce, so it is admitted under the shared law.  The text was
            # already strict-UTF-8 decoded by _text, so the re-encode is
            # lossless; IngestError subclasses ValueError, so this site still
            # fails closed to False exactly as before.
            counts = strict_ingest.load_safe(
                text[len(prefix):-len(suffix)].encode("utf-8"),
                label="independent-runtime counts",
            )
        except ValueError:
            return False
        return (
            isinstance(counts, dict)
            and bool(counts)
            and all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in counts.values())
        )
    if command_id == "raw-boundary-preflight":
        try:
            text = _text(stdout)
            if stderr != b"" or text is None or not text.endswith("\n") or text.count("\n") != 1:
                return False
            row = strict_ingest.load_safe(
                text.encode("utf-8"), label="raw-boundary-preflight row"
            )
        except ValueError:
            return False
        required = {
            "candidate_cli_flags",
            "candidate_cli_pycache_policy",
            "case_names",
            "divergence_count",
            "executed_cases",
            "family_counts",
            "first_divergence",
            "format_version",
            "status",
            "stream_sha256",
            "surfaces_per_case",
        }
        return (
            isinstance(row, dict)
            and set(row) == required
            and row.get("format_version") == "RR2-BOUNDED-RAW-PREFLIGHT-0.2"
            and row.get("status") == "PASS"
            and row.get("divergence_count") == 0
            and row.get("first_divergence") is None
            and isinstance(row.get("executed_cases"), int)
            and not isinstance(row["executed_cases"], bool)
            and row["executed_cases"] > 0
            and isinstance(row.get("case_names"), list)
            and all(isinstance(name, str) for name in row["case_names"])
            and len(row["case_names"]) == row["executed_cases"]
            and isinstance(row.get("family_counts"), dict)
            and all(
                isinstance(name, str)
                and isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 0
                for name, value in row["family_counts"].items()
            )
            and sum(row["family_counts"].values()) == row["executed_cases"]
            and isinstance(row.get("stream_sha256"), str)
            and re.fullmatch(r"[A-F0-9]{64}", row["stream_sha256"]) is not None
        )
    if command_id == "sidecar-transport":
        return stderr == b"" and _one_line(
            stdout,
            r"sidecar parity: checks=[1-9][0-9]* failures=0 fixtures=[1-9][0-9]*",
        ) is not None
    if command_id == "sidecar-receipts":
        return stderr == b"" and _one_line(
            stdout,
            r"wp5 receipt verification: checks=[1-9][0-9]* failures=0",
        ) is not None
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
        returncode, stdout, stderr, timed_out, overflow = _run_bounded(
            argv,
            ROOT,
            env,
            timeout,
        )
        if timed_out:
            failures += 1
            print(
                f"FAIL {command_id} timeout={timeout} "
                f"stdout_sha256={_digest(stdout)} "
                f"stderr_sha256={_digest(stderr)}"
            )
        elif overflow or returncode != 0 or not _summary(command_id, stdout, stderr):
            failures += 1
            print(
                f"FAIL {command_id} exit={returncode} output_overflow={int(overflow)} "
                f"stdout_sha256={_digest(stdout)} "
                f"stderr_sha256={_digest(stderr)}"
            )
    print(f"portable gate: checks={len(COMMANDS) + 1} failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
