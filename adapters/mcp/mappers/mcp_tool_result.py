"""Shape mapper: MCP tool-call result -> native evidence record + fact profile.

One mapper, one obligation. This module maps an MCP ``CallToolResult`` that a
caller intends to rely on as a *record* onto the calibrated ``REF`` family of the
shipped portable preflight, which the artifact binds to **OBL-02, exact
reference resolution**.

H4 (applicability calibration) is the governing obligation here. The native
precondition below is observable over the tool call and its result alone. When it
does not hold the mapper emits the uncalibrated family
``MCP_RESULT_UNCLASSIFIED`` and the shipped preflight abstains
(``INSUFFICIENT_EVIDENCE`` / ``PREFLIGHT_FAMILY_UNCALIBRATED``). Abstention is the
designed outcome, never a failure. **Fabricating a fact value is forbidden**: the
mapper derives every field from the call and the result, or it omits the field
and discloses the omission in ``notes``.

Native precondition (REF / OBL-02)
----------------------------------
The mapper maps a tool result as a REF record iff **at least one exact record
identity is observable**: the caller declares the record it asked for
(``call.record_reference.requested``), or the result declares the record it
carries (``call.record_reference.returned``), or both. No identity is ever
invented, and ``returned`` is never defaulted to ``requested``.

Derivation law, per native field
--------------------------------
``native.claimed_path``      := ``record_reference.requested`` verbatim, when present.
                               The exact record identity the caller relies on.
``native.referenced_record`` := ``record_reference.returned`` verbatim, when present.
                               The identity the delivered result claims to carry.
                               The two are aliases of one reference observation;
                               the preflight rejects them when they disagree
                               (``PREFLIGHT_REF_ALIAS_CONTRADICTION``), which is
                               precisely 'the tool returned a record other than
                               the one relied on'.
``native.claimed_sha256``    := ``record_reference.declared_revision_sha256``, but
                               **only** when ``revision_digest_domain`` is declared
                               and resolves against the delivered result. A digest
                               claim that cannot be bound to bytes is dropped and
                               disclosed (``CLAIM_UNBOUND_DIGEST_DOMAIN``); it is
                               never compared across digest domains, because a
                               cross-domain comparison manufactures false holds
                               (the H4 failure mode measured in proof/RESULTS.md).
``observations.referenced_record_found``
                             := ``result.isError is not True``. One explicit
                               Boolean lookup outcome per call.
``observations.observed_sha256``
                             := uppercase SHA-256 over the artifact's bounded
                               canonical JSON of the delivery projection, supplied
                               only when ``referenced_record_found`` is true (the
                               preflight rejects content testimony for an absent
                               record). The projection is the resolved
                               ``revision_digest_domain`` pointer when one was
                               declared and resolved, otherwise the whole result
                               object under the default domain ``canonical-json:/``.

Nothing from the result payload is copied into the native record: identities and
digests only. Payload content is neither recorded nor logged.

What this mapper does not do
----------------------------
It does not enforce, retrieve, store, or authorize. It does not verify that the
caller's attested identities and digests are true; H1 (state truthfulness) stays
with the host and a deceptive attester defeats this by construction.
"""

from __future__ import annotations

import dataclasses
import hashlib
import pathlib
import re
import sys
from typing import Any

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rr_bridge import (  # noqa: E402
    FACT_PROFILE_FORMAT_VERSION,
    canonical_json_bytes,
    evidence_sha256,
)

MAPPER_ID = "mcp-tool-result/1"
FAMILY_REF = "REF"
FAMILY_UNCLASSIFIED = "MCP_RESULT_UNCLASSIFIED"
OBLIGATION_REF = "OBL-02"
DEFAULT_DIGEST_DOMAIN = "canonical-json:/"

_HEX64 = re.compile(r"^[0-9A-F]{64}$")
_DOMAIN = re.compile(r"^canonical-json:(/.*|/)$")

# Field-level evidence pointers, exactly as adapters/portable_preflight.py's REF
# assessor records them. The preflight compares these; a drift here is a
# REJECTED_INVALID at the boundary, not a silent bad decision.
_REF_DERIVATIONS = {
    "exact_reference": ["/native/claimed_path", "/native/referenced_record"],
    "record_versions": [
        "/native/claimed_sha256",
        "/observations/referenced_record_found",
        "/observations/observed_sha256",
    ],
}


