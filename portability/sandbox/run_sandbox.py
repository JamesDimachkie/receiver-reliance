#!/usr/bin/env python3
"""Build, verify, and run the hardened receiver-reliance Linux sandbox."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import locale
import math
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
import platform
import re
import struct
import subprocess
import sys
import sysconfig
import time
from typing import Any

import expanded_gate


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DOCKERFILE = HERE / "Dockerfile"
BASELINE_SHA = "4e788d21e882a30bdda2aec3f780537161f81644"
EXPECTED_BRANCH = "sol/rr-portability-modelcheck-20260810"
CONTAINER_TIMEOUT_SECONDS = 1800
CLEANUP_TIMEOUT_SECONDS = 30
EXPECTED_ENTRYPOINT = [
    "python",
    "-B",
    "/repo/portability/sandbox/expanded_gate.py",
]
EXPECTED_COMMAND: list[str] = []
EXPECTED_PROCESS_PATH = EXPECTED_ENTRYPOINT[0]
EXPECTED_PROCESS_ARGS = EXPECTED_ENTRYPOINT[1:] + EXPECTED_COMMAND
EXPECTED_HOSTNAME = "rr-sandbox"
MOUNT_SOURCE_COMPARISON = "exact-after-host-resolve"
EXPECTED_EFFECTIVE_MOUNT_MODE = "ro"
EXPECTED_EFFECTIVE_MOUNT_PROPAGATION = "rprivate"

# Exact effective Config.Env for the manifest-pinned Python base plus this
# Dockerfile.  The first three entries are pinned-base metadata; the remaining
# entries are explicitly declared by Dockerfile and/or docker create.  HOSTNAME
# is explicit so Docker's otherwise synthesized process variable is represented
# in Config.Env and can be reconciled exactly with the inner process.
# Values are checked before the selected inspect projection is retained.  The
# sole retained value is the exact, public HOSTNAME constant needed for
# process/config reconciliation; all other environment values stay excluded.
EXPECTED_EFFECTIVE_ENVIRONMENT = {
    "PATH": "/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "PYTHON_VERSION": "3.14.1",
    "PYTHON_SHA256": "8dfa08b1959d9d15838a1c2dab77dc8d8ff4a553a1ed046dfacbc8095c6d42fc",
    "HOME": "/tmp",
    "HOSTNAME": EXPECTED_HOSTNAME,
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "TMPDIR": "/tmp",
    "TZ": "UTC",
}
PINNED_BASE_ENVIRONMENT_NAMES = {"PATH", "PYTHON_VERSION", "PYTHON_SHA256"}
DOCKERFILE_ENVIRONMENT_NAMES = {
    "HOME",
    "LANG",
    "LC_ALL",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONHASHSEED",
    "TMPDIR",
    "TZ",
}
CREATE_ENVIRONMENT_NAMES = set(DOCKERFILE_ENVIRONMENT_NAMES) | {"HOSTNAME"}
EXPECTED_ENVIRONMENT_NAMES = sorted(EXPECTED_EFFECTIVE_ENVIRONMENT)
ENVIRONMENT_NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
PUBLIC_ENVIRONMENT_NAME_EXCEPTIONS = {"GPG_KEY", "PYTHON_GPG_KEY"}
SECRET_LIKE_ENVIRONMENT_NAME_PATTERN = re.compile(
    r"(?:SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|PRIVATE|API_KEY|ACCESS_KEY|SESSION_KEY)",
    re.IGNORECASE,
)


class InnerReceiptError(ValueError):
    """The container's claimed PASS receipt is incomplete or inconsistent."""


class DockerMetadataError(ValueError):
    """Untrusted Docker JSON was malformed, ambiguous, or wrongly shaped."""


class DockerVersionError(DockerMetadataError):
    """The Docker version probe did not return the required object shape."""


class DockerInspectError(DockerMetadataError):
    """A Docker inspect response did not identify exactly one valid object."""


EXPECTED_OBSERVED = {
    "frozen_0_2_parity": {
        "total": 800,
        "failures": 0,
        "counts": {
            "semantic": 112,
            "competence": 370,
            "wrapper_arms": 224,
            "negative": 10,
            "metamorphic": 4,
            "error_law": 80,
        },
    },
    "composed_0_3_parity": {
        "0.2": {"total": 800, "failures": 0},
        "0.3": {"total": 107, "failures": 0},
    },
    "grounded_0_4_regression": {"checks": 504, "failures": 0},
    "contract_lint": {"findings": 0},
    "lint_gate_meta": {"checks": 7, "failures": 0},
    "grounded_properties": {"checks": 2296, "failures": 0},
    "audit_adversarial": {"checks": 6497, "failures": 0},
    "synthetic_proof_harness": {"tests": 7, "failures": 0},
    "fuzz_ci_smoke": {"strategies": 31, "completed": 31, "failures": 0},
    "batch_perf": {"checks": 2160, "failures": 0},
    "single_pass_audit_benchmark": {"checks": 1142, "failures": 0},
}

TOP_LEVEL_INNER_KEYS = {
    "schema",
    "treatment_exposed",
    "status",
    "environment",
    "boundary",
    "commands",
    "deterministic_projection_sha256",
}
ENVIRONMENT_KEYS = {
    "os",
    "release",
    "kernel",
    "machine",
    "python_implementation",
    "python_version",
    "python_build",
    "python_compiler",
    "python_executable",
    "python_build_flags",
    "word_size_bits",
    "byte_order",
    "locale_encoding",
    "filesystem_encoding",
}
BOUNDARY_KEYS = {
    "uid",
    "gid",
    "hostname",
    "environment_hostname",
    "capabilities",
    "no_new_privileges",
    "seccomp_mode",
    "root_read_only",
    "repo_read_only",
    "tmp",
    "network_interfaces",
    "environment_names",
    "secret_like_environment_names",
    "cgroup",
}
COMMAND_KEYS = {
    "gate_id",
    "cwd",
    "argv",
    "exit_code",
    "timed_out",
    "timeout_seconds",
    "stdout_sha256",
    "stdout_bytes",
    "stderr_sha256",
    "stderr_bytes",
    "stdout_b64",
    "stderr_b64",
    "elapsed_ms",
    "resources",
    "observed",
}
RESOURCE_KEYS = {
    "user_cpu_us",
    "system_cpu_us",
    "voluntary_context_switches",
    "involuntary_context_switches",
    "children_max_rss_kib",
}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
CONTAINER_ID_PATTERN = re.compile(r"[0-9a-f]{64}")
CONTAINER_ID_OUTPUT_PATTERN = re.compile(rb"[0-9a-f]{64}(?:\r?\n)?")
IMAGE_ID_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
IMAGE_TAG_PATTERN = re.compile(
    r"receiver-reliance-portability-sandbox:[0-9a-f]{12}"
)
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _receipt_error(path: str, message: str) -> InnerReceiptError:
    return InnerReceiptError(f"{path}: {message}")


