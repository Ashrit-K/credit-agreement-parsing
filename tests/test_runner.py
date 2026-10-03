"""The composed runner triggers D only after successful B3 completion."""
import json
import pytest


def test_handoff_order_run_identity_and_separate_model_overrides(tmp_path, monkeypatch):
    from credit_agreement_extractor import runner
    calls = []
    def stage(name, output):
        def invoke(*args, **kwargs):
            calls.append((name, args, kwargs)); return output
        return invoke
    for name, output in [('convert_document', 'a'), ('build_chunks', 'chunks'),
                         ('reflect_topics', 'classified'), ('build_topic_map', 'map'),
                         ('extract_credit_terms', {'status': 'completed'})]:
        monkeypatch.setattr(runner, name, stage(name, output))
    result = runner.run_pipeline('example.pdf', model='extract-model',
        reasoning_effort='high', classification_model='classify-model',
        classification_reasoning_effort='low', use_hierarchy=False,
        debug=True, run_id='composed', trace_root=tmp_path)
    assert result['status'] == 'completed'
    assert [c[0] for c in calls] == ['convert_document', 'build_chunks', 'reflect_topics',
                                   'build_topic_map', 'extract_credit_terms']
    assert calls[0][2]['use_hierarchy'] is False
    assert calls[2][2]['model'] == 'classify-model'
    assert calls[2][2]['reasoning_effort'] == 'low'
    assert calls[4][2]['model'] == 'extract-model'
    assert calls[4][2]['conversion'] == 'a'
    assert {c[2]['run_id'] for c in calls} == {'composed'}
    events = [json.loads(x) for x in (tmp_path/'composed/events.jsonl').read_text().splitlines()]
    assert any(e['event'] == 'topic_map_ready' for e in events)


def test_failed_topic_map_never_starts_extraction(tmp_path, monkeypatch):
    from credit_agreement_extractor import runner
    for name in ('convert_document', 'build_chunks', 'reflect_topics'):
        monkeypatch.setattr(runner, name, lambda *a, **k: object())
    def fail(*a, **k): raise ValueError('Incomplete map')
    monkeypatch.setattr(runner, 'build_topic_map', fail)
    called = []
    monkeypatch.setattr(runner, 'extract_credit_terms', lambda *a, **k: called.append(True))
    with pytest.raises(ValueError): runner.run_pipeline('test.pdf', trace_root=tmp_path)
    assert called == []


def test_public_exports_and_existing_scaffold_retained():
    from credit_agreement_extractor import extract_credit_terms, run_pipeline, extract_parties
    assert all(callable(f) for f in (extract_credit_terms, run_pipeline, extract_parties))


def test_runner_preserves_classifier_default_when_model_omitted(tmp_path, monkeypatch):
    from credit_agreement_extractor import runner
    for name in ('convert_document', 'build_chunks', 'build_topic_map'):
        monkeypatch.setattr(runner, name, lambda *a, **k: object())
    def classify(*a, **kwargs):
        assert kwargs.get('model', 'deepseek-v4-flash') == 'deepseek-v4-flash'
        return object()
    monkeypatch.setattr(runner, 'reflect_topics', classify)
    monkeypatch.setattr(runner, 'extract_credit_terms', lambda *a, **k: {})
    runner.run_pipeline('test.pdf', trace_root=tmp_path)
