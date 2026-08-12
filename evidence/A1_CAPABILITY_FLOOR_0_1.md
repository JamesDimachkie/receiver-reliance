# Gate 0 Capability Floor Specification 0.1

Status: `DRAFT_GATE_0_SPEC_ONLY`; implementation-independent capability
specification, candidate-blind obligation matrix, and manifest template; no
capability is sealed and no comparison is authorized  
Artifact ID: `EH-G0-A1-CAPABILITY-FLOOR-0.1`

This artifact is subordinate to:

- Foundation 0.4, SHA-256
  `CAFEA3889A9E0BB29117B79766C65BF96706A76A1B84C6484B14EE6ADA247138`;
- Foundation 0.4.1, SHA-256
  `453AAD8C4D1864A5AA2974EEC0EA2B8D47D96DD44F1EB43473AFC5E06A5067A2`;
- Foundation 0.4.2, SHA-256
  `966676E8055DCA531B327325E45813B8C6D315F2ACB38D8BD4E100E5D1DA1343`;
  and
- the evidence-only collision-map snapshot, SHA-256
  `18EAEA765FC510AD27F42642739FBAE3BDB64E9CCAB215AD797EE99DF57BB902`.

The independent Fable review, SHA-256
`48CB2DA33D5925A9B53108D09DEB29D5EAA7CCBEDACA9B1D4E92492606455D4F`,
is admission evidence, not specification authority.

## Bundle references

| Artifact | Path | SHA-256 |
|---|---|---|
| A2 shared vocabulary | `A2_SHARED_DOMAIN_VOCABULARY_0_1.schema.json` | `68E47F5627EC3BD9BC2B72155C32658A616890105DE28900D47864364B1154D3` |
| A2 treatment proposal | `A2_TREATMENT_EVENT_FAMILY_0_1.schema.json` | `4D8DC723780841A978D07A4CE766B40B50B55755307BD3A36DF3AA22962AAB47` |
| A3 parity manifest | `A3_INFORMATION_PARITY_0_1.json` | `4BBDE415CDDDE313E8AC9D385E784C0CCD1A8768D2E1D9B120A7D16D06753581` |
| A4 sanitized brief | `A4_WORLD_ORACLE_AUTHOR_BRIEF_0_1.md` | `D42B26C0CF11EEC082F2E27B2EE2843D41688B96539E933F5475B82132B8F3F8` |
| A4 access boundary | `A4_AUTHOR_ACCESS_BOUNDARY_0_1.json` | `80957486B6BF3A1AA2056F3B5F3098689F7B2C4C1190B73D1092FA9D951103A1` |
| A5 raw/capability fixtures | `A5_RAW_WORLD_CAPABILITY_FIXTURES_0_1.json` | `C9914580602AF61656EA8510ECF3150AEC4BD42EEECF2174A17E2BB4E28263B1` |
| A5 treatment overlays | `A5_TREATMENT_OVERLAY_FIXTURES_0_1.json` | `8DC2F39890C8526A2AB09E3CC65C871B76CE9FC93CDB3188D2F3AB53516CBC47` |
| A6 current status | `A6_UNSEALED_CAPABILITIES_0_1.json` | derived downstream; A6 pins this file after finalization |

The parked `benchmark/` and `interpretation-integrity/` trees are not imported,
extended, or treated as Gate 0 evidence.

## Candidate-blind enumeration receipt

The obligation enumeration was authored in fresh context
`/root/comparator_blind_author` from one inline sanitized packet containing the
shared baseline requirements plus neutral source claims and limits S01-S31.
The lane received no prior conversation, was instructed not to inspect files or
tools, and made no observed tool or filesystem call. Its prior treatment
exposure at dispatch was recorded as none. The integration root was already
treatment-exposed and only normalized IDs, reconciled source coverage, and
added conservative omissions; it later added the required neutral raw policy
identity field under the explicit quarantined-development transform receipt in
A5. Neither integration step restores candidate neutrality, and no
blind-authored obligation was deleted.

