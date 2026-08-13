from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from rr2 import Implementation, jcs, sha256_upper  # noqa: E402


SEED = 0xB1C0DE40
TOOL_ID = 5
REQUIRED_STEERING_CODE_OBJECTS = frozenset({
    "_dispatch",
    "_eval_atomic",
    "_execute",
    "_parse",
    "classify",
    "eval_predicate",
    "schema_errors",
})


def steering_requirements(monitored_names, observed_names):
    monitored = set(monitored_names)
    observed = set(observed_names)
    missing_monitored = sorted(REQUIRED_STEERING_CODE_OBJECTS - monitored)
    missing_observed = sorted(REQUIRED_STEERING_CODE_OBJECTS - observed)
    return missing_monitored, missing_observed


class BinaryConsole:
    def __init__(self, raw: bytes = b""):
        self.buffer = io.BytesIO(raw)


class BranchCoverage:
    def __init__(self, reference_root: Path):
        self.reference_root = str(reference_root.resolve()).lower()
        self.edges: set[tuple[str, str, int, int]] = set()
        self.events = 0
        self.code_objects: set[tuple[str, str]] = set()

    def callback(self, code, from_offset: int, to_offset: int):
        filename = str(code.co_filename).lower()
        if filename.startswith(self.reference_root):
            relative = str(Path(code.co_filename).resolve().relative_to(Path(self.reference_root))).replace("\\", "/")
            token = (relative, code.co_name, from_offset, to_offset)
            self.edges.add(token)
            self.code_objects.add((relative, code.co_name))
            self.events += 1

    def start(self, code_objects):
        sys.monitoring.use_tool_id(TOOL_ID, "rr2-reference-branch-coverage")
        sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.BRANCH, self.callback)
        sys.monitoring.set_events(TOOL_ID, sys.monitoring.events.NO_EVENTS)
        for code in code_objects:
            sys.monitoring.set_local_events(TOOL_ID, code, sys.monitoring.events.BRANCH)

    def stop(self):
        sys.monitoring.set_events(TOOL_ID, sys.monitoring.events.NO_EVENTS)
        sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.BRANCH, None)
        sys.monitoring.free_tool_id(TOOL_ID)

    def digest(self) -> str:
        records = [list(edge) for edge in sorted(self.edges)]
        return sha256_upper(jcs(records))


