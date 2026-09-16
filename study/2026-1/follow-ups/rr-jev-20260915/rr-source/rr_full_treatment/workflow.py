"""Candidate local model workflow with actual input capture at every receiver.

Domain time is a controlled discrete event clock. Wall timestamps independently
record when this program ran; domain intervals do not purport to measure elapsed
wall time. All principals and tasks are synthetic; this host makes no claim of
resisting its own operator. Development candidate: not qualified for study use.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time

from . import conditions, model_client, workload
from .decision_worker import state_bytes
from .host_facts import CapturedArtifact, UseContext, assemble, canonical, envelope, sha, subject
from .invoke import run as decide
from .observe import verify

EPOCH = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)


def stamp(seconds):
    return (EPOCH + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def cap(*parts):
    return "CAP_" + sha(canonical(parts))[:24]


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.mkdir(exist_ok=False)
        self.ordinal = 0
        self.events = []

    def write(self, name, raw):
        path = self.path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
        if path.read_bytes() != raw:
            raise RuntimeError("Stored capture differs from supplied bytes")
        return path

    def event(self, kind, **facts):
        self.ordinal += 1
        event = {"ordinal": self.ordinal, "domain_at": stamp(self.ordinal),
                 "domain_seconds": self.ordinal, "wall_at_ns": time.time_ns(), "kind": kind, **facts}
        with (self.path / "events.jsonl").open("ab") as stream:
            stream.write(canonical(event) + b"\n")
        self.events.append(event)
        return event


@dataclass(frozen=True)
class RegisteredAnswer:
    path: Path
    envelope_path: Path
    registered_envelope_sha256: str
    registered_node: str


class InvalidModelOutput(ValueError):
    """A fully observed model response failed the fixed task-output contract."""


def model_step(journal, name, messages, task, seed, episode_id):
    request = model_client.request_bytes(messages, seed)
    journal.write(name + ".request.json", request)
    journal.event("MODEL_REQUEST", node=name, request_sha256=sha(request))
    try:
        response = model_client.call(request)
    except Exception as error:
        if getattr(error, 'raw_response', None) is not None:
            journal.write(name + '.response.json', error.raw_response)
        journal.write(name + '.failure.json', canonical({'error_type':type(error).__name__, 'error':str(error)}))
        journal.event('MODEL_TRANSPORT_FAILED', node=name, request_sha256=sha(request),
                      error_type=type(error).__name__, error=str(error))
        raise
    journal.write(name + ".response.json", response["raw_response"])
    receipt = {key: value for key, value in response.items() if key not in ("raw_request", "raw_response")}
    journal.write(name + ".model-receipt.json", canonical(receipt))
    journal.event("MODEL_RESPONSE", node=name, response_sha256=response["response_sha256"])
    # A syntax/type failure is a retained failed model operation, never repaired.
    try:
        parsed = workload.parse_answer(response["text"], task)
    except ValueError as error:
        journal.event('MODEL_OUTPUT_REJECTED', node=name, response_sha256=response['response_sha256'],
                      error_type=type(error).__name__, error=str(error))
        raise InvalidModelOutput(str(error)) from error
    answer = workload.canonical_encode(parsed, task)
    path = journal.write(name + ".answer.json", answer)
    import base64
    answer_envelope = canonical({"format": "RR-SCIENTIFIC-CLOSED-ARTIFACT-1",
        "artifact_id": "ART_" + sha(canonical([episode_id, name, "model-output"])), "revision": 1,
        "media_type": "application/json", "content_b64": base64.b64encode(answer).decode()})
    envelope_path = journal.write(name + ".answer-envelope.json", answer_envelope)
    journal.event("ANSWER_SERIALIZED", node=name, answer_sha256=sha(answer),
                  envelope_sha256=sha(answer_envelope),
                  normalization="strict parsed JSON to canonical bytes; original response retained")
    return RegisteredAnswer(path, envelope_path, sha(answer_envelope), name)


def issue_records(artifact, use, *, delegated, issued_at):
    """Explicit local declarations of intended use; never assertions of truth."""
    source = cap("local-source-service")
    delegate = cap("local-delegated-service")
    issuer = delegate if delegated else source
    named_ref = "STANDING_" + sha(canonical(["named", issuer, use.receiver]))[:24]
    root_ref = "STANDING_" + sha(canonical(["root", source, use.receiver]))[:24]
    interval = {"effective_from": use.valid_from, "effective_until": use.valid_until}
    named = {"mandate_version_ref": named_ref, "subject_capability_id": issuer,
             "permitted_record_kinds": ["ADOPTION_DECLARED"], "purpose_ids": [use.purpose],
             "scope_ids": [use.scope], "policy_ref": use.policy, "interval": interval}
    acceptance = {"declaration_kind": "ADOPTION_DECLARED", "declaration_version_ref": "DECL_USE",
        "episode_id": use.episode_id, "exact_claim_version_id": subject(artifact), "interval": interval,
        "issuer_capability_id": issuer, "mandate_version_ref": named_ref, "policy_ref": use.policy,
        "purpose_id": use.purpose, "scope_id": use.scope, "receiver_capability_id": use.receiver,
        "recorded_at": issued_at, "standing_basis_ref": "DECL_GRANT" if delegated else named_ref}
    mandates, declarations = [named], [acceptance]
    if delegated:
        mandates.append({**named, "mandate_version_ref": root_ref, "subject_capability_id": source,
                         "permitted_record_kinds": ["DELEGATION_DECLARED"]})
        declarations.insert(0, {**acceptance, "declaration_kind": "DELEGATION_DECLARED",
            "declaration_version_ref": "DECL_GRANT", "issuer_capability_id": source,
            "mandate_version_ref": root_ref, "standing_basis_ref": root_ref,
            "delegate_capability_id": delegate, "grant_id": "GRANT_USE"})
    return {"mandates": mandates, "declarations": declarations,
            "included_refs": [row["declaration_version_ref"] for row in declarations],
            "declared_basis_refs": ["DECL_USE"]}


def prepare_receiver(journal, world, plan, parents, episode, *, delegated, attempt=0, service_fault=None):
    node = plan["id"]
    prefix = f"{node}/attempt-{attempt}"
    import base64
    actual_parents = {name: registered.path.read_bytes() for name, registered in parents.items()}
    messages = workload.receiver_messages(world, node, actual_parents)
    content = messages[1]["content"].encode("utf-8")
    parent_refs = tuple("PARENT_" + parents[name].registered_envelope_sha256 for name in plan["parents"])
    observed_parent_refs = []
    parent_captures = []
    # Expected identities come from the prior registration. Observed identities
    # come from the files actually delivered, independently of the expected list.
    for name in plan["parents"]:
        registered_raw = parents[name].envelope_path.read_bytes()
        if sha(registered_raw) != parents[name].registered_envelope_sha256:
            raise ValueError('Previously registered parent bytes changed')
        registered_path = journal.write(prefix + '.parent-registered-' + name + '.json', registered_raw)
        raw_envelope = registered_raw
        if service_fault == 'parent_version' and name == plan['parents'][0]:
            alternate = json.loads(raw_envelope)
            alternate['revision'] += 1
            raw_envelope = canonical(alternate)
            journal.event('PARENT_VERSION_ISSUED', node=node, attempt=attempt, parent=name,
                          registered_sha256=sha(registered_raw), issued_sha256=sha(raw_envelope),
                          payload_unchanged=True)
        delivered_path = journal.write(prefix + '.parent-delivered-' + name + '.json', raw_envelope)
        delivered = json.loads(raw_envelope)
        if base64.b64decode(delivered["content_b64"], validate=True) != actual_parents[name]:
            raise ValueError("Observed parent envelope does not contain the delivered payload")
        observed_parent_refs.append("PARENT_" + sha(raw_envelope))
        parent_captures.append({"node": name, "envelope_sha256": sha(raw_envelope),
            "payload_sha256": sha(actual_parents[name]), 'registered_sha256':sha(registered_raw),
            'registered_path':str(registered_path.relative_to(journal.path)).replace('\\','/'),
            'delivered_path':str(delivered_path.relative_to(journal.path)).replace('\\','/')})
    journal.event("PARENTS_CAPTURED", node=node, attempt=attempt, parents=parent_captures,
                  expected_parent_refs=list(parent_refs))
    receiver = cap(episode, node)
    artifact_id = "ART_" + sha(canonical([episode, node, "receiver-input"]))
    artifact = CapturedArtifact(content, artifact_id, 1, "", artifact_id, 1,
        tuple(observed_parent_refs), 1, receiver, "PURPOSE_" + world["task"].upper(), ("SCOPE_SYNTHETIC",), "PERMIT")
    artifact = replace(artifact, sender_envelope_sha256=sha(canonical(envelope(artifact))))
    # The file copy is the benign ingress effect audited by the OBL-26 table.
    issued = journal.event("INGRESS_GRANT_ISSUED", node=node, attempt=attempt, state="UNUSED",
                            nonce="NONCE_" + sha(prefix.encode()),
                            expires_after_seconds=0 if service_fault=='ingress_expired' else 120)
    prior_nonces = [event["nonce"] for event in journal.events if event["kind"] == "INGRESS_INVOKED"
                    and event["node"] == node]
    invocation = journal.event("INGRESS_INVOKED", node=node, attempt=attempt,
        revocation_checked=True, revoked_at=None, pre_invocation_state=issued["state"], nonce=issued["nonce"],
        prior_invocation_nonces=prior_nonces, effect_sha256=sha(content), grant_event=issued["ordinal"])
    captured_path = journal.write(prefix + ".captured.json", content)
    captured = captured_path.read_bytes()
    effect = journal.event("INGRESS_EFFECT_RECORDED", node=node, attempt=attempt,
                           effect_sha256=sha(captured), invocation_event=invocation["ordinal"])
    effect_events = [event for event in journal.events if event["kind"] == "INGRESS_EFFECT_RECORDED"
                     and event["invocation_event"] == invocation["ordinal"]]
    grant_facts = {"consumption_state": invocation["pre_invocation_state"], "effect_receipt_count": len(effect_events),
        "effect_sha256": invocation["effect_sha256"], "execution_receipt_effect_sha256": effect["effect_sha256"],
        "grant_expires_at": (issued["domain_seconds"] + issued["expires_after_seconds"])*1000,
        "grant_not_before": issued["domain_seconds"]*1000,
        "invocation_nonce": invocation["nonce"],
        "invocation_time": invocation["domain_seconds"]*1000, "prior_invocation_nonces": invocation["prior_invocation_nonces"],
        "revocation_checked_at": invocation["domain_seconds"]*1000 if invocation["revocation_checked"] else None,
        "revoked_at": invocation["revoked_at"]}
    # Declaration issue precedes the captured source ledger. RecordedUse is the
    # later receiver request to rely, not a retrospective assertion of execution.
    issue_event = journal.event("RELIANCE_DECLARATION_REQUESTED", node=node, attempt=attempt,
                                exact_claim=subject(artifact))
    use = UseContext(episode, receiver, cap("local-source-service"), artifact.observed_purpose,
        "SCOPE_SYNTHETIC", "POLICY_SHARED_0_1", parent_refs, 1, "ROUTE_" + node, "SLOT_" + node,
        "CARRIER_LOCAL", "OWNER_LOCAL", cap("local-source-service"), "AUTH_LOCAL", "PERMIT",
        stamp(0), stamp(0), stamp(0), stamp(100000), 0, 0, 100000*10**9, 1,
        "ACTION_" + sha(canonical([episode, node]))[:24],
        "CONTEXT_" + sha(canonical([episode, node])), "NONCE_" + sha(canonical([episode, node, attempt])))
    records = issue_records(artifact, use, delegated=delegated, issued_at=issue_event["domain_at"])
    prior_records = json.loads((journal.path / f'{node}/attempt-0.ledger-records.json').read_bytes()) if attempt else None
    records = conditions.declaration_response(records, service_fault, attempt, prior_records)
    records_path = journal.write(prefix + ".ledger-records.json", canonical(records))
    journal.event('DECLARATION_SERVICE_RESPONSE', node=node, attempt=attempt,
                  records_sha256=sha(records_path.read_bytes()), ledger_scope='THIS_EPISODE_RECEIVER',
                  complete_local_history=True)
    ledger_event = journal.event("LEDGER_SNAPSHOT_CAPTURED", node=node, attempt=attempt,
                                 records_sha256=sha(records_path.read_bytes()))
    use_event = journal.event("RECEIVER_RELIANCE_REQUESTED", node=node, attempt=attempt,
                              exact_claim=subject(artifact), receiver=receiver)
    use = replace(use, observed_at=ledger_event["domain_at"], use_at=use_event["domain_at"],
                  use_ns=use_event["domain_seconds"]*10**9)
    closure_event = journal.event("FINITE_HISTORY_CLOSED", node=node, attempt=attempt,
                                  through=use_event["domain_at"], snapshot_event=ledger_event["ordinal"])
    actual_records = json.loads(records_path.read_bytes())
    common = assemble(artifact, use,
        task={"instruction": messages[0]["content"], "constraints": []}, source_content=canonical(world),
        **actual_records, guard_observation=grant_facts,
        closure={"record_classes": ["CLAIM_VERSION", "DECLARATION_RECORD", "MANDATE_RECORD", "USE_RECORD"],
                 "through": closure_event["through"], "source_extent": ["SOURCE_MANDATE", "SOURCE_PRIMARY"]},
        transport={"carrier_fence": 1, "origin_finalized": True, "revocation_active": False,
            **{key: getattr(use, key) for key in ("route", "slot", "carrier", "owner", "principal", "authority")}},
        refetch_budget=1, attempt_ordinal=attempt)
    journal.write(prefix + ".common.json", common)
    journal.write(prefix + ".envelope.json", canonical(envelope(artifact)))
    return prefix, common, messages[0], captured_path


def episode(world, arm, out, *, delegated=False, seed=610100, package="a"):
    """Development clean trajectory. Conditions/remediation remain a next gate."""
    journal = Journal(out)
    identifier = "EP_" + sha(canonical([world, seed, delegated]))
    journal.write("world.json", canonical(world))
    journal.write("state.json", state_bytes(arm))
    journal.event("EPISODE_STARTED", episode=identifier, arm=arm, package=package)
    outputs, observations = {}, []
    try:
        outputs["SOURCE"] = model_step(journal, "SOURCE", workload.source_messages(world), world["task"], seed, identifier)
        for index, plan in enumerate(workload.nodes(world)):
            parents = {name: outputs[name] for name in plan["parents"]}
            prefix, common, system, capture_path = prepare_receiver(journal, world, plan, parents,
                identifier, delegated=delegated)
            receipt = decide(package, arm, common, state_bytes(arm))
            journal.write(prefix + ".decision-observation.json", canonical(receipt))
            binding = verify(common, state_bytes(arm), receipt, expected_package=package, expected_arm=arm)
            journal.write(prefix + ".binding.json", canonical(binding))
            import base64
            result = json.loads(base64.b64decode(receipt["output_b64"]))
            journal.event("DECISION_OBSERVED", node=plan["id"], attempt=0,
                          output_sha256=receipt["output_sha256"], witness_digest=result["witness_digest"])
            if result["disposition"] != "PASS":
                journal.event("RECEIVER_HELD", node=plan["id"], code=result["code"])
                raise RuntimeError("Clean development path was held: " + result["code"])
            captured = capture_path.read_bytes()
            journal.write(prefix + ".released.json", captured)
            journal.event("RECEIVER_PRESENTED", node=plan["id"], content_sha256=sha(captured),
                          common_sha256=sha(common), state_sha256=sha(state_bytes(arm)))
            messages = [system, {"role": "user", "content": captured.decode("utf-8")}]
            outputs[plan["id"]] = model_step(journal, plan["id"], messages, world["task"], seed+index+1, identifier)
            observations.append(binding)
        final = workload.nodes(world)[-1]["id"]
        parsed = workload.parse_answer(outputs[final].path.read_bytes(), world["task"])
        summary = {"status": "DEVELOPMENT_COMPLETED", "answer": parsed,
                   "answer_correct": parsed == workload.truth(world), "receivers": len(observations),
                   "binding_observations": observations}
    except Exception as error:
        summary = {"status": "DEVELOPMENT_FAILED", "error_type": type(error).__name__, "error": str(error),
                   "receivers_completed": len(observations)}
    journal.event("EPISODE_FINISHED", status=summary["status"])
    journal.write("summary.json", canonical(summary))
    return summary


def _coherent_source_control(journal, registered, world, identifier):
    """A declared semantic control preserves the genuine source response separately.

    This deterministic perturbation is a constructed control input, not a claim
    that the source model generated it. No reference answer is consulted.
    """
    import base64
    answer = workload.parse_answer(registered.path.read_bytes(), world['task'])
    if world['task'] == 'sum':
        answer['answer'] += 1
    else:
        values = set(answer['answer'])
        values.symmetric_difference_update({'A01'})
        answer['answer'] = sorted(values)
    raw = workload.canonical_encode(answer, world['task'])
    path = journal.write('SOURCE.control-answer.json', raw)
    env = canonical({'format':'RR-SCIENTIFIC-CLOSED-ARTIFACT-1',
        'artifact_id':'ART_'+sha(canonical([identifier,'SOURCE','constructed-semantic-control'])),
        'revision':1,'media_type':'application/json','content_b64':base64.b64encode(raw).decode()})
    envelope_path = journal.write('SOURCE.control-envelope.json',env)
    journal.event('SOURCE_CONTROL_RECORDED', node='SOURCE', original_answer_sha256=sha(registered.path.read_bytes()),
                  answer_sha256=sha(raw), envelope_sha256=sha(env),
                  operation='ADD_ONE' if world['task']=='sum' else 'TOGGLE_A01',
                  source_model_output_preserved=True)
    return RegisteredAnswer(path,envelope_path,sha(env),'SOURCE')


def run_episode(world, arm, out, *, condition, seed, package='a', cap_seconds=1200):
    """Full transforming trajectory; one common administrative refetch per node.

    The controller records outcomes but does not compute an answer oracle or a
    structural score. The independent post-run observer owns those quantities.
    A known hold, malformed task output or cap cancels only dependent work.
    Missing model/host observation invalidates the episode and stops execution.
    """
    import base64
    if condition not in conditions.CONDITIONS or cap_seconds != 1200:
        raise ValueError('Unregistered episode condition or resource cap')
    delegated = condition == 'clean_delegated'
    journal = Journal(out)
    identifier = 'EP_'+sha(canonical([world,seed,delegated]))
    journal.write('world.json',canonical(world))
    state = state_bytes(arm)
    journal.write('state.json',state)
    journal.event('EPISODE_STARTED',episode=identifier,arm=arm,package=package,condition=condition,
                  model_seed=seed,cap_seconds=cap_seconds)
    started = time.perf_counter_ns()
    outputs = {}
    capped = False
    observation_failure = None

    def cap_reached(node):
        nonlocal capped
        elapsed = time.perf_counter_ns()-started
        if not capped and elapsed >= cap_seconds*10**9:
            capped = True
            journal.event('EPISODE_CAP_REACHED',node=node,cap_seconds=cap_seconds,elapsed_ns=elapsed)
        return capped

    try:
        try:
            outputs['SOURCE'] = model_step(journal,'SOURCE',workload.source_messages(world),world['task'],seed,identifier)
            if condition == 'coherent_false':
                outputs['SOURCE'] = _coherent_source_control(journal,outputs['SOURCE'],world,identifier)
        except InvalidModelOutput:
            pass
        for index,plan in enumerate(workload.nodes(world)):
            node = plan['id']
            if cap_reached(node):
                journal.event('RECEIVER_CANCELLED',node=node,reason='EPISODE_WALL_CAP')
                continue
            missing = [name for name in plan['parents'] if name not in outputs]
            if missing:
                journal.event('RECEIVER_CANCELLED',node=node,reason='MISSING_PARENT_OUTPUT',parents=missing)
                continue
            parents = {name:outputs[name] for name in plan['parents']}
            for attempt in (0,1):
                if cap_reached(node):
                    journal.event('RECEIVER_CANCELLED',node=node,reason='EPISODE_WALL_CAP')
                    break
                fault = conditions.active_fault(condition,node,attempt,world['index'])
                prefix,common,system,capture_path = prepare_receiver(journal,world,plan,parents,identifier,
                    delegated=delegated,attempt=attempt,service_fault=fault)
                receipt = decide(package,arm,common,state)
                journal.write(prefix+'.decision-observation.json',canonical(receipt))
                binding = verify(common,state,receipt,expected_package=package,expected_arm=arm)
                journal.write(prefix+'.binding.json',canonical(binding))
                result = json.loads(base64.b64decode(receipt['output_b64'],validate=True))
                journal.event('DECISION_OBSERVED',node=node,attempt=attempt,
                    output_sha256=receipt['output_sha256'],witness_digest=result['witness_digest'],
                    disposition=result['disposition'],code=result['code'])
                if result['disposition'] != 'PASS':
                    if attempt == 0:
                        journal.event('REFRESH_REQUESTED',node=node,attempt=attempt,
                                      action_or_decision_ref=json.loads(common)['a2_raw_shared_bundle']['use_records'][0]['action_or_decision_ref'],
                                      reason='FIRST_NON_PASS',parent_outputs_unchanged=True)
                        continue
                    journal.event('RECEIVER_HELD',node=node,attempt=attempt,code=result['code'],
                                  reason='SECOND_NON_PASS')
                    break
                if cap_reached(node):
                    journal.event('RECEIVER_CANCELLED',node=node,reason='EPISODE_WALL_CAP')
                    break
                captured = capture_path.read_bytes()
                journal.write(prefix+'.released.json',captured)
                journal.event('RECEIVER_PRESENTED',node=node,attempt=attempt,content_sha256=sha(captured),
                              common_sha256=sha(common),state_sha256=sha(state))
                messages = [system,{'role':'user','content':captured.decode('utf-8')}]
                try:
                    outputs[node] = model_step(journal,node,messages,world['task'],seed+index+1,identifier)
                except InvalidModelOutput:
                    pass
                break
    except Exception as error:
        observation_failure = {'error_type':type(error).__name__,'error':str(error)}
        journal.event('OBSERVATION_FAILURE',**observation_failure)
    final_node = workload.nodes(world)[-1]['id']
    # The deadline is also observed after the last in-flight call. A call is
    # bounded by its own timeout; crossing the episode deadline is retained.
    cap_reached(final_node)
    status = ('OBSERVATION_FAILURE' if observation_failure else
              'COMPLETED' if final_node in outputs else 'NOT_COMPLETED')
    summary = {'status':status,'final_node':final_node,'output_nodes':list(outputs),
               'elapsed_ns':time.perf_counter_ns()-started,'cap_reached':capped,
               'observation_failure':observation_failure}
    journal.event('EPISODE_FINISHED',status=status)
    journal.write('terminal.json',canonical(summary))
    journal.write('summary.json',canonical(summary))
    return summary
