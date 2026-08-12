"""Portable, stdlib-only preflight for native evidence and host fact profiles.

This is the only shipping WP1 code surface.  It validates observations and,
when supplied, a host-produced fact profile.  It never builds an engine
request, invokes a runner, observes mutable host state, or performs effects.

``READY`` means only that this bounded preflight found sufficient,
noncontradictory native evidence (and that the optional profile agrees with
it).  It is not an engine decision or a pass.  ``REJECTED_INVALID`` records a
detectable contradiction or malformed assertion. ``INSUFFICIENT_EVIDENCE``
records unavailable host semantics and is an abstention, never a pass.

Fail-closed boundary law (F-WP1-010..013):

- Status precedence is ``REJECTED_INVALID`` over ``INSUFFICIENT_EVIDENCE``
  over ``READY``: a detectable contradiction is never downgraded to an
  abstention because some other control layer also abstained.  Every control
  layer that can run does run, and its issues are reported together.
- The JSONL boundary parses strictly: duplicate object members are rejected,
  line acquisition is bounded before allocation, and parser resource errors
  become deterministic per-line results, never process crashes.
- An empty or blank-only stream is ``INSUFFICIENT_EVIDENCE``, exit 2.  A
  caller gating on the exit status can never mistake "no evidence supplied"
  for "all records READY".
- Integers must lie in the governed engine's safe-integer domain
  (|n| <= 9007199254740991); out-of-domain integers are a domain violation.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from fnmatch import fnmatchcase
from typing import Any, TextIO

RESULT_FORMAT_VERSION = "RR-PORTABLE-PREFLIGHT-1"
FACT_PROFILE_FORMAT_VERSION = "RR-PORTABLE-FACT-PROFILE-1"

READY = "READY"
REJECTED_INVALID = "REJECTED_INVALID"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
RESULT_STATUSES = frozenset({READY, REJECTED_INVALID, INSUFFICIENT_EVIDENCE})

MAX_DEPTH = 32
MAX_ITEMS = 256
MAX_STRING = 4096
MAX_JSONL_BYTES = 4 * 1024 * 1024
SAFE_INTEGER_MAX = 9007199254740991
SAFE_INTEGER_MIN = -9007199254740991
HEX64 = re.compile(r"^[0-9A-F]{64}$")

FAMILY_OBLIGATION = {
    "REF": "OBL-02",
    "SCOPE": "OBL-03",
    "SUPERSEDE": "OBL-15",
    "LIFECYCLE": "OBL-17",
}


@dataclasses.dataclass(frozen=True, slots=True)
class PreflightIssue:
    """One stable, machine-readable preflight issue."""

    code: str
    pointer: str
    message: str
    remediation: str
    evidence_pointers: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "pointer": self.pointer,
            "message": self.message,
            "remediation": self.remediation,
            "evidence_pointers": list(self.evidence_pointers),
        }


@dataclasses.dataclass(frozen=True, slots=True)
class PreflightResult:
    """Versioned result whose status is exactly one fallback taxonomy value."""

    status: str
    record_id: str | None
    family: str | None
    obligation_id: str | None
    native_evidence_sha256: str | None
    profile_checked: bool
    issues: tuple[PreflightIssue, ...]

    def __post_init__(self) -> None:
        if self.status not in RESULT_STATUSES:
            raise ValueError(f"unknown preflight status {self.status!r}")

    @property
    def ready(self) -> bool:
        return self.status == READY

    def as_dict(self) -> dict[str, Any]:
        return {
            "format_version": RESULT_FORMAT_VERSION,
            "status": self.status,
            "record_id": self.record_id,
            "family": self.family,
            "obligation_id": self.obligation_id,
            "native_evidence_sha256": self.native_evidence_sha256,
            "profile_checked": self.profile_checked,
            "issues": [problem.as_dict() for problem in self.issues],
        }


@dataclasses.dataclass(frozen=True, slots=True)
class _Assessment:
    status: str
    issues: tuple[PreflightIssue, ...]
    facts: dict[str, Any] | None = None
    derivations: dict[str, list[str]] | None = None


def _issue(
    code: str,
    pointer: str,
    message: str,
    remediation: str,
    *evidence_pointers: str,
) -> PreflightIssue:
    return PreflightIssue(code, pointer, message, remediation, tuple(evidence_pointers))


def _invalid(*issues: PreflightIssue) -> _Assessment:
    return _Assessment(REJECTED_INVALID, tuple(issues))


def _insufficient(*issues: PreflightIssue) -> _Assessment:
    return _Assessment(INSUFFICIENT_EVIDENCE, tuple(issues))


def _walk_json(value: Any, pointer: str = "", depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise ValueError(f"JSON nesting exceeds {MAX_DEPTH} at {pointer or '/'}")
    if value is None or isinstance(value, (bool, int, str)):
        if isinstance(value, str) and len(value) > MAX_STRING:
            raise ValueError(f"string exceeds {MAX_STRING} characters at {pointer or '/'}")
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and not SAFE_INTEGER_MIN <= value <= SAFE_INTEGER_MAX
        ):
            raise ValueError(
                f"integer outside the governed safe-integer domain at {pointer or '/'}"
            )
        return
    if isinstance(value, float):
        raise ValueError(f"floating-point values are forbidden at {pointer or '/'}")
    if isinstance(value, Mapping):
        if len(value) > MAX_ITEMS:
            raise ValueError(f"object exceeds {MAX_ITEMS} members at {pointer or '/'}")
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(f"non-string object key at {pointer or '/'}")
            escaped = key.replace("~", "~0").replace("/", "~1")
            _walk_json(child, f"{pointer}/{escaped}", depth + 1)
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        if len(value) > MAX_ITEMS:
            raise ValueError(f"array exceeds {MAX_ITEMS} items at {pointer or '/'}")
        for index, child in enumerate(value):
            _walk_json(child, f"{pointer}/{index}", depth + 1)
        return
    raise ValueError(f"non-JSON value {type(value).__name__} at {pointer or '/'}")


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON for the bounded integer-only domain."""

    _walk_json(value)
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(raw) > MAX_JSONL_BYTES:
        raise ValueError(f"canonical JSON exceeds {MAX_JSONL_BYTES} bytes")
    return raw


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest().upper()


