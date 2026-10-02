"""Passage contracts test source scope, not model semantic accuracy."""
import copy
import pytest
from credit_agreement_extractor import topic_passages as passages


def source():
    items = [dict(item_id=f'#/texts/{n}', text=text, original_text=text,
                  pages=[1 if n < 2 else 2], heading_path=[], container_path=[])
             for n, text in enumerate(['Borrower: Example Ltd.', 'Interest is',
                                      'payable quarterly.', 'Unrelated notice.'])]
    return dict(schema_version=1, status='completed', source_sha256='a'*64,
                source_reading_order=[i['item_id'] for i in items], chunks=[
                    dict(chunk_id=f'chunk-{n}', item_ids=[i['item_id'] for i in pair],
                         items=pair, content='\n'.join(i['text'] for i in pair))
                    for n, pair in enumerate([items[:2], items[2:]])])


def answer(evidence=None, context=None, topic='interest_and_fees'):
    return {'classifications':[{'chunk_id':'chunk-1','topics':[{'topic':topic,
        'groups':[{'evidence_item_ids':evidence or ['#/texts/2'],
                   'context_item_ids':context or []}]}]}]}


def test_cross_page_group_retains_roles_source_order_and_stable_identity():
    doc = source(); before = copy.deepcopy(doc)
    packets = passages.build_passage_packets(doc)
    assert [i['item_id'] for i in packets[1]['neighbor_items']] == ['#/texts/1']
    rows = passages.validate_passage_classifications(answer(context=['#/texts/1']), doc, packets[1:])
    group = rows[0]['topics'][0]['groups'][0]
    assert group['evidence_pages'] == [2] and group['context_pages'] == [1]
    assert group['source_chunk_ids'] == ['chunk-0','chunk-1']
    assert rows == passages.validate_passage_classifications(answer(context=['#/texts/1']), doc, packets[1:])
    assert doc == before


@pytest.mark.parametrize('change', ['unknown_id','neighbor_only','overlap','duplicate_id',
    'extra_group','missing_row','duplicate_row','unknown_topic','empty_groups','empty_evidence',
    'duplicate_topic','unknown_chunk','other_batch_chunk'])
def test_rejects_invalid_passages(change):
    doc = source(); packets = passages.build_passage_packets(doc)
    data = answer(); row = data['classifications'][0]; label = row['topics'][0]; group = label['groups'][0]
    if change == 'unknown_id': group['evidence_item_ids'] = ['#/texts/99']
    if change == 'neighbor_only': group['evidence_item_ids'] = ['#/texts/1']
    if change == 'overlap': group['context_item_ids'] = ['#/texts/2']
    if change == 'duplicate_id': group['evidence_item_ids'] *= 2
    if change == 'extra_group': group['score'] = 1
    if change == 'missing_row': data['classifications'] = []
    if change == 'duplicate_row': data['classifications'].append(copy.deepcopy(row))
    if change == 'unknown_topic': label['topic'] = 'invented'
    if change == 'empty_groups': label['groups'] = []
    if change == 'empty_evidence': group['evidence_item_ids'] = []
    if change == 'duplicate_topic': row['topics'].append(copy.deepcopy(label))
    if change == 'unknown_chunk': row['chunk_id'] = 'invented'
    if change == 'other_batch_chunk': group['context_item_ids'] = ['#/texts/0']
    with pytest.raises(ValueError):
        passages.validate_passage_classifications(data, doc, packets[1:])


def test_parent_groups_and_exact_deduplication():
    doc = source(); packets = passages.build_passage_packets(doc)[1:]
    data = answer(topic='interest_and_fees.pik_toggle')
    data['classifications'][0]['topics'].append(copy.deepcopy(data['classifications'][0]['topics'][0]))
    data['classifications'][0]['topics'][-1]['topic'] = 'interest_and_fees'
    rows = passages.validate_passage_classifications(data, doc, packets)
    assert [t['topic'] for t in rows[0]['topics']] == ['interest_and_fees','interest_and_fees.pik_toggle']
    assert all(len(t['groups']) == 1 for t in rows[0]['topics'])


