"""Run the exact eleven-command charter gate and emit one durable receipt."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import time
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[1]
RECEIPT_ROOT = REPO / "portability" / "receipts"
SANDBOX = REPO / "portability" / "sandbox"
if str(SANDBOX) not in sys.path:
    sys.path.insert(0, str(SANDBOX))

import expanded_gate  # noqa: E402


HOME_MARKER = "<HOME>"


def _redact(value: str) -> str:
    """Remove the operator's home directory from a path recorded in evidence.

    Published receipts in this repository carry the maintainer's home directory
    inside ``runtime.executable`` and every ``executed_argv``. On a public
    artifact that is a leak with no evidentiary purpose: the interpreter identity
    that matters is the implementation, version and build, all recorded
    separately, and the account name carries none of it. The sealed receipts
    cannot be corrected without breaking their digests, so this stops new ones
    from repeating it. Path structure below the home directory is preserved.
    """

    home = str(pathlib.Path.home())
    if not home:
        return value
    for spelling in (home, home.replace("\\", "/")):
        for candidate in (spelling, spelling.replace("/", "\\")):
            if candidate and candidate in value:
                value = value.replace(candidate, HOME_MARKER)
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _git(command: list[str]) -> bytes:
    return subprocess.run(
        ["git", *command],
        cwd=REPO,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def receipt_path_error(
    receipt_path: pathlib.Path,
    repo: pathlib.Path = REPO,
    receipt_root: pathlib.Path = RECEIPT_ROOT,
) -> str | None:
    """Return the policy violation for a receipt destination, if any.

    Allowed destinations are the durable custody directory
    ``portability/receipts`` and any path entirely outside the repository
    (so a verification rerun can execute against a clean worktree without
    creating repository state).  Any other in-repository destination is
    rejected.
    """
    resolved = receipt_path.resolve()
    try:
        resolved.relative_to(receipt_root.resolve())
        return None
    except ValueError:
        pass
    try:
        resolved.relative_to(repo.resolve())
    except ValueError:
        return None
    return (
        "--receipt must stay under portability/receipts or entirely "
        "outside the repository"
    )


def receipt_path_label(
    receipt_path: pathlib.Path, repo: pathlib.Path = REPO
) -> str:
    """Receipt self-description for both permitted destination shapes."""
    resolved = receipt_path.resolve()
    try:
        return resolved.relative_to(repo.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def receipt_status(
    exit_code: int,
    git_start: dict[str, Any],
    git_end: dict[str, Any],
    command_count: int,
) -> str:
    """PASS only for a full clean-to-clean run of every authority command."""
    return (
        "PASS"
        if (
            exit_code == 0
            and git_start.get("clean") is True
            and git_end.get("clean") is True
            and git_end.get("head") == git_start.get("head")
            and command_count == len(expanded_gate.GATES)
        )
        else "FAIL"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    receipt_path = args.receipt.resolve()
    path_error = receipt_path_error(receipt_path)
    if path_error is not None:
        raise SystemExit(path_error)
    if receipt_path.exists():
        raise SystemExit("refusing to overwrite an existing gate receipt")

    started = datetime.now(timezone.utc)
    status_bytes = _git(["status", "--porcelain=v1", "--untracked-files=all"])
    receipt: dict[str, Any] = {
        "schema": "receiver-reliance/local-expanded-gate-receipt-2",
        "status": "STARTED",
        "started_utc": started.isoformat(),
        "authority_commands": 11,
        "receipt_path": receipt_path_label(receipt_path),
        "git": {
            "head": _git(["rev-parse", "HEAD"]).decode("ascii").strip(),
            "clean": status_bytes == b"",
            "status_bytes": len(status_bytes),
            "status_sha256": _sha256(status_bytes),
        },
        "runtime": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "machine": platform.machine(),
            "platform": platform.platform(),
            "executable": _redact(sys.executable),
        },
        "commands": [],
    }
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "TZ": "UTC",
        }
    )
    exit_code = 0
    for spec in expanded_gate.GATES:
        cwd = REPO / pathlib.PurePosixPath(spec.cwd).relative_to("/repo")
        executed = [sys.executable, *spec.argv[1:]]
        recorded_argv = [_redact(item) for item in executed]
        before = time.monotonic_ns()
        timed_out = False
        try:
            completed = subprocess.run(
                executed,
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=expanded_gate.COMMAND_TIMEOUT_SECONDS,
                check=False,
            )
            command_exit = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as error:
            timed_out = True
            command_exit = 124
            stdout = error.stdout or b""
            stderr = error.stderr or b""
        result: dict[str, Any] = {
            "gate_id": spec.gate_id,
            "cwd": spec.cwd,
            "declared_argv": list(spec.argv),
            "executed_argv": recorded_argv,
            "exit_code": command_exit,
            "timed_out": timed_out,
            "elapsed_ms": round((time.monotonic_ns() - before) / 1_000_000),
            "stdout_bytes": len(stdout),
            "stdout_sha256": _sha256(stdout),
            "stdout_b64": base64.b64encode(stdout).decode("ascii"),
            "stderr_bytes": len(stderr),
            "stderr_sha256": _sha256(stderr),
            "stderr_b64": base64.b64encode(stderr).decode("ascii"),
        }
        try:
            if timed_out or command_exit != 0:
                raise expanded_gate.GateFailure(
                    "timed out" if timed_out else f"exited {command_exit}"
                )
            result["observed"] = expanded_gate.validate_gate_output(
                spec.validator, stdout, stderr
            )
            result["status"] = "PASS"
        except (expanded_gate.GateFailure, UnicodeError, ValueError) as error:
            result["status"] = "FAIL"
            result["failure"] = {"type": type(error).__name__, "message": str(error)}
            exit_code = 1
        receipt["commands"].append(result)
        if exit_code:
            break

    end_status_bytes = _git(["status", "--porcelain=v1", "--untracked-files=all"])
    receipt["git_end"] = {
        "head": _git(["rev-parse", "HEAD"]).decode("ascii").strip(),
        "clean": end_status_bytes == b"",
        "status_bytes": len(end_status_bytes),
        "status_sha256": _sha256(end_status_bytes),
    }
    receipt["finished_utc"] = datetime.now(timezone.utc).isoformat()
    receipt["status"] = receipt_status(
        exit_code, receipt["git"], receipt["git_end"], len(receipt["commands"])
    )
    if receipt["status"] != "PASS":
        exit_code = 1
    receipt["receipt_sha256"] = _sha256(_canonical(receipt))
    payload = _canonical(receipt) + b"\n"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(receipt_path, "xb") as stream:
            stream.write(payload)
    except FileExistsError as error:
        raise SystemExit("refusing to overwrite an existing gate receipt") from error
    print(payload.decode("ascii"), end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