def _hash64(value: Any) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= MAX_ITEMS
        and all(isinstance(item, str) and 0 < len(item) <= MAX_STRING for item in value)
    )


def _scope_hash(items: Sequence[str]) -> str:
    """Injective digest of a path set: canonical JSON array, not a join.

    The historical newline join (still visible in the committed
    ``proof/arm_b1.py`` experiment arm) is not injective: an item containing
    a newline can collide with two separate items (F-WP1-013).  The portable
    surface digests the sorted canonical JSON array instead.
    """

    return (
        hashlib.sha256(canonical_json_bytes(sorted(items))).hexdigest().upper()
    )


def _in_scope(path: str, claimed: Sequence[str]) -> bool:
    """Match opaque, case-sensitive path strings without OS normalization."""

    for pattern in claimed:
        if path == pattern or fnmatchcase(path, pattern):
            return True
        if pattern.endswith("/**") and path.startswith(pattern[:-2]):
            return True
    return False


def _check_record(record: Any) -> tuple[dict[str, Any] | None, tuple[PreflightIssue, ...]]:
    if not isinstance(record, dict):
        return None, (
            _issue(
                "PREFLIGHT_RECORD_NOT_OBJECT",
                "/",
                "native evidence is not an object",
                "supply one JSON object per record",
            ),
        )
    allowed = {"record_id", "family", "native", "observations", "state_revision"}
    extra = sorted(set(record) - allowed)
    if extra:
        return None, (
            _issue(
                "PREFLIGHT_CALLER_ASSERTION",
                "/",
                f"closed native-evidence record contains unsupported fields {extra}",
                "remove caller conclusions and retain only native observations",
            ),
        )
    record_id = record.get("record_id")
    if not isinstance(record_id, str) or not (0 < len(record_id) <= MAX_STRING):
        return None, (
            _issue(
                "PREFLIGHT_RECORD_ID_INVALID",
                "/record_id",
                "record_id is missing or malformed",
                "supply one stable nonempty record identifier",
            ),
        )
    try:
        canonical_json_bytes(record)
    except (TypeError, ValueError) as exc:
        return None, (
            _issue(
                "PREFLIGHT_JSON_DOMAIN_INVALID",
                "/",
                f"native evidence is outside the bounded JSON domain: {exc}",
                "use bounded integer-only JSON observations",
            ),
        )
    family = record.get("family")
    if family not in FAMILY_OBLIGATION:
        return record, (
            _issue(
                "PREFLIGHT_FAMILY_UNCALIBRATED",
                "/family",
                f"no portable calibration rule exists for family {family!r}",
                "define and test an integration-owned native precondition",
            ),
        )
    if record.get("native") is None or record.get("observations") is None:
        return record, (
            _issue(
                "PREFLIGHT_NATIVE_EVIDENCE_MISSING",
                "/",
                "native claims or observations are unavailable",
                "collect both native claims and world observations",
            ),
        )
    if not isinstance(record.get("native"), dict) or not isinstance(
        record.get("observations"), dict
    ):
        return None, (
            _issue(
                "PREFLIGHT_NATIVE_EVIDENCE_INVALID",
                "/",
                "native and observations members must be objects",
                "repair the malformed evidence envelope",
            ),
        )
    revision = record.get("state_revision")
    if revision is not None and (
        not isinstance(revision, str) or not (0 < len(revision) <= MAX_STRING)
    ):
        return None, (
            _issue(
                "PREFLIGHT_REVISION_INVALID",
                "/state_revision",
                "state_revision is malformed",
                "use a stable nonempty revision string or omit it",
            ),
        )
    return record, ()


