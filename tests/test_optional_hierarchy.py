"""A10 ablation must preserve source content and remain usable through B4."""
import json
from dataclasses import replace

import pytest

from test_conversion import RecordingConverter, FailingConverter
from test_chunking import _canonical, _text, _table, _ref
from credit_agreement_extractor import conversion as conversion_module
from credit_agreement_extractor.conversion import convert_document
from credit_agreement_extractor.chunking import build_chunks, build_chunk_document, InvalidChunkInputError
from credit_agreement_extractor.hierarchy import build_hierarchy_sidecar
from credit_agreement_extractor.topic_reflection import reflect_topics
from credit_agreement_extractor.topic_map import build_topic_map
from credit_agreement_extractor.llm import LlmResponse
from credit_agreement_extractor.hierarchy import InvalidHierarchyInputError


def test_disabled_hierarchy_does_not_interpret_malformed_heading_levels():
    canonical = _canonical(texts=[_text(0, 'Heading', label='section_header', level='unknown')])
    result = build_chunk_document(canonical, source_sha256='a'*64,
                                  docling_json_sha256='b'*64)
    assert result['chunks'][0]['items'][0]['heading_path'] == []
    with pytest.raises(InvalidHierarchyInputError):
        build_hierarchy_sidecar(canonical, source_sha256='a'*64)


def test_annotation_preparation_explicitly_keeps_hierarchy(tmp_path, monkeypatch):
    # Run the background callback synchronously without reading real labels.
    from credit_agreement_extractor.annotation import AnnotationWorkspace
    from threading import Lock
    workspace = AnnotationWorkspace.__new__(AnnotationWorkspace)
    workspace.root, workspace.lock, workspace.jobs = tmp_path, Lock(), {}
    workspace.source = lambda document_id: tmp_path/'approved.pdf'
    workspace.catalog = lambda document_id: None
    class ImmediatePool:
        def submit(self, callback):
            callback()
    workspace.pool = ImmediatePool()
    calls = []
    monkeypatch.setattr(conversion_module, 'convert_document',
                        lambda *args, **kwargs: calls.append(kwargs))
    workspace.prepare('011')
    assert calls[0]['use_hierarchy'] is True
    assert workspace.jobs['011']['status'] == 'ready'


def test_malformed_manifest_source_is_not_a_cache_hit(tmp_path):
    source = source_file(tmp_path)
    artifact = convert_document(source, tmp_path/'converted', converter=RecordingConverter())
    manifest = json.loads(artifact.manifest_path.read_text())
    manifest['source'] = []
    artifact.manifest_path.write_text(json.dumps(manifest))
    refreshed = convert_document(source, tmp_path/'converted', converter=RecordingConverter())
    assert not refreshed.cached


def test_legacy_enabled_manifest_remains_reusable(tmp_path):
    source = source_file(tmp_path)
    artifact = convert_document(source, tmp_path/'converted', use_hierarchy=True, converter=RecordingConverter())
    manifest = json.loads(artifact.manifest_path.read_text())
    del manifest['hierarchy_sidecar']['enabled']
    artifact.manifest_path.write_text(json.dumps(manifest))
    assert convert_document(source, tmp_path/'converted', use_hierarchy=True,
                            converter=FailingConverter()).cached


def source_file(tmp_path):
    source = tmp_path/'agreement.pdf'
    source.write_bytes(b'%PDF-1.4\npublic test source\n%%EOF\n')
    return source


