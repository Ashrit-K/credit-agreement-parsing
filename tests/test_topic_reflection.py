import json
import copy
from threading import Barrier, Event, Lock
import pytest
from chunk_fixtures import document
from credit_agreement_extractor.chunking import ChunkArtifact
from credit_agreement_extractor.llm import LlmResponse, LlmError
from credit_agreement_extractor.topic_reflection import reflect_topics, validate_classifications, batch_chunks
from credit_agreement_extractor.tracing import current_trace, traced


def artifacts(tmp_path, text='The Borrower pays interest quarterly.'):
    source = document(text)
    path = tmp_path / 'document.chunks.json'
    path.write_text(json.dumps(source))
    chunks = ChunkArtifact('a'*64,tmp_path,path,1,'test',False)
    return chunks


class FakeClient:
    def __init__(self, fail=None): self.calls=[]; self.systems=[]; self.fail=fail
    def complete(self, system, evidence, **kwargs):
        self.calls.append((evidence,kwargs))
        self.systems.append(system)
        if self.fail and len(self.calls)==1: raise self.fail
        rows=[{'chunk_id':c['chunk_id'],'topics':[{'topic':'interest_and_fees',
              'groups':[{'evidence_item_ids':[c['items'][0]['item_id']],
                         'context_item_ids':[]}]}]} for c in evidence['chunks']]
        return LlmResponse(json.dumps({'classifications':rows}),kwargs['model'],'responses',{},0.1,{'kind':'unknown'})


def test_reflection_resume_and_override(tmp_path):
    chunks = artifacts(tmp_path)
    client=FakeClient()
    result=reflect_topics(chunks, client=client, debug=True, run_id='one', trace_root=tmp_path/'runs')
    assert result.classifications_json_path.is_file()
    assert result.classifications_json_path.name == 'document.topic-passages.json'
    assert json.loads(result.classifications_json_path.read_text())['schema_version'] == 2
    assert client.calls[0][1]['reasoning_effort']=='high'
    assert client.calls[0][1]['model']=='gpt-5.6-luna'
    assert 'proposed_topics' not in client.calls[0][0]['chunks'][0]
    reflect_topics(chunks, client=client, trace_root=tmp_path/'runs')
    assert len(client.calls)==1
    reflect_topics(chunks, client=client, reasoning_effort='low', trace_root=tmp_path/'runs')
    assert len(client.calls)==2


def test_reflection_supplies_shared_topic_definitions(tmp_path):
    from credit_agreement_extractor import topic_taxonomy

    chunks = artifacts(tmp_path)
    client = FakeClient()
    reflect_topics(chunks, client=client, trace_root=tmp_path/'runs')
    evidence = client.calls[0][0]
    assert 'topic_definitions' in evidence
    assert evidence['topic_definitions'] == topic_taxonomy.TOPIC_DEFINITIONS
    assert set(evidence['topic_definitions']) == set(evidence['taxonomy'])
    assert all(definition.strip() for definition in evidence['topic_definitions'].values())
    assert 'prepayment premiums' in evidence['topic_definitions']['repayment_and_prepayment.call_protection']
    assert 'useful evidence' in client.systems[0]
    assert 'supplied topic definitions' in client.systems[0]


def test_reflection_routes_qwen_messages_without_substitution(tmp_path):
    from dataclasses import replace
    class MessagesClient(FakeClient):
        def complete(self, system, evidence, **kwargs):
            return replace(super().complete(system, evidence, **kwargs), api_style='messages')
    chunks = artifacts(tmp_path)
    client = MessagesClient()
    result = reflect_topics(chunks, client=client, model='qwen3.8-flash',
                            reasoning_effort='high', trace_root=tmp_path/'runs')
    assert result.classifications_json_path.is_file()
    assert client.calls[0][1]['api_style'] == 'messages'
    assert client.calls[0][1]['reasoning_effort'] == 'high'