def _assess_ref(record: Mapping[str, Any]) -> _Assessment:
    native, observed = record["native"], record["observations"]
    claimed_path = native.get("claimed_path")
    referenced_record = native.get("referenced_record")
    aliases = [value for value in (claimed_path, referenced_record) if value is not None]
    if any(not isinstance(value, str) or not value for value in aliases):
        return _invalid(
            _issue(
                "PREFLIGHT_REF_IDENTITY_INVALID",
                "/native",
                "reference identity is malformed",
                "record a nonempty claimed_path or referenced_record",
            )
        )
    if claimed_path is not None and referenced_record is not None and claimed_path != referenced_record:
        return _invalid(
            _issue(
                "PREFLIGHT_REF_ALIAS_CONTRADICTION",
                "/native",
                "claimed_path and referenced_record assert different exact targets",
                "resolve the alias/path contradiction from one native snapshot",
                "/native/claimed_path",
                "/native/referenced_record",
            )
        )
    if not aliases:
        return _insufficient(
            _issue(
                "PREFLIGHT_REF_IDENTITY_MISSING",
                "/native",
                "no exact reference identity was observed",
                "collect claimed_path or referenced_record",
            )
        )
    found = observed.get("referenced_record_found")
    if found is None:
        return _insufficient(
            _issue(
                "PREFLIGHT_REF_LOOKUP_MISSING",
                "/observations/referenced_record_found",
                "reference presence was not observed",
                "record one explicit true/false lookup result",
            )
        )
    if not isinstance(found, bool):
        return _invalid(
            _issue(
                "PREFLIGHT_REF_LOOKUP_INVALID",
                "/observations/referenced_record_found",
                "reference presence testimony is not Boolean",
                "repair the malformed lookup observation",
            )
        )
    archived = observed.get("found_at_archived_location", False)
    if not isinstance(archived, bool):
        return _invalid(
            _issue(
                "PREFLIGHT_REF_ARCHIVE_FLAG_INVALID",
                "/observations/found_at_archived_location",
                "archive-location testimony is not Boolean",
                "repair the malformed location observation",
            )
        )
    claimed_digest = native.get("claimed_sha256")
    observed_digest = observed.get("observed_sha256")
    if claimed_digest is not None and not _hash64(claimed_digest):
        return _invalid(
            _issue(
                "PREFLIGHT_REF_CLAIMED_DIGEST_INVALID",
                "/native/claimed_sha256",
                "claimed digest is not uppercase SHA-256",
                "repair the malformed digest assertion",
            )
        )
    if found and observed_digest is None:
        return _insufficient(
            _issue(
                "PREFLIGHT_REF_CONTENT_MISSING",
                "/observations/observed_sha256",
                "found reference lacks content testimony",
                "hash the bytes from the same lookup snapshot",
            )
        )
    if observed_digest is not None and not _hash64(observed_digest):
        return _invalid(
            _issue(
                "PREFLIGHT_REF_OBSERVED_DIGEST_INVALID",
                "/observations/observed_sha256",
                "observed digest is not uppercase SHA-256",
                "repair the malformed digest observation",
            )
        )
    if not found and observed_digest is not None and not archived:
        return _invalid(
            _issue(
                "PREFLIGHT_REF_PRESENCE_CONTRADICTION",
                "/observations",
                "absence conflicts with current-location content testimony",
                "repeat one atomic lookup and retain one coherent result",
                "/observations/referenced_record_found",
                "/observations/observed_sha256",
            )
        )
    if found and archived:
        return _invalid(
            _issue(
                "PREFLIGHT_REF_LOCATION_CONTRADICTION",
                "/observations",
                "current and archived location testimony conflict",
                "report archived recovery only when the current target is absent",
            )
        )
    reference = aliases[0]
    versions: list[dict[str, str]] = []
    if found:
        assert isinstance(observed_digest, str)
        versions.append({"record_id": reference, "revision_sha256": observed_digest})
        if claimed_digest is not None:
            versions.append({"record_id": reference, "revision_sha256": claimed_digest})
    return _Assessment(
        READY,
        (),
        {"exact_reference": reference, "record_versions": versions},
        {
            "exact_reference": ["/native/claimed_path", "/native/referenced_record"],
            "record_versions": [
                "/native/claimed_sha256",
                "/observations/referenced_record_found",
                "/observations/observed_sha256",
            ],
        },
    )


