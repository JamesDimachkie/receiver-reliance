"""Bounded, deterministic concurrency and resource-accounting ladder.

This lane is treatment-exposed.  It must never author future blinded worlds,
their oracle, gold, or renderer.  The accepted receiver-reliance
implementation is imported read-only and is never modified by this harness.

The controller runs every level twice in fresh worker processes.  Workers
exercise both the in-process ``rr_batch.serve`` library surface and actual
``rr_batch.py`` batch clients.  Caller inputs and the start barrier are
deterministic; operating-system scheduling is deliberately left free so that
the byte-stability invariant is tested rather than assumed.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures
import ctypes
import ctypes.wintypes
import errno
import gc
import hashlib
import io
import json
import locale
import os
import pathlib
import platform
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from typing import Any, Callable


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
GROUND = REPO / "grounded-0_4"
RUNNER = GROUND / "rr_batch.py"
SUPPLEMENTAL_FIXTURES = (
    REPO
    / "supplemental-0_3"
    / "fixtures"
    / "B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json"
)
DEFAULT_LEVELS = (1, 2, 4, 8, 16, 32)
DEFAULT_REQUESTS = 200
DEFAULT_SOAK_REQUESTS = 1_000
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_SEED = 0x52525F434F4E43
RESOURCE_CEILING_ERRNOS = {errno.EAGAIN, errno.EMFILE, errno.ENFILE, errno.ENOMEM}
RESOURCE_CEILING_WINERRORS = {8, 14, 1450, 1455}

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(GROUND) not in sys.path:
    sys.path.insert(0, str(GROUND))

import rr_batch  # noqa: E402  (accepted implementation, read-only)
from portability.oracle import (  # noqa: E402
    FixtureOracle,
    jcs_bytes,
)


AUDITED_FORMAT_VERSION = "B1-AUDITED-DECISION-0.4.1"
AUDITED_FIELDS = frozenset(
    {
        "audit",
        "audit_sha256",
        "audited_behavior_class",
        "exit_code",
        "format_version",
        "sealed_response",
    }
)
AUDITED_BEHAVIOR_CLASSES = frozenset(
    {
        "VALID",
        "MALFORMED_OR_BOUNDARY",
        "BINDING_OR_CONFLICT",
        "OMISSION_OR_INCOMPLETE",
        "PROTOCOL_ERROR",
    }
)
PHYSICAL_COMPARATOR = "cached-one-record-isolated-grounded-0.4-rr_batch.py"


class InvariantFailure(RuntimeError):
    """A credible concurrency, ordering, cleanup, or progress divergence."""

    def __init__(self, message: str, divergence: dict[str, Any] | None = None):
        super().__init__(message)
        self.divergence = divergence


class HostCeiling(RuntimeError):
    """The declared ladder encountered a host resource ceiling."""


class ProcessRegistry:
    """Thread-safe list of live batch-client processes for probes/cleanup."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: dict[int, subprocess.Popen[bytes]] = {}

    def add(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            self._processes[process.pid] = process

    def discard(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            self._processes.pop(process.pid, None)

    def pids(self) -> list[int]:
        with self._lock:
            return sorted(self._processes)

    def terminate_all(self) -> list[dict[str, Any]]:
        with self._lock:
            processes = list(self._processes.values())
        outcomes: list[dict[str, Any]] = []
        for process in processes:
            if process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass
        for process in processes:
            try:
                exit_code = process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except OSError:
                    pass
                try:
                    exit_code = process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    exit_code = None
            _close_process_streams(process)
            outcomes.append({"pid": process.pid, "exit_code": exit_code})
            self.discard(process)
        return outcomes


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise InvariantFailure("120-second level deadline exhausted", {"kind": "timeout"})
    return remaining


def _is_host_ceiling(error: BaseException) -> bool:
    return isinstance(error, OSError) and (
        error.errno in RESOURCE_CEILING_ERRNOS
        or getattr(error, "winerror", None) in RESOURCE_CEILING_WINERRORS
    )


def _host_ceiling_detail(error: BaseException) -> dict[str, Any]:
    return {
        "kind": "host_resource_ceiling",
        "exception_type": type(error).__name__,
        "errno": getattr(error, "errno", None),
        "winerror": getattr(error, "winerror", None),
        "message": str(error),
    }


def _runtime_receipt() -> dict[str, Any]:
    gil_api = getattr(sys, "_is_gil_enabled", None)
    return {
        "implementation": platform.python_implementation(),
        "version": sys.version,
        "version_info": list(sys.version_info[:5]),
        "executable": sys.executable,
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "word_size_bits": struct.calcsize("P") * 8,
        "byte_order": sys.byteorder,
        "filesystem_encoding": sys.getfilesystemencoding(),
        "preferred_encoding": locale.getpreferredencoding(False),
        "gil_receipt": {
            "sys._is_gil_enabled_available": callable(gil_api),
            "sys._is_gil_enabled": gil_api() if callable(gil_api) else None,
        },
    }


def _load_templates() -> tuple[list[bytes], list[dict[str, Any]]]:
    """Use four valid class-covering fixtures plus small malformed records.

    The valid records are accepted synthetic fixtures, not excluded proof
    workspace data.  Only their exact request bytes are consumed.
    """
    with open(SUPPLEMENTAL_FIXTURES, encoding="utf-8") as handle:
        pack = json.load(handle)
    valid: list[bytes] = []
    valid_meta: list[dict[str, Any]] = []
    seen_classes: set[str] = set()
    for entry in pack["entries"]:
        behavior = entry["expected_response"]["output"]["result_object"]["behavior_class"]
        if behavior in seen_classes:
            continue
        raw = base64.b64decode(entry["semantic_request_jcs_lf_base64"], validate=True)
        if not raw.endswith(b"\n"):
            raise InvariantFailure("fixture request is not LF framed")
        valid.append(raw)
        valid_meta.append(
            {
                "entry_id": entry["entry_id"],
                "behavior_class": behavior,
                "request_sha256": _sha256(raw),
            }
        )
        seen_classes.add(behavior)
    required = {"VALID", "MALFORMED_OR_BOUNDARY", "BINDING_OR_CONFLICT", "OMISSION_OR_INCOMPLETE"}
    if seen_classes != required:
        raise InvariantFailure(
            "class-covering valid corpus unavailable",
            {"expected": sorted(required), "actual": sorted(seen_classes)},
        )
    malformed = [
        b"\n",
        b"{}\n",
        b"{]\n",
        b"\xff\n",
        b"null\n",
        b'{"a":1,"a":2}\n',
        b"[]\n",
    ]
    return valid + malformed, valid_meta


def _caller_requests(
    templates: list[bytes], caller_id: int, request_count: int, seed: int
) -> list[bytes]:
    """Build a replayable mixed stream with a valid record every 50 calls."""
    valid_count = 4
    malformed_count = len(templates) - valid_count
    if malformed_count <= 0:
        raise InvariantFailure("malformed request templates missing")
    rng = random.Random(seed ^ ((caller_id + 1) * 0x9E3779B97F4A7C15))
    requests: list[bytes] = []
    for index in range(request_count):
        if index % 50 == 0:
            template_index = (caller_id + index // 50) % valid_count
        else:
            template_index = valid_count + rng.randrange(malformed_count)
        requests.append(templates[template_index])
    return requests


def _request_order_sha256(requests: list[bytes]) -> str:
    digest = hashlib.sha256()
    for index, raw in enumerate(requests):
        digest.update(index.to_bytes(8, "big"))
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest().upper()


def _isolated_physical_record(
    raw: bytes, cache: dict[bytes, bytes], deadline: float | None = None
) -> bytes:
    """Return a cached one-record CUT observation for transport comparison only.

    These bytes are deliberately *not* a semantic expectation.  Semantic
    success is checked separately by projecting the audited envelope's
    ``sealed_response`` and comparing it with the clean-room oracle.
    """

    if raw in cache:
        return cache[raw]
    timeout = _remaining(deadline) if deadline is not None else DEFAULT_TIMEOUT_SECONDS
    result = subprocess.run(
        [sys.executable, "-B", str(RUNNER)],
        cwd=REPO,
        input=raw,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if result.returncode != 0 or result.stderr:
        raise InvariantFailure(
            "isolated physical comparator failed",
            {
                "kind": "physical_comparator_failure",
                "comparator": PHYSICAL_COMPARATOR,
                "raw_input_b64": base64.b64encode(raw).decode("ascii"),
                "raw_input_sha256": _sha256(raw),
                "exit_code": result.returncode,
                "stdout_sha256": _sha256(result.stdout),
                "stderr_b64": base64.b64encode(result.stderr[:4096]).decode("ascii"),
                "stderr_sha256": _sha256(result.stderr),
            },
        )
    if not result.stdout.endswith(b"\n") or len(result.stdout.splitlines(keepends=True)) != 1:
        raise InvariantFailure(
            "isolated physical comparator did not emit exactly one LF record",
            {
                "kind": "physical_comparator_framing",
                "comparator": PHYSICAL_COMPARATOR,
                "raw_input_sha256": _sha256(raw),
                "actual_b64": base64.b64encode(result.stdout[:4096]).decode("ascii"),
                "actual_sha256": _sha256(result.stdout),
            },
        )
    cache[raw] = result.stdout
    return result.stdout


def _physical_expected_output(
    requests: list[bytes], cache: dict[bytes, bytes], deadline: float | None = None
) -> bytes:
    """Concatenate isolated physical records without assigning semantics."""

    return b"".join(_isolated_physical_record(raw, cache, deadline) for raw in requests)


def _physical_cache_binding_sha256(cache: dict[bytes, bytes]) -> str:
    digest = hashlib.sha256()
    for raw in sorted(cache, key=lambda item: (_sha256(item), item)):
        output = cache[raw]
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
        digest.update(len(output).to_bytes(8, "big"))
        digest.update(output)
    return digest.hexdigest().upper()


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-JSON constant: {value}")


def _reject_json_float(value: str) -> None:
    raise ValueError(f"non-integer JSON number: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object member: {key}")
        result[key] = value
    return result


def _parse_audited_envelope(record: bytes) -> dict[str, Any]:
    """Strictly parse and independently canonical-validate one audited line."""

    if not record.endswith(b"\n") or len(record.splitlines(keepends=True)) != 1:
        raise InvariantFailure(
            "audited envelope is not exactly one LF-framed physical record",
            {
                "kind": "audited_envelope_framing",
                "actual_b64": base64.b64encode(record[:4096]).decode("ascii"),
                "actual_sha256": _sha256(record),
            },
        )
    try:
        text = record[:-1].decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
            parse_float=_reject_json_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise InvariantFailure(
            "audited envelope is not strict UTF-8 integer-domain JSON",
            {
                "kind": "audited_envelope_json",
                "actual_sha256": _sha256(record),
                "error": f"{type(error).__name__}: {error}",
            },
        ) from error
    if type(value) is not dict:
        raise InvariantFailure(
            "audited envelope root is not an object",
            {"kind": "audited_envelope_type", "actual_type": type(value).__name__},
        )
    actual_fields = frozenset(value)
    if actual_fields != AUDITED_FIELDS:
        raise InvariantFailure(
            "audited envelope fields differ from the frozen surface",
            {
                "kind": "audited_envelope_fields",
                "missing": sorted(AUDITED_FIELDS - actual_fields),
                "extra": sorted(actual_fields - AUDITED_FIELDS),
            },
        )
    if value["format_version"] != AUDITED_FORMAT_VERSION:
        raise InvariantFailure(
            "audited envelope format version differs",
            {
                "kind": "audited_envelope_version",
                "expected": AUDITED_FORMAT_VERSION,
                "actual": value["format_version"],
            },
        )
    if type(value["audit"]) is not dict or type(value["sealed_response"]) is not dict:
        raise InvariantFailure(
            "audited envelope object fields have invalid types",
            {
                "kind": "audited_envelope_type",
                "audit_type": type(value["audit"]).__name__,
                "sealed_response_type": type(value["sealed_response"]).__name__,
            },
        )
    if (
        type(value["audited_behavior_class"]) is not str
        or value["audited_behavior_class"] not in AUDITED_BEHAVIOR_CLASSES
        or type(value["exit_code"]) is not int
    ):
        raise InvariantFailure(
            "audited envelope scalar fields have invalid values",
            {
                "kind": "audited_envelope_type",
                "audited_behavior_class": value["audited_behavior_class"],
                "exit_code": value["exit_code"],
            },
        )
    audit_sha = value["audit_sha256"]
    audit_zeroed = dict(value)
    audit_zeroed["audit_sha256"] = "0" * 64
    recomputed_audit_sha = _sha256(jcs_bytes(audit_zeroed))
    if (
        type(audit_sha) is not str
        or len(audit_sha) != 64
        or any(character not in "0123456789ABCDEF" for character in audit_sha)
        or audit_sha != recomputed_audit_sha
    ):
        raise InvariantFailure(
            "audited envelope audit seal is invalid",
            {
                "kind": "audited_envelope_audit_seal",
                "declared": audit_sha,
                "recomputed": recomputed_audit_sha,
            },
        )
    canonical = jcs_bytes(value) + b"\n"
    if canonical != record:
        raise InvariantFailure(
            "audited envelope is not independent JCS plus LF",
            {
                "kind": "audited_envelope_canonicality",
                "expected_b64": base64.b64encode(canonical[:4096]).decode("ascii"),
                "expected_sha256": _sha256(canonical),
                "actual_b64": base64.b64encode(record[:4096]).decode("ascii"),
                "actual_sha256": _sha256(record),
            },
        )
    return value


def _audit_semantic_record(raw: bytes, record: bytes, oracle: FixtureOracle) -> bytes:
    """Validate an audited 0.4 envelope and return its canonical projection."""

    envelope = _parse_audited_envelope(record)
    audit = envelope["audit"]
    if audit.get("request_raw_sha256") != _sha256(raw):
        raise InvariantFailure(
            "audited envelope does not bind the physical request",
            {
                "kind": "audited_envelope_request_binding",
                "raw_input_b64": base64.b64encode(raw).decode("ascii"),
                "raw_input_sha256": _sha256(raw),
                "declared": audit.get("request_raw_sha256"),
            },
        )
    projected = jcs_bytes(envelope["sealed_response"]) + b"\n"
    expected = oracle.expected_record(raw)
    if projected != expected:
        raise InvariantFailure(
            "audited sealed_response diverged from the clean-room semantic oracle",
            {
                "kind": "semantic_oracle_divergence",
                "raw_input_b64": base64.b64encode(raw).decode("ascii"),
                "raw_input_sha256": _sha256(raw),
                "expected_b64": base64.b64encode(expected).decode("ascii"),
                "expected_sha256": _sha256(expected),
                "projected_b64": base64.b64encode(projected).decode("ascii"),
                "projected_sha256": _sha256(projected),
                "envelope_sha256": _sha256(record),
            },
        )
    sealed = envelope["sealed_response"]
    sealed_exit = sealed.get("exit_code")
    if envelope["exit_code"] != sealed_exit:
        raise InvariantFailure(
            "audited envelope exit_code disagrees with sealed_response",
            {
                "kind": "audited_envelope_semantics",
                "outer_exit_code": envelope["exit_code"],
                "sealed_exit_code": sealed_exit,
                "raw_input_sha256": _sha256(raw),
            },
        )
    if sealed_exit == 2:
        expected_behavior_class = "PROTOCOL_ERROR"
    else:
        output = sealed.get("output")
        result_object = output.get("result_object") if type(output) is dict else None
        expected_behavior_class = (
            result_object.get("behavior_class") if type(result_object) is dict else None
        )
    if envelope["audited_behavior_class"] != expected_behavior_class:
        raise InvariantFailure(
            "audited behavior class disagrees with sealed_response",
            {
                "kind": "audited_envelope_semantics",
                "outer_behavior_class": envelope["audited_behavior_class"],
                "sealed_behavior_class": expected_behavior_class,
                "raw_input_sha256": _sha256(raw),
            },
        )
    return projected


def _audit_semantic_outputs(
    inputs: dict[int, list[bytes]], outputs: dict[int, bytes], oracle: FixtureOracle
) -> dict[str, Any]:
    digest = hashlib.sha256()
    compared = 0
    for caller_id in sorted(inputs):
        records = outputs[caller_id].splitlines(keepends=True)
        if len(records) != len(inputs[caller_id]):
            raise InvariantFailure(
                "response count diverged before semantic projection",
                {
                    "kind": "semantic_response_count",
                    "caller_id": caller_id,
                    "expected": len(inputs[caller_id]),
                    "actual": len(records),
                },
            )
        for index, (raw, record) in enumerate(zip(inputs[caller_id], records)):
            projected = _audit_semantic_record(raw, record, oracle)
            digest.update(caller_id.to_bytes(4, "big"))
            digest.update(index.to_bytes(8, "big"))
            digest.update(len(projected).to_bytes(8, "big"))
            digest.update(projected)
            compared += 1
    return {
        "status": "PASS",
        "compared_audited_envelopes": compared,
        "projected_sealed_responses_sha256": digest.hexdigest().upper(),
    }


def _first_output_divergence(
    caller_id: int, requests: list[bytes], expected: bytes, actual: bytes
) -> dict[str, Any]:
    expected_lines = expected.splitlines(keepends=True)
    actual_lines = actual.splitlines(keepends=True)
    limit = min(len(expected_lines), len(actual_lines))
    index = next((i for i in range(limit) if expected_lines[i] != actual_lines[i]), limit)
    raw = requests[index] if index < len(requests) else b""
    expected_line = expected_lines[index] if index < len(expected_lines) else b""
    actual_line = actual_lines[index] if index < len(actual_lines) else b""
    return {
        "kind": "output_byte_divergence",
        "caller_id": caller_id,
        "request_index": index,
        "raw_input_b64": base64.b64encode(raw).decode("ascii"),
        "raw_input_sha256": _sha256(raw),
        "expected_b64": base64.b64encode(expected_line).decode("ascii"),
        "expected_sha256": _sha256(expected_line),
        "actual_b64": base64.b64encode(actual_line).decode("ascii"),
        "actual_sha256": _sha256(actual_line),
        "expected_response_count": len(expected_lines),
        "actual_response_count": len(actual_lines),
    }


def _framed_outputs_sha256(outputs: dict[int, bytes]) -> str:
    digest = hashlib.sha256()
    for caller_id in sorted(outputs):
        payload = outputs[caller_id]
        header = caller_id.to_bytes(4, "big") + len(payload).to_bytes(8, "big")
        digest.update(header)
        digest.update(payload)
    return digest.hexdigest().upper()


def _write_framed_outputs(path: pathlib.Path, outputs: dict[int, bytes]) -> str:
    with open(path, "wb") as handle:
        for caller_id in sorted(outputs):
            payload = outputs[caller_id]
            header = caller_id.to_bytes(4, "big") + len(payload).to_bytes(8, "big")
            handle.write(header)
            handle.write(payload)
    return _framed_outputs_sha256(outputs)


def _read_framed_outputs(path: pathlib.Path) -> dict[int, bytes]:
    outputs: dict[int, bytes] = {}
    with open(path, "rb") as handle:
        while True:
            header = handle.read(12)
            if not header:
                break
            if len(header) != 12:
                raise InvariantFailure("truncated output-spool header")
            caller_id = int.from_bytes(header[:4], "big")
            length = int.from_bytes(header[4:], "big")
            payload = handle.read(length)
            if len(payload) != length:
                raise InvariantFailure("truncated output-spool payload")
            if caller_id in outputs:
                raise InvariantFailure("duplicate caller in output spool")
            outputs[caller_id] = payload
    return outputs


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [
            ctypes.wintypes.DWORD,
            ctypes.wintypes.BOOL,
            ctypes.wintypes.DWORD,
        ]
        kernel32.OpenProcess.restype = ctypes.wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [
            ctypes.wintypes.HANDLE,
            ctypes.POINTER(ctypes.wintypes.DWORD),
        ]
        kernel32.GetExitCodeProcess.restype = ctypes.wintypes.BOOL
        kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
        kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        exit_code = ctypes.wintypes.DWORD()
        try:
            return bool(
                kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                and exit_code.value == 259  # STILL_ACTIVE
            )
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _windows_resource_snapshot(pids: set[int]) -> dict[str, Any]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    class ProcessMemoryCountersEx(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.wintypes.DWORD),
            ("PageFaultCount", ctypes.wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    class ThreadEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.wintypes.DWORD),
            ("cntUsage", ctypes.wintypes.DWORD),
            ("th32ThreadID", ctypes.wintypes.DWORD),
            ("th32OwnerProcessID", ctypes.wintypes.DWORD),
            ("tpBasePri", ctypes.wintypes.LONG),
            ("tpDeltaPri", ctypes.wintypes.LONG),
            ("dwFlags", ctypes.wintypes.DWORD),
        ]

    thread_counts = {pid: 0 for pid in pids}
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000004, 0)
    invalid = ctypes.c_void_p(-1).value
    if snapshot not in (0, invalid):
        entry = ThreadEntry32()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel32.Thread32First(snapshot, ctypes.byref(entry))
        while ok:
            owner = int(entry.th32OwnerProcessID)
            if owner in thread_counts:
                thread_counts[owner] += 1
            ok = kernel32.Thread32Next(snapshot, ctypes.byref(entry))
        kernel32.CloseHandle(snapshot)

    rss = 0
    handles = 0
    threads = 0
    sampled = 0
    unavailable: list[int] = []
    per_pid: dict[str, dict[str, int]] = {}
    for pid in sorted(pids):
        handle = kernel32.OpenProcess(0x1000 | 0x0400 | 0x0010, False, pid)
        if not handle:
            unavailable.append(pid)
            continue
        counters = ProcessMemoryCountersEx()
        counters.cb = ctypes.sizeof(counters)
        handle_count = ctypes.wintypes.DWORD()
        memory_ok = psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), ctypes.sizeof(counters)
        )
        handle_ok = kernel32.GetProcessHandleCount(handle, ctypes.byref(handle_count))
        kernel32.CloseHandle(handle)
        if not memory_ok or not handle_ok:
            unavailable.append(pid)
            continue
        row = {
            "rss_bytes": int(counters.WorkingSetSize),
            "peak_rss_bytes": int(counters.PeakWorkingSetSize),
            "handle_or_fd_count": int(handle_count.value),
            "thread_count": thread_counts.get(pid, 0),
        }
        per_pid[str(pid)] = row
        rss += row["rss_bytes"]
        handles += row["handle_or_fd_count"]
        threads += row["thread_count"]
        sampled += 1
    return {
        "method": "win32-ctypes",
        "requested_process_count": len(pids),
        "sampled_process_count": sampled,
        "rss_bytes": rss,
        "handle_or_fd_count": handles,
        "thread_count": threads,
        "unavailable_pids": unavailable,
        "per_pid": per_pid,
    }