def test_definition_change_invalidates_b3_checkpoint(tmp_path, monkeypatch):
    from credit_agreement_extractor import topic_taxonomy

    chunks = artifacts(tmp_path)
    client = FakeClient()
    first = reflect_topics(chunks, client=client, trace_root=tmp_path/'runs')
    first_profile = json.loads(first.classifications_json_path.read_text())['profile']
    monkeypatch.setitem(topic_taxonomy.TOPIC_DEFINITIONS, 'interest_and_fees',
                        'Interest rates and facility fees; revised definition for this test.')
    reflect_topics(chunks, client=client, trace_root=tmp_path/'runs')
    assert len(client.calls) == 2
    second_profile = json.loads(first.classifications_json_path.read_text())['profile']
    assert first_profile['topic_definitions_sha256'] != second_profile['topic_definitions_sha256']


@pytest.mark.parametrize('change', ['missing','unknown_chunk','unknown_topic','foreign_item','duplicate','possible'])
def test_invalid_classifications(change):
    doc=document('interest')
    rows=[{'chunk_id':'chunk-000001','topics':[{'topic':'interest_and_fees','item_ids':['#/texts/0']}]}]
    if change=='missing': rows=[]
    if change=='unknown_chunk': rows[0]['chunk_id']='other'
    if change=='unknown_topic': rows[0]['topics'][0]['topic']='invented'
    if change=='foreign_item': rows[0]['topics'][0]['item_ids']=['#/texts/99']
    if change=='duplicate': rows.append(copy.deepcopy(rows[0]))
    if change=='possible': rows[0]['possible_topics']=[]
    with pytest.raises(ValueError): validate_classifications({'classifications':rows},doc['chunks'])


def test_parent_and_no_labels():
    chunks=document('PIK')['chunks']
    rows=validate_classifications({'classifications':[{'chunk_id':'chunk-000001','topics':[
        {'topic':'interest_and_fees.pik_toggle','item_ids':['#/texts/0']}]}]},chunks)
    assert [t['topic'] for t in rows[0]['topics']]==['interest_and_fees','interest_and_fees.pik_toggle']
    assert validate_classifications({'classifications':[{'chunk_id':'chunk-000001','topics':[]}]},chunks)[0]['topics']==[]


def test_batch_count_size_and_oversized():
    chunks=[{'chunk_id':str(n),'items':[{'item_id':str(n),'text':'x'*100}], 'proposed_topics':[]} for n in range(11)]
    assert [len(b) for b in batch_chunks(chunks,5,24000)]==[5,5,1]
    assert all(len(b)==1 for b in batch_chunks(chunks,5,1))


def test_transient_retry_and_auth_no_retry(tmp_path):
    chunks = artifacts(tmp_path)
    client=FakeClient(LlmError('transient',retryable=True))
    reflect_topics(chunks,client=client,trace_root=tmp_path/'runs')
    assert len(client.calls)==2
    client=FakeClient(LlmError('auth',status=403))
    with pytest.raises(LlmError): reflect_topics(chunks,client=client,force=True,trace_root=tmp_path/'runs')
    assert len(client.calls)==1


def test_changed_b1_bytes_invalidate_classifier_checkpoint(tmp_path):
    chunks = artifacts(tmp_path)
    client = FakeClient()
    reflect_topics(chunks, client=client, trace_root=tmp_path/'runs')
    chunks.chunks_json_path.write_text(chunks.chunks_json_path.read_text()+' ')
    reflect_topics(chunks, client=client, trace_root=tmp_path/'runs')
    assert len(client.calls) == 2


def test_partial_failure_resumes_only_failed_batch(tmp_path):
    source=document('interest')
    source['chunks']=[]; source['source_reading_order']=[]
    for n in range(6):
        chunk=document('interest')['chunks'][0]
        chunk['chunk_id']=f'chunk-{n}'
        chunk['item_ids']=[f'#/texts/{n}']; chunk['items'][0]['item_id']=f'#/texts/{n}'
        source['chunks'].append(chunk); source['source_reading_order'].extend(chunk['item_ids'])
    path=tmp_path/'document.chunks.json'; path.write_text(json.dumps(source))
    chunks=ChunkArtifact('a'*64,tmp_path,path,6,'test',False)
    class Failing(FakeClient):
        def complete(self,*args,**kwargs):
            if len(self.calls)>=1: raise LlmError('stop',status=403)
            return super().complete(*args,**kwargs)
    with pytest.raises(LlmError): reflect_topics(chunks,client=Failing(),max_concurrency=1,trace_root=tmp_path/'runs')
    assert not (tmp_path/'stage-b-v2'/'document.topic-passages.json').exists()
    client=FakeClient()
    reflect_topics(chunks,client=client,trace_root=tmp_path/'runs')
    assert len(client.calls)==1
    assert len(client.calls[0][0]['chunks'])==1


