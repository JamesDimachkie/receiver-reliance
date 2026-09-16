"""Arm R-all -- receiver-local acceptance and use from candidate-neutral raw facts.

``architecture.arm_isolation``: R imports common code plus ``receiver_reliance``.
It imports neither ``rr_s_all_kernel`` nor either other arm.  The accepted
dependency pins are proved against the worktree before that import happens and
re-asserted before every accepted call.

The four ordered stages are ``r_semantics.derivation``,
``r_semantics.accepted_engine_mapping``, ``r_semantics.lineage`` and
``r_semantics.acceptance``.  ``r_semantics.evidence_authority`` fixes what each
reached baseline carries, and ``r_semantics.evidence_by_code`` fixes which codes
carry evidence at all.
"""

import copy
import json

from .common import decision
from .common import pins
from .common import seed_data
from .common import seam
from .common import wire

pins.verify_at_import()

import receiver_reliance as _engine  # noqa: E402  (pins gate this import)

pins.bind_module("receiver_reliance", _engine, "receiver_reliance/__init__.py")

ENTRYPOINT = "DECIDE_R"

# r_semantics.request_constructor: the pinned accepted seed, verified in place.
SEED_BYTES = wire.b64decode_strict("".join(seed_data.SEED_B64))
if len(SEED_BYTES) != seed_data.SEED_BYTE_LENGTH:
    raise ImportError("embedded OBL-26 seed byte length does not match its pin")
if wire.sha256_upper(SEED_BYTES) != seed_data.SEED_SHA256:
    raise ImportError("embedded OBL-26 seed SHA-256 does not match its pin")
SEED = json.loads(SEED_BYTES.decode("utf-8"))

