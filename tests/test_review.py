import json
import credit_agreement_extractor.review as review_module
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from credit_agreement_extractor.review import export_run_review, load_run_review, build_topic_review, build_stage_review


def test_controller_recorded_layout_survives_d_only_history():
    from credit_agreement_extractor.review import review_layout
    assert review_layout({'job': {'pipeline_layout': 'stage-b-v2'},
                          'events': [], 'snapshots': []}) == 'stage-b-v2'
    assert review_layout({'job': {'pipeline_layout': None},
                          'events': [], 'snapshots': []}) == 'historical'


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


def test_review_loads_current_extraction_and_conversion_substeps(tmp_path):
    run = saved_run(tmp_path)
    for stage in ('A9', 'A3.1', 'B5', 'D1', 'D2', 'D3', 'D4'):
        (run/'debug'/f'{stage}-output-one.json').write_text(json.dumps({'stage': stage}))
    data = load_run_review('review-1', trace_root=tmp_path)
    stages = build_stage_review(data)
    assert stages['D4']['return_value']['stage'] == 'D4'
    assert stages['A9']['return_value']['stage'] == 'A9'
    assert stages['B5']['return_value']['stage'] == 'B5'


def test_extraction_model_exchanges_are_paired_by_attempt(tmp_path):
    from credit_agreement_extractor.review import build_model_exchanges
    data = {'pipeline_layout': 'stage-b-v2', 'snapshots': [
        {'filename': 'D2-request-a.json', 'data': {'attempt_id': 'a'}},
        {'filename': 'D2-request-b.json', 'data': {'attempt_id': 'b'}},
        {'filename': 'D2-response-b.json', 'data': {'attempt_id': 'b'}},
        {'filename': 'D2-response-a.json', 'data': {'attempt_id': 'a'}}]}
    results = build_model_exchanges(data)
    assert [(r['request'], r['response']) for r in results] == [
        ('D2-request-a.json', 'D2-response-a.json'),
        ('D2-request-b.json', 'D2-response-b.json')]


def test_real_d2_trace_identity_and_validation_diagnostics(tmp_path):
    from credit_agreement_extractor.review import build_model_exchanges
    run = saved_run(tmp_path)
    (run/'debug'/'D3-validation-a.json').write_text(json.dumps({'_trace': {'attempt_id': 'a'}, 'errors': ['bad citation']}))
    assert any(s['filename']=='D3-validation-a.json' for s in load_run_review('review-1',trace_root=tmp_path)['snapshots'])
    data = {'pipeline_layout':'stage-b-v2', 'snapshots': [
        {'filename': 'D2-request-a.json', 'data': {'_trace': {'attempt_id':'a'}}},
        {'filename': 'D2-request-b.json', 'data': {'_trace': {'attempt_id':'b'}}},
        {'filename': 'D2-response-b.json', 'data': {'_trace': {'attempt_id':'b'}}},
        {'filename': 'D3-validation-a.json', 'data': {'_trace': {'attempt_id':'a'}}},
        {'filename': 'D2-response-a.json', 'data': {'_trace': {'attempt_id':'a'}}}]}
    rows=build_model_exchanges(data)
    assert rows[0]['response']=='D2-response-a.json' and rows[0]['error']=='D3-validation-a.json'


def test_extraction_only_review_renders_without_topic_classifications(tmp_path):
    run = saved_run(tmp_path)
    result = {'parties': [], 'source_evidence': {'#/texts/1': {'text': 'Actual borrower', 'pages': [1]}}}
    (run/'debug'/'D1-output-one.json').write_text(json.dumps(result))
    html = export_run_review('review-1', tmp_path/'d.html', trace_root=tmp_path).read_text()
    assert 'Actual borrower' in html
    assert 'Extraction result' in html


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


