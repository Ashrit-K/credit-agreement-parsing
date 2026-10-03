"""Test real retrieval/validation around an injected, source-only fake LLM."""
import json
from types import SimpleNamespace
import pytest
from test_retrieval import inputs
from test_extraction_models import answer
from credit_agreement_extractor.chunking import ChunkArtifact
from credit_agreement_extractor.topic_map import TopicMapArtifact
from credit_agreement_extractor.llm import LlmResponse, LlmError


def artifacts(tmp_path):
    doc, mapped = inputs()
    cp = tmp_path/'chunks.json'; mp = tmp_path/'map.json'
    cp.write_text(json.dumps(doc)); mp.write_text(json.dumps(mapped))
    return (TopicMapArtifact(doc['source_sha256'], mp),
            ChunkArtifact(doc['source_sha256'], tmp_path, cp, 2, 'test', False))


class FakeClient:
    def __init__(self, responses=None, model='deepseek-v4-pro'):
        self.settings = SimpleNamespace(model=model)
        self.responses = responses or [answer()]
        self.calls = []

    def complete(self, system, evidence, **kwargs):
        self.calls.append((system, evidence, kwargs))
        result = self.responses[min(len(self.calls)-1, len(self.responses)-1)]
        if isinstance(result, Exception): raise result
        if isinstance(result, LlmResponse): return result
        return LlmResponse(json.dumps(result), kwargs['model'], 'responses', {}, 0.01,
                           {'status': 'unknown'})


def run(tmp_path, client, **kwargs):
    from credit_agreement_extractor.orchestrator import extract_credit_terms
    mapped, chunks = artifacts(tmp_path)
    return extract_credit_terms(mapped, chunks, client=client,
        output_root=tmp_path/'output', trace_root=tmp_path/'runs', **kwargs)


def test_one_combined_call_persists_and_returns_real_cited_output(tmp_path):
    client = FakeClient()
    result = run(tmp_path, client, model='chosen-model', reasoning_effort='high',
                 debug=True, run_id='stage-d')
    assert len(client.calls) == 1
    system, request, settings = client.calls[0]
    assert 'expert credit' in system.lower()
    assert 'Borrower' in json.dumps(request['evidence'])
    assert 'output_schema' in request
    assert settings['model'] == 'chosen-model' and settings['reasoning_effort'] == 'high'
    assert result['status'] == 'completed' and result['schema_version'] == 1
    assert result['document_id'] == artifacts(tmp_path)[0].source_sha256
    assert result['source_evidence']['#/texts/2']['text'] == 'payable quarterly.'
    saved = list((tmp_path/'output').rglob('document.extraction.json'))
    assert len(saved) == 1 and json.loads(saved[0].read_text()) == result
    manifest = json.loads(saved[0].with_name('manifest.json').read_text())
    assert manifest['status'] == 'completed' and manifest['model'] == 'chosen-model'
    snapshots = list((tmp_path/'runs/stage-d/debug').glob('*.json'))
    assert snapshots
    events = [json.loads(x) for x in (tmp_path/'runs/stage-d/events.jsonl').read_text().splitlines()]
    assert {'D1', 'D2', 'D3', 'D4'} <= {e.get('stage') for e in events}


def test_invalid_output_retries_with_machine_feedback(tmp_path):
    bad = answer(); bad['parties'][0]['evidence_item_ids'] = ['#/texts/999']
    client = FakeClient([bad, answer()])
    assert run(tmp_path, client)['status'] == 'completed'
    assert len(client.calls) == 2
    assert 'validation_feedback' in client.calls[1][1]


def test_validation_retry_is_visible_to_shared_analytics(tmp_path):
    from credit_agreement_extractor.tracing import current_trace, summarize_run
    class Instrumented(FakeClient):
        def complete(self, *a, **k):
            response = super().complete(*a, **k)
            current_trace().event('llm_attempt', {'model': response.model, 'status': 'received',
                'usage': {'input_tokens': 10, 'output_tokens': 10},
                'cost': {'kind': 'estimated', 'amount': 0.001, 'currency': 'USD'}})
            return response
    bad = answer(); bad['parties'][0]['evidence_item_ids'] = ['#/texts/999']
    run(tmp_path, Instrumented([bad, answer()]), run_id='analytics')
    summary = summarize_run('analytics', trace_root=tmp_path/'runs')
    assert summary['request_count'] == 2 and summary['failed_requests'] == 1
    assert summary['retry_requests'] == 1