A separate fresh-context completeness reviewer received only the neutral
matrix. Its first pass returned `REVISE`, identifying continuous authorization,
origin-bound propagation, receipt-gated handoff acceptance, and fixture-class
ambiguity. After OBL-10 was narrowed, OBL-25 through OBL-27 were added, and the
four fixture classes were separated from their coverage modalities, the same
  reviewer returned `ACCEPT` for that 27-row blind-authored matrix. OBL-28 was
  later added conservatively by the treatment-exposed integration root after an
  independent collision-coverage attack found the omitted trusted-render-to-effect
  capability. A later fresh-context bounded novelty scout added EP-AEG, APS, and
  `verification.*` source rows S33-S35, strengthened the EP-AEC row S28, and
  then admitted the JEP -06 plus Semantic Interoperability -00 family as S36,
  Agent Governance Vocabulary v0.1.0 as S37, and TSTO/00 plus its JEP binding
  as S38; the
  treatment-exposed integration root mapped those capabilities onto existing
  obligations without claiming completeness or adding a new obligation. The
  earlier completeness receipt therefore does **not** accept the current 28-row
  draft or its expanded source coverage; a new candidate-blind completeness
  review remains `UNSEALED`. No blind-authored obligation was deleted, and no row
  is frozen, implemented, tested, or sealed.

This is a recorded context-isolation process, not proof of OS-enforced access
denial or a complete world model. A fresh candidate-blind completeness review
must accept the frozen matrix before any capability may seal. Later candidate-
aware gap analysis is a separate role and cannot rewrite the obligation set.

## Source-coverage ledger

Every row in the pinned collision map has exactly one disposition. `INCLUDED`
means the source-described capability contributes to one or more neutral obligations;
it does not mean an implementation exists. `DIAGNOSTIC_ONLY` supplies test or
validity cases but cannot satisfy a B1 row. `EXCLUDED_WITH_TRANSFER_LIMIT`
requires the stated bounded reason. `QUARANTINED` contributes nothing.