def test_topic_review_accepts_explicit_b2_bypass_without_fake_signals():
    data = topic_snapshots()
    data['snapshots'] = [s for s in data['snapshots'] if not s['filename'].startswith('B2-')]
    final = next(s['data'] for s in data['snapshots'] if s['filename'].startswith('B3-final'))
    final['profile'] = {'use_b2': False}
    result = build_topic_review(data)
    assert result['use_b2'] is False
    assert result['chunks'][0]['proposed_topics'] == []
    assert result['chunks'][0]['rule_evidence'] is None
    assert result['chunks'][0]['final_topics'][0]['topic'] == 'interest_and_fees'


def test_topic_review_does_not_use_stale_b2_when_explicitly_disabled():
    data = topic_snapshots()
    data['snapshots'][3]['data']['profile'] = {'use_b2': False}
    result = build_topic_review(data)
    assert result['chunks'][0]['proposed_topics'] == []
    assert result['chunks'][0]['rule_evidence'] is None


def test_topic_review_requires_b2_for_enabled_or_legacy_runs():
    data = topic_snapshots()
    data['snapshots'] = [s for s in data['snapshots'] if not s['filename'].startswith('B2-')]
    assert build_topic_review(data) is None


def test_html_reviewer_handles_skipped_b2_explicitly():
    template = Path(review_module.__file__).with_name('review.html').read_text()
    assert 'B2 was skipped for this classification' in template
    assert 'chunk.rule_evidence?.signals' in template


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
def test_model_exchanges_match_interleaved_attempt_ids():
    data = {'snapshots': [
        {'filename': 'B3-request-a.json', 'data': {'batch_id': 'batch-1', 'attempt': 1, 'attempt_id': 'a'}},
        {'filename': 'B3-request-b.json', 'data': {'batch_id': 'batch-2', 'attempt': 1, 'attempt_id': 'b'}},
        {'filename': 'B3-response-b.json', 'data': {'batch_id': 'batch-2', 'attempt': 1, 'attempt_id': 'b'}},
        {'filename': 'B3-response-a.json', 'data': {'batch_id': 'batch-1', 'attempt': 1, 'attempt_id': 'a'}},
        {'filename': 'B3-validation-error-a.json', 'data': {'batch_id': 'batch-1', 'attempt': 1, 'attempt_id': 'a'}},
    ]}
    assert hasattr(review_module, 'build_model_exchanges')
    assert review_module.build_model_exchanges(data) == [
        {'request': 'B3-request-a.json', 'response': 'B3-response-a.json',
         'error': 'B3-validation-error-a.json'},
        {'request': 'B3-request-b.json', 'response': 'B3-response-b.json', 'error': None},
    ]


def test_model_exchanges_keep_legacy_restarts_separate():
    meta = {'batch_id': 'batch-1', 'attempt': 1}
    data = {'snapshots': [
        {'filename': 'B3-request-old.json', 'data': meta},
        {'filename': 'B3-validation-error-old.json', 'data': meta},
        {'filename': 'B3-request-new.json', 'data': meta},
        {'filename': 'B3-response-new.json', 'data': meta},
    ]}
    assert hasattr(review_module, 'build_model_exchanges')
    assert review_module.build_model_exchanges(data) == [
        {'request': 'B3-request-old.json', 'response': None,
         'error': 'B3-validation-error-old.json'},
        {'request': 'B3-request-new.json', 'response': 'B3-response-new.json', 'error': None},
    ]


def test_stage_c_pairs_boundaries_by_span_not_completion_order():
    data = {'snapshots': [
        {'filename': 'C-input-a.json', 'data': {'args': ['A'], '_trace': {'span_id': 'a'}}},
        {'filename': 'C-input-b.json', 'data': {'args': ['B'], '_trace': {'span_id': 'b'}}},
        {'filename': 'C-output-b.json', 'data': {'text': 'B response', '_trace': {'span_id': 'b'}}},
        {'filename': 'C-output-a.json', 'data': {'text': 'A response', '_trace': {'span_id': 'a'}}},
    ]}
    stage = build_stage_review(data)['C']
    assert stage['input']['args'] == ['A']
    assert stage['return_value']['text'] == 'A response'