def _proc_resource_snapshot(pids: set[int]) -> dict[str, Any]:
    rss = 0
    handles = 0
    threads = 0
    sampled = 0
    unavailable: list[int] = []
    per_pid: dict[str, dict[str, int]] = {}
    for pid in sorted(pids):
        proc = pathlib.Path("/proc") / str(pid)
        try:
            status = (proc / "status").read_text(encoding="utf-8", errors="replace")
            fd_count = len(list((proc / "fd").iterdir()))
        except (FileNotFoundError, PermissionError, OSError):
            unavailable.append(pid)
            continue
        values: dict[str, int] = {}
        for line in status.splitlines():
            if line.startswith("VmRSS:"):
                values["rss_bytes"] = int(line.split()[1]) * 1024
            elif line.startswith("Threads:"):
                values["thread_count"] = int(line.split()[1])
        values.setdefault("rss_bytes", 0)
        values.setdefault("thread_count", 0)
        values["handle_or_fd_count"] = fd_count
        per_pid[str(pid)] = values
        rss += values["rss_bytes"]
        handles += fd_count
        threads += values["thread_count"]
        sampled += 1
    return {
        "method": "procfs",
        "requested_process_count": len(pids),
        "sampled_process_count": sampled,
        "rss_bytes": rss,
        "handle_or_fd_count": handles,
        "thread_count": threads,
        "unavailable_pids": unavailable,
        "per_pid": per_pid,
    }


