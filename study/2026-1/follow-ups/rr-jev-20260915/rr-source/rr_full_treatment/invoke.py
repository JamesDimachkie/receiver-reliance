"""Controller-side fresh-process invocation. This module imports no arm."""
import base64
import json
from pathlib import Path
import subprocess
import sys
import time

from .host_facts import canonical

ROOT = Path(__file__).resolve().parents[1]


def run(package, arm, common, state, *, observe=True):
    request = canonical({"package": package, "arm": arm, "observe": observe,
                         "common_b64": base64.b64encode(common).decode(),
                         "state_b64": base64.b64encode(state).decode()})
    started = time.perf_counter_ns()
    process = subprocess.run([sys.executable, "-B", "-m", "rr_full_treatment.decision_worker"],
                             input=request, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             cwd=ROOT, timeout=30, check=False)
    if process.returncode or process.stderr:
        raise RuntimeError(f"Arm worker failed: exit {process.returncode}, stderr {process.stderr[:1000]!r}")
    result = json.loads(process.stdout)
    result["controller_wall_ns"] = time.perf_counter_ns() - started
    return result