@pytest.mark.parametrize('error', [ValueError('invalid'), LlmError('busy', retryable=True)])
def test_bounded_failure_does_not_finalize(tmp_path, error):
    # A client ValueError is a configuration failure, not an output retry.
    client = FakeClient([error])
    with pytest.raises((ValueError, LlmError)): run(tmp_path, client, debug=True, run_id='failed')
    assert len(client.calls) == (2 if isinstance(error, LlmError) else 1)
    assert not list((tmp_path/'output').rglob('manifest.json'))
    assert not list((tmp_path/'output').rglob('document.extraction.json'))


def test_invalid_json_retries_only_twice(tmp_path):
    response = LlmResponse('not JSON', 'deepseek-v4-pro', 'responses', {}, 0, {})
    client = FakeClient([response])
    with pytest.raises(ValueError): run(tmp_path, client)
    assert len(client.calls) == 2


def test_auth_and_model_substitution_stop_immediately(tmp_path):
    auth = FakeClient([LlmError('denied', status=403)])
    with pytest.raises(LlmError): run(tmp_path, auth)
    assert len(auth.calls) == 1
    wrong = FakeClient([LlmResponse('{}', 'wrong-model', 'responses', {}, 0, {})])
    with pytest.raises(LlmError, match='model'): run(tmp_path, wrong)
    assert len(wrong.calls) == 1


def test_requested_api_style_is_checked_and_effective_style_saved(tmp_path):
    wrong = FakeClient([LlmResponse(json.dumps(answer()), 'deepseek-v4-pro', 'responses', {}, 0, {})])
    with pytest.raises(LlmError, match='API'): run(tmp_path, wrong, api_style='chat_completions')
    assert len(wrong.calls) == 1
    run(tmp_path, FakeClient(), api_style='responses')
    manifest = json.loads(next((tmp_path/'output').rglob('manifest.json')).read_text())
    assert manifest['api_style'] == 'responses'


def test_substituted_model_counts_as_failed_received_call(tmp_path):
    from credit_agreement_extractor.tracing import current_trace, summarize_run
    class Substituted(FakeClient):
        def complete(self, *a, **k):
            current_trace().event('llm_attempt', {'model': 'wrong-model', 'status': 'received',
                'usage': {'input_tokens': 1, 'output_tokens': 1}, 'cost': {}})
            return LlmResponse('{}', 'wrong-model', 'responses', {}, 0, {})
    with pytest.raises(LlmError): run(tmp_path, Substituted(), run_id='substitution')
    assert summarize_run('substitution', trace_root=tmp_path/'runs')['failed_requests'] == 1


def test_stale_map_fails_before_model(tmp_path):
    from credit_agreement_extractor.orchestrator import extract_credit_terms
    mapped, chunks = artifacts(tmp_path)
    data = json.loads(mapped.topic_map_json_path.read_text()); data['chunks_document_sha256'] = 'bad'
    mapped.topic_map_json_path.write_text(json.dumps(data)); client = FakeClient()
    with pytest.raises(ValueError):
        extract_credit_terms(mapped, chunks, client=client, output_root=tmp_path/'output',
                            trace_root=tmp_path/'runs')
    assert client.calls == []


def test_empty_map_is_explicit_missing_no_call(tmp_path):
    from credit_agreement_extractor.orchestrator import extract_credit_terms
    mapped, chunks = artifacts(tmp_path)
    data = json.loads(mapped.topic_map_json_path.read_text())
    data['topics'] = {k: [] for k in data['topics']}
    mapped.topic_map_json_path.write_text(json.dumps(data)); client = FakeClient()
    result = extract_credit_terms(mapped, chunks, client=client,
        output_root=tmp_path/'output', trace_root=tmp_path/'runs')
    assert client.calls == [] and result['parties'] == [] and result['issues']


def test_repeated_run_id_preserves_completed_output(tmp_path):
    client = FakeClient()
    run(tmp_path, client, run_id='same')
    saved = next((tmp_path/'output').rglob('document.extraction.json'))
    original = saved.read_bytes()
    run(tmp_path, client, run_id='same')
    assert len(list((tmp_path/'output').rglob('manifest.json'))) == 2
    assert saved.read_bytes() == original


def test_inputs_are_unchanged_and_basic_traces_exist(tmp_path):
    from credit_agreement_extractor.orchestrator import extract_credit_terms
    mapped, chunks = artifacts(tmp_path)
    before = [p.read_bytes() for p in (mapped.topic_map_json_path, chunks.chunks_json_path)]
    extract_credit_terms(mapped, chunks, client=FakeClient(), output_root=tmp_path/'output',
                         run_id='basic', trace_root=tmp_path/'runs')
    assert [p.read_bytes() for p in (mapped.topic_map_json_path, chunks.chunks_json_path)] == before
    assert (tmp_path/'runs/basic/events.jsonl').exists()
    assert not (tmp_path/'runs/basic/debug').exists()