def test_explicit_list_neighbors_are_atomic_and_heading_only_is_rejected():
    doc = source()
    for item in doc['chunks'][0]['items']: item['container_path'] = ['#/body','#/groups/0']
    doc['chunks'][0]['atomic_group_ids'] = ['#/groups/0']
    packets = passages.build_passage_packets(doc)
    assert len(packets[1]['neighbor_items']) == 2
    doc['chunks'][1]['items'][0]['heading_path'] = [{'item_id':'#/texts/0','text':'Borrower','depth':1}]
    packets = passages.build_passage_packets(doc, boundary_context_groups=0)
    with pytest.raises(ValueError):
        passages.validate_passage_classifications(answer(evidence=['#/texts/0']), doc, packets[1:])


@pytest.mark.parametrize('limit', [True, -1, 1.5, '1', None])
def test_neighbor_limit_validation(limit):
    with pytest.raises(ValueError): passages.build_passage_packets(source(), boundary_context_groups=limit)


def test_no_neighbors_and_no_pages_and_unclassified():
    doc = source()
    for chunk in doc['chunks']:
        for item in chunk['items']: item['pages'] = []
    packets = passages.build_passage_packets(doc, boundary_context_groups=0)
    assert all(not p['neighbor_items'] for p in packets)
    rows = passages.validate_passage_classifications(answer(), doc, packets[1:])
    assert rows[0]['topics'][0]['groups'][0]['evidence_pages'] == []
    assert passages.validate_passage_classifications({'classifications':[
        {'chunk_id':'chunk-1','topics':[]}]}, doc, packets[1:])[0]['topics'] == []


def test_multiple_topics_and_groups_keep_distinct_original_references():
    doc = source(); packets = passages.build_passage_packets(doc)
    data = {'classifications':[{'chunk_id':'chunk-0','topics':[
        {'topic':'parties_and_roles','groups':[{'evidence_item_ids':['#/texts/0'],'context_item_ids':[]}]},
        {'topic':'interest_and_fees','groups':[
            {'evidence_item_ids':['#/texts/2','#/texts/1'],'context_item_ids':[]},
            {'evidence_item_ids':['#/texts/1'],'context_item_ids':['#/texts/0']}]}]}]}
    rows = passages.validate_passage_classifications(data,doc,packets[:1])
    labels = rows[0]['topics']
    assert labels[0]['groups'][0]['evidence_item_ids'] == ['#/texts/0']
    assert len(labels[1]['groups']) == 2
    assert labels[1]['groups'][1]['evidence_item_ids'] == ['#/texts/1','#/texts/2']
    assert labels[1]['groups'][0]['group_id'] != labels[1]['groups'][1]['group_id']


def test_oversized_list_neighbor_is_complete_not_truncated():
    doc = source()
    for item in doc['chunks'][0]['items']:
        item['original_text'] = 'x'*25000
        item['container_path'] = ['#/groups/0']
    doc['chunks'][0]['atomic_group_ids'] = ['#/groups/0']
    packet = passages.build_passage_packets(doc)[1]
    assert [len(i['text']) for i in packet['neighbor_items']] == [25000,25000]


def test_table_core_rendering_preserved_and_missing_neighbor_table_is_explicit():
    doc = source(); table = doc['chunks'][0]['items'][0]
    table.update(item_id='#/tables/0',text='',original_text='')
    doc['chunks'][0]['item_ids'][0] = '#/tables/0'
    doc['source_reading_order'][0] = '#/tables/0'
    doc['chunks'][0]['content'] = 'Rate\tMargin\nSOFR\t3%\nInterest is'
    packets = passages.build_passage_packets(doc,boundary_context_groups=0)
    assert packets[0]['content'] == doc['chunks'][0]['content']
    # A two-group neighbor window reaches the table. Do not silently send an
    # empty table or guess which joined text belongs to its cells.
    with pytest.raises(ValueError,match='Neighbor table requires canonical'):
        passages.build_passage_packets(doc,boundary_context_groups=2)


@pytest.mark.parametrize('extra_at', ['response','row','topic','missing_context'])
def test_model_contract_is_strict_at_every_level(extra_at):
    doc = source(); packets = passages.build_passage_packets(doc)[1:]
    data = answer()
    if extra_at == 'response': data['summary'] = 'not allowed'
    if extra_at == 'row': data['classifications'][0]['confidence'] = 1
    if extra_at == 'topic': data['classifications'][0]['topics'][0]['score'] = 1
    if extra_at == 'missing_context':
        del data['classifications'][0]['topics'][0]['groups'][0]['context_item_ids']
    with pytest.raises(ValueError): passages.validate_passage_classifications(data,doc,packets)
