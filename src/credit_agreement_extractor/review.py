"""Export saved debug logs to a self-contained, read-only browser inspector.

This module does not call the pipeline or an LLM. The HTML is a snapshot of an
existing run; exporting again refreshes it from disk. No API key/configuration
files or arbitrary artifact paths are read. The saved debug copies are enough.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from .tracing import safe_data


def review_layout(data: dict) -> str:
    """Only explicit saved metadata selects the current numbering."""
    def marked(value):
        if isinstance(value, dict):
            return (value.get('pipeline_layout') == 'stage-b-v2'
                    or value.get('profile', {}).get('pipeline_layout') == 'stage-b-v2')
        return False
    if data.get('pipeline_layout') == 'stage-b-v2' or marked(data.get('job')):
        return 'stage-b-v2'
    if any(event.get('stage') in ('B2', 'B3')
           and event.get('event') == 'pipeline_layout' and marked(event)
           for event in data.get('events', [])):
        return 'stage-b-v2'
    for snapshot in data.get('snapshots', []):
        if snapshot['filename'].startswith(('B2-input-artifacts-', 'B2-final-',
                                            'B2-output-', 'B3-final-', 'B3-output-')):
            value = snapshot['data']
            if marked(value) or any(marked(value.get(key)) for key in (
                    'topic_passages_json_path', 'topic_classifications_json_path',
                    'topic_passage_map_json_path', 'topic_map_json_path')):
                return 'stage-b-v2'
    return 'historical'


def load_run_review(run_id: str, *, trace_root: str | Path = 'tmp/runs') -> dict:
    """Read only known pipeline snapshots inside one validated run directory."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', run_id):
        raise ValueError('Run ID must be an identifier, not a path.')
    directory = Path(trace_root) / run_id
    if directory.is_symlink():
        raise ValueError('Run directory must not be a symbolic link.')
    events_path = directory / 'events.jsonl'
    if events_path.is_symlink():
        raise ValueError('Event log must not be a symbolic link.')
    events = [json.loads(line) for line in events_path.read_text().splitlines() if line]
    snapshots = []
    debug = directory / 'debug'
    if debug.is_symlink():
        raise ValueError('Debug directory must not be a symbolic link.')
    # Avoid interpreting user-supplied paths in snapshot payloads as files to
    # read. Only the already-captured JSON files are loaded, in capture order.
    for path in sorted(debug.glob('*.json'), key=lambda p: (p.stat().st_mtime_ns, p.name)):
        if not re.match(r'^(?:A(?:[1-9]|10|11|3\.1)?|B[1-6]|C|D[1-4])-(?:input|output|request|response|final|validation|evidence|manifest)', path.name):
            continue
        if path.is_symlink():
            raise ValueError('Debug snapshots must not be symbolic links.')
        snapshots.append({'filename': path.name, 'data': json.loads(path.read_text())})
    return safe_data({'run_id':run_id, 'events':events, 'snapshots':snapshots})


def export_run_review(run_id: str, destination: str | Path, *,
                      trace_root: str | Path = 'tmp/runs') -> Path:
    """Embed actual captured data, escaping HTML script delimiters safely."""
    data = load_run_review(run_id, trace_root=trace_root)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_run_review(data), encoding='utf-8')
    return target


def render_run_review(data: dict) -> str:
    """Render a trace-backed projection, also accepting an unfinished live run.

    The controller owns safe file reading; this function does not follow paths
    from logs and never changes the original saved snapshot objects.
    """
    data = {**data, 'snapshots': list(data.get('snapshots', []))}
    data['pipeline_layout'] = review_layout(data)
    data['review'] = build_topic_review(data)
    data['stages'] = build_stage_review(data)
    data['model_exchanges'] = build_model_exchanges(data)
    # The human view already contains resolved source paragraphs. Do not embed
    # repeated full document snapshots (A, B1 and their downstream inputs) a
    # second time. Keep only model exchanges and the source manifest alongside
    # the view model so the browser stays responsive on longer agreements.
    compact = []
    for snapshot in data['snapshots']:
        name = snapshot['filename']
        classification = 'B2' if data['pipeline_layout'] == 'stage-b-v2' else 'B3'
        if name.startswith(tuple(classification + suffix for suffix in
                                ('-request-', '-response-', '-validation-error-')) + ('C-request-', 'C-response-', 'D2-request-', 'D2-response-', 'D3-validation-')):
            compact.append(snapshot)
        elif name.startswith('A-output-artifacts-'):
            compact.append({'filename':name, 'data':{
                'manifest_path':snapshot['data'].get('manifest_path', {})}})
    data['snapshots'] = compact
    encoded = json.dumps(data, ensure_ascii=True)
    # JSON lives in an inert script element. HTML still recognizes </script>
    # there, so escape '<' as well as '&' and '>' before embedding source text.
    encoded = encoded.replace('&', r'\u0026').replace('<', r'\u003c').replace('>', r'\u003e')
    template = Path(__file__).with_name('review.html').read_text()
    return template.replace('__RUN_DATA__', encoded)


