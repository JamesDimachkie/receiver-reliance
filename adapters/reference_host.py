"""NON-SHIPPING WP1 measurement experiment generalized from ``proof/arm_b1.py``.

F-WP1-009 stood down this general adapter, transcript, runner, replay, and
effect surface after three same-class boundary failures.  The module remains
only so the pinned all-408 experiment and historical regressions can be
reproduced.  It is intentionally absent from ``adapters.__all__`` and has no
command-line integration surface.  Shipping callers use
``adapters.portable_preflight``; no behavior here is claimable as fallback
capability.
"""

from __future__ import annotations

import argparse
import base64
import copy
import dataclasses
import fnmatch
import hashlib
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import weakref
from collections.abc import Callable, Mapping, Sequence
from typing import Any

EXPERIMENTAL_NON_SHIPPING = True

try:  # package import
    from .preflight import (
        FACT_FIELDS,
        FORMAT_VERSION,
        HEX64,
        ProfileIssue,
        canonical_json_bytes,
        issue,
        record_sha256,
        sha256_upper,
        validate_profile_envelope,
    )
except ImportError:  # direct script execution
    from preflight import (  # type: ignore
        FACT_FIELDS,
        FORMAT_VERSION,
        HEX64,
        ProfileIssue,
        canonical_json_bytes,
        issue,
        record_sha256,
        sha256_upper,
        validate_profile_envelope,
    )

FAMILY_OBLIGATION = {
    "REF": "OBL-02",
    "SCOPE": "OBL-03",
    "SUPERSEDE": "OBL-15",
    "LIFECYCLE": "OBL-17",
}
EFFECT_DOMAIN = "B1-SEMANTIC-EFFECT-RECEIPT-0.2"
HOST_EFFECT_BINDING_DOMAIN = "RR-HOST-EFFECT-BINDING-1"
NONCE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
EFFECT_RULES = {
    "OBL-19": (
        "OPR_6D9FA44D4442950313EA8047",
        {
            "receipt_event_sequence",
            "evidence_evaluation_sha256",
            "authorization_sha256",
            "gate_decision_sha256",
            "workflow_state_sha256",
            "invocation_sha256",
            "observed_effect_sha256",
        },
    ),
    "OBL-20": (
        "OPR_80083A7AF9FD2374306208D3",
        {
            "requested_effect_time",
            "invocation_authority_sha256",
            "authorized_effect_sha256",
            "invoked_effect_sha256",
            "observed_effect_sha256",
        },
    ),
    "OBL-26": (
        "OPR_2B12C8F8D4240FDA61CDA198",
        {
            "grant_not_before",
            "grant_expires_at",
            "invocation_time",
            "revocation_checked_at",
            "revoked_at",
            "consumption_state",
            "invocation_nonce",
            "effect_sha256",
            "execution_receipt_effect_sha256",
            "effect_receipt_count",
        },
    ),
    "OBL-28": (
        "OPR_B7ED0CA795AED58CC3A107DB",
        {
            "trusted_render_bytes_sha256",
            "action_manifest_bytes_sha256",
            "executed_effect_bytes_sha256",
            "render_manifest_sha256",
            "render_effect_sha256",
        },
    ),
}

# Concrete anchors for every obligation in HOST_OBLIGATIONS.md.
HOST_OBLIGATION_MAP = {
    "H1": "atomic observer recheck in preflight_profile and build_engine_request",
    "H2": "SQLiteNonceStore.consume_once BEGIN IMMEDIATE transaction",
    "H3": "field-by-field derivation and deterministic re-derivation comparison",
    "H4": "per-family native preconditions and explicit REFUSED outcomes",
    "H5": "build_transcript_entry + validate_transcript_entry with exact re-execution",
    "H6": "reconcile_effect_log exact ID/cardinality/digest/receipt checks",
}

@dataclasses.dataclass(frozen=True, slots=True)
class AdapterOutcome:
    status: str
    obligation_id: str
    profile: dict[str, Any] | None
    issues: tuple[ProfileIssue, ...]

    @property
    def ready(self) -> bool:
        return self.status == "PROFILE_READY" and self.profile is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "obligation_id": self.obligation_id,
            "profile": self.profile,
            "issues": [problem.as_dict() for problem in self.issues],
        }


class ProfilePreflightError(ValueError):
    """Raised when preflight cannot mint a validated-profile capability."""

    def __init__(self, issues: Sequence[ProfileIssue]):
        self.issues = tuple(issues)
        super().__init__("; ".join(map(str, self.issues)))


@dataclasses.dataclass(frozen=True, slots=True, init=False, eq=False, weakref_slot=True)
class ValidatedProfile:
    """Opaque capability minted only after successful, fresh preflight."""

    _profile_raw: bytes
    _profile_sha256: str
    _obligation_id: str
    _record_id: str
    _record_digest: str
    _state_revision: str | None
    _observer: Callable[[], Mapping[str, Any]]

    @property
    def _profile(self) -> dict[str, Any]:
        """Return a detached copy; mutating it cannot alter sealed bytes."""

        return json.loads(self._profile_raw)

    @property
    def obligation_id(self) -> str:
        return self._obligation_id

    @property
    def record_id(self) -> str:
        return self._record_id


@dataclasses.dataclass(frozen=True, slots=True)
class _CapabilitySeal:
    profile_raw: bytes
    profile_sha256: str
    obligation_id: str
    record_id: str
    record_digest: str
    state_revision: str | None
    observer: Callable[[], Mapping[str, Any]]


_VALIDATED_CAPABILITIES: weakref.WeakKeyDictionary[
    ValidatedProfile, _CapabilitySeal
] = weakref.WeakKeyDictionary()


def _mint_validated_profile(
    *,
    profile: dict[str, Any],
    record_digest: str,
    state_revision: str | None,
    observer: Callable[[], Mapping[str, Any]],
) -> ValidatedProfile:
    profile_raw = canonical_json_bytes(profile)
    capability = object.__new__(ValidatedProfile)
    object.__setattr__(capability, "_profile_raw", profile_raw)
    object.__setattr__(capability, "_profile_sha256", sha256_upper(profile_raw))
    object.__setattr__(capability, "_obligation_id", profile["obligation_id"])
    object.__setattr__(capability, "_record_id", profile["record_id"])
    object.__setattr__(capability, "_record_digest", record_digest)
    object.__setattr__(capability, "_state_revision", state_revision)
    object.__setattr__(capability, "_observer", observer)
    _VALIDATED_CAPABILITIES[capability] = _CapabilitySeal(
        profile_raw=profile_raw,
        profile_sha256=sha256_upper(profile_raw),
        obligation_id=profile["obligation_id"],
        record_id=profile["record_id"],
        record_digest=record_digest,
        state_revision=state_revision,
        observer=observer,
    )
    return capability


