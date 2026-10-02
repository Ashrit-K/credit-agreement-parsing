"""Human labels persist separately; neither raw source nor LLM evidence changes."""
import json
from pathlib import Path

import pytest

from credit_agreement_extractor.annotation import (
    AnnotationStore, RevisionConflict, build_annotation_document,
)


def review_document():
    canonical = {'texts': [
        {'self_ref': '#/texts/0', 'label': 'text', 'orig': 'Original lender names.',
         'text': 'Normalized lender names.', 'children': []},
        {'self_ref': '#/texts/1', 'label': 'text', 'text': 'Interest is payable.', 'children': []},
    ], 'tables': [{'self_ref': '#/tables/0', 'label': 'table', 'data': {
        'grid': [[{'text': 'Lender'}, {'text': 'Commitment'}],
                 [{'text': 'Bank A'}, {'text': '$10m'}]]}}]}
    hierarchy = {'source_sha256': 'a'*64, 'reading_order': ['#/texts/0', '#/tables/0', '#/texts/1'],
                 'items': {ref: {'pages': [page], 'heading_path': [], 'container_path': ['#/body']}
                           for ref, page in [('#/texts/0', 1), ('#/tables/0', 1), ('#/texts/1', 2)]}}
    return build_annotation_document(canonical, hierarchy, source_sha256='a'*64,
                                     name='agreement.pdf', document_id='011')


def test_passages_preserve_order_original_wording_tables_and_pages():
    doc = review_document()
    assert [p['item_id'] for p in doc['passages']] == ['#/texts/0', '#/tables/0', '#/texts/1']
    assert doc['passages'][0]['text'] == 'Original lender names.'
    assert doc['passages'][1]['table'] == [['Lender', 'Commitment'], ['Bank A', '$10m']]
    assert doc['passages'][2]['pages'] == [2]
    assert 'proposed_topics' not in doc and 'classifications' not in doc


def test_save_reload_multilabel_and_reviewed_empty_are_distinct(tmp_path):
    doc = review_document()
    store = AnnotationStore(tmp_path/'ground_truth')
    saved = store.save(doc, '#/texts/0', ['parties_and_roles', 'facility_and_commitment_terms'], revision=0)
    assert saved['revision'] == 1 and saved['reviewed'] is True
    store.save(doc, '#/texts/1', [], revision=0)
    loaded = AnnotationStore(tmp_path/'ground_truth').load(doc)
    assert loaded['annotations']['#/texts/1']['topics'] == []
    assert '#/tables/0' not in loaded['annotations']


def test_stale_save_does_not_overwrite_newer_review(tmp_path):
    doc = review_document()
    store = AnnotationStore(tmp_path)
    store.save(doc, '#/texts/0', ['parties_and_roles'], revision=0)
    with pytest.raises(RevisionConflict):
        store.save(doc, '#/texts/0', ['covenants'], revision=0)
    assert store.load(doc)['annotations']['#/texts/0']['topics'] == ['parties_and_roles']


@pytest.mark.parametrize('item,topics', [('#/texts/999', []), ('#/texts/0', ['invented']),
                                        ('#/texts/0', ['covenants', 'covenants'])])
def test_invalid_annotations_rejected(tmp_path, item, topics):
    with pytest.raises(ValueError):
        AnnotationStore(tmp_path).save(review_document(), item, topics, revision=0)


def test_source_catalog_change_keeps_old_labels_separate(tmp_path):
    doc = review_document()
    store = AnnotationStore(tmp_path)
    store.save(doc, '#/texts/0', ['parties_and_roles'], revision=0)
    changed = dict(doc, catalog_sha256='b'*64)
    assert store.load(changed)['annotations'] == {}
    assert store.load(doc)['annotations']['#/texts/0']['reviewed']


def test_human_topics_do_not_enter_b3_requests(tmp_path):
    # Exercise actual B3 transport boundary before/after writing contradictory
    # human labels. The fake provider records exactly what a model would see.
    from test_topic_reflection import artifacts, FakeClient
    from credit_agreement_extractor.topic_reflection import reflect_topics
    chunks = artifacts(tmp_path)
    client = FakeClient()
    reflect_topics(chunks, client=client, force=True, trace_root=tmp_path/'runs')
    first = json.dumps(client.calls[0][0], sort_keys=True)
    AnnotationStore(tmp_path/'evaluations'/'ground_truth').save(
        review_document(), '#/texts/0', ['covenants'], revision=0)
    reflect_topics(chunks, client=client, force=True, trace_root=tmp_path/'runs')
    assert json.dumps(client.calls[1][0], sort_keys=True) == first
    assert 'annotations' not in client.calls[1][0]


