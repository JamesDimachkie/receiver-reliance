"""Offline integrity and core-results verification; no inference or engine calls."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent


def check(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest().upper()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def run():
    manifest = read(ROOT / "MANIFEST.json")
    expected = manifest["files"]
    actual = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()}
    check(actual == set(expected) | {"MANIFEST.json"}, "Manifest file set mismatch")
    for name, metadata in expected.items():
        data = (ROOT / name).read_bytes()
        check(len(data) == metadata["bytes"] and digest(data) == metadata["sha256"], name)

    results = {}
    for name, calls in [("rr-jev-feasibility", 30), ("rr-jev-vitamin-c", 240)]:
        base = ROOT / name
        freeze = read(base / "freeze.json")
        for relative, sha256 in freeze["study_hashes"].items():
            check(digest((base / relative).read_bytes()) == sha256, "Freeze: " + relative)
        source = freeze.get("rr_source_hashes", freeze.get("rr_hashes"))
        check(len(source) == 59, "RR source count")
        for relative, sha256 in source.items():
            check(digest((ROOT / "rr-source" / relative).read_bytes()) == sha256,
                  "RR source: " + relative)
        for key, relative in [("cases_sha256", "cases.json"),
                              ("request_plan_sha256", "request-plan.json"),
                              ("qualification_sha256", "qualification/result.json"),
                              ("review_sha256", "REVIEW.md")]:
            if key in freeze:
                check(digest((base / relative).read_bytes()) == freeze[key], key)
        plan = read(base / "request-plan.json")
        semantics = read(base / "results/semantic.json")
        check(len(plan) == len(semantics) == calls, "Judgment count")
        bank = {}
        tokens = 0
        for planned in plan:
            key = planned["sha256"]
            check(digest(canonical(planned["request"])) == key, "Request hash")
            record = read(base / "live" / (key + ".json"))
            check(record["request"] == planned["request"], "Request identity")
            check(digest(record["raw_response_text"].encode()) == record["raw_response_sha256"],
                  "Response hash")
            response = json.loads(record["raw_response_text"])
            check(response == record["response"] and response["model"] == "jev-1.13.0",
                  "Parsed response or model identity")
            bank[key] = response["answers"]["support"]
            tokens += response["usage"]["input_tokens"]
        for row in semantics:
            answer = bank[row["request_sha256"]]
            check(row["answer"] == answer, "Semantic answer identity")
            gate = (answer["choice"] == "supports" and
                    answer["probabilities"]["supports"] >= .90 and answer["confidence"] >= .80)
            check(row.get("release", row.get("released_by_threshold")) == gate, "Release gate")
        summary = read(base / "results/summary.json")
        if name.endswith("feasibility"):
            rows = read(base / "results/rows.json")
            totals = summary["totals"]
            comparisons = [("rr_with_jev", "conventional_with_jev"),
                           ("rr_without_jev", "conventional_without_jev")]
            fields = ["released", "bad_semantic_release", "revocation_violation",
                      "useful_withheld", "logical_checks"]
            correct = sum(row["answer"]["choice"] == row["gold"] for row in semantics)
            check(correct == summary["semantic_label_correct"] == 30, "Synthetic labels")
            check(tokens == summary["reported_input_tokens"] == 14521, "Synthetic tokens")
            expected_episodes = 48
        else:
            rows = read(base / "results/episodes.json")
            totals = summary["arms"]
            comparisons = [("rr", "conventional")]
            fields = ["released", "unsupported_release", "withheld_support",
                      "refreshed", "logical_checks", "logical_input_tokens"]
            correct = sum(row["answer"]["choice"] == row["gold"] for row in semantics)
            check(correct == summary["correct"] == 194, "Benchmark agreement")
            negative = sum(row["release"] and row["gold"] != "supports" for row in semantics)
            withheld = sum(not row["release"] and row["gold"] == "supports" for row in semantics)
            check(negative == summary["unsupported_releases"] == 1, "Negative-label acceptances")
            check(withheld == summary["withheld_support"] == 38, "Positive-label withholding")
            pairs = {}
            for row in semantics:
                pairs.setdefault(row["pair_id"], {})[row["kind"]] = row
            check(len(pairs) == 120 and all(set(p) == {"support", "negative"} for p in pairs.values()),
                  "Pair structure")
            decreased = sum(p["support"]["p_support"] > p["negative"]["p_support"]
                            for p in pairs.values())
            check(decreased == summary["support_probability_decreased"] == 112, "Evidence sensitivity")
            check(tokens == summary["actual_input_tokens"] == 125692, "Benchmark tokens")
            expected_episodes = 480
        for arm, total in totals.items():
            arm_rows = [row for row in rows if row["arm"] == arm]
            check(len(arm_rows) == total["episodes"] == expected_episodes, "Episode count")
            for field in fields:
                check(sum(row[field] for row in arm_rows) == total[field], arm + ": " + field)
        for first, second in comparisons:
            decisions = [{r["case"]: r["released"] for r in rows if r["arm"] == arm}
                         for arm in (first, second)]
            check(decisions[0] == decisions[1] and len(decisions[0]) == expected_episodes,
                  "Comparator parity")
        results[name] = {"judgments": calls, "input_tokens": tokens,
                         "episodes": expected_episodes, "release_decision_parity": True}
    print(json.dumps({"status": "PASS", "manifest_files": len(expected),
                      "scope": "offline integrity and core recorded results; no new inference or engine replay",
                      "studies": results}, indent=2))


if __name__ == "__main__":
    run()