def _problem(obligation: str, pointer: str, message: str, fix: str, code: str = "H1"):
    return issue(code, obligation, pointer, message, fix)


def _require_dict(record: Any) -> tuple[dict[str, Any] | None, tuple[ProfileIssue, ...]]:
    obligation = FAMILY_OBLIGATION.get(record.get("family"), "UNMAPPED") if isinstance(record, dict) else "UNMAPPED"
    if not isinstance(record, dict):
        return None, (
            _problem(obligation, "/", "native record is not an object", "supply one JSON object per native record"),
        )
    if set(record) - {"record_id", "family", "native", "observations", "state_revision"}:
        return None, (
            _problem(
                obligation,
                "/",
                f"unknown record fields {sorted(set(record)-{'record_id','family','native','observations','state_revision'})}",
                "move raw data under native/observations or remove caller conclusions",
                "H3",
            ),
        )
    if not isinstance(record.get("record_id"), str) or not (0 < len(record["record_id"]) <= 160):
        return None, (_problem(obligation, "/record_id", "record id is missing or invalid", "supply a stable nonempty id <=160 characters"),)
    if record.get("family") not in FAMILY_OBLIGATION:
        return None, (
            _problem(
                obligation,
                "/family",
                f"no calibrated mapping for family {record.get('family')!r}",
                "register a native precondition and derivation before engine invocation",
                "H4",
            ),
        )
    if not isinstance(record.get("native"), dict) or not isinstance(record.get("observations"), dict):
        return None, (
            _problem(obligation, "/", "native and observations must be objects", "collect both raw native claims and world observations"),
        )
    revision = record.get("state_revision")
    if revision is not None and (not isinstance(revision, str) or not (0 < len(revision) <= 160)):
        return None, (_problem(obligation, "/state_revision", "state revision is invalid", "use a stable store revision string or omit it"),)
    try:
        canonical_json_bytes(record)
    except (TypeError, ValueError) as exc:
        return None, (_problem(obligation, "/", f"record is outside the finite JSON domain: {exc}", "bound collections/strings and use integer timestamps"),)
    return record, ()


def _hash64(value: Any) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def _scope_hash(items: Sequence[str]) -> str:
    """Injective digest of a path set (F-WP1-013).

    Matches ``portable_preflight._scope_hash`` exactly: SHA-256 of the
    canonical JSON array of the sorted items.  The historical newline join
    survives only in the committed ``proof/arm_b1.py`` experiment arm, whose
    receipts are sealed history.
    """

    return sha256_upper(canonical_json_bytes(sorted(items)))


def _in_scope(path: str, claimed: Sequence[str]) -> bool:
    for pattern in claimed:
        if path == pattern or fnmatch.fnmatch(path, pattern):
            return True
        if pattern.endswith("/**") and path.startswith(pattern[:-2]):
            return True
    return False


def _derive_ref(record: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, str], dict[str, Any], tuple[ProfileIssue, ...]]:
    obligation = "OBL-02"
    native, obs = record["native"], record["observations"]
    claimed_path = native.get("claimed_path")
    referenced_record = native.get("referenced_record")
    if claimed_path is not None and referenced_record is not None and claimed_path != referenced_record:
        return None, {}, {}, (
            _problem(
                obligation,
                "/native",
                "claimed_path and referenced_record identify different targets",
                "resolve the alias conflict from one atomic reference observation",
            ),
        )
    reference = claimed_path or referenced_record
    found, observed = obs.get("referenced_record_found"), obs.get("observed_sha256")
    archived = obs.get("found_at_archived_location") is True
    if not isinstance(reference, str) or not (0 < len(reference) <= 160):
        return None, {}, {}, (_problem(obligation, "/native/referenced_record", "reference identity is missing", "record claimed_path or referenced_record"),)
    if not isinstance(found, bool):
        return None, {}, {}, (_problem(obligation, "/observations/referenced_record_found", "presence was not observed", "record an explicit true/false lookup result"),)
    claimed = native.get("claimed_sha256")
    if claimed is not None and not _hash64(claimed):
        return None, {}, {}, (_problem(obligation, "/native/claimed_sha256", "claimed pin is malformed", "record null or a 64-character uppercase SHA-256"),)
    if found and not _hash64(observed):
        return None, {}, {}, (_problem(obligation, "/observations/observed_sha256", "found record lacks content testimony", "hash the bytes read in the same lookup snapshot"),)
    if not found and observed is not None and not archived:
        return None, {}, {}, (_problem(obligation, "/observations", "absence contradicts an observed digest", "repeat one lookup and report either found+digest or absent+null"),)
    if archived and found:
        return None, {}, {}, (_problem(obligation, "/observations", "current and archived location flags conflict", "report archived recovery only when the claimed location is absent"),)
    versions: list[dict[str, str]] = []
    if found:
        versions.append({"record_id": reference, "revision_sha256": observed})
        if claimed is not None:
            versions.append({"record_id": reference, "revision_sha256": claimed})
    facts = {"exact_reference": reference, "record_versions": versions}
    derivations = {
        "exact_reference": "native.claimed_path else native.referenced_record",
        "record_versions": "observed bytes testimony plus independent claimed pin when current location exists",
    }
    calibration = {
        "applicable": True,
        "native_precondition": "record asserts an exact reference and host performed one location lookup",
        "evidence_pointers": ["/native/claimed_path", "/native/referenced_record", "/observations/referenced_record_found"],
    }
    return facts, derivations, calibration, ()