@pytest.mark.parametrize('use_hierarchy', [False, True])
def test_stage_d_works_with_real_a_b_artifacts_in_both_modes(tmp_path, use_hierarchy):
    from credit_agreement_extractor import convert_document, build_chunks, reflect_topics, build_topic_map, extract_credit_terms
    from test_conversion import RecordingConverter
    from test_optional_hierarchy import source_file, OfflineClient
    conversion = convert_document(source_file(tmp_path), tmp_path/'a',
        use_hierarchy=use_hierarchy, converter=RecordingConverter(), trace_root=tmp_path/'runs')
    chunks = build_chunks(conversion, tmp_path/'b', trace_root=tmp_path/'runs')
    classified = reflect_topics(chunks, client=OfflineClient(), trace_root=tmp_path/'runs')
    mapped = build_topic_map(chunks, classified, trace_root=tmp_path/'runs')
    payload = dict(parties=[{'party_id': 'p1', 'name': 'Example Borrower, LLC',
        'roles': ['borrower'], 'status': 'supported', 'evidence_item_ids': ['#/texts/1']}],
        relationships=[], facilities=[], interest=[], issues=['Other fields are not established.'])
    result = extract_credit_terms(mapped, chunks, conversion=conversion, client=FakeClient([payload]),
        output_root=tmp_path/'output', trace_root=tmp_path/'runs')
    assert bool(result['source_evidence']['#/texts/1']['heading_path']) is use_hierarchy


def test_stage_d_requires_table_source_and_sends_canonical_cells(tmp_path):
    import hashlib
    from credit_agreement_extractor import ConversionArtifact, extract_credit_terms
    from credit_agreement_extractor.retrieval import document_hash
    from credit_agreement_extractor.topic_passages import build_passage_packets, validate_passage_classifications
    doc, mapped = inputs()
    table_id = '#/tables/0'
    doc['source_reading_order'][0] = table_id
    doc['chunks'][0]['item_ids'][0] = table_id
    doc['chunks'][0]['items'][0].update(item_id=table_id, text=None, original_text=None)
    row = validate_passage_classifications({'classifications': [
        {'chunk_id': 'chunk-0', 'topics': [{'topic': 'parties_and_roles', 'groups': [
            {'evidence_item_ids': [table_id], 'context_item_ids': []}]}]}]},
        doc, build_passage_packets(doc)[:1])[0]
    mapped['topics']['parties_and_roles'] = row['topics'][0]['groups']
    canonical = {'tables': [{'self_ref': table_id, 'data': {'grid': [[{'text': 'Lender Ltd'}]]}}]}
    canon = tmp_path/'canonical.json'; canon.write_text(json.dumps(canonical))
    doc['inputs'] = {'docling_json_sha256': hashlib.sha256(canon.read_bytes()).hexdigest()}
    mapped['chunks_document_sha256'] = document_hash(doc)
    cp, mp = tmp_path/'chunks.json', tmp_path/'map.json'
    cp.write_text(json.dumps(doc)); mp.write_text(json.dumps(mapped))
    chunks = ChunkArtifact(doc['source_sha256'], tmp_path, cp, 2, 'test', False)
    topic_map = TopicMapArtifact(doc['source_sha256'], mp)
    payload = dict(parties=[{'party_id': 'p1', 'name': 'Lender Ltd', 'roles': ['lender'],
        'status': 'supported', 'evidence_item_ids': [table_id]}], relationships=[],
        facilities=[], interest=[], issues=['Other fields are not established.'])
    client = FakeClient([payload])
    with pytest.raises(ValueError, match='canonical'):
        extract_credit_terms(topic_map, chunks, client=client, output_root=tmp_path/'output',
                             trace_root=tmp_path/'runs')
    assert client.calls == []
    conversion = ConversionArtifact(tmp_path/'source.pdf', doc['source_sha256'], 'pdf', tmp_path,
        tmp_path/'document.md', canon, None, tmp_path/'manifest.json', True)
    result = extract_credit_terms(topic_map, chunks, conversion=conversion, client=client,
        output_root=tmp_path/'output', trace_root=tmp_path/'runs')
    assert result['source_evidence'][table_id]['table_data']['grid'][0][0]['text'] == 'Lender Ltd'
    assert 'Lender Ltd' in json.dumps(client.calls[0][1]['evidence'])
