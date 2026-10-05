"""Offline review behavior; fixtures never read or write real human decisions."""
import hashlib
import http.client
import json
from pathlib import Path
from threading import Thread
from http.server import ThreadingHTTPServer

import pytest

from credit_agreement_extractor.extraction_review import ReviewWorkspace, Conflict, handler_for


@pytest.fixture
def workspace(tmp_path):
    source = tmp_path / 'raw_documents/pdf/test.pdf'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'%PDF-fixture')
    golden = tmp_path / 'evaluations/golden_documents.json'
    golden.parent.mkdir()
    golden.write_text(json.dumps({'documents': [{'id': '011', 'path': 'raw_documents/pdf/test.pdf'}]}))
    draft = golden.parent / 'ground_truth/extraction_drafts/test/reference.draft.json'
    draft.parent.mkdir(parents=True)
    draft.write_text(json.dumps({'schema_version': 'extraction-reference-draft-v1', 'documents': [{
        'document_id': '011', 'source_path': 'raw_documents/pdf/test.pdf',
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'facts': [{'fact_id': '011-F001', 'field': 'borrower', 'proposed_value': 'Example Ltd',
                   'value_status': 'proposed_supported', 'evidence': [{'source_text': 'Example Ltd is borrower', 'pdf_pages': [1], 'item_id': '#/texts/1'}]}],
        'review_notes': [],
    }]}))
    return ReviewWorkspace(tmp_path, draft)


def request(w, **changes):
    return {'draft_sha256': w.draft_sha256, 'document_id': '011', 'fact_id': '011-F001',
            'revision': 0, 'decision': 'approved', 'notes': '', **changes}


@pytest.mark.parametrize('decision,value', [('approved', None), ('edited', {'name': 'Corrected'}), ('rejected', None), ('skipped', None)])
def test_saved_decisions_survive_reopen_without_changing_draft(workspace, decision, value):
    w = workspace; original = w.draft_path.read_bytes()
    body = request(w, decision=decision, notes='Review note')
    if decision == 'edited': body['value'] = value
    saved = w.save(body)
    reopened = ReviewWorkspace(w.root, w.draft_path)
    record = reopened.state()['decisions']['011-F001']
    assert record == saved and record['revision'] == 1
    assert record['approved_for_reference'] == (decision in ('approved', 'edited'))
    assert record['value'] == (value if decision == 'edited' else 'Example Ltd')
    assert w.draft_path.read_bytes() == original


def test_stale_tabs_cannot_overwrite_and_history_is_retained(workspace):
    w = workspace; second = ReviewWorkspace(w.root, w.draft_path)
    w.save(request(w))
    with pytest.raises(Conflict): second.save(request(second, decision='rejected'))
    w.save(request(w, revision=1, decision='edited', value='Corrected', notes='Fixed name'))
    assert [x['decision'] for x in w.history('011-F001')] == ['approved', 'edited']


def test_missing_fact_requires_evidence_and_persists(workspace):
    w = workspace
    body = request(w, fact_id='manual-test', decision='edited', field='fees', value=0.01,
                   evidence=[{'source_text': 'Fee is 1%', 'pdf_pages': [1], 'item_id': None}])
    record = w.save(body)
    assert record['is_added'] and record['field'] == 'fees'
    assert ReviewWorkspace(w.root, w.draft_path).state()['decisions']['manual-test'] == record
    with pytest.raises(ValueError): w.save({**body, 'fact_id': 'manual-empty', 'evidence': []})


def test_wrong_identity_invalid_revision_and_nonfinite_value_fail(workspace):
    w = workspace
    for changes in ({'draft_sha256': 'wrong'}, {'document_id': '../bad'}, {'fact_id': 'bad'},
                    {'revision': True}, {'decision': 'anything'}, {'decision': 'edited', 'value': float('nan')}):
        with pytest.raises(ValueError): w.save(request(w, **changes))
    assert not w.state()['decisions']


def test_changed_draft_fails_closed_in_running_workspace(workspace):
    w = workspace
    w.draft_path.write_text(w.draft_path.read_text() + ' ')
    with pytest.raises(Conflict): w.save(request(w))


def test_modified_source_fails_validation(workspace):
    workspace.sources['011'].write_bytes(b'changed')
    with pytest.raises(ValueError): ReviewWorkspace(workspace.root, workspace.draft_path)


def test_explicit_unknown_and_failed_save_preserve_prior_review(workspace):
    w = workspace
    w.save(request(w, decision='edited', value=None, notes='Cannot resolve this value'))
    assert w.state()['decisions']['011-F001']['value'] is None
    with pytest.raises(ValueError): w.save(request(w, revision=1, decision='edited', value=float('inf')))
    assert len(w.history('011-F001')) == 1
    assert w.history('011-F001')[0]['value_status'] == 'unresolved'


def test_source_change_during_session_cannot_be_approved(workspace):
    w = workspace
    w.sources['011'].write_bytes(b'different source')
    with pytest.raises(Conflict): w.save(request(w))
    assert not w.state()['decisions']


def test_core_pipeline_has_no_import_of_review_module():
    import ast
    root = Path(__file__).parents[1] / 'src/credit_agreement_extractor'
    for filename in ('conversion.py', 'chunking.py', 'topic_reflection.py', 'topic_map.py',
                     'evidence.py', 'orchestrator.py', 'extraction_specialist.py', 'runner.py'):
        tree = ast.parse((root / filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom): assert 'extraction_review' not in (node.module or '')
            if isinstance(node, ast.Import): assert all('extraction_review' not in name.name for name in node.names)


def test_http_write_requires_origin_and_token(workspace):
    w = workspace; server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(w))
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    port = server.server_port; origin = f'http://127.0.0.1:{port}'
    def call(method, route, body=None, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', port)
        c.request(method, route, body=json.dumps(body) if body else None, headers=headers or {})
        r = c.getresponse(); data = r.read(); c.close(); return r.status, data
    try:
        assert call('POST', '/api/review', request(w))[0] == 403
        assert call('POST', '/api/review', request(w), {'Origin': 'http://evil.example', 'X-Review-Token': w.token})[0] == 403
        headers = {'Origin': origin, 'X-Review-Token': w.token, 'Content-Type': 'application/json'}
        assert call('POST', '/api/review', request(w), headers)[0] == 200
        assert call('POST', '/api/review', request(w), headers)[0] == 409
        assert call('GET', '/source?document=../.env')[0] == 400
        assert call('GET', '/api/state')[0] == 200
    finally:
        server.shutdown(); server.server_close(); thread.join()
