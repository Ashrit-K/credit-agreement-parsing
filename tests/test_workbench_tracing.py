import gzip
import json

import pytest

from credit_agreement_extractor import tracing
from credit_agreement_extractor.conversion import convert_document, InvalidDocumentInputError
from test_conversion import RecordingConverter, FailingConverter, FakeDoclingDocument


def events(root, run):
    return [json.loads(line) for line in (root/run/'events.jsonl').read_text().splitlines()]


def starts(rows):
    return [row['stage'] for row in rows if row['event'] == 'stage_started']


def test_step_is_noop_without_trace_and_restores_nested_failure(tmp_path):
    assert hasattr(tracing, 'trace_step')
    with tracing.trace_step('unused') as record:
        record({'answer': 1})

    @tracing.traced('parent')
    def operation(**kwargs):
        with tracing.trace_step('child', {'api_key': 'secret'}) as record:
            record({'answer': 1})
            with pytest.raises(ValueError):
                with tracing.trace_step('failed'):
                    raise ValueError('sensitive')
            tracing.current_trace().event('restored')
        tracing.current_trace().event('parent_restored')

    operation(debug=True, run_id='nested', trace_root=tmp_path)
    rows = events(tmp_path, 'nested')
    by_stage = {r['stage']: r for r in rows if r['event']=='stage_started'}
    assert by_stage['child']['parent_span_id'] == by_stage['parent']['span_id']
    assert by_stage['failed']['parent_span_id'] == by_stage['child']['span_id']
    assert next(r for r in rows if r['event']=='restored')['span_id'] == by_stage['child']['span_id']
    assert next(r for r in rows if r['event']=='parent_restored')['span_id'] == by_stage['parent']['span_id']
    assert next(r for r in rows if r['event']=='stage_finished' and r['stage']=='failed')['status']=='failed'
    assert 'sensitive' not in (tmp_path/'nested'/'events.jsonl').read_text()


@pytest.mark.parametrize('suffix,compressed,setup', [('.pdf', False, 'A5'), ('.htm', False, 'A6'), ('.htm', True, 'A6')])
def test_conversion_records_only_actual_paths_and_full_debug_evidence(tmp_path, suffix, compressed, setup):
    source = tmp_path/('source'+suffix)
    content = b'<html>agreement</html>' if suffix=='.htm' else b'%PDF source'
    original_bytes = gzip.compress(content) if compressed else content
    source.write_bytes(original_bytes)
    artifact = convert_document(source, tmp_path/'converted', converter=RecordingConverter(),
                                debug=True, run_id='fresh', trace_root=tmp_path/'runs')
    rows = events(tmp_path/'runs', 'fresh')
    assert starts(rows)==['A','A1','A2','A3','A4',setup]+(['A7'] if compressed else [])+['A8','A9','A10','A11']
    captured = [(p.name,json.loads(p.read_text())) for p in (tmp_path/'runs/fresh/debug').glob('*.json')]
    a8 = next(value for name,value in captured if name.startswith('A8-output-'))
    assert a8['canonical'] == FakeDoclingDocument().export_to_dict()
    assert a8['markdown'].startswith('# Credit Agreement')
    a11 = next(value for name,value in captured if name.startswith('A11-output-artifacts-'))
    assert a11['docling_json_path'] == FakeDoclingDocument().export_to_dict()
    assert a11['manifest_path']['source']['sha256']==artifact.source_sha256
    assert source.read_bytes()==original_bytes


def test_cache_trace_captures_cached_return_without_replaying_conversion(tmp_path):
    source=tmp_path/'source.pdf'; source.write_bytes(b'%PDF source')
    first=convert_document(source,tmp_path/'converted',converter=RecordingConverter(),trace_root=tmp_path/'runs')
    before={p:p.stat().st_mtime_ns for p in first.output_directory.iterdir()}
    artifact=convert_document(source,tmp_path/'converted',converter=FailingConverter(),debug=True,run_id='cached',trace_root=tmp_path/'runs')
    assert starts(events(tmp_path/'runs','cached'))==['A','A1','A2','A3','A3.1']
    assert artifact.cached
    assert before=={p:p.stat().st_mtime_ns for p in before}
    outputs=list((tmp_path/'runs/cached/debug').glob('A3.1-output-*.json'))
    assert any(json.loads(p.read_text()).get('cached') is True for p in outputs)


