import json
import copy
import pytest
from test_topic_signals import document
from credit_agreement_extractor.chunking import ChunkArtifact
from credit_agreement_extractor.topic_signals import classify_chunks
from credit_agreement_extractor.llm import LlmResponse, LlmError
from credit_agreement_extractor.topic_reflection import reflect_topics, validate_classifications, batch_chunks


def artifacts(tmp_path, text='The Borrower pays interest quarterly.'):
    source = document(text)
    path = tmp_path / 'document.chunks.json'
    path.write_text(json.dumps(source))
    chunks = ChunkArtifact('a'*64,tmp_path,path,1,'test',False)
    return chunks, classify_chunks(chunks, trace_root=tmp_path/'runs')


class FakeClient:
    def __init__(self, fail=None): self.calls=[]; self.systems=[]; self.fail=fail
    def complete(self, system, evidence, **kwargs):
        self.calls.append((evidence,kwargs))
        self.systems.append(system)
        if self.fail and len(self.calls)==1: raise self.fail
        rows=[{'chunk_id':c['chunk_id'],'topics':[{'topic':'interest_and_fees',
              'item_ids':[c['items'][0]['item_id']]}]} for c in evidence['chunks']]
        return LlmResponse(json.dumps({'classifications':rows}),kwargs['model'],'responses',{},0.1,{'kind':'unknown'})


def test_reflection_resume_and_override(tmp_path):
    chunks, signals = artifacts(tmp_path)
    client=FakeClient()
    result=reflect_topics(chunks, signals, client=client, debug=True, run_id='one', trace_root=tmp_path/'runs')
    assert result.classifications_json_path.is_file()
    assert client.calls[0][1]['reasoning_effort']=='high'
    assert client.calls[0][1]['model']=='gpt-5.6-luna'
    assert client.calls[0][0]['chunks'][0]['proposed_topics']
    reflect_topics(chunks, signals, client=client, trace_root=tmp_path/'runs')
    assert len(client.calls)==1
    reflect_topics(chunks, signals, client=client, reasoning_effort='low', trace_root=tmp_path/'runs')
    assert len(client.calls)==2


def test_reflection_supplies_shared_topic_definitions(tmp_path):
    from credit_agreement_extractor import topic_taxonomy

    chunks, signals = artifacts(tmp_path)
    client = FakeClient()
    reflect_topics(chunks, signals, client=client, trace_root=tmp_path/'runs')
    evidence = client.calls[0][0]
    assert 'topic_definitions' in evidence
    assert evidence['topic_definitions'] == topic_taxonomy.TOPIC_DEFINITIONS
    assert set(evidence['topic_definitions']) == set(evidence['taxonomy'])
    assert all(definition.strip() for definition in evidence['topic_definitions'].values())
    assert 'prepayment premiums' in evidence['topic_definitions']['repayment_and_prepayment.call_protection']
    assert 'useful evidence' in client.systems[0]
    assert 'supplied topic definitions' in client.systems[0]


def test_definition_change_invalidates_b3_checkpoint(tmp_path, monkeypatch):
    from credit_agreement_extractor import topic_taxonomy

    chunks, signals = artifacts(tmp_path)
    client = FakeClient()
    first = reflect_topics(chunks, signals, client=client, trace_root=tmp_path/'runs')
    first_profile = json.loads(first.classifications_json_path.read_text())['profile']
    monkeypatch.setitem(topic_taxonomy.TOPIC_DEFINITIONS, 'interest_and_fees',
                        'Interest rates and facility fees; revised definition for this test.')
    reflect_topics(chunks, signals, client=client, trace_root=tmp_path/'runs')
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
    chunks, signals = artifacts(tmp_path)
    client=FakeClient(LlmError('transient',retryable=True))
    reflect_topics(chunks,signals,client=client,trace_root=tmp_path/'runs')
    assert len(client.calls)==2
    client=FakeClient(LlmError('auth',status=403))
    with pytest.raises(LlmError): reflect_topics(chunks,signals,client=client,force=True,trace_root=tmp_path/'runs')
    assert len(client.calls)==1


def test_stale_b2_rejected(tmp_path):
    chunks, signals=artifacts(tmp_path)
    chunks.chunks_json_path.write_text(chunks.chunks_json_path.read_text()+' ')
    with pytest.raises(ValueError): reflect_topics(chunks,signals,client=FakeClient(),trace_root=tmp_path/'runs')


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
    signals=classify_chunks(chunks,trace_root=tmp_path/'runs')
    class Failing(FakeClient):
        def complete(self,*args,**kwargs):
            if len(self.calls)>=1: raise LlmError('stop',status=403)
            return super().complete(*args,**kwargs)
    with pytest.raises(LlmError): reflect_topics(chunks,signals,client=Failing(),trace_root=tmp_path/'runs')
    assert not (tmp_path/'document.topic-classifications.json').exists()
    client=FakeClient()
    reflect_topics(chunks,signals,client=client,trace_root=tmp_path/'runs')
    assert len(client.calls)==1
    assert len(client.calls[0][0]['chunks'])==1


def test_table_content_is_not_lost(tmp_path):
    chunks,signals=artifacts(tmp_path,'')
    doc=json.loads(chunks.chunks_json_path.read_text())
    doc['chunks'][0]['content']='Leverage\tMargin\n2x\t3%'
    chunks.chunks_json_path.write_text(json.dumps(doc))
    signals=classify_chunks(chunks,trace_root=tmp_path/'runs')
    client=FakeClient()
    reflect_topics(chunks,signals,client=client,trace_root=tmp_path/'runs')
    assert client.calls[0][0]['chunks'][0]['content']==doc['chunks'][0]['content']


def test_invalid_output_retry_records_diagnostics(tmp_path):
    chunks,signals=artifacts(tmp_path)
    class InvalidFirst(FakeClient):
        def complete(self,*args,**kwargs):
            result=super().complete(*args,**kwargs)
            if len(self.calls)==1: return LlmResponse('{"classifications":[]}',result.model,result.api_style,{},0,{'kind':'unknown'})
            return result
    client=InvalidFirst()
    reflect_topics(chunks,signals,client=client,debug=True,run_id='retry',trace_root=tmp_path/'runs')
    assert len(client.calls)==2
    assert list((tmp_path/'runs'/'retry'/'debug').glob('B3-validation-error*.json'))


def test_model_substitution_is_not_silently_accepted(tmp_path):
    chunks,signals=artifacts(tmp_path)
    class WrongModel(FakeClient):
        def complete(self,*args,**kwargs):
            result=super().complete(*args,**kwargs)
            return LlmResponse(result.text,'different-model',result.api_style,{},0,{'kind':'unknown'})
    client=WrongModel()
    with pytest.raises(LlmError): reflect_topics(chunks,signals,client=client,trace_root=tmp_path/'runs')
    assert len(client.calls)==1


@pytest.mark.parametrize('broken', ['[]','null'])
def test_malformed_checkpoint_is_rebuilt(tmp_path,broken):
    chunks,signals=artifacts(tmp_path)
    client=FakeClient()
    reflect_topics(chunks,signals,client=client,trace_root=tmp_path/'runs')
    next((tmp_path/'b3-checkpoints').rglob('batch-*.json')).write_text(broken)
    reflect_topics(chunks,signals,client=client,trace_root=tmp_path/'runs')
    assert len(client.calls)==2