def _fallback_resource_snapshot(pids: set[int]) -> dict[str, Any]:
    import resource

    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss_scale = 1 if platform.system() == "Darwin" else 1024
    fd_count: int | None
    try:
        fd_count = len(list(pathlib.Path("/dev/fd").iterdir()))
    except OSError:
        fd_count = None
    return {
        "method": "stdlib-self-fallback",
        "requested_process_count": len(pids),
        "sampled_process_count": 1,
        "rss_bytes": int(usage.ru_maxrss) * rss_scale,
        "handle_or_fd_count": fd_count,
        "thread_count": threading.active_count(),
        "unavailable_pids": sorted(pids - {os.getpid()}),
        "per_pid": {},
        "limitation": "child RSS/thread/FD current values unavailable without non-stdlib tooling",
    }


def _resource_snapshot(extra_pids: list[int] | None = None) -> dict[str, Any]:
    pids = {os.getpid(), *(extra_pids or [])}
    if os.name == "nt":
        return _windows_resource_snapshot(pids)
    if pathlib.Path("/proc/self/status").exists():
        return _proc_resource_snapshot(pids)
    return _fallback_resource_snapshot(pids)


class ResourceSampler:
    """Sample aggregate worker + batch-child resources without steering work."""

    def __init__(self, extra_pids: Callable[[], list[int]]) -> None:
        self._extra_pids = extra_pids
        self._stop = threading.Event()
        self._samples: list[dict[str, Any]] = []
        self._thread: threading.Thread | None = None
        self.before = _resource_snapshot(extra_pids())

    def start(self) -> None:
        def sample() -> None:
            while not self._stop.wait(0.01):
                self._samples.append(_resource_snapshot(self._extra_pids()))

        self._thread = threading.Thread(target=sample, name="rr-resource-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._samples.append(_resource_snapshot(self._extra_pids()))
        after = _resource_snapshot(self._extra_pids())
        numeric = ("rss_bytes", "handle_or_fd_count", "thread_count", "requested_process_count")
        peak: dict[str, Any] = {"method": self.before["method"]}
        for field in numeric:
            values = [row.get(field) for row in self._samples if isinstance(row.get(field), int)]
            peak[field] = max(values) if values else None
        return {
            "before": self.before,
            "peak": peak,
            "after": after,
            "sample_count": len(self._samples),
            "sampling_interval_seconds": 0.01,
            "scheduling_nonclaim": "sampling observes resources; it is not an execution schedule",
        }


def _close_process_streams(process: subprocess.Popen[bytes]) -> None:
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


def _assert_physical_outputs(
    mode: str,
    inputs: dict[int, list[bytes]],
    physical_expected: dict[int, bytes],
    outputs: dict[int, bytes],
) -> None:
    """Fail on the first concurrent-vs-isolated physical byte mismatch."""

    for caller_id in sorted(inputs):
        actual = outputs.get(caller_id, b"")
        if actual == physical_expected[caller_id]:
            continue
        divergence = _first_output_divergence(
            caller_id,
            inputs[caller_id],
            physical_expected[caller_id],
            actual,
        )
        divergence.update(
            {
                "kind": "physical_transport_mismatch",
                "mode": mode,
                "comparator": PHYSICAL_COMPARATOR,
                "semantic_nonclaim": (
                    "The CUT-derived isolated comparator establishes only physical "
                    "transport parity, never semantic correctness."
                ),
            }
        )
        raise InvariantFailure(
            f"{mode} caller diverged from isolated physical rr_batch bytes",
            divergence,
        )


def _run_library_callers(
    inputs: dict[int, list[bytes]], physical_expected: dict[int, bytes], deadline: float
) -> tuple[dict[int, bytes], dict[str, Any]]:
    participant_count = len(inputs)
    barrier = threading.Barrier(participant_count + 1)
    cancel = threading.Event()
    sampler = ResourceSampler(lambda: [])

    def call(caller_id: int) -> bytes:
        barrier.wait(timeout=_remaining(deadline))
        if cancel.is_set():
            return b""
        source = io.BytesIO(b"".join(inputs[caller_id]))
        sink = io.BytesIO()
        exit_code = rr_batch.serve(source, sink)
        if exit_code != 0:
            raise InvariantFailure(
                "library batch caller returned nonzero",
                {"kind": "library_exit", "caller_id": caller_id, "exit_code": exit_code},
            )
        return sink.getvalue()

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=participant_count)
    futures = {executor.submit(call, caller_id): caller_id for caller_id in sorted(inputs)}
    try:
        sampler.start()
        barrier.wait(timeout=_remaining(deadline))
        done, pending = concurrent.futures.wait(futures, timeout=_remaining(deadline))
        if pending:
            cancel.set()
            raise InvariantFailure(
                "library caller deadlock/timeout",
                {"kind": "timeout", "pending_callers": sorted(futures[item] for item in pending)},
            )
        outputs = {futures[future]: future.result() for future in done}
    finally:
        cancel.set()
        executor.shutdown(wait=True, cancel_futures=True)
        resources = sampler.stop()
    _assert_physical_outputs("library", inputs, physical_expected, outputs)
    return outputs, resources


