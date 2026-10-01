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
        if not re.match(r'^(?:A|B[1-4]|C)-(?:input|output|request|response|final|validation-error)', path.name):
            continue
        if path.is_symlink():
            raise ValueError('Debug snapshots must not be symbolic links.')
        snapshots.append({'filename': path.name, 'data': json.loads(path.read_text())})
    return safe_data({'run_id':run_id, 'events':events, 'snapshots':snapshots})


def export_run_review(run_id: str, destination: str | Path, *,
                      trace_root: str | Path = 'tmp/runs') -> Path:
    """Embed actual captured data, escaping HTML script delimiters safely."""
    data = load_run_review(run_id, trace_root=trace_root)
    data['review'] = build_topic_review(data)
    data['stages'] = build_stage_review(data)
    # The human view already contains resolved source paragraphs. Do not embed
    # repeated full document snapshots (A, B1 and their downstream inputs) a
    # second time. Keep only model exchanges and the source manifest alongside
    # the view model so the browser stays responsive on longer agreements.
    compact = []
    for snapshot in data['snapshots']:
        name = snapshot['filename']
        if name.startswith(('B3-request-', 'B3-response-', 'B3-validation-error-', 'C-request-', 'C-response-')):
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
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template.replace('__RUN_DATA__', encoded), encoding='utf-8')
    return target


def build_stage_review(data: dict) -> dict:
    """Expose actual boundary inputs/outputs once per implemented stage.

    Argument snapshots and captured file contents are distinct: an API receives
    artifact objects, while the file contents are what its transformation uses.
    Preserve both, and label substeps without events as uninstrumented in the UI.
    """
    result = {}
    for stage in ('A', 'B1', 'B2', 'B3', 'B4', 'C'):
        def last(prefix):
            found = [s['data'] for s in data['snapshots']
                     if s['filename'].startswith(prefix + '-')
                     and not (prefix.endswith(('-input', '-output'))
                              and s['filename'].startswith(prefix + '-artifacts-'))]
            return found[-1] if found else None
        inputs = {}
        # Some calls capture multiple argument artifacts in separate snapshots.
        # Merging fields retains their actual input files without duplicating
        # the repeated captures created by resuming the same run.
        for snapshot in data['snapshots']:
            if snapshot['filename'].startswith(stage + '-input-artifacts-'):
                inputs.update(snapshot['data'])
        result[stage] = {'input':last(stage + '-input'), 'input_artifacts':inputs,
                         'output':last(stage + '-output-artifacts'),
                         'return_value':last(stage + '-output'),
                         'events':[event for event in data.get('events', []) if event.get('stage') == stage]}
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
    final = captured('B3-final')
    topic_map = captured('B4-final')
    if not all((chunks, signals, final, topic_map)):
        return None
    canonical = (captured('A-output-artifacts') or {}).get('docling_json_path', {})
    canonical_items = {item['self_ref']:item for section in ('texts', 'tables')
                       for item in canonical.get(section, []) if 'self_ref' in item}
    guesses = {row['chunk_id']:row for row in signals['classifications']}
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
                     'proposed_topics':guesses[chunk['chunk_id']]['proposed_topics'],
                     'rule_evidence':guesses[chunk['chunk_id']],
                     'final_topics':labels[chunk['chunk_id']]['topics']})
    return {'topics':{topic:[ref['chunk_id'] for ref in refs] for topic, refs in topic_map['topics'].items()},
            'unclassified_chunk_ids':topic_map['unclassified_chunk_ids'], 'chunks':rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id')
    parser.add_argument('destination', type=Path)
    parser.add_argument('--trace-root', default='tmp/runs')
    args = parser.parse_args()
    print(export_run_review(args.run_id, args.destination, trace_root=args.trace_root))