# r_semantics.constants: the two decoded accepted constants and their digests.
CANONICALIZATION_DESCRIPTOR_B64 = (
    "eyJhZG1pdHRlZF9qc29uX2RvbWFpbiI6IkFTQ0lJX09CSkVDVF9LRVlTX1VURjhfU1RSSU5H"
    "U19TQUZFX0lOVEVHRVJTX0JPT0xFQU5TX05VTEwiLCJkZXNjcmlwdG9yX2lkIjoiRUhfQ0FO"
    "T05JQ0FMX0pTT05fMF8xIiwiZGlnZXN0X2FsZ29yaXRobSI6IlNIQS0yNTYiLCJkb21haW5f"
    "c2VwYXJhdG9ycyI6eyJhY2NlcHRhbmNlIjoiRUgtQUNDRVBUQU5DRS12MSIsImNsb3N1cmUi"
    "OiJFSC1DTE9TVVJFLXYxIiwiY29tbWl0X3Byb29mIjoiRUgtQ09NTUlULVBST09GLXYxIiwi"
    "ZGVzY3JpcHRvciI6IkVILURFU0NSSVBUT1ItdjEiLCJlbXB0eV9ldmVudF9sb2ciOiJFSC1F"
    "TVBUWS1FVkVOVC1MT0ctdjEiLCJldmVudF9jb250ZW50IjoiRUgtRVZFTlQtQ09OVEVOVC12"
    "MSIsImV2ZW50X3NldCI6IkVILUVWRU5ULVNFVC12MSIsImdyYW50IjoiRUgtR1JBTlQtdjEi"
    "LCJtYXBwaW5nX3NwZWMiOiJFSC1NQVBQSU5HLVNQRUMtdjEiLCJwb2xpY3kiOiJFSC1QT0xJ"
    "Q1ktdjEiLCJyYXdfcG9saWN5X2lkZW50aXR5IjoiRUgtUkFXLVBPTElDWS1JREVOVElUWS12"
    "MSIsInNoYXJlZF9idW5kbGUiOiJFSC1TSEFSRUQtQlVORExFLXYxIiwic25hcHNob3QiOiJF"
    "SC1TTkFQU0hPVC12MSIsInN0YW5kaW5nIjoiRUgtU1RBTkRJTkctdjEiLCJ2b2NhYnVsYXJ5"
    "IjoiRUgtVk9DQUItdjEifSwiaW5zdGFudF9mb3JtYXQiOiJSRkMzMzM5X1VUQ19GSVhFRF9T"
    "RUNPTkRTIiwic2VsZl9maWVsZF9leGNsdXNpb25zIjp7IkNhbm9uaWNhbGl6YXRpb25EZXNj"
    "cmlwdG9yIjpbImRlc2NyaXB0b3Jfc2hhMjU2Il0sIkNsb3N1cmVFdmlkZW5jZVJlY29yZCI6"
    "WyJjbG9zdXJlX2V2aWRlbmNlX2RpZ2VzdCJdLCJEZWxlZ2F0ZWRBY2NlcHRhbmNlR3JhbnRJ"
    "c3N1ZWQiOlsiZ3JhbnRfdmVyc2lvbl9kaWdlc3QiLCJjb21taXR0ZWRfYXQiLCJmcm9udGll"
    "cl9wb3NpdGlvbiIsImV2ZW50X2NvbnRlbnRfZGlnZXN0IiwicHJldmlvdXNfY29tbWl0X3By"
    "b29mX2RpZ2VzdCIsImNvbW1pdF9wcm9vZl9kaWdlc3QiXSwiRXZhbHVhdGlvblBvbGljeUJ1"
    "bmRsZSI6WyJwb2xpY3lfdmVyc2lvbl9kaWdlc3QiXSwiUHJlQWN0aW9uU25hcHNob3QiOlsi"
    "c25hcHNob3RfaWQiXSwiUmVsaWFuY2VBY2NlcHRhbmNlSXNzdWVkIjpbImFjY2VwdGFuY2Vf"
    "dmVyc2lvbl9pZCIsImNvbW1pdHRlZF9hdCIsImZyb250aWVyX3Bvc2l0aW9uIiwiZXZlbnRf"
    "Y29udGVudF9kaWdlc3QiLCJwcmV2aW91c19jb21taXRfcHJvb2ZfZGlnZXN0IiwiY29tbWl0"
    "X3Byb29mX2RpZ2VzdCJdLCJSb290U3RhbmRpbmdCYXNpc1ZlcnNpb24iOlsic3RhbmRpbmdf"
    "YmFzaXNfdmVyc2lvbl9kaWdlc3QiXX0sInNlcXVlbmNlX2FycmF5X3J1bGUiOiJQUkVTRVJW"
    "RV9PUkRFUiIsInNlcmlhbGl6YXRpb24iOiJSRkM4Nzg1X0pTT05fQ0FOT05JQ0FMSVpBVElP"
    "TiIsInNldF9hcnJheV9ydWxlIjoiU09SVF9MRVhJQ09HUkFQSElDX0FORF9SRUpFQ1RfRFVQ"
    "TElDQVRFUyIsInRleHRfZW5jb2RpbmciOiJVVEYtOCJ9"
)
CANONICALIZATION_DESCRIPTOR_BYTE_LENGTH = 1491
CANONICALIZATION_DESCRIPTOR_SHA256 = (
    "8A9B72EE6A4514AB9192782DF2361A649ACA9A210B20CE0ED59B71E4F8C11F94"
)
EVALUATION_POLICY_B64 = (
    "eyJpbmNvbXBhdGliaWxpdHlfcnVsZXMiOltdLCJsaWZlY3ljbGVfcmVkdWNlcl9yZWYiOiJM"
    "SUZFQ1lDTEVfUkVEVUNFUl9HMF8wMSIsIm1heF9zbmFwc2hvdF9hZ2Vfc2Vjb25kcyI6NjAs"
    "Im1pZ3JhdGlvbl9ydWxlcyI6W10sInBvbGljeV9pZCI6IlBPTElDWV9HMF8wMSIsInJlYXNv"
    "bl9jb2RlX3NldCI6WyJDTE9TVVJFX0lOQ09NUExFVEUiLCJDT01QRVRJTkdfU1VDQ0VTU09S"
    "UyIsIkZSRVNITkVTU19VTlJFU09MVkVEIiwiSU5DT01QQVRJQkxFX1JFQ09SRFMiLCJMSUZF"
    "Q1lDTEVfQ09ORkxJQ1QiLCJNVUxUSVBMRV9MSVZFX0dSQU5UUyIsIk1VTFRJUExFX1FVQUxJ"
    "RllJTkciLCJOT05DT01NVVRJTkdfTElGRUNZQ0xFIiwiTk9fTElTVEVEX1FVQUxJRllJTkci"
    "LCJPTkVfTElTVEVEX1FVQUxJRllJTkciLCJQT0xJQ1lfTUlTTUFUQ0giLCJSRUZFUkVOQ0Vf"
    "VU5SRVNPTFZFRCIsIlNUQU5ESU5HX0lOQVBQTElDQUJMRSIsIlRFTVBPUkFMX0lOQVBQTElD"
    "QUJMRSJdLCJyZXF1aXJlZF9ldmVudF9jbGFzc2VzIjpbIkNMQUlNX1ZFUlNJT04iLCJERUNM"
    "QVJBVElPTl9SRUNPUkQiLCJNQU5EQVRFX1JFQ09SRCIsIlVTRV9SRUNPUkQiXSwicmVxdWly"
    "ZWRfc291cmNlX3J1bGVfcmVmIjoiUkVRVUlSRURfU09VUkNFU19HMF8wMSIsInNlbGVjdG9y"
    "X2xhbmd1YWdlIjoiRUgtU0VMRUNUT1ItQ09SRS0wXzEiLCJzbmFwc2hvdF9mcmVzaG5lc3Nf"
    "bWV0aG9kX3JlZiI6IlNOQVBTSE9UX0ZSRVNITkVTU19HMF8wMSIsInN1cHBsZW1lbnRhcnlf"
    "dW5rbm93bl9yZWFzb25fY29kZV9zZXQiOlsiQ0xPU1VSRV9JTkNPTVBMRVRFIiwiRlJFU0hO"
    "RVNTX1VOUkVTT0xWRUQiLCJSRUZFUkVOQ0VfVU5SRVNPTFZFRCJdfQ=="
)
EVALUATION_POLICY_BYTE_LENGTH = 850
EVALUATION_POLICY_SHA256 = (
    "1FB9B260CB8CBA831A5F61C44143F5CC98C537B58D64B803700FBEC2FB750754"
)

