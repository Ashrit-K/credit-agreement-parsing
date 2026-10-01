"""B4: deterministic topic index, not a summary or legal extraction layer."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from .chunking import ChunkArtifact
from .topic_signals import _validate_document
from .topic_reflection import TopicClassificationArtifact, validate_classifications
from .topic_taxonomy import TAXONOMY_VERSION, VOCABULARY
from .tracing import atomic_json, traced, current_trace


@dataclass(frozen=True, slots=True)
class TopicMapArtifact:
    source_sha256: str
    topic_map_json_path: Path


def build_topic_map_document(document, classifications):
    """Validate evidence and index labels in B1 reading order without mutation."""
    _validate_document(document)
    if (classifications.get('status') != 'completed' or classifications.get('schema_version') != 1
        or classifications.get('classification_status') != 'final'
        or classifications.get('source_sha256') != document['source_sha256']
        or classifications.get('taxonomy_version') != TAXONOMY_VERSION
        or classifications.get('taxonomy') != list(VOCABULARY)):
        raise ValueError('B4 requires matching completed B3 classifications.')
    rows = validate_classifications({'classifications':classifications['classifications']},document['chunks'])
    topics = {topic:[] for topic in VOCABULARY}
    reading_order = {item_id:index for index,item_id in enumerate(document['source_reading_order'])}
    for row in rows:
        for label in row['topics']:
            # IDs stay resolvable to the original canonical Docling document.
            topics[label['topic']].append({'chunk_id':row['chunk_id'],
                                          'item_ids':sorted(label['item_ids'],key=reading_order.__getitem__)})
    return {'schema_version':1,'status':'completed','source_sha256':document['source_sha256'],
            'taxonomy_version':TAXONOMY_VERSION,'topics':topics,
            'source_chunk_order':[c['chunk_id'] for c in document['chunks']],
            'unclassified_chunk_ids':[r['chunk_id'] for r in rows if not r['topics']]}


@traced('B4')
def build_topic_map(chunks: ChunkArtifact, classifications: TopicClassificationArtifact, *,
                    debug=False, run_id=None, trace_root='tmp/runs') -> TopicMapArtifact:
    raw, classified_raw = chunks.chunks_json_path.read_bytes(), classifications.classifications_json_path.read_bytes()
    doc, classified = json.loads(raw), json.loads(classified_raw)
    if (chunks.source_sha256 != classifications.source_sha256 or chunks.source_sha256 != doc.get('source_sha256')
        or classified.get('profile',{}).get('chunks_json_sha256') != hashlib.sha256(raw).hexdigest()):
        raise ValueError('B4 input identity or B1 hash mismatch.')
    result = build_topic_map_document(doc,classified)
    trace = current_trace()
    trace.snapshot('B4-input-artifacts', {'chunks':doc,'classifications':classified})
    destination = chunks.chunks_json_path.parent / 'document.topic-map.json'
    atomic_json(destination,result)
    trace.snapshot('B4-final',result)
    return TopicMapArtifact(chunks.source_sha256,destination)