| ID | Registry source | Locator | Disposition | Obligation or bounded reason |
|---|---|---:|---|---|
| S01 | UCON | map:35 | INCLUDED | OBL-09, OBL-10, OBL-13, OBL-17 |
| S02 | ODRL 2.2 | map:36 | INCLUDED | OBL-01, OBL-09, OBL-10 |
| S03 | Contextual Integrity | map:37 | INCLUDED | OBL-01, OBL-03, OBL-12 |
| S04 | Data Use Ontology | map:38 | EXCLUDED_WITH_TRANSFER_LIMIT | Domain-specific secondary-use vocabulary adds no distinct generic obligation beyond OBL-01/09/12; it supplies no proof or handoff meaning. |
| S05 | Evidence networks | map:39 | INCLUDED | OBL-05, OBL-06, OBL-14, OBL-15 |
| S06 | Argumentation systems | map:40 | INCLUDED | OBL-06, OBL-09, OBL-18 |
| S07 | Social commitments | map:41 | INCLUDED | OBL-03, OBL-09, OBL-16, OBL-17 |
| S08 | Pact | map:42 | INCLUDED | OBL-01, OBL-02, OBL-21 |
| S09 | Citation distortion study | map:43 | DIAGNOSTIC_ONLY | Amplification cases for OBL-23; no prevalence or intervention inference. |
| S10 | MAST | map:44 | DIAGNOSTIC_ONLY | Failure-taxonomy and coverage patterns for OBL-24 only. |
| S11 | CheckList | map:45 | INCLUDED | OBL-21, OBL-24 testing method only; no domain semantics or gold. |
| S12 | AgentDojo | map:46 | DIAGNOSTIC_ONLY | Adversarial and utility controls for OBL-12/22/24. |
| S13 | AgentCIBench | map:47 | DIAGNOSTIC_ONLY | Executable contextual-flow cases for OBL-12/24 only. |
| S14 | Semantic Laundering preprint | map:48 | DIAGNOSTIC_ONLY | Prior-art/nonclaim terminology and transport-versus-warrant laundering cases for OBL-23 only; formal, inevitability, and outcome claims remain unaccepted. |
| S15 | Benchmark construct-validity review | map:49 | DIAGNOSTIC_ONLY | Construct-validity checks for OBL-24. |
| S16 | ToolEmu | map:50 | DIAGNOSTIC_ONLY | Emulation and human-validation patterns for OBL-24 only; no precision transfer. |
| S17 | LegalRuleML/Carneades | map:51 | INCLUDED | OBL-01, OBL-06, OBL-09, OBL-18; no legal-validity inference. |
| S18 | MemTX | map:62 | INCLUDED | OBL-02/03/04/07/09/11/13/14/15/18/19/20/24; paper-described capability only. |
| S19 | AuthMem-Bench | map:63 | INCLUDED | OBL-05, OBL-06, OBL-07, OBL-23, OBL-24. |
| S20 | PPMF | map:64 | INCLUDED | OBL-04/05/07/08/10/11/22/23/25. |
| S21 | TMA-NM | map:65 | INCLUDED | OBL-02, OBL-08, OBL-10, OBL-19, OBL-25, OBL-26; catalog repetition is not reproduction. |
| S22 | Context-to-Execution Integrity | map:66 | INCLUDED | OBL-02, OBL-08, OBL-11, OBL-20. |
| S23 | AIRGuard | map:67 | INCLUDED | OBL-07, OBL-08, OBL-09, OBL-10, OBL-11, OBL-12, OBL-19, OBL-20, OBL-22, OBL-23. |
| S24 | PCAA | map:68 | INCLUDED | OBL-08, OBL-09, OBL-19, OBL-20, OBL-26; executable fidelity remains unestablished. |
| S25 | Consent Integrity | map:69 | INCLUDED | OBL-08, OBL-20, OBL-26, OBL-28; total-mediation and burden assumptions remain explicit. |
| S26 | AGM | map:70 | INCLUDED | OBL-05, OBL-07, OBL-16, OBL-17, OBL-18, OBL-27. |
| S27 | Scientific-RAM | map:71 | INCLUDED | OBL-05, OBL-06, OBL-16, OBL-17, OBL-18, OBL-27. |
| S28 | EP-AEC -05 (EMILIA) | map:72 | INCLUDED | OBL-07, OBL-08, OBL-10, OBL-11, OBL-18, OBL-19, OBL-20, OBL-22, OBL-23, OBL-25, OBL-26; draft capability only, separate local authorization remains required. |
| S29 | Sanna Governance Envelopes | map:73 | INCLUDED | OBL-08, OBL-16, OBL-19, OBL-27 remain UNSEALED until proposed, accepted, committed, executed, shipped, and verified states plus their receipts are version-pinned and independently separated. |
| S32 | CROSS-MODEL-HANDOFF v1 | map:81-88 | QUARANTINED | No stable primary artifact; contributes no capability, schema, code, test, or term. |
| S33 | EP-AEG -00 | map:74 | INCLUDED | OBL-07, OBL-08, OBL-11, OBL-18, OBL-19, OBL-23, OBL-24; historical source-described capabilities are prior-art/nonclaim/test inputs only, and replaced status blocks current executable-baseline eligibility rather than capability admission. |
| S34 | APS -03 | map:75 | INCLUDED | OBL-02, OBL-08, OBL-09, OBL-10, OBL-11, OBL-17, OBL-19, OBL-20, OBL-22, OBL-23, OBL-25, OBL-26; recursive action authorization is not receiver claim adoption. |
| S35 | `verification.*` -01 | map:76 | INCLUDED | OBL-02, OBL-05, OBL-06, OBL-11, OBL-18, OBL-19, OBL-20, OBL-22; raw verdict, recommendation, and gate remain distinct signed fields before their normative `act`/`halt` mapping, which is neither receiver-issued adoption nor external action authorization. |
| S36 | JEP -06 + Semantic Interoperability -00 | map:77 | INCLUDED | OBL-02, OBL-03, OBL-07, OBL-09, OBL-12, OBL-17, OBL-18, OBL-19, OBL-22, OBL-23, OBL-24; signed immutable J/D/T/V events, actor/issuer/relying-party separation, bounded lifecycle carriers, ambiguity/loss and open-world closure declarations, plus support/truth/authorization non-inference are source-described draft capabilities. Profiles -00 is generic-encodability counterevidence, not another row; native JEP behavior belongs in B1 and only the receiver-local reducer remains a candidate treatment delta. No reviewed current JEP profile or TSTO binding supplies the exact receiver/episode/purpose/scope, non-transfer, depth-0 standing, lifecycle, four-state, closure-proof, and effect-bound conjunction. |
| S37 | Agent Governance Vocabulary v0.1.0 @ `0ce164984c038ac247eace4828ccf605ff716cfb` | map:78 | INCLUDED | OBL-01, OBL-09, OBL-21, OBL-23; canonical naming, descriptor dimensions, explicit exact/structural/partial/non-equivalent/no-mapping crosswalks, decision lineage, baseline revision, observation window, and measurement-versus-consumer-policy separation are prior-art/nonclaim inputs. Native crosswalk behavior belongs in B1; the forked open-review draft has no tag/release, its proposed JEP crosswalk targets obsolete draft-04, and its structure validator supplies no policy semantics or residual acceptance/effect machinery. |
| S38 | TSTO/00 + JEP-TSTO Binding/00 @ `c5a0de4f0e00835ee9355c9959d976f501c4f0c1` | map:79 | INCLUDED | OBL-02, OBL-03, OBL-07, OBL-09, OBL-17, OBL-18, OBL-22, OBL-23; immutable exact target identity/digest, evidence-backed baseline/target, versioned profile/policy, deterministic predicates, three-valued verification, and signer-issued JEP acceptance/delegation/termination are prior-art/nonclaim inputs. Native TSTO/JEP behavior belongs in B1; this untagged Experimental Draft is not a formal standard, its examples are unsigned, and it supplies neither the exact receiver-local acceptance conjunction nor atomic effect receipt. |

