"""Authority-first benign functional cases; neither candidate runtime was read.

Reviewer: Larch, /root/rr_full_treatment_fidelity, 2026-09-05.
Specification: study/2026-1/full-treatment/TREATMENT_SPEC.md
SHA256: EA256B8CF20044005936C5127546AEE9A5EEB7B4470B39261D642DEF2298C467
Read also: the supplied control/assembly sources, frozen treatment-v6 authority,
its pinned A2 schema, and the source-derived OBL26_CLASS_TABLE.md. No candidate
decision source, result, oracle, or decision comparison informed expectations.

Use case_factories(): every zero-argument factory returns
    (name, freshly assembled COMMON dict, expected R code, normative reason).
Use cases() to materialize the finite list. No runtime import or comparison.
The clean NFC case additionally has U/S4/S1 expectations in ARM_EXPECTATIONS.

Limits: dict-valued cases cannot represent malformed/noncanonical raw JSON,
wire UTF-8 faults, duplicate JSON keys, absent state arguments or mixed
syntax/structural-limit precedence. Those require a separately typed byte ABI
test set; they are not falsely counted here. These are logical conformance
records, not admitted study-population members or authenticated observations.
The 60-case cap leaves some individual legacy lineage/engine disjuncts to the
existing baseline tests. All R decision stages and the new relational rules
have focused coverage, not an assertion of exhaustive conformance.

Specification note: the inherited A2 D010 schema already rejects repeated
included_record_refs via uniqueItems. Under the expressly retained stage order,
this gives CLOSED_SCHEMA/FIELD_VALUE before derivation. The specification's
derivation-repeat sentence describes an unreachable later guard; the relevant
case preserves earlier admission. D020's mandate policy is a fixed constant,
so policy matching is tested via acceptance/grant fields, never an invalid
mandate-policy substitution disguised as an acceptance-stage case.

No irreducible ambiguity is assigned an invented oracle. Unresolved standing
on an inactive or independently nonmatching acceptance is deliberately omitted:
the exact population over which the all-UNKNOWN scan applies warrants a more
explicit sentence before using such an interaction as a normative oracle.
"""

from copy import deepcopy
from functools import partial
import json

from rr_full_treatment.test_host_facts import control
from rr_full_treatment.host_facts import assemble


SPEC_SHA256 = "EA256B8CF20044005936C5127546AEE9A5EEB7B4470B39261D642DEF2298C467"
APPLICABLE = "R_ACCEPTANCE_APPLICABLE"
INAPPLICABLE = "R_ACCEPTANCE_INAPPLICABLE"
UNKNOWN = "R_ACCEPTANCE_UNKNOWN"
CONFLICT = "R_ACCEPTANCE_CONFLICT"
DERIVATION = "R_DERIVATION_UNRESOLVED"
ENGINE_CONCLUSIVE = "R_ENGINE_CONCLUSIVE"
ENGINE_UNRESOLVED = "R_ENGINE_UNRESOLVED"
LINEAGE_CONCLUSIVE = "R_LINEAGE_CONCLUSIVE"
LINEAGE_UNRESOLVED = "R_LINEAGE_UNRESOLVED"
USE_AT = "2026-09-05T12:00:01Z"
BEFORE_USE = "2026-09-05T12:00:00Z"
AFTER_USE = "2026-09-05T12:00:02Z"
OTHER_CAP = "CAP_OTHER"

ARM_EXPECTATIONS = {
    "nfc_clean": {
        "U": "U_TRANSPARENT", "S4": "S_THRESHOLD_CLEAR",
        "S1": "S_THRESHOLD_CLEAR", "R": APPLICABLE,
    }
}


def _raw(document):
    return document["a2_raw_shared_bundle"]


def _use(document):
    return _raw(document)["use_records"][0]


def _ledger(document):
    return _raw(document)["ledger_observations"][0]


def _closure(document):
    return _raw(document)["closure_attestations"][0]


def _acceptance(document):
    return next(row for row in _raw(document)["declaration_records"]
                if row["declaration_version_ref"] == "DECL_USE")