def build_model_exchanges(data: dict) -> list[dict]:
    """Pair attempts by identity, not by neighboring log position.

    Concurrent responses can arrive in any order. New traces carry a unique
    attempt ID; historical traces use batch/attempt and stop at the next
    request with that same key, preserving restarted-run boundaries.
    Filename references avoid duplicating large model payloads in the export.
    """
    snapshots = data.get('snapshots', [])
    classification_stage = 'B2' if review_layout(data) == 'stage-b-v2' else 'B3'
    exchanges = []
    for index, request in enumerate(snapshots):
        stage = request['filename'].split('-request-', 1)[0]
        if stage not in (classification_stage, 'D2') or '-request-' not in request['filename']:
            continue
        metadata = request['data']
        identity = {**metadata.get('_trace', {}), **metadata}
        attempt_id = identity.get('attempt_id')

        def matches(snapshot):
            # Ordinary stage outputs can be lists, not attempt envelopes.
            # Only identity-bearing objects can match a model exchange.
            payload = snapshot['data']
            if not isinstance(payload, dict):
                return False
            other = {**payload.get('_trace', {}), **payload}
            if attempt_id:
                return other.get('attempt_id') == attempt_id
            return (other.get('batch_id'), other.get('attempt')) == (
                identity.get('batch_id'), identity.get('attempt'))

        response = error = None
        for snapshot in snapshots[index + 1:]:
            if not matches(snapshot):
                continue
            name = snapshot['filename']
            if not attempt_id and name.startswith(stage + '-request-'):
                break
            if name.startswith(stage + '-response-') and response is None:
                response = name
            if (name.startswith(stage + '-validation-error-') or
                (stage == 'D2' and name.startswith('D3-validation-'))) and error is None:
                error = name
        exchanges.append({'request': request['filename'],
                          'response': response, 'error': error})
    return exchanges


def build_stage_review(data: dict) -> dict:
    """Expose actual boundary inputs/outputs once per implemented stage.

    Argument snapshots and captured file contents are distinct: an API receives
    artifact objects, while the file contents are what its transformation uses.
    Preserve both, and label substeps without events as uninstrumented in the UI.
    """
    result = {}
    current = review_layout(data) == 'stage-b-v2'
    for stage in ('A', 'A1', 'A2', 'A3', 'A3.1', 'A4', 'A5', 'A6', 'A7',
                  'A8', 'A9', 'A10', 'A11', 'B1', 'B2', 'B3', 'B4', 'B5',
                  'C', 'D1', 'D2', 'D3', 'D4'):
        def last(prefix):
            found = [s['data'] for s in data['snapshots']
                     if s['filename'].startswith(prefix + '-')
                     and not (prefix.endswith(('-input', '-output'))
                              and s['filename'].startswith(prefix + '-artifacts-'))]
            value = found[-1] if found else None
            if value is not None and prefix.endswith('-artifacts'):
                return {key: item for key, item in value.items() if key != '_trace'}
            return value
        inputs = {}
        # Some calls capture multiple argument artifacts in separate snapshots.
        # Merging fields retains their actual input files without duplicating
        # the repeated captures created by resuming the same run.
        for snapshot in data['snapshots']:
            if snapshot['filename'].startswith(stage + '-input-artifacts-'):
                inputs.update({key: value for key, value in snapshot['data'].items()
                               if key != '_trace' and not (current and stage == 'B2'
                                                          and key in ('signals', 'topic_signals_json_path'))})
        result[stage] = {'input':last(stage + '-input'), 'input_artifacts':inputs,
                         'output':last(stage + '-output-artifacts'),
                         'return_value':last(stage + '-output'),
                         'events':[event for event in data.get('events', []) if event.get('stage') == stage]}
        if current and stage == 'B2' and result[stage]['output']:
            result[stage]['output'] = {key: value for key, value in result[stage]['output'].items()
                                       if key != 'topic_signals_json_path'}
        if stage == 'C':
            boundaries = [snapshot for snapshot in data['snapshots']
                          if snapshot['filename'].startswith(('C-input-', 'C-output-'))
                          and not snapshot['filename'].startswith(('C-input-artifacts-', 'C-output-artifacts-'))]
            span_id = (boundaries[-1]['data'].get('_trace') or {}).get('span_id') if boundaries else None
            if span_id:
                # The latest boundary may finish before an earlier request, or
                # have no response yet. Never pair independent "latest" values.
                for field, prefix in (('input', 'C-input-'), ('return_value', 'C-output-')):
                    matching = [snapshot['data'] for snapshot in boundaries
                                if snapshot['filename'].startswith(prefix)
                                and (snapshot['data'].get('_trace') or {}).get('span_id') == span_id]
                    result[stage][field] = matching[-1] if matching else None
    return result


