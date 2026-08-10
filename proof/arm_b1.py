"""B1 arm: host adapter + the frozen composed 0.3 engine.

Reads ONLY corpus.jsonl (same information as the baseline arm). For each
record the adapter derives a fact profile for the matching obligation from
the raw observations — deriving, not asserting: the blame join for
supersession, the glob-scope reduction, the version-testimony merge are all
computed here from raw facts. The frozen engine then classifies.

Honesty instrumentation:
  - fabricated_fields: schema-required fact fields with no native basis in
    this corpus (the adapter must invent a value to satisfy the schema).
    Counted per decision and reported — this is the adapter-burden metric.
  - Requests and responses are retained for audit (requests_log.jsonl).
  - Wall time is measured per decision in BOTH modes: subprocess ABI
    (deployment-shaped) and in-process (library-shaped).

Verdict rule (fixed before scoring): hold iff behavior_class != VALID.
"""
from __future__ import annotations

import base64
import copy
import fnmatch
import hashlib
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
IMPL3 = REPO / "baseline-run" / "implementation-output-0.3"
sys.path.insert(0, str(IMPL3))
import b1_capabilities as b1  # noqa: E402
import pcb_runner  # noqa: E402

OBLIGATION_BY_FAMILY = {
    "REF": "OBL-02",
    "SCOPE": "OBL-03",
    "SUPERSEDE": "OBL-15",
    "LIFECYCLE": "OBL-17",
}


def load_templates() -> dict[str, dict]:
    pack = json.load(
        open(REPO / "baseline-run/fixtures/PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json", encoding="utf-8")
    )
    templates: dict[str, dict] = {}
    for entry in pack["entries"]:
        for obligation in OBLIGATION_BY_FAMILY.values():
            if f"{obligation}-IO" in entry["entry_id"]:
                templates[obligation] = json.loads(
                    base64.b64decode(entry["semantic_request_jcs_lf_base64"]).decode()
                )
    return templates


TEMPLATES = load_templates()


