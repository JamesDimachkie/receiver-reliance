"""Small clean-room S-all semantic kernel.

This module is deliberately standard-library-only and has no authority to
release an artifact.  It maps closed canonical bytes to canonical advisory
decision bytes.  The outer host remains responsible for process, attempt,
runtime, input-retention, and result custody.
"""

from __future__ import annotations

import base64
import unicodedata
import binascii
import hashlib
import json
import math
import re
from typing import Any

MAX_INPUT_BYTES = 65_536
MAX_POLICY_BYTES = 8_192
MAX_ARTIFACT_BYTES = 32_768
MAX_INSTRUCTION_CHARS = 4_096
MAX_CONSTRAINTS = 32
MAX_CONSTRAINT_CHARS = 512
MAX_IDENTIFIER_CHARS = 128
HEX_RE = re.compile(r"[0-9A-F]{64}\Z")
IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")

INPUT_FORMAT = "RR-SCIENTIFIC-S-ALL-INPUT-1"
CANDIDATE_FORMAT = "RR-SCIENTIFIC-ARM-NEUTRAL-CANDIDATE-1"
TASK_FORMAT = "RR-SCIENTIFIC-CLOSED-TASK-1"
ARTIFACT_FORMAT = "RR-SCIENTIFIC-CLOSED-ARTIFACT-1"
LINEAGE_FORMAT = "RR-SCIENTIFIC-CLOSED-LINEAGE-OBSERVATION-1"
POLICY_FORMAT = "RR-SCIENTIFIC-S-ALL-POLICY-1"
OUTPUT_FORMAT = "RR-SCIENTIFIC-S-ALL-DECISION-1"
PROFILE = "static-reference-revision-digest/1"
BOUNDARY = "WITHHOLD_IF_SCORE_GE_THRESHOLD"
SELECTION_RULE = "MIN_RISK_THEN_MAX_COVERAGE_THEN_MIN_CLEAN_WITHHOLDING"
TIE_BREAK = "HIGHEST_THRESHOLD"

REFUSAL_MAP = {
    "malformed": "DEFER",
    "missing": "DEFER",
    "ambiguous": "DEFER",
    "stale": "DEFER",
    "noncanonical": "DEFER",
    "oversized": "DEFER",
    "inconsistent": "DEFER",
    "unknown": "DEFER",
    "runtime_failure": "DEFER",
}


class KernelInputError(ValueError):
    """Closed-wire validation failure with a stable refusal reason."""

    def __init__(self, reason_code: str):
        super().__init__(reason_code)
        self.reason_code = reason_code


def canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,  # JCS: no ASCII escaping; NFC strings pass through as UTF-8 (candidate fix for the wire-law gap, 2026-09-02)
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise KernelInputError("S_NON_JSON_VALUE") from exc
    return text.encode("utf-8")


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise KernelInputError("S_DUPLICATE_KEY")
        result[key] = value
    return result


def _parse_exact(raw: bytes, maximum: int, oversize_reason: str) -> Any:
    if not isinstance(raw, bytes):
        raise KernelInputError("S_BYTES_REQUIRED")
    if not raw or len(raw) > maximum:
        raise KernelInputError(oversize_reason if len(raw) > maximum else "S_MALFORMED")
    try:
        try:
            decoded_text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise KernelInputError("S_MALFORMED") from exc
        if not unicodedata.is_normalized("NFC", decoded_text):
            raise KernelInputError("S_NONCANONICAL")
        value = json.loads(
            decoded_text,
            object_pairs_hook=_pairs_no_duplicates,
            parse_constant=lambda _: (_ for _ in ()).throw(KernelInputError("S_NONFINITE")),
        )
    except KernelInputError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise KernelInputError("S_MALFORMED") from exc
    if canonical_bytes(value) != raw:
        raise KernelInputError("S_NONCANONICAL")
    return value