def _grant(document):
    return next(row for row in _raw(document)["declaration_records"]
                if row["declaration_kind"] == "DELEGATION_DECLARED")


def _mandate(document):
    ref = _acceptance(document)["mandate_version_ref"]
    return next(row for row in _raw(document)["domain_mandate_records"]
                if row["mandate_version_ref"] == ref)


def _grant_root(document):
    ref = _grant(document)["standing_basis_ref"]
    return next(row for row in _raw(document)["domain_mandate_records"]
                if row["mandate_version_ref"] == ref)


def _set(accessor, member, value):
    def edit(document):
        accessor(document)[member] = deepcopy(value)
    return edit


def _both(*edits):
    def edit(document):
        for apply in edits:
            apply(document)
    return edit


def _facts(document):
    return document["comparison_facts"]


def _guard(document):
    return document["guard_observation_facts"]


def _append(document, row, *, listed=True):
    _raw(document)["declaration_records"].append(deepcopy(row))
    if listed:
        _ledger(document)["included_record_refs"].append(row["declaration_version_ref"])
        _ledger(document)["committed_frontier"] += 1
        _closure(document)["committed_frontier"] += 1


def _two_acceptances(document):
    row = deepcopy(_acceptance(document))
    row["declaration_version_ref"] = "DECL_SECOND"
    _append(document, row)
    # Only DECL_USE is listed as a use basis. Both records still qualify.


def _lifecycle(document, *, target="DECL_USE", at=USE_AT,
               replacement=None, event="DECL_EVENT"):
    row = deepcopy(_acceptance(document))
    row.update(declaration_version_ref=event,
               declaration_kind="DECLARATION_WITHDRAWN" if replacement is None
               else "DECLARATION_REPLACED",
               target_declaration_family="ADOPTION_OR_INTENDED_USE",
               target_declaration_version_ref=target, effective_at=at)
    if replacement is not None:
        row["replacement_declaration_version_ref"] = replacement
    _append(document, row)


def _duplicate_grant(document):
    row = deepcopy(_grant(document))
    row["declaration_version_ref"] = "DECL_SECOND_GRANT"
    _append(document, row)


def _unlisted_bad_grant(document):
    row = deepcopy(_grant(document))
    row.update(declaration_version_ref="DECL_UNLISTED_GRANT",
               standing_basis_ref="STANDING_" + "F" * 24)
    # Same grant_id as the live grant, but outside the conversion domain.
    _append(document, row, listed=False)


def _mandate_declaration_collision(document):
    row = deepcopy(_acceptance(document))
    row["declaration_version_ref"] = _mandate(document)["mandate_version_ref"]
    _append(document, row)


def _mandate_grant_collision(document):
    _grant(document)["grant_id"] = _mandate(document)["mandate_version_ref"]


def _duplicate_declaration(document):
    # One ledger ref resolves to two converted rows; no repeated ledger item.
    _append(document, _acceptance(document), listed=False)


def _duplicate_mandate(document):
    _raw(document)["domain_mandate_records"].append(deepcopy(_mandate(document)))


def _wrong_kind_root_before_unknown(document):
    _grant(document)["standing_basis_ref"] = "DECL_USE"
    _lifecycle(document, target="DECL_MISSING", at=AFTER_USE)


def _repeated_ledger_reference(document):
    _ledger(document)["included_record_refs"].append("DECL_USE")
    _ledger(document)["committed_frontier"] += 1
    _closure(document)["committed_frontier"] += 1


def _inclusive_intervals(document):
    _facts(document).update(valid_from_ns=1001, use_time_ns=1001, valid_until_ns=1001)
    # All use-time interval edges equal use. Snapshot still strictly precedes use.
    for row in [*_raw(document)["declaration_records"],
                *_raw(document)["domain_mandate_records"]]:
        row["interval"] = {"effective_from": USE_AT, "effective_until": USE_AT}


