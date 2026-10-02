"""Pure B2 passage selection contracts; source content is never rewritten.

The model judges relevance. This module only enforces citation scope, coherent
reference contracts and deterministic provenance. Validation is not an accuracy
score, and cannot prove that the model selected every relevant provision.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pydantic import BaseModel, ConfigDict, Field
from .chunk_validation import _validate_document
from .topic_taxonomy import VOCABULARY, PARENT_TOPICS, TAXONOMY_VERSION


class PassageGroup(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    evidence_item_ids: list[str] = Field(min_length=1)
    context_item_ids: list[str]


class PassageTopic(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    topic: str
    groups: list[PassageGroup] = Field(min_length=1)


class PassageClassification(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    chunk_id: str
    topics: list[PassageTopic]


class PassageResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    classifications: list[PassageClassification]


def packet_hash(packets: list[dict]) -> str:
    """Fingerprint complete supplied evidence, including text and local scope."""
    return hashlib.sha256(json.dumps(packets, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def build_passage_packets(document: dict, *,
                          boundary_context_groups: int = 1) -> list[dict]:
    """Package unchanged B1 leaves plus bounded atomic neighboring groups.

    B1 keeps explicit list ancestors on items and lists its atomic group IDs on
    the owning chunk. Use those identifiers rather than guessing lists from
    bullets or legal numbering. A table remains one canonical leaf.
    """
    _validate_document(document)
    if (isinstance(boundary_context_groups, bool)
        or not isinstance(boundary_context_groups, int) or boundary_context_groups < 0):
        raise ValueError('boundary_context_groups must be a nonnegative integer.')
    units, positions = [], {}
    for chunk in document['chunks']:
        first = len(units)
        for item in chunk['items']:
            groups = set(chunk.get('atomic_group_ids', []))
            ancestry = [g for g in item.get('container_path', []) if g in groups]
            key = ancestry[0] if ancestry else item['item_id']
            if units and units[-1]['key'] == key:
                units[-1]['items'].append(item)
            else:
                units.append({'key':key, 'items':[item]})
        positions[chunk['chunk_id']] = (first, len(units))
    packets = []
    for chunk in document['chunks']:
        start, end = positions[chunk['chunk_id']]
        count = boundary_context_groups
        neighbors = [i for unit in units[max(0,start-count):start]+units[end:end+count]
                     for i in unit['items']]
        # Heading citations use the canonical global order as well. They are
        # contextual scope, never a substitute for direct evidence in the core.
        headings = {h['item_id']:h for i in chunk['items']+neighbors for h in i.get('heading_path', [])}
        allowed = set(chunk['item_ids']) | {i['item_id'] for i in neighbors} | set(headings)
        def record(item):
            result = deepcopy(item)
            result['text'] = item.get('original_text') or item.get('text') or ''
            return result
        packet = {'chunk_id':chunk['chunk_id'], 'items':[record(i) for i in chunk['items']],
                  'neighbor_items':[record(i) for i in neighbors],
                  'heading_path':list(headings.values()),
                  'allowed_item_ids':[i for i in document['source_reading_order'] if i in allowed]}
        # Core joined content preserves table rendering from the existing B1
        # artifact. Neighboring tables need canonical rendering supplied by A.
        if any(not i['text'] for i in packet['items']): packet['content'] = chunk['content']
        if any(i['item_id'].startswith('#/tables/') and not i['text'] for i in packet['neighbor_items']):
            raise ValueError('Neighbor table requires canonical Stage A table content; refusing to omit it.')
        packets.append(packet)
    return packets


def validate_passage_classifications(data: dict, document: dict, packets: list[dict]) -> list[dict]:
    """Strict model-facing validation followed by ordered provenance enrichment.

    `packets` may be one batch. A source item in another target's packet is not
    automatically citable: every group is checked against its target's scope.
    """
    _validate_document(document)
    parsed = PassageResponse.model_validate(data)
    targets = {p['chunk_id']:p for p in packets}
    if len(targets) != len(packets): raise ValueError('Duplicate target packet.')
    order = {i:n for n,i in enumerate(document['source_reading_order'])}
    items = {i['item_id']:i for c in document['chunks'] for i in c['items']}
    owners = {i:c['chunk_id'] for c in document['chunks'] for i in c['item_ids']}
    chunk_order = [c['chunk_id'] for c in document['chunks']]
    rows = {}
    for row in parsed.classifications:
        if row.chunk_id not in targets or row.chunk_id in rows:
            raise ValueError('Unknown or duplicate target chunk.')
        packet = targets[row.chunk_id]
        allowed, core = set(packet['allowed_item_ids']), {i['item_id'] for i in packet['items']}
        if not allowed <= set(order): raise ValueError('Packet contains noncanonical references.')
        labels = {}
        for label in row.topics:
            if label.topic not in VOCABULARY or label.topic in labels:
                raise ValueError('Unknown or duplicate topic.')
            groups = []
            for group in label.groups:
                evidence, context = group.evidence_item_ids, group.context_item_ids
                if (len(set(evidence)) != len(evidence) or len(set(context)) != len(context)
                    or set(evidence) & set(context) or not set(evidence+context) <= allowed):
                    raise ValueError('Duplicate, overlapping or out-of-scope passage citations.')
                if not set(evidence) & core:
                    raise ValueError('Passage requires core direct evidence, not only neighbors/headings.')
                groups.append((tuple(sorted(evidence,key=order.__getitem__)),
                               tuple(sorted(context,key=order.__getitem__))))
            labels[label.topic] = groups
        for child, parent in PARENT_TOPICS.items():
            if child in labels: labels.setdefault(parent, []).extend(labels[child])
        output = []
        for topic in VOCABULARY:
            if topic not in labels: continue
            enriched = []
            for evidence, context in sorted(set(labels[topic]), key=lambda g: (
                tuple(order[i] for i in g[0]), tuple(order[i] for i in g[1]))):
                identity = [document['source_sha256'],TAXONOMY_VERSION,topic,evidence,context]
                group_id = 'passage-'+hashlib.sha256(json.dumps(identity).encode()).hexdigest()
                selected_owners = {owners[i] for i in evidence+context}
                enriched.append({'group_id':group_id,'evidence_item_ids':list(evidence),
                    'context_item_ids':list(context),
                    'source_chunk_ids':[c for c in chunk_order if c in selected_owners],
                    'evidence_pages':sorted({p for i in evidence for p in items[i].get('pages', [])}),
                    'context_pages':sorted({p for i in context for p in items[i].get('pages', [])})})
            output.append({'topic':topic,'groups':enriched})
        rows[row.chunk_id] = {'chunk_id':row.chunk_id,'topics':output}
    if set(rows) != set(targets): raise ValueError('Classification must cover every supplied target.')
    return [rows[p['chunk_id']] for p in packets]


def revalidate_passage_rows(rows: list[dict], document: dict, packets: list[dict]) -> list[dict]:
    """Never trust enriched checkpoint/map metadata; recompute and compare it.

    Model answers have a deliberately smaller schema than saved groups. Strip
    only the known derived fields, validate the original contract, then require
    exact equality to catch changed roles, provenance and unknown saved fields.
    """
    raw = [{'chunk_id':r['chunk_id'],'topics':[
        {'topic':t['topic'],'groups':[
            {k:g[k] for k in ('evidence_item_ids','context_item_ids')} for g in t['groups']]}
        for t in r['topics']]} for r in rows]
    verified = validate_passage_classifications({'classifications':raw},document,packets)
    if verified != rows: raise ValueError('Passage metadata or ordering differs from canonical provenance.')
    return verified
