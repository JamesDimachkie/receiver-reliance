"""Referee: joins arm verdicts with ground truth, emits RESULTS.md + results.json.
Reads truth.jsonl (arms never do), verdicts_baseline.jsonl, verdicts_b1.jsonl,
optional verdicts_b1_subprocess.jsonl for deployment-mode latency.
"""
from __future__ import annotations

import json
import pathlib
import statistics

HERE = pathlib.Path(__file__).resolve().parent


def load(name: str) -> dict[str, dict]:
    path = HERE / name
    if not path.exists():
        return {}
    rows: dict[str, dict] = {}
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            row = json.loads(line)
            record_id = row.get("record_id") if isinstance(row, dict) else None
            if not isinstance(record_id, str) or not record_id:
                raise ValueError(f"{name}:{line_number}: record_id must be a nonempty string")
            if record_id in rows:
                raise ValueError(f"{name}:{line_number}: duplicate record_id {record_id!r}")
            rows[record_id] = row
    return rows


def require_exact_ids(name: str, rows: dict[str, dict], expected: set[str]) -> None:
    actual = set(rows)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{name}: record_id set mismatch; missing={missing} extra={extra}")


corpus = load("corpus.jsonl")
truth = load("truth.jsonl")
arms = {"baseline": load("verdicts_baseline.jsonl"), "b1": load("verdicts_b1.jsonl")}
calibrated = load("verdicts_b1_calibrated.jsonl")
if calibrated:
    arms["b1_calibrated"] = calibrated
b1_sub = load("verdicts_b1_subprocess.jsonl")

truth_ids = set(truth)
require_exact_ids("corpus.jsonl", corpus, truth_ids)
for name, rows in arms.items():
    require_exact_ids(f"verdicts_{name}.jsonl", rows, truth_ids)
if (HERE / "verdicts_b1_subprocess.jsonl").exists():
    require_exact_ids("verdicts_b1_subprocess.jsonl", b1_sub, truth_ids)

families = sorted({r["family"] for r in corpus.values()})
defect_types = sorted({d for t in truth.values() for d in t["defect_types"]})


def confusion(arm: dict[str, dict], subset=None) -> dict:
    tp = fp = fn = tn = 0
    for record_id, t in truth.items():
        if subset and not subset(corpus[record_id], t):
            continue
        hold = arm[record_id]["hold"]
        if t["defective"] and hold:
            tp += 1
        elif t["defective"] and not hold:
            fn += 1
        elif not t["defective"] and hold:
            fp += 1
        else:
            tn += 1
    n = tp + fp + fn + tn
    return {
        "n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "detection_rate": round(tp / (tp + fn), 4) if tp + fn else None,
        "false_hold_rate": round(fp / (fp + tn), 4) if fp + tn else None,
    }


results: dict = {"overall": {}, "per_family": {}, "per_defect_type": {}, "latency": {}, "burden": {}}
for name, arm in arms.items():
    results["overall"][name] = confusion(arm)
for family in families:
    results["per_family"][family] = {
        name: confusion(arm, lambda r, t, fam=family: r["family"] == fam) for name, arm in arms.items()
    }
for dtype in defect_types:
    results["per_defect_type"][dtype] = {}
    for name, arm in arms.items():
        rows = [t for t in truth.values() if dtype in t["defect_types"]]
        caught = sum(1 for t in rows if arm[t["record_id"]]["hold"])
        results["per_defect_type"][dtype][name] = {"n": len(rows), "caught": caught}

for name, arm in list(arms.items()) + ([("b1_subprocess", b1_sub)] if b1_sub else []):
    times = [v["seconds"] for v in arm.values() if "seconds" in v]
    if times:
        results["latency"][name] = {
            "mean_ms": round(statistics.mean(times) * 1000, 3),
            "p95_ms": round(sorted(times)[int(len(times) * 0.95) - 1] * 1000, 3),
        }