def test_table_content_is_not_lost(tmp_path):
    chunks = artifacts(tmp_path,'')
    doc=json.loads(chunks.chunks_json_path.read_text())
    doc['chunks'][0]['content']='Leverage\tMargin\n2x\t3%'
    chunks.chunks_json_path.write_text(json.dumps(doc))
    client=FakeClient()
    reflect_topics(chunks,client=client,trace_root=tmp_path/'runs')
    assert client.calls[0][0]['chunks'][0]['content']==doc['chunks'][0]['content']


def test_invalid_output_retry_records_diagnostics(tmp_path):
    chunks = artifacts(tmp_path)
    class InvalidFirst(FakeClient):
        def complete(self,*args,**kwargs):
            result=super().complete(*args,**kwargs)
            if len(self.calls)==1: return LlmResponse('{"classifications":[]}',result.model,result.api_style,{},0,{'kind':'unknown'})
            return result
    client=InvalidFirst()
    reflect_topics(chunks,client=client,debug=True,run_id='retry',trace_root=tmp_path/'runs')
    assert len(client.calls)==2
    assert list((tmp_path/'runs'/'retry'/'debug').glob('B2-validation-error*.json'))


def test_model_substitution_is_not_silently_accepted(tmp_path):
    chunks = artifacts(tmp_path)
    class WrongModel(FakeClient):
        def complete(self,*args,**kwargs):
            result=super().complete(*args,**kwargs)
            return LlmResponse(result.text,'different-model',result.api_style,{},0,{'kind':'unknown'})
    client=WrongModel()
    with pytest.raises(LlmError): reflect_topics(chunks,client=client,trace_root=tmp_path/'runs')
    assert len(client.calls)==1


@pytest.mark.parametrize('broken', ['[]','null'])
def test_malformed_checkpoint_is_rebuilt(tmp_path,broken):
    chunks = artifacts(tmp_path)
    client=FakeClient()
    reflect_topics(chunks,client=client,trace_root=tmp_path/'runs')
    next((tmp_path/'stage-b-v2'/'b2-checkpoints').rglob('batch-*.json')).write_text(broken)
    reflect_topics(chunks,client=client,trace_root=tmp_path/'runs')
    assert len(client.calls)==2


def multi_artifacts(tmp_path, count):
    source = document('interest')
    source['chunks'] = []
    source['source_reading_order'] = []
    for index in range(count):
        chunk = document('interest')['chunks'][0]
        chunk['chunk_id'] = f'chunk-{index:06d}'
        chunk['item_ids'] = [f'#/texts/{index}']
        chunk['items'][0]['item_id'] = chunk['item_ids'][0]
        source['chunks'].append(chunk)
        source['source_reading_order'].extend(chunk['item_ids'])
    path = tmp_path / 'document.chunks.json'
    path.write_text(json.dumps(source))
    chunks = ChunkArtifact('a'*64, tmp_path, path, count, 'test', False)
    return chunks


@pytest.mark.parametrize('limit', [0, -1, True, False, 1.5, '2', None])
def test_concurrency_requires_positive_integer(tmp_path, limit):
    chunks = artifacts(tmp_path)
    client = FakeClient()
    with pytest.raises(ValueError, match='max_concurrency'):
        reflect_topics(chunks, client=client, max_concurrency=limit,
                       trace_root=tmp_path/'runs')
    assert not client.calls