def _assess_scope(record: Mapping[str, Any]) -> _Assessment:
    native, observed = record["native"], record["observations"]
    claimed = native.get("claimed_paths")
    if claimed is None:
        return _insufficient(
            _issue(
                "PREFLIGHT_SCOPE_CLAIM_MISSING",
                "/native/claimed_paths",
                "claimed path set is unavailable",
                "collect the complete bounded claim set",
            )
        )
    if not _string_list(claimed):
        return _invalid(
            _issue(
                "PREFLIGHT_SCOPE_CLAIM_INVALID",
                "/native/claimed_paths",
                "claimed path set is malformed",
                "repair the bounded string list without interpreting paths locally",
            )
        )
    named = native.get("result_commit_named")
    found = observed.get("commit_found")
    if named is None or found is None:
        return _insufficient(
            _issue(
                "PREFLIGHT_SCOPE_LOOKUP_MISSING",
                "/observations/commit_found",
                "commit identity or lookup result is unavailable",
                "record result_commit_named and commit_found as Booleans",
            )
        )
    if not isinstance(named, bool) or not isinstance(found, bool):
        return _invalid(
            _issue(
                "PREFLIGHT_SCOPE_LOOKUP_INVALID",
                "/observations/commit_found",
                "commit identity or lookup testimony is malformed",
                "repair the Boolean evidence",
            )
        )
    changed = observed.get("commit_changed_paths")
    if found and changed is None:
        return _insufficient(
            _issue(
                "PREFLIGHT_SCOPE_CONTENT_MISSING",
                "/observations/commit_changed_paths",
                "found commit lacks its complete changed-path observation",
                "collect the bounded changed-path set from the same snapshot",
            )
        )
    if changed is not None and not _string_list(changed):
        return _invalid(
            _issue(
                "PREFLIGHT_SCOPE_CONTENT_INVALID",
                "/observations/commit_changed_paths",
                "changed-path observation is malformed",
                "repair the bounded opaque string list",
            )
        )
    if not found and changed is not None:
        return _invalid(
            _issue(
                "PREFLIGHT_SCOPE_PRESENCE_CONTRADICTION",
                "/observations",
                "missing commit conflicts with a changed-path set",
                "repeat commit resolution and retain one coherent result",
            )
        )
    declared = _scope_hash(claimed) if claimed else None
    if named and not found:
        recorded = None
    elif changed is None:
        recorded = declared
    else:
        outside = [path for path in changed if not _in_scope(path, claimed)]
        recorded = declared if not outside else _scope_hash(sorted(claimed + outside))
    kinds = (["ADOPTION"] if claimed else []) + (
        ["INTENDED_USE"] if native.get("status") is not None else []
    )
    return _Assessment(
        READY,
        (),
        {
            "declaration_effective_at": 0,
            "interval_end_exclusive": 1,
            "declaration_kinds": kinds,
            "declared_scope_sha256": declared,
            "recorded_use_scope_sha256": recorded,
        },
        {
            "declaration_effective_at": ["/native/claimed_paths"],
            "interval_end_exclusive": ["/observations/commit_found"],
            "declaration_kinds": ["/native/claimed_paths", "/native/status"],
            "declared_scope_sha256": ["/native/claimed_paths"],
            "recorded_use_scope_sha256": [
                "/native/claimed_paths",
                "/native/result_commit_named",
                "/observations/commit_found",
                "/observations/commit_changed_paths",
            ],
        },
    )


def _assess_supersede(record: Mapping[str, Any]) -> _Assessment:
    native, observed = record["native"], record["observations"]
    required = (
        ("/native/correction_ordinal", native.get("correction_ordinal")),
        ("/observations/corrected_version_sha256", observed.get("corrected_version_sha256")),
        ("/observations/corrected_first_added_epoch", observed.get("corrected_first_added_epoch")),
        ("/observations/doc_first_added_epochs", observed.get("doc_first_added_epochs")),
        ("/observations/later_docs_citing_invalidated", observed.get("later_docs_citing_invalidated")),
        ("/observations/later_docs_citing_any_later_member", observed.get("later_docs_citing_any_later_member")),
    )
    missing = [pointer for pointer, value in required if value is None]
    if missing:
        return _insufficient(
            _issue(
                "PREFLIGHT_SUPERSEDE_EVIDENCE_MISSING",
                missing[0],
                f"supersession evidence is incomplete: {missing}",
                "collect corrected bytes, citer identities, and citer chronology",
            )
        )
    digest = observed["corrected_version_sha256"]
    ordinal = native["correction_ordinal"]
    corrected_epoch = observed["corrected_first_added_epoch"]
    epochs = observed["doc_first_added_epochs"]
    invalidated = observed["later_docs_citing_invalidated"]
    any_later = observed["later_docs_citing_any_later_member"]
    if not _hash64(digest) or not _integer(ordinal) or ordinal < 0:
        return _invalid(
            _issue(
                "PREFLIGHT_SUPERSEDE_IDENTITY_INVALID",
                "/observations/corrected_version_sha256",
                "corrected digest or ordinal is malformed",
                "repair the digest and nonnegative chain ordinal",
            )
        )
    if not _integer(corrected_epoch) or corrected_epoch < 0:
        return _invalid(
            _issue(
                "PREFLIGHT_SUPERSEDE_TIME_INVALID",
                "/observations/corrected_first_added_epoch",
                "corrected-member epoch is malformed",
                "repair the nonnegative integer timestamp",
            )
        )
    if not isinstance(epochs, dict) or not all(
        isinstance(name, str) and _integer(epoch) and epoch >= 0
        for name, epoch in epochs.items()
    ):
        return _invalid(
            _issue(
                "PREFLIGHT_SUPERSEDE_CHRONOLOGY_INVALID",
                "/observations/doc_first_added_epochs",
                "citer chronology is malformed",
                "repair the closed document-to-epoch mapping",
            )
        )
    if not _string_list(invalidated) or not _string_list(any_later):
        return _invalid(
            _issue(
                "PREFLIGHT_SUPERSEDE_CITERS_INVALID",
                "/observations",
                "citer identity evidence is malformed",
                "repair the bounded raw citer lists",
            )
        )
    missing_epochs = sorted((set(invalidated) | set(any_later)) - set(epochs))
    if missing_epochs:
        return _insufficient(
            _issue(
                "PREFLIGHT_SUPERSEDE_CHRONOLOGY_MISSING",
                "/observations/doc_first_added_epochs",
                f"citer chronology is unavailable for {missing_epochs}",
                "observe a first-added epoch for every citer",
            )
        )
    any_later_set = set(any_later)
    blamed = sorted(
        name
        for name in invalidated
        if name not in any_later_set and epochs[name] >= corrected_epoch
    )
    return _Assessment(
        READY,
        (),
        {
            "corrected_version_sha256": digest,
            "correction_target_ordinal": ordinal,
            "invalidated_path_ids": blamed,
            "independent_valid_path_ids": sorted(any_later_set | set(invalidated)),
        },
        {
            "corrected_version_sha256": ["/observations/corrected_version_sha256"],
            "correction_target_ordinal": ["/native/correction_ordinal"],
            "invalidated_path_ids": [
                "/observations/corrected_first_added_epoch",
                "/observations/doc_first_added_epochs",
                "/observations/later_docs_citing_invalidated",
                "/observations/later_docs_citing_any_later_member",
            ],
            "independent_valid_path_ids": [
                "/observations/later_docs_citing_invalidated",
                "/observations/later_docs_citing_any_later_member",
            ],
        },
    )


