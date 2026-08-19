"""Deterministic, stdlib-only runner and receipt writer for portability CI.

The checked-in plan is the sole matrix/command input.  Normative divergence
returns nonzero.  ``INFRA_UNAVAILABLE`` is accepted only with durable evidence
of a predeclared runner absence or an observed setup/runtime-build failure.
Missing or ambiguous receipts from runnable normative rows fail closed.
"""

from __future__ import annotations

import argparse
import codecs
import ctypes
import decimal
import hashlib
import json
import locale
import math
import ntpath
import os
import pathlib
import platform
import posixpath
import re
import shutil
import struct
import subprocess
import sys
import sysconfig
import tempfile
import time
from typing import Any


SCHEMA = "rr.portability.matrix-receipt.v1"
SUMMARY_SCHEMA = "rr.portability.matrix-summary.v1"
HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_PLAN = HERE / "plan.json"
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT / "portability") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "portability"))

# Ambient tool resolution is the trust root for every provenance claim this
# file makes: a PATH- or current-directory-prepositioned `git` (or `docker`)
# can forge the clean status and HEAD that authorize the evidence, and a
# verification lane demonstrated exactly that (TRUST_MODEL.md).
# portability/pinned_tools.py was landed to close it and then adopted nowhere,
# which left a control outside the decision path. With RR_TOOL_DIR unset
# resolve() returns the bare name, so the argv is byte-identical to before and
# no receipt digest moves; with it set, tools resolve inside a directory an
# unprivileged process cannot write and never fall back to PATH.
import pinned_tools  # noqa: E402
import strict_ingest  # noqa: E402  (ADOPTION A4: the one shared ingest law)
SAFE_ENV_KEYS = (
    "CI",
    "COMSPEC",
    "GITHUB_ACTIONS",
    "LANG",
    "LC_ALL",
    "PATH",
    "PATHEXT",
    "RUNNER_ARCH",
    "RUNNER_OS",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "WINDIR",
)
BUILD_FLAG_NAMES = (
    "CONFIG_ARGS",
    "Py_DEBUG",
    "Py_GIL_DISABLED",
    "WITH_DOC_STRINGS",
    "WITH_DTRACE",
    "WITH_MIMALLOC",
    "WITH_PYMALLOC",
    "WITH_VALGRIND",
)
INFRA_PROOF_KINDS = frozenset(
    {
        "predeclared_runner_unavailable",
        "runtime_setup_unavailable",
        "runtime_build_unavailable",
    }
)
COUNT_FIELDS = (
    "count_totals",
    "checks",
    "failures",
    "findings",
    "tests",
    "case_progress",
)
COMMAND_FIELDS = frozenset(
    {
        "id",
        "argv",
        "cwd",
        "timeout_seconds",
        "timed_out",
        "exit",
        "elapsed_seconds",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_bytes",
        "stderr_bytes",
        "suite_counts",
        "expected_counts",
        "expectation_mismatches",
        "resources",
    }
)
RELEASELEVEL_TAGS = {
    "alpha": "a",
    "beta": "b",
    "candidate": "rc",
    "final": "",
}

# Receipt JSON crosses a hosted-artifact trust boundary.  Keep every numeric
# field within an explicitly finite domain before it participates in float
# conversion, formatting, arithmetic, or aggregation.  The general integer
# ceiling is intentionally below common signed 64-bit storage limits; the
# narrower ceilings describe fields whose real producer is already bounded.
MAX_RECEIPT_INTEGER = (1 << 63) - 1
MAX_RECEIPT_SECONDS = 365 * 24 * 60 * 60
MAX_TIMER_OVERRUN_SECONDS = 300
MAX_VERSION_COMPONENT = 999_999
MAX_LOGICAL_CPU_COUNT = 1_000_000
MAX_WORD_SIZE_BITS = 4096
MIN_PROCESS_EXIT = -(1 << 31)
MAX_PROCESS_EXIT = (1 << 32) - 1
MAX_JSON_NUMBER_LEXEME = 256
MAX_JSON_EXPONENT = 1_000_000
MAX_JSON_INPUT_BYTES = 16 * 1024 * 1024
MAX_JSON_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_JSON_NESTING_DEPTH = 64
# Nesting alone is not a resource bound.  A wide, shallow document well under the
# byte cap decodes fully before any exact-shape validation runs, and relying on
# MemoryError to stop it is not a bound at all once allocation pressure is severe
# (csf_92622f9b).  This caps structural nodes -- container members and array
# items -- counted lexically in the same finite-state pass as nesting.  The
# ceiling is far above any real receipt: the largest committed hosted receipt has
# well under ten thousand.
MAX_JSON_STRUCTURAL_NODES = 1_000_000


def _parse_json_integer(value: str) -> int:
    """Parse a JSON integer without erasing a negative-zero spelling."""

    if value == "-0":
        raise ValueError("negative-zero JSON integers are not permitted")
    if len(value) > MAX_JSON_NUMBER_LEXEME:
        raise ValueError("JSON integer lexeme exceeds the finite parser domain")
    return int(value)


def _parse_json_decimal(value: str) -> decimal.Decimal:
    """Parse a JSON fractional/exponent number without binary rounding.

    Downloaded receipts are hostile.  In particular, converting ``-1e-324``
    to binary64 erases both its magnitude and the evidence-significant fact
    that it was negative.  Decimal retains that lexical meaning while the
    explicit exponent/lexeme limits keep decoding total over a finite domain.
    """

    if len(value) > MAX_JSON_NUMBER_LEXEME:
        raise ValueError("JSON decimal lexeme exceeds the finite parser domain")
    exponent_match = re.search(r"[eE]([+-]?)(\d+)$", value)
    if exponent_match is not None:
        exponent_digits = exponent_match.group(2).lstrip("0") or "0"
        ceiling = str(MAX_JSON_EXPONENT)
        if len(exponent_digits) > len(ceiling) or (
            len(exponent_digits) == len(ceiling) and exponent_digits > ceiling
        ):
            raise ValueError("JSON decimal exponent exceeds the finite parser domain")
    try:
        parsed = decimal.Decimal(value)
    except decimal.InvalidOperation as exc:
        raise ValueError("invalid JSON decimal") from exc
    if not parsed.is_finite():
        raise ValueError("non-finite JSON decimal is not permitted")
    if parsed.is_zero() and parsed.is_signed():
        raise ValueError("negative-zero JSON decimals are not permitted")
    return parsed


def _preflight_json_structure(text: str) -> None:
    """Bound JSON structure before the recursive stdlib decoder sees it.

    The scan is lexical rather than semantic: the decoder still owns JSON
    grammar, while this finite-state pass ignores delimiters inside strings,
    rejects mismatched delimiters, and caps structural nesting without using
    the Python call stack.
    """

    delimiters: list[str] = []
    in_string = False
    escaped = False
    nodes = 0
    pairs = {"}": "{", "]": "["}
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "{[":
            delimiters.append(character)
            nodes += 1
            if len(delimiters) > MAX_JSON_NESTING_DEPTH:
                raise ValueError(
                    "JSON structural nesting exceeds the finite parser domain "
                    f"of {MAX_JSON_NESTING_DEPTH}"
                )
        elif character in "}]":
            if not delimiters or delimiters[-1] != pairs[character]:
                raise ValueError("JSON structural delimiters are mismatched")
            delimiters.pop()
        elif character in ",:":
            nodes += 1
        if nodes > MAX_JSON_STRUCTURAL_NODES:
            raise ValueError(
                "JSON structural node count exceeds the finite parser domain "
                f"of {MAX_JSON_STRUCTURAL_NODES}"
            )
    if in_string:
        raise ValueError("JSON document contains an unterminated string")
    if delimiters:
        raise ValueError("JSON document contains unclosed structural delimiters")


