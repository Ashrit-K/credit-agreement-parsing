import copy
import json
import pytest
from test_topic_reflection import artifacts, FakeClient
from credit_agreement_extractor.topic_reflection import reflect_topics
from credit_agreement_extractor.topic_map import build_topic_map, build_topic_map_document


def test_integrated_map_and_immutable_inputs(tmp_path):
    chunks = artifacts(tmp_path)
    before=chunks.chunks_json_path.read_bytes()
    classified=reflect_topics(chunks,client=FakeClient(),trace_root=tmp_path/'runs')
    result=build_topic_map(chunks,classified,debug=True,trace_root=tmp_path/'runs')
    mapped=json.loads(result.topic_map_json_path.read_text())
    group = mapped['topics']['interest_and_fees'][0]
    assert mapped['schema_version'] == 2
    assert result.topic_map_json_path.name == 'document.topic-passage-map.json'
    assert group['evidence_item_ids'] == ['#/texts/0']
    assert group['context_item_ids'] == []
    assert group['source_chunk_ids'] == ['chunk-000001']
    assert mapped['unclassified_chunk_ids']==[]
    assert chunks.chunks_json_path.read_bytes()==before
    assert mapped==build_topic_map_document(json.loads(before),json.loads(classified.classifications_json_path.read_text()))


def test_map_rejects_stale_hash_and_foreign_citation(tmp_path):
    chunks = artifacts(tmp_path)
    classified=reflect_topics(chunks,client=FakeClient(),trace_root=tmp_path/'runs')
    doc=json.loads(chunks.chunks_json_path.read_text())
    result=json.loads(classified.classifications_json_path.read_text())
    wrong=copy.deepcopy(result); wrong['source_sha256']='b'*64
    with pytest.raises(ValueError): build_topic_map_document(doc,wrong)
    wrong=copy.deepcopy(result); wrong['classifications'][0]['topics'][0]['groups'][0]['evidence_item_ids']=['#/texts/99']
    with pytest.raises(ValueError): build_topic_map_document(doc,wrong)
    chunks.chunks_json_path.write_text(json.dumps(doc)+' ')
    with pytest.raises(ValueError): build_topic_map(chunks,classified,trace_root=tmp_path/'runs')


def test_heading_and_body_citations_follow_global_reading_order():
    from chunk_fixtures import document
    from credit_agreement_extractor.topic_taxonomy import VOCABULARY,TAXONOMY_VERSION
    doc=document('3 percent',heading='Interest')
    classified={'schema_version':1,'status':'completed','classification_status':'final',
                'source_sha256':doc['source_sha256'],'taxonomy_version':TAXONOMY_VERSION,
                'taxonomy':list(VOCABULARY),'classifications':[{'chunk_id':'chunk-000001',
                'topics':[{'topic':'interest_and_fees','item_ids':['#/texts/0','#/texts/1']}]}]}
    result=build_topic_map_document(doc,classified)
    assert result['topics']['interest_and_fees'][0]['item_ids']==['#/texts/1','#/texts/0']


def test_inherited_heading_in_previous_chunk_is_ordered_before_body():
    from chunk_fixtures import document
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


@pytest.mark.parametrize('field', ['group_id','source_chunk_ids','evidence_pages','context_pages','packets_sha256'])
def test_v2_map_recomputes_provenance_and_packet_identity(tmp_path, field):
    chunks = artifacts(tmp_path)
    classified = reflect_topics(chunks,client=FakeClient(),trace_root=tmp_path/'runs')
    saved = json.loads(classified.classifications_json_path.read_text())
    if field == 'packets_sha256': saved['profile'][field] = 'wrong'
    else: saved['classifications'][0]['topics'][0]['groups'][0][field] = 'wrong'
    with pytest.raises(ValueError):
        build_topic_map_document(json.loads(chunks.chunks_json_path.read_text()),saved)