fab = [len(v.get("fabricated_fields", [])) for v in arms["b1"].values()]
results["burden"]["b1_fabricated_fields_total"] = sum(fab)
results["burden"]["b1_decisions_with_fabrication"] = sum(1 for x in fab if x)
results["burden"]["b1_request_bytes_mean"] = None
sizes = []
reqlog = HERE / "requests_log.jsonl"
if reqlog.exists():
    for line in open(reqlog, encoding="utf-8"):
        sizes.append(len(json.dumps(json.loads(line)["request"], separators=(",", ":"))))
    results["burden"]["b1_request_bytes_mean"] = round(statistics.mean(sizes)) if sizes else None

# Disagreements: where exactly one arm holds, grouped by (family, truth, direction)
disagreements: dict[str, list] = {}
for record_id, t in truth.items():
    base_hold = arms["baseline"][record_id]["hold"]
    b1_hold = arms["b1"][record_id]["hold"]
    if base_hold == b1_hold:
        continue
    direction = "b1_only" if b1_hold else "baseline_only"
    key = f"{corpus[record_id]['family']}|{'defective' if t['defective'] else 'clean'}|{direction}"
    entry = {
        "record_id": record_id,
        "b1_reasons": arms["b1"][record_id]["reasons"][:2],
        "baseline_reasons": arms["baseline"][record_id]["reasons"][:2],
        "defect_types": t["defect_types"],
        "provenance": t["provenance"],
    }
    disagreements.setdefault(key, []).append(entry)
results["disagreements_summary"] = {k: len(v) for k, v in sorted(disagreements.items())}
results["disagreement_samples"] = {k: v[:3] for k, v in sorted(disagreements.items())}

with open(HERE / "results.json", "w", encoding="utf-8", newline="\n") as fh:
    json.dump(results, fh, indent=1, sort_keys=True)

lines = ["# Native-records usefulness proof -- results", ""]
lines.append("| arm | n | detected | missed | false holds | detection rate | false-hold rate |")
lines.append("|---|---|---|---|---|---|---|")
for name, c in results["overall"].items():
    lines.append(
        f"| {name} | {c['n']} | {c['tp']} | {c['fn']} | {c['fp']} | {c['detection_rate']} | {c['false_hold_rate']} |"
    )
lines.append("")
arm_names = list(arms.keys())
lines.append("## Per defect type (caught / n)")
lines.append("")
lines.append("| defect type | " + " | ".join(arm_names) + " |")
lines.append("|---" * (len(arm_names) + 1) + "|")
for dtype, row in results["per_defect_type"].items():
    cells = [f"{row[name]['caught']}/{row[name]['n']}" for name in arm_names]
    lines.append(f"| {dtype} | " + " | ".join(cells) + " |")
lines.append("")
lines.append("## Per family false holds (fp/clean-n)")
lines.append("")
lines.append("| family | " + " | ".join(arm_names) + " |")
lines.append("|---" * (len(arm_names) + 1) + "|")
for family, row in results["per_family"].items():
    cells = [f"{row[name]['fp']}/{row[name]['fp'] + row[name]['tn']}" for name in arm_names]
    lines.append(f"| {family} | " + " | ".join(cells) + " |")
lines.append("")
lines.append("## Latency and burden")
lines.append("")
for name, row in results["latency"].items():
    lines.append(f"- {name}: mean {row['mean_ms']} ms, p95 {row['p95_ms']} ms per decision")
lines.append(f"- b1 fabricated fields: {results['burden']['b1_fabricated_fields_total']} across "
             f"{results['burden']['b1_decisions_with_fabrication']} decisions "
             f"(schema-required fields with no native basis)")
if results["burden"]["b1_request_bytes_mean"]:
    lines.append(f"- b1 mean request size: {results['burden']['b1_request_bytes_mean']} bytes")
lines.append("")
lines.append("## Disagreements (one arm holds, the other does not)")
lines.append("")
for key, count in results["disagreements_summary"].items():
    lines.append(f"- {key}: {count}")
with open(HERE / "RESULTS.md", "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(lines) + "\n")
print("\n".join(lines))
