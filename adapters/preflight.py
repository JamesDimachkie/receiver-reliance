"""NON-SHIPPING checks retained for the stood-down reference-host experiment.

F-WP1-009 replaced the exported surface with ``portable_preflight``. This
module remains only for historical measurement/regression reproduction and is
not imported by ``adapters.__init__``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

FORMAT_VERSION = "RR-HOST-FACT-PROFILE-1"
MAX_DEPTH = 32
MAX_ITEMS = 256
MAX_STRING = 4096
MAX_RECORD_BYTES = 4 * 1024 * 1024
HEX64 = re.compile(r"^[0-9A-F]{64}$")

FACT_FIELDS = {
    "OBL-02": frozenset({"exact_reference", "record_versions"}),
    "OBL-03": frozenset(
        {
            "declaration_effective_at",
            "interval_end_exclusive",
            "declaration_kinds",
            "declared_scope_sha256",
            "recorded_use_scope_sha256",
        }
    ),
    "OBL-15": frozenset(
        {
            "corrected_version_sha256",
            "correction_target_ordinal",
            "invalidated_path_ids",
            "independent_valid_path_ids",
        }
    ),
    "OBL-17": frozenset(
        {
            "event_sequences",
            "nonroot_predecessor_sequences",
            "acknowledged_at",
            "effective_at",
            "terminal_predecessor_sequences",
        }
    ),
}


@dataclasses.dataclass(frozen=True, slots=True)
class ProfileIssue:
    """One obligation-naming, actionable preflight failure."""

    code: str
    obligation: str
    pointer: str
    message: str
    fix: str

    def as_dict(self) -> dict[str, str]:
        return dataclasses.asdict(self)

    def __str__(self) -> str:
        return (
            f"{self.code}/{self.obligation} at {self.pointer}: {self.message} "
            f"Fix: {self.fix}"
        )


def issue(
    code: str, obligation: str, pointer: str, message: str, fix: str
) -> ProfileIssue:
    return ProfileIssue(code, obligation, pointer, message, fix)


def _walk_json(value: Any, pointer: str = "", depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise ValueError(f"JSON nesting exceeds {MAX_DEPTH} at {pointer or '/'}")
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str) and len(value) > MAX_STRING:
            raise ValueError(f"string exceeds {MAX_STRING} characters at {pointer or '/'}")
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
    """Return the repository's integer-only JCS-compatible representation."""

    _walk_json(value)
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError(f"canonical JSON exceeds {MAX_RECORD_BYTES} bytes")
    return raw


def sha256_upper(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def record_sha256(record: Mapping[str, Any]) -> str:
    return sha256_upper(canonical_json_bytes(record))


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_str_list(value: Any, *, maximum: int = MAX_ITEMS) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= maximum
        and all(isinstance(item, str) and 0 < len(item) <= 160 for item in value)
    )