def _object_from_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InnerReceiptError(f"duplicate JSON member {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise InnerReceiptError(f"non-finite JSON number {value!r}")


def _parse_json_float(value: str) -> float:
    """Parse one JSON float without admitting overflow as infinity."""

    try:
        parsed = float(value)
    except (OverflowError, ValueError) as exc:
        raise InnerReceiptError(f"invalid JSON number {value!r}") from exc
    if not math.isfinite(parsed):
        raise InnerReceiptError(f"non-finite JSON number {value!r}")
    return parsed


def _require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _receipt_error(path, "must be an object")
    return value


def _require_exact_keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise _receipt_error(path, f"schema mismatch; missing={missing!r} extra={extra!r}")


def _require_string(value: Any, path: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise _receipt_error(path, "must be a nonempty string")
    return value


def _require_int(value: Any, path: str, *, minimum: int | None = None) -> int:
    if type(value) is not int:
        raise _receipt_error(path, "must be an integer")
    if minimum is not None and value < minimum:
        raise _receipt_error(path, f"must be >= {minimum}")
    return value


def _require_string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise _receipt_error(path, "must be an array of strings")
    if value != sorted(set(value)):
        raise _receipt_error(path, "must be sorted and contain no duplicates")
    return value


def _require_sha256(value: Any, path: str) -> None:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise _receipt_error(path, "must be a lowercase SHA-256 digest")


def _secret_like_environment_names(names: list[str]) -> list[str]:
    return sorted(
        name
        for name in names
        if name not in PUBLIC_ENVIRONMENT_NAME_EXCEPTIONS
        and SECRET_LIKE_ENVIRONMENT_NAME_PATTERN.search(name)
    )


def _validate_environment(value: Any) -> None:
    environment = _require_object(value, "environment")
    _require_exact_keys(environment, ENVIRONMENT_KEYS, "environment")
    if environment["os"] != "Linux":
        raise _receipt_error("environment.os", "must be 'Linux'")
    for key in (
        "release",
        "kernel",
        "machine",
        "python_implementation",
        "python_version",
        "python_compiler",
        "python_executable",
        "locale_encoding",
        "filesystem_encoding",
    ):
        _require_string(environment[key], f"environment.{key}")
    python_build = environment["python_build"]
    if (
        not isinstance(python_build, list)
        or len(python_build) != 2
        or any(not isinstance(item, str) for item in python_build)
    ):
        raise _receipt_error("environment.python_build", "must be two strings")
    flags = _require_object(environment["python_build_flags"], "environment.python_build_flags")
    _require_exact_keys(
        flags,
        {"CONFIG_ARGS", "Py_DEBUG", "Py_GIL_DISABLED"},
        "environment.python_build_flags",
    )
    if flags["CONFIG_ARGS"] is not None and not isinstance(flags["CONFIG_ARGS"], str):
        raise _receipt_error(
            "environment.python_build_flags.CONFIG_ARGS", "must be string or null"
        )
    for key in ("Py_DEBUG", "Py_GIL_DISABLED"):
        if flags[key] is not None and type(flags[key]) is not int:
            raise _receipt_error(
                f"environment.python_build_flags.{key}", "must be integer or null"
            )
    word_size = _require_int(
        environment["word_size_bits"], "environment.word_size_bits"
    )
    if word_size not in (32, 64):
        raise _receipt_error("environment.word_size_bits", "must be 32 or 64")
    if environment["byte_order"] not in ("little", "big"):
        raise _receipt_error("environment.byte_order", "must be 'little' or 'big'")


def _validate_boundary(value: Any) -> None:
    boundary = _require_object(value, "boundary")
    _require_exact_keys(boundary, BOUNDARY_KEYS, "boundary")
    if _require_int(boundary["uid"], "boundary.uid") != 65532:
        raise _receipt_error("boundary.uid", "must equal 65532")
    if _require_int(boundary["gid"], "boundary.gid") != 65532:
        raise _receipt_error("boundary.gid", "must equal 65532")
    hostname = _require_string(boundary["hostname"], "boundary.hostname")
    if hostname != EXPECTED_HOSTNAME:
        raise _receipt_error(
            "boundary.hostname", f"must equal {EXPECTED_HOSTNAME!r}"
        )
    environment_hostname = _require_string(
        boundary["environment_hostname"], "boundary.environment_hostname"
    )
    if environment_hostname != EXPECTED_HOSTNAME:
        raise _receipt_error(
            "boundary.environment_hostname",
            f"must equal {EXPECTED_HOSTNAME!r}",
        )

    capabilities = _require_object(boundary["capabilities"], "boundary.capabilities")
    capability_fields = {"CapEff", "CapPrm", "CapBnd", "CapAmb"}
    _require_exact_keys(capabilities, capability_fields, "boundary.capabilities")
    for key in sorted(capability_fields):
        raw = _require_string(capabilities[key], f"boundary.capabilities.{key}")
        if re.fullmatch(r"[0-9A-Fa-f]+", raw) is None or int(raw, 16) != 0:
            raise _receipt_error(f"boundary.capabilities.{key}", "must be a zero hexadecimal mask")

    if _require_int(boundary["no_new_privileges"], "boundary.no_new_privileges") != 1:
        raise _receipt_error("boundary.no_new_privileges", "must equal 1")
    _require_int(boundary["seccomp_mode"], "boundary.seccomp_mode", minimum=0)
    for key in ("root_read_only", "repo_read_only"):
        if boundary[key] is not True:
            raise _receipt_error(f"boundary.{key}", "must be true")

    tmp = _require_object(boundary["tmp"], "boundary.tmp")
    _require_exact_keys(tmp, {"fs_type", "limit_bytes", "options"}, "boundary.tmp")
    if tmp["fs_type"] != "tmpfs":
        raise _receipt_error("boundary.tmp.fs_type", "must equal 'tmpfs'")
    if _require_int(tmp["limit_bytes"], "boundary.tmp.limit_bytes") != 256 * 1024 * 1024:
        raise _receipt_error("boundary.tmp.limit_bytes", "must equal 268435456")
    tmp_options = _require_string_list(tmp["options"], "boundary.tmp.options")
    required_tmp_options = {"rw", "noexec", "nosuid", "nodev"}
    if not required_tmp_options.issubset(tmp_options):
        raise _receipt_error("boundary.tmp.options", "missing required hardening option")

    if _require_string_list(
        boundary["network_interfaces"], "boundary.network_interfaces"
    ) != ["lo"]:
        raise _receipt_error("boundary.network_interfaces", "must equal ['lo']")
    environment_names = _require_string_list(
        boundary["environment_names"], "boundary.environment_names"
    )
    if not environment_names:
        raise _receipt_error("boundary.environment_names", "must not be empty")
    claimed_secret_names = _require_string_list(
        boundary["secret_like_environment_names"],
        "boundary.secret_like_environment_names",
    )
    recomputed_secret_names = _secret_like_environment_names(environment_names)
    if claimed_secret_names or recomputed_secret_names:
        raise _receipt_error("boundary.secret_like_environment_names", "must be empty")

    cgroup = _require_object(boundary["cgroup"], "boundary.cgroup")
    _require_exact_keys(
        cgroup,
        {
            "version",
            "cpu_max",
            "cpu_count",
            "memory_max_bytes",
            "memory_swap_max_bytes",
            "pids_max",
        },
        "boundary.cgroup",
    )
    if _require_int(cgroup["version"], "boundary.cgroup.version") != 2:
        raise _receipt_error("boundary.cgroup.version", "must equal 2")
    cpu_max = _require_string(cgroup["cpu_max"], "boundary.cgroup.cpu_max")
    try:
        quota_text, period_text = cpu_max.split()
        quota, period = int(quota_text), int(period_text)
    except (ValueError, TypeError) as exc:
        raise _receipt_error(
            "boundary.cgroup.cpu_max", "must contain integer quota and period"
        ) from exc
    if quota <= 0 or period <= 0 or quota / period != 2.0:
        raise _receipt_error("boundary.cgroup.cpu_max", "must encode exactly 2 CPUs")
    cpu_count = cgroup["cpu_count"]
    if type(cpu_count) not in (int, float) or cpu_count != 2.0:
        raise _receipt_error("boundary.cgroup.cpu_count", "must equal 2.0")
    memory_max = _require_int(
        cgroup["memory_max_bytes"], "boundary.cgroup.memory_max_bytes"
    )
    if memory_max != 4 * 1024**3:
        raise _receipt_error("boundary.cgroup.memory_max_bytes", "must equal 4294967296")
    if cgroup["memory_swap_max_bytes"] is not None and (
        _require_int(
            cgroup["memory_swap_max_bytes"],
            "boundary.cgroup.memory_swap_max_bytes",
        )
        != 0
    ):
        raise _receipt_error("boundary.cgroup.memory_swap_max_bytes", "must be zero or null")
    if _require_int(cgroup["pids_max"], "boundary.cgroup.pids_max") != 256:
        raise _receipt_error("boundary.cgroup.pids_max", "must equal 256")


def _validate_command(value: Any, index: int, spec: expanded_gate.GateSpec) -> None:
    path = f"commands[{index}]"
    command = _require_object(value, path)
    _require_exact_keys(command, COMMAND_KEYS, path)
    expected_identity = {
        "gate_id": spec.gate_id,
        "cwd": spec.cwd,
        "argv": list(spec.argv),
    }
    for key, expected in expected_identity.items():
        if command[key] != expected:
            raise _receipt_error(f"{path}.{key}", f"must equal {expected!r}")
    if _require_int(command["exit_code"], f"{path}.exit_code") != 0:
        raise _receipt_error(f"{path}.exit_code", "must equal 0")
    if command["timed_out"] is not False:
        raise _receipt_error(f"{path}.timed_out", "must be false")
    timeout_seconds = _require_int(
        command["timeout_seconds"], f"{path}.timeout_seconds"
    )
    if timeout_seconds != expanded_gate.COMMAND_TIMEOUT_SECONDS:
        raise _receipt_error(
            f"{path}.timeout_seconds",
            f"must equal {expanded_gate.COMMAND_TIMEOUT_SECONDS}",
        )
    for key in ("stdout_sha256", "stderr_sha256"):
        _require_sha256(command[key], f"{path}.{key}")
    for key in ("stdout_bytes", "stderr_bytes", "elapsed_ms"):
        _require_int(command[key], f"{path}.{key}", minimum=0)
    for stream in ("stdout", "stderr"):
        encoded = command[f"{stream}_b64"]
        if not isinstance(encoded, str):
            raise _receipt_error(f"{path}.{stream}_b64", "must be a string")
        try:
            raw = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError) as error:
            raise _receipt_error(
                f"{path}.{stream}_b64", "must be strict canonical base64"
            ) from error
        if base64.b64encode(raw).decode("ascii") != encoded:
            raise _receipt_error(
                f"{path}.{stream}_b64", "must be strict canonical base64"
            )
        if len(raw) != command[f"{stream}_bytes"]:
            raise _receipt_error(
                f"{path}.{stream}_bytes", "does not match retained transcript"
            )
        if sha256(raw) != command[f"{stream}_sha256"]:
            raise _receipt_error(
                f"{path}.{stream}_sha256",
                "does not match retained transcript",
            )

    resources = _require_object(command["resources"], f"{path}.resources")
    _require_exact_keys(resources, RESOURCE_KEYS, f"{path}.resources")
    for key in sorted(RESOURCE_KEYS):
        _require_int(resources[key], f"{path}.resources.{key}", minimum=0)

    expected_observed = EXPECTED_OBSERVED[spec.gate_id]
    if command["observed"] != expected_observed:
        raise _receipt_error(
            f"{path}.observed",
            f"must equal the declared count evidence {expected_observed!r}",
        )


def validate_inner_receipt(payload: bytes) -> dict[str, Any]:
    """Parse and fully validate the sole canonical PASS record from the container."""

    try:
        decoded = payload.decode("utf-8", errors="strict")
        receipt = json.loads(
            decoded,
            object_pairs_hook=_object_from_pairs,
            parse_constant=_reject_json_constant,
            parse_float=_parse_json_float,
        )
    except InnerReceiptError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise InnerReceiptError(f"invalid canonical JSON: {exc}") from exc
    receipt = _require_object(receipt, "receipt")
    try:
        canonical = canonical_bytes(receipt)
    except (TypeError, ValueError) as exc:
        raise InnerReceiptError(f"receipt cannot be canonicalized: {exc}") from exc
    if payload != canonical + b"\n":
        raise InnerReceiptError("receipt is not the sole canonical JSON record")
    _require_exact_keys(receipt, TOP_LEVEL_INNER_KEYS, "receipt")
    if receipt["schema"] != "receiver-reliance/sandbox-container-receipt-1":
        raise _receipt_error("schema", "unsupported inner receipt schema")
    if receipt["treatment_exposed"] is not True:
        raise _receipt_error("treatment_exposed", "must be true")
    if receipt["status"] != "PASS":
        raise _receipt_error("status", "must equal 'PASS'")

    _validate_environment(receipt["environment"])
    _validate_boundary(receipt["boundary"])
    commands = receipt["commands"]
    if not isinstance(commands, list):
        raise _receipt_error("commands", "must be an array")
    if len(commands) != len(expanded_gate.GATES):
        raise _receipt_error(
            "commands", f"must contain exactly {len(expanded_gate.GATES)} entries"
        )
    paired_commands = zip(commands, expanded_gate.GATES, strict=True)
    for index, (command, spec) in enumerate(paired_commands):
        _validate_command(command, index, spec)

    _require_sha256(
        receipt["deterministic_projection_sha256"],
        "deterministic_projection_sha256",
    )
    projection = expanded_gate._stable_projection(receipt["boundary"], commands)
    expected_projection_hash = sha256(canonical_bytes(projection))
    if receipt["deterministic_projection_sha256"] != expected_projection_hash:
        raise _receipt_error(
            "deterministic_projection_sha256",
            f"does not match recomputed projection {expected_projection_hash}",
        )
    return receipt


def validate_container_pass(completed: subprocess.CompletedProcess[bytes]) -> dict[str, Any]:
    if completed.returncode != 0:
        raise InnerReceiptError(
            f"container exited {completed.returncode}; PASS requires container exit 0"
        )
    return validate_inner_receipt(completed.stdout)


def run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 60,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        argv,
        cwd=cwd,
        input=input_bytes,
        stdin=None if input_bytes is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )


