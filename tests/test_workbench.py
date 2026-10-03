import json
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from credit_agreement_extractor.workbench import Workbench, make_server


@pytest.fixture
def project(tmp_path):
    corpus = tmp_path / 'raw_documents/pdf'
    corpus.mkdir(parents=True)
    (corpus / '011_credit_agreement.pdf').write_bytes(b'%PDF-original')
    return tmp_path


def wait_job(w, run_id):
    for _ in range(200):
        data = w.run_data(run_id)
        if data['job']['status'] != 'running':
            return data
        time.sleep(.005)
    pytest.fail('worker did not finish')


def test_defaults_result_durability_and_source_immutability(project):
    calls = []
    def pipeline(path, **kwargs):
        calls.append((path, kwargs))
        return {'credit_terms': {'amount': 42}}
    w = Workbench(project, pipeline=pipeline)
    job = w.start_job({'document_id': '011_credit_agreement.pdf', 'debug': False})
    assert job['settings']['model'] == 'deepseek-v4-pro'
    assert job['settings']['classification_model'] == 'deepseek-v4-flash'
    data = wait_job(w, job['run_id'])
    assert data['job']['status'] == 'completed'
    assert data['result']['credit_terms']['amount'] == 42
    assert calls[0][0].is_absolute()
    assert calls[0][1]['reasoning_effort'] == 'high'
    assert (project / 'raw_documents/pdf/011_credit_agreement.pdf').read_bytes() == b'%PDF-original'
    w.close()
    assert Workbench(project, pipeline=pipeline).run_data(job['run_id'])['result'] == data['result']


def test_single_job_and_sanitized_failure(project):
    entered, release = threading.Event(), threading.Event()
    def pipeline(*args, **kwargs):
        entered.set()
        release.wait(2)
        raise RuntimeError('secret-do-not-return')
    w = Workbench(project, pipeline=pipeline)
    job = w.start_job({'document_id': '011_credit_agreement.pdf'})
    assert entered.wait(1)
    try:
        with pytest.raises(RuntimeError):
            w.start_job({'document_id': '011_credit_agreement.pdf'})
    finally:
        release.set()
    data = wait_job(w, job['run_id'])
    assert data['job']['error_type'] == 'RuntimeError'
    assert 'secret-do-not-return' not in json.dumps(data)


def test_registered_paths_only(project, tmp_path):
    outside = tmp_path / 'outside.pdf'
    outside.write_bytes(b'outside')
    (project / 'raw_documents/pdf/link.pdf').symlink_to(outside)
    w = Workbench(project, pipeline=lambda *a, **k: {})
    assert [d['document_id'] for d in w.documents()] == ['011_credit_agreement.pdf']
    for bad in ['../outside.pdf', 'link.pdf', '/etc/passwd', '011_credit_agreement.pdf/..']:
        with pytest.raises((ValueError, FileNotFoundError)):
            w.source_path(bad)
    with pytest.raises(ValueError):
        w.run_data('../outside')