def _structural_fact_issues(obligation: str, facts: Any) -> list[ProfileIssue]:
    problems: list[ProfileIssue] = []
    if not isinstance(facts, dict):
        return [
            issue(
                "H3",
                obligation,
                "/facts",
                "fact profile is not an object",
                "submit the exact object returned by adapt_record",
            )
        ]
    expected = FACT_FIELDS.get(obligation)
    if expected is None:
        return [
            issue(
                "H4",
                obligation,
                "/obligation_id",
                "the reference adapter has no calibrated mapping for this obligation",
                "register and test a native applicability rule before invoking the engine",
            )
        ]
    missing, extra = sorted(expected - facts.keys()), sorted(facts.keys() - expected)
    if missing or extra:
        problems.append(
            issue(
                "H3",
                obligation,
                "/facts",
                f"closed profile fields differ (missing={missing}, extra={extra})",
                "use the adapter-produced facts without adding or deleting fields",
            )
        )
        return problems

    def malformed(pointer: str, detail: str) -> None:
        problems.append(
            issue(
                "H3",
                obligation,
                pointer,
                detail,
                "re-derive the profile from a complete native observation",
            )
        )

    if obligation == "OBL-02":
        if not isinstance(facts["exact_reference"], str) or not (
            0 < len(facts["exact_reference"]) <= 160
        ):
            malformed("/facts/exact_reference", "reference must be a nonempty string <=160")
        versions = facts["record_versions"]
        if not isinstance(versions, list) or len(versions) > MAX_ITEMS:
            malformed("/facts/record_versions", "version testimony must be an array <=256")
        else:
            for index, row in enumerate(versions):
                if not isinstance(row, dict) or set(row) != {"record_id", "revision_sha256"}:
                    malformed(f"/facts/record_versions/{index}", "testimony row has the wrong shape")
                elif not isinstance(row["record_id"], str) or not (
                    0 < len(row["record_id"]) <= 160
                ):
                    malformed(f"/facts/record_versions/{index}/record_id", "record id is invalid")
                elif not isinstance(row["revision_sha256"], str) or not HEX64.fullmatch(
                    row["revision_sha256"]
                ):
                    malformed(
                        f"/facts/record_versions/{index}/revision_sha256",
                        "revision digest must be 64 uppercase hexadecimal characters",
                    )
    elif obligation == "OBL-03":
        for name in ("declaration_effective_at", "interval_end_exclusive"):
            if not _is_int(facts[name]) or facts[name] < 0:
                malformed(f"/facts/{name}", "snapshot ordinal must be a nonnegative integer")
        if _is_int(facts["declaration_effective_at"]) and _is_int(
            facts["interval_end_exclusive"]
        ) and facts["declaration_effective_at"] >= facts["interval_end_exclusive"]:
            malformed(
                "/facts/interval_end_exclusive",
                "snapshot interval is empty or reversed",
            )
        if not _is_str_list(facts["declaration_kinds"]):
            malformed("/facts/declaration_kinds", "declaration kinds must be nonempty strings")
        for name in ("declared_scope_sha256", "recorded_use_scope_sha256"):
            value = facts[name]
            if value is not None and (not isinstance(value, str) or not HEX64.fullmatch(value)):
                malformed(f"/facts/{name}", "scope digest must be null or uppercase SHA-256")
    elif obligation == "OBL-15":
        if not isinstance(facts["corrected_version_sha256"], str) or not HEX64.fullmatch(
            facts["corrected_version_sha256"]
        ):
            malformed("/facts/corrected_version_sha256", "corrected version digest is invalid")
        if not _is_int(facts["correction_target_ordinal"]) or facts[
            "correction_target_ordinal"
        ] < 0:
            malformed("/facts/correction_target_ordinal", "ordinal must be nonnegative")
        for name in ("invalidated_path_ids", "independent_valid_path_ids"):
            if not _is_str_list(facts[name]):
                malformed(f"/facts/{name}", "path ids must be nonempty strings in an array <=256")
    elif obligation == "OBL-17":
        for name in (
            "event_sequences",
            "nonroot_predecessor_sequences",
            "terminal_predecessor_sequences",
        ):
            value = facts[name]
            if not isinstance(value, list) or len(value) > MAX_ITEMS or not all(
                _is_int(item) and item >= 0 for item in value
            ):
                malformed(f"/facts/{name}", "event sequence must contain nonnegative integers")
        for name in ("acknowledged_at", "effective_at"):
            if not _is_int(facts[name]) or facts[name] < 0:
                malformed(f"/facts/{name}", "event time must be a nonnegative integer")
    return problems