Foundation-only inputs not represented by their own collision-map row remain
explicit evidence gaps, never silent support:

| ID | Input | Use | Status |
|---|---|---|---|
| S30 | PROV/generic provenance | OBL-01/02/03/04/05/14/15 | UNSEALED: exact source claim and transfer-limit row missing from the pinned registry. |
| S31 | Ordinary typed diffs, version graphs, and generic policy evaluation | OBL-01/02/03/04/08/11/13/14/15/21/24 | UNSEALED: exact primary source and transfer-limit row missing. |

## Deduplicated mandatory obligations

Every row is mandatory for B1. Each fixture ID resolves in A5 and supplies the
required `INPUT_OUTPUT`, `INVARIANT`, `POLICY_PERMITTED_CONTROL`, and `FAILURE`
classes. The descriptions are implementation-independent.

| ID | Functional obligation | Source basis | Required fixtures |
|---|---|---|---|
| OBL-01 | Pin shared, versioned vocabulary for records, edges, purpose, scope, context, use, lifecycle, and decisions. | S02,S03,S08,S17,S30,S31,S37 | `CF-OBL-01-{IO,INV,CTRL,FAIL}` |
| OBL-02 | Give every record and material revision exact immutable identity; exact references never mean latest. | S08,S18,S21,S22,S30,S31,S34,S35,S36,S38 | `CF-OBL-02-{IO,INV,CTRL,FAIL}` |
| OBL-03 | Represent declarations of adoption/intended use with generic records and context/use/transition edges. | S03,S07,S18,S30,S31,S36,S38 | `CF-OBL-03-{IO,INV,CTRL,FAIL}` |
| OBL-04 | Record origin, custody, transformation, agents, activities, and derivation separately from truth or authority. | S18,S20,S30,S31 | `CF-OBL-04-{IO,INV,CTRL,FAIL}` |
| OBL-05 | Bind each exact proposition version to declared evidence items, spans, inference steps, and source versions. | S05,S19,S20,S26,S27,S30,S35 | `CF-OBL-05-{IO,INV,CTRL,FAIL}` |
| OBL-06 | Evaluate relevance, credibility, convergence, redundancy, dependence, attack/defense, burden, standard, and unresolved status. | S05,S06,S17,S19,S27,S35 | `CF-OBL-06-{IO,INV,CTRL,FAIL}` |
| OBL-07 | Keep evidentiary support and use-specific action authorization as distinct records, edges, and results. | S18,S19,S20,S23,S26,S28,S33,S36,S38 | `CF-OBL-07-{IO,INV,CTRL,FAIL}` |
| OBL-08 | Define an exact action manifest over actor, capability, target, effect, inputs, resources, purpose, scope, externality, assumptions, and policy. | S20,S21,S22,S23,S24,S25,S28,S29,S33,S34 | `CF-OBL-08-{IO,INV,CTRL,FAIL}` |
| OBL-09 | Evaluate permissions, prohibitions, duties, constraints, conditions, continuity, attributes, burdens, and conflicts under one policy version. | S01,S02,S06,S07,S17,S18,S23,S24,S31,S34,S36,S37,S38 | `CF-OBL-09-{IO,INV,CTRL,FAIL}` |
| OBL-10 | Enforce least authority and block independent-principal elevation across principal, class, capability, target, effect, subject, purpose, and scope. | S01,S02,S20,S21,S23,S28,S34 | `CF-OBL-10-{IO,INV,CTRL,FAIL}` |
| OBL-11 | Close and isolate each action's declared support, authority, policy, and influencing-resource basis. | S18,S20,S22,S23,S28,S31,S33,S34,S35 | `CF-OBL-11-{IO,INV,CTRL,FAIL}` |
| OBL-12 | Parameterize information flows by sender, recipient, subject, information type, transmission principle, context, purpose, and scope. | S03,S12,S13,S23,S36 | `CF-OBL-12-{IO,INV,CTRL,FAIL}` |
| OBL-13 | Stage memory changes and commit them transactionally with validation and atomic visibility. | S01,S18,S31 | `CF-OBL-13-{IO,INV,CTRL,FAIL}` |
| OBL-14 | Require declared parent and dependency closure for records, inferences, policies, actions, corrections, and handoff obligations. | S05,S18,S30,S31 | `CF-OBL-14-{IO,INV,CTRL,FAIL}` |
| OBL-15 | Apply exact-version correction, invalidation, and typed cascading repair while preserving independent valid paths. | S05,S18,S30,S31 | `CF-OBL-15-{IO,INV,CTRL,FAIL}` |
| OBL-16 | Package versioned role-aware handoffs with exact artifacts, intended use, support/provenance, authority, obligations, assumptions, missing evidence, and decision ownership. | S07,S26,S27,S29 | `CF-OBL-16-{IO,INV,CTRL,FAIL}` |
| OBL-17 | Track public commitments, duties, acknowledgement, discharge, expiry, violation, continuity, and closure as event-only lifecycle transitions. | S01,S07,S26,S27,S34,S36,S38 | `CF-OBL-17-{IO,INV,CTRL,FAIL}` |
| OBL-18 | Return unresolved/not-adjudicable whenever required authority, provenance, closure, dependency, standard, or world fact is absent or unknowable. | S06,S17,S18,S26,S27,S28,S30,S33,S35,S36,S38 | `CF-OBL-18-{IO,INV,CTRL,FAIL}` |
| OBL-19 | Emit tamper-evident receipts for evidence evaluation, authorization, gate decisions, workflow state, invocation, and observed effects. | S18,S21,S23,S24,S28,S29,S33,S34,S35,S36 | `CF-OBL-19-{IO,INV,CTRL,FAIL}` |
| OBL-20 | Mediate protected effects with a deterministic pre-effect gate that binds exact fields, effect, invocation authority, policy, and observed effect. | S18,S22,S23,S24,S25,S28,S34,S35 | `CF-OBL-20-{IO,INV,CTRL,FAIL}` |
| OBL-21 | Version and replay consumer expectations through one common matching suite. | S08,S11,S31,S37 | `CF-OBL-21-{IO,INV,CTRL,FAIL}` |
| OBL-22 | Treat retrieved content, tool output, metadata, bindings, and self-asserted trust as untrusted until validated for a declared role. | S12,S20,S23,S28,S30,S34,S35,S36,S38 | `CF-OBL-22-{IO,INV,CTRL,FAIL}` |
| OBL-23 | Prevent permission, handoff, trusted-tool traversal, receipt, repetition, or successful execution from automatically promoting evidentiary support. | S09,S14,S19,S20,S23,S28,S33,S34,S36,S37,S38 | `CF-OBL-23-{IO,INV,CTRL,FAIL}` |
| OBL-24 | Maintain exactly four required fixture classes per obligation—input/output, invariant, policy-permitted control, and failure—and tag replay, adversarial, bounded-state, and human-validated coverage modalities across those classes where applicable. Modalities do not create extra fixture classes. | S10,S11,S12,S13,S15,S16,S18,S19,S31,S33,S36 | `CF-OBL-24-{IO,INV,CTRL,FAIL}` |
| OBL-25 | Preserve non-malleable origin, principal, and action-class bindings across every authorization propagation; copying, transformation, or handoff cannot widen authority. | S20,S21,S28,S34 | `CF-OBL-25-{IO,INV,CTRL,FAIL}` |
| OBL-26 | Enforce authorization continuously through expiry and revocation, atomically consume single-use grants, reject replay, and emit one effect-linked execution receipt. | S21,S24,S25,S28,S34 | `CF-OBL-26-{IO,INV,CTRL,FAIL}` |
| OBL-27 | Represent handoff acceptance as version-pinned proposed, accepted, committed, executed, shipped, and verified state transitions, each separate from and linked to its exact receipt, without collapsing recipient sufficiency, authority, decision ownership, or downstream obligations. | S26,S27,S29 | `CF-OBL-27-{IO,INV,CTRL,FAIL}` |
| OBL-28 | Bind the exact trusted rendering bytes and fields presented for approval to the exact action manifest and executed effect; detect deceptive render/effect divergence and measure silent-pass and interaction-burden controls. | S25 | `CF-OBL-28-{IO,INV,CTRL,FAIL}` |

