"""Frozen source-anchored smoke cases, distinct retrieval/answer/boundary scores."""
import hashlib
import json
import math
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def normalized(text):
    return ' '.join(text.split()).casefold()


def validate_suite(suite, source_root):
    """Validate local source bytes and labels before any HTTP/model request."""
    cases = suite['cases']
    if not 20 <= len(cases) <= 30 or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Acceptance needs 20–30 unique frozen cases')
    pins = {pin['document_id']: pin for pin in suite['sources']}
    if len(pins) != len(suite['sources']) or not pins:
        raise ValueError('Source pins must be unique and nonempty')
    root = Path(source_root).resolve()
    texts = {}
    for key, pin in pins.items():
        path = (root / pin['relative_path']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Source pin escapes the fixed corpus')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != pin['content_hash']:
            raise ValueError('Frozen source bytes changed')
        texts[key] = normalized(data.decode('utf-8'))
    kinds = {'positive', 'unanswerable', 'boundary', 'chat', 'receipt'}
    for case in cases:
        if case['category'] not in kinds or not case['query'].strip():
            raise ValueError('Invalid case category or empty question')
        units = case.get('gold_units', [])
        if case['category'] == 'positive' and (not units or not case.get('answer_terms')):
            raise ValueError('A positive case needs source anchors and answer facts')
        if case['category'] != 'positive' and units:
            raise ValueError('Only answerable cases have gold evidence')
        for unit in units:
            pin = pins.get(unit['document_id'])
            if (pin is None or unit['document_version'] != pin['document_version']
                    or not unit['anchor'].strip()
                    or normalized(unit['anchor']) not in texts[unit['document_id']]):
                raise ValueError('Gold evidence must exist in the pinned original source')
        if any(not term.strip() for term in case.get('answer_terms', [])):
            raise ValueError('Expected facts must not be empty')
    if {c['category'] for c in cases} != kinds:
        raise ValueError('All five acceptance categories must be present')
    for key, value in suite['gates'].items():
        if not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError('Acceptance gates must be finite rates')
    return digest(suite)


def matches(unit, candidate):
    source = candidate.get('source', {})
    return (source.get('document_id') == unit['document_id']
            and source.get('document_version') == unit['document_version']
            and normalized(unit['anchor']) in normalized(candidate.get('text', '')))


def gold_ranking(units, candidates):
    ranks = [next((index + 1 for index, candidate in enumerate(candidates)
                   if matches(unit, candidate)), None) for unit in units]
    hit = [rank for rank in ranks if rank is not None]
    return {'unit_count': len(units), 'hit_count': len(hit), 'ranks': ranks,
            'recall': len(hit) / len(units),
            'reciprocal_rank': 1 / min(hit) if hit else 0.0}


def score_knowledge(case, status_code, response, audit, suite):
    checks = {'http_200': status_code == 200}
    receipt = response.get('execution_feedback') or {}
    checks['real_server_receipt'] = bool(receipt.get('request_id'))
    checks['stored_owner_and_tenant'] = bool(audit and audit.get('tenant_id') == suite['tenant_id']
        and audit['run']['actor_user_id'] == 'test' and audit['run']['request_id'] == receipt.get('request_id'))
    raw = (audit or {}).get('raw') or {}
    candidates = raw.get('candidates', [])
    event = raw.get('event', {})
    bundle = response.get('evidence_bundle') or {}
    items = bundle.get('items', [])
    evidence = [{'evidence_id': item['evidence_id'], 'source': item['source'],
                 'text': item['chain']['content']['text']} for item in items]
    # A rejected model answer still has a real completed processing result.
    # Measure that result rather than mistaking a missing answer bundle for lost retrieval.
    if not items and audit:
        processing = next((run for run in audit.get('processing', [])
                           if run['id'] == receipt.get('processing_run_id')), None)
        by_raw_id = {c['candidate_id']: c for c in candidates}
        if processing:
            evidence = [{'evidence_id': id, 'source': by_raw_id[id]['source'], 'text': by_raw_id[id]['text']}
                        for id in processing['selected_candidate_ids'] if id in by_raw_id]
    versions = response.get('runtime_versions') or receipt.get('runtime_versions') or {}
    checks['run_event_processing_binding'] = bool(event and receipt.get('retrieval_event_id') == event['id']
        and receipt.get('processing_run_id') == response.get('processing_run_id')
        and (audit or {}).get('run', {}).get('execution_feedback') == receipt)
    checks['recorded_versions'] = all(versions.get(key) for key in (
        'runtime_fingerprint', 'policy_bundle_version', 'retrieval_profile_version', 'model_revision',
        'parser_version', 'prompt_version', 'processing_configuration_version'))
    checks['pinned_embedding_signature'] = bool(event and digest(event.get('embedding_configuration')) == suite['embedding_signature'])
    by_id = {candidate['candidate_id']: candidate for candidate in candidates}
    checks['raw_content_hashes'] = bool(raw) and all(
        hashlib.sha256(candidate['text'].encode()).hexdigest() == candidate['content_hash'] for candidate in candidates)
    checks['final_candidates_in_raw'] = all(item.get('evidence_id') in by_id and
        item['text'] == by_id[item['evidence_id']]['text'] for item in evidence)
    checks['required_chain_checks'] = (bool(items) or not evidence) and all(all(item['chain']['checks'][name]['status'] == 'pass'
        for name in ('source_identity', 'source_version', 'source_locator', 'content_integrity', 'raw_link')) for item in items)
    citations = response.get('citations', [])
    checks['exact_citations_and_sources'] = all(c['evidence_id'] in by_id and c['quote'].strip()
        and c['quote'] in by_id[c['evidence_id']]['text'] and c['source'] == by_id[c['evidence_id']]['source'] for c in citations)
    result = {'checks': checks, 'raw_candidate_count': len(candidates), 'final_candidate_count': len(evidence)}
    if case['category'] == 'positive':
        raw_rank = gold_ranking(case['gold_units'], candidates)
        final_rank = gold_ranking(case['gold_units'], evidence)
        result.update(raw_gold=raw_rank, final_gold=final_rank)
        answer = normalized(response.get('answer', ''))
        result['missing_answer_terms'] = [term for term in case['answer_terms'] if normalized(term) not in answer]
        checks['answer_status'] = response.get('status') == 'answered'
        checks['answer_contains_expected_facts'] = not result['missing_answer_terms']
        checks['nonempty_checked_citations'] = bool(citations) and response.get('validation') == 'source_and_quote_checked'
        checks['citation_uses_gold_source'] = bool(citations) and all(any(
            c['source'].get('document_id') == unit['document_id'] and c['source'].get('document_version') == unit['document_version']
            for unit in case['gold_units']) for c in citations)
        checks['model_attempted'] = receipt.get('model_call', {}).get('attempted') is True
    else:
        checks['abstains_without_citations'] = (response.get('status') == 'insufficient_evidence'
            and response.get('validation') == 'no_verified_answer' and not citations)
    result['passed'] = all(checks.values())
    model_call = receipt.get('model_call', {})
    result['failure_stage'] = None if result['passed'] else (
        'answer_validation' if model_call.get('error_code') == 'unverified_excerpt_response' else
        'model_dependency' if model_call.get('status') == 'failed' else
        'transport_or_audit' if not all(checks[key] for key in ('http_200', 'real_server_receipt', 'stored_owner_and_tenant')) else
        'raw_retrieval' if case['category'] == 'positive' and result['raw_gold']['recall'] < 1 else
        'final_evidence' if case['category'] == 'positive' and result['final_gold']['recall'] < 1 else 'answer_or_contract')
    return result


def summarize(results, gates):
    def ratio(items, key):
        return sum(bool(row.get(key)) for row in items) / len(items) if items else None
    positive = [row for row in results if row['category'] == 'positive']
    absent = [row for row in results if row['category'] == 'unanswerable']
    boundary = [row for row in results if row['category'] == 'boundary']
    chat = [row for row in results if row['category'] == 'chat']
    receipt = [row for row in results if row['category'] == 'receipt']
    latency = sorted(row['elapsed_seconds'] for row in results if row.get('model_call_attempted'))
    metrics = {'case_pass_rate': ratio(results, 'passed'), 'positive_answer_rate': ratio(positive, 'passed'),
        'abstention_rate': ratio(absent, 'passed'), 'boundary_pass_rate': ratio(boundary, 'passed'),
        'chat_pass_rate': ratio(chat, 'passed'), 'receipt_pass_rate': ratio(receipt, 'passed'),
        'raw_gold_recall_at_20': sum(row.get('raw_gold', {}).get('recall', 0) for row in positive) / len(positive) if positive else None,
        'final_gold_recall_at_5': sum(row.get('final_gold', {}).get('recall', 0) for row in positive) / len(positive) if positive else None,
        'raw_gold_mrr_at_20': sum(row.get('raw_gold', {}).get('reciprocal_rank', 0) for row in positive) / len(positive) if positive else None,
        'model_attempted_cases': len(latency), 'estimated_cost': None,
        'cost_note': 'Provider usage/cost is not exposed by the current answer contract',
        'latency_p50_seconds': latency[math.ceil(len(latency)*.5)-1] if latency else None,
        'latency_p95_seconds': latency[math.ceil(len(latency)*.95)-1] if latency else None}
    gate_results = {name: metrics.get(name) is not None and metrics[name] >= value for name, value in gates.items()}
    return {'metrics': metrics, 'gate_results': gate_results, 'gates_passed': all(gate_results.values())}