def _distinct_direct_roots(document):
    other = deepcopy(_mandate(document))
    other["mandate_version_ref"] = "STANDING_" + "B" * 24
    _raw(document)["domain_mandate_records"].append(other)
    _acceptance(document)["mandate_version_ref"] = other["mandate_version_ref"]
    # The standing basis remains the original, field-identical mandate.


def _delegated_named_policy(document):
    _acceptance(document)["policy_ref"] = "POLICY_OTHER"
    _grant(document)["policy_ref"] = "POLICY_OTHER"
    # Grant matches acceptance, but the named mandate retains its required policy.


def _mandate_lifecycle_target(document):
    _lifecycle(document, target=_mandate(document)["mandate_version_ref"])


def _replacement(document, *, listed):
    row = deepcopy(_acceptance(document))
    row["declaration_version_ref"] = "DECL_REPLACEMENT"
    _append(document, row)
    _lifecycle(document, replacement="DECL_REPLACEMENT")
    if listed:
        _use(document)["declared_basis_refs"] = ["DECL_REPLACEMENT"]


def _wrong_kind_replacement(document):
    _lifecycle(document, replacement="DECL_EVENT")


def _self_conflict(document):
    _lifecycle(document, target="DECL_EVENT")


def _wrong_kind_standing_before_conflict(document):
    _self_conflict(document)
    _acceptance(document)["standing_basis_ref"] = "DECL_EVENT"


def _mandate_basis_before_conflict(document):
    _self_conflict(document)
    _use(document)["declared_basis_refs"] = [_mandate(document)["mandate_version_ref"]]


_DEFINITIONS = []


def _add(name, code, reason, edit=None, *, delegated=False, answer=7):
    _DEFINITIONS.append((name, code, reason, edit, delegated, answer))


# Controls, including a genuine NFC payload reaching both comparator adapters.
_add("direct_clean", APPLICABLE, "Direct standing equals the named mandate; exact listed use qualifies.")
_add("one_hop_distinct_roots", APPLICABLE,
     "All three one-hop objects match; grant root may differ from acceptance's named root.", delegated=True)
_add("nfc_clean", APPLICABLE,
     "NFC UTF-8 content is admitted; truth of the illustrative answer is not an R predicate.", answer="caf\u00e9")
_add("expected_parent_form", "FIELD_VALUE",
     "Expected parent requires all 64 uppercase digest digits; shared schema runs before R.",
     _set(_facts, "expected_direct_parents", ["PARENT_" + "A" * 24]))
_add("non_nfc_text", "NFC", "Inherited VALUE_UNICODE/NFC precedes closed schema and R.",
     lambda d: d["task_instruction_constraints"].update(instruction="cafe\u0301"))

# Derivation identities and conversion scope. None relies on a runtime verdict.
_add("snapshot_equal_use", DERIVATION, "Capture must be strictly before use, not equal.",
     _set(_ledger, "captured_at", USE_AT))
_add("listed_duplicate_grant", DERIVATION, "Two converted grants cannot share grant_id.",
     _duplicate_grant, delegated=True)
_add("unlisted_duplicate_and_unresolved_root_ignored", APPLICABLE,
     "Schema-valid unlisted declaration is excluded from both identity and root checks.",
     _unlisted_bad_grant, delegated=True)
_add("mandate_declaration_namespace_collision", DERIVATION,
     "A mandate ref colliding with a converted declaration ref is an explicit derivation failure.",
     _mandate_declaration_collision)
_add("mandate_grant_namespace_collision", DERIVATION,
     "A mandate ref colliding with a converted grant_id is an explicit derivation failure.",
     _mandate_grant_collision, delegated=True)
_add("two_converted_declaration_rows_one_reference", DERIVATION,
     "Duplicate converted declaration refs fail even when the ledger lists that ref just once.",
     _duplicate_declaration)
_add("duplicate_mandate_reference", DERIVATION, "All mandate records participate in identity checks.",
     _duplicate_mandate)
