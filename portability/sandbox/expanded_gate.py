#!/usr/bin/env python3
"""Run the receiver-reliance expanded gate inside the hardened container.

This module is stdlib-only.  It verifies the effective Linux containment
boundary before invoking any repository command and stops at the first failed
command or count assertion.  The sole stdout record is canonical JSON so the
host runner can preserve it without parsing human-oriented logs.
"""

from __future__ import annotations

import base64
import hashlib
import json
import locale
import os
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys
import sysconfig
import time
from dataclasses import dataclass
from typing import Any

try:
    import resource
except ModuleNotFoundError:  # Allows static plan tests on the Windows host.
    resource = None  # type: ignore[assignment]


REPO = Path("/repo")
TMPFS_LIMIT_BYTES = 256 * 1024 * 1024
MEMORY_LIMIT_BYTES = 4 * 1024 * 1024 * 1024
PIDS_LIMIT = 256
CPU_LIMIT = 2.0
COMMAND_TIMEOUT_SECONDS = 300
EXPECTED_HOSTNAME = "rr-sandbox"


class BoundaryFailure(RuntimeError):
    """The effective container boundary is weaker than the declared spec."""


class GateFailure(RuntimeError):
    """A command failed or its declared count was not observed."""


@dataclass(frozen=True)
class GateSpec:
    gate_id: str
    cwd: str
    argv: tuple[str, ...]
    validator: str


