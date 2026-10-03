"""B5: turn topic-map citations into source-backed, readable evidence.

No inference occurs here. Downstream extraction and future visual reviewers can
consume the same packet; original source wording remains the evidence boundary.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from .chunking import ChunkArtifact, _render_table
from .conversion import ConversionArtifact
from .retrieval import document_hash, select_topic_groups
from .topic_map import TopicMapArtifact
from .topic_taxonomy import VOCABULARY
from .tracing import atomic_json, current_trace, traced


@dataclass(frozen=True, slots=True)
class EvidenceArtifact:
    """A persisted, request-specific packet; not extracted legal facts."""
    source_sha256: str
    evidence_json_path: Path
    requested_topics: tuple[str, ...]


def package_topic_evidence(document: dict, selection: dict, *,
                           canonical_document: dict | None = None) -> dict:
    """Resolve selected IDs, preserving every group and evidence/context role.

    Revalidate the selection as a partial topic map first. This also makes the
    pure function safe to test/use independently of the persistence wrapper.
    """
    selected_map = {**selection, 'schema_version': 2,
        'topics': {t: selection.get('topics', {}).get(t, []) for t in VOCABULARY}}
    validated = select_topic_groups(document, selected_map,
                                    topics=selection.get('requested_topics'))
    if validated != selection:
        raise ValueError('Selection metadata differs from validated B4 result.')
    source = {i['item_id']: i for c in document['chunks'] for i in c['items']}

    def resolve(item_id: str) -> dict:
        item = source[item_id]
        # Original wording takes priority over Docling's normalized text.
        text = item.get('original_text') or item.get('text') or ''
        result = dict(item_id=item_id, text=text, pages=deepcopy(item.get('pages', [])),
            heading_path=deepcopy(item.get('heading_path', [])),
            container_path=deepcopy(item.get('container_path', [])))
        if item_id.startswith('#/tables/'):
            # A joined page cannot identify a particular table reliably. Use
            # its canonical grid, supplied via the verified Stage A artifact.
            if canonical_document is None:
                raise ValueError('Table evidence requires matching canonical Stage A JSON.')
            try:
                table = canonical_document['tables'][int(item_id.rsplit('/', 1)[1])]
            except (KeyError, IndexError, TypeError, ValueError) as error:
                raise ValueError('Table citation does not resolve in canonical JSON.') from error
            if table.get('self_ref') != item_id:
                raise ValueError('Canonical table reference mismatch.')
            text = _render_table(table, item_id=item_id)
            result['text'] = text
            result['table_data'] = deepcopy(table.get('data'))
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f'Selected evidence item has no readable source text: {item_id}')
        return result

    result = deepcopy(selection)
    result['packet_version'] = 'topic-evidence-v1'
    for topic, groups in result['topics'].items():
        for group in groups:
            group['evidence'] = [resolve(i) for i in group['evidence_item_ids']]
            group['context'] = [resolve(i) for i in group['context_item_ids']]
    return result


@traced('B4')
def _retrieve(document, topic_map, topics, **trace_options):
    """Keep B4 observable even when called through the composed public API."""
    current_trace().event('pipeline_layout', {'pipeline_layout': 'stage-b-v2'})
    current_trace().snapshot('B4-input-artifacts', {'chunks': document, 'topic_map': topic_map})
    selection = select_topic_groups(document, topic_map, topics=topics)
    current_trace().snapshot('B4-selection', selection)
    return selection


@traced('B5')
def _package(document, selection, canonical_document, **trace_options):
    current_trace().event('pipeline_layout', {'pipeline_layout': 'stage-b-v2'})
    result = package_topic_evidence(document, selection, canonical_document=canonical_document)
    current_trace().snapshot('B5-evidence-packet', result)
    return result


@traced('topic_evidence')
def retrieve_evidence(topic_map: TopicMapArtifact, chunks: ChunkArtifact, *,
                      topics: list[str], conversion: ConversionArtifact | None = None,
                      debug=False, run_id=None, trace_root='tmp/runs') -> EvidenceArtifact:
    """Public downstream entry point: run B4 then B5, save and return a packet.

    `topics` must already be approved taxonomy IDs. Canonical conversion is
    optional for text-only groups, required for tables. There is intentionally
    no evidence budget/truncation or question interpretation in this version.
    All source artifacts are read-only; outputs live beside the topic map.
    """
    document = json.loads(chunks.chunks_json_path.read_bytes())
    mapped_raw = topic_map.topic_map_json_path.read_bytes()
    mapped = json.loads(mapped_raw)
    if not (topic_map.source_sha256 == chunks.source_sha256 == document.get('source_sha256')):
        raise ValueError('Evidence source artifact identities do not match.')
    options = dict(debug=debug, run_id=run_id, trace_root=trace_root)
    # One shared run ID links the two stages even when the caller omits it.
    if options['run_id'] is None:
        from uuid import uuid4
        options['run_id'] = uuid4().hex
    selection = _retrieve(document, mapped, topics, **options)
    canonical, canonical_hash = None, None
    if conversion is not None:
        raw = conversion.docling_json_path.read_bytes()
        canonical_hash = hashlib.sha256(raw).hexdigest()
        if (conversion.source_sha256 != chunks.source_sha256
            or document.get('inputs', {}).get('docling_json_sha256') != canonical_hash):
            raise ValueError('Stage A canonical JSON identity/hash does not match B1.')
        canonical = json.loads(raw)
    result = _package(document, selection, canonical, **options)
    # Fingerprint actual inputs and requested topics. Distinct topic requests,
    # model maps and conversion modes never overwrite each other's packets.
    result['inputs'] = dict(topic_map_sha256=hashlib.sha256(mapped_raw).hexdigest(),
        chunks_document_sha256=document_hash(document), canonical_json_sha256=canonical_hash)
    request_id = document_hash(result)
    destination = topic_map.topic_map_json_path.parent / 'evidence' / request_id / 'document.evidence.json'
    atomic_json(destination, result)
    return EvidenceArtifact(chunks.source_sha256, destination, tuple(selection['requested_topics']))
