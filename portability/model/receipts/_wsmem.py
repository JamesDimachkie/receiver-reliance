"""Peak-working-set probe for the additive post-F-MODEL-003 precondition drivers.

Authored as new evidence tooling for the post-F-MODEL-003 N=48 run; it is not
part of finite model M and nothing in the model imports it.  Reads the OS-tracked
running maximum (``PROCESS_MEMORY_COUNTERS.PeakWorkingSetSize``), so a single
late sample is a true peak rather than an instantaneous reading.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes


class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


_CURRENT_PROCESS = ctypes.c_void_p(-1)

try:
    _PSAPI = ctypes.WinDLL("psapi", use_last_error=True)
    _PSAPI.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_PROCESS_MEMORY_COUNTERS),
        wintypes.DWORD,
    ]
    _PSAPI.GetProcessMemoryInfo.restype = wintypes.BOOL
except Exception:  # pragma: no cover - probe is best effort
    _PSAPI = None


def peak_working_set_bytes() -> int | None:
    """Return this process's OS-tracked peak working set, or None if unavailable."""
    if _PSAPI is None:
        return None
    try:
        counters = _PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        if not _PSAPI.GetProcessMemoryInfo(
            _CURRENT_PROCESS, ctypes.byref(counters), counters.cb
        ):
            return None
        return int(counters.PeakWorkingSetSize)
    except Exception:  # pragma: no cover - probe is best effort
        return None


def peak_mib() -> str:
    value = peak_working_set_bytes()
    if value is None:
        return "unavailable"
    return f"{value / (1024 * 1024):.1f} MiB"
