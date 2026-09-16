"""Independent RR local-study observer candidate; stdlib only.

Reads preserved episode evidence; never imports the workload or a decision law.
The controller is trusted to record events honestly. This is not an OS custody
proof or a complete validator of the full treatment's normative semantics.
Malformed/missing evidence returns INVALID with no numeric endpoint imputation.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re


class MeasurementFailure(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise MeasurementFailure(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest().upper()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def _nonfinite(value):
    raise MeasurementFailure('Nonfinite JSON number')


def decode(raw):
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_nonfinite)


def parse_answer(raw, task):
    require(type(raw) in (bytes, str), 'Answer is not text')
    encoded = raw if type(raw) is bytes else raw.encode('utf-8')
    require(len(encoded) <= 8192, 'Answer byte cap exceeded')
    value = decode(encoded.decode('utf-8'))
    require(type(value) is dict and set(value) == {'answer'}, 'Invalid answer fields')
    answer = value['answer']
    if task == 'sum':
        require(type(answer) is int, 'Sum answer must be an integer')
    else:
        require(task == 'selection' and type(answer) is list, 'Invalid selection answer')
        require(all(type(x) is str and re.fullmatch(r'[ABCD]0[1-5]', x)
                    for x in answer), 'Invalid selection ID')
        require(answer == sorted(set(answer)), 'Selection IDs not sorted and unique')
    return value


def graph(world):
    topology = world['topology']
    if topology == 'direct':
        return {'R1': ('SOURCE',)}
    if topology == 'chain':
        return {'R1': ('SOURCE',), 'R2': ('R1',), 'R3': ('R2',)}
    require(topology == 'fork', 'Unknown topology')
    return {'R1': ('SOURCE',), 'R2': ('R1',), 'R3': ('R1',),
            'R4': ('R2', 'R3', 'R1')}


def oracle(world, node='final'):
    """Expected answer directly from original groups, never generated answers."""
    plans = graph(world)
    if node == 'final':
        node = list(plans)[-1]
    groups_for = {'SOURCE': 'A', 'R1': 'AB', 'R2': 'ABC', 'R3': 'ABCD', 'R4': 'ABCD'}
    if world['topology'] == 'direct':
        groups_for['R1'] = 'ABCD'
    if world['topology'] == 'fork':
        groups_for['R3'] = 'ABD'
    require(node == 'SOURCE' or node in plans, 'Unknown oracle node')
    groups = world['groups']
    require(type(groups) is dict and set(groups) == set('ABCD'), 'Invalid original groups')
    task = world['task']
    require(task in ('sum', 'selection'), 'Unknown task')
    all_ids = set()
    for name, rows in groups.items():
        require(type(rows) is list and 3 <= len(rows) <= 5, 'Invalid group size')
        for index, row in enumerate(rows):
            if task == 'sum':
                require(type(row) is int and 1 <= row <= 40, 'Invalid original summand')
            else:
                require(type(row) is dict and set(row) == {'id', 'grade', 'count'}, 'Invalid item')
                require(row['id'] == f'{name}{index+1:02d}' and row['id'] not in all_ids,
                        'Invalid original ID')
                all_ids.add(row['id'])
                require(row['grade'] in ('A', 'B', 'C') and type(row['count']) is int
                        and 1 <= row['count'] <= 7, 'Invalid original item value')
    selected = [row for name in groups_for[node] for row in groups[name]]
    answer = (sum(selected) if task == 'sum' else
              sorted(row['id'] for row in selected if row['grade'] == 'A' and row['count'] >= 4))
    return {'answer': answer}


def _integer(value, label):
    require(type(value) is int and value >= 0, 'Invalid nonnegative integer: ' + label)
    return value


def _instant(value):
    require(type(value) is str, 'Invalid time')
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')


def _payload(raw):
    env = decode(raw)
    require(type(env) is dict and set(env) ==
            {'format', 'artifact_id', 'revision', 'media_type', 'content_b64'}, 'Invalid envelope')
    require(env['format'] == 'RR-SCIENTIFIC-CLOSED-ARTIFACT-1'
            and env['media_type'] == 'application/json'
            and type(env['revision']) is int and env['revision'] >= 1, 'Invalid envelope grammar')
    return base64.b64decode(env['content_b64'], validate=True)


def _witness(common_raw, state_raw, receipt, observed, decision_event, binding):
    """Reconstruct the public wire witness, independently of its decision law.

    Root integrated this explicit wire check into the separately authored scorer.
    Arm labels are not used to choose an endpoint or predict a decision.
    """
    state=decode(state_raw)
    formats={'RR-STUDY-TREATMENT-STATE-U-5':'U','RR-STUDY-TREATMENT-STATE-S-5':'S',
             'RR-STUDY-TREATMENT-STATE-R-5':'R'}
    require(state.get('format') in formats,'Unknown actual treatment state')
    module=formats[state['format']]
    entry=('DECIDE_'+module).encode('ascii')
    frame=lambda raw:len(raw).to_bytes(8,'big')+raw
    output=base64.b64decode(receipt['output_b64'],validate=True)
    require(set(observed)=={'code','disposition','format','input_digest','occurrence','pointer',
        'reason','remediation','stage','witness_digest'} and canonical(observed)==output,'Noncanonical decision wire')
    require(receipt['observed'] is True,'Decision was not observed')
    require(receipt['state_sha256']==binding['state_sha256']==sha(state_raw),'State capture mismatch')
    input_hash=sha(b'RR-STUDY-TREATMENT-INPUT-5\0'+frame(entry)+frame(common_raw)+frame(state_raw))
    require(observed['input_digest']==input_hash,'Decision input witness mismatch')
    constructions=receipt['constructions']
    require(len(constructions)==1 and constructions[0]['output_sha256']==sha(output),'Missing decision construction')
    evidence=constructions[0]['evidence']
    require(set(evidence)=={'code','module','occurrence','pointer','semantic_evidence','stage'},'Incomplete witness evidence')
    require(all(evidence[k]==observed[k] for k in ('code','occurrence','pointer','stage'))
        and evidence['module'] in (module,'PUBLIC_BOUNDARY'),'Witness fields disagree')
    witness=sha(b'RR-STUDY-TREATMENT-WITNESS-5\0'+frame(entry)+bytes.fromhex(input_hash)
        +frame(observed['disposition'].encode('ascii'))+frame(observed['reason'].encode('ascii'))
        +frame(observed['remediation'].encode('ascii'))+frame(canonical(evidence)))
    require(observed['witness_digest']==decision_event['witness_digest']==witness,'Unbound or spliced witness')
    calls=receipt['engine_calls']
    require(len(calls)==(1 if module=='R' else 0),'Engine call census outside the registered finite host domain')
    if calls:
        actual=base64.b64decode(calls[0]['request_b64'],validate=True)
        require(sha(actual)==calls[0]['request_sha256'],'Engine request hash mismatch')
        request=decode(actual);common=decode(common_raw)
        require(request['inner_request']['input']==common['a2_raw_shared_bundle']
            and request['decision_input']['facts']==common['guard_observation_facts'],'Engine consumed different input')
        if observed['code'].startswith('R_ACCEPTANCE_'):
            semantic=evidence['semantic_evidence']
            require(semantic['recorded_use_sha256']==sha(canonical(common['a2_raw_shared_bundle']['use_records'][0]))
                and semantic['engine_output_sha256']==sha(canonical(calls[0]['returned_envelope'])+b'\n'),
                'Acceptance witness consumed stale engine/use evidence')


class Evidence:
    def __init__(self, path):
        self.root = Path(path).resolve()
        self.world = self.obj('world.json')
        self.events = [decode(line) for line in self.raw('events.jsonl').splitlines() if line]
        require(bool(self.events), 'Empty event ledger')
        for number, row in enumerate(self.events, 1):
            require(type(row) is dict and row['ordinal'] == number
                    and type(row['ordinal']) is int, 'Nonunique or unordered event ordinal')
            _integer(row['domain_seconds'], 'domain_seconds')
            _integer(row['wall_at_ns'], 'wall_at_ns')
            _instant(row['domain_at'])
            require(row['domain_seconds']==number and row['domain_at']==
                    (datetime(2026,9,5,12)+timedelta(seconds=number)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'Domain clock differs from declared event clock')
        require(self.events[0]['kind'] == 'EPISODE_STARTED'
                and self.events[-1]['kind'] == 'EPISODE_FINISHED', 'Episode is not closed')
        require(len(self.find('EPISODE_STARTED')) == len(self.find('EPISODE_FINISHED')) == 1,
                'Duplicate episode boundary')
        require(not any(e['kind'] in ('MODEL_TRANSPORT_FAILED', 'OBSERVATION_FAILURE')
                        for e in self.events), 'Explicit observation failure')
        require(self.events[-1]['status'] in ('COMPLETED', 'NOT_COMPLETED'),
                'Unobserved or unregistered terminal outcome')
        self.obj('terminal.json')  # Presence/parse only; its claimed scores are not authority.

    def raw(self, name):
        require(type(name) is str, 'Non-string evidence path')
        target = (self.root / name).resolve()
        require(target.is_relative_to(self.root) and target.is_file(), 'Missing/outside evidence: ' + name)
        return target.read_bytes()

    def obj(self, name):
        return decode(self.raw(name))

    def find(self, kind, node=None, attempt=None):
        return [e for e in self.events if e['kind'] == kind
                and (node is None or e.get('node') == node)
                and (attempt is None or e.get('attempt') == attempt)]

    def one(self, kind, node=None, attempt=None):
        rows = self.find(kind, node, attempt)
        require(len(rows) == 1, f'Expected one {kind}: {node}/{attempt}')
        return rows[0]


def _model(evidence, node):
    request_event = evidence.one('MODEL_REQUEST', node)
    response_event = evidence.one('MODEL_RESPONSE', node)
    request_raw = evidence.raw(node + '.request.json')
    response_raw = evidence.raw(node + '.response.json')
    request, response = decode(request_raw), decode(response_raw)
    receipt = evidence.obj(node + '.model-receipt.json')
    require(request_event['ordinal'] < response_event['ordinal'], 'Reversed model events')
    require(sha(request_raw) == request_event['request_sha256'] == receipt['request_sha256'],
            'Model request hash mismatch')
    require(sha(response_raw) == response_event['response_sha256'] == receipt['response_sha256'],
            'Model response hash mismatch')
    require(response.get('done') is True and type(response['message']['content']) is str,
            'Incomplete model response')
    require(receipt['text'] == response['message']['content'], 'Response text mismatch')
    metrics = receipt['metrics']
    for key in ('prompt_eval_count', 'eval_count'):
        _integer(metrics[key], key)
        require(metrics[key] == response[key], 'Token receipt mismatch')
    require(metrics['done_reason'] == response.get('done_reason'), 'Stop reason mismatch')
    wall = _integer(receipt['wall_ns'], 'model wall_ns')
    rejected = evidence.find('MODEL_OUTPUT_REJECTED', node)
    try:
        parsed = parse_answer(response['message']['content'], evidence.world['task'])
    except (ValueError, TypeError, UnicodeError, RecursionError):
        require(len(rejected) == 1 and rejected[0]['ordinal'] > response_event['ordinal'],
                'Unrecorded malformed model output')
        require(not evidence.find('ANSWER_SERIALIZED', node), 'Rejected output was serialized')
        parsed = None
    else:
        require(not rejected, 'Valid response marked rejected')
        serialized = evidence.one('ANSWER_SERIALIZED', node)
        answer_raw = evidence.raw(node + '.answer.json')
        envelope_raw = evidence.raw(node + '.answer-envelope.json')
        require(answer_raw == canonical(parsed) and _payload(envelope_raw) == answer_raw,
                'Answer normalization/envelope mismatch')
        require(sha(answer_raw) == serialized['answer_sha256']
                and sha(envelope_raw) == serialized['envelope_sha256']
                and serialized['ordinal'] > response_event['ordinal'], 'Answer witness mismatch')
    return {'parsed': parsed, 'request': request,
            'semantic_output_error': parsed is not None and parsed != oracle(evidence.world, node),
            'invalid_output': parsed is None, 'model_wall_ns': wall,
            'prompt_tokens': metrics['prompt_eval_count'], 'output_tokens': metrics['eval_count'],
            'token_cap_hit': response.get('done_reason') == 'length'}


def _attempt(evidence, node, attempt, expected_parents, models, control):
    prefix = f'{node}/attempt-{attempt}'
    capture = evidence.raw(prefix + '.captured.json')
    content = decode(capture)
    common_raw = evidence.raw(prefix + '.common.json')
    common = decode(common_raw)
    envelope_raw = evidence.raw(prefix + '.envelope.json')
    require(_payload(envelope_raw) == capture, 'Input envelope differs from captured bytes')
    raw = common['a2_raw_shared_bundle']
    require(len(raw['use_records']) == 1, 'Nonunique current use')
    use = raw['use_records'][0]
    claim = 'CLAIM_' + sha(envelope_raw)
    require(use['exact_claim_version_id'] == claim
            and use['episode_id'] == evidence.events[0]['episode'], 'Current use identity mismatch')
    require(use['purpose_id'] == 'PURPOSE_' + evidence.world['task'].upper()
            and use['scope_id'] == 'SCOPE_SYNTHETIC', 'Current use outside registered domain')
    parent_event = evidence.one('PARENTS_CAPTURED', node, attempt)
    parents = parent_event['parents']
    require(tuple(p['node'] for p in parents) == expected_parents, 'Wrong actual parent set/order')
    require(type(content) is dict and set(content) == {'parents', 'groups'}, 'Invalid receiver input')
    require(tuple(p['id'] for p in content['parents']) == expected_parents, 'Input parents differ')
    increment_names = ({'R1': 'BCD'} if evidence.world['topology'] == 'direct' else
                       {'R1': 'B', 'R2': 'C', 'R3': 'D', 'R4': ''})[node]
    require(content['groups'] == {g: evidence.world['groups'][g] for g in increment_names},
            'Receiver increments differ from original groups')
    mismatched_parent, input_errors, registrations = False, [], []
    for row, supplied in zip(parents, content['parents']):
        name = row['node']
        require(name in models and models[name]['parsed'] is not None, 'Unobserved parent output')
        registered = evidence.raw(row['registered_path'])
        delivered = evidence.raw(row['delivered_path'])
        payload = _payload(delivered)
        require(sha(registered) == row['registered_sha256']
                and sha(delivered) == row['envelope_sha256']
                and sha(payload) == row['payload_sha256'], 'Parent capture hash mismatch')
        original_name = 'SOURCE.control-envelope.json' if name == 'SOURCE' and control else name + '.answer-envelope.json'
        require(registered == evidence.raw(original_name), 'Registration differs from actual prior output')
        require(_payload(registered) == payload == supplied['payload'].encode('utf-8'),
                'Parent payload altered or omitted from receiver input')
        mismatched_parent |= sha(registered) != sha(delivered)
        registrations.append('PARENT_' + sha(registered))
        if parse_answer(payload, evidence.world['task']) != oracle(evidence.world, name):
            input_errors.append(name)
    require(parent_event['expected_parent_refs'] == registrations, 'Expected parent identities changed')
    facts = common['comparison_facts']
    require(facts['expected_direct_parents'] == registrations
            and facts['observed_direct_parents'] == ['PARENT_' + p['envelope_sha256'] for p in parents],
            'COMMON parent facts disagree with captures')
    grant = evidence.one('INGRESS_GRANT_ISSUED', node, attempt)
    invocation = evidence.one('INGRESS_INVOKED', node, attempt)
    effect = evidence.one('INGRESS_EFFECT_RECORDED', node, attempt)
    require(grant['ordinal'] < invocation['ordinal'] < effect['ordinal']
            and invocation['grant_event'] == grant['ordinal']
            and effect['invocation_event'] == invocation['ordinal'], 'Ingress chronology mismatch')
    require(grant['state'] == invocation['pre_invocation_state'] == 'UNUSED'
            and grant['nonce'] == invocation['nonce']
            and invocation['effect_sha256'] == effect['effect_sha256'] == sha(capture),
            'Ingress receipt mismatch')
    ttl = _integer(grant['expires_after_seconds'], 'grant TTL')
    expired = invocation['domain_seconds'] > grant['domain_seconds'] + ttl
    guard = common['guard_observation_facts']
    require(guard['grant_expires_at'] == (grant['domain_seconds'] + ttl) * 1000
            and guard['invocation_time'] == invocation['domain_seconds'] * 1000
            and guard['effect_sha256'] == guard['execution_receipt_effect_sha256'] == sha(capture),
            'COMMON ingress facts disagree with receipts')
    records_raw = evidence.raw(prefix + '.ledger-records.json')
    records = decode(records_raw)
    service = evidence.one('DECLARATION_SERVICE_RESPONSE', node, attempt)
    snapshot = evidence.one('LEDGER_SNAPSHOT_CAPTURED', node, attempt)
    requested = evidence.one('RECEIVER_RELIANCE_REQUESTED', node, attempt)
    closure = evidence.one('FINITE_HISTORY_CLOSED', node, attempt)
    require(service['complete_local_history'] is True
            and service['ledger_scope'] == 'THIS_EPISODE_RECEIVER', 'Missing complete local history')
    require(service['records_sha256'] == snapshot['records_sha256'] == sha(records_raw), 'Ledger hash mismatch')
    require(service['ordinal'] < snapshot['ordinal'] < requested['ordinal'] < closure['ordinal']
            and closure['snapshot_event'] == snapshot['ordinal']
            and _instant(closure['through']) >= _instant(requested['domain_at']), 'Ledger chronology mismatch')
    require(use['occurred_at'] == requested['domain_at'] and requested['exact_claim'] == claim
            and requested['receiver'] == use['receiver_capability_id'], 'Use event mismatch')
    require(raw['declaration_records'] == records['declarations']
            and raw['domain_mandate_records'] == records['mandates']
            and use['declared_basis_refs'] == records['declared_basis_refs'], 'COMMON ledger differs from records')
    require(len(raw['ledger_observations']) == 1
            and raw['ledger_observations'][0]['included_record_refs'] == records['included_refs']
            and raw['ledger_observations'][0]['captured_at'] == snapshot['domain_at'], 'Snapshot fields mismatch')
    declarations = {}
    for row in records['declarations']:
        ref = row['declaration_version_ref']
        require(ref not in declarations, 'Duplicate declaration identity')
        declarations[ref] = row
    require(len(records['included_refs']) == len(set(records['included_refs']))
            and set(records['included_refs']) == set(declarations), 'Incomplete declaration frontier')
    basis = records['declared_basis_refs']
    require(type(basis) is list and len(basis) <= 1, 'Current basis outside registered domain')
    selected = [declarations[ref] for ref in basis if ref in declarations
                and declarations[ref]['declaration_kind'] == 'ADOPTION_DECLARED']
    absent = not selected
    wrong_scope = any(row['scope_id'] != use['scope_id'] for row in selected)
    for row in selected:
        for key in ('episode_id', 'exact_claim_version_id', 'receiver_capability_id', 'purpose_id'):
            require(row[key] == use[key], 'Current adoption exact-use mismatch: ' + key)
        require(row['policy_ref'] == 'POLICY_SHARED_0_1'
                and _instant(row['recorded_at']) <= _instant(use['occurred_at'])
                and _instant(row['interval']['effective_from']) <= _instant(use['occurred_at'])
                <= _instant(row['interval']['effective_until']), 'Adoption outside normal time/policy domain')
    decision = evidence.one('DECISION_OBSERVED', node, attempt)
    require(closure['ordinal'] < decision['ordinal'], 'Decision precedes evidence closure')
    receipt = evidence.obj(prefix + '.decision-observation.json')
    binding = evidence.obj(prefix + '.binding.json')
    decision_raw = base64.b64decode(receipt['output_b64'], validate=True)
    observed = decode(decision_raw)
    require(sha(decision_raw) == decision['output_sha256'] == receipt['output_sha256'] == binding['output_sha256'],
            'Decision receipt mismatch')
    require(receipt['common_sha256'] == binding['common_sha256'] == sha(common_raw)
            and binding['status'] == 'EXACT_INVOCATION_OBSERVED', 'Unbound decision invocation')
    require(observed['disposition'] == decision['disposition'], 'Decision disposition mismatch')
    _witness(common_raw,evidence.raw('state.json'),receipt,observed,decision,binding)
    phenotype = {'acceptance_absent': absent, 'acceptance_wrong_scope': wrong_scope,
                 'ingress_expired': expired, 'parent_version': mismatched_parent}
    return {'phenotypes': phenotype, 'semantic_input_error': bool(input_errors),
            'wrong_parent_nodes': input_errors, 'capture': capture, 'common_raw': common_raw,
            'use': use, 'decision': decision, 'prefix': prefix}


def _score(path):
    evidence = Evidence(path)
    world = evidence.world
    plans = graph(world)
    oracle(world)
    request_nodes = [row['node'] for row in evidence.find('MODEL_REQUEST')]
    require(len(request_nodes) == len(set(request_nodes))
            and set(request_nodes) <= {'SOURCE', *plans} and 'SOURCE' in request_nodes,
            'Model call census outside structural cap')
    models = {node: _model(evidence, node) for node in request_nodes}
    source_messages = models['SOURCE']['request']['messages']
    require(len(source_messages) == 2 and source_messages[1]['role'] == 'user'
            and decode(source_messages[1]['content']) == {'groups': {'A': world['groups']['A']}},
            'Source input differs from original group A')
    controls = evidence.find('SOURCE_CONTROL_RECORDED')
    require(len(controls) <= 1, 'Duplicate source control')
    control = bool(controls)
    if control:
        row = controls[0]
        answer = evidence.raw('SOURCE.control-answer.json')
        env = evidence.raw('SOURCE.control-envelope.json')
        require(sha(answer) == row['answer_sha256'] and sha(env) == row['envelope_sha256']
                and _payload(env) == answer and row['original_answer_sha256'] ==
                sha(evidence.raw('SOURCE.answer.json')), 'Source control capture mismatch')
        parse_answer(answer, world['task'])
    caps = evidence.find('EPISODE_CAP_REACHED')
    require(len(caps) <= 1, 'Duplicate episode cap')
    for cap in caps:
        require(cap['cap_seconds'] == 1200 and _integer(cap['elapsed_ns'], 'cap elapsed') >= 1200 * 10**9,
                'Invalid episode cap observation')
    presentations, attempts, ancestry = [], [], {}
    held_count = cancelled_count = retry_count = 0
    for node, parent_nodes in plans.items():
        presented = evidence.find('RECEIVER_PRESENTED', node)
        held = evidence.find('RECEIVER_HELD', node)
        cancelled = evidence.find('RECEIVER_CANCELLED', node)
        require(len(presented) + len(held) + len(cancelled) == 1, 'Missing/duplicate receiver terminal: ' + node)
        request_rows = evidence.find('RECEIVER_RELIANCE_REQUESTED', node)
        attempt_ids = [r['attempt'] for r in request_rows]
        require(attempt_ids in ([], [0], [0, 1]), 'Unregistered attempt sequence')
        details = [_attempt(evidence, node, attempt, parent_nodes, models, control) for attempt in attempt_ids]
        attempts.extend({'node': node, 'attempt': attempt, 'phenotypes': item['phenotypes']}
                        for attempt, item in zip(attempt_ids, details))
        refresh = evidence.find('REFRESH_REQUESTED', node)
        require(len(refresh) <= 1, 'Multiple refetches at node')
        retry_count += len(refresh)
        if len(details) == 2:
            require(len(refresh) == 1 and details[0]['decision']['disposition'] != 'PASS'
                    and details[0]['decision']['ordinal'] < refresh[0]['ordinal'] < request_rows[1]['ordinal'],
                    'Refetch without first non-PASS')
            require(details[0]['capture'] == details[1]['capture'], 'Refetch changed original model input')
            for key in ('episode_id', 'exact_claim_version_id', 'receiver_capability_id', 'purpose_id',
                        'scope_id', 'action_or_decision_ref', 'decision_context_ref'):
                require(details[0]['use'][key] == details[1]['use'][key], 'Refetch changed original use context')
        if held:
            held_count += 1
            require(attempt_ids == [0, 1] and details[-1]['decision']['disposition'] != 'PASS'
                    and node not in models, 'Hold without two rejected pre-use attempts')
        if cancelled:
            cancelled_count += 1
            require(node not in models, 'Cancelled node made model call')
            reason = cancelled[0]['reason']
            if reason == 'EPISODE_WALL_CAP':
                require(bool(caps) and caps[0]['ordinal'] < cancelled[0]['ordinal'], 'Unwitnessed cap cancellation')
            else:
                require(reason == 'MISSING_PARENT_OUTPUT'
                        and any(p not in models or models[p]['parsed'] is None for p in parent_nodes),
                        'Cancellation without missing parent')
        if presented:
            row = presented[0]
            require(node in models and row['attempt'] in attempt_ids, 'Presentation lacks observed model/attempt')
            item = details[attempt_ids.index(row['attempt'])]
            require(row['attempt'] == attempt_ids[-1] and item['decision']['disposition'] == 'PASS',
                    'Presentation without final PASS')
            release = evidence.raw(item['prefix'] + '.released.json')
            require(release == item['capture'] and sha(release) == row['content_sha256']
                    and sha(item['common_raw']) == row['common_sha256']
                    and row['state_sha256']==sha(evidence.raw('state.json')), 'Presentation bytes mismatch')
            messages = models[node]['request']['messages']
            require(len(messages) == 2 and messages[1]['role'] == 'user'
                    and messages[1]['content'].encode('utf-8') == release,
                    'Actual model request differs from presentation')
            require(item['decision']['ordinal'] < row['ordinal']
                    < evidence.one('MODEL_REQUEST', node)['ordinal'], 'Presentation chronology mismatch')
            ancestors = set()
            for parent in parent_nodes:
                ancestors.update(ancestry.get(parent, set()))
                if any(p['node'] == parent and p['structural_error'] for p in presentations):
                    ancestors.add(parent)
            ancestry[node] = ancestors
            presentations.append({'node': node, 'attempt': row['attempt'],
                'phenotypes': item['phenotypes'], 'structural_error': any(item['phenotypes'].values()),
                'semantic_input_error': item['semantic_input_error'],
                'wrong_parent_nodes': item['wrong_parent_nodes'],
                'defective_presentation_ancestors': sorted(ancestors)})
    require(set(request_nodes) == {'SOURCE', *(p['node'] for p in presentations)}, 'Model/presentation census mismatch')
    complete = all(node in models and models[node]['parsed'] is not None for node in plans)
    final = list(plans)[-1]
    final_correct = final in models and models[final]['parsed'] is not None and models[final]['parsed'] == oracle(world)
    require(evidence.events[-1]['status'] == ('COMPLETED' if final in models and models[final]['parsed'] is not None
                                            else 'NOT_COMPLETED'), 'Terminal status contradicts observed final output')
    times = [e['wall_at_ns'] for e in evidence.events]
    require(all(a <= b for a, b in zip(times, times[1:])), 'Wall clock moved backwards')
    return {'status': 'VALID', 'Y': sum(p['structural_error'] for p in presentations),
        'correct_completion': int(complete and final_correct and not caps),
        'trajectory_complete': int(complete), 'final_answer_correct': bool(final_correct),
        'presentations': len(presentations), 'presentation_cap': len(plans),
        'presentation_details': presentations, 'attempt_details': attempts,
        'phenotype_counts': {key: sum(p['phenotypes'][key] for p in presentations) for key in
            ('acceptance_absent', 'acceptance_wrong_scope', 'ingress_expired', 'parent_version')},
        'semantic_input_errors': sum(p['semantic_input_error'] for p in presentations),
        'semantic_output_errors': sum(m['semantic_output_error'] for name, m in models.items() if name != 'SOURCE'),
        'source_semantic_output_error': models['SOURCE']['semantic_output_error'],
        'invalid_model_outputs': sum(m['invalid_output'] for m in models.values()),
        'presented_descendants': sum(bool(p['defective_presentation_ancestors']) for p in presentations),
        'refusals': held_count, 'cancelled_receivers': cancelled_count, 'retries': retry_count,
        'classification_attempts': len(attempts), 'model_calls': len(models),
        'model_call_cap': 1 + len(plans), 'classification_attempt_cap': 2 * len(plans),
        'episode_cap_reached': bool(caps), 'token_cap_hits': sum(m['token_cap_hit'] for m in models.values()),
        'episode_wall_ns': times[-1] - times[0],
        'model_wall_ns': sum(m['model_wall_ns'] for m in models.values()),
        'prompt_tokens': sum(m['prompt_tokens'] for m in models.values()),
        'output_tokens': sum(m['output_tokens'] for m in models.values())}


def score_episode(path):
    """Return VALID endpoints or INVALID reason; never substitute zeros for missingness."""
    try:
        return _score(path)
    except (MeasurementFailure, OSError, ValueError, TypeError, KeyError, IndexError,
            UnicodeError, RecursionError) as error:
        return {'status': 'INVALID', 'reason': f'{type(error).__name__}: {error}'}