_DESCRIPTOR_BYTES = wire.b64decode_strict(CANONICALIZATION_DESCRIPTOR_B64)
_POLICY_BYTES = wire.b64decode_strict(EVALUATION_POLICY_B64)
if (
    len(_DESCRIPTOR_BYTES) != CANONICALIZATION_DESCRIPTOR_BYTE_LENGTH
    or wire.sha256_upper(_DESCRIPTOR_BYTES) != CANONICALIZATION_DESCRIPTOR_SHA256
):
    raise ImportError("the canonicalization descriptor does not match its constants")
if (
    len(_POLICY_BYTES) != EVALUATION_POLICY_BYTE_LENGTH
    or wire.sha256_upper(_POLICY_BYTES) != EVALUATION_POLICY_SHA256
):
    raise ImportError("the evaluation policy does not match its constants")
DESCRIPTOR = json.loads(_DESCRIPTOR_BYTES.decode("utf-8"))
POLICY = json.loads(_POLICY_BYTES.decode("utf-8"))
DOMAIN_SEPARATORS = DESCRIPTOR["domain_separators"]
SELF_FIELD_EXCLUSIONS = DESCRIPTOR["self_field_exclusions"]

# r_semantics.acceptance: the two exact required sets.
REQUIRED_SOURCE_EXTENT = frozenset(("SOURCE_MANDATE", "SOURCE_PRIMARY"))
REQUIRED_RECORD_CLASSES = frozenset(POLICY["required_event_classes"])

ACCEPTANCE_KINDS = ("ADOPTION_DECLARED", "INTENDED_USE_DECLARED")
DELEGATION_KIND = "DELEGATION_DECLARED"
REVOCATION_KIND = "DECLARATION_WITHDRAWN"
SUPERSESSION_KIND = "DECLARATION_REPLACED"

ENGINE_CONCLUSIVE_CLASSES = ("MALFORMED_OR_BOUNDARY", "BINDING_OR_CONFLICT")
ENGINE_UNRESOLVED_CLASSES = (
    "OMISSION_OR_INCOMPLETE",
    "AUDIT_INCOMPLETE",
    "PROTOCOL_ERROR",
)


class _DerivationUnresolved(Exception):
    """``r_semantics.derivation`` rejected the raw A2 facts."""


class _Unknown(Exception):
    """``r_semantics.acceptance`` reached an UNKNOWN horizon or reference."""


class _Conflict(Exception):
    """``r_semantics.acceptance`` reached a CONFLICT resolution."""


# -- r_semantics.derivation ---------------------------------------------------


