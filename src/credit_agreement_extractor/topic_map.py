"""B3: deterministic topic index with historical schema consumption."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from .chunking import ChunkArtifact
from .chunk_validation import _validate_document
from .topic_reflection import TopicClassificationArtifact, validate_classifications
from .topic_taxonomy import TAXONOMY_VERSION, VOCABULARY
from .tracing import atomic_json, traced, current_trace
from .topic_passages import build_passage_packets, packet_hash, revalidate_passage_rows


@dataclass(frozen=True, slots=True)
class TopicMapArtifact:
    source_sha256: str
    topic_map_json_path: Path


def build_topic_map_document(document, classifications):
    """Validate evidence and index labels in B1 reading order without mutation."""
    _validate_document(document)
    version = classifications.get('schema_version')
    if (classifications.get('status') != 'completed' or type(version) is not int or version not in (1,2)
        or classifications.get('classification_status') != 'final'
        or classifications.get('source_sha256') != document['source_sha256']
        or classifications.get('taxonomy_version') != TAXONOMY_VERSION
        or classifications.get('taxonomy') != list(VOCABULARY)):
        raise ValueError('Topic map requires matching completed classifications.')
    if version == 2:
        profile = classifications.get('profile', {})
        packets = build_passage_packets(document,
                                        boundary_context_groups=profile.get('boundary_context_groups'))
        layout = classifications.get('pipeline_layout', profile.get('pipeline_layout'))
        if layout is None and 'proposed_topics' in classifications:
            # Historical packet hashes included saved proposals. No rules run.
            for packet in packets:
                packet['proposed_topics'] = list(classifications['proposed_topics'].get(packet['chunk_id'], []))
        elif layout != 'stage-b-v2':
            raise ValueError('Unknown classification pipeline layout.')
        if profile.get('schema_version') != 2 or profile.get('packets_sha256') != packet_hash(packets):
            raise ValueError('Topic map passage packet hash or policy mismatch.')
        rows = revalidate_passage_rows(classifications['classifications'],document,packets)
    else:
        # Legacy citations retain their original meaning. Do not infer v2 roles.
        rows = validate_classifications({'classifications':classifications['classifications']},document['chunks'])
    topics = {topic:[] for topic in VOCABULARY}
    reading_order = {item_id:index for index,item_id in enumerate(document['source_reading_order'])}
    for row in rows:
        for label in row['topics']:
            # IDs stay resolvable to the original canonical Docling document.
            if version == 1:
                topics[label['topic']].append({'chunk_id':row['chunk_id'],
                    'item_ids':sorted(label['item_ids'],key=reading_order.__getitem__)})
            else:
                for group in label['groups']:
                    # Exact identities only: overlapping passages are not merged.
                    if not any(g['group_id'] == group['group_id'] for g in topics[label['topic']]):
                        topics[label['topic']].append(group)
    if version == 2:
        for groups in topics.values():
            groups.sort(key=lambda g:(tuple(reading_order[i] for i in g['evidence_item_ids']),
                                      tuple(reading_order[i] for i in g['context_item_ids'])))
    result = {'schema_version':version,'status':'completed','source_sha256':document['source_sha256'],
            'taxonomy_version':TAXONOMY_VERSION,'topics':topics,
            'source_chunk_order':[c['chunk_id'] for c in document['chunks']],
            'unclassified_chunk_ids':[r['chunk_id'] for r in rows if not r['topics']]}
    if classifications.get('pipeline_layout', classifications.get('profile', {}).get('pipeline_layout')) == 'stage-b-v2':
        result['pipeline_layout'] = 'stage-b-v2'
    if version == 2:
        # Bind future retrieval to exact B1 content/metadata, independent of
        # whitespace in the persisted JSON. Old maps can be rebuilt offline.
        result['chunks_document_sha256'] = hashlib.sha256(
            json.dumps(document, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return result


@traced('B3')
def build_topic_map(chunks: ChunkArtifact, classifications: TopicClassificationArtifact, *,
                    debug=False, run_id=None, trace_root='tmp/runs') -> TopicMapArtifact:
    current_trace().event('pipeline_layout', {'pipeline_layout':'stage-b-v2'})
    raw, classified_raw = chunks.chunks_json_path.read_bytes(), classifications.classifications_json_path.read_bytes()
    doc, classified = json.loads(raw), json.loads(classified_raw)
    if (chunks.source_sha256 != classifications.source_sha256 or chunks.source_sha256 != doc.get('source_sha256')
        or classified.get('profile',{}).get('chunks_json_sha256') != hashlib.sha256(raw).hexdigest()):
        raise ValueError('Topic map input identity or B1 hash mismatch.')
    result = build_topic_map_document(doc,classified)
    trace = current_trace()
    trace.snapshot('B3-input-artifacts', {'chunks':doc,'classifications':classified})
    filename = 'document.topic-passage-map.json' if result['schema_version'] == 2 else 'document.topic-map.json'
    directory = (classifications.classifications_json_path.parent
                 if result.get('pipeline_layout') == 'stage-b-v2'
                 else chunks.chunks_json_path.parent)
    destination = directory / filename
    atomic_json(destination,result)
    trace.snapshot('B3-final',result)
    return TopicMapArtifact(chunks.source_sha256,destination)