## Manifest record

Each obligation instantiates this record:

```text
CapabilityRecord =
  <obligation_id,
   row_class = B1_BEHAVIOR | B1_VALIDATION | DIAGNOSTIC_ONLY,
   mandatory,
   foundation_requirement_refs[],
   source_basis[] =
     <source_id, primary_source, source_version, artifact_digest?,
      exact_locator, described_claim, transfer_limit, collision_map_ref>,
   functional_spec_ref,
   fixture_refs =
     <input_output[], invariant[], policy_permitted_control[], failure[]>,
   realization =
     NOT_ATTEMPTED | AUTHORITATIVE_EXECUTABLE | LOCALLY_REIMPLEMENTED,
   realization_ref?,
   specification = DRAFT | FROZEN | INCOMPLETE,
   test_result = NOT_RUN | PASS | FAIL | INCOMPLETE,
   test_receipt_ref?,
   reviewer_acceptance =
     <reviewer_id?, author_separated, accepted, checklist_digest?>,
    source_obligation_fixture_chain_complete,
    gap_impact_ref,
    nonblocking_gap_review? =
      <reviewer_id, author_separated, candidate_rule_digest,
       cannot_express_or_subsume_candidate_rule,
       cannot_alter_endpoint, evidence_refs[], accepted>,
    seal_status = SEALED | UNSEALED>
```