def _run_process_callers(
    inputs: dict[int, list[bytes]], physical_expected: dict[int, bytes], deadline: float
) -> tuple[dict[int, bytes], dict[str, Any]]:
    participant_count = len(inputs)
    barrier = threading.Barrier(participant_count + 1)
    registry = ProcessRegistry()
    sampler = ResourceSampler(registry.pids)

    def call(caller_id: int) -> bytes:
        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                [sys.executable, "-B", str(RUNNER)],
                cwd=REPO,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            registry.add(process)
            barrier.wait(timeout=_remaining(deadline))
            stdout, stderr = process.communicate(
                input=b"".join(inputs[caller_id]), timeout=_remaining(deadline)
            )
            if process.returncode != 0:
                raise InvariantFailure(
                    "process batch caller returned nonzero",
                    {
                        "kind": "process_exit",
                        "caller_id": caller_id,
                        "exit_code": process.returncode,
                        "stderr_b64": base64.b64encode(stderr[:4096]).decode("ascii"),
                        "stderr_sha256": _sha256(stderr),
                    },
                )
            if stderr:
                raise InvariantFailure(
                    "process batch caller wrote stderr",
                    {
                        "kind": "process_stderr",
                        "caller_id": caller_id,
                        "stderr_b64": base64.b64encode(stderr[:4096]).decode("ascii"),
                        "stderr_sha256": _sha256(stderr),
                    },
                )
            return stdout
        except BaseException:
            try:
                barrier.abort()
            except threading.BrokenBarrierError:
                pass
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=5.0)
            raise
        finally:
            if process is not None:
                _close_process_streams(process)
                registry.discard(process)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=participant_count)
    futures = {executor.submit(call, caller_id): caller_id for caller_id in sorted(inputs)}
    try:
        sampler.start()
        try:
            barrier.wait(timeout=_remaining(deadline))
        except threading.BrokenBarrierError:
            for future in futures:
                if future.done():
                    future.result()
            raise InvariantFailure("process startup barrier broke")
        done, pending = concurrent.futures.wait(futures, timeout=_remaining(deadline))
        if pending:
            cleanup = registry.terminate_all()
            raise InvariantFailure(
                "process caller deadlock/timeout",
                {
                    "kind": "timeout",
                    "pending_callers": sorted(futures[item] for item in pending),
                    "cleanup": cleanup,
                },
            )
        outputs = {futures[future]: future.result() for future in done}
    finally:
        registry.terminate_all()
        executor.shutdown(wait=True, cancel_futures=True)
        resources = sampler.stop()
    _assert_physical_outputs("process", inputs, physical_expected, outputs)
    return outputs, resources