@dataclasses.dataclass(frozen=True, slots=True)
class Mapping:
    """One mapping attempt. ``mapped`` False means the mapper declined."""

    record: dict[str, Any]
    fact_profile: dict[str, Any] | None
    obligation_id: str | None
    family: str
    mapped: bool
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "mapper_id": MAPPER_ID,
            "family": self.family,
            "obligation_id": self.obligation_id,
            "mapped": self.mapped,
            "notes": list(self.notes),
            "record": self.record,
            "fact_profile": self.fact_profile,
        }


def _resolve_pointer(document: Any, pointer: str) -> tuple[Any, bool]:
    """Minimal RFC 6901 resolution. Returns (value, resolved)."""
    if pointer == "" or pointer == "/":
        return document, True
    node = document
    for raw in pointer.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            if token not in node:
                return None, False
            node = node[token]
        elif isinstance(node, list):
            if not token.isdigit() or int(token) >= len(node):
                return None, False
            node = node[int(token)]
        else:
            return None, False
    return node, True


def _record_id(call: Any, result: Any) -> str:
    """Content-addressed record id: stable for identical evidence, no clock."""
    try:
        seed = canonical_json_bytes({"call": call, "result": result})
    except (TypeError, ValueError):
        seed = repr((call, result)).encode("utf-8", "replace")
    return "MCPREC_" + hashlib.sha256(seed).hexdigest().upper()[:16]


def _unclassified(
    record_id: str, note: str, native: Any = None, observations: Any = None
) -> Mapping:
    record: dict[str, Any] = {"record_id": record_id, "family": FAMILY_UNCLASSIFIED}
    if native is not None:
        record["native"] = native
    if observations is not None:
        record["observations"] = observations
    return Mapping(record, None, None, FAMILY_UNCLASSIFIED, False, (note,))