_add("grant_wrong_kind_root_precedes_unknown", DERIVATION,
     "A grant resting on an acceptance is rejected at derivation before an unresolved lifecycle target.",
     _wrong_kind_root_before_unknown, delegated=True)
_add("repeated_ledger_ref_schema_precedes_derivation", "FIELD_VALUE",
     "Inherited A2 D010 uniqueItems fails at shared admission before the later duplicate-ref guard.",
     _repeated_ledger_reference)

# Native OBL-26 first-match table and pipeline precedence.
_add("grant_expiry_equality", ENGINE_CONCLUSIVE,
     "OBL-26 is half-open: invocation equal to expiry is MALFORMED_OR_BOUNDARY.",
     _set(_guard, "invocation_time", 2000))
_add("grant_lower_equality_no_added_chronology", APPLICABLE,
     "Lower grant edge is inclusive; a present later check timestamp adds no R chronology rule.",
     _both(_set(_guard, "invocation_time", 0), _set(_guard, "revocation_checked_at", 1001)))
_add("missing_revocation_check_native_binding_class", ENGINE_CONCLUSIVE,
     "Null revocation_checked_at is native ANY_ABSENT/BINDING_OR_CONFLICT, not omission UNKNOWN.",
     _set(_guard, "revocation_checked_at", None))
_add("consumed_guard_before_incomplete_lineage", ENGINE_UNRESOLVED,
     "Native CONSUMED is OMISSION_OR_INCOMPLETE and stops before lineage finalization.",
     _both(_set(_guard, "consumption_state", "CONSUMED"), _set(_facts, "origin_finalized", False)))

# Retained lineage runs before any acceptance disposition.
_add("origin_not_finalized_before_acceptance_conflict", LINEAGE_UNRESOLVED,
     "Incomplete origin stops before multiple-qualifying acceptance conflict.",
     _both(_two_acceptances, _set(_facts, "origin_finalized", False)))
_add("observed_parent_mismatch_before_acceptance_unknown", LINEAGE_CONCLUSIVE,
     "Observed identifiers are not coerced; valid expected/full versus ordinary observed id is lineage mismatch.",
     _both(_set(_facts, "observed_direct_parents", ["OBSERVED_PARENT"]),
           _set(_use, "declared_basis_refs", ["DECL_MISSING"])))
_add("all_inclusive_use_interval_equalities", APPLICABLE,
     "Lineage, acceptance, named mandate and delegated grant interval endpoints contain use inclusively.",
     _inclusive_intervals, delegated=True)

# Distinct clocks and exact acceptance horizons.
_add("snapshot_age_exactly_60", APPLICABLE, "The decoded 60-second maximum age includes equality.",
     _set(_ledger, "captured_at", "2026-09-05T11:59:01Z"))
_add("snapshot_age_61_before_conflict", UNKNOWN,
     "Age 61 fails the horizon and UNKNOWN precedes multiple-qualifying conflict.",
     _both(_two_acceptances, _set(_ledger, "captured_at", "2026-09-05T11:59:00Z")))
_add("acceptance_recorded_at_use", APPLICABLE, "Acceptance issue time equality qualifies.",
     _set(_acceptance, "recorded_at", USE_AT))
_add("acceptance_recorded_after_use", INAPPLICABLE, "A later acceptance issue time cannot qualify.",
     _set(_acceptance, "recorded_at", AFTER_USE))

# Each direct-mandate field independently matters, using only schema-valid data.
for _field, _value, _label in (
    ("permitted_record_kinds", ["INTENDED_USE_DECLARED"], "kind"),
    ("purpose_ids", ["PURPOSE_OTHER"], "purpose"),
    ("scope_ids", ["SCOPE_OTHER"], "scope"),
    ("interval", {"effective_from": "2026-09-05T11:00:00Z", "effective_until": BEFORE_USE}, "interval"),
    ("subject_capability_id", OTHER_CAP, "subject"),
):
    _add("direct_named_mandate_" + _label, INAPPLICABLE,
         "Direct standing clause (2) requires matching " + _label + "; resolution alone is insufficient.",
         _set(_mandate, _field, _value))
