import json
import pytest
from pydantic import SecretStr
from credit_agreement_extractor.tracing import traced, current_trace


def test_debug_and_basic_events_are_separate_and_secrets_redacted(tmp_path):
    @traced('test')
    def operation(value, *, debug=False, run_id=None, trace_root=None):
        current_trace().event('attempt', {'api_key': 'secret', 'usage': {'input_tokens': 1}})
        return {'value': value, 'credential': SecretStr('secret')}
    operation('hello', debug=True, run_id='shared', trace_root=tmp_path)
    folder = tmp_path / 'shared'
    assert 'secret' not in ''.join(p.read_text() for p in folder.rglob('*.json*'))
    assert list((folder / 'debug').glob('*.json'))
    rows = [json.loads(line) for line in (folder / 'events.jsonl').read_text().splitlines()]
    assert rows[-1]['status'] == 'completed'
    assert rows[1]['usage']['input_tokens'] == 1


def test_failure_and_non_debug_capture(tmp_path):
    @traced('test')
    def operation(*, debug=False, run_id=None, trace_root=None):
        raise ValueError('sensitive source text')
    with pytest.raises(ValueError):
        operation(run_id='shared', trace_root=tmp_path)
    assert not (tmp_path / 'shared' / 'debug').exists()
    assert 'sensitive source text' not in (tmp_path / 'shared' / 'events.jsonl').read_text()


def test_reject_path_traversal(tmp_path):
    @traced('test')
    def operation(**kwargs): return None
    with pytest.raises(ValueError): operation(run_id='../bad', trace_root=tmp_path)


def test_debug_saves_artifact_contents(tmp_path):
    from dataclasses import dataclass
    from pathlib import Path
    @dataclass
    class Artifact:
        json_path: Path
    output=tmp_path/'artifact.json'; output.write_text('{"data":"source wording"}')
    @traced('test')
    def operation(**kwargs): return Artifact(output)
    operation(debug=True,run_id='capture',trace_root=tmp_path)
    assert any('source wording' in p.read_text() for p in (tmp_path/'capture'/'debug').glob('*.json'))


def test_all_public_pipeline_wrappers_accept_debug_parameters():
    import inspect
    from credit_agreement_extractor import convert_document,build_chunks,reflect_topics,build_topic_map,extract_parties
    for function in (convert_document,build_chunks,reflect_topics,build_topic_map,extract_parties):
        assert {'debug','run_id','trace_root'} <= set(inspect.signature(function).parameters)


def test_summary_counts_unknown_costs_and_failed_attempts(tmp_path):
    from credit_agreement_extractor.tracing import summarize_run
    folder=tmp_path/'example'; folder.mkdir()
    events=[{'event':'llm_attempt','model':'luna','status':'received','latency_seconds':1,
             'usage':{'input_tokens':10,'output_tokens':2},'cost':{'kind':'estimated','amount':0.01,'currency':'USD'}},
            {'event':'llm_attempt','model':'luna','status':'failed','latency_seconds':2,'cost':{'kind':'unknown','amount':None}}]
    (folder/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events)+'\n')
    summary=summarize_run('example',trace_root=tmp_path)
    assert summary['request_count']==2 and summary['failed_requests']==1
    assert summary['input_tokens']==10 and summary['unknown_usage_requests']==1
    assert summary['known_cost_by_currency']=={'USD':0.01}
    assert summary['unknown_cost_requests']==1 and summary['cost_complete'] is False


def test_bad_debug_input_resets_context(tmp_path):
    from dataclasses import dataclass
    from pathlib import Path
    @dataclass
    class Artifact: json_path: Path
    path=tmp_path/'bad.json'; path.write_text('{bad')
    @traced('test')
    def operation(*args,**kwargs): return None
    with pytest.raises(ValueError): operation(Artifact(path),debug=True,run_id='bad',trace_root=tmp_path)
    assert current_trace() is None


def test_summary_counts_failed_response_without_counting_request_twice(tmp_path):
    from credit_agreement_extractor.tracing import summarize_run
    folder=tmp_path/'failure'; folder.mkdir()
    events=[{'event':'llm_attempt','span_id':'attempt-1','status':'received','model':'luna',
             'usage':{'input_tokens':'malformed','output_tokens':2}},
            {'event':'stage_finished','span_id':'attempt-1','stage':'C','status':'failed'}]
    (folder/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events)+'\n')
    result=summarize_run('failure',trace_root=tmp_path)
    assert result['request_count']==1 and result['failed_requests']==1
    assert result['unknown_usage_requests']==1


def test_simultaneous_c_snapshots_keep_context_and_redact_secrets(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from contextvars import copy_context
    from threading import Barrier
    from credit_agreement_extractor.llm import LlmResponse

    barrier = Barrier(2)

    @traced('C')
    def complete():
        trace = current_trace()
        trace.snapshot('C-request', {'payload': 'source', 'api_key': 'private-value'})
        barrier.wait(timeout=5)
        trace.snapshot('C-response', {'text': 'answer'})
        return LlmResponse('answer', 'gpt-5.6-luna', 'responses', {}, 0, {'kind': 'unknown'})

    def worker(index):
        with current_trace().bind(batch_id=f'batch-{index}', attempt=index+1,
                                  attempt_id=f'attempt-{index}', source_sha256='a'*64,
                                  authorization='private-value'):
            return complete()

    @traced('B3')
    def operation(**kwargs):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(copy_context().run, worker, index) for index in range(2)]
            return [future.result() for future in futures]

    operation(debug=True, run_id='snapshots', trace_root=tmp_path)
    folder = tmp_path/'snapshots'
    captured = [(p.name, json.loads(p.read_text())) for p in (folder/'debug').glob('C-*.json')]
    assert len(captured)==8
    assert 'private-value' not in ''.join(p.read_text() for p in folder.rglob('*.json*'))
    identities = {}
    for name, data in captured:
        meta = data['_trace']
        assert meta['run_id']=='snapshots' and meta['stage']=='C'
        assert meta['source_sha256']=='a'*64
        index = int(meta['batch_id'].split('-')[1])
        assert meta['attempt']==index+1 and meta['attempt_id']==f'attempt-{index}'
        assert 'authorization' not in meta
        identities.setdefault(index, set()).add(meta['span_id'])
        if name.startswith('C-output'):
            assert data['model']=='gpt-5.6-luna' and data['text']=='answer'
        if name.startswith('C-request'):
            assert data['payload']=='source' and data['api_key']=='[REDACTED]'
    assert all(len(spans)==1 for spans in identities.values())
    assert identities[0] != identities[1]