def map_tool_result(payload: Any) -> Mapping:
    """Map one MCP tool-call result onto native evidence + a host fact profile.

    ``payload`` members:
      ``call.record_reference.requested``  exact record identity relied on
      ``call.record_reference.returned``   identity the result declares (optional)
      ``call.record_reference.declared_revision_sha256``    (optional)
      ``call.record_reference.revision_digest_domain``      (required with the above)
      ``result``                           the MCP CallToolResult, verbatim
      ``reliance``                         free-form intent context; logged, never classified
    """
    if not isinstance(payload, dict):
        return _unclassified("MCPREC_MALFORMED", "MAPPER_PAYLOAD_NOT_OBJECT")
    call = payload.get("call")
    result = payload.get("result")
    record_id = _record_id(call, result)

    if not isinstance(result, dict):
        return _unclassified(record_id, "MAPPER_RESULT_NOT_OBJECT")
    if not isinstance(call, dict):
        return _unclassified(record_id, "MAPPER_CALL_CONTEXT_MISSING")

    reference = call.get("record_reference")
    if not isinstance(reference, dict):
        return _unclassified(record_id, "MAPPER_NO_RECORD_REFERENCE_DECLARED")

    requested = reference.get("requested")
    returned = reference.get("returned")
    for value, label in ((requested, "requested"), (returned, "returned")):
        if value is not None and (not isinstance(value, str) or not value):
            return _unclassified(record_id, f"MAPPER_REFERENCE_{label.upper()}_MALFORMED")
    if requested is None and returned is None:
        # Native precondition unmet: no exact record identity is observable, so
        # this result carries no OBL-02 semantics. Decline; never invent one.
        return _unclassified(record_id, "MAPPER_PRECONDITION_UNMET_NO_EXACT_IDENTITY")

    notes: list[str] = []
    if returned is None:
        notes.append("IDENTITY_AGREEMENT_UNCHECKED_RESULT_DECLARES_NO_IDENTITY")
    if requested is None:
        notes.append("REQUESTED_REFERENCE_ABSENT_JUDGING_RETURNED_IDENTITY_ONLY")

    # -- delivery outcome (one explicit Boolean per call) ---------------------
    is_error = result.get("isError")
    if is_error is not None and not isinstance(is_error, bool):
        return _unclassified(record_id, "MAPPER_RESULT_ISERROR_NOT_BOOLEAN")
    found = is_error is not True

    # -- digest domain + projection ------------------------------------------
    declared = reference.get("declared_revision_sha256")
    domain = reference.get("revision_digest_domain")
    claimed_sha256: str | None = None
    active_domain = DEFAULT_DIGEST_DOMAIN
    projection: Any = result

    if declared is not None:
        if not isinstance(declared, str) or not _HEX64.fullmatch(declared):
            return _unclassified(record_id, "MAPPER_DECLARED_DIGEST_MALFORMED")
        if not isinstance(domain, str) or not _DOMAIN.fullmatch(domain):
            notes.append("CLAIM_UNBOUND_DIGEST_DOMAIN")
        else:
            value, resolved = _resolve_pointer(result, domain.split(":", 1)[1])
            if not resolved:
                notes.append("CLAIM_UNBOUND_DIGEST_DOMAIN")
            else:
                claimed_sha256 = declared
                active_domain = domain
                projection = value
    elif isinstance(domain, str) and _DOMAIN.fullmatch(domain):
        value, resolved = _resolve_pointer(result, domain.split(":", 1)[1])
        if resolved:
            active_domain = domain
            projection = value
        else:
            notes.append("DIGEST_DOMAIN_UNRESOLVED_USING_FULL_RESULT")

    # -- observed content testimony ------------------------------------------
    observed_sha256: str | None = None
    if found:
        try:
            observed_sha256 = (
                hashlib.sha256(canonical_json_bytes(projection)).hexdigest().upper()
            )
        except (TypeError, ValueError) as exc:
            # The delivered payload lies outside the artifact's bounded JSON
            # domain, so no content testimony can be derived from it. Abstain.
            return _unclassified(
                record_id,
                f"MAPPER_PAYLOAD_OUT_OF_BOUNDED_JSON_DOMAIN: {str(exc)[:120]}",
            )

    native: dict[str, Any] = {}
    if requested is not None:
        native["claimed_path"] = requested
    if returned is not None:
        native["referenced_record"] = returned
    if claimed_sha256 is not None:
        native["claimed_sha256"] = claimed_sha256

    observations: dict[str, Any] = {"referenced_record_found": found}
    if observed_sha256 is not None:
        observations["observed_sha256"] = observed_sha256

    record = {
        "record_id": record_id,
        "family": FAMILY_REF,
        "native": native,
        "observations": observations,
    }

    facts = _ref_facts(native, observations)
    profile = {
        "format_version": FACT_PROFILE_FORMAT_VERSION,
        "record_id": record_id,
        "obligation_id": OBLIGATION_REF,
        "native_evidence_sha256": evidence_sha256(record),
        "facts": facts,
        "derivations": dict(_REF_DERIVATIONS),
        "fabricated_fields": [],
    }
    notes.append(f"DIGEST_DOMAIN={active_domain}")
    return Mapping(record, profile, OBLIGATION_REF, FAMILY_REF, True, tuple(notes))


def _ref_facts(native: dict[str, Any], observations: dict[str, Any]) -> dict[str, Any]:
    """Derive the OBL-02 fact profile exactly as the shipped REF assessor does.

    Held deliberately identical to ``adapters/portable_preflight.py::_assess_ref``
    so ``preflight(record, profile)`` cross-checks this derivation instead of
    trusting it. Any drift surfaces as ``PREFLIGHT_PROFILE_FACT_MISMATCH``.
    """
    reference = next(
        value
        for value in (native.get("claimed_path"), native.get("referenced_record"))
        if value is not None
    )
    versions: list[dict[str, str]] = []
    if observations.get("referenced_record_found"):
        versions.append(
            {"record_id": reference, "revision_sha256": observations["observed_sha256"]}
        )
        if native.get("claimed_sha256") is not None:
            versions.append(
                {"record_id": reference, "revision_sha256": native["claimed_sha256"]}
            )
    return {"exact_reference": reference, "record_versions": versions}


__all__ = [
    "DEFAULT_DIGEST_DOMAIN",
    "FAMILY_REF",
    "FAMILY_UNCLASSIFIED",
    "MAPPER_ID",
    "Mapping",
    "OBLIGATION_REF",
    "map_tool_result",
]