_add("direct_named_mandate_policy", INAPPLICABLE,
     "Acceptance policy must match the fixed named-mandate policy; the mandate itself stays schema-valid.",
     _set(_acceptance, "policy_ref", "POLICY_OTHER"))
_add("direct_field_equal_but_different_root", INAPPLICABLE,
     "Direct basis and named mandate must be the same record, not merely field-equal records.",
     _distinct_direct_roots)

# Exact declaration/use tuple is independent of correct standing.
for _field, _value, _label in (
    ("receiver_capability_id", OTHER_CAP, "receiver"),
    ("episode_id", "EP_OTHER", "episode"),
    ("exact_claim_version_id", "CLAIM_OTHER", "claim"),
    ("purpose_id", "PURPOSE_OTHER", "purpose"),
    ("scope_id", "SCOPE_OTHER", "scope"),
):
    _add("acceptance_use_" + _label, INAPPLICABLE,
         "Acceptance " + _label + " must equal the exact selected use.",
         _set(_acceptance, _field, _value))

# Complete one-hop match, isolating fields the former projections could omit.
for _field, _value, _label in (
    ("purpose_id", "PURPOSE_OTHER", "purpose"),
    ("scope_id", "SCOPE_OTHER", "scope"),
    ("policy_ref", "POLICY_OTHER", "policy"),
    ("interval", {"effective_from": "2026-09-05T11:00:00Z", "effective_until": BEFORE_USE}, "interval"),
    ("delegate_capability_id", OTHER_CAP, "delegate"),
):
    _add("one_hop_grant_" + _label, INAPPLICABLE,
         "Resolved grant with mismatching " + _label + " is nonqualifying, not unresolved standing.",
         _set(_grant, _field, _value), delegated=True)
_add("one_hop_named_mandate_policy", INAPPLICABLE,
     "Grant and acceptance agree, but the separate named mandate's policy also must match.",
     _delegated_named_policy, delegated=True)
_add("one_hop_named_mandate_subject", INAPPLICABLE,
     "The delegated acceptance's named mandate subject must match its issuer, independently of the grant.",
     _set(_mandate, "subject_capability_id", OTHER_CAP), delegated=True)
_add("one_hop_grant_root_permission", INAPPLICABLE,
     "A resolved grant root must permit DELEGATION_DECLARED; root resolution alone is insufficient.",
     _set(_grant_root, "permitted_record_kinds", ["ADOPTION_DECLARED"]), delegated=True)
_add("one_hop_grant_root_issuer", INAPPLICABLE,
     "The grant-root subject must equal the grant issuer, not merely the acceptance issuer.",
     _set(_grant_root, "subject_capability_id", OTHER_CAP), delegated=True)

# Effective-time reduction, reference namespaces and explicit replacement listing.
_add("withdrawal_effective_at_use", INAPPLICABLE,
     "Lifecycle equality is effective and removes the sole listed acceptance.", _lifecycle)
_add("withdrawal_effective_after_use", APPLICABLE,
     "A resolvable future lifecycle event does not yet remove its target.",
     partial(_lifecycle, at=AFTER_USE))
_add("future_unresolved_target_before_conflict", UNKNOWN,
     "Target resolution occurs even before effect time; UNKNOWN precedes multiple qualifying acceptances.",
     _both(_two_acceptances, partial(_lifecycle, target="DECL_MISSING", at=AFTER_USE)))
_add("mandate_is_not_lifecycle_target", UNKNOWN,
     "Lifecycle targets resolve only in converted declarations; a mandate ref is unresolved, not wrong-kind conflict.",
     _mandate_lifecycle_target)
_add("replacement_not_listed", INAPPLICABLE,
     "New acceptance may qualify, but cannot inherit the removed acceptance's declared-basis membership.",
     partial(_replacement, listed=False))
_add("replacement_explicitly_listed", APPLICABLE,
     "Effective replacement removes the old acceptance; the new sole qualifying acceptance is explicitly listed.",
     partial(_replacement, listed=True))