def _timestamp_assessment(timestamps: Any) -> _Assessment | None:
    if timestamps is None:
        return None
    if not isinstance(timestamps, list) or not timestamps or len(timestamps) > MAX_ITEMS:
        return _invalid(
            _issue(
                "PREFLIGHT_LIFECYCLE_TIMESTAMPS_INVALID",
                "/observations/lifecycle_event_timestamps",
                "lifecycle timestamp testimony is malformed",
                "record a bounded nonempty array of nonnegative integers",
            )
        )
    if any(not _integer(value) or value < 0 for value in timestamps):
        return _invalid(
            _issue(
                "PREFLIGHT_LIFECYCLE_TIMESTAMPS_INVALID",
                "/observations/lifecycle_event_timestamps",
                "lifecycle timestamp testimony contains a malformed value",
                "repair the nonnegative integer timestamps",
            )
        )
    for index, (left, right) in enumerate(zip(timestamps, timestamps[1:])):
        if left >= right:
            return _invalid(
                _issue(
                    "PREFLIGHT_LIFECYCLE_NONINCREASING",
                    f"/observations/lifecycle_event_timestamps/{index + 1}",
                    "lifecycle timestamps are equal or decrease in native order",
                    "repair the contradictory native chronology before applicability",
                    f"/observations/lifecycle_event_timestamps/{index}",
                    f"/observations/lifecycle_event_timestamps/{index + 1}",
                )
            )
    return _Assessment(READY, ())


