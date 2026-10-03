"""B4: strict taxonomy retrieval, with no ranking or model inference."""
from copy import deepcopy
import hashlib
import json

from .chunk_validation import _validate_document
from .topic_taxonomy import TAXONOMY_VERSION, VOCABULARY


def document_hash(document: dict) -> str:
    """Hash semantic JSON, so indentation does not change source identity."""
    return hashlib.sha256(json.dumps(
        document, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def select_topic_groups(document: dict, topic_map: dict, *, topics: list[str]) -> dict:
    """Return all exact mapped groups for approved topics, without mutation.

    The downstream caller chooses topics. This stage must never translate a
    broad request, invent a label, truncate evidence, or rank passages.
    """
    _validate_document(document)
    if (not isinstance(topics, (list, tuple)) or not topics
        or any(not isinstance(t, str) or t not in VOCABULARY for t in topics)):
        raise ValueError('Request a nonempty list of approved taxonomy IDs.')
    if (type(topic_map.get('schema_version')) is not int
        or topic_map['schema_version'] != 2 or topic_map.get('status') != 'completed'
        or topic_map.get('source_sha256') != document['source_sha256']
        or topic_map.get('taxonomy_version') != TAXONOMY_VERSION
        or topic_map.get('chunks_document_sha256') != document_hash(document)):
        raise ValueError('Map identity/schema/hash mismatch; rebuild old maps with B3.')
    if set(topic_map.get('topics', {})) != set(VOCABULARY):
        raise ValueError('Map must contain the complete approved taxonomy.')

    # Index source items once. All provenance below is computed from B1,
    # rather than trusting page/owner metadata copied into the topic map.
    items = {i['item_id']: i for c in document['chunks'] for i in c['items']}
    owners = {i: c['chunk_id'] for c in document['chunks'] for i in c['item_ids']}
    chunk_order = [c['chunk_id'] for c in document['chunks']]
    order = {i: n for n, i in enumerate(document['source_reading_order'])}
    requested = [t for t in VOCABULARY if t in topics]
    selected = {}
    for topic in requested:
        groups = topic_map['topics'][topic]
        if not isinstance(groups, list):
            raise ValueError('Mapped passage groups must be a list.')
        seen = set()
        for group in groups:
            if not isinstance(group, dict):
                raise ValueError('Malformed passage group.')
            evidence = group.get('evidence_item_ids')
            context = group.get('context_item_ids')
            if (not isinstance(evidence, list) or not evidence or not isinstance(context, list)
                or any(not isinstance(i, str) or i not in items for i in evidence + context)
                or len(set(evidence + context)) != len(evidence + context)):
                raise ValueError('Unresolved, empty, duplicate or overlapping passage citations.')
            if evidence != sorted(evidence, key=order.__getitem__) or context != sorted(context, key=order.__getitem__):
                raise ValueError('Passage citations must retain canonical reading order.')
            identity = [document['source_sha256'], TAXONOMY_VERSION, topic, tuple(evidence), tuple(context)]
            expected_id = 'passage-' + hashlib.sha256(json.dumps(identity).encode()).hexdigest()
            selected_owners = {owners[i] for i in evidence + context}
            expected = dict(group_id=expected_id, evidence_item_ids=evidence, context_item_ids=context,
                source_chunk_ids=[c for c in chunk_order if c in selected_owners],
                evidence_pages=sorted({p for i in evidence for p in items[i].get('pages', [])}),
                context_pages=sorted({p for i in context for p in items[i].get('pages', [])}))
            if group != expected or expected_id in seen:
                raise ValueError('Passage identity/provenance mismatch or duplicate group.')
            seen.add(expected_id)
        # B3's canonical ordering is part of the retrieval contract, not a
        # formatting preference. Valid individual groups can still be shuffled.
        expected_order = sorted(groups, key=lambda g: (
            tuple(order[i] for i in g['evidence_item_ids']),
            tuple(order[i] for i in g['context_item_ids'])))
        if groups != expected_order:
            raise ValueError('Mapped groups must retain canonical source order.')
        selected[topic] = deepcopy(groups)
    return dict(schema_version=1, status='completed', pipeline_layout='stage-b-v2',
        source_sha256=document['source_sha256'], taxonomy_version=TAXONOMY_VERSION,
        chunks_document_sha256=document_hash(document), requested_topics=requested,
        empty_topics=[t for t in requested if not selected[t]], topics=selected)
