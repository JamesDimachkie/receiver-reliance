#!/usr/bin/env python3
"""Read findings.json and print the tables the reports quote.

Kept in-tree so every number in PROOF_REPORT.md can be regenerated rather than
retyped.  Usage: python -B summarize.py [findings.json]
"""

from __future__ import annotations

import collections
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "findings.json"
d = json.load(open(path, encoding="utf-8"))

print(f"obligations={d['obligations']} elapsed={d['elapsed_seconds']}s "
      f"evaluations={d['evaluations']} sealed_pipeline_calls={d.get('sealed_pipeline_calls')}")
print("counts:", d["counts"])
print()

by = collections.defaultdict(collections.Counter)
for r in d["results"]:
    by[r["property"]][r["status"]] += 1
print(f"{'property':<52}{'PROVEN':>8}{'BOUNDED':>9}{'REFUTED':>9}{'ERROR':>7}")
for p in sorted(by):
    c = by[p]
    print(f"{p:<52}{c['PROVEN']:>8}{c['PROVEN-BOUNDED']:>9}{c['REFUTED']:>9}{c['ERROR']:>7}")
print()

kinds = collections.Counter(f["kind"] for f in d["findings"])
print("findings:", dict(kinds))
print()

for kind in ("UNREACHABLE-ROW-DISJUNCT", "NO-WITNESS-IN-ABSTRACTION", "SHADOWED-DISJUNCT",
             "NEVER-SOLE-REASON", "CLOSURE-ROW-NOT-EXERCISED",
             "AUDITED-CLASS-OUTSIDE-FROZEN-VOCABULARY", "E2E-PROTOCOL-ERROR"):
    rows = [f for f in d["findings"] if f["kind"] == kind]
    if rows:
        print(f"-- {kind} ({len(rows)})")
        for f in rows:
            print(f"   {f['subject']}")
        print()

dep = {f["subject"] for f in d["findings"] if f["kind"] == "PRECEDENCE-DEPENDENT"}
indep = [r["subject"] for r in d["results"] if r["property"] == "B1.precedence-independent-pair"]
print(f"-- precedence-dependent pairs: {len(dep)} of {len(dep) + len(indep)}")
print(f"-- no co-satisfying input found for: {indep}")
print()

modes = collections.Counter()
for r in d["results"]:
    if r["property"].startswith(("A2.", "A3.", "A5.")):
        modes[(r["property"][:2], r["detail"].get("mode", "-"))] += 1
print("search mode by property:", dict(modes))
print()

classes = collections.Counter()
for r in d["results"]:
    if r["property"] == "C4.no-unclassified-input":
        for c in r["detail"]["classes_observed"]:
            classes[c] += 1
print("operations in which each class was observed under sampling:", dict(classes))

dom = d["domain_summary"]
print()
print(f"{'obligation':<12}{'fields':>7}{'finite':>8}{'exhaustive':>12}")
for oid in sorted(dom):
    s = dom[oid]
    print(f"{oid:<12}{s['fields']:>7}{s['finite_fields']:>8}{s['exhaustive_fields']:>12}")