def test_stage_c_does_not_substitute_old_output_for_pending_attempt():
    data = {'snapshots': [
        {'filename': 'C-input-a.json', 'data': {'args': ['A'], '_trace': {'span_id': 'a'}}},
        {'filename': 'C-output-a.json', 'data': {'text': 'A response', '_trace': {'span_id': 'a'}}},
        {'filename': 'C-input-b.json', 'data': {'args': ['B'], '_trace': {'span_id': 'b'}}},
    ]}
    stage = build_stage_review(data)['C']
    assert stage['input']['args'] == ['B']
    assert stage['return_value'] is None


def passage_snapshots():
    data = topic_snapshots()
    chunks = data['snapshots'][1]['data']['chunks_json_path']['chunks']
    chunks[0]['items'].append({'item_id':'#/texts/2','original_text':'Unrelated notice.', 'pages':[3]})
    chunks.append({'chunk_id':'chunk-0','pages':[2],'content':'Interest terms',
                   'items':[{'item_id':'#/texts/0','original_text':'Interest terms', 'pages':[2]}]})
    data['snapshots'][2]['data']['topic_signals_json_path']['classifications'].append(
        {'chunk_id':'chunk-0','proposed_topics':[]})
    group = {'group_id':'passage-one','evidence_item_ids':['#/texts/1'],
             'context_item_ids':['#/texts/0'],'evidence_pages':[3],'context_pages':[2],
             'source_chunk_ids':['chunk-0','chunk-1']}
    data['snapshots'][3]['data'] = {'schema_version':2,'classifications':[
        {'chunk_id':'chunk-1','topics':[{'topic':'interest_and_fees','groups':[group]}]},
        {'chunk_id':'chunk-0','topics':[]}]}
    data['snapshots'][4]['data'] = {'schema_version':2,
        'topics':{'interest_and_fees':[group]},'unclassified_chunk_ids':['chunk-0']}
    return data


def test_passage_review_resolves_roles_without_unrelated_page_text():
    result = build_topic_review(passage_snapshots())
    assert result['schema_version'] == 2 and not result['legacy_citations']
    group = result['passage_topics']['interest_and_fees'][0]
    assert group['evidence_items'][0]['text'] == 'Interest payable in arrears.'
    assert group['evidence_items'][0]['pages'] == [3]
    assert group['context_items'][0]['text'] == 'Interest terms'
    assert group['context_items'][0]['pages'] == [2]
    assert 'Unrelated notice.' not in json.dumps(group)
    assert group['target_chunk_ids'] == ['chunk-1']
    assert len(result['chunks'][0]['items']) == 2  # Full context still available.


def test_legacy_review_does_not_invent_evidence_roles():
    result = build_topic_review(topic_snapshots())
    assert result['legacy_citations'] and result['passage_topics'] == {}


def test_passage_review_missing_citation_is_an_error_not_fabricated_text():
    data = passage_snapshots()
    data['snapshots'][4]['data']['topics']['interest_and_fees'][0]['context_item_ids'] = ['#/texts/99']
    with pytest.raises(ValueError): build_topic_review(data)


def test_item_renderer_shows_heading_provenance_separately_from_selected_context():
    template = Path(review_module.__file__).with_name('review.html').read_text()
    assert "'Source heading path: '" in template
    assert 'item.heading_path' in template


def test_chunk_inspector_uses_passage_records_for_v2_map_references():
    template = Path(review_module.__file__).with_name('review.html').read_text()
    assert 'mapReferences(c)' in template
    assert 'review.passage_topics[topic]' in template