def _assess_lifecycle(record: Mapping[str, Any]) -> _Assessment:
    observed = record["observations"]
    timestamps = observed.get("lifecycle_event_timestamps")
    timestamp_result = _timestamp_assessment(timestamps)
    if timestamp_result is not None and timestamp_result.status == REJECTED_INVALID:
        return timestamp_result
    events = observed.get("lifecycle_events")
    if events is None:
        return _insufficient(
            _issue(
                "PREFLIGHT_LIFECYCLE_UNTYPED",
                "/observations/lifecycle_events",
                "noncontradictory timestamps do not establish EFFECTIVE or ACKNOWLEDGMENT semantics",
                "collect explicit event_type, occurred_at, and sequence evidence",
                "/observations/lifecycle_event_timestamps",
            )
        )
    expected_fields = {"event_type", "occurred_at", "sequence"}
    if not isinstance(events, list) or not events or len(events) > MAX_ITEMS:
        return _invalid(
            _issue(
                "PREFLIGHT_LIFECYCLE_EVENTS_INVALID",
                "/observations/lifecycle_events",
                "typed lifecycle evidence is malformed",
                "repair the bounded closed event list",
            )
        )
    if any(
        not isinstance(event, dict)
        or set(event) != expected_fields
        or event.get("event_type") not in {"EFFECTIVE", "ACKNOWLEDGMENT", "OTHER"}
        or not _integer(event.get("occurred_at"))
        or event["occurred_at"] < 0
        or not _integer(event.get("sequence"))
        or event["sequence"] < 0
        for event in events
    ):
        return _invalid(
            _issue(
                "PREFLIGHT_LIFECYCLE_EVENTS_INVALID",
                "/observations/lifecycle_events",
                "typed lifecycle evidence has a malformed or open event row",
                "use closed {event_type,occurred_at,sequence} rows",
            )
        )
    ordered = sorted(events, key=lambda event: event["sequence"])
    if len({event["sequence"] for event in ordered}) != len(ordered):
        return _invalid(
            _issue(
                "PREFLIGHT_LIFECYCLE_SEQUENCE_CONTRADICTION",
                "/observations/lifecycle_events",
                "typed lifecycle sequence identifiers are duplicated",
                "repair the contradictory native sequence",
            )
        )
    if any(
        left["occurred_at"] >= right["occurred_at"]
        for left, right in zip(ordered, ordered[1:])
    ):
        return _invalid(
            _issue(
                "PREFLIGHT_LIFECYCLE_NONINCREASING",
                "/observations/lifecycle_events",
                "typed lifecycle time contradicts strict native sequence order",
                "repair the contradictory native chronology before applicability",
            )
        )
    if timestamps is not None and timestamps != [event["occurred_at"] for event in ordered]:
        return _invalid(
            _issue(
                "PREFLIGHT_LIFECYCLE_VIEW_CONTRADICTION",
                "/observations",
                "typed events and timestamp-only views disagree",
                "retain one coherent atomic lifecycle observation",
            )
        )
    effective = [event for event in events if event["event_type"] == "EFFECTIVE"]
    acknowledgments = [
        event for event in events if event["event_type"] == "ACKNOWLEDGMENT"
    ]
    if len(effective) != 1 or len(acknowledgments) != 1:
        return _insufficient(
            _issue(
                "PREFLIGHT_LIFECYCLE_SEMANTICS_AMBIGUOUS",
                "/observations/lifecycle_events",
                "exact EFFECTIVE and ACKNOWLEDGMENT semantics are unavailable",
                "disambiguate to exactly one event of each required type",
            )
        )
    effective_event, acknowledgment = effective[0], acknowledgments[0]
    effective_index = ordered.index(effective_event)
    acknowledgment_index = ordered.index(acknowledgment)
    if acknowledgment_index != len(ordered) - 1 or effective_index >= acknowledgment_index:
        return _invalid(
            _issue(
                "PREFLIGHT_LIFECYCLE_ORDER_CONTRADICTION",
                "/observations/lifecycle_events",
                "ACKNOWLEDGMENT is not terminal and strictly after EFFECTIVE",
                "repair the contradictory native order before applicability",
            )
        )
    sequences = [event["sequence"] for event in ordered]
    return _Assessment(
        READY,
        (),
        {
            "event_sequences": sequences,
            "nonroot_predecessor_sequences": sequences[:acknowledgment_index],
            "acknowledged_at": acknowledgment["occurred_at"],
            "effective_at": effective_event["occurred_at"],
            "terminal_predecessor_sequences": [ordered[-2]["sequence"]],
        },
        {
            "event_sequences": ["/observations/lifecycle_events"],
            "nonroot_predecessor_sequences": ["/observations/lifecycle_events"],
            "acknowledged_at": ["/observations/lifecycle_events"],
            "effective_at": ["/observations/lifecycle_events"],
            "terminal_predecessor_sequences": ["/observations/lifecycle_events"],
        },
    )


_ASSESSORS = {
    "REF": _assess_ref,
    "SCOPE": _assess_scope,
    "SUPERSEDE": _assess_supersede,
    "LIFECYCLE": _assess_lifecycle,
}


def _strict_equal(left: Any, right: Any) -> bool:
    """Type-strict JSON-tree equality: True is never equal to 1 (F-WP1-012)."""

    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(
            _strict_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _strict_equal(a, b) for a, b in zip(left, right)
        )
    if type(left) is not type(right):
        return False
    return left == right