def test_human_label_file_is_not_a_valid_pipeline_input(tmp_path):
    from credit_agreement_extractor.chunking import ChunkArtifact
    from credit_agreement_extractor.topic_reflection import reflect_topics
    doc = review_document()
    store = AnnotationStore(tmp_path/'evaluations'/'ground_truth')
    store.save(doc, '#/texts/0', ['parties_and_roles'], revision=0)
    label_file = next(store.root.glob('*.json'))
    handle = ChunkArtifact('a'*64, label_file.parent, label_file, 1, 'test', False)
    with pytest.raises(ValueError):
        reflect_topics(handle, trace_root=tmp_path/'runs')


def test_legacy_reviews_keep_all_fields_and_leave_definitions_unknown(tmp_path):
    from credit_agreement_extractor.topic_taxonomy import VOCABULARY
    doc = review_document()
    store = AnnotationStore(tmp_path)
    path = store._path(doc)
    legacy = dict(store.load(doc), taxonomy_version='credit-topics-v1')
    old = {'reviewed': True, 'topics': ['parties_and_roles'], 'notes': 'My note',
           'revision': 7, 'updated_at': '2026-10-01T00:00:00Z'}
    legacy['annotations'] = {'#/texts/0': old, '#/texts/1': dict(old, topics=[])}
    path.write_text(json.dumps(legacy))
    original = path.read_bytes()
    loaded = store.load(doc)
    for item, record in legacy['annotations'].items():
        assert all(loaded['annotations'][item][k] == v for k, v in record.items())
        assert set(loaded['annotations'][item]['reviewed_topics']) == set(VOCABULARY) - {'contract_definitions'}
    assert path.read_bytes() == original  # Loading is not a disk migration.
    saved = store.save(doc, '#/texts/0', ['parties_and_roles', 'contract_definitions'], revision=7, notes='My note')
    assert set(saved['reviewed_topics']) == set(VOCABULARY)
    assert saved['revision'] == 8
    assert store.load(doc)['annotations']['#/texts/1'] == loaded['annotations']['#/texts/1']


def test_contract_definitions_has_shared_meaning():
    from credit_agreement_extractor.topic_taxonomy import VOCABULARY, TOPIC_DEFINITIONS
    assert 'contract_definitions' in VOCABULARY
    assert 'Merely using' in TOPIC_DEFINITIONS['contract_definitions']


def test_ui_does_not_reopen_completed_reviews_after_topic_addition():
    from credit_agreement_extractor import annotation
    html = Path(annotation.__file__).with_name('annotation.html').read_text()
    assert 'function fullyReviewed(a){return Boolean(a?.reviewed)}' in html
    assert 'need new-topic check' not in html
    assert 'New-topic check needed' not in html
    assert 'Previous labels saved · check' not in html


@pytest.mark.parametrize('version,expected', [(None, 409), ('credit-topics-v1', 409), ('credit-topics-v2', 200)])
def test_http_save_requires_current_taxonomy_before_claiming_coverage(tmp_path, version, expected):
    from io import BytesIO
    from types import SimpleNamespace
    from credit_agreement_extractor.annotation import handler_for
    doc = review_document()
    store = AnnotationStore(tmp_path)
    workspace = SimpleNamespace(store=store, catalog=lambda _: doc)
    handler = handler_for(workspace).__new__(handler_for(workspace))
    body = json.dumps({'taxonomy_version': version, 'document_id': '011',
                       'catalog_sha256': doc['catalog_sha256'], 'item_id': '#/texts/0',
                       'topics': ['contract_definitions'], 'revision': 0}).encode()
    handler.headers = {'Content-Length': str(len(body))}
    handler.rfile = BytesIO(body)
    handler.path = '/api/annotation'
    responses = []
    handler.send = lambda status, data: responses.append((status, data))
    handler.do_POST()
    assert responses[0][0] == expected
    assert bool(store.load(doc)['annotations']) == (expected == 200)