`AUTHORITATIVE_EXECUTABLE` additionally requires a source- or maintainer-linked
implementation, exact version and hash, local execution receipt, and the
source's authoritative method. A local implementation is always labeled
`LOCALLY_REIMPLEMENTED`; it cannot use a cited system's conformance name.

## Deterministic sealing and gap algebra

An obligation is `SEALED` if and only if all are true:

```text
specification == FROZEN
and test_result == PASS
and realization in {AUTHORITATIVE_EXECUTABLE, LOCALLY_REIMPLEMENTED}
and every source -> obligation -> required-fixture-class chain resolves
and every referenced digest resolves
and an author-separated reviewer accepts the frozen checklist
```

Every other terminal combination is `UNSEALED`; ambiguity is blocking. B1 is
sealed only when every B1 behavior and validation row is sealed and the exact-
binding and derived-arm parity gates pass. `Nonblocking` is only a frozen gap-
impact conclusion; it is never a row class, satisfaction state, or optionality
marker.

Every gap maps the complete, nonoverlapping frozen universes of case families,
endpoints, witnesses, and claims to `AFFECTED | UNAFFECTED | UNKNOWN`. An
overlap, omission, ambiguity, or `UNKNOWN` makes the gap unbounded and keeps the
primary contrast closed. A bounded gap makes every reachable stratum
`NOT_ADJUDICABLE`. Any mandatory gap makes any primary result
`EXPLORATORY_ONLY`.