def validate_profile_envelope(
    envelope: Any,
    current_record: Mapping[str, Any],
    *,
    expected_obligation: str,
    expected_facts: Mapping[str, Any],
    expected_state_revision: str | None = None,
) -> tuple[ProfileIssue, ...]:
    """Validate shape, binding, freshness, and derivation agreement.

    Applicability is resolved by ``reference_host.preflight_profile`` before
    this function is entered, so a forced inapplicable profile never reaches
    a purely structural check and cannot be mistaken for a pass.
    """

    obligation = expected_obligation
    problems: list[ProfileIssue] = []
    if not isinstance(envelope, dict):
        return (
            issue(
                "H3",
                obligation,
                "/",
                "profile envelope is not an object",
                "pass the profile returned by adapt_record",
            ),
        )
    required = {
        "format_version",
        "obligation_id",
        "record_id",
        "observation_raw_sha256",
        "state_revision",
        "facts",
        "derivations",
        "fabricated_fields",
        "calibration",
    }
    if set(envelope) != required:
        problems.append(
            issue(
                "H3",
                obligation,
                "/",
                f"closed envelope fields differ (missing={sorted(required-set(envelope))}, "
                f"extra={sorted(set(envelope)-required)})",
                "use the unmodified adapter-produced envelope",
            )
        )
        return tuple(problems)
    if envelope["format_version"] != FORMAT_VERSION:
        problems.append(
            issue(
                "H3",
                obligation,
                "/format_version",
                "unknown fact-profile format",
                f"regenerate with format {FORMAT_VERSION}",
            )
        )
    if envelope["obligation_id"] != obligation:
        problems.append(
            issue(
                "H4",
                obligation,
                "/obligation_id",
                f"profile names {envelope['obligation_id']!r} but the record maps to {obligation}",
                "select the obligation through the adapter family mapping",
            )
        )
    record_id = current_record.get("record_id")
    if envelope["record_id"] != record_id:
        problems.append(
            issue(
                "H1",
                obligation,
                "/record_id",
                "profile is bound to a different record",
                "re-derive from the current record snapshot",
            )
        )
    try:
        current_digest = record_sha256(current_record)
    except (TypeError, ValueError) as exc:
        problems.append(
            issue(
                "H1",
                obligation,
                "/",
                f"current observation cannot be canonically bound: {exc}",
                "supply a finite integer-only JSON observation",
            )
        )
    else:
        if envelope["observation_raw_sha256"] != current_digest:
            problems.append(
                issue(
                    "H1",
                    obligation,
                    "/observation_raw_sha256",
                    "profile was derived from a stale or different observation snapshot",
                    "read state again and regenerate the profile before engine invocation",
                )
            )
    current_revision = current_record.get("state_revision")
    if envelope["state_revision"] != current_revision:
        problems.append(
            issue(
                "H1",
                obligation,
                "/state_revision",
                "profile state revision differs from the current record revision",
                "derive and invoke against the same atomic state snapshot",
            )
        )
    if expected_state_revision is not None and current_revision != expected_state_revision:
        problems.append(
            issue(
                "H1",
                obligation,
                "/state_revision",
                f"current revision {current_revision!r} is not required revision {expected_state_revision!r}",
                "retry from the required state revision or abort the decision",
            )
        )
    if envelope["fabricated_fields"] != []:
        problems.append(
            issue(
                "H3",
                obligation,
                "/fabricated_fields",
                "profile declares fabricated semantic fields",
                "refuse the mapping and collect the missing native observations",
            )
        )
    problems.extend(_structural_fact_issues(obligation, envelope["facts"]))
    if envelope["facts"] != expected_facts:
        problems.append(
            issue(
                "H3",
                obligation,
                "/facts",
                "submitted facts differ from deterministic re-derivation",
                "discard caller-supplied conclusions and use the adapter-derived facts",
            )
        )
    calibration = envelope["calibration"]
    if not isinstance(calibration, dict) or set(calibration) != {
        "applicable",
        "native_precondition",
        "evidence_pointers",
    }:
        problems.append(
            issue(
                "H4",
                obligation,
                "/calibration",
                "applicability evidence is absent or malformed",
                "regenerate the profile so its native precondition is recorded",
            )
        )
    elif calibration["applicable"] is not True:
        problems.append(
            issue(
                "H4",
                obligation,
                "/calibration/applicable",
                "a non-applicable profile was forced toward the engine",
                "record a refusal/abstention instead of invoking the engine",
            )
        )
    if not isinstance(envelope["derivations"], dict) or set(
        envelope["derivations"]
    ) != FACT_FIELDS[obligation]:
        problems.append(
            issue(
                "H3",
                obligation,
                "/derivations",
                "field-level derivation ledger is incomplete",
                "regenerate with the reference adapter and retain its derivation ledger",
            )
        )
    return tuple(problems)