def _cleanup_resource_check(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for field, allowance in (("thread_count", 0), ("handle_or_fd_count", 2)):
        first = before.get(field)
        last = after.get(field)
        if isinstance(first, int) and isinstance(last, int):
            checks[field] = {
                "before": first,
                "after": last,
                "allowance": allowance,
                "pass": last <= first + allowance,
            }
        else:
            checks[field] = {"before": first, "after": last, "pass": None}
    checks["pass"] = all(row.get("pass") is not False for row in checks.values() if isinstance(row, dict))
    return checks


def _library_cancellation_probe(
    participant_count: int,
    deadline: float,
    physical_cache: dict[bytes, bytes],
    oracle: FixtureOracle,
) -> dict[str, Any]:
    before = _resource_snapshot()
    start = threading.Barrier(participant_count + 1)
    acknowledged = threading.Barrier(participant_count + 1)
    cancel = threading.Event()
    counts = [0] * participant_count
    expected = _isolated_physical_record(b"\n", physical_cache, deadline)
    _audit_semantic_record(b"\n", expected, oracle)
    errors: list[str] = []

    def caller(caller_id: int) -> None:
        try:
            start.wait(timeout=_remaining(deadline))
            actual = rr_batch.response_bytes(b"\n")
            if actual != expected:
                errors.append(f"caller {caller_id} byte mismatch")
                return
            _audit_semantic_record(b"\n", actual, oracle)
            counts[caller_id] = 1
            acknowledged.wait(timeout=_remaining(deadline))
            # Wait on an explicit cancellation primitive instead of spinning.
            # This makes the probe acknowledgement-driven and prevents GIL
            # contention from delaying the controller's cancellation action.
            cancel.wait(timeout=_remaining(deadline))
        except BaseException as error:  # preserve as cancellation-probe evidence
            errors.append(f"caller {caller_id}: {type(error).__name__}: {error}")

    threads = [
        threading.Thread(target=caller, args=(caller_id,), name=f"rr-cancel-{caller_id}", daemon=True)
        for caller_id in range(participant_count)
    ]
    for thread in threads:
        thread.start()
    start.wait(timeout=_remaining(deadline))
    acknowledged.wait(timeout=_remaining(deadline))
    during = _resource_snapshot()
    cancel.set()
    for thread in threads:
        thread.join(timeout=_remaining(deadline))
    alive = [thread.name for thread in threads if thread.is_alive()]
    threads.clear()
    # The barriers/event are themselves Win32-handle owners on CPython.
    # Release the probe apparatus before taking the cleanup snapshot so the
    # measurement describes retained resources, not the active receipt code.
    del caller
    del start
    del acknowledged
    del cancel
    gc.collect()
    after = _resource_snapshot()
    cleanup = _cleanup_resource_check(before, after)
    if errors or alive or not cleanup["pass"] or any(count == 0 for count in counts):
        raise InvariantFailure(
            "library cancellation cleanup failed",
            {
                "kind": "cancellation_cleanup",
                "errors": errors,
                "alive_threads": alive,
                "processed_counts": counts,
                "resource_cleanup": cleanup,
            },
        )
    return {
        "barriers": ["all-callers-started", "one-response-acknowledged"],
        "cancellation_action": "threading.Event.set",
        "processed_min": min(counts),
        "processed_max": max(counts),
        "alive_threads_after": alive,
        "before": before,
        "during": during,
        "after": after,
        "resource_cleanup": cleanup,
        "physical_comparator": PHYSICAL_COMPARATOR,
        "semantic_oracle": "portability.oracle.FixtureOracle.expected_record",
        "pass": True,
    }


def _process_cancellation_probe(
    participant_count: int,
    deadline: float,
    physical_cache: dict[bytes, bytes],
    oracle: FixtureOracle,
) -> dict[str, Any]:
    before = _resource_snapshot()
    processes: list[subprocess.Popen[bytes]] = []
    expected = _isolated_physical_record(b"\n", physical_cache, deadline)
    _audit_semantic_record(b"\n", expected, oracle)
    acknowledgements: list[dict[str, Any]] = []
    try:
        for caller_id in range(participant_count):
            process = subprocess.Popen(
                [sys.executable, "-B", str(RUNNER)],
                cwd=REPO,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            processes.append(process)
            assert process.stdin is not None
            assert process.stdout is not None
            process.stdin.write(b"\n")
            process.stdin.flush()
            actual = process.stdout.readline()
            if actual != expected:
                raise InvariantFailure(
                    "process cancellation pre-ack divergence",
                    {
                        "kind": "cancellation_ack",
                        "caller_id": caller_id,
                        "raw_input_b64": "Cg==",
                        "expected_b64": base64.b64encode(expected).decode("ascii"),
                        "actual_b64": base64.b64encode(actual).decode("ascii"),
                    },
                )
            _audit_semantic_record(b"\n", actual, oracle)
            acknowledgements.append({"caller_id": caller_id, "pid": process.pid})
        during = _resource_snapshot([process.pid for process in processes])
        for process in processes:
            process.terminate()
        exit_codes: list[dict[str, Any]] = []
        for process in processes:
            try:
                exit_code = process.wait(timeout=_remaining(deadline))
            except subprocess.TimeoutExpired:
                process.kill()
                exit_code = process.wait(timeout=_remaining(deadline))
            exit_codes.append({"pid": process.pid, "exit_code": exit_code})
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                try:
                    process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    pass
            _close_process_streams(process)
    pids = [process.pid for process in processes]
    processes.clear()
    del process
    gc.collect()
    lingering = [pid for pid in pids if _process_alive(pid)]
    after = _resource_snapshot()
    cleanup = _cleanup_resource_check(before, after)
    if lingering or not cleanup["pass"]:
        raise InvariantFailure(
            "process cancellation cleanup failed",
            {
                "kind": "cancellation_cleanup",
                "lingering_pids": lingering,
                "resource_cleanup": cleanup,
            },
        )
    return {
        "barrier": "one-flushed-response-acknowledged-per-process",
        "cancellation_action": "Popen.terminate then bounded wait/kill fallback",
        "acknowledgements": acknowledgements,
        "exit_codes": exit_codes,
        "lingering_pids_after": lingering,
        "before": before,
        "during": during,
        "after": after,
        "resource_cleanup": cleanup,
        "physical_comparator": PHYSICAL_COMPARATOR,
        "semantic_oracle": "portability.oracle.FixtureOracle.expected_record",
        "pass": True,
    }


def _worker_run(args: argparse.Namespace) -> int:
    started = time.monotonic()
    deadline = started + args.worker_timeout
    result: dict[str, Any] = {
        "format_version": "RR-CONCURRENCY-WORKER-3",
        "mode": args.worker_mode,
        "participants": args.worker_participants,
        "requests_per_caller": args.worker_requests,
        "seed": args.seed,
        "schedule": {
            "caller_order": list(range(args.worker_participants)),
            "start_barrier": "all-callers-ready",
            "input_generation": "valid-every-50; otherwise seeded malformed selection",
            "os_interleaving": "uncontrolled stress dimension",
        },
        "runtime": _runtime_receipt(),
        "status": "INVARIANT_FAILURE",
    }
    try:
        templates, valid_meta = _load_templates()
        inputs = {
            caller_id: _caller_requests(
                templates, caller_id, args.worker_requests, args.seed
            )
            for caller_id in range(args.worker_participants)
        }
        oracle = FixtureOracle()
        oracle_validation = oracle.validation_receipt()
        physical_cache: dict[bytes, bytes] = {}
        physical_expected = {
            caller_id: _physical_expected_output(requests, physical_cache, deadline)
            for caller_id, requests in inputs.items()
        }
        if args.worker_mode == "library":
            outputs, resources = _run_library_callers(inputs, physical_expected, deadline)
        elif args.worker_mode == "process":
            outputs, resources = _run_process_callers(inputs, physical_expected, deadline)
        else:
            raise InvariantFailure(f"unknown worker mode: {args.worker_mode}")
        unique_records = sorted(
            {raw for requests in inputs.values() for raw in requests}, key=_sha256
        )
        semantic_audit = _audit_semantic_outputs(inputs, outputs, oracle)
        expected_sha256 = _framed_outputs_sha256(physical_expected)
        actual_sha256 = _framed_outputs_sha256(outputs)
        if expected_sha256 != actual_sha256:
            raise InvariantFailure(
                "aggregate physical transport comparison failed",
                {
                    "kind": "physical_transport_mismatch",
                    "comparator": PHYSICAL_COMPARATOR,
                    "expected_sha256": expected_sha256,
                    "actual_sha256": actual_sha256,
                    "unique_input_records": len(unique_records),
                },
            )
        cancellation = None
        if args.worker_cancellation:
            if args.worker_mode == "library":
                cancellation = _library_cancellation_probe(
                    args.worker_participants, deadline, physical_cache, oracle
                )
            else:
                cancellation = _process_cancellation_probe(
                    args.worker_participants, deadline, physical_cache, oracle
                )
        spool = pathlib.Path(args.worker_spool).resolve()
        if spool.parent != pathlib.Path(args.worker_spool_parent).resolve():
            raise InvariantFailure("worker spool escaped controller temp directory")
        output_sha256 = _write_framed_outputs(spool, outputs)
        caller_receipts = []
        for caller_id in sorted(outputs):
            lines = outputs[caller_id].splitlines(keepends=True)
            if len(lines) != args.worker_requests:
                raise InvariantFailure(
                    "response count diverged",
                    _first_output_divergence(
                        caller_id,
                        inputs[caller_id],
                        physical_expected[caller_id],
                        outputs[caller_id],
                    ),
                )
            caller_receipts.append(
                {
                    "caller_id": caller_id,
                    "request_count": len(inputs[caller_id]),
                    "response_count": len(lines),
                    "request_order_sha256": _request_order_sha256(inputs[caller_id]),
                    "output_order_sha256": _sha256(outputs[caller_id]),
                    "output_bytes": len(outputs[caller_id]),
                }
            )
        result.update(
            {
                "status": "PASS",
                "valid_fixture_inputs": valid_meta,
                "caller_receipts": caller_receipts,
                "aggregate_framed_output_sha256": output_sha256,
                "physical_transport_comparator": {
                    "kind": PHYSICAL_COMPARATOR,
                    "source": "grounded-0_4/rr_batch.py, one input record per fresh process",
                    "cache_scope": "one worker run, keyed by exact raw input bytes",
                    "expected_sha256": expected_sha256,
                    "actual_sha256": actual_sha256,
                    "compared_response_lines": sum(len(items) for items in inputs.values()),
                    "unique_input_records": len(unique_records),
                    "isolated_binding_sha256": _physical_cache_binding_sha256(physical_cache),
                    "semantic_nonclaim": (
                        "CUT-derived isolated bytes establish physical-line transport parity "
                        "only; they are not semantic expected results."
                    ),
                },
                "semantic_oracle": {
                    "source": "portability.oracle.FixtureOracle.expected_record",
                    "projection": "independent JCS(sealed_response) plus LF",
                    "envelope_format_version": AUDITED_FORMAT_VERSION,
                    "envelope_validation": (
                        "strict UTF-8 integer-domain JSON; exact top-level fields and types; "
                        "audit seal; independent whole-envelope JCS+LF canonicality; "
                        "request hash binding"
                    ),
                    "fixture_binding_sha256": oracle_validation["fixture_binding_sha256"],
                    **semantic_audit,
                },
                "resources": resources,
                "cancellation": cancellation,
                "elapsed_seconds": time.monotonic() - started,
            }
        )
        print(_json_bytes(result).decode("utf-8"))
        return 0
    except BaseException as error:  # the controller needs a bounded receipt for every stop
        if _is_host_ceiling(error):
            result["status"] = "HOST_CEILING"
            result["stop"] = _host_ceiling_detail(error)
            exit_code = 2
        elif isinstance(error, HostCeiling):
            result["status"] = "HOST_CEILING"
            result["stop"] = {"kind": "host_resource_ceiling", "message": str(error)}
            exit_code = 2
        else:
            result["status"] = "INVARIANT_FAILURE"
            result["stop"] = {
                "kind": "invariant_failure",
                "exception_type": type(error).__name__,
                "message": str(error),
                "divergence": error.divergence if isinstance(error, InvariantFailure) else None,
                "traceback": traceback.format_exc(limit=20),
            }
            exit_code = 1
        result["elapsed_seconds"] = time.monotonic() - started
        print(_json_bytes(result).decode("utf-8"))
        return exit_code


def _decode_worker_result(stdout: bytes) -> dict[str, Any]:
    lines = [line for line in stdout.decode("utf-8", errors="replace").splitlines() if line.strip()]
    if not lines:
        raise InvariantFailure("worker emitted no receipt")
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as error:
        raise InvariantFailure(
            "worker receipt was not JSON",
            {
                "kind": "worker_protocol",
                "stdout_sha256": _sha256(stdout),
                "stdout_tail_b64": base64.b64encode(stdout[-4096:]).decode("ascii"),
                "decode_error": str(error),
            },
        ) from error


def _kill_controller_worker(process: subprocess.Popen[bytes]) -> dict[str, Any]:
    if process.poll() is None:
        process.terminate()
        try:
            exit_code = process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                exit_code = process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                exit_code = None
    else:
        exit_code = process.returncode
    return {"pid": process.pid, "exit_code": exit_code}


def _invoke_worker(
    mode: str,
    participants: int,
    request_count: int,
    seed: int,
    deadline: float,
    spool: pathlib.Path,
    spool_parent: pathlib.Path,
    cancellation: bool,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-B",
        str(pathlib.Path(__file__).resolve()),
        "--worker-mode",
        mode,
        "--worker-participants",
        str(participants),
        "--worker-requests",
        str(request_count),
        "--worker-timeout",
        str(_remaining(deadline)),
        "--worker-spool",
        str(spool),
        "--worker-spool-parent",
        str(spool_parent),
        "--seed",
        str(seed),
    ]
    if cancellation:
        command.append("--worker-cancellation")
    try:
        process = subprocess.Popen(
            command,
            cwd=REPO,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        if _is_host_ceiling(error):
            return {"status": "HOST_CEILING", "stop": _host_ceiling_detail(error)}
        raise
    try:
        stdout, stderr = process.communicate(timeout=_remaining(deadline))
    except subprocess.TimeoutExpired:
        cleanup = _kill_controller_worker(process)
        return {
            "status": "INVARIANT_FAILURE",
            "stop": {
                "kind": "timeout",
                "message": "worker exceeded the shared 120-second level deadline",
                "cleanup": cleanup,
            },
        }
    result = _decode_worker_result(stdout)
    result["worker_process_exit"] = process.returncode
    result["worker_stderr_sha256"] = _sha256(stderr)
    result["worker_stderr_bytes"] = len(stderr)
    if stderr:
        result["worker_stderr_b64"] = base64.b64encode(stderr[:4096]).decode("ascii")
    if process.returncode not in (0, 1, 2):
        result["status"] = "INVARIANT_FAILURE"
        result["stop"] = {
            "kind": "worker_exit",
            "exit_code": process.returncode,
            "stderr_sha256": _sha256(stderr),
        }
    return result


def _compare_spools(
    first: pathlib.Path, second: pathlib.Path, participants: int
) -> dict[str, Any] | None:
    if first.stat().st_size == second.stat().st_size:
        with open(first, "rb") as left, open(second, "rb") as right:
            while True:
                a = left.read(1024 * 1024)
                b = right.read(1024 * 1024)
                if a != b:
                    break
                if not a:
                    return None
    left_outputs = _read_framed_outputs(first)
    right_outputs = _read_framed_outputs(second)
    for caller_id in range(participants):
        first_bytes = left_outputs.get(caller_id, b"")
        second_bytes = right_outputs.get(caller_id, b"")
        if first_bytes != second_bytes:
            first_lines = first_bytes.splitlines(keepends=True)
            second_lines = second_bytes.splitlines(keepends=True)
            limit = min(len(first_lines), len(second_lines))
            index = next((i for i in range(limit) if first_lines[i] != second_lines[i]), limit)
            a = first_lines[index] if index < len(first_lines) else b""
            b = second_lines[index] if index < len(second_lines) else b""
            return {
                "kind": "identical_seed_byte_mismatch",
                "caller_id": caller_id,
                "response_index": index,
                "run_1_b64": base64.b64encode(a).decode("ascii"),
                "run_1_sha256": _sha256(a),
                "run_2_b64": base64.b64encode(b).decode("ascii"),
                "run_2_sha256": _sha256(b),
            }
    return {"kind": "spool_framing_mismatch"}


def _run_paired_level(
    mode: str,
    participants: int,
    request_count: int,
    seed: int,
    timeout_seconds: float,
    temp_dir: pathlib.Path,
) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + timeout_seconds
    runs: list[dict[str, Any]] = []
    spools: list[pathlib.Path] = []
    for repeat in (1, 2):
        spool = temp_dir / f"{mode}-p{participants}-r{request_count}-repeat{repeat}.bin"
        result = _invoke_worker(
            mode,
            participants,
            request_count,
            seed,
            deadline,
            spool,
            temp_dir,
            cancellation=repeat == 2,
        )
        result["repeat"] = repeat
        runs.append(result)
        if result.get("status") != "PASS":
            return {
                "mode": mode,
                "participants": participants,
                "requests_per_caller": request_count,
                "timeout_seconds": timeout_seconds,
                "status": result.get("status", "INVARIANT_FAILURE"),
                "runs": runs,
                "elapsed_seconds": time.monotonic() - started,
            }
        if not spool.is_file():
            return {
                "mode": mode,
                "participants": participants,
                "requests_per_caller": request_count,
                "timeout_seconds": timeout_seconds,
                "status": "INVARIANT_FAILURE",
                "runs": runs,
                "stop": {"kind": "worker_protocol", "message": "worker output spool missing"},
                "elapsed_seconds": time.monotonic() - started,
            }
        spools.append(spool)
    mismatch = _compare_spools(spools[0], spools[1], participants)
    if mismatch is not None:
        return {
            "mode": mode,
            "participants": participants,
            "requests_per_caller": request_count,
            "timeout_seconds": timeout_seconds,
            "status": "INVARIANT_FAILURE",
            "runs": runs,
            "stop": {"kind": "invariant_failure", "divergence": mismatch},
            "elapsed_seconds": time.monotonic() - started,
        }
    return {
        "mode": mode,
        "participants": participants,
        "requests_per_caller": request_count,
        "total_requests_per_repeat": participants * request_count,
        "timeout_seconds": timeout_seconds,
        "status": "PASS",
        "identical_seed_runs": 2,
        "byte_match": True,
        "aggregate_framed_output_sha256": runs[0]["aggregate_framed_output_sha256"],
        "runs": runs,
        "elapsed_seconds": time.monotonic() - started,
    }


def _git_receipt() -> dict[str, Any]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    status = subprocess.run(
        ["git", "status", "--short"], cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return {
        "head": head.stdout.decode("ascii", errors="replace").strip() if head.returncode == 0 else None,
        "head_exit": head.returncode,
        "clean": status.returncode == 0 and status.stdout == b"",
        "status_exit": status.returncode,
        "status_sha256": _sha256(status.stdout),
    }


def _free_threaded_candidates() -> list[list[str]]:
    candidates: list[list[str]] = []
    if os.name == "nt":
        candidates.append(["py", "-3.14t"])
    candidates.extend([["python3.14t"], ["python3.14-freethreaded"]])
    return candidates


def _discover_free_threaded() -> tuple[list[str] | None, dict[str, Any]]:
    probes: list[dict[str, Any]] = []
    code = (
        "import json,sys; "
        "f=getattr(sys,'_is_gil_enabled',None); "
        "print(json.dumps({'version':sys.version,'api':callable(f),'gil':f() if callable(f) else None}))"
    )
    for command in _free_threaded_candidates():
        try:
            result = subprocess.run(
                command + ["-B", "-c", code],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15.0,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            probes.append({"command": command, "status": type(error).__name__, "message": str(error)})
            continue
        parsed = None
        if result.returncode == 0:
            try:
                parsed = json.loads(result.stdout.decode("utf-8"))
            except json.JSONDecodeError:
                parsed = None
        probes.append(
            {
                "command": command,
                "exit_code": result.returncode,
                "stdout_sha256": _sha256(result.stdout),
                "stderr_sha256": _sha256(result.stderr),
                "receipt": parsed,
            }
        )
        if parsed and parsed.get("api") is True and parsed.get("gil") is False:
            return command, {"status": "AVAILABLE", "probes": probes, "selected": command}
    return None, {"status": "INFRA_UNAVAILABLE", "probes": probes, "selected": None}


def _write_receipt(path: pathlib.Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(payload, encoding="utf-8", newline="\n")


def _run_external_free_threaded(
    prefix: list[str], args: argparse.Namespace, receipt_path: pathlib.Path
) -> dict[str, Any]:
    child_receipt = receipt_path.with_name(receipt_path.stem + "-cpython-3.14t.json")
    command = prefix + [
        "-B",
        str(pathlib.Path(__file__).resolve()),
        "--levels",
        "1,2,4,8",
        "--requests",
        str(args.requests),
        "--soak-requests",
        str(args.soak_requests),
        "--timeout",
        str(args.timeout),
        "--seed",
        str(args.seed),
        "--attempt",
        str(args.attempt),
        "--runtime-label",
        "cpython-3.14t",
        "--receipt",
        str(child_receipt),
        "--no-free-threaded",
    ]
    if args.skip_soak:
        command.append("--skip-soak")
    result = subprocess.run(
        command,
        cwd=REPO,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "command": command,
        "exit_code": result.returncode,
        "stdout_sha256": _sha256(result.stdout),
        "stderr_sha256": _sha256(result.stderr),
        "receipt_path": str(child_receipt.relative_to(REPO)),
        "receipt_exists": child_receipt.is_file(),
        "receipt_sha256": _sha256(child_receipt.read_bytes()) if child_receipt.is_file() else None,
    }


def _safe_remove_temp(temp_dir: pathlib.Path) -> None:
    resolved = temp_dir.resolve()
    if resolved.parent != HERE.resolve() or not resolved.name.startswith(".rr-concurrency-"):
        raise InvariantFailure(f"refusing to remove unexpected temp path: {resolved}")
    shutil.rmtree(resolved)


def _controller_run(args: argparse.Namespace) -> int:
    if not 1 <= args.attempt <= 3:
        raise SystemExit("--attempt must be between 1 and the charter ceiling of 3")
    levels = tuple(int(item) for item in args.levels.split(",") if item)
    if not levels or any(level not in DEFAULT_LEVELS for level in levels):
        raise SystemExit("--levels must be a nonempty subset of 1,2,4,8,16,32")
    if tuple(sorted(set(levels))) != levels:
        raise SystemExit("--levels must be unique and ascending")
    if args.requests > DEFAULT_REQUESTS:
        raise SystemExit("the normative request bound may not be raised above 200")
    if args.soak_requests > DEFAULT_SOAK_REQUESTS:
        raise SystemExit("the soak request bound may not be raised above 1000")
    if args.timeout > DEFAULT_TIMEOUT_SECONDS:
        raise SystemExit("the per-level timeout may not be raised above 120 seconds")
    if args.requests <= 0 or args.soak_requests <= 0 or args.timeout <= 0:
        raise SystemExit("request counts and timeout must be positive")

    receipt_path = pathlib.Path(args.receipt).resolve()
    if HERE.resolve() not in receipt_path.parents:
        raise SystemExit("receipt path must remain under portability/concurrency")
    started = time.monotonic()
    receipt: dict[str, Any] = {
        "format_version": "RR-CONCURRENCY-LADDER-3",
        "treatment_exposed": True,
        "treatment_notice": (
            "This lane must never author future blinded worlds, oracle, gold, or renderer."
        ),
        "runtime_label": args.runtime_label,
        "runtime": _runtime_receipt(),
        "git": _git_receipt(),
        "bounds": {
            "levels": list(levels),
            "requests_per_caller": args.requests,
            "soak_requests_per_caller": args.soak_requests,
            "soak_highest_passing_levels": 2,
            "timeout_seconds_per_mode_level_including_two_runs_and_cancellation": args.timeout,
            "identical_seed_runs_per_level": 2,
            "seed": args.seed,
            "modes": ["library", "process"],
        },
        "attempt": args.attempt,
        "levels": [],
        "soaks": [],
        "status": "RUNNING",
        "nonclaims": [
            "No efficacy, novelty, security, fuzzing-completeness, external-standard, or universal-portability claim.",
            "OS thread/process interleavings are sampled stress, not exhaustively enumerated schedules.",
            "Isolated accepted rr_batch bytes are a physical transport comparator only and make no semantic claim.",
            "Semantic expectations come only from independent projection of each audited envelope's sealed_response through the clean-room FixtureOracle API.",
        ],
    }
    temp_dir = pathlib.Path(tempfile.mkdtemp(prefix=".rr-concurrency-", dir=HERE))
    exit_code = 0
    highest_passing: list[int] = []
    try:
        stop = False
        for participants in levels:
            level_receipt = {"participants": participants, "modes": [], "status": "PASS"}
            for mode in ("library", "process"):
                case = _run_paired_level(
                    mode,
                    participants,
                    args.requests,
                    args.seed,
                    args.timeout,
                    temp_dir,
                )
                level_receipt["modes"].append(case)
                if case["status"] != "PASS":
                    level_receipt["status"] = case["status"]
                    receipt["stop"] = {
                        "phase": "normative",
                        "participants": participants,
                        "mode": mode,
                        "status": case["status"],
                    }
                    stop = True
                    if case["status"] == "INVARIANT_FAILURE":
                        exit_code = 1
                    break
            receipt["levels"].append(level_receipt)
            if stop:
                break
            highest_passing.append(participants)

        if not stop and not args.skip_soak:
            for participants in highest_passing[-2:]:
                soak_receipt = {"participants": participants, "modes": [], "status": "PASS"}
                for mode in ("library", "process"):
                    case = _run_paired_level(
                        mode,
                        participants,
                        args.soak_requests,
                        args.seed,
                        args.timeout,
                        temp_dir,
                    )
                    soak_receipt["modes"].append(case)
                    if case["status"] != "PASS":
                        soak_receipt["status"] = case["status"]
                        receipt["stop"] = {
                            "phase": "soak",
                            "participants": participants,
                            "mode": mode,
                            "status": case["status"],
                        }
                        stop = True
                        if case["status"] == "INVARIANT_FAILURE":
                            exit_code = 1
                        break
                receipt["soaks"].append(soak_receipt)
                if stop:
                    break

        receipt["completed_normative_levels"] = highest_passing
        receipt["highest_passing_level"] = highest_passing[-1] if highest_passing else None
        receipt["ceiling_stopped"] = bool(
            receipt.get("stop", {}).get("status") == "HOST_CEILING"
        )
        if exit_code:
            receipt["status"] = "INVARIANT_FAILURE"
        elif receipt["ceiling_stopped"]:
            receipt["status"] = "CEILING_STOPPED"
        else:
            receipt["status"] = "PASS"

        if not args.no_free_threaded and receipt["status"] == "PASS":
            prefix, discovery = _discover_free_threaded()
            receipt["free_threaded_3_14t"] = discovery
            if prefix is not None:
                external = _run_external_free_threaded(prefix, args, receipt_path)
                receipt["free_threaded_3_14t"]["run"] = external
                if external["exit_code"] != 0:
                    receipt["status"] = "INVARIANT_FAILURE"
                    receipt["stop"] = {
                        "phase": "free-threaded-3.14t",
                        "status": "INVARIANT_FAILURE",
                    }
                    exit_code = 1
        elif args.no_free_threaded:
            receipt["free_threaded_3_14t"] = {"status": "NOT_REQUESTED_BY_CONTROLLER"}
    except BaseException as error:
        receipt["status"] = "INVARIANT_FAILURE"
        receipt["stop"] = {
            "phase": "controller",
            "exception_type": type(error).__name__,
            "message": str(error),
            "divergence": error.divergence if isinstance(error, InvariantFailure) else None,
            "traceback": traceback.format_exc(limit=20),
        }
        exit_code = 1
    finally:
        receipt["elapsed_seconds"] = time.monotonic() - started
        _write_receipt(receipt_path, receipt)
        _safe_remove_temp(temp_dir)
    print(
        f"concurrency ladder: status={receipt['status']} "
        f"completed={receipt.get('completed_normative_levels', [])} "
        f"receipt={receipt_path}"
    )
    return exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--levels", default=",".join(map(str, DEFAULT_LEVELS)))
    parser.add_argument("--requests", type=int, default=DEFAULT_REQUESTS)
    parser.add_argument("--soak-requests", type=int, default=DEFAULT_SOAK_REQUESTS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--skip-soak", action="store_true")
    parser.add_argument("--no-free-threaded", action="store_true")
    parser.add_argument("--runtime-label", default="normative-host")
    parser.add_argument(
        "--receipt", default=str(HERE / "receipts" / "latest.json")
    )

    # Internal worker protocol.  The controller is the supported entry point.
    parser.add_argument("--worker-mode", choices=("library", "process"))
    parser.add_argument("--worker-participants", type=int)
    parser.add_argument("--worker-requests", type=int)
    parser.add_argument("--worker-timeout", type=float)
    parser.add_argument("--worker-spool")
    parser.add_argument("--worker-spool-parent")
    parser.add_argument("--worker-cancellation", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.worker_mode:
        required = (
            args.worker_participants,
            args.worker_requests,
            args.worker_timeout,
            args.worker_spool,
            args.worker_spool_parent,
        )
        if any(value is None for value in required):
            raise SystemExit("incomplete internal worker arguments")
        return _worker_run(args)
    return _controller_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
