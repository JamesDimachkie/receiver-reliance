"""Frozen VitaminC follow-up. Standard library; run with Python -B."""
from __future__ import annotations
import base64
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / 'rr-jev-feasibility'
sys.path.insert(0, str(PREVIOUS))
import pilot as p

SEED = 'rr-jev-vitc-20260915-v1'
DATA_HASH = '7ad1808dbc30c62e0a1427a53022d0dfaff668a1fde3c4b612a2d266edd753ad'
MAP = {'SUPPORTS': 'supports', 'REFUTES': 'contradicts', 'NOT ENOUGH INFO': 'insufficient'}
MAX_CALLS = 240
MAX_BYTES = 1_000_000

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write(path, obj):
    p.write_json(HERE / path, obj)

def digest(path):
    return p.sha(Path(path).read_bytes())

def study_hashes():
    paths = ['PROTOCOL.md', 'study.py', 'selected.json', 'episodes.json', 'request-plan.json', 'LICENSE-DATA.txt']
    result = {name: digest(HERE / name) for name in paths}
    for name in ('pilot.py', 'cases.py', 'freeze.json'):
        result['../rr-jev-feasibility/' + name] = digest(PREVIOUS / name)
    return result

def state(row, revision):
    return dict(claim=row['claim'], source=row['evidence'], source_revision=revision,
                artifact_revision=1, purpose='PURPOSE_SUMMARY')

def prepare():
    if (HERE / 'freeze.json').exists():
        raise RuntimeError('Already frozen')
    p.verify_freeze()
    data_path = HERE.parent.parent / 'work/vitaminc/test.jsonl'
    assert digest(data_path).lower() == DATA_HASH
    groups = defaultdict(list)
    for line in data_path.read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row['revision_type'] == 'real':
            groups[(row['case_id'], row['claim'])].append(row)
    eligible = []
    for (case_id, claim), rows in groups.items():
        if len(rows) != 2 or len({r['page'] for r in rows}) != 1 or len({r['evidence'] for r in rows}) != 2:
            continue
        labels = {r['label'] for r in rows}
        if labels not in ({'SUPPORTS', 'REFUTES'}, {'SUPPORTS', 'NOT ENOUGH INFO'}):
            continue
        if any(len(r['evidence']) > 6000 for r in rows):
            continue
        rank = p.sha((SEED + '\0' + case_id + '\0' + claim).encode())
        eligible.append((rank, rows))
    selected, pages, quotas = [], set(), Counter()
    for rank, rows in sorted(eligible):
        support = next(r for r in rows if r['label'] == 'SUPPORTS')
        negative = next(r for r in rows if r['label'] != 'SUPPORTS')
        label = negative['label']
        if support['page'] in pages or quotas[label] == 60:
            continue
        pages.add(support['page'])
        quotas[label] += 1
        selected.append(dict(pair_id=rank[:20], support=support, negative=negative))
        if len(selected) == 120:
            break
    assert len(selected) == 120 and set(quotas.values()) == {60}
    episodes, requests = [], {}
    for pair in selected:
        for direction, initial_name, current_name in (
            ('support_to_negative', 'support', 'negative'),
            ('negative_to_support', 'negative', 'support'),
            ('unchanged_support', 'support', 'support'),
            ('unchanged_negative', 'negative', 'negative')):
            changed = initial_name != current_name
            initial = state(pair[initial_name], 1)
            current = state(pair[current_name], 2 if changed else 1)
            episodes.append(dict(id=pair['pair_id'] + '__' + direction, pair_id=pair['pair_id'],
                transition='source_contradicts' if changed else 'unchanged', direction=direction,
                initial=initial, current=current, gold=MAP[pair[current_name]['label']],
                may_reissue=True, expected_initial_structural=not changed, expected_final_structural=True))
            for value in (initial, current):
                request = p.request_for(value)
                requests[p.fingerprint(request)] = request
    keys = sorted(requests)
    random.Random(SEED).shuffle(keys)
    assert len(keys) == MAX_CALLS
    plan = [{'sha256': key, 'request': requests[key]} for key in keys]
    assert sum(len(p.canonical(x['request'])) for x in plan) <= MAX_BYTES
    write('selected.json', selected)
    write('episodes.json', episodes)
    write('request-plan.json', plan)
    print(json.dumps(dict(pairs=len(selected), pages=len(pages), episodes=len(episodes), requests=len(plan),
                         quotas=quotas, submitted_bytes=sum(len(p.canonical(x['request'])) for x in plan))))