def _derive_scope(record: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, str], dict[str, Any], tuple[ProfileIssue, ...]]:
    obligation = "OBL-03"
    native, obs = record["native"], record["observations"]
    claimed = native.get("claimed_paths")
    named, found, changed = native.get("result_commit_named"), obs.get("commit_found"), obs.get("commit_changed_paths")
    if not isinstance(claimed, list) or len(claimed) > 256 or not all(isinstance(p, str) and 0 < len(p) <= 160 for p in claimed):
        return None, {}, {}, (_problem(obligation, "/native/claimed_paths", "claimed paths are partially observed or malformed", "record a bounded list of nonempty path/glob strings"),)
    if not isinstance(named, bool) or not isinstance(found, bool):
        return None, {}, {}, (_problem(obligation, "/observations/commit_found", "commit lookup state is incomplete", "record result_commit_named and commit_found as booleans"),)
    if found and (not isinstance(changed, list) or len(changed) > 256 or not all(isinstance(p, str) and 0 < len(p) <= 160 for p in changed)):
        return None, {}, {}, (_problem(obligation, "/observations/commit_changed_paths", "found commit has no complete changed-path observation", "read the bounded changed-path set from the same commit snapshot"),)
    if not found and changed is not None:
        return None, {}, {}, (_problem(obligation, "/observations", "missing commit contradicts a changed-path set", "repeat commit resolution and retain one coherent result"),)
    declared = _scope_hash(claimed) if claimed else None
    if named and not found:
        recorded = None
    elif changed is None:
        recorded = declared
    else:
        outside = [path for path in changed if not _in_scope(path, claimed)]
        recorded = declared if not outside else _scope_hash(sorted(claimed + outside))
    kinds = (["ADOPTION"] if claimed else []) + (["INTENDED_USE"] if native.get("status") is not None else [])
    facts = {
        # These are ordinals of the adapter's two-snapshot protocol, not
        # fabricated wall-clock times: claim snapshot 0 precedes use snapshot 1.
        "declaration_effective_at": 0,
        "interval_end_exclusive": 1,
        "declaration_kinds": kinds,
        "declared_scope_sha256": declared,
        "recorded_use_scope_sha256": recorded,
    }
    derivations = {
        "declaration_effective_at": "ordinal 0 of the claim-then-use snapshot protocol",
        "interval_end_exclusive": "ordinal 1 of the claim-then-use snapshot protocol",
        "declaration_kinds": "ADOPTION from claimed_paths; INTENDED_USE from native status",
        "declared_scope_sha256": "SHA-256 of the canonical JSON array of sorted native claimed_paths",
        "recorded_use_scope_sha256": "same digest if all observed paths are in scope; expanded digest on outside use; null on missing named commit",
    }
    calibration = {
        "applicable": True,
        "native_precondition": "claim snapshot precedes a coherent result-commit lookup snapshot",
        "evidence_pointers": ["/native/claimed_paths", "/native/result_commit_named", "/observations/commit_found", "/observations/commit_changed_paths"],
    }
    return facts, derivations, calibration, ()


def _derive_supersede(record: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, str], dict[str, Any], tuple[ProfileIssue, ...]]:
    obligation = "OBL-15"
    native, obs = record["native"], record["observations"]
    corrected_hash, ordinal = obs.get("corrected_version_sha256"), native.get("correction_ordinal")
    corrected_epoch, epochs = obs.get("corrected_first_added_epoch"), obs.get("doc_first_added_epochs")
    invalidated, any_later = obs.get("later_docs_citing_invalidated"), obs.get("later_docs_citing_any_later_member")
    if not _hash64(corrected_hash):
        return None, {}, {}, (_problem(obligation, "/observations/corrected_version_sha256", "corrected version bytes were not observed", "hash the corrected version in the same chain snapshot"),)
    if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 0:
        return None, {}, {}, (_problem(obligation, "/native/correction_ordinal", "correction ordinal is invalid", "derive a nonnegative version-chain ordinal"),)
    if not isinstance(corrected_epoch, int) or isinstance(corrected_epoch, bool) or corrected_epoch < 0:
        return None, {}, {}, (_problem(obligation, "/observations/corrected_first_added_epoch", "correction time is absent", "observe the corrected member's first-added epoch"),)
    if not isinstance(epochs, dict) or not all(isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) and v >= 0 for k, v in epochs.items()):
        return None, {}, {}, (_problem(obligation, "/observations/doc_first_added_epochs", "citer chronology is partial or malformed", "record first-added epochs for every cited document"),)
    for pointer, value in (("later_docs_citing_invalidated", invalidated), ("later_docs_citing_any_later_member", any_later)):
        if not isinstance(value, list) or len(value) > 256 or not all(isinstance(name, str) and 0 < len(name) <= 160 for name in value):
            return None, {}, {}, (_problem(obligation, f"/observations/{pointer}", "citation join is partial or malformed", "record the bounded raw citation identities before deriving blame"),)
    missing_epochs = sorted((set(invalidated) | set(any_later)) - set(epochs))
    if missing_epochs:
        return None, {}, {}, (_problem(obligation, "/observations/doc_first_added_epochs", f"citers lack chronology: {missing_epochs[:5]}", "observe every cited document's first-added epoch"),)
    any_later_set = set(any_later)
    blamed = []
    for name in invalidated:
        if name in any_later_set:
            continue
        if epochs[name] < corrected_epoch:
            continue
        blamed.append(name)
    reliance_surface = sorted(any_later_set | set(invalidated))
    facts = {
        "corrected_version_sha256": corrected_hash,
        "correction_target_ordinal": ordinal,
        "invalidated_path_ids": sorted(blamed),
        "independent_valid_path_ids": reliance_surface,
    }
    derivations = {
        "corrected_version_sha256": "SHA-256 testimony for observed corrected version bytes",
        "correction_target_ordinal": "native version-chain correction ordinal",
        "invalidated_path_ids": "post-correction invalidated-only citers after subtracting later-member citers",
        "independent_valid_path_ids": "union of raw invalidated-member and later-member citation surfaces",
    }
    calibration = {
        "applicable": True,
        "native_precondition": "corrected chain member, citer identities, and citer chronology are all observed",
        "evidence_pointers": ["/native/correction_ordinal", "/observations/corrected_version_sha256", "/observations/later_docs_citing_invalidated", "/observations/later_docs_citing_any_later_member", "/observations/doc_first_added_epochs"],
    }
    return facts, derivations, calibration, ()