def hex64(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest().upper()


def scope_hash(items: list[str]) -> str:
    return hex64("\n".join(sorted(items)))


def in_scope(path: str, claimed: list[str]) -> bool:
    for pattern in claimed:
        if path == pattern or fnmatch.fnmatch(path, pattern):
            return True
        if pattern.endswith("/**") and path.startswith(pattern[:-2]):
            return True
    return False


def build_request(record: dict, facts: dict) -> dict:
    obligation = OBLIGATION_BY_FAMILY[record["family"]]
    request = copy.deepcopy(TEMPLATES[obligation])
    request_id = "RUN_" + hashlib.sha256(record["record_id"].encode()).hexdigest()[:24].upper()
    request["request_id"] = request_id
    request["inner_request"]["request_id"] = request_id
    request["decision_input"]["facts"] = facts
    request["inner_request_raw_sha256"] = b1.sha256_upper(
        b1.jcs_bytes(request["inner_request"]) + b"\n"
    )
    request["inner_input_sha256"] = b1.sha256_upper(b1.jcs_bytes(request["inner_request"]["input"]))
    return request


def derive_facts(record: dict) -> tuple[dict, list[str]]:
    """Map raw observations to the obligation's fact profile.
    Returns (facts, fabricated_field_names)."""
    family = record["family"]
    native = record["native"]
    obs = record["observations"]
    fabricated: list[str] = []

    if family == "REF":
        reference_id = native.get("claimed_path") or native["referenced_record"]
        # record_versions is the host's version testimony for records it
        # actually HOLDS. A missing record contributes nothing (the claim's
        # own pin must not vouch for its target's existence); a held record
        # contributes its observed hash, plus the claimed pin as a second
        # testimony row so a pin/content divergence is an inconsistency.
        versions: list[dict] = []
        if obs.get("referenced_record_found") and obs.get("observed_sha256"):
            versions.append({"record_id": reference_id, "revision_sha256": obs["observed_sha256"]})
            if native.get("claimed_sha256"):
                versions.append({"record_id": reference_id, "revision_sha256": native["claimed_sha256"]})
        facts = {"exact_reference": reference_id[:160], "record_versions": versions}
        for row in facts["record_versions"]:
            row["record_id"] = row["record_id"][:160]
        return facts, fabricated

    if family == "SCOPE":
        claimed_paths = native.get("claimed_paths") or []
        declared = scope_hash(claimed_paths) if claimed_paths else None
        changed = obs.get("commit_changed_paths")
        if native.get("result_commit_named") and not obs.get("commit_found"):
            recorded = None  # a named result commit that cannot be resolved
        elif changed is None:
            recorded = declared  # nothing recorded contradicts the declaration
        else:
            outside = [p for p in changed if not in_scope(p, claimed_paths)]
            recorded = declared if not outside else scope_hash(sorted(claimed_paths + outside))
        kinds = []
        if claimed_paths:
            kinds.append("ADOPTION")
        if native.get("status") is not None:
            kinds.append("INTENDED_USE")
        facts = {
            "declaration_effective_at": 0,
            "interval_end_exclusive": 1,
            "declaration_kinds": kinds,
            "declared_scope_sha256": declared,
            "recorded_use_scope_sha256": recorded,
        }
        fabricated += ["declaration_effective_at", "interval_end_exclusive"]
        return facts, fabricated

    if family == "SUPERSEDE":
        corrected_epoch = obs.get("corrected_first_added_epoch")
        epochs = obs.get("doc_first_added_epochs") or {}
        any_later = set(obs.get("later_docs_citing_any_later_member") or [])
        blamed: list[str] = []
        for name in obs.get("later_docs_citing_invalidated") or []:
            if name in any_later:
                continue
            added = epochs.get(name)
            if corrected_epoch is not None and added is not None and added < corrected_epoch:
                continue
            blamed.append(name)
        reliance_surface = sorted(any_later | set(obs.get("later_docs_citing_invalidated") or []))
        facts = {
            "corrected_version_sha256": obs.get("corrected_version_sha256"),
            "correction_target_ordinal": native["correction_ordinal"],
            "invalidated_path_ids": sorted(blamed)[:256],
            "independent_valid_path_ids": reliance_surface[:256],
        }
        return facts, fabricated

    if family == "LIFECYCLE":
        ts = obs.get("lifecycle_event_timestamps") or []
        if CALIBRATED and len(ts) < 2:
            # OBL-17 requires an acknowledgment event ordered after the
            # effective event. A single-event lifecycle has no such second
            # event: the obligation is INAPPLICABLE to this record, and the
            # calibrated adapter declines to force it (the strict adapter
            # forces it and eats the false holds — both are measured).
            return None, fabricated
        facts = {
            "event_sequences": ts[:256],
            "nonroot_predecessor_sequences": ts[:-1][:256],
            "acknowledged_at": ts[-1] if ts else 0,
            "effective_at": ts[0] if ts else 0,
            "terminal_predecessor_sequences": ts[-2:-1][:256],
        }
        # acknowledgment is not a native concept in these task records; the
        # adapter reuses first/last event times to satisfy the schema.
        fabricated += ["acknowledged_at", "effective_at"]
        return facts, fabricated

    raise ValueError(family)


CALIBRATED = False


def main() -> None:
    global CALIBRATED
    subprocess_mode = "--subprocess" in sys.argv
    CALIBRATED = "--calibrated" in sys.argv
    verdicts = []
    request_log = []
    started = time.perf_counter()
    with open(HERE / "corpus.jsonl", encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh]
    for record in records:
        facts, fabricated = derive_facts(record)
        if facts is None:
            verdicts.append(
                {
                    "record_id": record["record_id"],
                    "hold": False,
                    "behavior_class": "INAPPLICABLE",
                    "reasons": ["obligation_inapplicable_to_record"],
                    "fabricated_fields": fabricated,
                    "seconds": 0.0,
                }
            )
            continue
        request = build_request(record, facts)
        raw = b1.jcs_bytes(request) + b"\n"
        t0 = time.perf_counter()
        if subprocess_mode:
            import subprocess as sp

            proc = sp.run(
                [sys.executable, "-I", "-B", str(IMPL3 / "pcb_runner.py"), "execute"],
                input=raw, capture_output=True,
            )
            out = proc.stdout
        else:
            response, _exit = pcb_runner._execute(raw)
            out = b1.jcs_bytes(response) + b"\n"
        seconds = time.perf_counter() - t0
        response_obj = json.loads(out.decode())
        if response_obj.get("ok"):
            behavior = response_obj["output"]["result_object"]["behavior_class"]
            reasons = [] if behavior == "VALID" else [f"class:{behavior}"]
            reasons += response_obj["output"].get("unresolved_reasons") or []
        else:
            behavior = "PROTOCOL_ERROR"
            reasons = [f"protocol:{response_obj['errors'][0]['code']}:{response_obj['errors'][0]['pointer']}"]
        verdicts.append(
            {
                "record_id": record["record_id"],
                "hold": behavior != "VALID",
                "behavior_class": behavior,
                "reasons": reasons,
                "fabricated_fields": fabricated,
                "seconds": seconds,
            }
        )
        request_log.append(
            {
                "record_id": record["record_id"],
                "request": request,
                "response_receipt": response_obj.get("receipt_sha256"),
                "behavior_class": behavior,
            }
        )
    total = time.perf_counter() - started
    suffix = ("_calibrated" if CALIBRATED else "") + ("_subprocess" if subprocess_mode else "")
    with open(HERE / f"verdicts_b1{suffix}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for verdict in verdicts:
            fh.write(json.dumps(verdict, sort_keys=True) + "\n")
    with open(HERE / f"requests_log{suffix}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for row in request_log:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    holds = sum(1 for v in verdicts if v["hold"])
    protocol_errors = sum(1 for v in verdicts if v["behavior_class"] == "PROTOCOL_ERROR")
    print(
        f"b1 arm ({'subprocess' if subprocess_mode else 'in-process'}): "
        f"{len(verdicts)} records, {holds} holds, {protocol_errors} protocol errors, {total:.3f}s total"
    )


if __name__ == "__main__":
    main()
