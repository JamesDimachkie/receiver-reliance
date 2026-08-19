"""The only module in this adapter that depends on the rest of the repository.

Everything the gate needs from the artifact is reached through a surface the
README's "The supported surface" section pins, so this adapter is a consumer of
the published contract rather than a second reader of engine internals:

* ``receiver_reliance`` — ``decide_audited`` (the one supported evidentiary
  route), ``verify_audit_seal``, ``AUDIT_FORMAT``. Importing the package runs the
  eleven-file engine manifest gate, so a drifted tree refuses to serve rather
  than deciding from unknown bytes.
* ``adapters`` — the shipped three-state preflight and its bounded
  canonicalization. This adapter adds no fourth state and re-derives none of its
  rules (``adapters/README.md``).
* ``portability/strict_ingest`` — the one bounded ingest law, for every byte this
  adapter reads that it did not produce (ADOPTION A4).

Two engine-internal handles the README declares reachable-but-not-an-API (``b1``,
``pcb_runner``, ``authority_surface``) are deliberately **not** used:

* Request digests are recomputed with ``adapters``' ``canonical_json_bytes``
  rather than the engine's ``jcs_bytes``. ``calibrate()`` proves the two agree
  byte-exactly over all 112 shipped pack entries, and a divergence could not
  produce a wrong classification if it ever appeared: the bound digests are
  re-derived engine-side, so a mismatch returns ``PROTOCOL_ERROR`` at exit code
  2 rather than a decision.
* ``predicate_source()`` reads the frozen decision table out of the two
  published contract documents and checks their digests against the
  ``governing_authorities`` the envelope itself names, so what ``rr_gate_explain``
  shows is bound to the bytes that governed that decision instead of to whatever
  the running process happens to have loaded.

Envelope strategy: shipped conformance fixture entries are request templates —
the engine's own accepted shapes. Only ``decision_input.facts`` and the request
ids are substituted, and every bound digest is recomputed. ``calibrate()`` proves
that recomputation reproduces all 112 shipped pack entries byte-exactly before
any substitution is trusted.

No claim is added here. Classification and sealed-audit value only; the
non-claims are ``TRUST_MODEL.md``'s, unchanged.
"""

from __future__ import annotations

import copy
import hashlib
import os
import pathlib
import sys
from typing import Any

sys.dont_write_bytecode = True

_HERE = pathlib.Path(__file__).resolve().parent


def _default_rr_home() -> pathlib.Path:
    """In-tree default: ``adapters/mcp`` -> ``adapters`` -> the repository root."""
    return _HERE.parents[1]


def rr_home() -> pathlib.Path:
    override = os.environ.get("RR_HOME")
    return pathlib.Path(override).resolve() if override else _default_rr_home().resolve()


RR_HOME = rr_home()
if not (RR_HOME / "grounded-0_4" / "rr_api.py").is_file():
    raise RuntimeError(
        f"receiver-reliance not found at {RR_HOME}; set RR_HOME to the artifact root"
    )

