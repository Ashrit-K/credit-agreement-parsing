import copy
import json
import pytest
from test_topic_reflection import artifacts, FakeClient
from credit_agreement_extractor.topic_reflection import reflect_topics
from credit_agreement_extractor.topic_map import build_topic_map, build_topic_map_document


def test_integrated_map_and_immutable_inputs(tmp_path):
    chunks,signals=artifacts(tmp_path)
    before=chunks.chunks_json_path.read_bytes()
    classified=reflect_topics(chunks,signals,client=FakeClient(),trace_root=tmp_path/'runs')
    result=build_topic_map(chunks,classified,debug=True,trace_root=tmp_path/'runs')
    mapped=json.loads(result.topic_map_json_path.read_text())
    assert mapped['topics']['interest_and_fees']==[{'chunk_id':'chunk-000001','item_ids':['#/texts/0']}]
    assert mapped['unclassified_chunk_ids']==[]
    assert chunks.chunks_json_path.read_bytes()==before
    assert mapped==build_topic_map_document(json.loads(before),json.loads(classified.classifications_json_path.read_text()))


def test_map_rejects_stale_hash_and_foreign_citation(tmp_path):
    chunks,signals=artifacts(tmp_path)
    classified=reflect_topics(chunks,signals,client=FakeClient(),trace_root=tmp_path/'runs')
    doc=json.loads(chunks.chunks_json_path.read_text())
    result=json.loads(classified.classifications_json_path.read_text())
    wrong=copy.deepcopy(result); wrong['source_sha256']='b'*64
    with pytest.raises(ValueError): build_topic_map_document(doc,wrong)
    wrong=copy.deepcopy(result); wrong['classifications'][0]['topics'][0]['item_ids']=['#/texts/99']
    with pytest.raises(ValueError): build_topic_map_document(doc,wrong)
    chunks.chunks_json_path.write_text(json.dumps(doc)+' ')
    with pytest.raises(ValueError): build_topic_map(chunks,classified,trace_root=tmp_path/'runs')


def test_heading_and_body_citations_follow_global_reading_order():
    from test_topic_signals import document
    from credit_agreement_extractor.topic_taxonomy import VOCABULARY,TAXONOMY_VERSION
    doc=document('3 percent',heading='Interest')
    classified={'schema_version':1,'status':'completed','classification_status':'final',
                'source_sha256':doc['source_sha256'],'taxonomy_version':TAXONOMY_VERSION,
                'taxonomy':list(VOCABULARY),'classifications':[{'chunk_id':'chunk-000001',
                'topics':[{'topic':'interest_and_fees','item_ids':['#/texts/0','#/texts/1']}]}]}
    result=build_topic_map_document(doc,classified)
    assert result['topics']['interest_and_fees'][0]['item_ids']==['#/texts/1','#/texts/0']


def test_inherited_heading_in_previous_chunk_is_ordered_before_body():
    from test_topic_signals import document
    from credit_agreement_extractor.topic_taxonomy import VOCABULARY,TAXONOMY_VERSION
    doc=document('3 percent',heading='Interest')
    header,body=doc['chunks'][0]['items']
    doc['chunks']=[{'chunk_id':'header','item_ids':['#/texts/1'],'items':[header],'content':'Interest'},
                   {'chunk_id':'body','item_ids':['#/texts/0'],'items':[body],'content':'3 percent'}]
    classified={'schema_version':1,'status':'completed','classification_status':'final',
                'source_sha256':doc['source_sha256'],'taxonomy_version':TAXONOMY_VERSION,
                'taxonomy':list(VOCABULARY),'classifications':[{'chunk_id':'header','topics':[]},
                {'chunk_id':'body','topics':[{'topic':'interest_and_fees','item_ids':['#/texts/0','#/texts/1']}]}]}
    assert build_topic_map_document(doc,classified)['topics']['interest_and_fees'][0]['item_ids']==['#/texts/1','#/texts/0']