def current_snapshots():
    data = passage_snapshots()
    data['snapshots'][3]['filename'] = 'B2-final-1.json'
    data['snapshots'][3]['data']['profile'] = {'pipeline_layout': 'stage-b-v2'}
    data['snapshots'][4]['filename'] = 'B3-final-1.json'
    return data


def test_current_review_uses_explicit_layout_and_ignores_stale_guesses():
    result = build_topic_review(current_snapshots())
    assert result['pipeline_layout'] == 'stage-b-v2'
    assert result['classification_stage'] == 'B2'
    assert result['map_stage'] == 'B3'
    assert result['chunks'][0]['proposed_topics'] == []
    assert result['chunks'][0]['rule_evidence'] is None
    assert result['passage_topics']['interest_and_fees'][0]['evidence_items'][0]['pages'] == [3]


def test_unmarked_bypass_remains_historical_layout():
    data = passage_snapshots()
    data['snapshots'][3]['data']['profile'] = {'use_b2': False}
    result = build_topic_review(data)
    assert result['classification_stage'] == 'B3'
    assert result['map_stage'] == 'B4'


def test_current_model_exchanges_pair_attempt_ids_and_ignore_old_prefix():
    data = current_snapshots()
    data['snapshots'] += [
        {'filename': 'B2-request-a.json', 'data': {'attempt_id': 'a'}},
        {'filename': 'B2-request-b.json', 'data': {'attempt_id': 'b'}},
        {'filename': 'B2-response-b.json', 'data': {'attempt_id': 'b'}},
        {'filename': 'B3-request-old.json', 'data': {'attempt_id': 'a'}},
        {'filename': 'B2-response-a.json', 'data': {'attempt_id': 'a'}},
    ]
    assert review_module.build_model_exchanges(data) == [
        {'request': 'B2-request-a.json', 'response': 'B2-response-a.json', 'error': None},
        {'request': 'B2-request-b.json', 'response': 'B2-response-b.json', 'error': None},
    ]


def test_current_export_retains_classification_exchanges(tmp_path):
    run = saved_run(tmp_path)
    for snapshot in current_snapshots()['snapshots']:
        (run / 'debug' / snapshot['filename']).write_text(json.dumps(snapshot['data']))
    (run / 'debug' / 'B2-request-new.json').write_text(json.dumps({'attempt_id': 'new'}))
    html = export_run_review('review-1', tmp_path / 'current.html', trace_root=tmp_path).read_text()
    embedded = json.loads(re.search(r'id="run-data">(.*?)</script>', html, re.S).group(1))
    assert embedded['pipeline_layout'] == 'stage-b-v2'
    assert any(s['filename'] == 'B2-request-new.json' for s in embedded['snapshots'])


def test_source_metadata_cannot_relabel_historical_stage_numbers():
    data = topic_snapshots()
    data['snapshots'][0]['data']['docling_json_path']['pipeline_layout'] = 'stage-b-v2'
    assert build_topic_review(data)['classification_stage'] == 'B3'


def test_current_input_profile_selects_layout_before_classification_finishes():
    data = {'snapshots': [{'filename': 'B2-input-artifacts-one.json',
                          'data': {'profile': {'pipeline_layout': 'stage-b-v2'}}}]}
    assert review_module.review_layout(data) == 'stage-b-v2'


def test_current_event_selects_layout_without_inventing_missing_outputs():
    data = {'events': [{'event': 'pipeline_layout', 'stage': 'B2',
                        'pipeline_layout': 'stage-b-v2'}], 'snapshots': []}
    assert review_module.review_layout(data) == 'stage-b-v2'
    assert build_topic_review(data) is None
    assert build_stage_review(data)['B2']['output'] is None


@pytest.mark.parametrize('status', ['completed', 'failed'])
def test_standalone_current_map_entry_selects_layout_without_debug(status):
    data = {'events': [
        {'event': 'pipeline_layout', 'stage': 'B3', 'pipeline_layout': 'stage-b-v2'},
        {'event': 'stage_finished', 'stage': 'B3', 'status': status}], 'snapshots': []}
    assert review_module.review_layout(data) == 'stage-b-v2'
    assert build_topic_review(data) is None
    assert build_stage_review(data)['B3']['output'] is None


