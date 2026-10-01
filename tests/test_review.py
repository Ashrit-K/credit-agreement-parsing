import json
from pathlib import Path
import re

import pytest

from credit_agreement_extractor.review import export_run_review, load_run_review, build_topic_review, build_stage_review


def saved_run(tmp_path):
    run = tmp_path / 'review-1'
    (run / 'debug').mkdir(parents=True)
    (run / 'events.jsonl').write_text(json.dumps({'event':'stage_finished', 'stage':'B4',
                                               'status':'completed', 'time_unix':1})+'\n')
    (run / 'debug' / 'B4-final-one.json').write_text(json.dumps({'topics':{'covenants':[]}}))
    (run / 'debug' / 'unrelated.json').write_text('{"should_not_load":true}')
    return run


def test_loads_logged_events_and_allowlisted_snapshots(tmp_path):
    saved_run(tmp_path)
    data = load_run_review('review-1', trace_root=tmp_path)
    assert data['events'][0]['stage'] == 'B4'
    assert data['snapshots'][0]['data']['topics'] == {'covenants':[]}
    assert len(data['snapshots']) == 1
    assert data['run_id'] == 'review-1'


def test_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        load_run_review('../private', trace_root=tmp_path)


def test_missing_run_is_not_replaced_with_sample_data(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_run_review('missing', trace_root=tmp_path)


def test_export_escapes_untrusted_script_delimiters(tmp_path):
    run = saved_run(tmp_path)
    dangerous = '</script><script>alert(1)</script>'
    (run / 'debug' / 'B3-request-one.json').write_text(json.dumps({'system':dangerous}))
    destination = tmp_path / 'view.html'
    assert export_run_review('review-1', destination, trace_root=tmp_path) == destination
    text = destination.read_text()
    assert dangerous not in text
    assert r'\u003c/script\u003e' in text
    assert 'review-1' in text
    assert 'Source text' in text
    assert 'Illustrative preview' not in text


def test_embedded_json_round_trips_source_punctuation(tmp_path):
    run = saved_run(tmp_path)
    original = 'Borrower & Lender: x < 10; y > 5; </script>'
    (run / 'debug' / 'B3-request-one.json').write_text(json.dumps({'system':original}))
    destination = export_run_review('review-1', tmp_path / 'view.html', trace_root=tmp_path)
    embedded = re.search(r'id="run-data">(.*?)</script>', destination.read_text(), re.S).group(1)
    decoded = json.loads(embedded)
    assert decoded['snapshots'][0]['data']['system'] == original


def test_refuses_symlinked_run(tmp_path):
    run = saved_run(tmp_path)
    (tmp_path / 'alias').symlink_to(run, target_is_directory=True)
    with pytest.raises(ValueError):
        load_run_review('alias', trace_root=tmp_path)


def topic_snapshots():
    chunk = {'chunk_id':'chunk-1', 'pages':[3], 'content':'Interest payable in arrears.',
             'items':[{'item_id':'#/texts/1', 'original_text':'Interest payable in arrears.',
                       'text':'normalized wording', 'pages':[3], 'heading_path':[]} ]}
    return {'snapshots':[
        {'filename':'A-output-artifacts-1.json', 'data':{'docling_json_path':{
            'texts':[{'self_ref':'#/texts/1', 'text':'Interest payable in arrears.'}]}}},
        {'filename':'B1-output-artifacts-1.json', 'data':{'chunks_json_path':{'chunks':[chunk]}}},
        {'filename':'B2-output-artifacts-1.json', 'data':{'topic_signals_json_path':{
            'classifications':[{'chunk_id':'chunk-1', 'proposed_topics':['parties_and_roles']}]}}},
        {'filename':'B3-final-1.json', 'data':{'classifications':[{'chunk_id':'chunk-1',
            'topics':[{'topic':'interest_and_fees', 'item_ids':['#/texts/1']}]}]}},
        {'filename':'B4-final-1.json', 'data':{'topics':{'interest_and_fees':[
            {'chunk_id':'chunk-1', 'item_ids':['#/texts/1']}]}, 'unclassified_chunk_ids':[]}}
    ]}


def test_topic_review_joins_labels_to_original_source_text():
    result = build_topic_review(topic_snapshots())
    assert result['topics']['interest_and_fees'] == ['chunk-1']
    row = result['chunks'][0]
    assert row['items'][0]['text'] == 'Interest payable in arrears.'
    assert row['pages'] == [3]
    assert row['proposed_topics'] == ['parties_and_roles']
    assert row['final_topics'][0]['item_ids'] == ['#/texts/1']


def test_topic_review_resolves_cited_heading_outside_chunk():
    data = topic_snapshots()
    chunk = data['snapshots'][1]['data']['chunks_json_path']['chunks'][0]
    chunk['items'][0]['heading_path'] = [{'item_id':'#/texts/0','text':'Interest','depth':1}]
    data['snapshots'][3]['data']['classifications'][0]['topics'][0]['item_ids'] = ['#/texts/0']
    result = build_topic_review(data)
    assert result['chunks'][0]['headings'][0]['text'] == 'Interest'


def test_topic_review_preserves_unclassified_chunks():
    data = topic_snapshots()
    data['snapshots'][3]['data']['classifications'][0]['topics'] = []
    data['snapshots'][4]['data'] = {'topics':{'interest_and_fees':[]},'unclassified_chunk_ids':['chunk-1']}
    assert build_topic_review(data)['unclassified_chunk_ids'] == ['chunk-1']


def test_missing_topic_artifacts_are_explicit():
    assert build_topic_review({'snapshots':[]}) is None


def test_topic_review_renders_canonical_table_cells():
    data = topic_snapshots()
    canonical = data['snapshots'][0]['data']['docling_json_path']
    canonical['tables'] = [{'self_ref':'#/tables/0','data':{'table_cells':[
        {'start_row_offset':0,'text':'Rate'}, {'start_row_offset':0,'text':'1.5%'},
        {'start_row_offset':1,'text':'Payment'}, {'start_row_offset':1,'text':'In arrears'}]}}]
    chunk = data['snapshots'][1]['data']['chunks_json_path']['chunks'][0]
    chunk['items'] = [{'item_id':'#/tables/0','item_type':'table','pages':[3]}]
    result = build_topic_review(data)
    assert result['chunks'][0]['items'][0]['table'] == [['Rate','1.5%'],['Payment','In arrears']]


def test_stage_review_exposes_conversion_artifacts_and_stage_inputs():
    data = topic_snapshots()
    data['events'] = [{'stage':'A','event':'stage_finished','status':'completed'}]
    data['snapshots'].extend([
        {'filename':'A-input-one.json','data':{'args':['agreement.pdf']}},
        {'filename':'B1-input-artifacts-one.json','data':{'docling_json_path':{'name':'canonical'}}},
        {'filename':'B1-input-artifacts-two.json','data':{'hierarchy_json_path':{'items':{}}}},
        {'filename':'B1-input-args.json','data':{'args':['conversion-artifact']}},
        {'filename':'B1-input-artifacts-last.json','data':{'manifest_path':{'status':'completed'}}},
        {'filename':'B1-output-value.json','data':{'cached':False}},
        {'filename':'B1-output-artifacts-last.json','data':{'chunks_json_path':{'chunks':[]}}},
    ])
    stages = build_stage_review(data)
    assert stages['A']['input']['args'] == ['agreement.pdf']
    assert 'docling_json_path' in stages['A']['output']
    assert stages['B1']['input_artifacts']['hierarchy_json_path'] == {'items':{}}
    assert stages['B1']['input_artifacts']['docling_json_path'] == {'name':'canonical'}
    assert stages['B1']['input']['args'] == ['conversion-artifact']
    assert stages['B1']['return_value'] == {'cached':False}
    assert stages['A']['events'][0]['status'] == 'completed'