def qualify():
    rows = []
    # Four pairs, two per negative stratum. Real RR and fractional API-shaped data.
    selected, chosen, quota = read(HERE / 'selected.json'), set(), Counter()
    for pair in selected:
        label = pair['negative']['label']
        if quota[label] < 2:
            chosen.add(pair['pair_id']); quota[label] += 1
    stub = {'model': 'qualification-fixture', 'usage': {'input_tokens': 10}, 'answers': {'support': {
        'type': 'choice', 'choice': 'supports', 'confidence': .95,
        'probabilities': {'supports': .98, 'contradicts': .01, 'insufficient': .01}}}}
    bank = {x['sha256']: {'response': stub} for x in read(HERE / 'request-plan.json')}
    for case in read(HERE / 'episodes.json'):
        if case['pair_id'] not in chosen:
            continue
        for refreshed in (False, True):
            assessment = p.assessment_for(case['current' if refreshed else 'initial'], bank)
            common = p.make_common(case, assessment, refreshed=refreshed)
            rr, code, _ = p.actual_rr(common, HERE / 'qualification/traces', case['id'] + str(refreshed))
            conventional, reason = p.conventional(common)
            expected = True if refreshed else case['expected_initial_structural']
            payload = json.loads(base64.b64decode(json.loads(common)['delivered_artifact_envelope']['content_b64']))
            assert json.loads(payload['assessment']['answer_json']) == stub['answers']['support']
            rows.append(dict(case=case['id'], refreshed=refreshed, rr=rr, conventional=conventional,
                             expected=expected, rr_code=code, conventional_reason=reason))
    assert len(rows) == 32 and all(r['rr'] == r['conventional'] == r['expected'] for r in rows)
    write('qualification/result.json', dict(at=p.now(), rows=rows, study_hashes=study_hashes(), rr_hashes=p.source_hashes()))
    print(json.dumps(dict(qualified=len(rows), passed=True)))

def freeze():
    if (HERE / 'freeze.json').exists() or (HERE / 'live/attempts.jsonl').exists():
        raise RuntimeError('Do not replace frozen study')
    qualification = read(HERE / 'qualification/result.json')
    assert qualification['study_hashes'] == study_hashes()
    assert qualification['rr_hashes'] == p.source_hashes()
    assert (HERE / 'REVIEW.md').exists()
    write('freeze.json', dict(at=p.now(), local_pre_outcome=True, study_hashes=study_hashes(), rr_hashes=p.source_hashes(),
        qualification_sha256=digest(HERE / 'qualification/result.json'), review_sha256=digest(HERE / 'REVIEW.md'),
        data_sha256=DATA_HASH, max_post_attempts=MAX_CALLS, max_submitted_bytes=MAX_BYTES, python=sys.version))
    print('Frozen 120 pairs, 240 requests and 480 episodes before inference.')

def verify_freeze():
    frozen = read(HERE / 'freeze.json')
    assert frozen['study_hashes'] == study_hashes()
    assert frozen['rr_hashes'] == p.source_hashes()
    assert frozen['qualification_sha256'] == digest(HERE / 'qualification/result.json')
    assert frozen['review_sha256'] == digest(HERE / 'REVIEW.md')
    p.verify_freeze()
    return frozen

def collect():
    verify_freeze()
    key = os.environ.pop('TYPESAFE_API_KEY', '').strip()
    if len(key) < 16 or any(c.isspace() for c in key) or key.startswith(('http', '{')):
        raise RuntimeError('A single local TypeSafe API key is required; value not shown')
    live = HERE / 'live'
    live.mkdir(exist_ok=True)
    log = live / 'attempts.jsonl'
    if log.exists():
        raise RuntimeError('Existing attempts; no automatic resumption or retry')
    def send(method, path, body=None):
        connection = http.client.HTTPSConnection('api.typesafe.ai', timeout=30)
        try:
            connection.request(method, path, body=body,
                headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
            response = connection.getresponse()
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise RuntimeError('Response exceeds cap')
            return response.status, raw.decode('utf-8').replace(key, '[REDACTED]')
        finally:
            connection.close()
    status, raw = send('GET', '/v1/models')
    if status != 200:
        raise RuntimeError('Model discovery HTTP ' + str(status))
    models = json.loads(raw)
    assert p.MODEL in {m['name'] for m in models['models']}
    write('live/models.json', dict(at=p.now(), response=models, raw_response_text=raw, raw_response_sha256=p.sha(raw.encode())))
    plan, total_bytes = read(HERE / 'request-plan.json'), 0
    for ordinal, item in enumerate(plan, 1):
        request, request_id = item['request'], item['sha256']
        body = p.canonical(request)
        total_bytes += len(body)
        if ordinal > MAX_CALLS or total_bytes > MAX_BYTES:
            raise RuntimeError('Fixed request budget exceeded')
        attempt = dict(ordinal=ordinal, request_sha256=request_id, started_at=p.now(), submitted_bytes=len(body))
        with log.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(attempt) + '\n'); stream.flush()
        record = {**attempt, 'request': request}
        started = time.perf_counter()
        try:
            status, raw = send('POST', '/v1/systemone', body)
            record.update(http_status=status, seconds=time.perf_counter() - started, raw_response_text=raw,
                          raw_response_sha256=p.sha(raw.encode()), completed_at=p.now())
            if status != 200:
                raise RuntimeError('HTTP ' + str(status))
            record['response'] = json.loads(raw)
            p.validate_response(record['response'])
            record['valid'] = True
        except Exception as exc:
            record.update(valid=False, error=type(exc).__name__, completed_at=p.now())
            write('live/' + request_id + '.json', record)
            raise RuntimeError('Stopped on retained attempt ' + str(ordinal)) from None
        write('live/' + request_id + '.json', record)
        if ordinal % 20 == 0:
            print(json.dumps(dict(collected=ordinal, of=len(plan))), flush=True)
    key = ''