@pytest.mark.parametrize('stage,event', [('A', 'pipeline_layout'), ('B3', 'source_artifact')])
def test_untrusted_source_events_cannot_change_review_numbering(stage, event):
    data = {'events': [{'stage': stage, 'event': event, 'pipeline_layout': 'stage-b-v2'}],
            'snapshots': []}
    assert review_module.review_layout(data) == 'historical'


def test_current_stage_details_do_not_expose_stale_heuristic_snapshots():
    stages = build_stage_review(current_snapshots())
    assert not stages['B2']['output']


@pytest.mark.parametrize('current', [True, False, None])
def test_javascript_renders_layout_controls_and_evidence(current):
    """Execute the standalone script with a small DOM, without dependencies."""
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is unavailable for the standalone JavaScript check.')
    data = current_snapshots() if current else passage_snapshots()
    if current is None:
        data = {'pipeline_layout': 'stage-b-v2', 'snapshots': [], 'events': []}
    data.update(run_id='disposable', pipeline_layout=review_module.review_layout(data))
    data['review'] = build_topic_review(data)
    data['stages'] = build_stage_review(data)
    data['model_exchanges'] = []
    template = Path(review_module.__file__).with_name('review.html').read_text()
    script = re.findall(r'<script>(.*?)</script>', template, re.S)[0]
    harness = r'''
class Element {
 constructor(){this.children=[];this.dataset={};this.style={};this.classList={toggle(){},remove(){},add(){}};this.value='';this.textContent=''}
 append(...items){this.children.push(...items)}
 replaceChildren(...items){this.children=items}
 setAttribute(){}
 addEventListener(){}
 get options(){return this.children}
 querySelector(){return this.children[0]}
 querySelectorAll(){return []}
}
const elements=new Map();
const document={body:new Element(),getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id)},createElement(){return new Element()},createTextNode(text){return {textContent:text}},querySelector(id){return this.getElementById(id)},querySelectorAll(){return []}};
document.getElementById('run-data').textContent=JSON.stringify(INPUT);
'''
    checks = r'''
function visible(element){return [element.textContent,...(element.children||[]).map(visible)].join(' ')}
const initial={controls:document.getElementById('stage').options.map(o=>o.textContent),source:visible(document.getElementById('source')),results:visible(document.getElementById('classification'))};
stage='B2';selected=null;render();initial.classification=visible(document.getElementById('classification'));initial.classificationSource=visible(document.getElementById('source'));
if(currentLayout){stage='B4';render();initial.pending=visible(document.getElementById('source'));stage='B1';topic='__all';selected=null;render();initial.chunk=visible(document.getElementById('source'))}
console.log(JSON.stringify(initial));
'''
    result = subprocess.run([node, '-'], input='const INPUT='+json.dumps(data)+';\n'+harness+script+checks,
                            text=True, capture_output=True, check=True)
    rendered = json.loads(result.stdout)
    if current is None:
        assert 'No source classification captured' in rendered['classificationSource']
        return
    assert 'Interest payable in arrears.' in rendered['source']
    if current:
        assert 'B2 · LLM classifications' in rendered['controls']
        assert 'B3 · Topic map' in rendered['controls']
        assert not any('Heuristic' in option for option in rendered['controls'])
        assert 'B2 selected this passage group; B3 indexes' in rendered['results']
        assert 'B2 proposals' not in rendered['results']
        assert 'B2 proposals' not in rendered['classification']
        assert 'No output recorded for this run.' in rendered['pending']
        assert 'Interest payable in arrears.' in rendered['chunk']
    else:
        assert 'B3 selected this passage group; B4 indexes' in rendered['results']
        assert 'B2 proposals' in rendered['results']
