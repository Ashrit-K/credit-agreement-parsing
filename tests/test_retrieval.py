"""B4/B5 source-backed contracts; fixtures contain no human review labels."""
import copy
import json
import pytest
from test_topic_passages import source
from credit_agreement_extractor.topic_passages import (
    build_passage_packets, validate_passage_classifications, packet_hash,
)
from credit_agreement_extractor.topic_map import build_topic_map_document
from credit_agreement_extractor.topic_taxonomy import TAXONOMY_VERSION, VOCABULARY
from credit_agreement_extractor import retrieval


def inputs():
    doc = source()
    packets = build_passage_packets(doc)
    answer = {'classifications': [
        {'chunk_id': 'chunk-0', 'topics': [{'topic': 'parties_and_roles', 'groups': [
            {'evidence_item_ids': ['#/texts/0'], 'context_item_ids': []}]}]},
        {'chunk_id': 'chunk-1', 'topics': [{'topic': 'interest_and_fees', 'groups': [
            {'evidence_item_ids': ['#/texts/2'], 'context_item_ids': ['#/texts/1']}]}]},
    ]}
    classified = dict(schema_version=2, status='completed', classification_status='final',
        pipeline_layout='stage-b-v2', source_sha256=doc['source_sha256'],
        taxonomy_version=TAXONOMY_VERSION, taxonomy=list(VOCABULARY),
        classifications=validate_passage_classifications(answer, doc, packets),
        profile={'schema_version': 2, 'boundary_context_groups': 1,
                 'packets_sha256': packet_hash(packets)})
    return doc, build_topic_map_document(doc, classified)


def test_selects_all_groups_in_taxonomy_order_without_mutation():
    doc, mapped = inputs(); before = copy.deepcopy((doc, mapped))
    result = retrieval.select_topic_groups(doc, mapped,
        topics=['interest_and_fees', 'parties_and_roles', 'parties_and_roles'])
    assert result['requested_topics'] == ['parties_and_roles', 'interest_and_fees']
    assert result['topics']['interest_and_fees'] == mapped['topics']['interest_and_fees']
    assert (doc, mapped) == before


@pytest.mark.parametrize('topics', [[], 'parties_and_roles', ['loan pricing'], [None]])
def test_rejects_invalid_requests(topics):
    doc, mapped = inputs()
    with pytest.raises(ValueError): retrieval.select_topic_groups(doc, mapped, topics=topics)


def test_empty_topic_and_subtopic_are_explicit():
    doc, mapped = inputs()
    result = retrieval.select_topic_groups(doc, mapped, topics=['interest_and_fees.pik_toggle'])
    assert result['topics'] == {'interest_and_fees.pik_toggle': []}
    assert result['empty_topics'] == ['interest_and_fees.pik_toggle']


@pytest.mark.parametrize('field,value', [
    ('source_sha256', 'b'*64), ('taxonomy_version', 'wrong'),
    ('schema_version', 1), ('schema_version', True), ('status', 'partial'),
    ('chunks_document_sha256', 'wrong'),
])
def test_rejects_stale_or_legacy_map(field, value):
    doc, mapped = inputs(); mapped[field] = value
    with pytest.raises(ValueError): retrieval.select_topic_groups(doc, mapped, topics=['interest_and_fees'])


@pytest.mark.parametrize('field,value', [
    ('evidence_item_ids', ['#/texts/99']), ('context_item_ids', ['#/texts/2']),
    ('evidence_pages', [999]), ('group_id', 'invented'), ('source_chunk_ids', []),
])
def test_rejects_corrupt_group(field, value):
    doc, mapped = inputs(); mapped['topics']['interest_and_fees'][0][field] = value
    with pytest.raises(ValueError): retrieval.select_topic_groups(doc, mapped, topics=['interest_and_fees'])


def test_stale_wording_is_rejected():
    doc, mapped = inputs(); doc['chunks'][0]['items'][0]['original_text'] = 'Different borrower'
    with pytest.raises(ValueError): retrieval.select_topic_groups(doc, mapped, topics=['parties_and_roles'])


def test_rejects_reordered_groups_even_when_each_group_is_valid():
    doc, mapped = inputs()
    packets = build_passage_packets(doc)
    earlier = validate_passage_classifications({'classifications': [
        {'chunk_id': 'chunk-0', 'topics': [{'topic': 'interest_and_fees', 'groups': [
            {'evidence_item_ids': ['#/texts/1'], 'context_item_ids': []}]}]}]}, doc, packets[:1])[0]
    mapped['topics']['interest_and_fees'].insert(0, earlier['topics'][0]['groups'][0])
    assert len(retrieval.select_topic_groups(doc, mapped, topics=['interest_and_fees'])['topics']['interest_and_fees']) == 2
    mapped['topics']['interest_and_fees'].reverse()
    with pytest.raises(ValueError, match='order'):
        retrieval.select_topic_groups(doc, mapped, topics=['interest_and_fees'])