def test_disabled_hierarchy_is_explicit_skip_and_invalid_input_fails_a1(tmp_path):
    source=tmp_path/'source.pdf'; source.write_bytes(b'%PDF source')
    convert_document(source,tmp_path/'converted',converter=RecordingConverter(),use_hierarchy=False,run_id='off',trace_root=tmp_path/'runs')
    rows=events(tmp_path/'runs','off')
    assert 'A10' not in starts(rows)
    assert any(r['event']=='stage_skipped' and r['stage']=='A10' for r in rows)
    with pytest.raises(InvalidDocumentInputError):
        convert_document(tmp_path/'missing.pdf',run_id='invalid',trace_root=tmp_path/'runs')
    rows=events(tmp_path/'runs','invalid')
    assert starts(rows)==['A','A1']
    assert next(r for r in rows if r['event']=='stage_finished' and r['stage']=='A1')['status']=='failed'


def test_converter_failure_is_at_a8_without_later_stages(tmp_path):
    source=tmp_path/'source.pdf'; source.write_bytes(b'%PDF source')
    with pytest.raises(AssertionError):
        convert_document(source,tmp_path/'converted',converter=FailingConverter(),run_id='failed',trace_root=tmp_path/'runs')
    rows=events(tmp_path/'runs','failed')
    assert starts(rows)==['A','A1','A2','A3','A4','A5','A8']
    assert next(r for r in rows if r['event']=='stage_finished' and r['stage']=='A8')['status']=='failed'


def test_debug_does_not_read_incomplete_cache_before_cache_validation(tmp_path):
    source=tmp_path/'source.pdf'; source.write_bytes(b'%PDF source')
    first=convert_document(source,tmp_path/'converted',converter=RecordingConverter(),trace_root=tmp_path/'runs')
    first.hierarchy_json_path.write_text('{')
    replacement=RecordingConverter()
    result=convert_document(source,tmp_path/'converted',converter=replacement,debug=True,run_id='repair',trace_root=tmp_path/'runs')
    assert not result.cached
    assert replacement.received_paths==[source]


def test_cache_decision_closes_skipped_paths_after_cached_return(tmp_path):
    source=tmp_path/'source.pdf'; source.write_bytes(b'%PDF source')
    convert_document(source,tmp_path/'converted',converter=RecordingConverter(),trace_root=tmp_path/'runs')
    convert_document(source,tmp_path/'converted',converter=FailingConverter(),run_id='cached-state',trace_root=tmp_path/'runs')
    rows=events(tmp_path/'runs','cached-state')
    hit=next(r for r in rows if r['event']=='cache_hit' and r['stage']=='A3.1')
    finished=next(r for r in rows if r['event']=='stage_finished' and r['stage']=='A3.1')
    assert rows.index(hit)>rows.index(finished)
    assert hit['span_id']!=finished['span_id']
    assert {r['stage'] for r in rows if r['event']=='stage_skipped' and r['reason']=='cache_hit'}=={'A4','A5','A6','A7','A8','A9','A10','A11'}


def test_fresh_plain_pdf_decisions_and_a9_output_are_recorded(tmp_path):
    source=tmp_path/'source.pdf'; source.write_bytes(b'%PDF source')
    artifact=convert_document(source,tmp_path/'converted',converter=RecordingConverter(),debug=True,run_id='decisions',trace_root=tmp_path/'runs')
    rows=events(tmp_path/'runs','decisions')
    skipped={r['stage']:r for r in rows if r['event']=='stage_skipped'}
    assert set(skipped)=={'A3.1','A6','A7'}
    assert skipped['A3.1']['reason']=='cache_miss'
    assert skipped['A6']['reason']=='unselected_format'
    assert skipped['A7']['reason']=='not_gzip_html'
    output=json.loads(next((tmp_path/'runs/decisions/debug').glob('A9-output-*.json')).read_text())
    assert output['canonical']==json.loads(artifact.docling_json_path.read_text())
    assert output['markdown']==artifact.markdown_path.read_text()