def _derive_lifecycle(record: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, str], dict[str, Any], tuple[ProfileIssue, ...]]:
    obligation = "OBL-17"
    events = record["observations"].get("lifecycle_events")
    if not isinstance(events, list) or len(events) > 256:
        return None, {}, {}, (
            _problem(
                obligation,
                "/observations/lifecycle_events",
                "OBL-17 requires typed lifecycle events; timestamps alone do not establish acknowledgment",
                "record explicit event_type, occurred_at, and sequence evidence or REFUSE",
                "H4",
            ),
        )
    expected_fields = {"event_type", "occurred_at", "sequence"}
    if not events or any(
        not isinstance(event, dict)
        or set(event) != expected_fields
        or event["event_type"] not in {"EFFECTIVE", "ACKNOWLEDGMENT", "OTHER"}
        or not isinstance(event["occurred_at"], int)
        or isinstance(event["occurred_at"], bool)
        or event["occurred_at"] < 0
        or not isinstance(event["sequence"], int)
        or isinstance(event["sequence"], bool)
        or event["sequence"] < 0
        for event in events
    ):
        return None, {}, {}, (
            _problem(
                obligation,
                "/observations/lifecycle_events",
                "typed lifecycle evidence is partial, ambiguous, or malformed",
                "record closed {event_type,occurred_at,sequence} rows using the declared event types",
                "H4",
            ),
        )
    acknowledgments = [event for event in events if event["event_type"] == "ACKNOWLEDGMENT"]
    effective_events = [event for event in events if event["event_type"] == "EFFECTIVE"]
    if len(acknowledgments) != 1 or len(effective_events) != 1:
        return None, {}, {}, (
            _problem(
                obligation,
                "/observations/lifecycle_events",
                "OBL-17 needs exactly one explicit EFFECTIVE and one explicit ACKNOWLEDGMENT event",
                "disambiguate event types or record REFUSED/INAPPLICABLE",
                "H4",
            ),
        )
    ordered = sorted(events, key=lambda event: event["sequence"])
    if len({event["sequence"] for event in ordered}) != len(ordered):
        return None, {}, {}, (
            _problem(
                obligation,
                "/observations/lifecycle_events",
                "event sequence identifiers are duplicated",
                "record unique sequence identifiers from the native event log",
                "H1",
            ),
        )
    if any(
        left["occurred_at"] >= right["occurred_at"]
        for left, right in zip(ordered, ordered[1:])
    ):
        return None, {}, {}, (
            _problem(
                obligation,
                "/observations/lifecycle_events",
                "lifecycle timestamps contradict strict native sequence order",
                "repair non-increasing event times or record REFUSED",
                "H4",
            ),
        )
    acknowledgment = acknowledgments[0]
    effective = effective_events[0]
    sequences = [event["sequence"] for event in ordered]
    ack_index = ordered.index(acknowledgment)
    effective_index = ordered.index(effective)
    if ack_index != len(ordered) - 1:
        return None, {}, {}, (
            _problem(
                obligation,
                "/observations/lifecycle_events",
                "the explicit ACKNOWLEDGMENT is not the terminal lifecycle event",
                "observe a terminal ACKNOWLEDGMENT or record REFUSED/INAPPLICABLE",
                "H4",
            ),
        )
    if (
        effective_index >= ack_index
        or effective["sequence"] >= acknowledgment["sequence"]
        or effective["occurred_at"] >= acknowledgment["occurred_at"]
    ):
        return None, {}, {}, (
            _problem(
                obligation,
                "/observations/lifecycle_events",
                "ACKNOWLEDGMENT is not strictly after EFFECTIVE in sequence and time",
                "repair contradictory native ordering/timestamps or record REFUSED",
                "H4",
            ),
        )
    terminal_predecessor = ordered[-2]["sequence"]
    facts = {
        "event_sequences": sequences,
        "nonroot_predecessor_sequences": sequences[:ack_index],
        "acknowledged_at": acknowledgment["occurred_at"],
        "effective_at": effective["occurred_at"],
        "terminal_predecessor_sequences": [terminal_predecessor],
    }
    derivations = {
        "event_sequences": "typed lifecycle events sorted by native sequence",
        "nonroot_predecessor_sequences": "sequences preceding the explicit ACKNOWLEDGMENT event",
        "acknowledged_at": "occurred_at of the explicit ACKNOWLEDGMENT event",
        "effective_at": "occurred_at of the explicit EFFECTIVE event",
        "terminal_predecessor_sequences": "observed immediate sequence predecessor of the terminal explicit ACKNOWLEDGMENT",
    }
    calibration = {
        "applicable": True,
        "native_precondition": "exactly one typed EFFECTIVE followed in sequence and time by a terminal typed ACKNOWLEDGMENT, with unique native sequences",
        "evidence_pointers": ["/observations/lifecycle_events"],
    }
    return facts, derivations, calibration, ()


DERIVERS = {
    "REF": _derive_ref,
    "SCOPE": _derive_scope,
    "SUPERSEDE": _derive_supersede,
    "LIFECYCLE": _derive_lifecycle,
}


def adapt_record(record: Mapping[str, Any], *, expected_state_revision: str | None = None) -> AdapterOutcome:
    """Derive a fact-profile envelope or explicitly refuse the mapping."""

    checked, problems = _require_dict(record)
    obligation = FAMILY_OBLIGATION.get(record.get("family"), "UNMAPPED") if isinstance(record, dict) else "UNMAPPED"
    if checked is None:
        return AdapterOutcome("REFUSED", obligation, None, problems)
    if expected_state_revision is not None and checked.get("state_revision") != expected_state_revision:
        return AdapterOutcome(
            "REFUSED",
            obligation,
            None,
            (_problem(obligation, "/state_revision", f"record revision {checked.get('state_revision')!r} is not required revision {expected_state_revision!r}", "retry the atomic state read at the required revision"),),
        )
    facts, derivations, calibration, problems = DERIVERS[checked["family"]](checked)
    if problems:
        return AdapterOutcome("REFUSED", obligation, None, problems)
    assert facts is not None
    profile = {
        "format_version": FORMAT_VERSION,
        "obligation_id": obligation,
        "record_id": checked["record_id"],
        "observation_raw_sha256": record_sha256(checked),
        "state_revision": checked.get("state_revision"),
        "facts": facts,
        "derivations": derivations,
        "fabricated_fields": [],
        "calibration": calibration,
    }
    problems = validate_profile_envelope(
        profile,
        checked,
        expected_obligation=obligation,
        expected_facts=facts,
        expected_state_revision=expected_state_revision,
    )
    if problems:
        return AdapterOutcome("REFUSED", obligation, None, problems)
    return AdapterOutcome("PROFILE_READY", obligation, profile, ())


def preflight_profile(
    record: Mapping[str, Any],
    profile: Mapping[str, Any],
    *,
    observer: Callable[[], Mapping[str, Any]] | None = None,
) -> ValidatedProfile:
    """Re-derive and mint a capability only from a freshly verified record.

    The caller must provide an atomic observer callback, called now and again
    immediately before request construction. A plain profile can never reach
    the builder.
    """

    obligation = FAMILY_OBLIGATION.get(record.get("family"), "UNMAPPED") if isinstance(record, Mapping) else "UNMAPPED"
    if observer is None:
        raise ProfilePreflightError(
            (
                _problem(
                    obligation,
                    "/state_revision",
                    "freshness is unverified",
                    "provide an atomic observer/revision callback used again at build time",
                    "H1",
                ),
            )
        )
    current: Mapping[str, Any] = record
    if observer is not None:
        try:
            observed = observer()
        except Exception as exc:
            raise ProfilePreflightError(
                (
                    _problem(
                        obligation,
                        "/",
                        f"atomic observer failed: {type(exc).__name__}",
                        "retry one atomic observation before preflight",
                        "H1",
                    ),
                )
            ) from exc
        if not isinstance(observed, Mapping):
            raise ProfilePreflightError(
                (
                    _problem(
                        obligation,
                        "/",
                        "atomic observer did not return a record mapping",
                        "return the complete native record and revision from one observation",
                        "H1",
                    ),
                )
            )
        current = observed
        if record_sha256(current) != record_sha256(record):
            raise ProfilePreflightError(
                (
                    _problem(
                        obligation,
                        "/observation_raw_sha256",
                        "record changed before preflight completed",
                        "discard the profile and derive again from the fresh atomic observation",
                        "H1",
                    ),
                )
            )
    expected = adapt_record(current)
    if not expected.ready:
        raise ProfilePreflightError(expected.issues)
    assert expected.profile is not None
    problems = list(validate_profile_envelope(
        profile,
        current,
        expected_obligation=expected.obligation_id,
        expected_facts=expected.profile["facts"],
        expected_state_revision=None,
    ))
    if isinstance(profile, Mapping) and profile.get("derivations") != expected.profile[
        "derivations"
    ]:
        problems.append(
            _problem(
                expected.obligation_id,
                "/derivations",
                "submitted derivation ledger differs from deterministic re-derivation",
                "retain the adapter-produced field derivations unchanged",
                "H3",
            )
        )
    if isinstance(profile, Mapping) and profile.get("calibration") != expected.profile[
        "calibration"
    ]:
        problems.append(
            _problem(
                expected.obligation_id,
                "/calibration",
                "submitted applicability evidence differs from current calibration",
                "discard the profile and rerun the current applicability rule",
                "H4",
            )
        )
    if problems:
        raise ProfilePreflightError(problems)
    return _mint_validated_profile(
        profile=copy.deepcopy(expected.profile),
        record_digest=record_sha256(current),
        state_revision=current.get("state_revision"),
        observer=observer,
    )