def _json_load(path: pathlib.Path) -> dict[str, Any]:
    # ADOPTION A4: parsing goes through the one shared safety law.  Matrix
    # plans and downloaded hosted receipts both reach this decoder, and the
    # implementation treats hosted artifacts as hostile: default decoding
    # would erase the first of two conflicting ``entry_id``, ``outcome``,
    # ``git``, ``environment`` or ``status`` members before any closed-shape,
    # identity or binding check saw them (csf_3df8c8b0).  strict_ingest
    # rejects the duplicate deterministically; IngestError is a ValueError.
    # Kept local, deliberately: the byte-size admission (this verifier's own
    # finite input domain), the lexical structure preflight (bounds nesting
    # BEFORE the recursive decoder allocates), and Decimal numeric fidelity
    # (passed through load_safe, affecting values only, never acceptance).
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_JSON_INPUT_BYTES + 1)
        if len(raw) > MAX_JSON_INPUT_BYTES:
            raise ValueError(
                "JSON document exceeds the finite input domain of "
                f"{MAX_JSON_INPUT_BYTES} bytes"
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("JSON document is not valid UTF-8") from exc
        _preflight_json_structure(text)
        value = strict_ingest.load_safe(
            raw,
            label="JSON document",
            parse_float=_parse_json_decimal,
            parse_int=_parse_json_integer,
        )
    except (MemoryError, RecursionError) as exc:
        raise ValueError(
            f"JSON processing exceeded its finite resource boundary ({type(exc).__name__})"
        ) from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _normative_entries(plan: dict[str, Any]) -> list[dict[str, Any]]:
    spec = plan["normative"]
    entries: list[dict[str, Any]] = []
    for version in spec["python_versions"]:
        for raw_platform in spec["platforms"]:
            item = dict(raw_platform)
            item.update(
                {
                    "id": (
                        f"normative-cpython-{_slug(version)}-"
                        f"{_slug(item['runner'])}-{_slug(item['architecture'])}"
                    ),
                    "classification": spec["classification"],
                    "claim_scope": spec["claim_scope"],
                    "role": spec["role"],
                    "runtime": "CPython",
                    "implementation": "CPython",
                    "python_version": version,
                    "profile": "focused",
                }
            )
            entries.append(item)
    return entries


def all_entries(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return _normative_entries(plan) + list(plan["stress"]) + [plan["expanded_gate"]]


def find_entry(plan: dict[str, Any], entry_id: str) -> dict[str, Any]:
    matches = [entry for entry in all_entries(plan) if entry["id"] == entry_id]
    if len(matches) != 1:
        raise ValueError(f"entry {entry_id!r} resolved {len(matches)} times")
    return matches[0]


def profile_commands(plan: dict[str, Any], profile: str) -> list[dict[str, Any]]:
    profiles = plan["profiles"]
    if profile == "focused":
        return list(profiles["portability_checks"]) + list(
            profiles["baseline_nonperformance"]
        )
    if profile == "expanded":
        return list(profiles["baseline_nonperformance"]) + list(
            profiles["expanded_extra"]
        )
    if profile == "free_threaded":
        return (
            list(profiles["portability_checks"])
            + list(profiles["baseline_nonperformance"])
            + list(profiles["free_threaded_extra"])
        )
    raise ValueError(f"unknown profile: {profile}")


def matrix_rows(plan: dict[str, Any], role: str) -> list[dict[str, Any]]:
    if role == "normative_matrix":
        entries = _normative_entries(plan)
    elif role == "stress_matrix":
        entries = list(plan["stress"])
    else:
        raise ValueError(f"unknown matrix role: {role}")
    rows = []
    for entry in entries:
        if not entry.get("runnable", True):
            continue
        rows.append(
            {
                "id": entry["id"],
                "classification": entry["classification"],
                "claim_scope": entry["claim_scope"],
                "runner": entry["runner"],
                "architecture": entry["architecture"],
                "setup_architecture": entry["setup_architecture"],
                "python_version": entry["python_version"],
                "python_dev_mode": bool(entry.get("python_dev_mode", False)),
            }
        )
    return rows


def _normalize_arch(value: str) -> str:
    folded = value.strip().lower().replace("_", "-")
    if folded in {"amd64", "x86-64", "x64"}:
        return "x64"
    if folded in {"aarch64", "arm64"}:
        return "arm64"
    if folded in {"x86", "i386", "i686"}:
        return "x86"
    return folded or "unknown"


def _darwin_translated() -> bool | None:
    if platform.system() != "Darwin":
        return None
    try:
        libc = ctypes.CDLL(None)
        value = ctypes.c_int(0)
        size = ctypes.c_size_t(ctypes.sizeof(value))
        name = ctypes.c_char_p(b"sysctl.proc_translated")
        result = libc.sysctlbyname(name, ctypes.byref(value), ctypes.byref(size), None, 0)
        if result != 0:
            return None
        return bool(value.value)
    except (AttributeError, OSError):
        return None


def _execution_arch(expected: str) -> dict[str, Any]:
    machine = _normalize_arch(platform.machine())
    translated = _darwin_translated()
    windows_wow = bool(os.environ.get("PROCESSOR_ARCHITEW6432"))
    if translated or windows_wow:
        mode = "emulated"
    elif machine == _normalize_arch(expected):
        mode = "native"
    else:
        mode = "emulated_or_mismatch"
    return {
        "requested": _normalize_arch(expected),
        "machine": machine,
        "mode": mode,
        "darwin_rosetta": translated,
        "windows_wow64": windows_wow,
    }


def _physical_memory_bytes() -> int | None:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        try:
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.total_physical)
        except (AttributeError, OSError):
            return None
        return None
    try:
        return int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
    except (AttributeError, OSError, ValueError):
        return None


def _resource_snapshot() -> dict[str, float | int | None]:
    times = os.times()
    snapshot: dict[str, float | int | None] = {
        "children_user_seconds": float(times.children_user),
        "children_system_seconds": float(times.children_system),
        "max_rss_kib": None,
    }
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        max_rss = float(usage.ru_maxrss)
        if platform.system() == "Darwin":
            max_rss /= 1024.0
        snapshot["max_rss_kib"] = int(max_rss)
    except (ImportError, OSError, ValueError):
        pass
    return snapshot


def _resource_delta(
    before: dict[str, float | int | None], after: dict[str, float | int | None]
) -> dict[str, float | int | None]:
    return {
        "children_user_seconds": round(
            float(after["children_user_seconds"]) - float(before["children_user_seconds"]), 6
        ),
        "children_system_seconds": round(
            float(after["children_system_seconds"])
            - float(before["children_system_seconds"]),
            6,
        ),
        "max_rss_kib": after["max_rss_kib"],
    }


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [pinned_tools.git(), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def git_receipt() -> dict[str, Any]:
    sha = _git(["rev-parse", "HEAD"])
    status = _git(["status", "--porcelain=v1", "--untracked-files=all"])
    if sha.returncode != 0 or status.returncode != 0:
        return {
            "sha": None,
            "github_sha": os.environ.get("GITHUB_SHA"),
            "clean": None,
            "error": (sha.stderr + status.stderr).strip(),
        }
    raw_status = status.stdout.encode("utf-8")
    return {
        "sha": sha.stdout.strip(),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "clean": not bool(status.stdout),
        "status_sha256": hashlib.sha256(raw_status).hexdigest(),
        "status_line_count": len(status.stdout.splitlines()),
    }


def environment_receipt(entry: dict[str, Any]) -> dict[str, Any]:
    gil_probe = getattr(sys, "_is_gil_enabled", None)
    build_flags = {name: sysconfig.get_config_var(name) for name in BUILD_FLAG_NAMES}
    try:
        locale_name = locale.setlocale(locale.LC_ALL, None)
    except locale.Error as exc:
        locale_name = f"UNAVAILABLE: {exc}"
    uname = platform.uname()
    disk = shutil.disk_usage(REPO_ROOT)
    return {
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "kernel_version": platform.version(),
            "uname": list(uname),
        },
        "architecture": _execution_arch(entry["architecture"]),
        "runtime": {
            "implementation": platform.python_implementation(),
            "full_version": sys.version,
            "version_info": list(sys.version_info),
            "setup_python_version": os.environ.get("RR_SETUP_PYTHON_VERSION"),
            "executable": sys.executable,
            "build": list(platform.python_build()),
            "compiler": platform.python_compiler(),
            "build_flags": build_flags,
            "gil_enabled": gil_probe() if callable(gil_probe) else None,
            "dev_mode": bool(sys.flags.dev_mode),
        },
        "abi": {
            "word_size_bits": struct.calcsize("P") * 8,
            "byte_order": sys.byteorder,
        },
        "encoding": {
            "locale": locale_name,
            "preferred": locale.getpreferredencoding(False),
            "filesystem": sys.getfilesystemencoding(),
            "filesystem_errors": sys.getfilesystemencodeerrors(),
            "default": sys.getdefaultencoding(),
            "stdout": sys.stdout.encoding,
            "stderr": sys.stderr.encoding,
        },
        "resources": {
            "logical_cpu_count": os.cpu_count(),
            "physical_memory_bytes": _physical_memory_bytes(),
            "disk_total_bytes": disk.total,
            "disk_free_bytes": disk.free,
        },
    }


def planned_commands(plan: dict[str, Any], entry: dict[str, Any]) -> list[dict[str, Any]]:
    # Keep the checked-in command templates as the stable receipt identity.
    # Executed command records carry the platform-specific interpreter and
    # temporary paths.  Expanding those values here would make receipts from
    # Windows/macOS impossible to validate in the Linux summary job.
    return [dict(spec) for spec in profile_commands(plan, entry["profile"])]


def _base_receipt(plan: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "entry_id": entry["id"],
        "classification": entry["classification"],
        "claim_scope": entry["claim_scope"],
        "role": entry["role"],
        "requested": {
            key: entry.get(key)
            for key in (
                "runner",
                "os_family",
                "architecture",
                "setup_architecture",
                "runtime",
                "implementation",
                "python_version",
                "distribution_release",
                "python_language_version",
                "profile",
                "required_capability",
                "language_floor",
                "non_substitute_for",
            )
        },
        "git": git_receipt(),
        "environment": environment_receipt(entry),
        "commands_planned": planned_commands(plan, entry),
        "commands": [],
        "suite_counts": [],
        "outcome": None,
        "reason": None,
        "infra_proof": None,
    }


def _infra_proof(kind: str, producer: str, evidence: str) -> dict[str, str]:
    if kind not in INFRA_PROOF_KINDS:
        raise ValueError(f"unsupported infrastructure proof kind: {kind}")
    if not producer.strip() or not evidence.strip():
        raise ValueError("infrastructure proof requires producer and evidence")
    return {"kind": kind, "producer": producer, "evidence": evidence}


def _capability_unavailable(
    plan: dict[str, Any], entry: dict[str, Any], receipt: dict[str, Any]
) -> str | None:
    return _environment_binding_error(
        receipt["environment"], entry, plan.get("environment_requirements")
    )


def _sanitized_environment(entry: dict[str, Any]) -> dict[str, str]:
    child = {key: os.environ[key] for key in SAFE_ENV_KEYS if key in os.environ}
    child.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "TZ": "UTC",
        }
    )
    if entry.get("python_dev_mode"):
        child["PYTHONDEVMODE"] = "1"
    return child


