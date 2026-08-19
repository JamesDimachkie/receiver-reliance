"""Native-record corpus extraction for the receiver-reliance usefulness proof.

Walks REAL recorded agent-handoff artifacts in the operator workspace (no
precomputed verdicts): hash-pinned research handoffs, structured task-claim
files, version-superseded foundation documents, and task lifecycle history
from git. Emits:

  corpus.jsonl  - one observation record per handoff claim; BOTH arms read
                  exactly this file and nothing else (same-information rule).
  truth.jsonl   - mechanical ground-truth labels, written separately so the
                  arms cannot read them.

Seeded records are perturbed clones of real records (controlled positives
per defect type); arms are blind to provenance.

Determinism: no clock, no randomness. Seeding is keyed by record index.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

# Extraction runs only on the operator workstation that holds the source
# workspace. The emitted synthetic corpus ships; the workspace does not.
_SOURCE = os.environ.get("RR_SOURCE_WORKSPACE")
if _SOURCE is None:
    sys.exit(
        "extract_corpus: set RR_SOURCE_WORKSPACE to the source workspace root. "
        "Extraction is operator-only; the shipped corpus.synthetic.jsonl and "
        "truth.synthetic.jsonl are its committed, regenerable output."
    )
WORKSPACE = pathlib.Path(_SOURCE)
EPI = WORKSPACE / "planning" / "epistemic-handoff"
TASKS = WORKSPACE / ".agent-tasks"
HANDOFFS = WORKSPACE / ".claude" / "handoffs"
OUT_DIR = pathlib.Path(__file__).resolve().parent
REPO = OUT_DIR.parent
if str(REPO / "portability") not in sys.path:
    sys.path.insert(0, str(REPO / "portability"))

# Provenance this script records must not depend on whichever `git` the
# ambient PATH resolves first (TRUST_MODEL.md's harness boundary).
import pinned_tools  # noqa: E402

HEX64 = re.compile(r"\b[A-F0-9]{64}\b")
# `NAME.md`, SHA-256 `HASH`  (the epistemic-handoff citation convention)
PIN_RE = re.compile(
    r"`([A-Za-z0-9_./\-]+\.(?:md|json|py))`[,;]?\s+SHA-256\s+`([A-F0-9]{64})`",
    re.S,
)
HANDOFF_REF_RE = re.compile(r"\.claude/handoffs/([A-Za-z0-9_.\-]+\.md)")
COMMIT_RE = re.compile(r"\b([0-9a-f]{7,10})\b(?=[^0-9a-f]|$)")


def sha256_file(path: pathlib.Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest().upper()
    except OSError:
        return None


def git(repo: pathlib.Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            [pinned_tools.git(), "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None
    return proc.stdout if proc.returncode == 0 else None


def rid(*parts: str) -> str:
    return "REC_" + hashlib.sha256("|".join(parts).encode()).hexdigest()[:16].upper()


records: list[dict] = []
truths: list[dict] = []


def emit(family: str, native: dict, observations: dict, defect_types: list[str], provenance: str, key: str) -> None:
    record_id = rid(family, key, provenance)
    records.append(
        {
            "record_id": record_id,
            "family": family,
            "native": native,
            "observations": observations,
        }
    )
    truths.append(
        {
            "record_id": record_id,
            "provenance": provenance,
            "defect_types": sorted(defect_types),
            "defective": bool(defect_types),
        }
    )


# --------------------------------------------------------------------------
# Family REF: pinned document references (OBL-02-shaped)
# A handoff/review doc cites another record by name with a pinned SHA-256.
# Native claim: (source_doc, referenced_name, claimed_sha256).
# World observation: the referenced record's current bytes hash, or absence.
# --------------------------------------------------------------------------


def resolve_named(name: str) -> pathlib.Path | None:
    reference = pathlib.PurePosixPath(name)
    if (
        reference.is_absolute()
        or not reference.parts
        or any(part in {"", ".", ".."} for part in reference.parts)
    ):
        return None

    workspace = WORKSPACE.resolve()

    def admitted(candidate: pathlib.Path) -> pathlib.Path | None:
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(workspace)
        except (OSError, ValueError):
            return None
        return resolved if resolved.is_file() else None

    # A citation carrying directory components names exactly one
    # workspace-relative path. Never discard those components and substitute a
    # preferred-directory basename.
    if len(reference.parts) > 1:
        return admitted(WORKSPACE.joinpath(*reference.parts))

    base = reference.name
    candidates = [
        EPI / base,
        EPI / "gate-0-spec" / base,
        HANDOFFS / base,
        HANDOFFS / "archive" / base,
        *EPI.rglob(base),
    ]
    matches = {
        resolved
        for candidate in candidates
        if (resolved := admitted(candidate)) is not None
    }
    # A basename-only citation is admissible only when it is unambiguous.
    return next(iter(matches)) if len(matches) == 1 else None


ref_count = 0
for doc in sorted(EPI.glob("*.md")):
    text = doc.read_text(encoding="utf-8", errors="replace")
    for name, claimed in PIN_RE.findall(text):
        target = resolve_named(name)
        observed = sha256_file(target) if target else None
        native = {
            "source_doc": str(doc.relative_to(WORKSPACE)),
            "referenced_record": pathlib.Path(name).name,
            "claimed_sha256": claimed,
        }
        obs = {
            "referenced_record_found": target is not None,
            "observed_sha256": observed,
        }
        defects = []
        if target is None:
            defects.append("missing_reference_target")
        elif observed != claimed:
            defects.append("pin_hash_mismatch")
        emit("REF", native, obs, defects, "real", f"{doc.name}:{name}:{claimed[:8]}")
        ref_count += 1

# TASK result-text references to handoff files (existence claims, no hash)
for task_file in sorted(TASKS.glob("TASK-*.json")):
    try:
        task = json.loads(task_file.read_text(encoding="utf-8"))
    except ValueError:
        continue
    result_text = str(task.get("result", ""))
    for name in HANDOFF_REF_RE.findall(result_text):
        at_claimed = (HANDOFFS / name).is_file()
        in_archive = (HANDOFFS / "archive" / name).is_file()
        native = {
            "source_doc": str(task_file.relative_to(WORKSPACE)),
            "referenced_record": name,
            "claimed_path": f".claude/handoffs/{name}",
            "claimed_sha256": None,
        }
        obs = {
            "referenced_record_found": at_claimed,
            "found_at_archived_location": in_archive,
            "observed_sha256": sha256_file(HANDOFFS / name)
            if at_claimed
            else (sha256_file(HANDOFFS / "archive" / name) if in_archive else None),
        }
        defects = [] if at_claimed else ["stale_reference_path"]
        emit("REF", native, obs, defects, "real", f"{task_file.name}:{name}")
        ref_count += 1

# --------------------------------------------------------------------------
# Family SCOPE: declared claim scope vs recorded use (OBL-03-shaped)
# Native claim: task claims paths + names a result commit in a repo.
# World observation: the commit's actual changed paths from git.
# Claimed paths may be glob patterns (`dir/**`); scope membership honors them.
# --------------------------------------------------------------------------

import fnmatch


def path_in_scope(path: str, claimed: list[str]) -> bool:
    for pattern in claimed:
        if path == pattern or fnmatch.fnmatch(path, pattern):
            return True
        if pattern.endswith("/**") and path.startswith(pattern[:-2]):
            return True
    return False


scope_count = 0
for task_file in sorted(TASKS.glob("TASK-*.json")):
    try:
        task = json.loads(task_file.read_text(encoding="utf-8"))
    except ValueError:
        continue
    repo_path = pathlib.Path(str(task.get("repo", "")))
    if not (repo_path / ".git").exists():
        continue
    result_text = str(task.get("result", ""))
    claimed_paths = task.get("claimed_paths") or []
    # A bare digit run (a date, a count) is not a commit reference; require
    # at least one hex letter before treating a token as a named commit.
    commit_tokens = [t for t in COMMIT_RE.findall(result_text) if re.search(r"[a-f]", t)]
    commit = None
    for cand in commit_tokens:
        if git(repo_path, "cat-file", "-e", f"{cand}^{{commit}}") is not None:
            commit = cand
            break
    changed: list[str] | None = None
    if commit:
        out = git(repo_path, "show", "--name-only", "--format=", commit)
        if out is not None:
            changed = sorted(p for p in out.splitlines() if p.strip())
    native = {
        "source_doc": str(task_file.relative_to(WORKSPACE)),
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "claimed_paths": sorted(claimed_paths),
        "result_commit": commit,
        "result_commit_named": bool(commit_tokens),
    }
    obs = {
        "commit_found": commit is not None,
        "commit_changed_paths": changed,
    }
    defects = []
    if commit_tokens and commit is None:
        defects.append("unknown_result_commit")
    if changed is not None and claimed_paths:
        outside = [p for p in changed if not path_in_scope(p, claimed_paths)]
        if outside:
            defects.append("recorded_use_outside_declared_scope")
    emit("SCOPE", native, obs, defects, "real", task_file.name)
    scope_count += 1

# --------------------------------------------------------------------------
# Family SUPERSEDE: version-supersession consistency (OBL-15-shaped)
# Native claim: a doc chain where version N+1 corrects version N; later
# records must not keep relying on the invalidated version.
# World observation: which later docs cite which chain members.
# --------------------------------------------------------------------------

CHAIN = [
    "EPISTEMIC_HANDOFF_FOUNDATION_0_3_20260807.md",
    "EPISTEMIC_HANDOFF_FOUNDATION_0_4_20260807.md",
    "EPISTEMIC_HANDOFF_FOUNDATION_0_4_1_20260807.md",
    "EPISTEMIC_HANDOFF_FOUNDATION_0_4_2_20260807.md",
]
chain_stems = {name: name.replace("_20260807.md", "") for name in CHAIN}
later_docs = [
    doc
    for doc in sorted(EPI.glob("*.md"))
    if doc.name not in CHAIN
]


def first_added_epoch(path: pathlib.Path) -> int | None:
    out = git(WORKSPACE, "log", "--follow", "--format=%ct", "--", str(path.relative_to(WORKSPACE)))
    if out is None or not out.strip():
        return None
    return int(out.split()[-1])  # oldest commit touching the file


doc_added = {doc.name: first_added_epoch(doc) for doc in later_docs}
chain_added = {name: first_added_epoch(EPI / name) for name in CHAIN}

supersede_count = 0
for ordinal in range(1, len(CHAIN)):
    corrected = CHAIN[ordinal]
    invalidated = CHAIN[ordinal - 1]
    corrected_path = EPI / corrected
    later_members = CHAIN[ordinal:]
    citers_of_invalidated = []
    citers_of_any_later = []
    for doc in later_docs:
        text = doc.read_text(encoding="utf-8", errors="replace")
        if re.search(re.escape(chain_stems[invalidated]) + r"\b", text):
            citers_of_invalidated.append(doc.name)
        if any(
            re.search(re.escape(chain_stems[m]) + r"\b", text) for m in later_members
        ):
            citers_of_any_later.append(doc.name)
    native = {
        "chain": "EPISTEMIC_HANDOFF_FOUNDATION",
        "correction_ordinal": ordinal + 1,
        "corrected_version": corrected,
        "invalidated_version": invalidated,
    }
    corrected_epoch = chain_added.get(corrected)
    # Shared observations carry RAW world facts only (citation lists and
    # first-added epochs). The blame join — who relies SOLELY on the
    # invalidated version, gated by temporal eligibility — is decision work
    # each arm must do (or fail to do) itself.
    obs = {
        "corrected_version_sha256": sha256_file(corrected_path),
        "corrected_first_added_epoch": corrected_epoch,
        "later_docs_citing_invalidated": sorted(citers_of_invalidated),
        "later_docs_citing_any_later_member": sorted(citers_of_any_later),
        "doc_first_added_epochs": {
            name: doc_added.get(name)
            for name in sorted(set(citers_of_invalidated) | set(citers_of_any_later))
        },
    }
    # Referee-only derivation (ground truth), not shared with the arms.
    sole_reliance = []
    for name in citers_of_invalidated:
        if name in set(citers_of_any_later):
            continue
        added = doc_added.get(name)
        if corrected_epoch is not None and added is not None and added < corrected_epoch:
            continue  # predates the correction; exonerated
        sole_reliance.append(name)
    defects = ["reliance_on_superseded_version"] if sole_reliance else []
    emit("SUPERSEDE", native, obs, defects, "real", f"chain:{ordinal}")
    supersede_count += 1

# --------------------------------------------------------------------------
# Family LIFECYCLE: task lifecycle event ordering (OBL-17-shaped)
# Native claim: each task-claim file accretes lifecycle events (open ->
# progress -> done) recorded as git commits touching the file.
# World observation: commit timestamps for the file, oldest first.
# --------------------------------------------------------------------------

life_count = 0
for task_file in sorted(TASKS.glob("TASK-*.json")):
    out = git(WORKSPACE, "log", "--follow", "--format=%ct", "--", str(task_file.relative_to(WORKSPACE)))
    if out is None or not out.strip():
        continue
    timestamps = [int(x) for x in out.split()][::-1]  # oldest first
    try:
        task = json.loads(task_file.read_text(encoding="utf-8"))
    except ValueError:
        task = {}
    native = {
        "source_doc": str(task_file.relative_to(WORKSPACE)),
        "task_id": task.get("task_id"),
        "status": task.get("status"),
    }
    obs = {"lifecycle_event_timestamps": timestamps}
    defects = []
    if any(b <= a for a, b in zip(timestamps, timestamps[1:])):
        defects.append("lifecycle_order_violation")
    emit("LIFECYCLE", native, obs, defects, "real", task_file.name)
    life_count += 1

# --------------------------------------------------------------------------
# Seeded defects: perturbed clones of clean real records, one per defect
# type per family, deterministic selection (first N clean records).
# --------------------------------------------------------------------------

by_family: dict[str, list[int]] = {}
for idx, rec in enumerate(records):
    if not truths[idx]["defective"]:
        by_family.setdefault(rec["family"], []).append(idx)


def seed_from(family: str, nth: int) -> tuple[dict, dict] | None:
    pool = by_family.get(family, [])
    if nth >= len(pool):
        return None
    src = records[pool[nth]]
    return json.loads(json.dumps(src["native"])), json.loads(json.dumps(src["observations"]))


seeded = 0
for nth in range(3):
    pair = seed_from("REF", nth * 2)
    if pair:
        native, obs = pair
        flipped = ("0" if native["claimed_sha256"][0] != "0" else "1") + native["claimed_sha256"][1:] if native.get("claimed_sha256") else None
        if flipped:
            native["claimed_sha256"] = flipped
            emit("REF", native, obs, ["pin_hash_mismatch"], "seeded", f"seed-ref-hash-{nth}")
            seeded += 1
    pair = seed_from("REF", nth * 2 + 1)
    if pair:
        native, obs = pair
        native["referenced_record"] = f"NONEXISTENT_{nth}_" + native["referenced_record"]
        obs["referenced_record_found"] = False
        obs["found_at_archived_location"] = False
        obs["observed_sha256"] = None
        emit("REF", native, obs, ["missing_reference_target"], "seeded", f"seed-ref-missing-{nth}")
        seeded += 1
scope_seeded = 0
for idx in by_family.get("SCOPE", []):
    if scope_seeded >= 3:
        break
    src = records[idx]
    if src["observations"].get("commit_changed_paths") is None or not src["native"].get("claimed_paths"):
        continue
    native = json.loads(json.dumps(src["native"]))
    obs = json.loads(json.dumps(src["observations"]))
    obs["commit_changed_paths"] = sorted(obs["commit_changed_paths"] + ["src/OUT_OF_SCOPE_INJECTED.ts"])
    emit("SCOPE", native, obs, ["recorded_use_outside_declared_scope"], "seeded", f"seed-scope-{scope_seeded}")
    seeded += 1
    scope_seeded += 1
for nth in range(3):
    pair = seed_from("LIFECYCLE", nth)
    if pair:
        native, obs = pair
        ts = obs["lifecycle_event_timestamps"]
        if len(ts) >= 2:
            obs["lifecycle_event_timestamps"] = [ts[0]] + [ts[0]] + ts[1:]
        else:
            obs["lifecycle_event_timestamps"] = ts + ts
        emit("LIFECYCLE", native, obs, ["lifecycle_order_violation"], "seeded", f"seed-life-{nth}")
        seeded += 1
pair = seed_from("SUPERSEDE", 0)
if pair:
    native, obs = pair
    fake = "SEEDED_STALE_CITER_20260810.md"
    obs["later_docs_citing_invalidated"] = sorted(obs["later_docs_citing_invalidated"] + [fake])
    epoch = obs.get("corrected_first_added_epoch") or 0
    obs["doc_first_added_epochs"][fake] = epoch + 86400  # committed after the correction
    emit("SUPERSEDE", native, obs, ["reliance_on_superseded_version"], "seeded", "seed-supersede-0")
    seeded += 1

with open(OUT_DIR / "corpus.jsonl", "w", encoding="utf-8", newline="\n") as fh:
    for rec in records:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
with open(OUT_DIR / "truth.jsonl", "w", encoding="utf-8", newline="\n") as fh:
    for row in truths:
        fh.write(json.dumps(row, sort_keys=True) + "\n")

defective = sum(1 for t in truths if t["defective"])
print(
    f"corpus: {len(records)} records "
    f"(REF={ref_count} SCOPE={scope_count} SUPERSEDE={supersede_count} "
    f"LIFECYCLE={life_count} seeded={seeded}) | defective={defective} "
    f"clean={len(records) - defective}"
)
for fam in ("REF", "SCOPE", "SUPERSEDE", "LIFECYCLE"):
    fam_truth = [t for i, t in enumerate(truths) if records[i]["family"] == fam]
    fam_def = sum(1 for t in fam_truth if t["defective"])
    print(f"  {fam:10} n={len(fam_truth):3}  defective={fam_def}")