def _profile_issues(
    profile: Any,
    record: Mapping[str, Any],
    assessment: _Assessment,
) -> tuple[PreflightIssue, ...]:
    """Validate a supplied profile as far as the available layers allow.

    When ``assessment.facts`` is ``None`` (the family assessor could not
    run), the two fact/derivation comparisons are skipped; every other check
    still runs, so a malformed or contradictory profile is never silently
    ignored on a non-READY path (F-WP1-012).
    """
    if not isinstance(profile, dict):
        return (
            _issue(
                "PREFLIGHT_PROFILE_NOT_OBJECT",
                "/fact_profile",
                "fact profile is not an object",
                "supply a closed portable fact-profile envelope",
            ),
        )
    required = {
        "format_version",
        "record_id",
        "obligation_id",
        "native_evidence_sha256",
        "facts",
        "derivations",
        "fabricated_fields",
    }
    if set(profile) != required:
        return (
            _issue(
                "PREFLIGHT_PROFILE_SHAPE_INVALID",
                "/fact_profile",
                f"closed profile fields differ (missing={sorted(required-set(profile))}, extra={sorted(set(profile)-required)})",
                "use the exact portable fact-profile envelope",
            ),
        )
    problems: list[PreflightIssue] = []
    obligation = FAMILY_OBLIGATION.get(record.get("family"))
    try:
        expected_digest = _sha256(record)
    except (TypeError, ValueError):
        expected_digest = None
    comparisons = (
        (
            profile["format_version"] == FACT_PROFILE_FORMAT_VERSION,
            "PREFLIGHT_PROFILE_VERSION_INVALID",
            "/fact_profile/format_version",
            "unknown fact-profile format version",
        ),
        (
            profile["record_id"] == record["record_id"],
            "PREFLIGHT_PROFILE_RECORD_MISMATCH",
            "/fact_profile/record_id",
            "profile is bound to a different record",
        ),
        (
            profile["obligation_id"] == obligation,
            "PREFLIGHT_PROFILE_OBLIGATION_MISMATCH",
            "/fact_profile/obligation_id",
            "profile obligation differs from the calibrated family",
        ),
        (
            profile["native_evidence_sha256"] == expected_digest,
            "PREFLIGHT_PROFILE_EVIDENCE_MISMATCH",
            "/fact_profile/native_evidence_sha256",
            "profile is stale or bound to different native evidence",
        ),
        (
            profile["fabricated_fields"] == [],
            "PREFLIGHT_PROFILE_FABRICATION_DECLARED",
            "/fact_profile/fabricated_fields",
            "profile declares fabricated semantic fields",
        ),
        (
            assessment.facts is None
            or _strict_equal(profile["facts"], assessment.facts),
            "PREFLIGHT_PROFILE_FACT_MISMATCH",
            "/fact_profile/facts",
            "profile facts differ from deterministic native-evidence validation",
        ),
        (
            assessment.facts is None
            or _strict_equal(profile["derivations"], assessment.derivations),
            "PREFLIGHT_PROFILE_DERIVATION_MISMATCH",
            "/fact_profile/derivations",
            "field-level evidence pointers differ from the calibrated mapping",
        ),
    )
    for matches, code, pointer, message in comparisons:
        if not matches:
            problems.append(
                _issue(
                    code,
                    pointer,
                    message,
                    "regenerate the host-owned profile from this exact observation",
                )
            )
    try:
        canonical_json_bytes(profile)
    except (TypeError, ValueError) as exc:
        problems.append(
            _issue(
                "PREFLIGHT_PROFILE_JSON_INVALID",
                "/fact_profile",
                f"profile is outside the bounded JSON domain: {exc}",
                "repair the malformed profile envelope",
            )
        )
    return tuple(problems)


def preflight(record: Any, fact_profile: Any | None = None) -> PreflightResult:
    """Classify one native record and optionally validate its host profile.

    Every control layer that can run does run — envelope validation, the
    family assessor, and profile validation — and their issues are reported
    together.  Status precedence is ``REJECTED_INVALID`` over
    ``INSUFFICIENT_EVIDENCE`` over ``READY``: a detectable contradiction on
    any layer is never downgraded to an abstention because another layer
    abstained (F-WP1-012).  ``profile_checked`` is ``True`` exactly when
    profile validation actually ran, never merely because a profile was
    supplied.
    """

    checked, envelope_issues = _check_record(record)
    record_id = record.get("record_id") if isinstance(record, dict) else None
    family = record.get("family") if isinstance(record, dict) else None
    obligation = FAMILY_OBLIGATION.get(family)
    evidence_digest: str | None = None
    if checked is not None:
        try:
            evidence_digest = _sha256(checked)
        except (TypeError, ValueError):
            evidence_digest = None
    if checked is None:
        return PreflightResult(
            REJECTED_INVALID,
            record_id if isinstance(record_id, str) else None,
            family if isinstance(family, str) else None,
            obligation,
            evidence_digest,
            False,
            envelope_issues,
        )
    assessment: _Assessment | None = None
    if (
        family in _ASSESSORS
        and isinstance(checked.get("native"), dict)
        and isinstance(checked.get("observations"), dict)
    ):
        assessment = _ASSESSORS[family](checked)
    profile_problems: tuple[PreflightIssue, ...] = ()
    profile_checked = False
    if fact_profile is not None:
        profile_problems = _profile_issues(
            fact_profile,
            checked,
            assessment if assessment is not None else _Assessment(INSUFFICIENT_EVIDENCE, ()),
        )
        profile_checked = True
    statuses = {READY}
    if envelope_issues or assessment is None:
        statuses.add(INSUFFICIENT_EVIDENCE)
    if assessment is not None:
        statuses.add(assessment.status)
    if profile_problems:
        statuses.add(REJECTED_INVALID)
    if REJECTED_INVALID in statuses:
        status = REJECTED_INVALID
    elif INSUFFICIENT_EVIDENCE in statuses:
        status = INSUFFICIENT_EVIDENCE
    else:
        status = READY
    issues = (
        tuple(envelope_issues)
        + (assessment.issues if assessment is not None else ())
        + profile_problems
    )
    return PreflightResult(
        status,
        record_id,
        family if isinstance(family, str) else None,
        obligation,
        evidence_digest,
        profile_checked,
        issues,
    )