_add("wrong_kind_replacement_does_not_restore", INAPPLICABLE,
     "A replacement ref naming the lifecycle event cannot restore the removed acceptance.",
     _wrong_kind_replacement)
_add("effective_self_target_conflict", CONFLICT,
     "An effective lifecycle event targeting itself resolves to a non-acceptance declaration and conflicts.",
     _self_conflict)
_add("wrong_kind_standing_before_target_conflict", UNKNOWN,
     "An acceptance basis resolving to a lifecycle declaration is unresolved standing; UNKNOWN precedes self-target conflict.",
     _wrong_kind_standing_before_conflict)
_add("two_qualifying_only_one_listed", CONFLICT,
     "Multiple qualifying acceptances conflict even if only one is a listed use basis.", _two_acceptances)
_add("mandate_basis_unknown_before_target_conflict", UNKNOWN,
     "Declared bases resolve only in converted declarations; mandate-as-basis UNKNOWN precedes self-target conflict.",
     _mandate_basis_before_conflict)
_add("source_extent_unknown_before_conflict", UNKNOWN,
     "Exact source extent is required; missing SOURCE_MANDATE precedes multiple-qualifying conflict.",
     _both(_two_acceptances, _set(_closure, "source_extent", ["SOURCE_PRIMARY"])))
_add("record_classes_unknown_before_conflict", UNKNOWN,
     "The exact required record-class set is required before conflict classification.",
     _both(_two_acceptances, _set(_closure, "closed_record_classes",
           ["CLAIM_VERSION", "DECLARATION_RECORD", "USE_RECORD"])))
_add("closure_horizon_unknown_before_conflict", UNKNOWN,
     "Closure ending before use makes the horizon UNKNOWN before multiple-qualifying conflict; clean control covers equality.",
     _both(_two_acceptances, _set(_closure, "closed_through", BEFORE_USE)))

# Astra additions after the explicit scan-domain clarification. The original
# independently authored 60-case file remains byte-for-byte in the review record.
def _mismatching_unknown_standing(document):
    _two_acceptances(document)
    extra = deepcopy(_acceptance(document))
    extra.update(declaration_version_ref="DECL_NONMATCHING", episode_id="EP_OTHER",
                 standing_basis_ref="STANDING_MISSING")
    _append(document, extra)


def _removed_unknown_standing(document):
    _acceptance(document)["standing_basis_ref"] = "STANDING_MISSING"
    _lifecycle(document)


_add("nonmatching_active_standing_unknown_before_conflict", UNKNOWN,
     "The declared scan covers all active acceptances even with another nonmatching field.",
     _mismatching_unknown_standing)
_add("removed_standing_not_scanned", INAPPLICABLE,
     "An effectively removed acceptance's standing does not create an UNKNOWN condition.",
     _removed_unknown_standing)


def _materialize(definition):
    name, code, reason, edit, delegated, answer = definition
    artifact, use, inputs = control(delegated=delegated, answer=answer)
    document = json.loads(assemble(artifact, use, **inputs))
    if edit is not None:
        edit(document)
    return name, document, code, reason


def case_factories():
    """Return 60 independent no-argument factories; no decision module is called."""
    assert len(_DEFINITIONS) == 62, len(_DEFINITIONS)
    assert len({item[0] for item in _DEFINITIONS}) == len(_DEFINITIONS)
    return tuple(partial(_materialize, definition) for definition in _DEFINITIONS)


def cases():
    return [factory() for factory in case_factories()]


if __name__ == "__main__":
    generated = cases()
    # Construction-only check. Serializing does not validate schema or semantics.
    for name, document, expected_code, reason in generated:
        json.dumps(document, ensure_ascii=False, allow_nan=False)
        assert all(isinstance(value, str) and value for value in (name, expected_code, reason))
    print(json.dumps({"spec_sha256": SPEC_SHA256, "cases_constructed": len(generated),
                      "runtime_comparisons": 0}, sort_keys=True))