_TEMPLATE_CACHE: dict[pathlib.Path, dict[str, dict[str, Any]]] = {}


def _load_templates(repo_root: pathlib.Path) -> dict[str, dict[str, Any]]:
    root = repo_root.resolve()
    if root in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[root]
    pack_path = root / "baseline-run" / "fixtures" / "PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json"
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    templates: dict[str, dict[str, Any]] = {}
    for entry in pack["entries"]:
        for obligation in FACT_FIELDS:
            if f"{obligation}-IO" in entry["entry_id"]:
                templates[obligation] = json.loads(base64.b64decode(entry["semantic_request_jcs_lf_base64"]))
    if set(templates) != set(FACT_FIELDS):
        raise RuntimeError(f"H5: request templates missing {sorted(set(FACT_FIELDS)-set(templates))}")
    _TEMPLATE_CACHE[root] = templates
    return templates


def build_engine_request(profile: ValidatedProfile, repo_root: os.PathLike[str] | str) -> tuple[dict[str, Any], bytes]:
    """Build request bytes from an opaque, freshly rechecked capability."""

    if not isinstance(profile, ValidatedProfile):
        raise TypeError("H1/H3: build_engine_request requires a ValidatedProfile capability")
    try:
        seal = _VALIDATED_CAPABILITIES[profile]
    except (KeyError, TypeError):
        raise TypeError(
            "H1/H3: build_engine_request requires a ValidatedProfile capability"
        ) from None
    if (
        profile._profile_raw != seal.profile_raw
        or profile._profile_sha256 != seal.profile_sha256
        or profile._obligation_id != seal.obligation_id
        or profile._record_id != seal.record_id
        or profile._record_digest != seal.record_digest
        or profile._state_revision != seal.state_revision
        or profile._observer is not seal.observer
    ):
        raise ProfilePreflightError(
            (
                _problem(
                    seal.obligation_id,
                    "/profile",
                    "validated capability state changed after preflight",
                    "discard the capability and rerun preflight",
                    "H3",
                ),
            )
        )
    try:
        current = seal.observer()
    except Exception as exc:
        raise ProfilePreflightError(
            (
                _problem(
                    seal.obligation_id,
                    "/",
                    f"atomic observer failed at build: {type(exc).__name__}",
                    "abort request construction and retry observation/preflight",
                    "H1",
                ),
            )
        ) from exc
    try:
        current_raw = canonical_json_bytes(current)
        current_snapshot = json.loads(current_raw)
        current_digest = sha256_upper(current_raw)
    except Exception as exc:
        raise ProfilePreflightError(
            (
                _problem(
                    seal.obligation_id,
                    "/",
                    f"atomic observer returned an invalid record: {type(exc).__name__}",
                    "abort request construction and retry a bounded atomic observation",
                    "H1",
                ),
            )
        ) from exc
    if not isinstance(current_snapshot, dict) or current_digest != seal.record_digest:
        raise ProfilePreflightError(
            (
                _problem(
                    seal.obligation_id,
                    "/observation_raw_sha256",
                    "record changed after preflight and before request construction",
                    "discard the capability and derive/preflight the new atomic snapshot",
                    "H1",
                ),
            )
        )
    if current_snapshot.get("state_revision") != seal.state_revision:
        raise ProfilePreflightError(
            (
                _problem(
                    seal.obligation_id,
                    "/state_revision",
                    "state revision changed after preflight",
                    "discard the capability and retry at the current revision",
                    "H1",
                ),
            )
        )
    if sha256_upper(seal.profile_raw) != seal.profile_sha256:
        raise ProfilePreflightError(
            (
                _problem(
                    seal.obligation_id,
                    "/profile",
                    "validated profile seal changed after preflight",
                    "discard the capability and rerun preflight",
                    "H3",
                ),
            )
        )
    try:
        raw_profile = json.loads(seal.profile_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProfilePreflightError(
            (_problem(seal.obligation_id, "/profile", "sealed profile bytes are invalid", "discard the capability", "H3"),)
        ) from exc
    current_outcome = adapt_record(current_snapshot)
    if not current_outcome.ready:
        raise ProfilePreflightError(current_outcome.issues)
    assert current_outcome.profile is not None
    if canonical_json_bytes(current_outcome.profile) != seal.profile_raw:
        raise ProfilePreflightError(
            (
                _problem(
                    seal.obligation_id,
                    "/profile",
                    "sealed profile differs from build-time deterministic re-derivation",
                    "discard the capability and rerun preflight on the atomic snapshot",
                    "H3",
                ),
            )
        )
    obligation = raw_profile["obligation_id"]
    request = copy.deepcopy(_load_templates(pathlib.Path(repo_root))[obligation])
    request_id = "RUN_" + hashlib.sha256(raw_profile["record_id"].encode("utf-8")).hexdigest()[:24].upper()
    request["request_id"] = request_id
    request["inner_request"]["request_id"] = request_id
    request["decision_input"]["facts"] = copy.deepcopy(raw_profile["facts"])
    request["inner_request_raw_sha256"] = sha256_upper(canonical_json_bytes(request["inner_request"]) + b"\n")
    request["inner_input_sha256"] = sha256_upper(canonical_json_bytes(request["inner_request"]["input"]))
    raw = canonical_json_bytes(request) + b"\n"
    return request, raw


def _execute_core_request(
    request_raw: bytes, repo_root: os.PathLike[str] | str
) -> tuple[dict[str, Any], int, bytes]:
    runner_path = (
        pathlib.Path(repo_root)
        / "baseline-run"
        / "implementation-output-0.3"
        / "pcb_runner.py"
    ).resolve()
    completed = subprocess.run(
        [sys.executable, "-I", "-B", str(runner_path), "execute"],
        input=request_raw,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    if completed.stderr:
        raise RuntimeError("accepted core wrote unexpected stderr")
    response = _strict_transcript_json(completed.stdout)
    if (
        not isinstance(response, dict)
        or completed.stdout != canonical_json_bytes(response) + b"\n"
    ):
        raise RuntimeError("accepted core returned noncanonical response bytes")
    return response, completed.returncode, completed.stdout


def _strict_transcript_json(raw: bytes) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant {value} is forbidden")

    return json.loads(raw.decode("utf-8"), parse_constant=reject_constant)


def build_transcript_entry(
    request_raw: bytes,
    response_raw: bytes,
    engine_exit_code: int,
    repo_root: os.PathLike[str] | str,
) -> dict[str, Any]:
    """H5: build a transcript that passes exact core-engine re-execution."""

    if not isinstance(request_raw, bytes) or not isinstance(response_raw, bytes):
        raise TypeError("H5: request_raw and response_raw must be bytes")
    try:
        request = _strict_transcript_json(request_raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ValueError("H5: request bytes are not strict JSON") from exc
    decision_input = request.get("decision_input") if isinstance(request, dict) else None
    if not isinstance(decision_input, dict):
        raise ValueError("H5: request bytes do not contain a decision_input object")
    entry = {
        "format_version": "RR-HOST-CORE-TRANSCRIPT-2",
        "request_id": request.get("request_id"),
        "request_raw_base64": base64.b64encode(request_raw).decode("ascii"),
        "request_raw_sha256": sha256_upper(request_raw),
        "decision_input": decision_input,
        "decision_input_sha256": sha256_upper(canonical_json_bytes(decision_input)),
        "response_raw_base64": base64.b64encode(response_raw).decode("ascii"),
        "response_raw_sha256": sha256_upper(response_raw),
        "engine_exit_code": engine_exit_code,
    }
    problems = validate_transcript_entry(entry, repo_root)
    if problems:
        raise ProfilePreflightError(problems)
    return entry


def validate_transcript_entry(
    entry: Mapping[str, Any], repo_root: os.PathLike[str] | str
) -> tuple[ProfileIssue, ...]:
    """Validate exact bytes, schemas, IDs, seals, bindings, and semantics.

    Semantic derivation is checked by re-executing the accepted frozen core on
    the exact retained request bytes and requiring byte-exact response and
    exit-code equality.
    """

    obligation = "H5-TRANSCRIPT"
    problems: list[ProfileIssue] = []
    required = {
        "format_version",
        "request_id",
        "request_raw_base64",
        "request_raw_sha256",
        "decision_input",
        "decision_input_sha256",
        "response_raw_base64",
        "response_raw_sha256",
        "engine_exit_code",
    }
    if not isinstance(entry, dict) or set(entry) != required:
        return (
            _problem(
                obligation,
                "/",
                "transcript has the wrong closed shape",
                "retain the exact output of build_transcript_entry",
                "H5",
            ),
        )
    if entry["format_version"] != "RR-HOST-CORE-TRANSCRIPT-2":
        problems.append(
            _problem(
                obligation,
                "/format_version",
                "transcript format literal is not RR-HOST-CORE-TRANSCRIPT-2",
                "regenerate the transcript with the current host adapter",
                "H5",
            )
        )
    decoded: dict[str, bytes] = {}
    parsed: dict[str, Any] = {}
    for prefix in ("request", "response"):
        encoded = entry[f"{prefix}_raw_base64"]
        if not isinstance(encoded, str) or len(encoded) > 6 * 1024 * 1024:
            problems.append(
                _problem(
                    obligation,
                    f"/{prefix}_raw_base64",
                    "transcript base64 is absent or exceeds the finite input boundary",
                    "retain bounded exact engine wire bytes",
                    "H5",
                )
            )
            continue
        try:
            raw = base64.b64decode(encoded, validate=True)
        except Exception:
            problems.append(
                _problem(
                    obligation,
                    f"/{prefix}_raw_base64",
                    "transcript bytes are not strict base64",
                    "restore the original transcript bytes",
                    "H5",
                )
            )
            continue
        decoded[prefix] = raw
        if sha256_upper(raw) != entry[f"{prefix}_raw_sha256"]:
            problems.append(
                _problem(
                    obligation,
                    f"/{prefix}_raw_sha256",
                    "transcript byte digest does not match",
                    "reject the transcript and recover the original bytes",
                    "H5",
                )
            )
        try:
            value = _strict_transcript_json(raw)
        except Exception:
            problems.append(
                _problem(
                    obligation,
                    f"/{prefix}_raw_base64",
                    "retained wire bytes are not UTF-8 JSON",
                    "restore one canonical JSON object followed by LF",
                    "H5",
                )
            )
            continue
        try:
            canonical = canonical_json_bytes(value) + b"\n"
        except Exception:
            canonical = None
        if not isinstance(value, dict) or raw != canonical:
            problems.append(
                _problem(
                    obligation,
                    f"/{prefix}_raw_base64",
                    "retained wire bytes are not the canonical object plus LF",
                    "retain exact canonical engine wire bytes",
                    "H5",
                )
            )
            continue
        parsed[prefix] = value
    request = parsed.get("request")
    response = parsed.get("response")
    if request is not None and request.get("format_version") != "B1-SEMANTIC-DECISION-REQUEST-0.2":
        problems.append(
            _problem(obligation, "/request_raw_base64", "unexpected core request format literal", "use the accepted core request format", "H5")
        )
    if response is not None and response.get("format_version") != "PCB-RUNNER-RESPONSE-0.2":
        problems.append(
            _problem(obligation, "/response_raw_base64", "unexpected core response format literal", "retain the accepted runner response format", "H5")
        )
    if request is not None and response is not None:
        if not (
            entry["request_id"]
            == request.get("request_id")
            == response.get("request_id")
        ):
            problems.append(
                _problem(obligation, "/request_id", "request/response/transcript IDs do not correlate", "reject the mixed transcript", "H5")
            )
        embedded = request.get("decision_input")
        try:
            embedded_digest = sha256_upper(canonical_json_bytes(embedded))
            retained_digest = sha256_upper(canonical_json_bytes(entry["decision_input"]))
        except Exception:
            embedded_digest = retained_digest = ""
        if not (
            embedded == entry["decision_input"]
            and retained_digest == entry["decision_input_sha256"]
            and embedded_digest == retained_digest
        ):
            problems.append(
                _problem(obligation, "/decision_input", "decision-input binding is invalid", "restore the input embedded in the retained request", "H5")
            )
    if request is not None:
        try:
            expected_response, expected_exit, expected_raw = _execute_core_request(
                decoded["request"], repo_root
            )
        except Exception as exc:
            problems.append(
                _problem(
                    obligation,
                    "/response_raw_base64",
                    f"core re-execution failed deterministically: {type(exc).__name__}",
                    "reject the transcript and investigate the retained request/engine boundary",
                    "H5",
                )
            )
        else:
            if (
                "response" not in decoded
                or decoded["response"] != expected_raw
                or entry["engine_exit_code"] != expected_exit
                or parsed.get("response") != expected_response
            ):
                problems.append(
                    _problem(
                        obligation,
                        "/response_raw_base64",
                        "response, exit code, schema/seal, or semantic derivation differs from exact core re-execution",
                        "reject the transcript and retain the core response produced for these request bytes",
                        "H5",
                    )
                )
    return tuple(problems)


@dataclasses.dataclass(frozen=True, slots=True)
class NonceClaim:
    admitted_to_engine: bool
    consumption_state: str
    prior_invocation_nonces: tuple[str, ...]
    state_revision: str


class SQLiteNonceStore:
    """H2 reference check-and-consume store; one transaction per claim."""

    def __init__(self, path: os.PathLike[str] | str):
        self.path = pathlib.Path(path)
        connection = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS consumed_nonce (nonce TEXT PRIMARY KEY, ordinal INTEGER NOT NULL UNIQUE)")
            connection.execute("CREATE TABLE IF NOT EXISTS revision (singleton INTEGER PRIMARY KEY CHECK(singleton=1), value INTEGER NOT NULL)")
            connection.execute("INSERT OR IGNORE INTO revision(singleton,value) VALUES(1,0)")
        finally:
            connection.close()

    def consume_once(self, nonce: str) -> NonceClaim:
        if not isinstance(nonce, str) or NONCE_RE.fullmatch(nonce) is None:
            raise ValueError("H2: nonce must match [A-Za-z0-9_.:-]{1,160}")
        connection = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = tuple(row[0] for row in connection.execute("SELECT nonce FROM consumed_nonce ORDER BY ordinal"))
            existing = connection.execute("SELECT ordinal FROM consumed_nonce WHERE nonce=?", (nonce,)).fetchone()
            if existing is None:
                revision = int(connection.execute("SELECT value FROM revision WHERE singleton=1").fetchone()[0]) + 1
                connection.execute("INSERT INTO consumed_nonce(nonce,ordinal) VALUES(?,?)", (nonce, revision))
                connection.execute("UPDATE revision SET value=? WHERE singleton=1", (revision,))
                connection.execute("COMMIT")
                return NonceClaim(True, "UNUSED", prior, str(revision))
            revision = int(connection.execute("SELECT value FROM revision WHERE singleton=1").fetchone()[0])
            connection.execute("COMMIT")
            return NonceClaim(False, "USED", prior, str(revision))
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()


def effect_receipt_sha256(*, operation_handle: str, obligation_id: str, request_id: str, decision_input: Mapping[str, Any], operation_fields_object: Mapping[str, Any]) -> str:
    """H6: recompute the frozen engine's effect-receipt preimage digest."""

    preimage = {
        "domain": EFFECT_DOMAIN,
        "operation_handle": operation_handle,
        "obligation_id": obligation_id,
        "request_id": request_id,
        "decision_input_sha256": sha256_upper(canonical_json_bytes(decision_input)),
        "operation_fields_object": dict(operation_fields_object),
    }
    return sha256_upper(canonical_json_bytes(preimage))


def host_effect_binding_sha256(
    *,
    effect_id: str,
    effect_sha256: str,
    engine_effect_receipt_sha256: str,
    preimage: Mapping[str, Any],
) -> str:
    """Bind the engine receipt and full preimage to one exact host effect ID."""

    if not isinstance(effect_id, str) or not (0 < len(effect_id) <= 160):
        raise ValueError("H6: effect_id must be a nonempty string <=160")
    if not _hash64(effect_sha256) or not _hash64(engine_effect_receipt_sha256):
        raise ValueError("H6: effect and engine receipt digests must be uppercase SHA-256")
    binding = {
        "domain": HOST_EFFECT_BINDING_DOMAIN,
        "effect_id": effect_id,
        "effect_sha256": effect_sha256,
        "engine_effect_receipt_sha256": engine_effect_receipt_sha256,
        "engine_effect_receipt_preimage_sha256": sha256_upper(
            canonical_json_bytes(preimage)
        ),
    }
    return sha256_upper(canonical_json_bytes(binding))


@dataclasses.dataclass(frozen=True, slots=True)
class EffectReconciliation:
    ok: bool
    issues: tuple[ProfileIssue, ...]
    normalized_observed_log: tuple[tuple[str, str], ...]


def reconcile_effect_log(
    *,
    expected_effect_ids: Sequence[str],
    observed_effect_log: Sequence[Mapping[str, Any]],
    expectations: Mapping[str, Mapping[str, Any]],
) -> EffectReconciliation:
    """H6: reconcile the exact expected effect set against a complete log.

    ``expectations`` maps every expected effect ID to closed
    ``{effect_sha256,effect_receipt_sha256,host_effect_binding_sha256,preimage}``
    evidence. Completeness
    is relative to the caller's explicit expected ID set; this helper does not
    claim to discover effects omitted by the host's observation boundary.
    """

    obligation = "H6-EFFECTS"
    problems: list[ProfileIssue] = []
    if (
        not isinstance(expected_effect_ids, Sequence)
        or isinstance(expected_effect_ids, (str, bytes))
        or not all(isinstance(effect_id, str) and 0 < len(effect_id) <= 160 for effect_id in expected_effect_ids)
    ):
        problems.append(
            _problem(obligation, "/expected_effect_ids", "expected effect IDs are malformed", "supply the complete bounded expected ID sequence", "H6")
        )
        return EffectReconciliation(False, tuple(problems), ())
    expected = list(expected_effect_ids)
    if len(set(expected)) != len(expected):
        problems.append(
            _problem(obligation, "/expected_effect_ids", "expected effect IDs contain duplicates", "deduplicate the expected effect set before execution", "H6")
        )
    observed_pairs: list[tuple[str, str]] = []
    if not isinstance(observed_effect_log, Sequence) or isinstance(observed_effect_log, (str, bytes)):
        problems.append(
            _problem(obligation, "/observed_effect_log", "observed effect log is not a sequence", "supply the complete normalized observed log", "H6")
        )
    else:
        for index, row in enumerate(observed_effect_log):
            if not isinstance(row, Mapping) or set(row) != {"effect_id", "effect_sha256"}:
                problems.append(
                    _problem(obligation, f"/observed_effect_log/{index}", "effect log row has the wrong closed shape", "record exactly effect_id and effect_sha256", "H6")
                )
                continue
            effect_id, digest = row["effect_id"], row["effect_sha256"]
            if not isinstance(effect_id, str) or not (0 < len(effect_id) <= 160) or not _hash64(digest):
                problems.append(
                    _problem(obligation, f"/observed_effect_log/{index}", "effect ID or digest is malformed", "record a bounded ID and uppercase SHA-256", "H6")
                )
                continue
            observed_pairs.append((effect_id, digest))
    observed_ids = [effect_id for effect_id, _digest in observed_pairs]
    if len(set(observed_ids)) != len(observed_ids):
        problems.append(
            _problem(obligation, "/observed_effect_log", "observed effect log contains duplicate IDs", "reject duplicate execution receipts and reconcile one row per expected ID", "H6")
        )
    if len(observed_ids) != len(expected) or set(observed_ids) != set(expected):
        problems.append(
            _problem(
                obligation,
                "/observed_effect_log",
                f"observed effect ID/cardinality mismatch (expected={sorted(set(expected))}, observed={sorted(set(observed_ids))})",
                "reconcile only after the complete expected effect set has been observed",
                "H6",
            )
        )
    if not isinstance(expectations, Mapping) or set(expectations) != set(expected):
        problems.append(
            _problem(obligation, "/expectations", "receipt expectations do not cover the exact expected ID set", "supply one closed expectation per expected effect ID", "H6")
        )
    observed_by_id = dict(observed_pairs)
    for effect_id in expected:
        expectation = expectations.get(effect_id) if isinstance(expectations, Mapping) else None
        if not isinstance(expectation, Mapping) or set(expectation) != {
            "effect_sha256",
            "effect_receipt_sha256",
            "host_effect_binding_sha256",
            "preimage",
        }:
            problems.append(
                _problem(
                    obligation,
                    f"/expectations/{effect_id}",
                    "effect expectation has the wrong closed shape",
                    "retain exactly effect_sha256, effect_receipt_sha256, host_effect_binding_sha256, and preimage",
                    "H6",
                )
            )
            continue
        expected_digest = expectation["effect_sha256"]
        expected_receipt = expectation["effect_receipt_sha256"]
        expected_host_binding = expectation["host_effect_binding_sha256"]
        preimage = expectation["preimage"]
        if not _hash64(expected_digest) or not _hash64(expected_receipt) or not _hash64(expected_host_binding) or not isinstance(preimage, Mapping):
            problems.append(
                _problem(obligation, f"/expectations/{effect_id}", "expectation digest, receipt, or preimage is malformed", "retain the complete receipt preimage and uppercase digests", "H6")
            )
            continue
        if observed_by_id.get(effect_id) != expected_digest:
            problems.append(
                _problem(obligation, f"/observed_effect_log/{effect_id}", "observed effect digest differs from expectation", "reject the effect outcome and investigate execution drift", "H6")
            )
        operation_fields = preimage.get("operation_fields_object")
        rule = EFFECT_RULES.get(preimage.get("obligation_id"))
        if (
            rule is None
            or preimage.get("operation_handle") != rule[0]
            or not isinstance(operation_fields, Mapping)
            or set(operation_fields) != rule[1]
        ):
            problems.append(
                _problem(
                    obligation,
                    f"/expectations/{effect_id}/preimage",
                    "effect operation or complete operation-field schema is invalid",
                    "retain the exact frozen effect operation handle and all required operation fields",
                    "H6",
                )
            )
            continue
        if not isinstance(operation_fields, Mapping) or expected_digest not in operation_fields.values():
            problems.append(
                _problem(obligation, f"/expectations/{effect_id}/preimage", "receipt preimage does not bind the observed effect digest", "include the expected observed-effect digest in the complete operation fields", "H6")
            )
            continue
        try:
            recomputed = effect_receipt_sha256(**dict(preimage))
        except (TypeError, ValueError, KeyError) as exc:
            problems.append(
                _problem(obligation, f"/expectations/{effect_id}/preimage", f"receipt preimage cannot be recomputed: {type(exc).__name__}", "restore the complete normalized preimage", "H6")
            )
        else:
            if recomputed != expected_receipt:
                problems.append(
                    _problem(obligation, f"/expectations/{effect_id}/effect_receipt_sha256", "effect receipt digest does not match the complete preimage", "reject the receipt and recompute it from the observed effect log", "H6")
                )
            try:
                recomputed_host_binding = host_effect_binding_sha256(
                    effect_id=effect_id,
                    effect_sha256=expected_digest,
                    engine_effect_receipt_sha256=expected_receipt,
                    preimage=preimage,
                )
            except (TypeError, ValueError) as exc:
                problems.append(
                    _problem(obligation, f"/expectations/{effect_id}/host_effect_binding_sha256", f"host effect binding cannot be recomputed: {type(exc).__name__}", "restore the exact host effect ID and complete normalized receipt evidence", "H6")
                )
            else:
                if recomputed_host_binding != expected_host_binding:
                    problems.append(
                        _problem(obligation, f"/expectations/{effect_id}/host_effect_binding_sha256", "engine receipt/preimage is not bound to this exact host effect ID", "reject copied or relabeled effect evidence", "H6")
                    )
    normalized = tuple(sorted(observed_pairs))
    return EffectReconciliation(not problems, tuple(problems), normalized)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="derive and preflight host fact profiles")
    parser.add_argument("--input", type=pathlib.Path, help="JSONL input (default: stdin)")
    parser.add_argument("--output", type=pathlib.Path, help="JSONL output (default: stdout)")
    args = parser.parse_args()
    source = args.input.open("r", encoding="utf-8") if args.input else sys.stdin
    sink = args.output.open("w", encoding="utf-8", newline="\n") if args.output else sys.stdout
    refused = 0
    try:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                outcome = adapt_record(record)
            except (json.JSONDecodeError, ValueError) as exc:
                outcome = AdapterOutcome("REFUSED", "UNMAPPED", None, (_problem("UNMAPPED", "/", f"line {number} is not valid bounded JSON: {exc}", "repair the raw observation before retrying"),))
            refused += not outcome.ready
            sink.write(json.dumps(outcome.as_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n")
    finally:
        if args.input:
            source.close()
        if args.output:
            sink.close()
    return 2 if refused else 0


if __name__ == "__main__":
    raise SystemExit(
        "reference_host.py is a non-shipping measurement experiment; "
        "use adapters/portable_preflight.py"
    )