GATES = (
    GateSpec(
        "frozen_0_2_parity",
        "/repo/baseline-run",
        ("python", "-B", "implementation-output-0.2/run_conformance_0_2.py"),
        "core_800",
    ),
    GateSpec(
        "composed_0_3_parity",
        "/repo/baseline-run",
        (
            "python",
            "-B",
            "implementation-output-0.3/run_conformance_0_3.py",
            "--suite",
            "all",
        ),
        "composed_800_107",
    ),
    GateSpec(
        "grounded_0_4_regression",
        "/repo",
        ("python", "-B", "grounded-0_4/test_grounded_0_4.py"),
        "checks_517",
    ),
    GateSpec(
        "contract_lint",
        "/repo",
        ("python", "-B", "grounded-0_4/lint_contract.py", "--gate"),
        "lint_zero",
    ),
    GateSpec(
        "lint_gate_meta",
        "/repo",
        ("python", "-B", "grounded-0_4/test_lint_gate.py"),
        "checks_9",
    ),
    GateSpec(
        "grounded_properties",
        "/repo",
        ("python", "-B", "grounded-0_4/test_properties.py"),
        "checks_2296",
    ),
    GateSpec(
        "audit_adversarial",
        "/repo",
        ("python", "-B", "grounded-0_4/test_audit_adversarial.py"),
        "checks_6497",
    ),
    GateSpec(
        "synthetic_proof_harness",
        "/repo",
        ("python", "-B", "proof/test_proof_harness.py"),
        "unittest_9",
    ),
    GateSpec(
        "fuzz_ci_smoke",
        "/repo",
        ("python", "-B", "fuzz/fuzz.py", "--ci-smoke"),
        "fuzz_31",
    ),
    GateSpec(
        "batch_perf",
        "/repo",
        ("python", "-B", "grounded-0_4/test_batch.py", "--perf"),
        "checks_2160",
    ),
    GateSpec(
        "single_pass_audit_benchmark",
        "/repo",
        (
            "python",
            "-B",
            "grounded-0_4/test_single_pass_audit.py",
            "--benchmark",
        ),
        "checks_1142",
    ),
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def _decode_mount_field(value: str) -> str:
    return re.sub(
        r"\\([0-7]{3})",
        lambda match: chr(int(match.group(1), 8)),
        value,
    )


def _mount_table() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for line in Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines():
        fields = line.split()
        separator = fields.index("-")
        mount_point = _decode_mount_field(fields[4])
        result[mount_point] = {
            "mount_options": sorted(fields[5].split(",")),
            "fs_type": fields[separator + 1],
            "super_options": sorted(fields[separator + 3].split(",")),
        }
    return result


def _parse_size(value: str) -> int:
    match = re.fullmatch(r"([0-9]+)([kKmMgG]?)", value)
    if not match:
        raise BoundaryFailure(f"unparseable tmpfs size: {value!r}")
    multiplier = {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3}[
        match.group(2).lower()
    ]
    return int(match.group(1)) * multiplier


def _tmpfs_size(mount: dict[str, Any]) -> int:
    for item in mount["super_options"]:
        if item.startswith("size="):
            return _parse_size(item.split("=", 1)[1])
    raise BoundaryFailure("/tmp tmpfs has no explicit size option")


def _status_fields() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            result[key] = value.strip()
    return result


def _check_cgroup() -> dict[str, Any]:
    root = Path("/sys/fs/cgroup")
    if not (root / "cgroup.controllers").exists():
        raise BoundaryFailure("cgroup v2 is required to verify resource limits")

    cpu_raw = _read_text(str(root / "cpu.max"))
    quota_text, period_text = cpu_raw.split()
    if quota_text == "max":
        raise BoundaryFailure("CPU limit is unbounded")
    quota = int(quota_text)
    period = int(period_text)
    cpu_ratio = quota / period
    if cpu_ratio != CPU_LIMIT:
        raise BoundaryFailure(f"CPU limit {cpu_ratio} != {CPU_LIMIT}")

    memory_raw = _read_text(str(root / "memory.max"))
    if memory_raw == "max" or int(memory_raw) != MEMORY_LIMIT_BYTES:
        raise BoundaryFailure(
            f"memory.max {memory_raw!r} != {MEMORY_LIMIT_BYTES}"
        )

    pids_raw = _read_text(str(root / "pids.max"))
    if pids_raw == "max" or int(pids_raw) != PIDS_LIMIT:
        raise BoundaryFailure(f"pids.max {pids_raw!r} != {PIDS_LIMIT}")

    swap_path = root / "memory.swap.max"
    swap_raw = _read_text(str(swap_path)) if swap_path.exists() else None
    if swap_raw not in (None, "0"):
        raise BoundaryFailure(f"memory.swap.max {swap_raw!r} != '0'")

    return {
        "version": 2,
        "cpu_max": cpu_raw,
        "cpu_count": cpu_ratio,
        "memory_max_bytes": int(memory_raw),
        "memory_swap_max_bytes": None if swap_raw is None else int(swap_raw),
        "pids_max": int(pids_raw),
    }


def verify_boundary() -> dict[str, Any]:
    if platform.system() != "Linux":
        raise BoundaryFailure(f"Linux required, observed {platform.system()!r}")
    if os.geteuid() != 65532 or os.getegid() != 65532:
        raise BoundaryFailure(
            f"numeric non-root identity required, observed {os.geteuid()}:{os.getegid()}"
        )

    # Bind both process-visible hostname representations before any repository
    # command runs.  Only this one allowlisted, non-secret environment value is
    # retained; no other process environment values enter the receipt.
    hostname = os.uname().nodename
    if hostname != EXPECTED_HOSTNAME:
        raise BoundaryFailure(
            f"kernel nodename {hostname!r} != declared {EXPECTED_HOSTNAME!r}"
        )
    environment_hostname = os.environ.get("HOSTNAME")
    if environment_hostname != EXPECTED_HOSTNAME:
        raise BoundaryFailure(
            "process HOSTNAME does not equal the declared sandbox hostname"
        )

    status = _status_fields()
    for field in ("CapEff", "CapPrm", "CapBnd", "CapAmb"):
        if int(status.get(field, "-1"), 16) != 0:
            raise BoundaryFailure(f"{field} is not zero: {status.get(field)!r}")
    if status.get("NoNewPrivs") != "1":
        raise BoundaryFailure(
            f"NoNewPrivs is not active: {status.get('NoNewPrivs')!r}"
        )

    mounts = _mount_table()
    for required in ("/", "/repo", "/tmp"):
        if required not in mounts:
            raise BoundaryFailure(f"required mount {required!r} is absent")
    if "ro" not in mounts["/"]["mount_options"]:
        raise BoundaryFailure("container root filesystem is not read-only")
    if "ro" not in mounts["/repo"]["mount_options"]:
        raise BoundaryFailure("repository bind mount is not read-only")

    tmp_mount = mounts["/tmp"]
    if tmp_mount["fs_type"] != "tmpfs":
        raise BoundaryFailure(f"/tmp is {tmp_mount['fs_type']!r}, not tmpfs")
    tmp_options = set(tmp_mount["mount_options"]) | set(tmp_mount["super_options"])
    for required in ("rw", "noexec", "nosuid", "nodev"):
        if required not in tmp_options:
            raise BoundaryFailure(f"/tmp is missing mount option {required!r}")
    tmp_size = _tmpfs_size(tmp_mount)
    if tmp_size != TMPFS_LIMIT_BYTES:
        raise BoundaryFailure(
            f"/tmp limit {tmp_size} != declared {TMPFS_LIMIT_BYTES}"
        )

    interfaces = sorted(path.name for path in Path("/sys/class/net").iterdir())
    if interfaces != ["lo"]:
        raise BoundaryFailure(
            f"network namespace exposes interfaces beyond loopback: {interfaces!r}"
        )

    public_key_names = {"GPG_KEY", "PYTHON_GPG_KEY"}
    secret_pattern = re.compile(
        r"(?:SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|PRIVATE|API_KEY|ACCESS_KEY|SESSION_KEY)",
        re.IGNORECASE,
    )
    secret_like_names = sorted(
        name
        for name in os.environ
        if name not in public_key_names and secret_pattern.search(name)
    )
    if secret_like_names:
        raise BoundaryFailure(
            f"secret-like environment names are present: {secret_like_names!r}"
        )

    return {
        "uid": os.geteuid(),
        "gid": os.getegid(),
        "hostname": hostname,
        "environment_hostname": environment_hostname,
        "capabilities": {
            field: status[field] for field in ("CapEff", "CapPrm", "CapBnd", "CapAmb")
        },
        "no_new_privileges": int(status["NoNewPrivs"]),
        "seccomp_mode": int(status.get("Seccomp", "0")),
        "root_read_only": True,
        "repo_read_only": True,
        "tmp": {
            "fs_type": tmp_mount["fs_type"],
            "limit_bytes": tmp_size,
            "options": sorted(tmp_options),
        },
        "network_interfaces": interfaces,
        "environment_names": sorted(os.environ),
        "secret_like_environment_names": secret_like_names,
        "cgroup": _check_cgroup(),
    }


def _unique_summary_line(
    candidate_pattern: str,
    pattern: str,
    text: str,
    description: str,
) -> re.Match[str]:
    candidates = [
        line.rstrip("\r")
        for line in text.splitlines()
        if re.match(candidate_pattern, line)
    ]
    if len(candidates) != 1:
        raise GateFailure(
            f"expected exactly one {description}; observed {len(candidates)}"
        )
    match = re.fullmatch(pattern, candidates[0])
    if match is None:
        raise GateFailure(f"malformed {description}")
    return match


def _reject_duplicate_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse a repeated member instead of resolving it last-value-wins.

    This is the authoritative summary parser: its result decides whether a gate
    passes.  Default JSON decoding collapses ``{"a":1,"a":800}`` to 800, so a
    subprocess could print contradictory raw evidence and still sum to the
    expected total (csf_0d1df8c6).  Rejection is the only defensible reading of
    a document that says two different things.
    """
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate JSON member {key!r}")
        seen[key] = value
    return seen


def _count_object(raw: str, description: str) -> dict[str, int]:
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_members)
    except (json.JSONDecodeError, ValueError) as error:
        raise GateFailure(
            f"{description} counts are not valid unambiguous JSON"
        ) from error
    if (
        not isinstance(value, dict)
        or not value
        or not all(
            isinstance(key, str)
            and type(member) is int
            and member >= 0
            for key, member in value.items()
        )
    ):
        raise GateFailure(f"{description} counts are outside the finite schema")
    return value


def _extract_counts(pattern: str, text: str, expected: int) -> dict[str, int]:
    candidates = [
        line.rstrip("\r") for line in text.splitlines() if "checks=" in line
    ]
    if len(candidates) != 1:
        raise GateFailure(
            "expected exactly one checks/failures summary; "
            f"observed {len(candidates)}"
        )
    candidate = candidates[0]
    if candidate.count("checks=") != 1 or candidate.count("failures=") != 1:
        raise GateFailure("malformed checks/failures summary")
    match = re.search(pattern, candidate)
    if match is None:
        raise GateFailure("malformed checks/failures summary")
    checks = int(match.group("checks"))
    failures = int(match.group("failures"))
    if checks != expected or failures != 0:
        raise GateFailure(
            f"summary observed checks={checks} failures={failures}; expected {expected}/0"
        )
    return {"checks": checks, "failures": failures}


def validate_gate_output(validator: str, stdout: bytes, stderr: bytes) -> dict[str, Any]:
    try:
        out = stdout.decode("utf-8", errors="strict")
        err = stderr.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise GateFailure("gate output is not strict UTF-8") from error
    combined = out + "\n" + err

    if validator == "core_800":
        match = _unique_summary_line(
            r"^mode=in-process\b",
            r"mode=in-process counts=(?P<counts>\{[^\r\n]+\}) failures=(?P<failures>[0-9]+)",
            combined,
            "frozen 0.2 in-process summary",
        )
        counts = _count_object(match.group("counts"), "frozen 0.2")
        failures = int(match.group("failures"))
        if sum(counts.values()) != 800 or failures != 0:
            raise GateFailure(
                f"frozen 0.2 observed total={sum(counts.values())} failures={failures}"
            )
        return {"total": 800, "failures": 0, "counts": counts}

    if validator == "composed_800_107":
        composed_lines = [
            line
            for line in combined.splitlines()
            if re.match(r"^mode=in-process\s+suite=", line)
        ]
        if len(composed_lines) != 2:
            raise GateFailure(
                "composed gate requires exactly two suite summaries; "
                f"observed {len(composed_lines)}"
            )
        observed: dict[str, dict[str, int]] = {}
        for suite, expected in (("0.2", 800), ("0.3", 107)):
            match = _unique_summary_line(
                rf"^mode=in-process\s+suite={re.escape(suite)}\b",
                rf"mode=in-process suite={re.escape(suite)} "
                rf"counts=(?P<counts>\{{[^\r\n]+\}}) "
                rf"total=(?P<total>[0-9]+) failures=(?P<failures>[0-9]+)",
                combined,
                f"composed {suite} summary",
            )
            total = int(match.group("total"))
            failures = int(match.group("failures"))
            counts = _count_object(match.group("counts"), f"composed {suite}")
            if total != expected or sum(counts.values()) != expected or failures != 0:
                raise GateFailure(
                    f"{suite} observed total={total} sum={sum(counts.values())} "
                    f"failures={failures}; expected {expected}/0"
                )
            observed[suite] = {"total": total, "failures": failures}
        return observed

    count_validators = {
        "checks_517": 517,
        "checks_9": 9,
        "checks_2296": 2296,
        "checks_6497": 6497,
        "checks_2160": 2160,
        "checks_1142": 1142,
        # Era-legacy values: the SHA-pinned portability-era gate receipts
        # replay through these via verify_receipts.py; no live GateSpec
        # references them.
        "checks_504": 504,
        "checks_7": 7,
    }
    if validator in count_validators:
        return _extract_counts(
            r"checks=(?P<checks>[0-9]+) failures=(?P<failures>[0-9]+)",
            combined,
            count_validators[validator],
        )

    if validator == "lint_zero":
        lines = [
            line.rstrip("\r")
            for line in combined.splitlines()
            if line.startswith("lint:")
        ]
        if lines != ["lint: 0 findings"]:
            raise GateFailure(
                "contract lint requires one zero-finding summary; "
                f"observed {lines!r}"
            )
        return {"findings": 0}

    unittest_match = re.fullmatch(r"unittest_([0-9]+)", validator)
    if unittest_match is not None:
        # The expected count lives in the validator name, as it does for every
        # ``checks_*`` validator above, so a sealed receipt replays through the
        # count its own era declared.  ``unittest_7`` is era-legacy: the two
        # SHA-pinned gate receipts reach it through verify_receipts.py's
        # LEGACY_GATE_VALIDATORS, and no live GateSpec references it.
        expected_tests = int(unittest_match.group(1))
        lines = [line.rstrip("\r") for line in combined.splitlines()]
        ran_lines = [
            line for line in lines if re.match(r"^Ran\b", line)
        ]
        ran = [
            match.group(1)
            for line in ran_lines
            if (match := re.fullmatch(r"Ran\s+([0-9]+)\s+tests?\b.*", line))
        ]
        ok = [line for line in lines if line == "OK"]
        failed = [
            line
            for line in lines
            if re.match(r"^(?:FAILED|ERROR)(?:\s|$)", line)
        ]
        if (
            len(ran_lines) != 1
            or ran != [str(expected_tests)]
            or len(ok) != 1
            or failed
        ):
            raise GateFailure(
                f"proof harness did not report {expected_tests} passing tests"
            )
        return {"tests": expected_tests, "failures": 0}

    if validator == "fuzz_31":
        summaries = re.findall(
            r"^rr-fuzz: verdict=[^\r\n]+\r?$", combined, re.MULTILINE
        )
        if len(summaries) != 1:
            raise GateFailure(
                f"fuzz smoke requires exactly one summary; observed {len(summaries)}"
            )
        match = re.fullmatch(
            r"rr-fuzz: verdict=PASS cases=(?P<done>[0-9]+)/(?P<total>[0-9]+) "
            r"[^\r\n]*failures=(?P<failures>[0-9]+) budget_exhausted=false\r?",
            summaries[0],
        )
        if not match:
            raise GateFailure("fuzz smoke did not report a passing 31/31 summary")
        done = int(match.group("done"))
        total = int(match.group("total"))
        failures = int(match.group("failures"))
        if (done, total, failures) != (31, 31, 0):
            raise GateFailure(
                f"fuzz smoke observed {done}/{total} failures={failures}; expected 31/31/0"
            )
        return {"strategies": total, "completed": done, "failures": failures}

    raise GateFailure(f"unknown output validator {validator!r}")


def _resource_snapshot() -> dict[str, int]:
    if resource is None:
        raise BoundaryFailure("Linux resource accounting module is unavailable")
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "user_cpu_us": round(usage.ru_utime * 1_000_000),
        "system_cpu_us": round(usage.ru_stime * 1_000_000),
        "max_rss_kib": int(usage.ru_maxrss),
        "voluntary_context_switches": int(usage.ru_nvcsw),
        "involuntary_context_switches": int(usage.ru_nivcsw),
    }


def _resource_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    result = {
        key: after[key] - before[key]
        for key in before
        if key != "max_rss_kib"
    }
    result["children_max_rss_kib"] = after["max_rss_kib"]
    return result


def run_gate(spec: GateSpec) -> dict[str, Any]:
    before = _resource_snapshot()
    started = time.monotonic_ns()
    timed_out = False
    try:
        completed = subprocess.run(
            spec.argv,
            cwd=spec.cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = 124
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""

    elapsed_ms = round((time.monotonic_ns() - started) / 1_000_000)
    after = _resource_snapshot()
    result: dict[str, Any] = {
        "gate_id": spec.gate_id,
        "cwd": spec.cwd,
        "argv": list(spec.argv),
        "exit_code": returncode,
        "timed_out": timed_out,
        "timeout_seconds": COMMAND_TIMEOUT_SECONDS,
        "stdout_sha256": _sha256(stdout),
        "stdout_bytes": len(stdout),
        "stderr_sha256": _sha256(stderr),
        "stderr_bytes": len(stderr),
        "stdout_b64": base64.b64encode(stdout).decode("ascii"),
        "stderr_b64": base64.b64encode(stderr).decode("ascii"),
        "elapsed_ms": elapsed_ms,
        "resources": _resource_delta(before, after),
    }
    if timed_out or returncode != 0:
        reason = "timed out" if timed_out else f"exited {returncode}"
        raise GateFailure(json.dumps({"reason": reason, "result": result}, sort_keys=True))

    try:
        result["observed"] = validate_gate_output(spec.validator, stdout, stderr)
    except GateFailure:
        result["failure_evidence"] = {
            "stdout_b64": base64.b64encode(stdout).decode("ascii"),
            "stderr_b64": base64.b64encode(stderr).decode("ascii"),
        }
        raise GateFailure(
            json.dumps({"reason": "count assertion", "result": result}, sort_keys=True)
        )
    return result


def _environment_receipt() -> dict[str, Any]:
    return {
        "os": platform.system(),
        "release": platform.release(),
        "kernel": platform.version(),
        "machine": platform.machine(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_build": list(platform.python_build()),
        "python_compiler": platform.python_compiler(),
        "python_executable": sys.executable,
        "python_build_flags": {
            "CONFIG_ARGS": sysconfig.get_config_var("CONFIG_ARGS"),
            "Py_DEBUG": sysconfig.get_config_var("Py_DEBUG"),
            "Py_GIL_DISABLED": sysconfig.get_config_var("Py_GIL_DISABLED"),
        },
        "word_size_bits": struct.calcsize("P") * 8,
        "byte_order": sys.byteorder,
        "locale_encoding": locale.getencoding(),
        "filesystem_encoding": sys.getfilesystemencoding(),
    }


def _stable_projection(boundary: dict[str, Any], gates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "receiver-reliance/sandbox-stable-projection-1",
        "boundary": {
            "uid": boundary["uid"],
            "gid": boundary["gid"],
            "hostname": boundary["hostname"],
            "environment_hostname": boundary["environment_hostname"],
            "capabilities": boundary["capabilities"],
            "no_new_privileges": boundary["no_new_privileges"],
            "root_read_only": boundary["root_read_only"],
            "repo_read_only": boundary["repo_read_only"],
            "tmp_limit_bytes": boundary["tmp"]["limit_bytes"],
            "network_interfaces": boundary["network_interfaces"],
            "cgroup": boundary["cgroup"],
        },
        "gates": [
            {
                "gate_id": gate["gate_id"],
                "cwd": gate["cwd"],
                "argv": gate["argv"],
                "exit_code": gate["exit_code"],
                "timed_out": gate["timed_out"],
                "observed": gate["observed"],
            }
            for gate in gates
        ],
    }


def main() -> int:
    receipt: dict[str, Any] = {
        "schema": "receiver-reliance/sandbox-container-receipt-1",
        "treatment_exposed": True,
        "status": "STARTED",
        "environment": _environment_receipt(),
        "commands": [],
    }
    try:
        boundary = verify_boundary()
        receipt["boundary"] = boundary
    except Exception as exc:
        receipt["status"] = "HARDENING_FAILURE"
        receipt["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        print(_canonical_bytes(receipt).decode("ascii"), flush=True)
        return 1

    for spec in GATES:
        try:
            receipt["commands"].append(run_gate(spec))
        except GateFailure as exc:
            receipt["status"] = "NORMATIVE_DIVERGENCE"
            receipt["failure"] = {
                "gate_id": spec.gate_id,
                "type": type(exc).__name__,
                "message": str(exc),
            }
            print(_canonical_bytes(receipt).decode("ascii"), flush=True)
            return 1

    stable = _stable_projection(boundary, receipt["commands"])
    receipt["deterministic_projection_sha256"] = _sha256(_canonical_bytes(stable))
    receipt["status"] = "PASS"
    print(_canonical_bytes(receipt).decode("ascii"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