def _reject_constant(token: str) -> None:
    raise ValueError(f"non-finite JSON constant {token}")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """object_pairs_hook that fails closed on duplicate members (F-WP1-011)."""

    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object member {key!r}")
        result[key] = value
    return result


def _bounded_lines(source: TextIO):
    """Yield (number, line, oversized) without unbounded line buffering.

    Characters are accumulated only up to ``MAX_JSONL_BYTES``; the remainder
    of an oversized line is drained chunk-by-chunk and discarded, so a
    newline-free flood cannot force an allocation proportional to its length
    (F-WP1-010).  One UTF-8 character is at least one byte, so a line whose
    character count exceeds the byte cap necessarily exceeds it in bytes.
    """

    number = 0
    buffer: list[str] = []
    buffered = 0
    oversized = False
    while True:
        chunk = source.read(65536)
        if not chunk:
            if buffer or oversized:
                number += 1
                yield number, "".join(buffer), oversized
            return
        start = 0
        while True:
            newline = chunk.find("\n", start)
            if newline == -1:
                tail = chunk[start:]
                if not oversized:
                    if buffered + len(tail) > MAX_JSONL_BYTES:
                        oversized = True
                        buffer.clear()
                        buffered = 0
                    else:
                        buffer.append(tail)
                        buffered += len(tail)
                break
            tail = chunk[start:newline]
            if not oversized and buffered + len(tail) > MAX_JSONL_BYTES:
                oversized = True
                buffer.clear()
                buffered = 0
            if not oversized:
                buffer.append(tail)
            number += 1
            yield number, "".join(buffer), oversized
            buffer.clear()
            buffered = 0
            oversized = False
            start = newline + 1


def _line_error(number: int, message: str) -> PreflightResult:
    return PreflightResult(
        REJECTED_INVALID,
        None,
        None,
        None,
        None,
        False,
        (
            _issue(
                "PREFLIGHT_JSONL_INVALID",
                "/",
                f"line {number}: {message}",
                "repair the JSONL row and retry",
            ),
        ),
    )


def process_jsonl(source: TextIO, sink: TextIO) -> int:
    """Process portable JSONL streams fail-closed.

    Returns 2 when any row is not READY **or when no row was supplied**: an
    empty or blank-only stream emits one INSUFFICIENT_EVIDENCE diagnostic
    row, so an exit-status gate can never mistake "no evidence supplied" for
    "all records READY" (F-WP1-010).  Rows are acquired with bounded
    buffering, parsed with duplicate-member rejection (F-WP1-011), and every
    parser resource error becomes a deterministic per-line result.
    """

    nonready = 0
    rows = 0
    for number, line, oversized in _bounded_lines(source):
        if not oversized and not line.strip():
            continue
        rows += 1
        if oversized or len(line.encode("utf-8")) > MAX_JSONL_BYTES:
            result = _line_error(number, f"row exceeds {MAX_JSONL_BYTES} bytes")
        else:
            try:
                payload = json.loads(
                    line,
                    parse_constant=_reject_constant,
                    object_pairs_hook=_reject_duplicate_pairs,
                )
                if isinstance(payload, dict) and "record" in payload:
                    if set(payload) - {"record", "fact_profile"}:
                        result = _line_error(number, "wrapper has unsupported fields")
                    else:
                        result = preflight(payload["record"], payload.get("fact_profile"))
                else:
                    result = preflight(payload)
            except (json.JSONDecodeError, ValueError, RecursionError) as exc:
                result = _line_error(number, f"{type(exc).__name__}: {exc}")
        nonready += result.status != READY
        sink.write(
            json.dumps(
                result.as_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )
    if rows == 0:
        empty = PreflightResult(
            INSUFFICIENT_EVIDENCE,
            None,
            None,
            None,
            None,
            False,
            (
                _issue(
                    "PREFLIGHT_STREAM_EMPTY",
                    "/",
                    "no native-evidence rows were supplied",
                    "supply at least one JSONL evidence row",
                ),
            ),
        )
        sink.write(
            json.dumps(
                empty.as_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )
        return 2
    return 2 if nonready else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="portable native-evidence/fact-profile preflight")
    parser.add_argument("--input", default="-", help="JSONL input path, or - for stdin")
    parser.add_argument("--output", default="-", help="JSONL output path, or - for stdout")
    args = parser.parse_args(argv)
    if args.input != "-" and args.output != "-":
        import os

        if os.path.abspath(args.input) == os.path.abspath(args.output):
            parser.error("input and output must differ: opening the output would truncate the input before any row is read")
    source = sys.stdin if args.input == "-" else open(args.input, "r", encoding="utf-8")
    sink = (
        sys.stdout
        if args.output == "-"
        else open(args.output, "w", encoding="utf-8", newline="\n")
    )
    try:
        return process_jsonl(source, sink)
    finally:
        if source is not sys.stdin:
            source.close()
        if sink is not sys.stdout:
            sink.close()


if __name__ == "__main__":
    raise SystemExit(main())
