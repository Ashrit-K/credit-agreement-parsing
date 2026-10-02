import inspect
import json
import pytest

import credit_agreement_extractor as api


def test_a10_enabled_by_default():
    assert inspect.signature(api.convert_document).parameters['use_hierarchy'].default is True


def test_heuristic_api_removed():
    assert not hasattr(api, 'classify_chunks')
    assert not hasattr(api, 'TopicSignalsArtifact')
    assert 'classify_chunks' not in api.__all__
    assert 'TopicSignalsArtifact' not in api.__all__


def test_classifier_takes_chunks_only():
    parameters = inspect.signature(api.reflect_topics).parameters
    assert 'signals' not in parameters
    assert 'use_b2' not in parameters


def test_current_layout_profiles_outputs_and_traces(tmp_path):
    from test_topic_reflection import artifacts, FakeClient
    chunks = artifacts(tmp_path)
    options = dict(debug=True, run_id='current', trace_root=tmp_path/'runs')
    classified = api.reflect_topics(chunks, client=FakeClient(), **options)
    mapped = api.build_topic_map(chunks, classified, **options)
    result = json.loads(classified.classifications_json_path.read_text())
    assert result['pipeline_layout'] == result['profile']['pipeline_layout'] == 'stage-b-v2'
    assert not {'proposed_topics', 'use_b2', 'signals_json_sha256'} & result.keys()
    assert not {'use_b2', 'signals_json_sha256'} & result['profile'].keys()
    assert json.loads(mapped.topic_map_json_path.read_text())['pipeline_layout'] == 'stage-b-v2'
    assert list((tmp_path/'stage-b-v2'/'b2-checkpoints').rglob('batch-*.json'))
    assert not (tmp_path/'b3-checkpoints').exists()
    snapshots = list((tmp_path/'runs'/'current'/'debug').glob('*.json'))
    assert any(p.name.startswith('B2-request') for p in snapshots)
    assert any(p.name.startswith('B3-final') for p in snapshots)
    assert not any(p.name.startswith('B4-') for p in snapshots)


def test_new_layout_preserves_historical_artifacts(tmp_path):
    from test_topic_reflection import artifacts, FakeClient
    chunks = artifacts(tmp_path)
    historical = [tmp_path/'document.topic-passages.json', tmp_path/'document.topic-passage-map.json']
    for path in historical:
        path.write_bytes(b'historical saved bytes')
    classified = api.reflect_topics(chunks, client=FakeClient(), trace_root=tmp_path/'runs')
    mapped = api.build_topic_map(chunks, classified, trace_root=tmp_path/'runs')
    assert all(path.read_bytes() == b'historical saved bytes' for path in historical)
    assert classified.classifications_json_path.parent.name == 'stage-b-v2'
    assert mapped.topic_map_json_path.parent == classified.classifications_json_path.parent


def test_failed_basic_run_records_layout_before_validation(tmp_path):
    from test_topic_reflection import artifacts, FakeClient
    chunks = artifacts(tmp_path)
    chunks.chunks_json_path.write_text('{}')
    with pytest.raises(ValueError):
        api.reflect_topics(chunks, client=FakeClient(), run_id='failed', trace_root=tmp_path/'runs')
    events = [json.loads(line) for path in (tmp_path/'runs'/'failed').glob('*.jsonl')
              for line in path.read_text().splitlines()]
    assert any(event.get('pipeline_layout') == 'stage-b-v2' for event in events)


def test_human_annotations_rejected_even_with_valid_b1_fields(tmp_path):
    from test_topic_reflection import artifacts, FakeClient
    chunks = artifacts(tmp_path)
    document = json.loads(chunks.chunks_json_path.read_text())
    document['annotations'] = {'#/texts/0': {'topics': ['covenants']}}
    chunks.chunks_json_path.write_text(json.dumps(document))
    client = FakeClient()
    with pytest.raises(ValueError):
        api.reflect_topics(chunks, client=client, trace_root=tmp_path/'runs')
    assert client.calls == []