def test_packages_original_evidence_and_cross_page_context():
    from credit_agreement_extractor.evidence import package_topic_evidence
    doc, mapped = inputs()
    selection = retrieval.select_topic_groups(doc, mapped, topics=['interest_and_fees'])
    before = copy.deepcopy((doc, selection))
    packet = package_topic_evidence(doc, selection)
    group = packet['topics']['interest_and_fees'][0]
    assert group['evidence'][0]['text'] == 'payable quarterly.'
    assert group['evidence'][0]['pages'] == [2]
    assert group['context'][0]['text'] == 'Interest is'
    assert group['context'][0]['pages'] == [1]
    assert (doc, selection) == before


def test_packages_full_original_wording_headings_without_hierarchy_dependency():
    from credit_agreement_extractor.evidence import package_topic_evidence
    doc, mapped = inputs()
    doc['chunks'][0]['items'][0]['original_text'] = 'Borrower: ' + 'x' * 30000
    # Update map binding as would an offline B3 rebuild; groups are unchanged.
    mapped['chunks_document_sha256'] = retrieval.document_hash(doc)
    selected = retrieval.select_topic_groups(doc, mapped, topics=['parties_and_roles'])
    item = package_topic_evidence(doc, selected)['topics']['parties_and_roles'][0]['evidence'][0]
    assert len(item['text']) == 30010
    assert item['heading_path'] == []


def test_package_rejects_missing_text_and_stale_selection():
    from credit_agreement_extractor.evidence import package_topic_evidence
    doc, mapped = inputs()
    selected = retrieval.select_topic_groups(doc, mapped, topics=['parties_and_roles'])
    selected['chunks_document_sha256'] = 'wrong'
    with pytest.raises(ValueError): package_topic_evidence(doc, selected)
    selected['chunks_document_sha256'] = retrieval.document_hash(doc)
    doc['chunks'][0]['items'][0]['original_text'] = ''
    doc['chunks'][0]['items'][0]['text'] = ''
    selected['chunks_document_sha256'] = retrieval.document_hash(doc)
    with pytest.raises(ValueError, match='text'): package_topic_evidence(doc, selected)


def test_public_api_persists_distinct_requests_and_traces(tmp_path):
    from credit_agreement_extractor import retrieve_evidence
    from credit_agreement_extractor.chunking import ChunkArtifact
    from credit_agreement_extractor.topic_map import TopicMapArtifact
    doc, mapped = inputs()
    chunks_path = tmp_path / 'chunks.json'; map_path = tmp_path / 'map.json'
    chunks_path.write_text(json.dumps(doc)); map_path.write_text(json.dumps(mapped))
    before = (chunks_path.read_bytes(), map_path.read_bytes())
    chunks = ChunkArtifact(doc['source_sha256'], tmp_path, chunks_path, 1, 'test', False)
    topic_map = TopicMapArtifact(doc['source_sha256'], map_path)
    first = retrieve_evidence(topic_map, chunks, topics=['parties_and_roles'],
        debug=True, run_id='retrieval-test', trace_root=tmp_path / 'runs')
    second = retrieve_evidence(topic_map, chunks, topics=['interest_and_fees'],
        trace_root=tmp_path / 'runs')
    assert first.evidence_json_path != second.evidence_json_path
    assert first.evidence_json_path.exists()
    assert (chunks_path.read_bytes(), map_path.read_bytes()) == before
    events = [json.loads(line) for line in (tmp_path / 'runs/retrieval-test/events.jsonl').read_text().splitlines()]
    assert {'B4', 'B5'} <= {e.get('stage') or e.get('data', {}).get('stage') for e in events}


def test_table_requires_canonical_cells_and_preserves_them():
    from credit_agreement_extractor.evidence import package_topic_evidence
    doc, mapped = inputs()
    old_id = '#/texts/0'; new_id = '#/tables/0'
    doc['source_reading_order'][0] = new_id
    doc['chunks'][0]['item_ids'][0] = new_id
    doc['chunks'][0]['items'][0].update(item_id=new_id, text=None, original_text=None)
    # Construct a valid group through the same validator used by B3.
    packets = build_passage_packets(doc)
    row = validate_passage_classifications({'classifications': [
        {'chunk_id': 'chunk-0', 'topics': [{'topic': 'parties_and_roles', 'groups': [
            {'evidence_item_ids': [new_id], 'context_item_ids': []}]}]}]}, doc, packets[:1])[0]
    mapped['topics']['parties_and_roles'] = row['topics'][0]['groups']
    mapped['chunks_document_sha256'] = retrieval.document_hash(doc)
    selected = retrieval.select_topic_groups(doc, mapped, topics=['parties_and_roles'])
    with pytest.raises(ValueError, match='canonical'): package_topic_evidence(doc, selected)
    cells = [[{'text': 'Lender'}, {'text': 'Commitment'}], [{'text': 'Kestrel'}, {'text': '$6.6m'}]]
    canonical = {'tables': [{'self_ref': new_id, 'data': {'grid': cells}}]}
    packet = package_topic_evidence(doc, selected, canonical_document=canonical)
    item = packet['topics']['parties_and_roles'][0]['evidence'][0]
    assert item['text'] == 'Lender\tCommitment\nKestrel\t$6.6m'
    assert item['table_data']['grid'] == cells