def _derive(bundle):
    """Validate the raw A2 facts and return the derived working record.

    Conversion (T-12/T-17/E51): every mandate record is converted; a
    declaration row is converted only when its declaration reference is in
    the single ledger's ordered included-record list, and an unlisted row is
    ignored for every purpose.  Identity collisions among the converted
    records and the mandate namespace, and a converted delegation whose root
    does not resolve to a mandate record, fail here, before acceptance.
    Grants are addressed by declaration reference only.  Nothing in
    ``bundle`` is mutated; every container built here is new.
    """
    uses = bundle["use_records"]
    ledgers = bundle["ledger_observations"]
    closures = bundle["closure_attestations"]
    if len(uses) != 1 or len(ledgers) != 1 or len(closures) != 1:
        raise _DerivationUnresolved("not exactly one use, ledger and closure")
    use = uses[0]
    ledger = ledgers[0]
    closure = closures[0]

    if ledger["action_or_decision_ref"] != use["action_or_decision_ref"]:
        raise _DerivationUnresolved("action reference does not match")
    if ledger["decision_context_ref"] != use["decision_context_ref"]:
        raise _DerivationUnresolved("decision reference does not match")
    # T-7/T-16: capture is strictly before use; equality fails here.
    if not _before(ledger["captured_at"], use["occurred_at"]):
        raise _DerivationUnresolved("the snapshot was not captured before the use")
    if closure["ledger_id"] != ledger["ledger_id"]:
        raise _DerivationUnresolved("closure ledger does not match")
    if closure["committed_frontier"] != ledger["committed_frontier"]:
        raise _DerivationUnresolved("closure frontier does not match")

    order = ledger["included_record_refs"]
    listed = frozenset(order)
    if len(listed) != len(order):
        raise _DerivationUnresolved("repeated ledger reference")

    roots = {}
    for mandate in bundle["domain_mandate_records"]:
        key = mandate["mandate_version_ref"]
        if key in roots:
            raise _DerivationUnresolved("duplicate mandate reference")
        roots[key] = mandate

    records = {}
    for record in bundle["declaration_records"]:
        key = record["declaration_version_ref"]
        if key not in listed:
            continue  # unlisted: ignored for every purpose
        if key in records:
            raise _DerivationUnresolved("duplicate converted declaration reference")
        records[key] = record

    position = {ref: index for index, ref in enumerate(order)}
    events = [records[ref] for ref in order if ref in records]

    grants = {}
    grant_ids = set()
    for record in events:
        if record["declaration_kind"] != DELEGATION_KIND:
            continue
        grant_id = record.get("grant_id")
        if grant_id is not None:
            if grant_id in grant_ids:
                raise _DerivationUnresolved(
                    "duplicate converted delegation grant identity"
                )
            if grant_id in records:
                raise _DerivationUnresolved(
                    "a grant identity collides with a converted declaration reference"
                )
            grant_ids.add(grant_id)
        grants[record["declaration_version_ref"]] = record

    for key in roots:
        if key in records or key in grant_ids:
            raise _DerivationUnresolved(
                "a mandate reference collides with a converted declaration identity"
            )

    for ref, grant in grants.items():
        basis = grant.get("standing_basis_ref")
        if basis == ref:
            raise _DerivationUnresolved("delegation standing cycle")
        if basis in records:
            # One hop only: a grant rests on a mandate record, never on another
            # converted declaration (a recursive or wrong-kind root).
            raise _DerivationUnresolved("nonrecursive delegation violated")
        if basis not in roots:
            raise _DerivationUnresolved("delegation standing is unresolved")

    return {
        "use": use,
        "ledger": ledger,
        "closure": closure,
        "roots": roots,
        "records": records,
        "events": events,
        "grants": grants,
        "position": position,
        # canonical_wire / evidence_authority.recorded_use_sha256: compact UTF-8
        # key-sorted exact selected A2 use_records[0] with no LF.
        "recorded_use_sha256": wire.sha256_upper(wire.jcs(use)),
    }


def _before(left, right):
    return _instant(left) < _instant(right)


def _at_or_before(left, right):
    return _instant(left) <= _instant(right)