def load_bank():
    plan = read(HERE / 'request-plan.json')
    attempts = [json.loads(x) for x in (HERE / 'live/attempts.jsonl').read_text().splitlines()]
    assert len(attempts) == len(plan) == MAX_CALLS
    assert sum(x['submitted_bytes'] for x in attempts) <= MAX_BYTES
    result = {}
    for ordinal, (item, attempt) in enumerate(zip(plan, attempts), 1):
        key, request = item['sha256'], item['request']
        record = read(HERE / ('live/' + key + '.json'))
        assert attempt['ordinal'] == ordinal and attempt['request_sha256'] == key
        assert record['valid'] is True and record['http_status'] == 200
        assert p.fingerprint(request) == key and record['request'] == request
        assert json.loads(record['raw_response_text']) == record['response']
        assert p.sha(record['raw_response_text'].encode()) == record['raw_response_sha256']
        p.validate_response(record['response'])
        result[key] = record
    return result

def wilson(k, n):
    z = 1.959963984540054
    den = 1 + z*z/n
    center = (k/n + z*z/(2*n))/den
    margin = z*math.sqrt(k/n*(1-k/n)/n + z*z/(4*n*n))/den
    return [max(0, center-margin), min(1, center+margin)]

def analyze():
    verify_freeze()
    bank, pairs = load_bank(), read(HERE / 'selected.json')
    semantic, pair_results = [], []
    for pair in pairs:
        two = []
        for kind in ('support', 'negative'):
            row = pair[kind]
            key = p.fingerprint(p.request_for(state(row, 1)))
            answer = bank[key]['response']['answers']['support']
            record = dict(pair_id=pair['pair_id'], unique_id=row['unique_id'], page=row['page'], kind=kind,
                gold=MAP[row['label']], predicted=answer['choice'], correct=answer['choice'] == MAP[row['label']],
                p_support=answer['probabilities']['supports'], confidence=answer['confidence'],
                release=p.sufficient(answer), request_sha256=key, answer=answer,
                claim=row['claim'], evidence=row['evidence'])
            semantic.append(record); two.append(record)
        pair_results.append(dict(pair_id=pair['pair_id'], both_correct=all(r['correct'] for r in two),
            prediction_changes=two[0]['predicted'] != two[1]['predicted'],
            support_probability_drop=two[0]['p_support'] - two[1]['p_support'],
            release_correct_both=two[0]['release'] and not two[1]['release']))
    write('results/semantic.json', semantic)
    write('results/pairs.json', pair_results)
    rows = []
    for index, case in enumerate(read(HERE / 'episodes.json'), 1):
        assessment = p.assessment_for(case['initial'], bank)
        initial_answer = json.loads(assessment['answer_json'])
        for arm in ('rr', 'conventional'):
            selected_assessment, refreshed = assessment, False
            common = p.make_common(case, assessment)
            calls = [p.fingerprint(p.request_for(case['initial']))]
            rr_seconds = 0.
            phases = []
            for phase in ('initial', 'refreshed'):
                if arm == 'rr':
                    valid, reason, elapsed = p.actual_rr(common, HERE / 'results/rr-traces', case['id'] + '_' + phase)
                    rr_seconds += elapsed
                else:
                    valid, reason = p.conventional(common)
                phases.append(dict(phase=phase, valid=valid, reason=reason))
                if valid or phase == 'refreshed':
                    break
                refreshed = True
                selected_assessment = p.assessment_for(case['current'], bank)
                calls.append(p.fingerprint(p.request_for(case['current'])))
                common = p.make_common(case, selected_assessment, refreshed=True)
            released = valid and p.sufficient(json.loads(selected_assessment['answer_json']))
            presentation_hash = None
            if released:
                artifact = base64.b64decode(json.loads(common)['delivered_artifact_envelope']['content_b64'])
                payload = json.loads(artifact)
                assert payload['claim'] == case['current']['claim']
                assert payload['source_sha256'] == p.sha(case['current']['source'].encode())
                assert payload['source_revision'] == case['current']['source_revision']
                assert payload['intended_use'] == case['current']['purpose']
                assert payload['assessment'] == p.assessment_for(case['current'], bank)
                presentation_hash = p.sha(artifact)
                destination = HERE / 'results/presentations' / (case['id'] + '_' + arm + '.json')
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(artifact)
            rows.append(dict(case=case['id'], pair_id=case['pair_id'], direction=case['direction'], arm=arm,
                gold=case['gold'], structural=valid, phases=phases, released=released,
                unsupported_release=released and case['gold'] != 'supports',
                withheld_support=not released and case['gold'] == 'supports', refreshed=refreshed,
                logical_checks=len(calls), logical_input_tokens=sum(bank[x]['response']['usage']['input_tokens'] for x in calls),
                rr_worker_seconds=rr_seconds, presentation_sha256=presentation_hash))
        stale_release = p.sufficient(initial_answer)
        rows.append(dict(case=case['id'], pair_id=case['pair_id'], direction=case['direction'], arm='stale_cache_diagnostic',
            gold=case['gold'], released=stale_release, unsupported_release=stale_release and case['gold'] != 'supports',
            withheld_support=not stale_release and case['gold'] == 'supports', refreshed=False, logical_checks=1,
            logical_input_tokens=bank[p.fingerprint(p.request_for(case['initial']))]['response']['usage']['input_tokens']))
        if index % 80 == 0:
            print(json.dumps(dict(episodes_evaluated=index, of=480)), flush=True)
    write('results/episodes.json', rows)
    totals = {}
    for arm in ('rr', 'conventional', 'stale_cache_diagnostic'):
        subset = [r for r in rows if r['arm'] == arm]
        fields = ['released', 'unsupported_release', 'withheld_support', 'refreshed', 'logical_checks', 'logical_input_tokens']
        totals[arm] = dict(episodes=len(subset), **{field: sum(r[field] for r in subset) for field in fields})
    primary_pairs = list(zip([r for r in rows if r['arm'] == 'rr'], [r for r in rows if r['arm'] == 'conventional']))
    mismatches = [a['case'] for a,b in primary_pairs if (a['released'], a['refreshed'], a['structural']) != (b['released'], b['refreshed'], b['structural'])]
    negatives = [r for r in semantic if r['kind'] == 'negative']
    positives = [r for r in semantic if r['kind'] == 'support']
    false_release = sum(r['release'] for r in negatives)
    withheld = sum(not r['release'] for r in positives)
    confusion = {label: dict(Counter(r['predicted'] for r in semantic if r['gold'] == label)) for label in MAP.values()}
    thresholds = {str(t): dict(unsupported_release=sum(r['predicted']=='supports' and r['p_support']>=t and r['confidence']>=.8 for r in negatives),
        withheld_support=sum(not (r['predicted']=='supports' and r['p_support']>=t and r['confidence']>=.8) for r in positives)) for t in (.5,.8,.9,.95,.99)}
    drops = [r['support_probability_drop'] for r in pair_results]
    summary = dict(at=p.now(), judgments=len(semantic), correct=sum(r['correct'] for r in semantic), confusion=confusion,
        pairs=len(pairs), both_labels_correct=sum(r['both_correct'] for r in pair_results),
        both_release_decisions_correct=sum(r['release_correct_both'] for r in pair_results),
        prediction_changes=sum(r['prediction_changes'] for r in pair_results),
        support_probability_decreased=sum(d>0 for d in drops), median_support_probability_drop=statistics.median(drops),
        unsupported_releases=false_release, unsupported_examples=len(negatives), unsupported_release_wilson95=wilson(false_release,len(negatives)),
        withheld_support=withheld, supported_examples=len(positives), withheld_support_wilson95=wilson(withheld,len(positives)),
        threshold_diagnostics=thresholds, arms=totals, primary_policy_mismatches=mismatches,
        actual_api_calls=len(bank), actual_submitted_bytes=sum(r['submitted_bytes'] for r in bank.values()),
        actual_input_tokens=sum(r['response']['usage']['input_tokens'] for r in bank.values()),
        returned_models=dict(Counter(r['response']['model'] for r in bank.values())),
        median_http_seconds=statistics.median(r['seconds'] for r in bank.values()),
        max_http_seconds=max(r['seconds'] for r in bank.values()),
        rr_worker_seconds=sum(r.get('rr_worker_seconds',0) for r in rows),
        rr_invocations=len(list((HERE / 'results/rr-traces').glob('*.json'))),
        presentation_files=len(list((HERE / 'results/presentations').glob('*.json'))))
    write('results/summary.json', summary)
    verify_freeze()
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    command = sys.argv[1]
    assert command in ('prepare','qualify','freeze','collect','analyze','verify_freeze')
    globals()[command]()