No gap may be called nonblocking until an author-separated comparator reviewer
has frozen and accepted evidence that the missing capability cannot express or
subsume the receiver-local rule and cannot alter the endpoint. Any plausible
substitute or unresolved equivalence remains blocking. This review is separate
from ordinary source/fixture acceptance and is repeated after any candidate-rule,
endpoint, or comparator change.

Enumeration completeness rests on the candidate-blind source-disposition,
obligation-enumeration, and completeness-review chain. A later-discovered
mandatory omission is appended as an UNSEALED row and retroactively
reclassifies every causally reachable prior result as `EXPLORATORY_ONLY`.
Remediation requires a new run and never rehabilitates the old result.

Only unaffected descriptive strata may say:

> Beyond the composition as sealed, which lacked [enumerated capability].

The phrase “beyond established capability” is prohibited.

## Exact action-input binding gate

Before any rule contrast, B1 with the candidate consuming rule disabled and only
the common declaration interface present must pass:

- one coherent exact-match positive;
- an unrelated policy-admitted/action-safe record negative;
- protected-field mismatch;
- exact-effect mismatch;
- invocation/capability mismatch;
- changed-action mismatch;
- replay and nonce-reuse mismatch; and
- trusted-render bytes/fields that differ from the executed manifest or effect,
  plus policy-permitted silent-pass and burden controls; and
- a candidate reliance record that cannot satisfy support or external action
  authorization.

B1-ATTENTION and G-BIND inherit the identical B1 implementation digest and rerun
candidate-disabled parity. Any mismatch blocks the rule contrast. No additional
representation arm is present.

## Diagnostic-only MemTX boundary

`B-MEMTX` is not a B1 obligation. It exists only if a hash-pinned authoritative
executable passes a frozen diagnostic suite under the source's authoritative
method. Until then its exact status is
`B_MEMTX_DIAGNOSTIC_UNAVAILABLE`. A neutral local replica may satisfy a B1
functional obligation after normal sealing, but cannot support a MemTX-specific
result.

## Current instantiated status

A6 contains all 28 mandatory obligations as `UNSEALED`, with
`realization=NOT_ATTEMPTED`, `specification=DRAFT`, `test_result=NOT_RUN`, no
complete source-to-fixture chain, no author-separated acceptance, and unbounded
gap impact. Therefore:

```text
B1_SEALING_INCOMPLETE
primary_contrast_open = false
sealed_count = 0
```

This is the correct Gate 0 status. It licenses no framework, novelty, efficacy,
integration-gap, contribution, or established-capability claim.