def _instant(text):
    """RFC3339 UTC fixed seconds, as declared by the descriptor instant_format."""
    if not isinstance(text, str) or len(text) != 20 or not text.endswith("Z"):
        raise _DerivationUnresolved("instant is not RFC3339 UTC fixed seconds")
    return (
        int(text[0:4]),
        int(text[5:7]),
        int(text[8:10]),
        int(text[11:13]),
        int(text[14:16]),
        int(text[17:19]),
    )


# -- r_semantics.accepted_engine_mapping --------------------------------------


def _build_request(common):
    """The exact OBL-26 accepted request, from raw common facts only."""
    request = copy.deepcopy(SEED)
    request["decision_input"]["facts"] = copy.deepcopy(
        common["guard_observation_facts"]
    )
    bundle = copy.deepcopy(common["a2_raw_shared_bundle"])
    request["inner_request"]["input"] = bundle
    request["inner_input_sha256"] = wire.sha256_upper(wire.jcs(bundle))
    request["inner_request_raw_sha256"] = wire.sha256_upper(
        wire.jcs(request["inner_request"]) + b"\n"
    )
    return wire.jcs(request) + b"\n"


def _engine_class(common):
    """Invoke the accepted engine and map its audited class."""
    pins.assert_verified("receiver_reliance")
    request_bytes = _build_request(common)
    try:
        envelope = _engine.decide_audited(request_bytes)
    except BaseException:  # r_semantics.accepted_engine_mapping: exception
        return "UNRESOLVED", None
    if not isinstance(envelope, dict):
        return "UNRESOLVED", None
    if envelope.get("format_version") != _engine.AUDIT_FORMAT:
        return "UNRESOLVED", None
    native = envelope.get("audited_behavior_class")
    if native in ENGINE_CONCLUSIVE_CLASSES:
        return "CONCLUSIVE", None
    if native in ENGINE_UNRESOLVED_CLASSES:
        return "UNRESOLVED", None
    if native != "VALID":
        # an unregistered native class
        return "UNRESOLVED", None
    try:
        output = wire.jcs(envelope) + b"\n"
    except ValueError:
        return "UNRESOLVED", None
    return "VALID", wire.sha256_upper(output)


# -- r_semantics.lineage ------------------------------------------------------


def _lineage(common):
    facts = common["comparison_facts"]
    if not facts["origin_finalized"]:
        return "UNRESOLVED"
    conclusive = (
        facts["expected_receiver_capability"] != facts["observed_receiver_capability"]
        or facts["expected_direct_parents"] != facts["observed_direct_parents"]
        or facts["expected_route"] != facts["observed_route"]
        or facts["expected_slot"] != facts["observed_slot"]
        or facts["expected_carrier"] != facts["observed_carrier"]
        or facts["expected_generation"] != facts["observed_generation"]
        or bool(facts["revocation_active"])
        or facts["current_fence"] > facts["carrier_fence"]
        or not (
            facts["valid_from_ns"] <= facts["use_time_ns"] <= facts["valid_until_ns"]
        )
    )
    if conclusive:
        return "CONCLUSIVE"
    return "CONTINUE"


# -- r_semantics.acceptance ---------------------------------------------------


def _acceptance(derived):
    """r_semantics.acceptance under the corrected treatment specification.

    Every UNKNOWN condition is evaluated before either CONFLICT rule: the
    exact required source extent and record-class set, the closure and
    snapshot horizons, every lifecycle target, the standing of every active
    acceptance, and every declared basis.  Only then does an effective
    wrong-kind lifecycle target or a second qualifying acceptance conflict.
    Exactly one qualifying acceptance listed by this recorded use is
    APPLICABLE; anything else is INAPPLICABLE.
    """
    use = derived["use"]
    closure = derived["closure"]
    at = use["occurred_at"]

    if frozenset(closure["source_extent"]) != REQUIRED_SOURCE_EXTENT:
        raise _Unknown("closure source extent is not the exact required set")
    if frozenset(closure["closed_record_classes"]) != REQUIRED_RECORD_CLASSES:
        raise _Unknown("closure record classes are not the exact required set")
    if not _at_or_before(at, closure["closed_through"]):
        raise _Unknown("the closure horizon does not reach the use time")
    if not _snapshot_fresh(derived, use):
        raise _Unknown("the pre-action snapshot is not fresh through the use time")

    killed, target_conflict = _lifecycle_targets(derived, use)

    active = []
    for record in derived["events"]:
        if record["declaration_kind"] not in ACCEPTANCE_KINDS:
            continue
        if record["declaration_version_ref"] in killed:
            continue
        # Standing is resolved for every active acceptance whether or not its
        # other fields match: unresolved standing is UNKNOWN before any CONFLICT.
        active.append((record, _standing(derived, record)))

    for ref in use["declared_basis_refs"]:
        if ref not in derived["records"]:
            raise _Unknown("a declared basis reference is unresolved")

    if target_conflict:
        raise _Conflict(
            "an effective lifecycle record targets a record of the wrong kind"
        )

    qualifying = [
        record for record, standing in active if _qualifies(record, standing, use)
    ]
    if len(qualifying) > 1:
        raise _Conflict("more than one qualifying acceptance")
    if len(qualifying) == 1:
        ref = qualifying[0]["declaration_version_ref"]
        if ref in use["declared_basis_refs"]:
            return "APPLICABLE", ref
    return "INAPPLICABLE", None