def test_a10_default_skips_builder_and_finalizes_three_artifacts(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('A10 must not run when disabled')
    monkeypatch.setattr(conversion_module, 'build_hierarchy_sidecar', forbidden)
    artifact = convert_document(source_file(tmp_path), tmp_path/'converted', use_hierarchy=False, converter=RecordingConverter())
    assert artifact.hierarchy_json_path is None
    assert not (artifact.output_directory/'document.hierarchy.json').exists()
    manifest = json.loads(artifact.manifest_path.read_text())
    assert manifest['status'] == 'completed'
    assert manifest['hierarchy_sidecar'] == {'enabled': False, 'status': 'disabled'}
    assert manifest['artifacts']['hierarchy_json'] is None
    assert all(p.is_file() for p in (artifact.docling_json_path, artifact.markdown_path, artifact.manifest_path))
    assert artifact.output_directory.name == 'a10-disabled'


def test_modes_preserve_each_others_files_and_reuse_separate_caches(tmp_path):
    source = source_file(tmp_path)
    enabled = convert_document(source, tmp_path/'converted', use_hierarchy=True, converter=RecordingConverter())
    before = {p: p.read_bytes() for p in enabled.output_directory.iterdir() if p.is_file()}
    disabled = convert_document(source, tmp_path/'converted', use_hierarchy=False, converter=RecordingConverter())
    assert enabled.output_directory != disabled.output_directory
    assert {p: p.read_bytes() for p in before} == before
    for mode in (True, False):
        cached = convert_document(source, tmp_path/'converted', use_hierarchy=mode, converter=FailingConverter())
        assert cached.cached
    assert json.loads(enabled.manifest_path.read_text())['hierarchy_sidecar']['enabled'] is True


@pytest.mark.parametrize('value', [None, 'false', 0, 1])
def test_toggle_requires_boolean(tmp_path, value):
    with pytest.raises(ValueError, match='use_hierarchy must be a boolean'):
        convert_document(source_file(tmp_path), tmp_path/'converted', use_hierarchy=value, converter=RecordingConverter())


def test_flat_fallback_preserves_body_order_lists_tables_and_pages():
    canonical = _canonical(
        texts=[_text(0, 'Heading', label='section_header', level=1),
               _text(1, 'List one', parent_id='#/groups/0'),
               _text(2, 'List two', parent_id='#/groups/0', page=2)],
        tables=[_table(0, [['Lender', 'Amount'], ['Kestrel', '$6.6m']], page=2)],
        groups=[{'self_ref':'#/groups/0', 'label':'list', 'parent':_ref('#/body'),
                 'children':[_ref('#/texts/1'), _ref('#/texts/2')]}],
        body_children=['#/tables/0', '#/texts/0', '#/groups/0'])
    result = build_chunk_document(canonical, None, source_sha256='a'*64,
                                  docling_json_sha256='b'*64, hierarchy_json_sha256=None)
    items = [i for c in result['chunks'] for i in c['items']]
    assert [i['item_id'] for i in items] == ['#/tables/0', '#/texts/0', '#/texts/1', '#/texts/2']
    assert all(i['heading_path'] == [] for i in items)
    assert items[0]['pages'] == [2]
    assert items[-1]['container_path'] == ['#/body', '#/groups/0']
    assert any({'#/texts/1', '#/texts/2'} <= set(c['item_ids']) for c in result['chunks'])
    assert any('Kestrel' in c['content'] for c in result['chunks'])
    assert result['inputs']['use_hierarchy'] is False


@pytest.mark.parametrize('broken', ['missing', 'cycle', 'duplicate', 'malformed_body'])
def test_flat_fallback_rejects_broken_canonical_structure(broken):
    canonical = _canonical(texts=[_text(0, 'Borrower')])
    if broken == 'missing': canonical['body']['children'] = [_ref('#/texts/99')]
    if broken == 'duplicate': canonical['body']['children'] *= 2
    if broken == 'malformed_body': canonical['body']['children'] = 'not a list'
    if broken == 'cycle':
        canonical['groups'] = [{'self_ref':'#/groups/0', 'label':'list', 'children':[_ref('#/groups/0')]}]
        canonical['body']['children'] = [_ref('#/groups/0')]
    with pytest.raises(InvalidChunkInputError):
        build_chunk_document(canonical, None, source_sha256='a'*64,
                             docling_json_sha256='b'*64, hierarchy_json_sha256=None)


class OfflineClient:
    """Only the transport is replaced; source and citation validation stay real."""
    def __init__(self): self.requests = []
    def complete(self, system, evidence, **kwargs):
        self.requests.append(evidence)
        rows = [{'chunk_id': c['chunk_id'], 'topics':[{'topic':'parties_and_roles',
                  'groups':[{'evidence_item_ids':['#/texts/1'], 'context_item_ids':[]}]}]}
                for c in evidence['chunks']]
        return LlmResponse(json.dumps({'classifications':rows}), kwargs['model'],
                           kwargs['api_style'], {}, 0, {'kind':'unknown'})


@pytest.mark.parametrize('use_hierarchy', [False, True])
def test_both_a10_modes_work_through_b3_with_debug(tmp_path, use_hierarchy):
    from credit_agreement_extractor.review import load_run_review, build_topic_review
    options = {'debug':True, 'run_id':'ablation', 'trace_root':tmp_path/'runs'}
    artifact = convert_document(source_file(tmp_path), tmp_path/'converted',
                                use_hierarchy=use_hierarchy, converter=RecordingConverter(), **options)
    chunks = build_chunks(artifact, tmp_path/'stage_b', **options)
    assert build_chunks(artifact, tmp_path/'stage_b', **options).cached
    source = json.loads(chunks.chunks_json_path.read_text())
    assert source['inputs']['use_hierarchy'] is use_hierarchy
    assert all(bool(i['heading_path']) is use_hierarchy for c in source['chunks'] for i in c['items'])
    assert (chunks.output_directory.name == 'a10-disabled') is (not use_hierarchy)
    client = OfflineClient()
    final = reflect_topics(chunks, client=client, **options)
    topic_map = build_topic_map(chunks, final, **options)
    assert json.loads(topic_map.topic_map_json_path.read_text())['topics']['parties_and_roles']
    review = load_run_review('ablation', trace_root=tmp_path/'runs')
    assert build_topic_review(review)['chunks'][0]['items'][1]['text'] == 'Example Borrower, LLC'


def test_b1_requires_explicit_disabled_manifest_and_rejects_missing_enabled_sidecar(tmp_path):
    artifact = convert_document(source_file(tmp_path), tmp_path/'converted',
                                use_hierarchy=True, converter=RecordingConverter())
    with pytest.raises(InvalidChunkInputError):
        build_chunks(replace(artifact, hierarchy_json_path=None), tmp_path/'stage_b')
    artifact.hierarchy_json_path.unlink()
    with pytest.raises(InvalidChunkInputError):
        build_chunks(artifact, tmp_path/'stage_b')


def test_b1_on_off_outputs_and_downstream_files_are_preserved(tmp_path):
    source = source_file(tmp_path)
    enabled = convert_document(source, tmp_path/'converted', use_hierarchy=True, converter=RecordingConverter())
    on = build_chunks(enabled, tmp_path/'stage_b')
    before = on.chunks_json_path.read_bytes()
    disabled = convert_document(source, tmp_path/'converted', use_hierarchy=False, converter=RecordingConverter())
    off = build_chunks(disabled, tmp_path/'stage_b')
    assert on.chunks_json_path != off.chunks_json_path
    assert on.chunks_json_path.read_bytes() == before
    assert on.chunking_profile != off.chunking_profile
    assert build_chunks(enabled, tmp_path/'stage_b').cached
    assert build_chunks(disabled, tmp_path/'stage_b').cached


def test_disabled_cache_does_not_accept_an_enabled_manifest(tmp_path):
    source = source_file(tmp_path)
    artifact = convert_document(source, tmp_path/'converted', use_hierarchy=False, converter=RecordingConverter())
    manifest = json.loads(artifact.manifest_path.read_text())
    manifest['hierarchy_sidecar'] = {'enabled':True, 'schema_version':1}
    artifact.manifest_path.write_text(json.dumps(manifest))
    assert not convert_document(source, tmp_path/'converted', use_hierarchy=False, converter=RecordingConverter()).cached


def test_disabled_b1_cache_invalidates_when_canonical_changes(tmp_path):
    artifact = convert_document(source_file(tmp_path), tmp_path/'converted', converter=RecordingConverter())
    chunks = build_chunks(artifact, tmp_path/'stage_b')
    canonical = json.loads(artifact.docling_json_path.read_text())
    canonical['texts'][1]['text'] = 'Different Borrower'
    artifact.docling_json_path.write_text(json.dumps(canonical))
    rebuilt = build_chunks(artifact, tmp_path/'stage_b')
    assert not rebuilt.cached
    assert 'Different Borrower' in rebuilt.chunks_json_path.read_text()