def _expand_argument(value: str, entry: dict[str, Any] | None = None) -> str:
    if value == "{python}":
        return sys.executable
    temporary = os.environ.get("RUNNER_TEMP", tempfile.gettempdir())
    expanded = value.replace("{temp}", temporary)
    if "{entry_id}" in expanded:
        if entry is None or "id" not in entry:
            raise ValueError("{entry_id} requires an entry with an id")
        expanded = expanded.replace("{entry_id}", entry["id"])
    return expanded


def parse_suite_counts(stdout: bytes, stderr: bytes) -> dict[str, Any]:
    # Replacement decoding keeps this function total over arbitrary child output,
    # but a line that needed replacement is not evidence: U+FFFD means the bytes
    # were not what the suite claims to have printed, and such a line could still
    # match a count pattern and contribute to an expected total (csf_95727c25).
    # Those lines are dropped, so they read as absent output rather than as
    # authorization.  The drop is deliberately not reported in the return value:
    # this dict IS the receipt's suite_counts shape, validated field-for-field by
    # _suite_counts_validation_error against every committed receipt, so adding a
    # key here would move every one of them.
    text = (stdout + b"\n" + stderr).decode("utf-8", "replace")
    text = "\n".join(line for line in text.splitlines() if "�" not in line)
    count_totals = []
    for match in re.finditer(r"counts=(\{[^\r\n]+?\})(?=\s+[a-z_]+=|\s*$)", text):
        try:
            # Duplicate count names must not collapse into an expected total
            # (ADOPTION A4: the shared law owns the rejection).
            value = strict_ingest.load_safe(match.group(1).encode("utf-8"))
        except ValueError:
            continue
        if isinstance(value, dict) and all(
            _is_nonnegative_integer(item) for item in value.values()
        ):
            count_totals.append(sum(value.values()))

    def bounded_matches(pattern: str) -> list[int]:
        values = []
        for raw in re.findall(pattern, text):
            parsed = _bounded_decimal(raw, MAX_RECEIPT_INTEGER)
            # Preserve an explicit, serializable out-of-domain marker so a
            # hostile subprocess line cannot crash receipt production and
            # cannot be mistaken for absent evidence.
            values.append(
                parsed if parsed is not None else MAX_RECEIPT_INTEGER + 1
            )
        return values

    return {
        "count_totals": count_totals,
        "checks": bounded_matches(r"\bchecks=(\d+)"),
        "failures": bounded_matches(r"\bfailures=(\d+)"),
        "findings": bounded_matches(r"\blint:\s*(\d+) findings\b"),
        "tests": bounded_matches(r"\bRan\s+(\d+)\s+tests?\b"),
        "case_progress": [
            [
                _bounded_decimal(done, MAX_RECEIPT_INTEGER)
                if _bounded_decimal(done, MAX_RECEIPT_INTEGER) is not None
                else MAX_RECEIPT_INTEGER + 1,
                _bounded_decimal(total, MAX_RECEIPT_INTEGER)
                if _bounded_decimal(total, MAX_RECEIPT_INTEGER) is not None
                else MAX_RECEIPT_INTEGER + 1,
            ]
            for done, total in re.findall(r"\bcases=(\d+)/(\d+)\b", text)
        ],
    }