class ReferenceBlackBox:
    """Executes the frozen public CLI entry point without source inspection."""

    def __init__(self):
        path = ROOT / "baseline-run/implementation-output-0.3/pcb_runner.py"
        spec = importlib.util.spec_from_file_location("_rr2_frozen_reference_blackbox", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("reference loader unavailable")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.path = str(path)

    def monitorable_code_objects(self):
        codes = set()
        for owner in (self.module, self.module.b1):
            for name in dir(owner):
                value = getattr(owner, name)
                code = getattr(value, "__code__", None)
                if code is not None and str(code.co_filename).lower().startswith(str((ROOT / "baseline-run/implementation-output-0.3").resolve()).lower()):
                    codes.add(code)
        return codes

    def execute(self, raw: bytes) -> tuple[int, bytes, bytes]:
        original = (sys.argv, sys.stdin, sys.stdout, sys.stderr)
        stdin = BinaryConsole(raw); stdout = BinaryConsole(); stderr = BinaryConsole()
        try:
            sys.argv = [self.path, "execute"]
            sys.stdin, sys.stdout, sys.stderr = stdin, stdout, stderr
            code = self.module.main()
        finally:
            sys.argv, sys.stdin, sys.stdout, sys.stderr = original
        return code, stdout.buffer.getvalue(), stderr.buffer.getvalue()


def load_seeds():
    raws: list[bytes] = []
    requests: list[dict] = []
    for rel in (
        "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json",
        "supplemental-0_3/fixtures/B1_SUPPLEMENTAL_SEMANTIC_FIXTURE_PACK_0_3.json",
    ):
        with (ROOT / rel).open("r", encoding="utf-8") as handle:
            pack = json.load(handle)
        for entry in pack["entries"]:
            raws.append(base64.b64decode(entry["semantic_request_jcs_lf_base64"]))
            requests.append(entry["semantic_request"])
    raws.extend([
        bytes.fromhex("7b22f0908080223a302c22ee8080223a307d0a"),
        bytes.fromhex("7b22ee8080223a302c22f0908080223a307d0a"),
        bytes.fromhex("225c7564383030220a"),
        bytes.fromhex("7b225c7564383030223a307d0a"),
        bytes.fromhex("7b22223a302c2222"),
        bytes.fromhex("7b22223a302c22223a307d0a"),
        bytes.fromhex("7b2261223a302c226122"),
        b"", b"\xff\n", b"\xef\xbb\xbf{}\n", b"{}\n", b"1.0\n", b"-0\n",
    ])
    return raws, requests


def recompute_inner(request: dict) -> None:
    request["inner_request_raw_sha256"] = sha256_upper(jcs(request["inner_request"]) + b"\n")
    request["inner_input_sha256"] = sha256_upper(jcs(request["inner_request"]["input"]))


def generate(identity: int, rng: random.Random, corpus: list[bytes], requests: list[dict]) -> tuple[str, bytes]:
    strategy = identity % 20
    parent = corpus[rng.randrange(len(corpus))]
    if strategy == 0:
        return "empty", b""
    if strategy == 1:
        return "invalid_utf8", bytes([0x80 + rng.randrange(128)]) + parent[:rng.randrange(min(len(parent), 32) + 1)] + b"\n"
    if strategy == 2:
        return "bom", b"\xef\xbb\xbf" + parent
    if strategy == 3:
        key = chr(97 + rng.randrange(8)).encode()
        return "duplicate_complete", b'{"' + key + b'":0,"' + key + b'":1}\n'
    if strategy == 4:
        key = chr(97 + rng.randrange(8)).encode()
        return "duplicate_truncated", b'{"' + key + b'":0,"' + key + b'"'
    if strategy == 5:
        cut = rng.randrange(len(parent) + 1) if parent else 0
        return "truncate", parent[:cut]
    if strategy == 6 and parent:
        at = rng.randrange(len(parent))
        return "delete_byte", parent[:at] + parent[at + 1:]
    if strategy == 7:
        at = rng.randrange(len(parent) + 1)
        return "insert_byte", parent[:at] + bytes([rng.randrange(256)]) + parent[at:]
    if strategy == 8 and parent:
        at = rng.randrange(len(parent))
        return "flip_byte", parent[:at] + bytes([parent[at] ^ (1 << rng.randrange(8))]) + parent[at + 1:]
    if strategy == 9:
        return "framing", parent.rstrip(b"\n") + (b"" if identity & 1 else b"\n\n")
    if strategy == 10:
        return "key_order", b'{"\xf0\x90\x80\x80":0,"\xee\x80\x80":0}\n' if identity & 1 else b'{"\xee\x80\x80":0,"\xf0\x90\x80\x80":0}\n'
    if strategy == 11:
        forms = [b'"\\ud800"\n', b'{"\\udfff":0}\n', b'"e\\u0301"\n', '"\u00e9"\n'.encode()]
        return "unicode", forms[rng.randrange(len(forms))]
    if strategy == 12:
        forms = [b"-0\n", b"1.0\n", b"1e0\n", b"9007199254740992\n", b"-9007199254740992\n", b"01\n"]
        return "number", forms[rng.randrange(len(forms))]
    if strategy == 13:
        depth = 1 + rng.randrange(150)
        return "nesting", b"[" * depth + b"0" + b"]" * depth + b"\n"
    if strategy == 14:
        values = [{}, [], None, True, False, {"format_version": "x"}, {"a": rng.randrange(20)}]
        return "schema_root", jcs(values[rng.randrange(len(values))]) + b"\n"
    if strategy == 15:
        return "valid_seed", jcs(requests[rng.randrange(len(requests))]) + b"\n"
    if strategy == 16:
        request = json.loads(json.dumps(requests[rng.randrange(len(requests))]))
        facts = request["inner_request"]["input"].get("observable_external_facts", [])
        if facts:
            facts[0]["fact"] = f"coverage_identity={identity:08X}"
        recompute_inner(request)
        return "opaque_label", jcs(request) + b"\n"
    if strategy == 17:
        request = json.loads(json.dumps(requests[rng.randrange(len(requests))]))
        field = ["operation_handle", "obligation_id", "request_id"][rng.randrange(3)]
        if field == "request_id":
            request["inner_request"][field] = "RUN_" + f"{identity:024X}"[-24:]
        elif field == "operation_handle":
            request[field] = requests[(identity + 1) % len(requests)][field]
        else:
            request[field] = requests[(identity + 1) % len(requests)][field]
        return "binding", jcs(request) + b"\n"
    if strategy == 18:
        request = json.loads(json.dumps(requests[rng.randrange(len(requests))]))
        facts = request["decision_input"]["facts"]
        if facts:
            key = sorted(facts)[rng.randrange(len(facts))]
            value = facts[key]
            if isinstance(value, bool): facts[key] = not value
            elif isinstance(value, int): facts[key] = value + (1 if value < 9007199254740991 else -1)
            elif isinstance(value, list): facts[key] = list(reversed(value)) if value else [None]
            elif isinstance(value, str): facts[key] = value + "_X"
            elif value is None: facts[key] = 0
        return "fact_mutation", jcs(request) + b"\n"
    suffix = bytes(rng.randrange(256) for _ in range(1 + rng.randrange(8)))
    return "raw_suffix", parent + suffix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identities", type=int, default=50_000)
    parser.add_argument("--coverage-identities", type=int, default=2_000)
    args = parser.parse_args()
    if args.identities < 1:
        raise SystemExit("identities must be positive")

    candidate = Implementation(ROOT)
    reference = ReferenceBlackBox()
    coverage = BranchCoverage(ROOT / "baseline-run/implementation-output-0.3")
    rng = random.Random(SEED)
    corpus, requests = load_seeds()
    unique_raw: set[str] = set()
    stream = hashlib.sha256()
    strategy_counts: dict[str, int] = {}
    coverage_cases = 0
    divergences = []
    monitored_identities = min(args.identities, max(1, args.coverage_identities))
    monitoring_active = True
    monitored_codes = reference.monitorable_code_objects()
    monitored_names = sorted({code.co_name for code in monitored_codes})
    coverage.start(monitored_codes)
    try:
        for identity in range(args.identities):
            if identity == monitored_identities and monitoring_active:
                coverage.stop(); monitoring_active = False
            strategy, raw = generate(identity, rng, corpus, requests)
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
            digest = hashlib.sha256(raw).hexdigest().upper()
            unique_raw.add(digest)
            stream.update(identity.to_bytes(8, "big")); stream.update(bytes.fromhex(digest))
            before = len(coverage.edges)
            ref_code, ref_out, ref_err = reference.execute(raw)
            cand_code, cand_out = candidate.execute_bytes(raw)
            if len(coverage.edges) > before:
                corpus.append(raw); coverage_cases += 1
            if (ref_code, ref_out, ref_err) != (cand_code, cand_out, b""):
                try:
                    ref_object = json.loads(ref_out)
                    ref_summary = ref_object.get("errors") or ref_object.get("output", {}).get("result_object")
                except Exception:
                    ref_summary = None
                try:
                    candidate_object = json.loads(cand_out)
                    candidate_summary = candidate_object.get("errors") or candidate_object.get("output", {}).get("result_object")
                except Exception:
                    candidate_summary = None
                divergences.append({
                    "identity": identity,
                    "strategy": strategy,
                    "input_sha256": digest,
                    "input_hex": raw.hex(),
                    "reference_exit": ref_code,
                    "candidate_exit": cand_code,
                    "reference_stdout_sha256": sha256_upper(ref_out),
                    "candidate_stdout_sha256": sha256_upper(cand_out),
                    "reference_summary": ref_summary,
                    "candidate_summary": candidate_summary,
                    "reference_stderr_sha256": sha256_upper(ref_err),
                })
                break
    finally:
        if monitoring_active:
            coverage.stop()

    observed_names = sorted({name for _, name in coverage.code_objects})
    missing_monitored, missing_observed = steering_requirements(monitored_names, observed_names)
    steering_requirements_satisfied = not missing_monitored and not missing_observed
    falsifier_missing_monitored, falsifier_missing_observed = steering_requirements({"_execute"}, {"_execute"})
    execute_only_falsifier_rejected = bool(falsifier_missing_monitored and falsifier_missing_observed)
    receipt = {
        "format_version": "RR2-COVERAGE-GUIDED-DIFFERENTIAL-0.1",
        "seed_hex": f"0x{SEED:08X}",
        "requested_identities": args.identities,
        "executed_identities": sum(strategy_counts.values()),
        "unique_raw_inputs": len(unique_raw),
        "stream_sha256": stream.hexdigest().upper(),
        "reference_target": "frozen composed 0.3 CLI loaded and executed as a black box",
        "coverage_mechanism": "CPython sys.monitoring BRANCH events filtered to the frozen composed reference target",
        "reference_unique_branch_edges": len(coverage.edges),
        "reference_branch_events": coverage.events,
        "reference_code_objects_with_branch_events": len(coverage.code_objects),
        "reference_monitored_code_objects": monitored_names,
        "reference_observed_code_objects": observed_names,
        "steering_code_objects_required": sorted(REQUIRED_STEERING_CODE_OBJECTS),
        "steering_code_objects_missing_monitored": missing_monitored,
        "steering_code_objects_missing_observed": missing_observed,
        "steering_requirements_satisfied": steering_requirements_satisfied,
        "execute_only_falsifier": {
            "monitored_code_objects": ["_execute"],
            "observed_code_objects": ["_execute"],
            "missing_monitored": falsifier_missing_monitored,
            "missing_observed": falsifier_missing_observed,
            "rejected": execute_only_falsifier_rejected,
        },
        "reference_branch_edge_set_sha256": coverage.digest(),
        "coverage_increasing_identities": coverage_cases,
        "coverage_monitored_identities": monitored_identities,
        "coverage_percentage": None,
        "coverage_denominator_note": "No source or disassembly was read, so no total reachable-edge denominator or percentage is claimed.",
        "strategy_counts": dict(sorted(strategy_counts.items())),
        "divergence_count": len(divergences),
        "first_divergence": divergences[0] if divergences else None,
        "status": "PASS" if not divergences and sum(strategy_counts.values()) == args.identities and steering_requirements_satisfied and execute_only_falsifier_rejected else "FAIL",
    }
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