@pytest.mark.parametrize('limit', [2, 3, 5])
def test_concurrent_batches_are_bounded_and_traced(tmp_path, limit):
    chunks = multi_artifacts(tmp_path, limit*2)
    barrier = Barrier(limit)
    lock = Lock()

    class Concurrent(FakeClient):
        active = 0
        peak = 0

        @traced('C')
        def complete(self, system, evidence, **kwargs):
            with lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            try:
                barrier.wait(timeout=5)
                trace = current_trace()
                trace.event('llm_attempt', {'model':kwargs['model']})
                return super().complete(system, evidence, **kwargs)
            finally:
                with lock: self.active -= 1

    client = Concurrent()
    result = reflect_topics(chunks, client=client, max_chunks=1,
                            max_concurrency=limit, debug=True, run_id='parallel',
                            trace_root=tmp_path/'runs')
    assert client.peak == limit
    rows = json.loads(result.classifications_json_path.read_text())['classifications']
    assert [r['chunk_id'] for r in rows] == [f'chunk-{i:06d}' for i in range(limit*2)]
    assert [r['topics'][0]['groups'][0]['evidence_item_ids'] for r in rows] == [[f'#/texts/{i}'] for i in range(limit*2)]
    directory = tmp_path/'runs'/'parallel'
    events = [json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
    parent = next(e['span_id'] for e in events if e['event']=='stage_started' and e['stage']=='B2')
    starts = [e for e in events if e['event']=='stage_started' and e['stage']=='C']
    assert len(starts) == limit*2
    assert len({e['span_id'] for e in starts}) == limit*2
    assert all(e['parent_span_id']==parent and e['attempt']==1 for e in starts)
    assert {e['batch_id'] for e in starts} == {f'batch-{i+1:06d}' for i in range(limit*2)}
    calls = [e for e in events if e['event']=='llm_attempt']
    assert {(e['span_id'],e['batch_id'],e['attempt']) for e in calls} == {
        (e['span_id'],e['batch_id'],e['attempt']) for e in starts}
    requests = list((directory/'debug').glob('B2-request-*.json'))
    responses = list((directory/'debug').glob('B2-response-*.json'))
    assert len(requests) == len(responses) == limit*2
    assert len({p.name for p in requests+responses}) == limit*4
    request_data = [json.loads(p.read_text()) for p in requests]
    response_data = [json.loads(p.read_text()) for p in responses]
    assert len({r['attempt_id'] for r in request_data}) == limit*2
    assert {(r['attempt_id'], r['batch_id'], r['attempt']) for r in request_data} == {
        (r['attempt_id'], r['batch_id'], r['attempt']) for r in response_data}


def test_default_concurrency_and_out_of_order_completion(tmp_path):
    chunks = multi_artifacts(tmp_path, 5)
    barrier = Barrier(5)
    last_finished = Event()
    finished = []

    class Reversed(FakeClient):
        def complete(self, system, evidence, **kwargs):
            chunk_id = evidence['chunks'][0]['chunk_id']
            barrier.wait(timeout=5)
            if chunk_id != 'chunk-000004':
                assert last_finished.wait(timeout=5)
            result = super().complete(system, evidence, **kwargs)
            finished.append(chunk_id)
            if chunk_id == 'chunk-000004': last_finished.set()
            return result

    result = reflect_topics(chunks, client=Reversed(), max_chunks=1,
                            trace_root=tmp_path/'runs')
    assert finished[0] == 'chunk-000004'
    rows = json.loads(result.classifications_json_path.read_text())['classifications']
    assert [r['chunk_id'] for r in rows] == [f'chunk-{i:06d}' for i in range(5)]


def test_sequential_equivalence_and_concurrency_independent_resume(tmp_path):
    chunks = multi_artifacts(tmp_path, 8)
    client = FakeClient()
    first = reflect_topics(chunks, client=client, max_chunks=1,
                           max_concurrency=1, trace_root=tmp_path/'runs')
    sequential = first.classifications_json_path.read_bytes()
    assert [e['chunks'][0]['chunk_id'] for e, _ in client.calls] == [f'chunk-{i:06d}' for i in range(8)]
    resumed = reflect_topics(chunks, client=client, max_chunks=1,
                             max_concurrency=3, trace_root=tmp_path/'runs')
    assert resumed.cached and len(client.calls)==8
    assert resumed.classifications_json_path.read_bytes() == sequential
    parallel = reflect_topics(chunks, client=client, max_chunks=1,
                              max_concurrency=3, force=True, trace_root=tmp_path/'runs')
    assert parallel.classifications_json_path.read_bytes() == sequential


def test_concurrent_failure_keeps_inflight_checkpoint_and_stops_scheduling(tmp_path):
    chunks = multi_artifacts(tmp_path, 7)
    barrier = Barrier(2)
    release_success = Event()
    started = []

    class Partial(FakeClient):
        def complete(self, system, evidence, **kwargs):
            chunk_id = evidence['chunks'][0]['chunk_id']
            started.append(chunk_id)
            barrier.wait(timeout=5)
            if chunk_id == 'chunk-000000':
                release_success.set()
                raise LlmError('auth', status=403)
            assert release_success.wait(timeout=5)
            return super().complete(system, evidence, **kwargs)

    with pytest.raises(LlmError):
        reflect_topics(chunks, client=Partial(), max_chunks=1,
                       max_concurrency=2, trace_root=tmp_path/'runs')
    assert set(started) == {'chunk-000000','chunk-000001'}
    assert not (tmp_path/'stage-b-v2'/'document.topic-passages.json').exists()
    assert len(list((tmp_path/'stage-b-v2'/'b2-checkpoints').rglob('batch-*.json'))) == 1
    client = FakeClient()
    result = reflect_topics(chunks, client=client, max_chunks=1,
                            max_concurrency=2, trace_root=tmp_path/'runs')
    assert len(client.calls)==6
    assert 'chunk-000001' not in {e['chunks'][0]['chunk_id'] for e, _ in client.calls}
    successful = result.classifications_json_path.read_bytes()
    with pytest.raises(LlmError):
        reflect_topics(chunks, client=Partial(), max_chunks=1,
                       max_concurrency=2, force=True, trace_root=tmp_path/'runs')
    assert result.classifications_json_path.read_bytes() == successful


def test_each_parallel_batch_has_its_own_two_attempts(tmp_path):
    chunks = multi_artifacts(tmp_path, 3)
    barrier = Barrier(3)
    attempts = {}

    class RetryEach(FakeClient):
        def complete(self, system, evidence, **kwargs):
            key = evidence['chunks'][0]['chunk_id']
            attempts[key] = attempts.get(key, 0)+1
            if attempts[key]==1:
                barrier.wait(timeout=5)
                return LlmResponse('{"classifications":[]}',kwargs['model'], 'responses', {}, 0, {'kind':'unknown'})
            return super().complete(system, evidence, **kwargs)

    reflect_topics(chunks, client=RetryEach(), max_chunks=1,
                   max_concurrency=3, trace_root=tmp_path/'runs')
    assert set(attempts.values()) == {2}


def test_neighbor_policy_changes_checkpoint_and_keeps_old_output(tmp_path):
    chunks = multi_artifacts(tmp_path, 2)
    old = tmp_path/'document.topic-classifications.json'
    old.write_text('historical output')
    client = FakeClient()
    first = reflect_topics(chunks, client=client, boundary_context_groups=0,
                           trace_root=tmp_path/'runs')
    profile = json.loads(first.classifications_json_path.read_text())['profile']
    assert profile['boundary_context_groups'] == 0 and profile['packets_sha256']
    assert not client.calls[0][0]['chunks'][0]['neighbor_items']
    reflect_topics(chunks, client=client, boundary_context_groups=1,
                   trace_root=tmp_path/'runs')
    assert len(client.calls) == 2
    assert client.calls[-1][0]['chunks'][0]['neighbor_items'][0]['item_id'] == '#/texts/1'
    assert old.read_text() == 'historical output'


def test_tampered_passage_checkpoint_provenance_is_rebuilt(tmp_path):
    chunks = artifacts(tmp_path)
    client = FakeClient()
    reflect_topics(chunks, client=client, trace_root=tmp_path/'runs')
    path = next((tmp_path/'stage-b-v2'/'b2-checkpoints').rglob('batch-*.json'))
    saved = json.loads(path.read_text())
    saved['classifications'][0]['topics'][0]['groups'][0]['evidence_pages'] = [99]
    path.write_text(json.dumps(saved))
    reflect_topics(chunks, client=client, trace_root=tmp_path/'runs')
    assert len(client.calls) == 2