def test_public_failures_and_persisted_packet_are_traced(tmp_path):
    from credit_agreement_extractor import retrieve_evidence
    from credit_agreement_extractor.chunking import ChunkArtifact
    from credit_agreement_extractor.topic_map import TopicMapArtifact
    doc, mapped = inputs()
    chunks_path = tmp_path/'chunks.json'; map_path = tmp_path/'map.json'
    chunks_path.write_text(json.dumps(doc)); map_path.write_text(json.dumps(mapped))
    chunks = ChunkArtifact(doc['source_sha256'], tmp_path, chunks_path, 1, 'test', False)
    artifact = TopicMapArtifact(doc['source_sha256'], map_path)
    retrieve_evidence(artifact, chunks, topics=['parties_and_roles'], debug=True,
        run_id='full-packet', trace_root=tmp_path/'runs')
    snapshots = [json.loads(p.read_text()) for p in (tmp_path/'runs/full-packet/debug').glob('*.json')]
    assert any('evidence_json_path' in s and isinstance(s['evidence_json_path'], dict) for s in snapshots)
    chunks_path.write_text('invalid JSON')
    with pytest.raises(ValueError):
        retrieve_evidence(artifact, chunks, topics=['parties_and_roles'],
            run_id='bad-input', trace_root=tmp_path/'runs')
    events = [json.loads(s) for s in (tmp_path/'runs/bad-input/events.jsonl').read_text().splitlines()]
    assert any(e.get('status') == 'failed' for e in events)


def test_public_rejects_canonical_hash_mismatch(tmp_path):
    from credit_agreement_extractor import retrieve_evidence, ConversionArtifact
    from credit_agreement_extractor.chunking import ChunkArtifact
    from credit_agreement_extractor.topic_map import TopicMapArtifact
    doc, mapped = inputs()
    cp = tmp_path/'chunks.json'; mp = tmp_path/'map.json'; canon = tmp_path/'canonical.json'
    cp.write_text(json.dumps(doc)); mp.write_text(json.dumps(mapped)); canon.write_text('{}')
    conversion = ConversionArtifact(tmp_path/'source.pdf', doc['source_sha256'], 'pdf', tmp_path,
        tmp_path/'document.md', canon, None, tmp_path/'manifest.json', True)
    with pytest.raises(ValueError, match='hash'):
        retrieve_evidence(TopicMapArtifact(doc['source_sha256'], mp),
            ChunkArtifact(doc['source_sha256'], tmp_path, cp, 1, 'test', False),
            topics=['parties_and_roles'], conversion=conversion, trace_root=tmp_path/'runs')


def test_pageless_context_and_heading_metadata_are_preserved():
    from credit_agreement_extractor.evidence import package_topic_evidence
    doc, mapped = inputs()
    for chunk in doc['chunks']:
        for item in chunk['items']:
            item['pages'] = []
    doc['chunks'][1]['items'][0]['heading_path'] = [
        {'item_id': '#/texts/1', 'text': 'Interest is', 'depth': 1}]
    # Recompute map group provenance through the classification validator.
    packets = build_passage_packets(doc)
    rows = validate_passage_classifications({'classifications': [
        {'chunk_id': 'chunk-1', 'topics': [{'topic': 'interest_and_fees', 'groups': [
            {'evidence_item_ids': ['#/texts/2'], 'context_item_ids': ['#/texts/1']}]}]}]}, doc, packets[1:])
    mapped['topics']['interest_and_fees'] = rows[0]['topics'][0]['groups']
    mapped['chunks_document_sha256'] = retrieval.document_hash(doc)
    selected = retrieval.select_topic_groups(doc, mapped, topics=['interest_and_fees'])
    evidence = package_topic_evidence(doc, selected)['topics']['interest_and_fees'][0]['evidence'][0]
    assert evidence['pages'] == []
    assert evidence['heading_path'] == doc['chunks'][1]['items'][0]['heading_path']