def _exact_keys(value: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise KernelInputError("S_WRONG_TYPE")
    if set(value) != set(keys) or len(value) != len(keys):
        raise KernelInputError("S_UNKNOWN_OR_MISSING_FIELD")
    return value


def _string(value: Any, *, maximum: int, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise KernelInputError("S_INVALID_STRING")
    if identifier and IDENTIFIER_RE.fullmatch(value) is None:
        raise KernelInputError("S_INVALID_IDENTIFIER")
    return value


def _integer(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not (0 <= value <= 2_147_483_647):
        raise KernelInputError("S_INVALID_INTEGER")
    return value


def _sha(value: Any) -> str:
    if not isinstance(value, str) or HEX_RE.fullmatch(value) is None:
        raise KernelInputError("S_INVALID_SHA256")
    return value


def _validate_task(value: Any) -> None:
    value = _exact_keys(value, ("constraints", "format", "instruction", "task_id"))
    if value["format"] != TASK_FORMAT:
        raise KernelInputError("S_UNKNOWN_FORMAT")
    _string(value["task_id"], maximum=MAX_IDENTIFIER_CHARS, identifier=True)
    _string(value["instruction"], maximum=MAX_INSTRUCTION_CHARS)
    constraints = value["constraints"]
    if not isinstance(constraints, list) or len(constraints) > MAX_CONSTRAINTS:
        raise KernelInputError("S_INVALID_CONSTRAINTS")
    for constraint in constraints:
        _string(constraint, maximum=MAX_CONSTRAINT_CHARS)


def _validate_artifact(value: Any) -> bytes:
    value = _exact_keys(value, ("artifact_id", "content_b64", "format", "media_type", "revision"))
    if value["format"] != ARTIFACT_FORMAT:
        raise KernelInputError("S_UNKNOWN_FORMAT")
    _string(value["artifact_id"], maximum=MAX_IDENTIFIER_CHARS, identifier=True)
    _integer(value["revision"])
    if value["media_type"] not in ("application/json", "text/plain"):
        raise KernelInputError("S_UNKNOWN_MEDIA_TYPE")
    encoded = value["content_b64"]
    if not isinstance(encoded, str) or len(encoded) > ((MAX_ARTIFACT_BYTES + 2) // 3) * 4:
        raise KernelInputError("S_ARTIFACT_OVERSIZED")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise KernelInputError("S_INVALID_BASE64") from exc
    if not decoded or len(decoded) > MAX_ARTIFACT_BYTES:
        raise KernelInputError("S_ARTIFACT_OVERSIZED")
    if base64.b64encode(decoded).decode("ascii") != encoded:
        raise KernelInputError("S_NONCANONICAL_BASE64")
    if value["media_type"] == "application/json":
        _parse_exact(decoded, MAX_ARTIFACT_BYTES, "S_ARTIFACT_OVERSIZED")
    else:
        try:
            decoded.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise KernelInputError("S_INVALID_TEXT_ARTIFACT") from exc
    return decoded


def delivered_artifact_sha256(artifact: dict[str, Any]) -> str:
    """Digest the complete canonical delivered-artifact envelope."""

    _validate_artifact(artifact)
    return hashlib.sha256(canonical_bytes(artifact)).hexdigest().upper()


def _validate_lineage(value: Any) -> None:
    value = _exact_keys(value, ("format", "source_artifact_id", "source_revision", "source_sha256"))
    if value["format"] != LINEAGE_FORMAT:
        raise KernelInputError("S_UNKNOWN_FORMAT")
    _string(value["source_artifact_id"], maximum=MAX_IDENTIFIER_CHARS, identifier=True)
    _integer(value["source_revision"])
    _sha(value["source_sha256"])


def _validate_candidate(candidate: Any) -> tuple[bool, bool, bool]:
    candidate = _exact_keys(candidate, ("format", "lineage", "task", "transfer"))
    if candidate["format"] != CANDIDATE_FORMAT:
        raise KernelInputError("S_UNKNOWN_FORMAT")
    _validate_task(candidate["task"])
    _validate_lineage(candidate["lineage"])
    transfer = _exact_keys(
        candidate["transfer"],
        (
            "declared_sha256",
            "delivered_artifact",
            "delivered_artifact_id",
            "delivered_revision",
            "requested_artifact_id",
            "requested_revision",
        ),
    )
    artifact = transfer["delivered_artifact"]
    _validate_artifact(artifact)
    requested_id = _string(transfer["requested_artifact_id"], maximum=MAX_IDENTIFIER_CHARS, identifier=True)
    delivered_id = _string(transfer["delivered_artifact_id"], maximum=MAX_IDENTIFIER_CHARS, identifier=True)
    requested_revision = _integer(transfer["requested_revision"])
    delivered_revision = _integer(transfer["delivered_revision"])
    declared = _sha(transfer["declared_sha256"])
    # Duplicated delivery metadata must describe the artifact envelope.  A
    # contradiction is ambiguous evidence, not a fourth classifier feature.
    if artifact["artifact_id"] != delivered_id or artifact["revision"] != delivered_revision:
        raise KernelInputError("S_INCONSISTENT_DELIVERY_METADATA")
    return (
        requested_id != delivered_id,
        requested_revision != delivered_revision,
        declared != delivered_artifact_sha256(artifact),
    )


def _rational(value: Any) -> None:
    value = _exact_keys(value, ("denominator", "numerator"))
    numerator = value["numerator"]
    denominator = value["denominator"]
    if isinstance(numerator, bool) or not isinstance(numerator, int) or numerator < 0:
        raise KernelInputError("S_INVALID_RATIONAL")
    if isinstance(denominator, bool) or not isinstance(denominator, int) or denominator <= 0:
        raise KernelInputError("S_INVALID_RATIONAL")
    if numerator > denominator:
        raise KernelInputError("S_INVALID_RATIONAL")
    if math.gcd(numerator, denominator) != 1:
        raise KernelInputError("S_NONCANONICAL_RATIONAL")


def _validate_policy(policy: Any) -> tuple[str, int | None]:
    if not isinstance(policy, dict):
        raise KernelInputError("S_WRONG_TYPE")
    if policy["policy_state"] == "UNFROZEN":
        policy = _exact_keys(
            policy,
            (
                "operating_threshold",
                "policy_state",
                "refusal_map",
                "selection_rule",
                "selection_tie_break",
                "target_clean_withholding",
            ),
        )
        expected = {
            "operating_threshold": None,
            "refusal_map": None,
            "selection_rule": None,
            "selection_tie_break": None,
            "target_clean_withholding": None,
        }
        if any(policy[key] != expected[key] for key in expected):
            raise KernelInputError("S_POLICY_INCONSISTENT")
        return "UNFROZEN", None
    policy = _exact_keys(
        policy,
        (
            "boundary",
            "format",
            "operating_threshold",
            "policy_state",
            "refusal_map",
            "selection_rule",
            "selection_tie_break",
            "target_clean_withholding",
        ),
    )
    if policy["format"] != POLICY_FORMAT:
        raise KernelInputError("S_POLICY_UNKNOWN_FORMAT")
    if policy["policy_state"] != "FROZEN":
        raise KernelInputError("S_POLICY_UNKNOWN_STATE")
    threshold = policy["operating_threshold"]
    if isinstance(threshold, bool) or not isinstance(threshold, int) or not (0 <= threshold <= 4):
        raise KernelInputError("S_POLICY_INVALID_THRESHOLD")
    if policy["boundary"] != BOUNDARY:
        raise KernelInputError("S_POLICY_INVALID_BOUNDARY")
    if policy["selection_rule"] != SELECTION_RULE or policy["selection_tie_break"] != TIE_BREAK:
        raise KernelInputError("S_POLICY_INVALID_SELECTION")
    if policy["refusal_map"] != REFUSAL_MAP:
        raise KernelInputError("S_POLICY_INVALID_REFUSAL_MAP")
    _rational(policy["target_clean_withholding"])
    return "FROZEN", threshold


def _defer(raw_input: bytes, raw_policy: bytes, reason: str) -> bytes:
    output = {
        "candidate_sha256": None,
        "disposition": "DEFER",
        "feature_bits": None,
        "format": OUTPUT_FORMAT,
        "input_sha256": hashlib.sha256(raw_input if isinstance(raw_input, bytes) else b"").hexdigest().upper(),
        "module_semantics_id": PROFILE,
        "policy_sha256": hashlib.sha256(raw_policy if isinstance(raw_policy, bytes) else b"").hexdigest().upper(),
        "reason_code": reason,
        "risk_score": None,
    }
    return canonical_bytes(output)


def decide(raw_input: bytes, raw_policy: bytes) -> bytes:
    """Return canonical advisory bytes; every invalid state deterministically DEFERs."""

    try:
        policy = _parse_exact(raw_policy, MAX_POLICY_BYTES, "S_POLICY_OVERSIZED")
        policy_state, threshold = _validate_policy(policy)
        if policy_state != "FROZEN" or threshold is None:
            return _defer(raw_input, raw_policy, "S_POLICY_UNFROZEN")
        source = _parse_exact(raw_input, MAX_INPUT_BYTES, "S_INPUT_OVERSIZED")
        source = _exact_keys(source, ("candidate", "candidate_sha256", "format", "profile"))
        if source["format"] != INPUT_FORMAT or source["profile"] != PROFILE:
            raise KernelInputError("S_UNKNOWN_FORMAT")
        candidate_sha = _sha(source["candidate_sha256"])
        if hashlib.sha256(canonical_bytes(source["candidate"])).hexdigest().upper() != candidate_sha:
            raise KernelInputError("S_STALE_CANDIDATE_SHA256")
        features = _validate_candidate(source["candidate"])
        score = sum(features)
        blocked = score >= threshold
        output = {
            "candidate_sha256": candidate_sha,
            "disposition": "BLOCK" if blocked else "PASS",
            "feature_bits": list(features),
            "format": OUTPUT_FORMAT,
            "input_sha256": hashlib.sha256(raw_input).hexdigest().upper(),
            "module_semantics_id": PROFILE,
            "policy_sha256": hashlib.sha256(raw_policy).hexdigest().upper(),
            "reason_code": "S_SCORE_AT_OR_ABOVE_THRESHOLD" if blocked else "S_SCORE_BELOW_THRESHOLD",
            "risk_score": score,
        }
        return canonical_bytes(output)
    except KernelInputError as exc:
        return _defer(raw_input, raw_policy, exc.reason_code)
    except Exception:
        # The pure function is total at its public boundary.  Unexpected local
        # failure still cannot improve a disposition.
        return _defer(raw_input, raw_policy, "S_RUNTIME_FAILURE")


def verify_decision(raw_input: bytes, raw_policy: bytes, raw_output: bytes) -> bool:
    """Exact independent replay check; caller-created coherent reseals do not help."""

    if not isinstance(raw_output, bytes) or len(raw_output) > MAX_POLICY_BYTES:
        return False
    return decide(raw_input, raw_policy) == raw_output