def build_topic_review(data: dict) -> dict | None:
    """Join captured stage outputs into a human view without changing them.

    IDs are lookup keys, not the main display. Source wording, heading context,
    table cells and page numbers remain attached to each displayed paragraph.
    The result is a disposable view model, never a new canonical artifact.
    """
    def captured(prefix):
        matches = [s['data'] for s in data['snapshots'] if s['filename'].startswith(prefix + '-')]
        return matches[-1] if matches else None

    chunks = (captured('B1-output-artifacts') or {}).get('chunks_json_path')
    signals = (captured('B2-output-artifacts') or {}).get('topic_signals_json_path')
    layout = review_layout(data)
    classification_stage, map_stage = ('B2', 'B3') if layout == 'stage-b-v2' else ('B3', 'B4')
    final = captured(classification_stage + '-final')
    topic_map = captured(map_stage + '-final')
    use_b2 = layout != 'stage-b-v2' and (final or {}).get('profile', {}).get('use_b2', True)
    if not all((chunks, final, topic_map)) or (use_b2 and not signals):
        return None
    canonical = (captured('A-output-artifacts') or {}).get('docling_json_path', {})
    canonical_items = {item['self_ref']:item for section in ('texts', 'tables')
                       for item in canonical.get(section, []) if 'self_ref' in item}
    # A stale B2 snapshot in the run must not appear as input to a bypassed B3.
    guesses = {row['chunk_id']:row for row in signals['classifications']} if use_b2 else {}
    labels = {row['chunk_id']:row for row in final['classifications']}
    rows = []
    for chunk in chunks['chunks']:
        paragraphs, headings = [], {}
        for item in chunk['items']:
            source = canonical_items.get(item['item_id'], {})
            # Tables have no item.text in some B1 outputs. Resolve their actual
            # canonical cells rather than silently showing an empty paragraph.
            text = item.get('original_text') or item.get('text') or source.get('orig') or source.get('text') or ''
            table_rows = {}
            for cell in source.get('data', {}).get('table_cells', []):
                table_rows.setdefault(cell.get('start_row_offset', 0), []).append(cell.get('text', ''))
            table = [table_rows[k] for k in sorted(table_rows)]
            paragraphs.append({'item_id':item['item_id'], 'text':text,
                               'pages':item.get('pages', []), 'table':table,
                               'item_type':item.get('item_type'), 'heading_path':item.get('heading_path', [])})
            for heading in item.get('heading_path', []):
                headings[heading['item_id']] = heading
        rows.append({'chunk_id':chunk['chunk_id'], 'pages':chunk.get('pages', []),
                     'content':chunk.get('content', ''), 'items':paragraphs,
                     'headings':list(headings.values()),
                     'proposed_topics':guesses[chunk['chunk_id']]['proposed_topics'] if use_b2 else [],
                     'rule_evidence':guesses[chunk['chunk_id']] if use_b2 else None,
                     'final_topics':labels[chunk['chunk_id']]['topics']})
    version = topic_map.get('schema_version', 1)
    if version not in (1,2) or final.get('schema_version',1) != version:
        raise ValueError('Review requires matching supported B3/B4 schemas.')
    passage_topics = {}
    if version == 2:
        lookup = {i['item_id']:i for row in rows for i in row['items']}
        passage_topics = {topic:[] for topic in topic_map['topics']}
        for topic, groups in topic_map['topics'].items():
            for group in groups:
                refs = group['evidence_item_ids']+group['context_item_ids']
                if not set(refs) <= set(lookup):
                    raise ValueError('Saved passage citation has no captured source item.')
                targets = [row['chunk_id'] for row in rows for label in row['final_topics']
                           if label['topic'] == topic and group in label['groups']]
                if not targets:
                    raise ValueError('B4 group does not match the captured B3 result.')
                passage_topics[topic].append({**group,'topic':topic,'target_chunk_ids':targets,
                    'evidence_items':[lookup[i] for i in group['evidence_item_ids']],
                    'context_items':[lookup[i] for i in group['context_item_ids']]})
        # Chunk-based navigation remains available for B1, B2 and unclassified
        # sources. It is not the default passage evidence display for B3/B4.
        topics = {topic:list(dict.fromkeys(c for g in groups for c in g['target_chunk_ids']))
                  for topic, groups in passage_topics.items()}
    else:
        topics = {topic:[ref['chunk_id'] for ref in refs] for topic, refs in topic_map['topics'].items()}
    return {'schema_version':version,'legacy_citations':version == 1,'use_b2':use_b2,
            'pipeline_layout':layout,'classification_stage':classification_stage,'map_stage':map_stage,
            'passage_topics':passage_topics,'topics':topics,
            'unclassified_chunk_ids':topic_map['unclassified_chunk_ids'], 'chunks':rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id')
    parser.add_argument('destination', type=Path)
    parser.add_argument('--trace-root', default='tmp/runs')
    args = parser.parse_args()
    print(export_run_review(args.run_id, args.destination, trace_root=args.trace_root))