def test_exact_group_deduplication_but_not_partial_overlap():
    from test_topic_passages import source
    from credit_agreement_extractor.topic_passages import build_passage_packets, validate_passage_classifications, packet_hash
    from credit_agreement_extractor.topic_taxonomy import VOCABULARY,TAXONOMY_VERSION
    doc = source(); proposed = {c['chunk_id']:[] for c in doc['chunks']}
    packets = build_passage_packets(doc)
    for packet in packets:
        packet['proposed_topics'] = proposed[packet['chunk_id']]
    shared = {'evidence_item_ids':['#/texts/1','#/texts/2'],'context_item_ids':[]}
    data = {'classifications':[{'chunk_id':p['chunk_id'],'topics':[
        {'topic':'interest_and_fees','groups':[copy.deepcopy(shared)]}]} for p in packets]}
    data['classifications'][1]['topics'][0]['groups'].append(
        {'evidence_item_ids':['#/texts/2'],'context_item_ids':['#/texts/1']})
    rows = validate_passage_classifications(data,doc,packets)
    classified = {'schema_version':2,'status':'completed','classification_status':'final',
        'source_sha256':doc['source_sha256'],'taxonomy_version':TAXONOMY_VERSION,
        'taxonomy':list(VOCABULARY),'classifications':rows,'proposed_topics':proposed,
        'profile':{'boundary_context_groups':1,'schema_version':2,'packets_sha256':packet_hash(packets)}}
    result = build_topic_map_document(doc,classified)
    assert len(result['topics']['interest_and_fees']) == 2
    assert result['topics']['interest_and_fees'][0]['evidence_item_ids'] == ['#/texts/1','#/texts/2']
    assert result['source_chunk_order'] == ['chunk-0','chunk-1']


def test_v2_map_keeps_unclassified_targets_and_rejects_unsupported_schema(tmp_path):
    chunks = artifacts(tmp_path)
    class EmptyClient(FakeClient):
        def complete(self,*args,**kwargs):
            response = super().complete(*args,**kwargs)
            from credit_agreement_extractor.llm import LlmResponse
            return LlmResponse(json.dumps({'classifications':[
                {'chunk_id':'chunk-000001','topics':[]}]}),response.model,response.api_style,
                {},0,{'kind':'unknown'})
    saved = reflect_topics(chunks,client=EmptyClient(),trace_root=tmp_path/'runs')
    classified = json.loads(saved.classifications_json_path.read_text())
    doc = json.loads(chunks.chunks_json_path.read_text())
    mapped = build_topic_map_document(doc,classified)
    assert mapped['unclassified_chunk_ids'] == ['chunk-000001']
    assert all(not refs for refs in mapped['topics'].values())
    for version in (True,3,'2',None):
        classified['schema_version'] = version
        with pytest.raises(ValueError): build_topic_map_document(doc,classified)


def test_public_legacy_map_filename_stays_legacy(tmp_path):
    import hashlib
    from credit_agreement_extractor.topic_reflection import TopicClassificationArtifact
    from credit_agreement_extractor.topic_taxonomy import VOCABULARY,TAXONOMY_VERSION
    chunks = artifacts(tmp_path)
    path = tmp_path/'legacy.json'
    classified = {'schema_version':1,'status':'completed','classification_status':'final',
        'source_sha256':chunks.source_sha256,'taxonomy_version':TAXONOMY_VERSION,
        'taxonomy':list(VOCABULARY),'profile':{'chunks_json_sha256':
            hashlib.sha256(chunks.chunks_json_path.read_bytes()).hexdigest()},
        'classifications':[{'chunk_id':'chunk-000001','topics':[
            {'topic':'interest_and_fees','item_ids':['#/texts/0']}]}]}
    path.write_text(json.dumps(classified))
    artifact = build_topic_map(chunks,TopicClassificationArtifact(chunks.source_sha256,path),
                               trace_root=tmp_path/'runs')
    assert artifact.topic_map_json_path.name == 'document.topic-map.json'
    assert json.loads(artifact.topic_map_json_path.read_text())['schema_version'] == 1
