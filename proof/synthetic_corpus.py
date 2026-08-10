"""Build the portable synthetic corpus for the proof harness.

The checked-in JSONL files use the exact top-level contract consumed by the
existing proof arms and referee:

* corpus: ``record_id``, ``family``, ``native``, ``observations``
* truth: ``record_id``, ``provenance``, ``defect_types``, ``defective``

Corpus rows contain native claims and raw observations only.  Mechanical
labels stay in the separately written truth rows.  Generation is a pure
function of ``SEED`` (recorded below) and explicit command-line arguments: it
does not read the workspace, clock, network, randomness, or environment.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import pathlib
import re
from collections.abc import Iterable


# Recorded corpus seed.  It keys every synthetic identifier and content hash.
SEED = 0x20260810
HERE = pathlib.Path(__file__).resolve().parent
FAMILIES = ("REF", "SCOPE", "SUPERSEDE", "LIFECYCLE")
COMMIT_RE = re.compile(r"\b([0-9a-f]{7,10})\b(?=[^0-9a-f]|$)")


def seeded_digest(seed: int, label: str) -> str:
    """Return a deterministic SHA-256-shaped value for synthetic content."""
    return hashlib.sha256(f"{seed}:{label}".encode()).hexdigest().upper()


def record_id(seed: int, family: str, case: str) -> str:
    return "REC_" + seeded_digest(seed, f"{family}:{case}")[:16]


def path_in_scope(path: str, claimed: list[str]) -> bool:
    """Mechanical SCOPE truth, including directory-recursive ``dir/**``."""
    for pattern in claimed:
        if path == pattern or fnmatch.fnmatch(path, pattern):
            return True
        if pattern.endswith("/**") and path.startswith(pattern[:-2]):
            return True
    return False


def commit_tokens(text: str) -> list[str]:
    """Return commit-shaped tokens; digit-only dates/counts do not qualify."""
    return [token for token in COMMIT_RE.findall(text) if re.search(r"[a-f]", token)]


def supersession_blame(
    corrected_epoch: int | None,
    invalidated_citers: Iterable[str],
    later_member_citers: Iterable[str],
    doc_epochs: dict[str, int | None],
) -> list[str]:
    """Mechanically identify temporally eligible, sole-version reliance."""
    later = set(later_member_citers)
    blamed: list[str] = []
    for name in invalidated_citers:
        if name in later:
            continue
        added = doc_epochs.get(name)
        if corrected_epoch is not None and added is not None and added < corrected_epoch:
            continue
        blamed.append(name)
    return sorted(blamed)


def build(seed: int = SEED) -> tuple[list[dict], list[dict]]:
    """Return corpus and mechanical truth rows in canonical case order."""
    records: list[dict] = []
    truths: list[dict] = []

    def emit(
        family: str,
        case: str,
        native: dict,
        observations: dict,
        defect_types: Iterable[str] = (),
    ) -> None:
        rid = record_id(seed, family, case)
        defects = sorted(defect_types)
        records.append(
            {
                "record_id": rid,
                "family": family,
                "native": native,
                "observations": observations,
            }
        )
        truths.append(
            {
                "record_id": rid,
                "provenance": "synthetic",
                "defect_types": defects,
                "defective": bool(defects),
            }
        )

    # REF / OBL-02: raw reference claims plus observed target state.
    clean_hash = seeded_digest(seed, "ref-clean-content")
    emit(
        "REF",
        "clean-pin",
        {
            "source_doc": "synthetic/handoff-clean.md",
            "referenced_record": "foundation-clean.md",
            "claimed_sha256": clean_hash,
        },
        {"referenced_record_found": True, "observed_sha256": clean_hash},
    )
    emit(
        "REF",
        "pin-mismatch",
        {
            "source_doc": "synthetic/handoff-mismatch.md",
            "referenced_record": "foundation-mismatch.md",
            "claimed_sha256": seeded_digest(seed, "ref-claimed-content"),
        },
        {
            "referenced_record_found": True,
            "observed_sha256": seeded_digest(seed, "ref-observed-content"),
        },
        ["pin_hash_mismatch"],
    )
    emit(
        "REF",
        "missing-target",
        {
            "source_doc": "synthetic/handoff-missing.md",
            "referenced_record": "missing.md",
            "claimed_sha256": seeded_digest(seed, "ref-missing-claim"),
        },
        {"referenced_record_found": False, "observed_sha256": None},
        ["missing_reference_target"],
    )
    emit(
        "REF",
        "stale-path",
        {
            "source_doc": "synthetic/task-stale.json",
            "referenced_record": "handoff-stale.md",
            "claimed_path": ".claude/handoffs/handoff-stale.md",
            "claimed_sha256": None,
        },
        {
            "referenced_record_found": False,
            "found_at_archived_location": True,
            "observed_sha256": seeded_digest(seed, "ref-archived-content"),
        },
        ["stale_reference_path"],
    )

    # SCOPE / OBL-03.  These raw rows are derived with the same mechanics as
    # the workspace extractor, including the two 2026-08-10 regressions.
    glob_claim = ["dir/**"]
    glob_changes = ["dir/README.md", "dir/nested/item.json"]
    assert all(path_in_scope(path, glob_claim) for path in glob_changes)
    emit(
        "SCOPE",
        "clean-recursive-glob",
        {
            "source_doc": "synthetic/task-glob.json",
            "task_id": "SYN-SCOPE-GLOB",
            "status": "done",
            "claimed_paths": glob_claim,
            "result_commit": "deadbee",
            "result_commit_named": bool(commit_tokens("implemented in deadbee")),
        },
        {"commit_found": True, "commit_changed_paths": glob_changes},
    )
    outside_changes = glob_changes + ["other/outside.txt"]
    outside = [path for path in outside_changes if not path_in_scope(path, glob_claim)]
    emit(
        "SCOPE",
        "outside-recursive-glob",
        {
            "source_doc": "synthetic/task-outside.json",
            "task_id": "SYN-SCOPE-OUTSIDE",
            "status": "done",
            "claimed_paths": glob_claim,
            "result_commit": "feed123",
            "result_commit_named": bool(commit_tokens("implemented in feed123")),
        },
        {"commit_found": True, "commit_changed_paths": outside_changes},
        ["recorded_use_outside_declared_scope"] if outside else [],
    )
    emit(
        "SCOPE",
        "unknown-commit",
        {
            "source_doc": "synthetic/task-unknown-commit.json",
            "task_id": "SYN-SCOPE-UNKNOWN",
            "status": "done",
            "claimed_paths": ["src/owned.py"],
            "result_commit": None,
            "result_commit_named": bool(commit_tokens("result abc1234")),
        },
        {"commit_found": False, "commit_changed_paths": None},
        ["unknown_result_commit"],
    )
    digit_only = commit_tokens("closed on 20260810 after 1234567 checks")
    emit(
        "SCOPE",
        "clean-digit-only-result",
        {
            "source_doc": "synthetic/task-digit-only.json",
            "task_id": "SYN-SCOPE-DIGITS",
            "status": "done",
            "claimed_paths": ["src/owned.py"],
            "result_commit": None,
            "result_commit_named": bool(digit_only),
        },
        {"commit_found": False, "commit_changed_paths": None},
    )

    # SUPERSEDE / OBL-15.  Timestamps are fixed logical epochs, not a clock.
    corrected_epoch = 200
    corrected_hash = seeded_digest(seed, "superseding-version")
    supersede_native = {
        "chain": "SYNTHETIC_FOUNDATION",
        "correction_ordinal": 2,
        "corrected_version": "SYNTHETIC_FOUNDATION_0_2.md",
        "invalidated_version": "SYNTHETIC_FOUNDATION_0_1.md",
    }

    pre_doc = "PRE_CORRECTION_CITER.md"
    pre_obs = {
        "corrected_version_sha256": corrected_hash,
        "corrected_first_added_epoch": corrected_epoch,
        "later_docs_citing_invalidated": [pre_doc],
        "later_docs_citing_any_later_member": [],
        "doc_first_added_epochs": {pre_doc: 100},
    }
    pre_blame = supersession_blame(
        corrected_epoch,
        pre_obs["later_docs_citing_invalidated"],
        pre_obs["later_docs_citing_any_later_member"],
        pre_obs["doc_first_added_epochs"],
    )
    emit(
        "SUPERSEDE",
        "clean-pre-correction-citer",
        dict(supersede_native),
        pre_obs,
        ["reliance_on_superseded_version"] if pre_blame else [],
    )

    post_doc = "POST_CORRECTION_CITER.md"
    post_obs = {
        "corrected_version_sha256": corrected_hash,
        "corrected_first_added_epoch": corrected_epoch,
        "later_docs_citing_invalidated": [post_doc],
        "later_docs_citing_any_later_member": [],
        "doc_first_added_epochs": {post_doc: 201},
    }
    post_blame = supersession_blame(
        corrected_epoch,
        post_obs["later_docs_citing_invalidated"],
        post_obs["later_docs_citing_any_later_member"],
        post_obs["doc_first_added_epochs"],
    )
    emit(
        "SUPERSEDE",
        "post-correction-sole-reliance",
        dict(supersede_native),
        post_obs,
        ["reliance_on_superseded_version"] if post_blame else [],
    )

    later_doc = "CITER_WITH_CURRENT_VERSION.md"
    later_obs = {
        "corrected_version_sha256": corrected_hash,
        "corrected_first_added_epoch": corrected_epoch,
        "later_docs_citing_invalidated": [later_doc],
        "later_docs_citing_any_later_member": [later_doc],
        "doc_first_added_epochs": {later_doc: 202},
    }
    later_blame = supersession_blame(
        corrected_epoch,
        later_obs["later_docs_citing_invalidated"],
        later_obs["later_docs_citing_any_later_member"],
        later_obs["doc_first_added_epochs"],
    )
    emit(
        "SUPERSEDE",
        "clean-current-version-citer",
        dict(supersede_native),
        later_obs,
        ["reliance_on_superseded_version"] if later_blame else [],
    )

    # LIFECYCLE / OBL-17: ordered, duplicate-event defect, and a legitimate
    # single-event lifecycle that distinguishes strict from calibrated B1.
    emit(
        "LIFECYCLE",
        "clean-ordered",
        {
            "source_doc": "synthetic/task-lifecycle-clean.json",
            "task_id": "SYN-LIFE-CLEAN",
            "status": "done",
        },
        {"lifecycle_event_timestamps": [100, 200, 300]},
    )
    duplicate_events = [100, 100, 300]
    emit(
        "LIFECYCLE",
        "duplicate-event",
        {
            "source_doc": "synthetic/task-lifecycle-duplicate.json",
            "task_id": "SYN-LIFE-DUPLICATE",
            "status": "done",
        },
        {"lifecycle_event_timestamps": duplicate_events},
        ["lifecycle_order_violation"]
        if any(b <= a for a, b in zip(duplicate_events, duplicate_events[1:]))
        else [],
    )
    emit(
        "LIFECYCLE",
        "clean-single-event",
        {
            "source_doc": "synthetic/task-lifecycle-single.json",
            "task_id": "SYN-LIFE-SINGLE",
            "status": "open",
        },
        {"lifecycle_event_timestamps": [100]},
    )

    return records, truths


def render_jsonl(rows: Iterable[dict]) -> bytes:
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()


def write(output_dir: pathlib.Path, seed: int = SEED) -> tuple[pathlib.Path, pathlib.Path]:
    records, truths = build(seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = output_dir / "corpus.synthetic.jsonl"
    truth_path = output_dir / "truth.synthetic.jsonl"
    corpus_path.write_bytes(render_jsonl(records))
    truth_path.write_bytes(render_jsonl(truths))
    return corpus_path, truth_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=pathlib.Path, default=HERE)
    parser.add_argument("--seed", type=lambda value: int(value, 0), default=SEED)
    args = parser.parse_args()
    corpus_path, truth_path = write(args.output_dir, args.seed)
    records, truths = build(args.seed)
    defective = sum(row["defective"] for row in truths)
    family_counts = " ".join(
        f"{family}={sum(row['family'] == family for row in records)}"
        for family in FAMILIES
    )
    print(
        f"synthetic corpus seed={args.seed:#x}: {len(records)} records "
        f"({family_counts}) defective={defective} clean={len(records) - defective}"
    )
    print(f"wrote {corpus_path} and {truth_path}")


if __name__ == "__main__":
    main()
