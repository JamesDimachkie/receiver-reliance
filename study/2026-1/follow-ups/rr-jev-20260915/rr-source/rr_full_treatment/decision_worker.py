"""One fresh-process arm invocation with out-of-band execution observation.

The profile hook records actual calls/returns without changing their arguments
or results. It is a controller observation under the local honest-host model,
not resistance to an administrator or proof of the source observations' truth.
"""
from __future__ import annotations

import base64
import importlib
import json
from pathlib import Path
import sys
import time

from .host_facts import canonical, sha


def state_bytes(arm: str) -> bytes:
    module = "S" if arm in ("S1", "S4") else arm
    if module not in ("U", "S", "R"):
        raise ValueError("Unregistered arm")
    state = {"format": f"RR-STUDY-TREATMENT-STATE-{module}-5"}
    if module == "S":
        state["operating_threshold"] = int(arm[1:])
    return canonical(state)


def invoke(package: str, arm: str, common: bytes, state: bytes, observe=True) -> dict:
    if package not in ("a", "b") or arm not in ("U", "S1", "S4", "R"):
        raise ValueError("Unregistered package or arm")
    module_id = "s" if arm.startswith("S") else arm.lower()
    module = importlib.import_module(f"rr_full_treatment.runtime_{package}.{module_id}")
    output_module = importlib.import_module(f"rr_full_treatment.runtime_{package}.common." +
                                            ("result" if package == "a" else "decision"))
    output_code = (output_module.decision_bytes if package == "a" else output_module.build).__code__
    engine_code = None
    if arm == "R":
        import receiver_reliance
        engine_code = receiver_reliance.decide_audited.__code__
    engine_calls, constructions = [], []
    pending = {}

    def profile(frame, event, value):
        if frame.f_code == engine_code:
            if event == "call":
                request = frame.f_locals["request"]
                if type(request) is not bytes:
                    raise RuntimeError("The actual engine invocation was not bound to raw request bytes")
                pending[id(frame)] = {"request_b64": base64.b64encode(request).decode(),
                                      "request_sha256": sha(request)}
            elif event == "return":
                item = pending.pop(id(frame))
                item["returned_envelope"] = value
                engine_calls.append(item)
        elif frame.f_code == output_code and event == "return":
            local = frame.f_locals
            evidence = {key: local[key] for key in
                        ("code", "module", "occurrence", "pointer", "semantic_evidence", "stage")}
            constructions.append({"evidence": evidence, "output_sha256": sha(value)})

    start_wall, start_cpu = time.perf_counter_ns(), time.process_time_ns()
    if observe:
        if sys.getprofile() is not None:
            raise RuntimeError("Unregistered profile hook already active")
        sys.setprofile(profile)
    try:
        output = module.decide(common, state)
    finally:
        sys.setprofile(None)
    result = {"output_b64": base64.b64encode(output).decode(), "output_sha256": sha(output),
              "common_sha256": sha(common), "state_sha256": sha(state),
              "wall_ns": time.perf_counter_ns()-start_wall, "cpu_ns": time.process_time_ns()-start_cpu,
              "package": package, "arm": arm, "observed": observe,
              "engine_calls": engine_calls, "constructions": constructions,
              "runtime_imports": sorted(name for name in sys.modules if name.startswith("rr_full_treatment.runtime_"))}
    if pending:
        raise RuntimeError("An observed engine call did not return")
    return result


def main():
    request = json.loads(sys.stdin.buffer.read(2_000_000))
    result = invoke(request["package"], request["arm"],
                    base64.b64decode(request["common_b64"], validate=True),
                    base64.b64decode(request["state_b64"], validate=True), request.get("observe", True))
    sys.stdout.buffer.write(canonical(result))


if __name__ == "__main__":
    main()