def _expectation_mismatches(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    mismatches = []
    for metric, wanted in expected.items():
        observed = actual.get(metric)
        if observed != wanted:
            mismatches.append(f"{metric}: expected {wanted!r}, observed {observed!r}")
    return mismatches


def _run_command(spec: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    argv = [_expand_argument(value, entry) for value in spec["argv"]]
    cwd = (REPO_ROOT / spec["cwd"]).resolve()
    before = _resource_snapshot()
    started = time.monotonic_ns()
    timed_out = False
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=_sanitized_environment(entry),
            capture_output=True,
            check=False,
            timeout=spec["timeout_seconds"],
        )
        exit_code: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
    elapsed = (time.monotonic_ns() - started) / 1_000_000_000
    after = _resource_snapshot()
    counts = parse_suite_counts(stdout, stderr)
    mismatches = _expectation_mismatches(spec.get("expected", {}), counts)

    print(f"::group::{spec['id']}", flush=True)
    if stdout:
        sys.stdout.buffer.write(stdout)
        if not stdout.endswith(b"\n"):
            sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
    if stderr:
        sys.stderr.buffer.write(stderr)
        if not stderr.endswith(b"\n"):
            sys.stderr.buffer.write(b"\n")
        sys.stderr.buffer.flush()
    print(f"::endgroup::{spec['id']}", flush=True)
    return {
        "id": spec["id"],
        "argv": argv,
        "cwd": spec["cwd"],
        "timeout_seconds": spec["timeout_seconds"],
        "timed_out": timed_out,
        "exit": exit_code,
        "elapsed_seconds": round(elapsed, 6),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
        "suite_counts": counts,
        "expected_counts": spec.get("expected", {}),
        "expectation_mismatches": mismatches,
        "resources": _resource_delta(before, after),
    }


def _output_path(name: str) -> pathlib.Path:
    if pathlib.Path(name).name != name:
        raise ValueError("--output-name must be a file name, not a path")
    root = pathlib.Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    root.mkdir(parents=True, exist_ok=True)
    return root / name


def _decimal_json_lexeme(value: decimal.Decimal) -> str:
    """Return one deterministic JSON-number spelling for an exact Decimal."""

    if not value.is_finite():
        raise ValueError("non-finite decimals cannot be written as JSON")
    if value.is_zero():
        if value.is_signed():
            raise ValueError("negative zero cannot be written as canonical JSON")
        return "0"
    sign, raw_digits, exponent = value.as_tuple()
    digits = list(raw_digits)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exponent += 1
    coefficient = "".join(str(item) for item in digits)
    point = len(coefficient) + exponent
    if -6 <= point <= 21:
        if point <= 0:
            body = "0." + ("0" * -point) + coefficient
        elif point >= len(coefficient):
            body = coefficient + ("0" * (point - len(coefficient)))
        else:
            body = coefficient[:point] + "." + coefficient[point:]
    else:
        fraction = ("." + coefficient[1:]) if len(coefficient) > 1 else ""
        body = f"{coefficient[0]}{fraction}e{point - 1}"
    return ("-" if sign else "") + body


def _canonical_json_chunks(value: Any):
    """Yield deterministic JSON without traversing containers recursively."""

    stack: list[tuple[str, Any, int]] = [("value", value, 0)]
    active_containers: set[int] = set()
    while stack:
        operation, item, level = stack.pop()
        if operation == "text":
            yield item
            continue
        if operation == "leave":
            active_containers.remove(item)
            continue

        if isinstance(item, dict):
            if not all(isinstance(key, str) for key in item):
                raise TypeError("JSON object keys must be strings")
            structural_depth = level + 1
            if structural_depth > MAX_JSON_NESTING_DEPTH:
                raise ValueError(
                    "JSON structural nesting exceeds the finite writer domain "
                    f"of {MAX_JSON_NESTING_DEPTH}"
                )
            identity = id(item)
            if identity in active_containers:
                raise ValueError("cyclic containers cannot be written as JSON")
            if not item:
                yield "{}"
                continue
            active_containers.add(identity)
            indent = "  " * level
            child_indent = "  " * (level + 1)
            operations: list[tuple[str, Any, int]] = [("text", "{\n", 0)]
            for index, key in enumerate(sorted(item)):
                if index:
                    operations.append(("text", ",\n", 0))
                operations.append(
                    ("text", f"{child_indent}{json.dumps(key)}: ", 0)
                )
                operations.append(("value", item[key], level + 1))
            operations.extend(
                [
                    ("text", f"\n{indent}}}", 0),
                    ("leave", identity, 0),
                ]
            )
            stack.extend(reversed(operations))
            continue

        if isinstance(item, (list, tuple)):
            structural_depth = level + 1
            if structural_depth > MAX_JSON_NESTING_DEPTH:
                raise ValueError(
                    "JSON structural nesting exceeds the finite writer domain "
                    f"of {MAX_JSON_NESTING_DEPTH}"
                )
            identity = id(item)
            if identity in active_containers:
                raise ValueError("cyclic containers cannot be written as JSON")
            if not item:
                yield "[]"
                continue
            active_containers.add(identity)
            indent = "  " * level
            child_indent = "  " * (level + 1)
            operations = [("text", "[\n", 0)]
            for index, child in enumerate(item):
                if index:
                    operations.append(("text", ",\n", 0))
                operations.append(("text", child_indent, 0))
                operations.append(("value", child, level + 1))
            operations.extend(
                [
                    ("text", f"\n{indent}]", 0),
                    ("leave", identity, 0),
                ]
            )
            stack.extend(reversed(operations))
            continue

        if isinstance(item, decimal.Decimal):
            yield _decimal_json_lexeme(item)
            continue
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("non-finite floats cannot be written as JSON")
            if item == 0.0 and math.copysign(1.0, item) < 0:
                raise ValueError("negative zero cannot be written as canonical JSON")
        if _is_integer(item) and not _is_bounded_integer(
            item, -MAX_RECEIPT_INTEGER, MAX_RECEIPT_INTEGER
        ):
            raise ValueError("integer exceeds the finite writer domain")
        yield json.dumps(item, allow_nan=False)


def _canonical_json(value: Any, level: int = 0) -> str:
    """Encode the receipt tree, including exact Decimal values, deterministically."""

    if level != 0:
        raise ValueError("canonical JSON encoding must begin at the root")
    encoded = "".join(_canonical_json_chunks(value))
    if len(encoded.encode("utf-8")) > MAX_JSON_OUTPUT_BYTES:
        raise ValueError(
            "JSON document exceeds the finite output domain of "
            f"{MAX_JSON_OUTPUT_BYTES} bytes"
        )
    return encoded


def _write_json(path: pathlib.Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    total = 0
    try:
        with temporary.open("wb") as handle:
            for chunk in _canonical_json_chunks(value):
                encoded = chunk.encode("utf-8")
                total += len(encoded)
                if total > MAX_JSON_OUTPUT_BYTES:
                    raise ValueError(
                        "JSON document exceeds the finite output domain of "
                        f"{MAX_JSON_OUTPUT_BYTES} bytes"
                    )
                handle.write(encoded)
            if total + 1 > MAX_JSON_OUTPUT_BYTES:
                raise ValueError(
                    "JSON document exceeds the finite output domain of "
                    f"{MAX_JSON_OUTPUT_BYTES} bytes"
                )
            handle.write(b"\n")
        temporary.replace(path)
    except (MemoryError, RecursionError) as exc:
        temporary.unlink(missing_ok=True)
        raise ValueError(
            f"JSON writing exceeded its finite resource boundary ({type(exc).__name__})"
        ) from exc
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    print(f"receipt_path={path}")


def run_entry(plan: dict[str, Any], entry: dict[str, Any], output: pathlib.Path) -> int:
    receipt = _base_receipt(plan, entry)
    unavailable = _capability_unavailable(plan, entry, receipt)
    if unavailable:
        receipt["outcome"] = "INFRA_UNAVAILABLE"
        receipt["reason"] = unavailable
        receipt["infra_proof"] = _infra_proof(
            "runtime_build_unavailable",
            "portability/matrix/receipt.py:runtime-probe",
            unavailable,
        )
        _write_json(output, receipt)
        return 0

    for spec in profile_commands(plan, entry["profile"]):
        result = _run_command(spec, entry)
        receipt["commands"].append(result)
        receipt["suite_counts"].append({"id": result["id"], **result["suite_counts"]})
        if result["timed_out"] or result["exit"] != 0 or result["expectation_mismatches"]:
            if entry["classification"] == "normative":
                receipt["outcome"] = "DIVERGENCE"
            else:
                receipt["outcome"] = "OBSERVED_DIVERGENCE"
            receipt["reason"] = f"first failing command: {result['id']}"
            break
    else:
        receipt["outcome"] = "PASS"

    _write_json(output, receipt)
    return 1 if receipt["outcome"] == "DIVERGENCE" else 0


def unavailable_entry(
    plan: dict[str, Any],
    entry: dict[str, Any],
    output: pathlib.Path,
    reason: str,
    proof_kind: str,
    evidence: str,
) -> int:
    receipt = _base_receipt(plan, entry)
    receipt["outcome"] = "INFRA_UNAVAILABLE"
    receipt["reason"] = reason
    receipt["infra_proof"] = _infra_proof(
        proof_kind,
        "portability/matrix/receipt.py:workflow-setup-observer",
        evidence,
    )
    _write_json(output, receipt)
    return 0


def _synthetic_unavailable(
    entry: dict[str, Any], reason: str, plan: dict[str, Any] | None = None
) -> dict[str, Any]:
    if entry.get("runnable", True):
        raise ValueError("synthetic infrastructure receipts are only valid for unscheduled rows")
    evidence = entry.get("infra_evidence")
    checked = entry.get("evidence_checked")
    if not isinstance(evidence, str) or not evidence or not isinstance(checked, str) or not checked:
        raise ValueError(f"predeclared unavailable row {entry['id']} lacks durable evidence")
    return {
        "schema": SCHEMA,
        "entry_id": entry["id"],
        "classification": entry["classification"],
        "claim_scope": entry["claim_scope"],
        "role": entry["role"],
        "requested": {
            key: entry.get(key)
            for key in (
                "runner",
                "os_family",
                "architecture",
                "setup_architecture",
                "runtime",
                "implementation",
                "python_version",
                "distribution_release",
                "python_language_version",
                "profile",
                "required_capability",
                "language_floor",
                "non_substitute_for",
            )
        },
        "git": {
            "sha": None,
            "github_sha": os.environ.get("GITHUB_SHA"),
            "clean": None,
            "unavailable": True,
        },
        "environment": {
            "os": None,
            "architecture": {
                "requested": entry.get("architecture"),
                "machine": None,
                "mode": "unavailable",
                "darwin_rosetta": None,
                "windows_wow64": None,
            },
            "runtime": None,
            "abi": None,
            "encoding": None,
            "resources": None,
        },
        "commands_planned": (
            profile_commands(plan, entry["profile"]) if plan is not None else []
        ),
        "commands": [],
        "suite_counts": [],
        "outcome": "INFRA_UNAVAILABLE",
        "reason": reason,
        "infra_proof": _infra_proof(
            "predeclared_runner_unavailable",
            "portability/matrix/plan.json",
            f"{evidence} (checked {checked})",
        ),
        "infra_evidence": entry.get("infra_evidence"),
        "evidence_checked": entry.get("evidence_checked"),
    }


def _synthetic_missing(
    entry: dict[str, Any], reason: str, plan: dict[str, Any]
) -> dict[str, Any]:
    row = {
        "schema": SCHEMA,
        "entry_id": entry["id"],
        "classification": entry["classification"],
        "claim_scope": entry["claim_scope"],
        "role": entry["role"],
        "requested": {
            key: entry.get(key)
            for key in (
                "runner",
                "os_family",
                "architecture",
                "setup_architecture",
                "runtime",
                "implementation",
                "python_version",
                "distribution_release",
                "python_language_version",
                "profile",
                "required_capability",
                "language_floor",
                "non_substitute_for",
            )
        },
        "git": None,
        "environment": None,
        "commands_planned": profile_commands(plan, entry["profile"]),
        "commands": [],
        "suite_counts": [],
        "outcome": "RECEIPT_MISSING",
        "reason": reason,
        "infra_proof": None,
    }
    return row


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_nonnegative_integer(
    value: Any, maximum: int = MAX_RECEIPT_INTEGER
) -> bool:
    return _is_integer(value) and 0 <= value <= maximum


def _is_bounded_integer(value: Any, minimum: int, maximum: int) -> bool:
    return _is_integer(value) and minimum <= value <= maximum


def _is_nonnegative_number(
    value: Any, maximum: int | float = MAX_RECEIPT_SECONDS
) -> bool:
    # Do not coerce an integer to float: ``float(10**1000)`` raises
    # OverflowError.  Exact type branches also keep JSON booleans out.
    if _is_integer(value):
        return 0 <= value <= maximum
    if isinstance(value, float):
        return (
            math.isfinite(value)
            and not (value == 0.0 and math.copysign(1.0, value) < 0)
            and 0.0 <= value <= maximum
        )
    if isinstance(value, decimal.Decimal):
        return (
            value.is_finite()
            and not (value.is_zero() and value.is_signed())
            and decimal.Decimal(0) <= value <= decimal.Decimal(maximum)
        )
    return False


def _is_bounded_json_scalar(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool)):
        return True
    if _is_integer(value):
        return -MAX_RECEIPT_INTEGER <= value <= MAX_RECEIPT_INTEGER
    if isinstance(value, float):
        return (
            math.isfinite(value)
            and not (value == 0.0 and math.copysign(1.0, value) < 0)
            and abs(value) <= MAX_RECEIPT_INTEGER
        )
    if isinstance(value, decimal.Decimal):
        return (
            value.is_finite()
            and not (value.is_zero() and value.is_signed())
            and abs(value) <= decimal.Decimal(MAX_RECEIPT_INTEGER)
        )
    return False


def _bounded_decimal(value: str, maximum: int) -> int | None:
    """Parse unsigned decimal text without exposing ``int`` to huge input."""

    if re.fullmatch(r"\d+", value) is None:
        return None
    canonical = value.lstrip("0") or "0"
    ceiling = str(maximum)
    if len(canonical) > len(ceiling) or (
        len(canonical) == len(ceiling) and canonical > ceiling
    ):
        return None
    return int(canonical)


def _expected_requested(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        key: entry.get(key)
        for key in (
            "runner",
            "os_family",
            "architecture",
            "setup_architecture",
            "runtime",
            "implementation",
            "python_version",
            "distribution_release",
            "python_language_version",
            "profile",
            "required_capability",
            "language_floor",
            "non_substitute_for",
        )
    }


def _codec_name(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return codecs.lookup(value).name
    except LookupError:
        return None


def _version_info_validation_error(value: Any, full_version: Any) -> str | None:
    """Validate the JSON projection of ``sys.version_info`` and its display.

    Python exposes five fields with a closed release-level vocabulary.  The
    final-release serial is zero; prerelease serial zero remains valid for
    development snapshots such as ``3.x.0a0``.  ``sys.version`` starts with
    the corresponding public version before optional build metadata.
    """

    if not isinstance(value, list) or len(value) != 5:
        return "environment runtime version_info must be a five-item array"
    if not all(
        _is_nonnegative_integer(item, MAX_VERSION_COMPONENT) for item in value[:3]
    ):
        return "environment runtime version_info numbers are outside the finite integer domain"
    releaselevel = value[3]
    if not isinstance(releaselevel, str) or releaselevel not in RELEASELEVEL_TAGS:
        return "environment runtime version_info releaselevel is invalid"
    serial = value[4]
    if not _is_nonnegative_integer(serial, MAX_VERSION_COMPONENT):
        return "environment runtime version_info serial is outside the finite integer domain"
    if releaselevel == "final" and serial != 0:
        return "environment runtime final version_info must have serial zero"
    if not isinstance(full_version, str) or not full_version:
        return "environment runtime full_version must be nonempty"
    public = f"{value[0]}.{value[1]}.{value[2]}"
    if releaselevel != "final":
        public += f"{RELEASELEVEL_TAGS[releaselevel]}{serial}"
    if re.match(rf"{re.escape(public)}(?=$|[\s()+-])", full_version) is None:
        return "runtime full_version disagrees with version_info release metadata"
    return None


def _environment_binding_error(
    value: Any,
    entry: dict[str, Any],
    plan_requirements: Any,
) -> str | None:
    """Recompute whether execution evidence satisfies its checked-in row.

    This is deliberately separate from the structural receipt validator: the
    summary must not rely on the runner's preflight classification.
    """

    expected_requirement_fields = {
        "word_size_bits",
        "byte_order",
        "preferred_encoding",
        "filesystem_encoding",
        "default_encoding",
        "stream_encoding",
    }
    if not isinstance(plan_requirements, dict) or set(plan_requirements) != (
        expected_requirement_fields
    ):
        return "checked-in environment requirements have an invalid schema"
    os_value = value.get("os") if isinstance(value, dict) else None
    arch = value.get("architecture") if isinstance(value, dict) else None
    runtime = value.get("runtime") if isinstance(value, dict) else None
    abi = value.get("abi") if isinstance(value, dict) else None
    encoding = value.get("encoding") if isinstance(value, dict) else None
    if not all(isinstance(item, dict) for item in (os_value, arch, runtime, abi, encoding)):
        return "execution environment lacks a bindable field group"

    expected_os = entry.get("os_family")
    if os_value.get("system") != expected_os:
        return (
            f"requested OS family {expected_os!r}, observed "
            f"{os_value.get('system')!r}"
        )
    uname = os_value.get("uname")
    if not isinstance(uname, list) or len(uname) != 6:
        return "environment uname does not contain the six platform fields"
    if (
        uname[0] != os_value.get("system")
        or uname[2] != os_value.get("release")
        or uname[3] != os_value.get("kernel_version")
    ):
        return "environment uname disagrees with the recorded OS fields"

    expected_arch = _normalize_arch(str(entry.get("architecture", "")))
    observed_machine = _normalize_arch(str(arch.get("machine", "")))
    if arch.get("requested") != expected_arch:
        return "recorded requested architecture disagrees with the plan"
    if observed_machine != expected_arch:
        return f"requested native {expected_arch}, observed machine {observed_machine}"
    if _normalize_arch(uname[4]) != observed_machine:
        return "environment uname machine disagrees with architecture evidence"
    if arch.get("mode") != "native":
        return f"requested native {expected_arch}, observed mode {arch.get('mode')!r}"
    if expected_os == "Darwin" and arch.get("darwin_rosetta") is not False:
        return "native macOS execution lacks negative Rosetta evidence"
    if expected_os == "Windows" and arch.get("windows_wow64") is not False:
        return "native Windows execution lacks negative WOW64 evidence"

    expected_impl = entry.get("implementation")
    actual_impl = runtime.get("implementation")
    if not isinstance(expected_impl, str) or not expected_impl:
        return "checked-in matrix entry lacks an implementation identity"
    if actual_impl != expected_impl:
        return f"requested implementation {expected_impl!r}, observed {actual_impl!r}"
    version_info = runtime.get("version_info")
    version_info_error = _version_info_validation_error(
        version_info, runtime.get("full_version")
    )
    if version_info_error:
        return version_info_error
    actual_pair = tuple(version_info[:2]) if isinstance(version_info, list) else ()
    actual_triple = tuple(version_info[:3]) if isinstance(version_info, list) else ()
    full_version = runtime.get("full_version")
    version_match = (
        re.match(r"(\d+)\.(\d+)\.(\d+)", full_version)
        if isinstance(full_version, str)
        else None
    )
    if version_match is None or tuple(map(int, version_match.groups())) != actual_triple:
        return "runtime full_version disagrees with version_info"
    requested_version = str(entry.get("python_version", ""))
    if expected_impl == "CPython":
        match = re.fullmatch(r"(\d+)\.(\d+)(?:t)?", requested_version)
        if match is None:
            return f"checked-in CPython version {requested_version!r} is invalid"
        requested_numbers = tuple(
            _bounded_decimal(item, MAX_VERSION_COMPONENT) for item in match.groups()
        )
        if any(item is None for item in requested_numbers):
            return f"checked-in CPython version {requested_version!r} is out of range"
        expected_pair = requested_numbers
        if actual_pair != expected_pair:
            return f"requested CPython {expected_pair}, observed version {actual_pair}"
    elif expected_impl == "PyPy":
        match = re.fullmatch(r"pypy(\d+)\.(\d+)", requested_version)
        if match is None:
            return f"checked-in PyPy version {requested_version!r} is invalid"
        requested_numbers = tuple(
            _bounded_decimal(item, MAX_VERSION_COMPONENT) for item in match.groups()
        )
        if any(item is None for item in requested_numbers):
            return f"checked-in PyPy version {requested_version!r} is out of range"
        expected_pair = requested_numbers
        if actual_pair != expected_pair:
            return f"requested PyPy language version {expected_pair}, observed {actual_pair}"
    elif expected_impl == "GraalVM":
        setup_match = re.fullmatch(r"graalpy-(\d+)\.(\d+)", requested_version)
        distribution_release = str(entry.get("distribution_release", ""))
        distribution_match = re.fullmatch(r"(\d+)\.(\d+)", distribution_release)
        language_version = str(entry.get("python_language_version", ""))
        language_match = re.fullmatch(r"(\d+)\.(\d+)", language_version)
        if setup_match is None or distribution_match is None:
            return "checked-in GraalPy setup/distribution release is invalid"
        setup_pair = tuple(
            _bounded_decimal(item, MAX_VERSION_COMPONENT)
            for item in setup_match.groups()
        )
        distribution_pair = tuple(
            _bounded_decimal(item, MAX_VERSION_COMPONENT)
            for item in distribution_match.groups()
        )
        if any(item is None for item in (*setup_pair, *distribution_pair)):
            return "checked-in GraalPy setup/distribution release is out of range"
        if setup_pair != distribution_pair:
            return "checked-in GraalPy setup spec disagrees with its distribution release"
        if language_match is None:
            return "checked-in GraalPy Python language version is invalid"
        expected_language_pair = tuple(
            _bounded_decimal(item, MAX_VERSION_COMPONENT)
            for item in language_match.groups()
        )
        if any(item is None for item in expected_language_pair):
            return "checked-in GraalPy Python language version is out of range"
        if actual_pair != expected_language_pair:
            return (
                f"requested GraalPy Python language version {expected_language_pair}, "
                f"observed {actual_pair}"
            )
        resolved_setup = runtime.get("setup_python_version")
        resolved_match = (
            re.fullmatch(r"graalpy(\d+)\.(\d+)\.(\d+)", resolved_setup)
            if isinstance(resolved_setup, str)
            else None
        )
        if resolved_match is None:
            return "GraalPy execution lacks the resolved setup-python release"
        resolved_numbers = tuple(
            _bounded_decimal(item, MAX_VERSION_COMPONENT)
            for item in resolved_match.groups()
        )
        if any(item is None for item in resolved_numbers):
            return "GraalPy resolved setup-python release is out of range"
        resolved_pair = resolved_numbers[:2]
        if resolved_pair != distribution_pair:
            return (
                f"requested GraalPy distribution release {distribution_pair}, "
                f"setup-python resolved {resolved_pair}"
            )

    flags = runtime.get("build_flags")
    if not isinstance(flags, dict):
        return "runtime build flags are unavailable"
    capability = entry.get("required_capability")
    if capability == "free_threaded":
        if not _is_integer(flags.get("Py_GIL_DISABLED")) or flags["Py_GIL_DISABLED"] != 1:
            return "free-threaded row lacks Py_GIL_DISABLED=1"
        if runtime.get("gil_enabled") is not False:
            return "free-threaded row lacks sys._is_gil_enabled() == false evidence"
    elif capability == "pydebug":
        if not _is_integer(flags.get("Py_DEBUG")) or flags["Py_DEBUG"] != 1:
            return "pydebug row lacks Py_DEBUG=1"
    elif capability == "dev_mode":
        if runtime.get("dev_mode") is not True:
            return "development-mode row lacks sys.flags.dev_mode == true"
    elif capability is not None:
        return f"checked-in matrix entry has unsupported capability {capability!r}"

    if abi.get("word_size_bits") != plan_requirements["word_size_bits"]:
        return "execution word size does not match the checked-in requirement"
    if abi.get("byte_order") != plan_requirements["byte_order"]:
        return "execution byte order does not match the checked-in requirement"
    encoding_bindings = {
        "preferred": "preferred_encoding",
        "filesystem": "filesystem_encoding",
        "default": "default_encoding",
        "stdout": "stream_encoding",
        "stderr": "stream_encoding",
    }
    for observed_field, requirement_field in encoding_bindings.items():
        observed_name = _codec_name(encoding.get(observed_field))
        required_name = _codec_name(plan_requirements[requirement_field])
        if required_name is None or observed_name != required_name:
            return (
                f"execution encoding {observed_field}={encoding.get(observed_field)!r} "
                f"does not match {plan_requirements[requirement_field]!r}"
            )
    return None


def _runnable_git_binding_error(value: Any, expected_sha: str | None) -> str | None:
    if not isinstance(value, dict):
        return "runnable receipt lacks git evidence"
    if value.get("github_sha") is None:
        return "runnable receipt lacks GITHUB_SHA binding"
    if value.get("github_sha") != value.get("sha"):
        return "runnable receipt git sha does not match GITHUB_SHA"
    if value.get("clean") is not True or value.get("status_line_count") != 0:
        return "runnable receipt was not captured from a clean checkout"
    # Run currency.  The commit a receipt must belong to is supplied by the
    # caller -- the workflow SHA for a live summary, HOSTED_HEAD for the sealed
    # hosted replay -- and is never read from this process environment.  A
    # validator whose verdict depends on an ambient variable is green where the
    # variable is unset and red where it is set; that is ERRATA E17.
    # expected_sha has no default, so no caller can drop the authority by
    # omission; passing None is an explicit statement that the caller holds no
    # external authority, and asserts nothing beyond the self-consistency
    # already required above.
    if expected_sha is not None and value.get("sha") != expected_sha:
        return "runnable receipt sha does not match the expected workflow sha"
    return None


def _git_validation_error(value: Any) -> str | None:
    if not isinstance(value, dict):
        return "git evidence must be an object"
    expected_fields = {
        "sha",
        "github_sha",
        "clean",
        "status_sha256",
        "status_line_count",
    }
    if set(value) != expected_fields:
        return "git evidence fields do not match the executed-receipt schema"
    sha = value.get("sha")
    github_sha = value.get("github_sha")
    status_hash = value.get("status_sha256")
    status_lines = value.get("status_line_count")
    if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        return "git sha must be 40 lowercase hexadecimal characters"
    if github_sha is not None:
        if not isinstance(github_sha, str) or re.fullmatch(r"[0-9a-f]{40}", github_sha) is None:
            return "GITHUB_SHA must be null or 40 lowercase hexadecimal characters"
        if github_sha != sha:
            return "git sha does not match GITHUB_SHA"
    if not isinstance(value.get("clean"), bool):
        return "git clean status must be boolean"
    if not isinstance(status_hash, str) or re.fullmatch(r"[0-9a-f]{64}", status_hash) is None:
        return "git status hash must be 64 lowercase hexadecimal characters"
    if not _is_nonnegative_integer(status_lines):
        return "git status line count is outside the finite integer domain"
    if value["clean"] != (status_lines == 0):
        return "git clean status disagrees with the status line count"
    if status_lines == 0 and status_hash != hashlib.sha256(b"").hexdigest():
        return "empty git status has the wrong hash"
    return None


def _environment_validation_error(value: Any, entry: dict[str, Any]) -> str | None:
    if not isinstance(value, dict) or set(value) != {
        "os",
        "architecture",
        "runtime",
        "abi",
        "encoding",
        "resources",
    }:
        return "environment fields do not match the executed-receipt schema"

    os_value = value.get("os")
    if not isinstance(os_value, dict) or set(os_value) != {
        "system",
        "release",
        "kernel_version",
        "uname",
    }:
        return "environment os evidence has an invalid schema"
    if not all(isinstance(os_value[field], str) for field in ("system", "release", "kernel_version")):
        return "environment os strings are invalid"
    if not isinstance(os_value["uname"], list) or not os_value["uname"] or not all(
        isinstance(item, str) for item in os_value["uname"]
    ):
        return "environment uname must be a nonempty string array"

    arch = value.get("architecture")
    if not isinstance(arch, dict) or set(arch) != {
        "requested",
        "machine",
        "mode",
        "darwin_rosetta",
        "windows_wow64",
    }:
        return "environment architecture evidence has an invalid schema"
    if arch.get("requested") != _normalize_arch(entry["architecture"]):
        return "environment requested architecture disagrees with the plan"
    if not isinstance(arch.get("machine"), str) or not arch["machine"]:
        return "environment machine architecture must be nonempty"
    if arch.get("mode") not in {"native", "emulated", "emulated_or_mismatch"}:
        return "environment architecture mode is invalid"
    if arch.get("darwin_rosetta") is not None and not isinstance(arch["darwin_rosetta"], bool):
        return "darwin_rosetta must be boolean or null"
    if not isinstance(arch.get("windows_wow64"), bool):
        return "windows_wow64 must be boolean"

    runtime = value.get("runtime")
    if not isinstance(runtime, dict) or set(runtime) != {
        "implementation",
        "full_version",
        "version_info",
        "setup_python_version",
        "executable",
        "build",
        "compiler",
        "build_flags",
        "gil_enabled",
        "dev_mode",
    }:
        return "environment runtime evidence has an invalid schema"
    for field in ("implementation", "full_version", "executable", "compiler"):
        if not isinstance(runtime.get(field), str):
            return f"environment runtime {field} must be a string"
        if not runtime[field]:
            # F-MATRIX-013: alternative runtimes (GraalPy, PyPy) legitimately
            # report an empty `platform.python_compiler()`; the empty string is
            # the honest recorded value for observation receipts.  Normative
            # receipts keep the nonempty requirement.
            if field != "compiler" or entry.get("classification") == "normative":
                return f"environment runtime {field} must be nonempty"
    if runtime.get("setup_python_version") is not None and not isinstance(
        runtime["setup_python_version"], str
    ):
        return "environment runtime setup_python_version must be a string or null"
    version_info_error = _version_info_validation_error(
        runtime.get("version_info"), runtime.get("full_version")
    )
    if version_info_error:
        return version_info_error
    if not isinstance(runtime.get("build"), list) or not runtime["build"] or not all(
        isinstance(item, str) for item in runtime["build"]
    ):
        return "environment runtime build must be a nonempty string array"
    flags = runtime.get("build_flags")
    if not isinstance(flags, dict) or set(flags) != set(BUILD_FLAG_NAMES):
        return "environment runtime build_flags has an invalid schema"
    if not all(_is_bounded_json_scalar(item) for item in flags.values()):
        return "environment runtime build_flags contains a non-scalar value"
    if runtime.get("gil_enabled") is not None and not isinstance(runtime["gil_enabled"], bool):
        return "environment runtime gil_enabled must be boolean or null"
    if not isinstance(runtime.get("dev_mode"), bool):
        return "environment runtime dev_mode must be boolean"

    abi = value.get("abi")
    if not isinstance(abi, dict) or set(abi) != {"word_size_bits", "byte_order"}:
        return "environment ABI evidence has an invalid schema"
    if not _is_nonnegative_integer(
        abi.get("word_size_bits"), MAX_WORD_SIZE_BITS
    ) or abi["word_size_bits"] == 0:
        return "environment word size must be a positive integer"
    if abi.get("byte_order") not in {"little", "big"}:
        return "environment byte order is invalid"

    encoding = value.get("encoding")
    encoding_fields = {
        "locale",
        "preferred",
        "filesystem",
        "filesystem_errors",
        "default",
        "stdout",
        "stderr",
    }
    if not isinstance(encoding, dict) or set(encoding) != encoding_fields:
        return "environment encoding evidence has an invalid schema"
    if not all(isinstance(encoding[field], str) and encoding[field] for field in encoding_fields):
        return "environment encoding values must be nonempty strings"

    resources = value.get("resources")
    if not isinstance(resources, dict) or set(resources) != {
        "logical_cpu_count",
        "physical_memory_bytes",
        "disk_total_bytes",
        "disk_free_bytes",
    }:
        return "environment resource evidence has an invalid schema"
    for field in resources:
        item = resources[field]
        maximum = (
            MAX_LOGICAL_CPU_COUNT
            if field == "logical_cpu_count"
            else MAX_RECEIPT_INTEGER
        )
        if item is not None and not _is_nonnegative_integer(item, maximum):
            return f"environment resource {field} is outside its finite integer domain"
    total = resources["disk_total_bytes"]
    free = resources["disk_free_bytes"]
    if total is None or free is None or free > total:
        return "environment disk resource values are inconsistent"
    return None


def _suite_counts_validation_error(value: Any) -> str | None:
    if not isinstance(value, dict) or set(value) != set(COUNT_FIELDS):
        return "suite_counts fields do not match the parser schema"
    for field in COUNT_FIELDS[:-1]:
        values = value[field]
        if not isinstance(values, list) or not all(
            _is_nonnegative_integer(item) for item in values
        ):
            return f"suite_counts {field} must be a nonnegative integer array"
    progress = value["case_progress"]
    if not isinstance(progress, list):
        return "suite_counts case_progress must be an array"
    for pair in progress:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(_is_nonnegative_integer(item) for item in pair)
            or pair[0] > pair[1]
        ):
            return "suite_counts case_progress contains an invalid pair"
    return None


def _argv_validation_error(
    actual: Any,
    templates: Any,
    row: dict[str, Any],
    temp_roots: set[str],
) -> str | None:
    if not isinstance(actual, list) or not all(isinstance(item, str) for item in actual):
        return "command argv must be a string array"
    if not isinstance(templates, list) or len(actual) != len(templates):
        return "command argv length does not match the plan"
    environment = row.get("environment")
    runtime = environment.get("runtime") if isinstance(environment, dict) else None
    executable = runtime.get("executable") if isinstance(runtime, dict) else None
    for index, (observed, template) in enumerate(zip(actual, templates)):
        if not isinstance(template, str):
            return "planned argv contains a non-string template"
        if template == "{python}":
            if observed != executable:
                return f"command argv[{index}] does not match the recorded interpreter"
            continue
        expected = template.replace("{entry_id}", row["entry_id"])
        if "{temp}" not in expected:
            if observed != expected:
                return f"command argv[{index}] does not match the plan"
            continue
        prefix, suffix = expected.split("{temp}", 1)
        if not observed.startswith(prefix) or (suffix and not observed.endswith(suffix)):
            return f"command argv[{index}] does not match the temporary-path template"
        end = len(observed) - len(suffix) if suffix else len(observed)
        temp_root = observed[len(prefix) : end]
        if not temp_root or not (ntpath.isabs(temp_root) or posixpath.isabs(temp_root)):
            return f"command argv[{index}] has a non-absolute temporary root"
        temp_roots.add(temp_root)
        if len(temp_roots) != 1:
            return "command argv uses inconsistent temporary roots"
    return None


def _command_validation_error(
    command: Any,
    spec: dict[str, Any],
    row: dict[str, Any],
    temp_roots: set[str],
) -> str | None:
    if not isinstance(command, dict) or set(command) != COMMAND_FIELDS:
        return "command result fields do not match the executed-command schema"
    if command.get("id") != spec["id"]:
        return "command id does not match the plan"
    argv_error = _argv_validation_error(command.get("argv"), spec["argv"], row, temp_roots)
    if argv_error:
        return argv_error
    if command.get("cwd") != spec["cwd"]:
        return "command cwd does not match the plan"
    if command.get("timeout_seconds") != spec["timeout_seconds"] or not _is_integer(
        command.get("timeout_seconds")
    ):
        return "command timeout does not match the plan"
    timed_out = command.get("timed_out")
    if not isinstance(timed_out, bool):
        return "command timed_out must be boolean"
    exit_code = command.get("exit")
    if timed_out:
        if exit_code is not None:
            return "timed-out command must have a null exit"
    elif not _is_bounded_integer(exit_code, MIN_PROCESS_EXIT, MAX_PROCESS_EXIT):
        return "completed command exit is outside the finite process-code domain"
    elapsed_ceiling = spec["timeout_seconds"] + MAX_TIMER_OVERRUN_SECONDS
    if not _is_nonnegative_number(command.get("elapsed_seconds"), elapsed_ceiling):
        return "command elapsed_seconds is outside its finite plan-bounded domain"
    for field in ("stdout_sha256", "stderr_sha256"):
        digest = command.get(field)
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            return f"command {field} must be 64 lowercase hexadecimal characters"
    for field in ("stdout_bytes", "stderr_bytes"):
        if not _is_nonnegative_integer(command.get(field)):
            return f"command {field} is outside the finite integer domain"
    counts = command.get("suite_counts")
    counts_error = _suite_counts_validation_error(counts)
    if counts_error:
        return counts_error
    expected_counts = spec.get("expected", {})
    if command.get("expected_counts") != expected_counts:
        return "command expected_counts does not match the plan"
    mismatches = command.get("expectation_mismatches")
    if not isinstance(mismatches, list) or not all(isinstance(item, str) for item in mismatches):
        return "command expectation_mismatches must be a string array"
    if mismatches != _expectation_mismatches(expected_counts, counts):
        return "command expectation_mismatches disagrees with suite_counts"
    resources = command.get("resources")
    if not isinstance(resources, dict) or set(resources) != {
        "children_user_seconds",
        "children_system_seconds",
        "max_rss_kib",
    }:
        return "command resources fields do not match the resource schema"
    for field in ("children_user_seconds", "children_system_seconds"):
        if not _is_nonnegative_number(resources.get(field)):
            return f"command resource {field} is outside the finite numeric domain"
    max_rss = resources.get("max_rss_kib")
    if max_rss is not None and not _is_nonnegative_integer(max_rss):
        return "command resource max_rss_kib is outside the finite integer domain"
    return None


def _receipt_validation_error(
    row: dict[str, Any],
    entry: dict[str, Any],
    plan: dict[str, Any],
    expected_sha: str | None = None,
) -> str | None:
    top_level_fields = {
        "schema",
        "entry_id",
        "classification",
        "claim_scope",
        "role",
        "requested",
        "git",
        "environment",
        "commands_planned",
        "commands",
        "suite_counts",
        "outcome",
        "reason",
        "infra_proof",
    }
    if not entry.get("runnable", True):
        top_level_fields.update({"infra_evidence", "evidence_checked"})
    if set(row) != top_level_fields:
        return "top-level receipt fields do not match the receipt schema"
    required_matches = {
        "schema": SCHEMA,
        "entry_id": entry["id"],
        "classification": entry["classification"],
        "claim_scope": entry["claim_scope"],
        "role": entry["role"],
    }
    for field, expected in required_matches.items():
        if row.get(field) != expected:
            return f"{field} does not match the checked-in matrix entry"
    if row.get("requested") != _expected_requested(entry):
        return "requested environment does not match the checked-in matrix entry"

    outcome = row.get("outcome")
    allowed = {"PASS", "DIVERGENCE", "OBSERVED_DIVERGENCE", "INFRA_UNAVAILABLE"}
    if outcome not in allowed:
        return "unsupported or missing outcome"
    if entry.get("runnable", True):
        git_error = _git_validation_error(row.get("git"))
        if git_error:
            return git_error
        environment_error = _environment_validation_error(row.get("environment"), entry)
        if environment_error:
            return environment_error
        # Every artifact produced by a scheduled row, including an explicit
        # runtime/setup absence, must belong to the workflow SHA and a clean
        # checkout.  Otherwise a stale or locally forged INFRA_UNAVAILABLE
        # receipt can suppress a normative row without executing it.
        git_binding_error = _runnable_git_binding_error(row.get("git"), expected_sha)
        if git_binding_error:
            return git_binding_error
        if outcome in {"PASS", "DIVERGENCE", "OBSERVED_DIVERGENCE"}:
            environment_binding_error = _environment_binding_error(
                row.get("environment"),
                entry,
                plan.get("environment_requirements"),
            )
            if environment_binding_error:
                return environment_binding_error
    commands = row.get("commands")
    planned = row.get("commands_planned")
    if not isinstance(commands, list) or not isinstance(planned, list):
        return "receipt commands and commands_planned must be arrays"
    expected_planned = planned_commands(plan, entry)
    if planned != expected_planned:
        return "commands_planned does not match the checked-in command manifest"
    if len(commands) > len(expected_planned):
        return "receipt contains more command results than the checked-in manifest"
    temp_roots: set[str] = set()
    for index, command in enumerate(commands):
        command_error = _command_validation_error(
            command, expected_planned[index], row, temp_roots
        )
        if command_error:
            return f"command {index} ({expected_planned[index]['id']}): {command_error}"
    expected_suite_counts = [
        {"id": command["id"], **command["suite_counts"]}
        for command in commands
    ]
    if row.get("suite_counts") != expected_suite_counts:
        return "top-level suite_counts does not match executed command aggregation"
    command_ids = [
        command.get("id") if isinstance(command, dict) else None
        for command in commands
    ]
    failed_commands = [
        command
        for command in commands
        if not isinstance(command, dict)
        or command.get("timed_out") is not False
        or command.get("exit") != 0
        or bool(command.get("expectation_mismatches"))
    ]
    if outcome == "PASS":
        if row.get("reason") is not None or row.get("infra_proof") is not None:
            return "PASS receipt must not contain a reason or infrastructure proof"
        if len(commands) != len(planned):
            return "PASS receipt did not execute every planned command"
        if failed_commands:
            return "PASS receipt contains a failed or ambiguous command result"
        if command_ids != [
            command["id"] for command in expected_planned
        ]:
            return "PASS receipt command identities or order do not match the manifest"
        return None
    if outcome == "DIVERGENCE":
        if entry["classification"] != "normative" or not failed_commands:
            return "DIVERGENCE requires a failed normative command result"
        if command_ids != [
            command["id"] for command in expected_planned[: len(commands)]
        ]:
            return "DIVERGENCE command identities or order do not match the manifest prefix"
        if failed_commands != [commands[-1]]:
            return "DIVERGENCE must stop at its first and final failed command"
        if row.get("reason") != f"first failing command: {commands[-1]['id']}":
            return "DIVERGENCE reason does not identify the first failed command"
        if row.get("infra_proof") is not None:
            return "DIVERGENCE receipt must not contain infrastructure proof"
        return None
    if outcome == "OBSERVED_DIVERGENCE":
        if entry["classification"] == "normative" or not failed_commands:
            return "OBSERVED_DIVERGENCE requires a failed non-normative command result"
        if command_ids != [
            command["id"] for command in expected_planned[: len(commands)]
        ]:
            return "OBSERVED_DIVERGENCE command identities or order do not match the manifest prefix"
        if failed_commands != [commands[-1]]:
            return "OBSERVED_DIVERGENCE must stop at its first and final failed command"
        if row.get("reason") != f"first failing command: {commands[-1]['id']}":
            return "OBSERVED_DIVERGENCE reason does not identify the first failed command"
        if row.get("infra_proof") is not None:
            return "OBSERVED_DIVERGENCE receipt must not contain infrastructure proof"
        return None

    if commands or row.get("suite_counts") != []:
        return "INFRA_UNAVAILABLE receipt must not contain executed command evidence"
    proof = row.get("infra_proof")
    if not isinstance(proof, dict):
        return "INFRA_UNAVAILABLE lacks an explicit infra_proof object"
    kind = proof.get("kind")
    producer = proof.get("producer")
    evidence = proof.get("evidence")
    if kind not in INFRA_PROOF_KINDS:
        return "INFRA_UNAVAILABLE has an unsupported proof kind"
    if not isinstance(producer, str) or not producer.strip():
        return "INFRA_UNAVAILABLE proof lacks a producer"
    if not isinstance(evidence, str) or not evidence.strip():
        return "INFRA_UNAVAILABLE proof lacks evidence"
    reason = row.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return "INFRA_UNAVAILABLE lacks a reason"
    if entry.get("runnable", True) and kind == "predeclared_runner_unavailable":
        return "runnable row cannot use predeclared runner-unavailable proof"
    if not entry.get("runnable", True) and kind != "predeclared_runner_unavailable":
        return "unscheduled row requires predeclared runner-unavailable proof"
    expected_proof = {
        "predeclared_runner_unavailable": (
            "portability/matrix/plan.json",
            f"{entry.get('infra_evidence')} (checked {entry.get('evidence_checked')})",
        ),
        "runtime_setup_unavailable": (
            "portability/matrix/receipt.py:workflow-setup-observer",
            "steps.setup.outcome=failure",
        ),
        "runtime_build_unavailable": (
            "portability/matrix/receipt.py:runtime-probe",
            reason,
        ),
    }
    if (producer, evidence) != expected_proof[kind]:
        return f"INFRA_UNAVAILABLE proof fields do not match kind {kind!r}"
    return None


def summarize(
    plan: dict[str, Any],
    receipts_dir: pathlib.Path,
    output: pathlib.Path,
    upstream_job_results: dict[str, str] | None = None,
    *,
    workflow_sha: str | None = None,
) -> int:
    expected = {entry["id"]: entry for entry in all_entries(plan)}
    expected_by_filename = {
        f"receipt-{entry_id}.json": entry for entry_id, entry in expected.items()
    }
    loaded: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    gating_errors: list[str] = []
    observation_errors: list[str] = []
    invalid_entry_ids: set[str] = set()

    def record_error(message: str, entry: dict[str, Any] | None = None) -> None:
        errors.append(message)
        if entry is not None and entry.get("classification") != "normative":
            observation_errors.append(message)
        else:
            gating_errors.append(message)

    if receipts_dir.exists():
        for path in sorted(receipts_dir.rglob("receipt-*.json")):
            filename_entry = expected_by_filename.get(path.name)
            try:
                receipt = _json_load(path)
                entry_id = receipt["entry_id"]
            except (
                KeyError,
                OSError,
                ValueError,
                json.JSONDecodeError,
                MemoryError,
                RecursionError,
            ) as exc:
                record_error(f"invalid receipt {path}: {exc}", filename_entry)
                continue
            if not isinstance(entry_id, str):
                record_error(
                    f"invalid receipt {path}: entry_id must be a string",
                    filename_entry,
                )
                continue
            if entry_id not in expected:
                record_error(f"unexpected receipt entry_id at {path}", filename_entry)
                continue
            if filename_entry is None or filename_entry["id"] != entry_id:
                # A normative artifact can never borrow an observation-only
                # filename (or vice versa) to change its gating class.
                mismatch_entry = (
                    filename_entry
                    if filename_entry is not None
                    and filename_entry.get("classification") != "normative"
                    and expected[entry_id].get("classification") != "normative"
                    else None
                )
                record_error(
                    f"receipt filename does not match entry_id at {path}",
                    mismatch_entry,
                )
                continue
            if entry_id in loaded:
                record_error(
                    f"duplicate receipt for {entry_id!r}", expected[entry_id]
                )
                invalid_entry_ids.add(entry_id)
                continue
            try:
                validation_error = _receipt_validation_error(
                    receipt, expected[entry_id], plan, workflow_sha
                )
            except Exception as exc:
                # Artifact contents are hostile.  A validator bug or an
                # arithmetic/formatting edge must make the summary red, never
                # terminate it before a durable failure summary is written.
                validation_error = (
                    "validator rejected hostile artifact with "
                    f"{type(exc).__name__}"
                )
            if validation_error:
                record_error(
                    f"invalid receipt {path}: {validation_error}",
                    expected[entry_id],
                )
                invalid_entry_ids.add(entry_id)
            else:
                loaded[entry_id] = receipt

    results = dict(upstream_job_results or {})
    for role in ("normative_matrix", "expanded_gate"):
        result = results.get(role)
        if result is not None and result != "success":
            record_error(
                f"upstream normative job {role!r} concluded {result!r}"
            )

    rows = []
    for entry_id, entry in expected.items():
        if entry_id in loaded:
            rows.append(loaded[entry_id])
            continue
        if not entry.get("runnable", True):
            reason = entry["infra_reason"]
            rows.append(_synthetic_unavailable(entry, reason, plan))
        else:
            reason = (
                "No durable receipt artifact was produced for this scheduled row; "
                "runner/job failure, receipt-writer failure, or artifact loss is ambiguous."
            )
            rows.append(_synthetic_missing(entry, reason, plan))

    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        classification = row["classification"]
        outcome = row["outcome"]
        counts.setdefault(classification, {})[outcome] = (
            counts.setdefault(classification, {}).get(outcome, 0) + 1
        )
    normative_bad = [
        row["entry_id"]
        for row in rows
        if row["classification"] == "normative"
        and (
            row["outcome"] not in {"PASS", "INFRA_UNAVAILABLE"}
            or row["entry_id"] in invalid_entry_ids
        )
    ]
    summary = {
        "schema": SUMMARY_SCHEMA,
        "plan_schema": plan["schema"],
        "counts": counts,
        "errors": errors,
        "gating_errors": gating_errors,
        "observation_errors": observation_errors,
        "normative_failures": normative_bad,
        "upstream_job_results": results,
        "rows": rows,
    }
    _write_json(output, summary)
    return 1 if normative_bad or gating_errors else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=pathlib.Path, default=DEFAULT_PLAN)
    subparsers = parser.add_subparsers(dest="command", required=True)

    emit = subparsers.add_parser("emit-matrix")
    emit.add_argument("--role", choices=("normative_matrix", "stress_matrix"), required=True)

    run = subparsers.add_parser("run")
    run.add_argument("--entry", required=True)
    run.add_argument("--output-name", required=True)

    unavailable = subparsers.add_parser("infra-unavailable")
    unavailable.add_argument("--entry", required=True)
    unavailable.add_argument("--output-name", required=True)
    unavailable.add_argument("--reason", required=True)
    unavailable.add_argument(
        "--proof-kind",
        choices=("runtime_setup_unavailable",),
        required=True,
    )
    unavailable.add_argument("--evidence", required=True)

    summary = subparsers.add_parser("summarize")
    summary.add_argument("--receipts-dir", type=pathlib.Path, required=True)
    summary.add_argument("--output-name", required=True)
    summary.add_argument("--workflow-sha", required=False)
    summary.add_argument("--normative-job-result", required=False)
    summary.add_argument("--expanded-gate-job-result", required=False)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    plan = _json_load(args.plan)
    if args.command == "emit-matrix":
        print(json.dumps({"include": matrix_rows(plan, args.role)}, separators=(",", ":")))
        return 0
    output = _output_path(args.output_name)
    if args.command == "summarize":
        # The one place this program consults the process environment.  Below
        # this line the expected commit travels as an argument, so no
        # validator verdict can depend on the shell it was invoked from.  An
        # empty GITHUB_SHA counts as absent rather than as a SHA that no
        # receipt can match.
        workflow_sha = args.workflow_sha or os.environ.get("GITHUB_SHA") or None
        if workflow_sha is None:
            print(
                "summarize requires the commit its receipts must belong to: "
                "pass --workflow-sha or set GITHUB_SHA",
                file=sys.stderr,
            )
            return 2
        return summarize(
            plan,
            args.receipts_dir,
            output,
            {
                "normative_matrix": args.normative_job_result,
                "expanded_gate": args.expanded_gate_job_result,
            },
            workflow_sha=workflow_sha,
        )
    entry = find_entry(plan, args.entry)
    if args.command == "run":
        return run_entry(plan, entry, output)
    if args.command == "infra-unavailable":
        return unavailable_entry(
            plan,
            entry,
            output,
            args.reason,
            args.proof_kind,
            args.evidence,
        )
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
