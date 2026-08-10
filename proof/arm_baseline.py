"""Baseline arm: a small schema-plus-policy validator (the reviewer's
"much smaller" comparator). Reads ONLY corpus.jsonl. Single-record rules a
diligent engineer writes in an afternoon — shape checks plus per-family
policy checks over the fields present in the record. Its stated design
boundary: no relational joins across records or entities (the SUPERSEDE
blame join is exactly the kind of rule such gates omit; the omission is a
design property of the arm, disclosed up front, not an implementation slip).

Verdict per record: {"record_id", "hold": bool, "reasons": [...]}.
"""
from __future__ import annotations

import fnmatch
import json
import pathlib
import time

HERE = pathlib.Path(__file__).resolve().parent

REQUIRED = {
    "REF": ["referenced_record_found"],
    "SCOPE": ["commit_found"],
    "SUPERSEDE": ["corrected_version_sha256"],
    "LIFECYCLE": ["lifecycle_event_timestamps"],
}


def in_scope(path: str, claimed: list[str]) -> bool:
    for pattern in claimed:
        if path == pattern or fnmatch.fnmatch(path, pattern):
            return True
        if pattern.endswith("/**") and path.startswith(pattern[:-2]):
            return True
    return False


def decide(record: dict) -> dict:
    family = record["family"]
    native = record["native"]
    obs = record["observations"]
    reasons: list[str] = []

    for key in REQUIRED.get(family, []):
        if key not in obs:
            reasons.append(f"shape:missing:{key}")

    if family == "REF":
        if not obs.get("referenced_record_found"):
            reasons.append("reference_target_not_found")
        claimed = native.get("claimed_sha256")
        observed = obs.get("observed_sha256")
        if claimed and observed and claimed != observed:
            reasons.append("pin_hash_mismatch")
    elif family == "SCOPE":
        if native.get("result_commit_named") and not obs.get("commit_found"):
            reasons.append("named_commit_not_found")
        changed = obs.get("commit_changed_paths")
        claimed_paths = native.get("claimed_paths") or []
        if changed and claimed_paths:
            outside = [p for p in changed if not in_scope(p, claimed_paths)]
            if outside:
                reasons.append("changed_paths_outside_claim")
    elif family == "SUPERSEDE":
        if not obs.get("corrected_version_sha256"):
            reasons.append("corrected_version_unresolvable")
        # No cross-record blame join: single-record policy only.
    elif family == "LIFECYCLE":
        ts = obs.get("lifecycle_event_timestamps") or []
        if any(b <= a for a, b in zip(ts, ts[1:])):
            reasons.append("lifecycle_not_strictly_ordered")

    return {"record_id": record["record_id"], "hold": bool(reasons), "reasons": reasons}


def main() -> None:
    verdicts = []
    started = time.perf_counter()
    with open(HERE / "corpus.jsonl", encoding="utf-8") as fh:
        for line in fh:
            record = json.loads(line)
            t0 = time.perf_counter()
            verdict = decide(record)
            verdict["seconds"] = time.perf_counter() - t0
            verdicts.append(verdict)
    total = time.perf_counter() - started
    with open(HERE / "verdicts_baseline.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for verdict in verdicts:
            fh.write(json.dumps(verdict, sort_keys=True) + "\n")
    holds = sum(1 for v in verdicts if v["hold"])
    print(f"baseline arm: {len(verdicts)} records, {holds} holds, {total:.3f}s total")


if __name__ == "__main__":
    main()
