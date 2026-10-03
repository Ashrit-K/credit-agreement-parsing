"""Stage D defaults are independent of classification and shared C settings."""
import inspect


def test_extraction_defaults_are_pro_high():
    from credit_agreement_extractor.runner import run_pipeline
    from credit_agreement_extractor.orchestrator import extract_credit_terms
    from credit_agreement_extractor.extraction_specialist import CreditTermSpecialist
    for function in (run_pipeline, extract_credit_terms, CreditTermSpecialist.run):
        parameters = inspect.signature(function).parameters
        assert parameters['model'].default == 'deepseek-v4-pro'
        assert parameters['reasoning_effort'].default == 'high'


def test_runner_routes_absolute_generated_roots(tmp_path, monkeypatch):
    from credit_agreement_extractor import runner
    calls = {}
    def record(name):
        def invoke(*args, **kwargs):
            calls[name] = kwargs
            return {}
        return invoke
    for name in ('convert_document', 'build_chunks', 'reflect_topics',
                 'build_topic_map', 'extract_credit_terms'):
        monkeypatch.setattr(runner, name, record(name))
    runner.run_pipeline('doc.pdf', generated_root=tmp_path/'generated',
                        trace_root=tmp_path/'traces')
    assert calls['convert_document']['output_root'] == tmp_path/'generated/converted'
    assert calls['build_chunks']['output_root'] == tmp_path/'generated/stage_b'
    assert calls['extract_credit_terms']['output_root'] == tmp_path/'generated/stage_d'
    assert calls['extract_credit_terms']['model'] == 'deepseek-v4-pro'
    assert calls['reflect_topics']['reasoning_effort'] == 'medium'