def text(completed: subprocess.CompletedProcess[bytes]) -> str:
    return completed.stdout.decode("utf-8", errors="replace").strip()


def error_text(completed: subprocess.CompletedProcess[bytes]) -> str:
    return completed.stderr.decode("utf-8", errors="replace").strip()


def _created_container_id(payload: bytes) -> str:
    """Validate Docker CLI create output before it becomes an object handle."""

    if CONTAINER_ID_OUTPUT_PATTERN.fullmatch(payload) is None:
        raise RuntimeError(
            "docker create returned invalid container id output "
            f"(bytes={len(payload)}, sha256={sha256(payload)})"
        )
    if payload.endswith(b"\r\n"):
        identifier = payload[:-2]
    elif payload.endswith(b"\n"):
        identifier = payload[:-1]
    else:
        identifier = payload
    return identifier.decode("ascii")


def _docker_object_from_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one Docker metadata object without silently collapsing duplicates."""

    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DockerMetadataError(f"duplicate JSON member {key!r}")
        result[key] = value
    return result


def _reject_docker_json_constant(value: str) -> None:
    raise DockerMetadataError(f"non-finite JSON number {value!r}")


def _parse_docker_json_float(value: str) -> float:
    """Parse one Docker metadata float without admitting overflow to infinity."""

    try:
        parsed = float(value)
    except (OverflowError, ValueError) as exc:
        raise DockerMetadataError(f"invalid JSON number {value!r}") from exc
    if not math.isfinite(parsed):
        raise DockerMetadataError(f"non-finite JSON number {value!r}")
    return parsed


def _parse_docker_json(payload: bytes, description: str) -> Any:
    """Decode one finite, duplicate-free Docker JSON value."""

    try:
        decoded = payload.decode("utf-8", errors="strict")
        return json.loads(
            decoded,
            object_pairs_hook=_docker_object_from_pairs,
            parse_constant=_reject_docker_json_constant,
            parse_float=_parse_docker_json_float,
        )
    except DockerMetadataError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
        RecursionError,
    ) as exc:
        raise DockerMetadataError(
            f"{description} was not valid JSON: {exc}"
        ) from exc


def _parse_docker_version(payload: bytes) -> dict[str, Any]:
    """Parse the untrusted Docker version probe before any member access."""

    try:
        version = _parse_docker_json(payload, "Docker version response")
    except DockerMetadataError as exc:
        raise DockerVersionError(str(exc)) from exc
    if not isinstance(version, dict):
        raise DockerVersionError("response root must be an object")

    server = version.get("Server")
    if not isinstance(server, dict):
        raise DockerVersionError("Server must be an object")
    server_os = server.get("Os")
    if not isinstance(server_os, str) or not server_os:
        raise DockerVersionError("Server.Os must be a nonempty string")

    client = version.get("Client")
    if not isinstance(client, dict):
        raise DockerVersionError("Client must be an object")
    return version


def _parse_docker_inspect(payload: bytes, description: str) -> dict[str, Any]:
    """Require the CLI inspect representation of exactly one Docker object."""

    try:
        response = _parse_docker_json(payload, description)
    except DockerMetadataError as exc:
        raise DockerInspectError(str(exc)) from exc
    if not isinstance(response, list):
        raise DockerInspectError(f"{description} root must be an array")
    if len(response) != 1:
        raise DockerInspectError(
            f"{description} must contain exactly one object, got {len(response)}"
        )
    if not isinstance(response[0], dict):
        raise DockerInspectError(f"{description}[0] must be an object")
    return response[0]


def _validated_image_inspect(
    payload: bytes, expected_image_tag: str
) -> dict[str, str]:
    """Retain one built image identity obtained by inspecting its exact tag."""

    if (
        not isinstance(expected_image_tag, str)
        or IMAGE_TAG_PATTERN.fullmatch(expected_image_tag) is None
    ):
        raise DockerInspectError("expected image tag has invalid shape")
    raw = _parse_docker_inspect(payload, "Docker image inspect response")
    image_id = raw.get("Id")
    if not isinstance(image_id, str) or IMAGE_ID_PATTERN.fullmatch(image_id) is None:
        raise DockerInspectError("Docker image inspect Id has invalid shape")
    image_os = raw.get("Os")
    if not isinstance(image_os, str) or not image_os:
        raise DockerInspectError("Docker image inspect Os must be a nonempty string")
    image_arch = raw.get("Architecture")
    if not isinstance(image_arch, str) or not image_arch:
        raise DockerInspectError(
            "Docker image inspect Architecture must be a nonempty string"
        )
    return {
        "id": image_id,
        "tag": expected_image_tag,
        "os": image_os,
        "architecture": image_arch,
    }


def _docker_required_member(
    value: dict[str, Any], key: str, path: str
) -> Any:
    """Read one required Docker metadata member without default coercion."""

    if key not in value:
        raise DockerInspectError(f"{path}.{key} is missing")
    return value[key]


def _docker_required_object(
    value: dict[str, Any], key: str, path: str
) -> dict[str, Any]:
    member = _docker_required_member(value, key, path)
    if not isinstance(member, dict):
        raise DockerInspectError(f"{path}.{key} must be an object")
    return member


def _docker_required_list(
    value: dict[str, Any], key: str, path: str, *, allow_null: bool = False
) -> list[Any]:
    member = _docker_required_member(value, key, path)
    if member is None and allow_null:
        return []
    if not isinstance(member, list):
        suffix = " or null" if allow_null else ""
        raise DockerInspectError(f"{path}.{key} must be an array{suffix}")
    return member


def _docker_required_mapping(
    value: dict[str, Any], key: str, path: str, *, allow_null: bool = False
) -> dict[str, Any]:
    member = _docker_required_member(value, key, path)
    if member is None and allow_null:
        return {}
    if not isinstance(member, dict):
        suffix = " or null" if allow_null else ""
        raise DockerInspectError(f"{path}.{key} must be an object{suffix}")
    return member


def _docker_private_mode(value: dict[str, Any], key: str) -> str:
    member = _docker_required_member(value, key, "HostConfig")
    if not isinstance(member, str):
        raise DockerInspectError(f"HostConfig.{key} must be a string")
    return "private" if member == "" else member


def _strict_json_equal(actual: Any, expected: Any) -> bool:
    """Compare JSON-shaped evidence without Python bool/int equivalence."""

    if type(actual) is not type(expected):
        return False
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _strict_json_equal(left, right)
            for left, right in zip(actual, expected, strict=True)
        )
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            _strict_json_equal(actual[key], expected[key]) for key in expected
        )
    return actual == expected


def _repository_source_for_host(resolved: PurePath, host_os: str) -> str:
    """Render one already-resolved repository identity for a Docker host.

    Keeping platform rendering separate from filesystem resolution lets the
    same fail-closed rule be tested against Windows, Linux, and macOS roots
    without pretending a foreign path is resolvable on the current host.
    """

    if not resolved.is_absolute():
        raise RuntimeError("repository mount source did not resolve absolutely")
    if host_os in {"Linux", "Darwin"}:
        # A foreign Windows object renders its UNC root as POSIX-looking
        # "//server/share", so the dialect is checked before rendering and the
        # implementation-defined POSIX double-slash root is refused outright.
        if not isinstance(resolved, PurePosixPath):
            raise RuntimeError(
                f"{host_os} repository mount source is not a POSIX path dialect"
            )
        source = resolved.as_posix()
        if not source.startswith("/"):
            raise RuntimeError(
                f"{host_os} repository mount source is not an absolute POSIX path"
            )
        if source.startswith("//"):
            raise RuntimeError(
                f"{host_os} repository mount source uses an"
                " implementation-defined POSIX double-slash root"
            )
    elif host_os == "Windows":
        if not isinstance(resolved, PureWindowsPath):
            raise RuntimeError(
                "Windows repository mount source is not a Windows path dialect"
            )
        source = str(resolved)
        if not (resolved.drive or source.startswith("\\\\")):
            raise RuntimeError(
                "Windows repository mount source has no drive or UNC anchor"
            )
        if source.startswith("\\\\"):
            # CPython 3.14 treats any leading double backslash as absolute,
            # so UNC anatomy is validated explicitly on the component level:
            # the anchor must name both a server and a share that are real
            # names, not empty or whitespace-only components, on every
            # supported interpreter.  In the \\?\UNC\ and \\.\UNC\ extended
            # forms the real server and share sit after the namespace
            # prefix, which is what gets validated there.
            components = source[2:].split("\\")
            if (
                len(components) >= 2
                and components[0] in ("?", ".")
                and components[1].upper() == "UNC"
            ):
                server = components[2] if len(components) > 2 else ""
                share = components[3] if len(components) > 3 else ""
            else:
                server = components[0]
                share = components[1] if len(components) > 1 else ""
            if not server.strip() or not share.strip():
                raise RuntimeError(
                    "Windows repository mount source UNC anchor must name"
                    " both a server and a share"
                )
    else:
        raise RuntimeError(f"unsupported Docker host platform {host_os!r}")
    if "," in source:
        raise RuntimeError(
            "repository mount source contains a comma unsupported by --mount"
        )
    if '"' in source:
        # Docker's --mount value crosses Go's strict CSV reader; a bare
        # double quote in the source makes the whole plan unparseable, so it
        # fails closed here instead.
        raise RuntimeError(
            "repository mount source contains a double quote unsupported by"
            " --mount CSV parsing"
        )
    try:
        source.encode("utf-8")
    except UnicodeEncodeError as error:
        # A surrogate-escaped source is a real POSIX filename whose bytes
        # cannot survive strict UTF-8 plan hashing, and Go's JSON would
        # coerce them to U+FFFD, silently changing the mount identity; it
        # fails closed here instead.
        raise RuntimeError(
            "repository mount source is not strictly UTF-8 encodable"
        ) from error
    if "\x00" in source:
        # Operating-system argv cannot carry NUL, so the plan would fail
        # before Docker could even parse it.
        raise RuntimeError(
            "repository mount source contains a NUL byte unsupported by"
            " process arguments"
        )
    if "\n" in source:
        # A line feed splits the --mount value into a second CSV record that
        # Docker never reads.  A lone interior carriage return is ordinary
        # field data under Go's CSV grammar and stays legal.
        raise RuntimeError(
            "repository mount source contains a newline unsupported by"
            " --mount CSV parsing"
        )
    if source and (
        (source[0].isspace() and source[0] not in "\x1c\x1d\x1e\x1f")
        or (source[-1].isspace() and source[-1] not in "\x1c\x1d\x1e\x1f")
    ):
        # Docker trims each field value with Go's TrimSpace and rejects a
        # value whose trimmed spelling differs, so edge whitespace can never
        # form a usable plan.  The information separators U+001C..U+001F are
        # whitespace to Python but not to Go and therefore stay legal, as
        # does every interior spelling.
        raise RuntimeError(
            "repository mount source has leading or trailing whitespace"
            " rejected by --mount field parsing"
        )
    return source


def intended_repository_source(repo: Path = REPO) -> str:
    """Return the one host-resolved source accepted for the repository bind.

    Resolution applies only to the trusted local path.  Inspected Docker
    metadata is never normalized: accepting a normalized untrusted value would
    collapse traversal, alternate spelling, or case variants into the intended
    source.  Native POSIX hosts use their exact resolved POSIX spelling;
    Windows hosts use the exact resolved native spelling supplied to the CLI.
    """

    return _repository_source_for_host(repo.resolve(strict=True), platform.system())


def docker_create_args(
    image: str, repository_source: str | None = None
) -> list[str]:
    source = (
        intended_repository_source()
        if repository_source is None
        else repository_source
    )
    return [
        "docker",
        "create",
        "--read-only",
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--user",
        "65532:65532",
        "--cpus",
        "2.0",
        "--memory",
        "4g",
        "--memory-swap",
        "4g",
        "--pids-limit",
        "256",
        "--shm-size",
        "16m",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=268435456,mode=1777",
        "--mount",
        (
            f"type=bind,src={source},dst=/repo,readonly,"
            f"bind-propagation={EXPECTED_EFFECTIVE_MOUNT_PROPAGATION}"
        ),
        "--workdir",
        "/repo",
        "--hostname",
        EXPECTED_HOSTNAME,
        "--env",
        "HOME=/tmp",
        "--env",
        f"HOSTNAME={EXPECTED_HOSTNAME}",
        "--env",
        "TMPDIR=/tmp",
        "--env",
        "LANG=C.UTF-8",
        "--env",
        "LC_ALL=C.UTF-8",
        "--env",
        "TZ=UTC",
        "--env",
        "PYTHONHASHSEED=0",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--label",
        "org.receiver-reliance.role=portability-sandbox",
        image,
    ]


def _git_receipt() -> dict[str, Any]:
    head = run(["git", "rev-parse", "HEAD"], cwd=REPO)
    branch = run(["git", "branch", "--show-current"], cwd=REPO)
    status = run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=REPO,
    )
    ancestor = run(
        ["git", "merge-base", "--is-ancestor", BASELINE_SHA, "HEAD"],
        cwd=REPO,
    )
    if (
        any(item.returncode != 0 for item in (head, branch, status))
        or ancestor.returncode not in (0, 1)
    ):
        raise RuntimeError("git preflight failed")
    status_raw = status.stdout
    return {
        "sha": text(head),
        "branch": text(branch),
        "clean": not bool(status_raw),
        "status_sha256": sha256(status_raw),
        "baseline_ancestor": ancestor.returncode == 0,
    }


def _host_profile() -> dict[str, Any]:
    uname = platform.uname()
    return {
        "os": uname.system,
        "release": uname.release,
        "kernel": uname.version,
        "machine": uname.machine,
        "processor": uname.processor,
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_full_version": sys.version,
        "python_build": list(platform.python_build()),
        "python_compiler": platform.python_compiler(),
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


def _selected_inspect(raw: dict[str, Any]) -> dict[str, Any]:
    host = _docker_required_object(raw, "HostConfig", "container")
    config = _docker_required_object(raw, "Config", "container")
    environment = _docker_required_list(config, "Env", "Config")
    parsed_environment: dict[str, str] = {}
    for index, item in enumerate(environment):
        if not isinstance(item, str):
            raise DockerInspectError(f"Config.Env[{index}] must be a string")
        if "=" not in item:
            raise DockerInspectError(
                f"Config.Env[{index}] must have exact NAME=value form"
            )
        name, value = item.split("=", 1)
        if ENVIRONMENT_NAME_PATTERN.fullmatch(name) is None:
            raise DockerInspectError(
                f"Config.Env[{index}] has an invalid environment name"
            )
        if name in parsed_environment:
            raise DockerInspectError(f"Config.Env has duplicate name {name!r}")
        parsed_environment[name] = value

    actual_names = set(parsed_environment)
    expected_names = set(EXPECTED_EFFECTIVE_ENVIRONMENT)
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    value_mismatch = sorted(
        name
        for name in expected_names & actual_names
        if parsed_environment[name] != EXPECTED_EFFECTIVE_ENVIRONMENT[name]
    )
    if missing or extra or value_mismatch:
        # Report names and mismatch classes only.  Config.Env values are not
        # safe receipt material even when the current allowlist is public.
        raise DockerInspectError(
            "Config.Env does not match the deterministic allowlist; "
            f"missing={missing!r} extra={extra!r} "
            f"value_mismatch={value_mismatch!r}"
        )
    env_names = sorted(parsed_environment)

    raw_mounts = _docker_required_list(host, "Mounts", "HostConfig")
    mounts: list[dict[str, Any]] = []
    request_mount_keys = {
        "Type",
        "Source",
        "Target",
        "ReadOnly",
        "BindOptions",
    }
    request_bind_option_keys = {"Propagation"}
    for index, item in enumerate(raw_mounts):
        path = f"HostConfig.Mounts[{index}]"
        if not isinstance(item, dict):
            raise DockerInspectError(f"{path} must be an object")
        actual_keys = set(item)
        if actual_keys != request_mount_keys:
            missing = sorted(request_mount_keys - actual_keys)
            extra = sorted(actual_keys - request_mount_keys)
            raise DockerInspectError(
                f"{path} schema mismatch; missing={missing!r} extra={extra!r}"
            )
        bind_options = _docker_required_mapping(item, "BindOptions", path)
        actual_bind_option_keys = set(bind_options)
        if actual_bind_option_keys != request_bind_option_keys:
            missing = sorted(request_bind_option_keys - actual_bind_option_keys)
            extra = sorted(actual_bind_option_keys - request_bind_option_keys)
            raise DockerInspectError(
                f"{path}.BindOptions schema mismatch; "
                f"missing={missing!r} extra={extra!r}"
            )
        propagation = _docker_required_member(
            bind_options, "Propagation", f"{path}.BindOptions"
        )
        if not isinstance(propagation, str):
            raise DockerInspectError(
                f"{path}.BindOptions.Propagation must be a string"
            )
        mounts.append(
            {
                "type": _docker_required_member(item, "Type", path),
                # Retain the exact untrusted source.  It is compared without
                # normalization so traversal/case/alternate spellings cannot
                # collapse into the trusted host-resolved repository path.
                "source": _docker_required_member(item, "Source", path),
                "destination": _docker_required_member(item, "Target", path),
                # Preserve the untrusted JSON value verbatim.  In particular,
                # bool("false") must never become security evidence for true.
                "read_only": _docker_required_member(item, "ReadOnly", path),
                # Moby's mount.Mount.Consistency field is tagged omitempty.
                # The exact native default therefore has no Consistency
                # member.  The exact-key check above rejects both non-default
                # values and an unsupported explicit-empty representation.
                "consistency": "default",
                # The create plan requests this explicitly.  Binding the
                # request-side value prevents a propagation option from being
                # hidden behind the independently correct root Mounts report.
                "propagation": propagation,
            }
        )

    # HostConfig.Mounts is the requested mount declaration.  Docker's root
    # Mounts array is a separate report of the mount that will actually be
    # installed in the container.  Retain and bind both independently: request
    # equality alone cannot prove the effective source or writability.
    raw_effective_mounts = _docker_required_list(raw, "Mounts", "container")
    effective_mounts: list[dict[str, Any]] = []
    effective_mount_keys = {
        "Type",
        "Source",
        "Destination",
        "Mode",
        "RW",
        "Propagation",
    }
    for index, item in enumerate(raw_effective_mounts):
        path = f"container.Mounts[{index}]"
        if not isinstance(item, dict):
            raise DockerInspectError(f"{path} must be an object")
        actual_keys = set(item)
        if actual_keys != effective_mount_keys:
            missing = sorted(effective_mount_keys - actual_keys)
            extra = sorted(actual_keys - effective_mount_keys)
            raise DockerInspectError(
                f"{path} schema mismatch; missing={missing!r} extra={extra!r}"
            )
        effective_mounts.append(
            {
                "type": _docker_required_member(item, "Type", path),
                # Preserve the exact effective source spelling.  As with the
                # request-side source, it is never normalized and is redacted
                # to a digest if a mismatch must enter a receipt.
                "source": _docker_required_member(item, "Source", path),
                "destination": _docker_required_member(item, "Destination", path),
                "mode": _docker_required_member(item, "Mode", path),
                "read_write": _docker_required_member(item, "RW", path),
                "propagation": _docker_required_member(item, "Propagation", path),
            }
        )

    binds = _docker_required_list(host, "Binds", "HostConfig", allow_null=True)
    volumes = _docker_required_mapping(config, "Volumes", "Config", allow_null=True)
    devices = _docker_required_list(host, "Devices", "HostConfig", allow_null=True)
    device_requests = _docker_required_list(
        host, "DeviceRequests", "HostConfig", allow_null=True
    )
    port_bindings = _docker_required_mapping(
        host, "PortBindings", "HostConfig", allow_null=True
    )
    return {
        "container_id": raw.get("Id"),
        "image_id": raw.get("Image"),
        "image_tag": config.get("Image"),
        "process_path": raw.get("Path"),
        "process_args": raw.get("Args"),
        "user": config.get("User"),
        "working_dir": config.get("WorkingDir"),
        "entrypoint": config.get("Entrypoint"),
        "command": config.get("Cmd"),
        "hostname": config.get("Hostname"),
        # Config.Env was already matched to the exact allowlist.  Retain only
        # this one known non-secret value so the host can reconcile it to the
        # process observation without exposing general environment values.
        "environment_hostname": parsed_environment.get("HOSTNAME"),
        "environment_names": env_names,
        "readonly_rootfs": host.get("ReadonlyRootfs"),
        "network_disabled": config.get("NetworkDisabled"),
        "network_mode": host.get("NetworkMode"),
        "cap_drop": host.get("CapDrop"),
        "security_opt": host.get("SecurityOpt"),
        "nano_cpus": host.get("NanoCpus"),
        "memory_bytes": host.get("Memory"),
        "memory_swap_bytes": host.get("MemorySwap"),
        "pids_limit": host.get("PidsLimit"),
        "shm_size_bytes": host.get("ShmSize"),
        "tmpfs": host.get("Tmpfs"),
        "mounts": mounts,
        "effective_mounts": effective_mounts,
        "legacy_binds": len(binds),
        "image_volumes": sorted(volumes),
        "devices": len(devices),
        "device_requests": len(device_requests),
        "pid_mode": _docker_private_mode(host, "PidMode"),
        "ipc_mode": _docker_private_mode(host, "IpcMode"),
        "uts_mode": _docker_private_mode(host, "UTSMode"),
        "userns_mode": _docker_private_mode(host, "UsernsMode"),
        "port_bindings": len(port_bindings),
        "auto_remove": host.get("AutoRemove"),
        "oom_kill_disable": host.get("OomKillDisable"),
        "init_process": host.get("Init"),
        "publish_all_ports": host.get("PublishAllPorts"),
        "privileged": host.get("Privileged"),
        "readonly_paths": host.get("ReadonlyPaths"),
        "masked_paths": host.get("MaskedPaths"),
    }


def _assert_inspect(
    spec: dict[str, Any],
    expected_container_id: str,
    expected_image_id: str,
    expected_image_tag: str,
    expected_repository_source: str | None = None,
) -> None:
    if CONTAINER_ID_PATTERN.fullmatch(expected_container_id) is None:
        raise RuntimeError("invalid expected container id")
    if (
        not isinstance(expected_image_id, str)
        or IMAGE_ID_PATTERN.fullmatch(expected_image_id) is None
    ):
        raise RuntimeError("invalid expected image id")
    if (
        not isinstance(expected_image_tag, str)
        or IMAGE_TAG_PATTERN.fullmatch(expected_image_tag) is None
    ):
        raise RuntimeError("invalid expected image tag")
    repo_source = (
        intended_repository_source()
        if expected_repository_source is None
        else expected_repository_source
    )
    if not isinstance(repo_source, str) or not repo_source:
        raise RuntimeError("invalid expected repository mount source")
    expected = {
        "container_id": expected_container_id,
        "image_id": expected_image_id,
        "image_tag": expected_image_tag,
        "process_path": EXPECTED_PROCESS_PATH,
        "process_args": EXPECTED_PROCESS_ARGS,
        "user": "65532:65532",
        "working_dir": "/repo",
        "entrypoint": EXPECTED_ENTRYPOINT,
        "command": EXPECTED_COMMAND,
        "hostname": EXPECTED_HOSTNAME,
        "environment_hostname": EXPECTED_EFFECTIVE_ENVIRONMENT["HOSTNAME"],
        "environment_names": EXPECTED_ENVIRONMENT_NAMES,
        "readonly_rootfs": True,
        # Config.NetworkDisabled is Docker's legacy config bit.  The effective
        # network isolation is HostConfig.NetworkMode=none; both representations
        # are nevertheless required to retain their exact Docker boolean shape.
        "network_disabled": False,
        "network_mode": "none",
        "nano_cpus": 2_000_000_000,
        "memory_bytes": 4 * 1024 * 1024 * 1024,
        "memory_swap_bytes": 4 * 1024 * 1024 * 1024,
        "pids_limit": 256,
        "shm_size_bytes": 16 * 1024 * 1024,
        "legacy_binds": 0,
        "image_volumes": [],
        "devices": 0,
        "device_requests": 0,
        "pid_mode": "private",
        "ipc_mode": "private",
        "uts_mode": "private",
        "userns_mode": "private",
        "port_bindings": 0,
        "auto_remove": False,
        "oom_kill_disable": False,
        "init_process": False,
        "publish_all_ports": False,
        "privileged": False,
    }
    mismatches = {
        key: {"expected": value, "actual": spec.get(key)}
        for key, value in expected.items()
        if not _strict_json_equal(spec.get(key), value)
    }
    if sorted(spec.get("cap_drop") or []) != ["ALL"]:
        mismatches["cap_drop"] = {"expected": ["ALL"], "actual": spec.get("cap_drop")}
    security = [item.lower() for item in spec.get("security_opt") or []]
    if "no-new-privileges=true" not in security:
        mismatches["security_opt"] = {
            "expected_contains": "no-new-privileges=true",
            "actual": spec.get("security_opt"),
        }
    tmpfs = spec.get("tmpfs") or {}
    expected_tmp = {"rw", "noexec", "nosuid", "nodev", "size=268435456", "mode=1777"}
    actual_tmp = set((tmpfs.get("/tmp") or "").split(","))
    if actual_tmp != expected_tmp:
        mismatches["tmpfs"] = {
            "expected": {"/tmp": sorted(expected_tmp)},
            "actual": {"/tmp": sorted(actual_tmp)},
        }
    expected_mounts = [
        {
            "type": "bind",
            "source": repo_source,
            "destination": "/repo",
            "read_only": True,
            "consistency": "default",
            "propagation": EXPECTED_EFFECTIVE_MOUNT_PROPAGATION,
        }
    ]
    expected_effective_mounts = [
        {
            "type": "bind",
            "source": repo_source,
            "destination": "/repo",
            "mode": EXPECTED_EFFECTIVE_MOUNT_MODE,
            "read_write": False,
            "propagation": EXPECTED_EFFECTIVE_MOUNT_PROPAGATION,
        }
    ]

    def summarized_mounts(actual_mounts: Any) -> Any:
        if isinstance(actual_mounts, list):
            actual_summary: Any = []
            for mount in actual_mounts:
                if not isinstance(mount, dict):
                    actual_summary.append({"type": type(mount).__name__})
                    continue
                source = mount.get("source")
                actual_summary.append(
                    {
                        "type": mount.get("type"),
                        "source_type": type(source).__name__,
                        "source_sha256": (
                            sha256(source.encode("utf-8", errors="surrogatepass"))
                            if isinstance(source, str)
                            else None
                        ),
                        **{
                            key: mount.get(key)
                            for key in (
                                "destination",
                                "read_only",
                                "consistency",
                                "mode",
                                "read_write",
                                "propagation",
                            )
                            if key in mount
                        },
                    }
                )
        else:
            actual_summary = {"type": type(actual_mounts).__name__}
        return actual_summary

    if not _strict_json_equal(spec.get("mounts"), expected_mounts):
        actual_mounts = spec.get("mounts")
        mismatches["mounts"] = {
            "expected": [
                {
                    **expected_mounts[0],
                    "source": "intended-resolved-repository",
                    "source_sha256": sha256(repo_source.encode("utf-8")),
                }
            ],
            "actual": summarized_mounts(actual_mounts),
        }
    if not _strict_json_equal(
        spec.get("effective_mounts"), expected_effective_mounts
    ):
        actual_effective_mounts = spec.get("effective_mounts")
        mismatches["effective_mounts"] = {
            "expected": [
                {
                    **expected_effective_mounts[0],
                    "source": "intended-resolved-repository",
                    "source_sha256": sha256(repo_source.encode("utf-8")),
                }
            ],
            "actual": summarized_mounts(actual_effective_mounts),
        }
    if mismatches:
        raise RuntimeError(
            "effective Docker config mismatch: "
            + json.dumps(mismatches, sort_keys=True)
        )


def _reconcile_inner_environment(
    inner_receipt: dict[str, Any], effective_config: dict[str, Any]
) -> None:
    """Bind process-observed names and hostname to inspected Config.Env."""

    boundary = _require_object(inner_receipt.get("boundary"), "boundary")
    inner_names = _require_string_list(
        boundary.get("environment_names"), "boundary.environment_names"
    )
    effective_names = _require_string_list(
        effective_config.get("environment_names"),
        "effective_config.environment_names",
    )
    if not _strict_json_equal(inner_names, effective_names):
        raise _receipt_error(
            "boundary.environment_names",
            "must exactly equal inspected Config.Env names",
        )

    hostname_chain = {
        "kernel_nodename": boundary.get("hostname"),
        "process_environment": boundary.get("environment_hostname"),
        "config_hostname": effective_config.get("hostname"),
        "config_environment": effective_config.get("environment_hostname"),
        "pinned_environment": EXPECTED_EFFECTIVE_ENVIRONMENT["HOSTNAME"],
        "declared_plan": EXPECTED_HOSTNAME,
    }
    if any(
        not _strict_json_equal(value, EXPECTED_HOSTNAME)
        for value in hostname_chain.values()
    ):
        raise _receipt_error(
            "boundary.environment_hostname",
            "kernel, process environment, inspected config, and plan hostnames "
            "must all equal the declared sandbox hostname",
        )

    claimed_secret_names = _require_string_list(
        boundary.get("secret_like_environment_names"),
        "boundary.secret_like_environment_names",
    )
    recomputed_secret_names = _secret_like_environment_names(effective_names)
    if claimed_secret_names != recomputed_secret_names:
        raise _receipt_error(
            "boundary.secret_like_environment_names",
            "must equal secret-name classification of inspected Config.Env",
        )
    if claimed_secret_names:
        raise _receipt_error(
            "boundary.secret_like_environment_names", "must be empty"
        )


def _infra_receipt(
    detail: str,
    *,
    git_state: dict[str, Any],
    host: dict[str, Any],
    image: dict[str, Any],
    plan: dict[str, Any],
    probe: subprocess.CompletedProcess[bytes] | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema": "receiver-reliance/sandbox-host-receipt-1",
        "status": "INFRA_UNAVAILABLE",
        "treatment_exposed": True,
        "detail": detail,
        "git": git_state,
        "host": host,
        "image": image,
        "plan": plan,
    }
    if probe is not None:
        receipt["probe"] = {
            "exit_code": probe.returncode,
            "stdout_sha256": sha256(probe.stdout),
            "stderr_sha256": sha256(probe.stderr),
            "stderr": error_text(probe)[-2000:],
        }
    return receipt


def _emit(receipt: dict[str, Any], output: Path | None) -> None:
    encoded = canonical_bytes(receipt) + b"\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(encoded)
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def _cleanup_stream_evidence(value: Any) -> dict[str, Any]:
    """Describe captured cleanup output without trusting its Python shape."""

    if value is None:
        data = b""
    elif isinstance(value, bytes):
        data = value
    else:
        return {
            "valid_bytes": False,
            "python_type": type(value).__name__,
            "bytes": None,
            "sha256": None,
        }
    return {
        "valid_bytes": True,
        "python_type": "bytes",
        "bytes": len(data),
        "sha256": sha256(data),
    }


def _cleanup_exception_evidence(exc: Exception) -> dict[str, str]:
    try:
        detail = str(exc)
    except Exception:
        detail = "<exception text unavailable>"
    return {
        "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
        "detail": detail,
    }


def _cleanup_container(container_id: str | None) -> dict[str, Any]:
    """Attempt forced removal and turn every ordinary outcome into evidence."""

    if container_id is None:
        return {
            "status": "NOT_REQUIRED",
            "attempted": False,
            "container_id": None,
            "container_removed": False,
            "timeout_seconds": CLEANUP_TIMEOUT_SECONDS,
        }

    command = ["docker", "rm", "--force", container_id]
    cleanup: dict[str, Any] = {
        "status": "FAILURE",
        "attempted": True,
        "container_id": container_id,
        "container_removed": False,
        "timeout_seconds": CLEANUP_TIMEOUT_SECONDS,
        "command": command,
    }
    try:
        removed = run(command, timeout=CLEANUP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        cleanup.update(
            {
                "failure_kind": "TIMEOUT",
                "exception": _cleanup_exception_evidence(exc),
                "stdout": _cleanup_stream_evidence(exc.stdout),
                "stderr": _cleanup_stream_evidence(exc.stderr),
            }
        )
        return cleanup
    except OSError as exc:
        cleanup.update(
            {
                "failure_kind": "LAUNCH_FAILURE",
                "exception": _cleanup_exception_evidence(exc),
            }
        )
        return cleanup
    except Exception as exc:
        cleanup.update(
            {
                "failure_kind": "CALL_EXCEPTION",
                "exception": _cleanup_exception_evidence(exc),
            }
        )
        return cleanup

    if not isinstance(removed, subprocess.CompletedProcess):
        cleanup.update(
            {
                "failure_kind": "MALFORMED_RESULT",
                "result_type": type(removed).__name__,
            }
        )
        return cleanup

    stdout = _cleanup_stream_evidence(removed.stdout)
    stderr = _cleanup_stream_evidence(removed.stderr)
    cleanup.update(
        {
            "exit_code": (
                removed.returncode if type(removed.returncode) is int else None
            ),
            "stdout": stdout,
            "stderr": stderr,
        }
    )
    if (
        type(removed.returncode) is not int
        or not stdout["valid_bytes"]
        or not stderr["valid_bytes"]
    ):
        cleanup["failure_kind"] = "MALFORMED_RESULT"
        cleanup["returncode_type"] = type(removed.returncode).__name__
        return cleanup
    if removed.returncode != 0:
        cleanup["failure_kind"] = "NONZERO_EXIT"
        return cleanup

    cleanup["status"] = "SUCCESS"
    cleanup["container_removed"] = True
    return cleanup


def _plan(image: str) -> dict[str, Any]:
    repository_source = intended_repository_source()
    return {
        "schema": "receiver-reliance/sandbox-plan-1",
        "build": [
            "docker",
            "build",
            "--pull",
            "--network=none",
            "--file",
            str(DOCKERFILE),
            "--tag",
            image,
            str(HERE),
        ],
        "create": docker_create_args(image, repository_source),
        "expected_repository_mount": {
            "source": repository_source,
            "source_sha256": sha256(repository_source.encode("utf-8")),
            "destination": "/repo",
            "read_only": True,
            "comparison": MOUNT_SOURCE_COMPARISON,
            "host_os": platform.system(),
            "request": {
                "type": "bind",
                "target": "/repo",
                "read_only": True,
                "consistency": {
                    "mode": "default",
                    "inspect_member": "omitted",
                },
                "propagation": EXPECTED_EFFECTIVE_MOUNT_PROPAGATION,
            },
            "effective": {
                "type": "bind",
                "destination": "/repo",
                "mode": EXPECTED_EFFECTIVE_MOUNT_MODE,
                "read_write": False,
                "propagation": EXPECTED_EFFECTIVE_MOUNT_PROPAGATION,
            },
        },
        "expected_image": {
            "tag": image,
            "container_config_image": image,
            "container_root_image": "docker-image-inspect.Id",
        },
        "expected_execution": {
            "entrypoint": EXPECTED_ENTRYPOINT,
            "command": EXPECTED_COMMAND,
            "path": EXPECTED_PROCESS_PATH,
            "args": EXPECTED_PROCESS_ARGS,
        },
        "expected_hostname": {
            "config": EXPECTED_HOSTNAME,
            "environment": EXPECTED_EFFECTIVE_ENVIRONMENT["HOSTNAME"],
            "kernel_nodename": EXPECTED_HOSTNAME,
        },
        "expected_environment_names": EXPECTED_ENVIRONMENT_NAMES,
        "container_timeout_seconds": CONTAINER_TIMEOUT_SECONDS,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, help="also write canonical receipt JSON here")
    parser.add_argument(
        "--print-plan",
        action="store_true",
        help="print the exact build/create plan without invoking Docker",
    )
    args = parser.parse_args(argv)

    dockerfile_sha = sha256(DOCKERFILE.read_bytes())
    image = f"receiver-reliance-portability-sandbox:{dockerfile_sha[:12]}"
    plan = _plan(image)
    if args.print_plan:
        _emit(plan, args.receipt)
        return 0

    try:
        git_state = _git_receipt()
    except Exception as exc:
        receipt = {
            "schema": "receiver-reliance/sandbox-host-receipt-1",
            "status": "PREFLIGHT_FAILURE",
            "treatment_exposed": True,
            "detail": str(exc),
        }
        _emit(receipt, args.receipt)
        return 1
    host = _host_profile()
    image_identity = {"tag": image, "dockerfile_sha256": dockerfile_sha}

    try:
        probe = run(["docker", "version", "--format", "{{json .}}"], timeout=20)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        _emit(
            _infra_receipt(
                f"Docker CLI unavailable: {exc}",
                git_state=git_state,
                host=host,
                image=image_identity,
                plan=plan,
            ),
            args.receipt,
        )
        return 2
    if probe.returncode != 0:
        _emit(
            _infra_receipt(
                "Docker daemon unavailable",
                git_state=git_state,
                host=host,
                image=image_identity,
                plan=plan,
                probe=probe,
            ),
            args.receipt,
        )
        return 2
    try:
        docker_version = _parse_docker_version(probe.stdout)
    except DockerVersionError as exc:
        _emit(
            _infra_receipt(
                f"Docker version response was invalid: {exc}",
                git_state=git_state,
                host=host,
                image=image_identity,
                plan=plan,
                probe=probe,
            ),
            args.receipt,
        )
        return 2
    server = docker_version["Server"]
    server_os = server["Os"]
    if server_os.casefold() != "linux":
        _emit(
            _infra_receipt(
                f"Docker Linux server unavailable: Server.Os={server_os!r}",
                git_state=git_state,
                host=host,
                image=image_identity,
                plan=plan,
                probe=probe,
            ),
            args.receipt,
        )
        return 2

    if not git_state["clean"] or not git_state["baseline_ancestor"]:
        receipt = {
            "schema": "receiver-reliance/sandbox-host-receipt-1",
            "status": "PREFLIGHT_FAILURE",
            "treatment_exposed": True,
            "detail": "sandbox requires a clean checkout descended from the mandated baseline",
            "git": git_state,
        }
        _emit(receipt, args.receipt)
        return 1
    if git_state["branch"] and git_state["branch"] != EXPECTED_BRANCH:
        receipt = {
            "schema": "receiver-reliance/sandbox-host-receipt-1",
            "status": "PREFLIGHT_FAILURE",
            "treatment_exposed": True,
            "detail": f"unexpected branch {git_state['branch']!r}",
            "git": git_state,
        }
        _emit(receipt, args.receipt)
        return 1

    build_started = time.monotonic_ns()
    try:
        build = run(plan["build"], timeout=600)
    except subprocess.TimeoutExpired as exc:
        receipt = {
            "schema": "receiver-reliance/sandbox-host-receipt-1",
            "status": "SANDBOX_SETUP_FAILURE",
            "treatment_exposed": True,
            "git": git_state,
            "detail": "Docker image build timed out after 600 seconds",
            "build": {
                "stdout_sha256": sha256(exc.stdout or b""),
                "stderr_sha256": sha256(exc.stderr or b""),
            },
        }
        _emit(receipt, args.receipt)
        return 1
    build_elapsed_ms = round((time.monotonic_ns() - build_started) / 1_000_000)
    if build.returncode != 0:
        receipt = {
            "schema": "receiver-reliance/sandbox-host-receipt-1",
            "status": "SANDBOX_SETUP_FAILURE",
            "treatment_exposed": True,
            "git": git_state,
            "build": {
                "exit_code": build.returncode,
                "elapsed_ms": build_elapsed_ms,
                "stdout_sha256": sha256(build.stdout),
                "stderr_sha256": sha256(build.stderr),
                "stderr": error_text(build)[-4000:],
            },
        }
        _emit(receipt, args.receipt)
        return 1

    container_id: str | None = None
    receipt: dict[str, Any] = {
        "schema": "receiver-reliance/sandbox-host-receipt-1",
        "status": "STARTED",
        "treatment_exposed": True,
        "git": git_state,
        "host": host,
        "docker": {
            "client_version": docker_version["Client"].get("Version"),
            "client_os": docker_version["Client"].get("Os"),
            "client_arch": docker_version["Client"].get("Arch"),
            "server_version": docker_version["Server"].get("Version"),
            "server_os": docker_version["Server"].get("Os"),
            "server_arch": docker_version["Server"].get("Arch"),
        },
        "image": image_identity.copy(),
        "plan": plan,
        "build": {
            "exit_code": build.returncode,
            "elapsed_ms": build_elapsed_ms,
            "stdout_sha256": sha256(build.stdout),
            "stderr_sha256": sha256(build.stderr),
        },
    }
    exit_code = 1
    try:
        image_inspected = run(["docker", "image", "inspect", image], timeout=30)
        if image_inspected.returncode != 0:
            raise RuntimeError(
                "docker image inspect failed: " + error_text(image_inspected)[-2000:]
            )
        inspected_image = _validated_image_inspect(image_inspected.stdout, image)
        image_arch = inspected_image["architecture"]
        server_arch = docker_version["Server"].get("Arch")
        receipt["image"].update(
            {
                "id": inspected_image["id"],
                "os": inspected_image["os"],
                "architecture": image_arch,
                "native_vs_emulated": (
                    "native" if image_arch == server_arch else "emulated_or_cross_platform"
                ),
            }
        )
        created = run(plan["create"], timeout=60)
        if created.returncode != 0:
            raise RuntimeError("docker create failed: " + error_text(created)[-2000:])
        created_container_id = _created_container_id(created.stdout)
        container_id = created_container_id

        inspected = run(["docker", "inspect", container_id], timeout=30)
        if inspected.returncode != 0:
            raise RuntimeError("docker inspect failed: " + error_text(inspected)[-2000:])
        raw_inspect = _parse_docker_inspect(
            inspected.stdout, "Docker container inspect response"
        )
        effective = _selected_inspect(raw_inspect)
        _assert_inspect(
            effective,
            container_id,
            inspected_image["id"],
            image,
            plan["expected_repository_mount"]["source"],
        )
        receipt["effective_config"] = effective

        started_ns = time.monotonic_ns()
        try:
            started = run(
                ["docker", "start", "--attach", container_id],
                timeout=CONTAINER_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            receipt["status"] = "SANDBOX_TIMEOUT"
            receipt["container"] = {
                "timeout_seconds": CONTAINER_TIMEOUT_SECONDS,
                "stdout_sha256": sha256(exc.stdout or b""),
                "stderr_sha256": sha256(exc.stderr or b""),
            }
            exit_code = 1
        else:
            elapsed_ms = round((time.monotonic_ns() - started_ns) / 1_000_000)
            receipt["container"] = {
                "exit_code": started.returncode,
                "elapsed_ms": elapsed_ms,
                "stdout_sha256": sha256(started.stdout),
                "stdout_bytes": len(started.stdout),
                "stderr_sha256": sha256(started.stderr),
                "stderr_bytes": len(started.stderr),
            }
            try:
                inner = validate_container_pass(started)
                _reconcile_inner_environment(inner, effective)
            except InnerReceiptError as exc:
                receipt["status"] = "INVALID_CONTAINER_RECEIPT"
                receipt["detail"] = str(exc)
                receipt["container"]["stdout"] = started.stdout.decode(
                    "utf-8", errors="replace"
                )[-8000:]
                receipt["container"]["stderr"] = started.stderr.decode(
                    "utf-8", errors="replace"
                )[-8000:]
                exit_code = 1
            else:
                receipt["inner_receipt"] = inner
                receipt["status"] = "PASS"
                exit_code = 0
    except Exception as exc:
        receipt["status"] = "SANDBOX_SETUP_FAILURE"
        receipt["detail"] = str(exc)
        exit_code = 1
    finally:
        primary_status = receipt["status"]
        primary_exit_code = exit_code
        cleanup = _cleanup_container(container_id)
        cleanup["primary_status"] = primary_status
        cleanup["primary_exit_code"] = primary_exit_code
        receipt["cleanup"] = cleanup
        if cleanup["status"] == "FAILURE" and primary_exit_code == 0:
            receipt["status"] = "CLEANUP_FAILURE"
            receipt["detail"] = (
                "forced container cleanup failed after primary PASS: "
                + str(cleanup["failure_kind"])
            )
            exit_code = 1

    _emit(receipt, args.receipt)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