MAX_SNAPSHOT_AGE_SECONDS = POLICY["max_snapshot_age_seconds"]


def _snapshot_fresh(derived, use):
    """The snapshot horizon reaches the use time (T-7/T-16).

    Age is ``occurred_at`` minus ``captured_at``.  An age at most the decoded
    evaluation policy's ``max_snapshot_age_seconds`` passes, equality
    included; a greater age is UNKNOWN.  ``r_semantics.derivation`` has
    already required the capture to precede the use strictly.
    """
    age = _epoch(use["occurred_at"]) - _epoch(derived["ledger"]["captured_at"])
    return 0 <= age <= MAX_SNAPSHOT_AGE_SECONDS


_DAYS_BEFORE_MONTH = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)


def _epoch(text):
    """Seconds since 1970-01-01T00:00:00Z for an RFC3339 UTC fixed-seconds instant."""
    year, month, day, hour, minute, second = _instant(text)
    days = 365 * (year - 1970) + (year - 1969) // 4 - (year - 1901) // 100
    days += (year - 1601) // 400
    days += _DAYS_BEFORE_MONTH[month - 1]
    if month > 2 and (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        days += 1
    days += day - 1
    return ((days * 24 + hour) * 60 + minute) * 60 + second


def _lifecycle_targets(derived, use):
    """Removed acceptance targets, and whether an effective wrong-kind target exists.

    Every lifecycle record's target is resolved whether or not the record is
    yet effective; an unresolved target is UNKNOWN (T-13/T-14).  An effective
    record removes an acceptance target, or marks a conflict when its resolved
    target is any other converted record, itself included.  A replacement
    removes its target regardless of the replacement's own validity; the
    replacement qualifies, or not, on its own as a listed acceptance.
    """
    killed = set()
    conflict = False
    for record in derived["events"]:
        if record["declaration_kind"] not in (REVOCATION_KIND, SUPERSESSION_KIND):
            continue
        target_ref = record.get("target_declaration_version_ref")
        target = derived["records"].get(target_ref)
        if target is None:
            raise _Unknown("a lifecycle target reference is unresolved")
        effective = record.get("effective_at")
        if effective is None or not _at_or_before(effective, use["occurred_at"]):
            continue
        if target["declaration_kind"] in ACCEPTANCE_KINDS:
            killed.add(target_ref)
        else:
            conflict = True
    return killed, conflict


def _standing(derived, record):
    """Resolve an acceptance's standing objects, or raise ``_Unknown``.

    Returns ``(grant, named_root, grant_root)``.  Delegated standing: the
    basis resolves to a converted delegation grant by declaration reference
    only, the named mandate resolves, and the grant's own root was resolved
    at derivation.  Direct standing: the basis resolves to a mandate record
    and the named mandate resolves; ``grant`` and ``grant_root`` are ``None``.
    A basis resolving to any other converted record, to nothing, or to a
    grant by its ``grant_id`` is unresolved standing (UNKNOWN).
    """
    basis = record.get("standing_basis_ref")
    grant = derived["grants"].get(basis)
    if grant is None and basis not in derived["roots"]:
        raise _Unknown("an acceptance standing basis is unresolved")
    named = derived["roots"].get(record.get("mandate_version_ref"))
    if named is None:
        raise _Unknown("the named root mandate is unresolved")
    if grant is None:
        return None, named, None
    return grant, named, derived["roots"][grant["standing_basis_ref"]]


def _qualifies(record, standing, use):
    """Use match, issue edge and interval, then the full one-hop or direct match.

    Every object here is resolved; a mismatching field is nonqualifying,
    never UNKNOWN.  Delegated standing matches (1) the grant, (2) the named
    root mandate and (3) the grant's own root; direct standing requires the
    basis and the named mandate to be the same record, matched on (2).
    """
    at = use["occurred_at"]
    if record["receiver_capability_id"] != use["receiver_capability_id"]:
        return False
    if record["episode_id"] != use["episode_id"]:
        return False
    if record["exact_claim_version_id"] != use["exact_claim_version_id"]:
        return False
    if record["purpose_id"] != use["purpose_id"]:
        return False
    if record["scope_id"] != use["scope_id"]:
        return False
    if not _at_or_before(record["recorded_at"], at):
        return False
    if not _covers(record["interval"], at):
        return False

    grant, named, grant_root = standing
    if grant is None:
        if record.get("standing_basis_ref") != named["mandate_version_ref"]:
            return False
    else:
        # (1) the referenced grant
        if grant["purpose_id"] != record["purpose_id"]:
            return False
        if grant["scope_id"] != record["scope_id"]:
            return False
        if grant["policy_ref"] != record["policy_ref"]:
            return False
        if not _covers(grant["interval"], at):
            return False
        if grant.get("delegate_capability_id") != record["issuer_capability_id"]:
            return False
        # (3) the grant's own root mandate
        if DELEGATION_KIND not in grant_root["permitted_record_kinds"]:
            return False
        if grant_root["subject_capability_id"] != grant.get("issuer_capability_id"):
            return False

    # (2) the named root mandate
    if record["declaration_kind"] not in named["permitted_record_kinds"]:
        return False
    if record["purpose_id"] not in named["purpose_ids"]:
        return False
    if record["scope_id"] not in named["scope_ids"]:
        return False
    if named["policy_ref"] != record["policy_ref"]:
        return False
    if not _covers(named["interval"], at):
        return False
    if named["subject_capability_id"] != record["issuer_capability_id"]:
        return False
    return True


def _covers(interval, instant):
    return _at_or_before(interval["effective_from"], instant) and _at_or_before(
        instant, interval["effective_until"]
    )


# -- the arm ------------------------------------------------------------------


def _evaluate(canonical_common_value, canonical_module_state_value):
    del canonical_module_state_value  # STATE_R carries only its format
    try:
        derived = _derive(canonical_common_value["a2_raw_shared_bundle"])
    except (_DerivationUnresolved, KeyError, IndexError, TypeError, ValueError):
        return "R_DERIVATION_UNRESOLVED", None

    engine_class, engine_output_sha256 = _engine_class(canonical_common_value)
    if engine_class == "CONCLUSIVE":
        return "R_ENGINE_CONCLUSIVE", None
    if engine_class != "VALID":
        return "R_ENGINE_UNRESOLVED", None

    lineage = _lineage(canonical_common_value)
    if lineage == "UNRESOLVED":
        return "R_LINEAGE_UNRESOLVED", None
    if lineage == "CONCLUSIVE":
        return "R_LINEAGE_CONCLUSIVE", None

    try:
        acceptance_class, selected = _acceptance(derived)
    except _Unknown:
        acceptance_class, selected = "UNKNOWN", None
    except _Conflict:
        acceptance_class, selected = "CONFLICT", None
    except (KeyError, IndexError, TypeError, ValueError):
        return "R_DERIVATION_UNRESOLVED", None

    evidence = {
        "acceptance_class": acceptance_class,
        "engine_class": "VALID",
        "engine_output_sha256": engine_output_sha256,
        "lineage_class": "COMPLETE",
        "recorded_use_sha256": derived["recorded_use_sha256"],
        "selected_issuance_id": selected,
    }
    return "R_ACCEPTANCE_" + acceptance_class, evidence


_SEMANTICS = seam.Semantics(ENTRYPOINT, _evaluate)


def decide(canonical_common_bytes: bytes, canonical_module_state_bytes: bytes) -> bytes:
    """The production entrypoint DECIDE_R."""
    return seam.decide(
        _SEMANTICS, canonical_common_bytes, canonical_module_state_bytes
    )


decide_r = decide

_ = decision