def test_partial_events_concurrent_status_and_restart(project):
    folder = project / 'tmp/runs/history'
    folder.mkdir(parents=True)
    rows = [{'event': 'stage_started', 'stage': 'C', 'span_id': 'one'},
            {'event': 'stage_started', 'stage': 'C', 'span_id': 'two'},
            {'event': 'stage_finished', 'stage': 'C', 'span_id': 'one', 'status': 'completed'}]
    (folder / 'events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows)+'{"event":')
    (folder / 'job.json').write_text(json.dumps({'run_id':'history','status':'running'}))
    debug = folder / 'debug'
    debug.mkdir()
    (debug / 'D4-output-abc.json').write_text('{"answer":42}')
    (debug / 'arbitrary.json').write_text('{"secret":"no"}')
    w = Workbench(project, pipeline=lambda *a, **k: {})
    data = w.run_data('history')
    assert data['job']['status'] == 'interrupted'
    assert data['stages']['C']['status'] == 'interrupted'
    assert data['stages']['C']['active_spans'] == ['two']
    assert data['events'] == rows
    assert data['snapshots'] == [{'filename':'D4-output-abc.json','stage':'D4'}]
    assert data['result'] == {'answer':42}
    assert w.snapshot('history', 'D4-output-abc.json') == {'answer':42}
    with pytest.raises(ValueError):
        w.snapshot('history','arbitrary.json')


def test_corrupt_complete_event_is_not_silently_ignored(project):
    folder = project / 'tmp/runs/bad'
    folder.mkdir(parents=True)
    (folder / 'events.jsonl').write_text('broken\n')
    with pytest.raises(ValueError):
        Workbench(project).run_data('bad')


def test_history_only_resolves_registered_source_and_never_reads_logged_paths(project):
    for name, source in [('known',str(project/'raw_documents/pdf/011_credit_agreement.pdf')),
                         ('unknown','/etc/passwd')]:
        folder = project/'tmp/runs'/name/'debug'
        folder.mkdir(parents=True)
        (folder/'A-input-a.json').write_text(json.dumps({'args':[source]}))
    w = Workbench(project)
    history = {r['run_id']:r for r in w.runs()}
    assert history['known']['document_id'] == '011_credit_agreement.pdf'
    assert history['unknown']['document_id'] is None
    assert w.run_data('known')['job']['document_id'] == '011_credit_agreement.pdf'


def test_snapshot_symlinks_and_stage_allowlist(project):
    debug = project/'tmp/runs/safe/debug'
    debug.mkdir(parents=True)
    (debug/'A3.1-output-a.json').write_text('{"cached":true}')
    (debug/'A99-output-a.json').write_text('{"ignored":true}')
    (debug/'B5-output-a.json').symlink_to(debug/'A3.1-output-a.json')
    w = Workbench(project)
    with pytest.raises(ValueError):
        w.run_data('safe')
    with pytest.raises(ValueError):
        w.snapshot('safe','B5-output-a.json')


def test_evidence_manifest_snapshots_and_live_review(project,monkeypatch):
    from credit_agreement_extractor import review
    folder = project/'tmp/runs/live'
    debug = folder/'debug'
    debug.mkdir(parents=True)
    (folder/'events.jsonl').write_text('{"event":"stage_started","stage":"D2"}\n{"event":')
    (debug/'D2-evidence-a.json').write_text('{"original":"source"}')
    (debug/'D4-manifest-a.json').write_text('{"completed":true}')
    seen = []
    monkeypatch.setattr(review,'render_run_review',lambda data: seen.append(data) or '<html>live</html>',raising=False)
    w = Workbench(project)
    assert {s['filename'] for s in w.run_data('live')['snapshots']} == {'D2-evidence-a.json','D4-manifest-a.json'}
    assert w.review('live') == '<html>live</html>'
    assert seen[0]['events'] == [{'event':'stage_started','stage':'D2'}]
    assert next(s['data'] for s in seen[0]['snapshots'] if s['filename'].startswith('D2')) == {'original':'source'}


def test_independent_overrides_and_invalid_settings(project):
    w = Workbench(project,pipeline=lambda *a,**k:{})
    for options in [{'debug':'false'}, {'reasoning_effort':[]}, {'trace_root':'/tmp'},
                    {'model':'bad/model'}]:
        with pytest.raises(ValueError):
            w.start_job({'document_id':'011_credit_agreement.pdf',**options})
    job = w.start_job({'document_id':'011_credit_agreement.pdf','model':'gpt-5.6-luna',
                       'reasoning_effort':'xhigh','classification_reasoning_effort':'high'})
    assert job['settings']['model'] == 'gpt-5.6-luna'
    assert job['settings']['classification_model'] == 'deepseek-v4-flash'
    wait_job(w,job['run_id'])


def test_thread_start_failure_releases_single_worker(project,monkeypatch):
    w = Workbench(project,pipeline=lambda *a,**k:{})
    with monkeypatch.context() as patch:
        patch.setattr(threading.Thread,'start',lambda self: (_ for _ in ()).throw(RuntimeError('secret')))
        with pytest.raises(RuntimeError):
            w.start_job({'document_id':'011_credit_agreement.pdf'})
    assert w.runs()[0]['status'] == 'failed'
    wait_job(w,w.start_job({'document_id':'011_credit_agreement.pdf'})['run_id'])


def test_batch_projection_retains_scope_with_concurrent_attempts(project):
    folder = project/'tmp/runs/batches'
    folder.mkdir(parents=True)
    rows = [{'event':'batch_attempt','stage':'B2','batch_id':'a','attempt_id':'one','chunk_ids':['c1']},
            {'event':'batch_attempt','stage':'B2','batch_id':'b','attempt_id':'two','chunk_ids':['c2']},
            {'event':'batch_validated','stage':'B2','batch_id':'a','attempt_id':'one'},
            {'event':'batch_reused','stage':'B2','batch_id':'c'}]
    (folder/'events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    batch = Workbench(project).run_data('batches')['batches']
    assert (batch['active'],batch['completed'],batch['reused']) == (1,1,1)
    assert next(r for r in batch['records'] if r['batch_id']=='a')['chunk_ids'] == ['c1']


def test_historical_spans_and_d_validation_are_inspectable(project):
    folder = project/'tmp/runs/legacy'
    debug = folder/'debug'
    debug.mkdir(parents=True)
    (debug/'D3-validation-a.json').write_text('{"valid":true}')
    rows = [{'event':'stage_started','stage':'B6','span_id':'old'},
            {'event':'batch_failed','stage':'D2','batch_id':'specialist','attempt':1}]
    (folder/'events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    data = Workbench(project).run_data('legacy')
    assert data['snapshots'] == [{'filename':'D3-validation-a.json','stage':'D3'}]
    assert data['batches']['failed'] == 0
    assert data['stages']['B6']['active_spans'] == ['old']
    assert data['stages']['B6']['status'] == 'unrecorded'


def test_process_owner_excludes_second_controller_without_interrupting_job(project):
    entered, release = threading.Event(), threading.Event()
    def pipeline(*args,**kwargs):
        entered.set()
        release.wait(2)
        return {}
    w = Workbench(project,pipeline=pipeline)
    job = w.start_job({'document_id':'011_credit_agreement.pdf'})
    assert entered.wait(1)
    try:
        with pytest.raises(RuntimeError):
            Workbench(project,pipeline=pipeline)
        with pytest.raises(RuntimeError):
            w.close()
        assert w.run_data(job['run_id'])['job']['status'] == 'running'
    finally:
        release.set()
    wait_job(w,job['run_id'])
    w.close()
    replacement = Workbench(project,pipeline=pipeline)
    assert replacement.run_data(job['run_id'])['job']['status'] == 'completed'
    replacement.close()


def test_unroutable_models_and_messages_efforts_rejected_before_worker(project):
    w = Workbench(project,pipeline=lambda *a,**k: pytest.fail('must not invoke pipeline'))
    for options in [{'model':'not-a-real-model'}, {'classification_model':'not-a-real-model'},
                    {'model':'qwen3.8-flash','reasoning_effort':'medium'},
                    {'classification_model':'qwen3.8-flash','classification_reasoning_effort':'xhigh'}]:
        with pytest.raises(ValueError):
            w.start_job({'document_id':'011_credit_agreement.pdf',**options})
    assert w.runs() == []
    w.close()


def test_saved_extraction_source_resolves_only_registered_pdf_hash(project):
    import hashlib
    digest = hashlib.sha256(b'%PDF-original').hexdigest()
    for run_id,payload in [('input',{'args':[{'source_sha256':digest}]}),
                           ('output',{'document_id':digest}),('bad',{'document_id':'0'*64})]:
        debug = project/'tmp/runs'/run_id/'debug'
        debug.mkdir(parents=True)
        name = 'D1-input-a.json' if run_id=='input' else 'D4-output-a.json'
        (debug/name).write_text(json.dumps(payload))
    w = Workbench(project)
    assert w.run_data('input')['job']['document_id'] == '011_credit_agreement.pdf'
    assert w.run_data('output')['job']['document_id'] == '011_credit_agreement.pdf'
    assert w.run_data('bad')['job']['document_id'] is None
    assert w.run_data('input')['job']['document_id'] == '011_credit_agreement.pdf'
    w.close()


def test_http_requires_same_origin_token_and_host(project):
    w = Workbench(project, pipeline=lambda *a, **k: {'ok':True})
    server = make_server(w)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        config = json.load(urlopen(base+'/api/config'))
        from credit_agreement_extractor.llm import MODEL_ROUTES
        assert config['models'] == MODEL_ROUTES
        assert config['routes']['runs'] == '/api/runs'
        body = json.dumps({'document_id':'011_credit_agreement.pdf'}).encode()
        for headers in [{}, {'Origin':'https://evil.example','X-Workbench-Token':config['token']},
                        {'Origin':base,'X-Workbench-Token':config['token'],'Host':'evil.example'}]:
            with pytest.raises(HTTPError) as error:
                urlopen(Request(base+'/api/runs',data=body,headers=headers))
            assert error.value.code == 403
        job = json.load(urlopen(Request(base+'/api/runs',data=body,
            headers={'Origin':base,'X-Workbench-Token':config['token']})))
        assert wait_job(w,job['run_id'])['job']['status'] == 'completed'
        assert urlopen(base+'/api/documents/011_credit_agreement.pdf/pdf').read() == b'%PDF-original'
        with pytest.raises(HTTPError):
            urlopen(base+'/api/runs/history/snapshots/../job.json')
    finally:
        server.shutdown()
        server.server_close()