for _p in (str(RR_HOME), str(RR_HOME / "portability")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import adapters  # noqa: E402
import receiver_reliance  # noqa: E402
import strict_ingest  # noqa: E402
from adapters.portable_preflight import canonical_json_bytes  # noqa: E402

preflight = adapters.preflight
READY = adapters.READY
REJECTED_INVALID = adapters.REJECTED_INVALID
INSUFFICIENT_EVIDENCE = adapters.INSUFFICIENT_EVIDENCE
FACT_PROFILE_FORMAT_VERSION = adapters.FACT_PROFILE_FORMAT_VERSION
PREFLIGHT_RESULT_FORMAT_VERSION = adapters.RESULT_FORMAT_VERSION

decide_audited = receiver_reliance.decide_audited
verify_audit_seal = receiver_reliance.verify_audit_seal
AUDIT_FORMAT = receiver_reliance.AUDIT_FORMAT
ENGINE_MANIFEST_SHA256 = receiver_reliance.ENGINE_MANIFEST_SHA256

#: Every value ``audited_behavior_class`` can take. Six, not four: the law
#: assigns four, the audited surface adds two (TRUST_MODEL.md). A consumer that
#: switches on this field must handle all six, and this adapter is one.
AUDITED_BEHAVIOR_CLASSES = (
    "VALID",
    "MALFORMED_OR_BOUNDARY",
    "BINDING_OR_CONFLICT",
    "OMISSION_OR_INCOMPLETE",
    "AUDIT_INCOMPLETE",
    "PROTOCOL_ERROR",
)

_PACK_PATH = (
    RR_HOME / "baseline-run" / "fixtures" / "PRIMARY_BASELINE_SEMANTIC_FIXTURE_PACK_0_2.json"
)
#: The two published contract documents the frozen decision table is assembled
#: from, keyed by the ``governing_authorities`` member that names each one's
#: bytes. ``rr_api`` reads the same two files under the same two digests.
_CONTRACT_SOURCES: dict[str, tuple[pathlib.Path, tuple[str, ...]]] = {
    "decision_table_contract_sha256": (
        RR_HOME / "baseline-run" / "control" / "B1_PRIMARY_IMPLEMENTER_CONTRACT_0_1.json",
        ("semantic_decision_contract", "operation_decision_table"),
    ),
    "composed_contract_sha256": (
        RR_HOME
        / "supplemental-0_3"
        / "control"
        / "B1_SUPPLEMENTAL_COMPARATOR_CONTRACT_0_3.json",
        ("semantic_decision_contract_supplement", "supplemental_operation_decision_table"),
    ),
}


def load_json(path: pathlib.Path) -> Any:
    """Read one JSON document under the shared bounded ingest law (ADOPTION A4).

    Duplicate keys, non-finite constants, lone surrogates and the frozen core's
    nesting and member ceilings are rejected rather than silently resolved. This
    adapter reads bytes produced by the repository, by a host's MCP client, and
    by its own audit log on disk; none of the three is a byte it produced in the
    process doing the reading.
    """
    return strict_ingest.load_safe(path.read_bytes(), label=path.name)


_PACK = load_json(_PACK_PATH)


def evidence_sha256(value: Any) -> str:
    """Uppercase SHA-256 over the artifact's bounded canonical JSON.

    Identical to the digest ``portable_preflight`` recomputes for a native
    evidence record, so a fact profile bound with this function is checkable by
    the preflight rather than merely asserted by the host.
    """
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest().upper()


def _recompute_bindings(request: dict[str, Any]) -> dict[str, Any]:
    request["inner_request_raw_sha256"] = evidence_sha256_bytes(
        canonical_json_bytes(request["inner_request"]) + b"\n"
    )
    request["inner_input_sha256"] = evidence_sha256_bytes(
        canonical_json_bytes(request["inner_request"]["input"])
    )
    return request


def evidence_sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def calibrate() -> dict[str, Any]:
    """Prove digest recomputation reproduces every shipped pack entry byte-exactly.

    This is the gate on the request side of the boundary: if the envelope this
    adapter builds is not the shape the conformance suite validated, the engine
    will still answer and the answer will be about a different request. It also
    stands in for the one equivalence this adapter depends on — that ``adapters``'
    canonicalization and the engine's agree on these bytes.
    """
    mismatches: list[str] = []
    for entry in _PACK["entries"]:
        request = copy.deepcopy(entry["semantic_request"])
        want_inner_raw = request["inner_request_raw_sha256"]
        want_inner_input = request["inner_input_sha256"]
        _recompute_bindings(request)
        ok = (
            request["inner_request_raw_sha256"] == want_inner_raw
            and request["inner_input_sha256"] == want_inner_input
            and evidence_sha256_bytes(canonical_json_bytes(request) + b"\n")
            == entry["semantic_request_raw_sha256"]
        )
        if not ok:
            mismatches.append(entry["entry_id"])
    total = len(_PACK["entries"])
    return {
        "entries": total,
        "reproduced": total - len(mismatches),
        "mismatches": mismatches,
        "pack_id": _PACK["pack_id"],
    }


def operation_handle(obligation_id: str) -> str:
    return next(
        e["semantic_request"]["operation_handle"]
        for e in _PACK["entries"]
        if e["obligation_id"] == obligation_id
    )


def build_request(
    obligation_id: str, facts: dict[str, Any], request_seed: str
) -> dict[str, Any]:
    """Template the engine's own accepted envelope; substitute facts and ids only."""
    base = next(e for e in _PACK["entries"] if e["obligation_id"] == obligation_id)
    request = copy.deepcopy(base["semantic_request"])
    request["decision_input"]["facts"] = facts
    run_id = "RUN_" + evidence_sha256_bytes(request_seed.encode("utf-8"))[:24]
    request["request_id"] = run_id
    request["inner_request"]["request_id"] = run_id
    return _recompute_bindings(request)


def predicate_source(
    obligation_id: str, behavior_class: str, governing_authorities: Any = None
) -> dict[str, Any] | None:
    """The frozen decision-table predicate for one class, bound to its own bytes.

    Returns ``None`` when no row exists for the obligation and class — an
    obligation this adapter never maps, or a class the audited surface added
    (``AUDIT_INCOMPLETE``, ``PROTOCOL_ERROR``) which the frozen tables do not
    assign and therefore cannot witness.

    ``authority_binding`` is what makes this worth showing: each contract's
    SHA-256 is compared against the ``governing_authorities`` member the envelope
    recorded, so a reader can tell whether the predicate displayed is the one
    that governed that decision or merely the one on disk now. With no
    authorities supplied it reports ``unbound`` rather than claiming agreement.
    """
    handle = operation_handle(obligation_id)
    authorities = governing_authorities if isinstance(governing_authorities, dict) else {}
    for key, (path, pointer) in _CONTRACT_SOURCES.items():
        raw = path.read_bytes()
        document = strict_ingest.load_safe(raw, label=path.name)
        rows = document.get(pointer[0], {}).get(pointer[1], [])
        row = next((r for r in rows if r.get("operation_handle") == handle), None)
        if row is None:
            continue
        predicate = (row.get("class_predicates") or {}).get(behavior_class)
        if predicate is None:
            return None
        actual = evidence_sha256_bytes(raw)
        recorded = authorities.get(key)
        return {
            "predicate": predicate,
            "authority_key": key,
            "contract_path": path.relative_to(RR_HOME).as_posix(),
            "contract_sha256": actual,
            "authority_binding": (
                "unbound"
                if not isinstance(recorded, str)
                else "matches_decision" if recorded == actual else "differs_from_decision"
            ),
        }
    return None


__all__ = [
    "AUDITED_BEHAVIOR_CLASSES",
    "AUDIT_FORMAT",
    "ENGINE_MANIFEST_SHA256",
    "FACT_PROFILE_FORMAT_VERSION",
    "INSUFFICIENT_EVIDENCE",
    "PREFLIGHT_RESULT_FORMAT_VERSION",
    "READY",
    "REJECTED_INVALID",
    "RR_HOME",
    "build_request",
    "calibrate",
    "canonical_json_bytes",
    "decide_audited",
    "evidence_sha256",
    "evidence_sha256_bytes",
    "load_json",
    "operation_handle",
    "predicate_source",
    "preflight",
    "verify_audit_seal",
]
