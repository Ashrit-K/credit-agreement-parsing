"""Read-only, trace-backed workbench projections."""
import json
import re
from pathlib import Path

from .tracing import safe_data, summarize_run

STAGES = ['A', *[f'A{i}' for i in range(1, 12)], 'A3.1',
          *[f'B{i}' for i in range(1, 7)], 'C', *[f'D{i}' for i in range(1, 5)]]
SNAPSHOT = re.compile(r'^(A(?:[1-9]|10|11|3\.1)?|B[1-6]|C|D[1-4])-(?:input|output|request|response|final|validation(?:-error)?|evidence|manifest)[A-Za-z0-9_.-]*\.json$')


def checked_path(root: Path, *parts: str) -> Path:
    path = root
    for part in parts:
        if not part or part in ('.', '..') or '/' in part or '\\' in part:
            raise ValueError('Invalid identifier')
        path = path / part
        if path.is_symlink():
            raise ValueError('Symbolic links are not permitted')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path escapes registered root')
    return path


def read_events(directory: Path) -> list[dict]:
    path = checked_path(directory, 'events.jsonl')
    if not path.exists():
        return []
    raw = path.read_text(encoding='utf-8')
    lines = raw.splitlines(keepends=True)
    events = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError('Trace event must be an object')
            events.append(safe_data(row))
        except json.JSONDecodeError:
            if index == len(lines)-1 and not line.endswith('\n'):
                break
            raise ValueError('Corrupt completed trace record') from None
    return events


def snapshot_metadata(directory: Path) -> list[dict]:
    debug = checked_path(directory, 'debug')
    if not debug.exists():
        return []
    result = []
    for path in sorted(debug.glob('*.json'), key=lambda p: (p.stat().st_mtime_ns, p.name)):
        match = SNAPSHOT.fullmatch(path.name)
        if match:
            checked_path(debug, path.name)
            result.append({'filename':path.name, 'stage':match.group(1)})
    return result


def project_stages(events, job):
    stages = {stage:{'status':'unrecorded' if job is None or job.get('status')=='historical' else 'waiting',
                     'active_spans':[], 'events':[]} for stage in STAGES}
    for row in events:
        stage = row.get('stage')
        if stage not in stages:
            continue
        view = stages[stage]
        view['events'].append(row)
        span = row.get('span_id')
        event = row.get('event')
        if event == 'stage_started':
            if span and span not in view['active_spans']:
                view['active_spans'].append(span)
            view['status'] = 'running'
        elif event == 'stage_finished':
            if span in view['active_spans']:
                view['active_spans'].remove(span)
            status = row.get('status', 'completed')
            if status == 'failed' or view['status'] == 'failed':
                view['status'] = 'failed'
            else:
                view['status'] = 'running' if view['active_spans'] else status
        elif event in ('stage_skipped', 'cache_hit'):
            view['status'] = 'skipped' if event == 'stage_skipped' else 'cached'
    if job and job.get('status') in ('failed', 'interrupted'):
        for view in stages.values():
            if view['status'] == 'running':
                view['status'] = 'interrupted'
    if job and job.get('status') == 'historical':
        for view in stages.values():
            if view['status'] == 'running':
                view['status'] = 'unrecorded'
    return stages


def project_batches(events):
    batches = {}
    for row in events:
        name, batch = row.get('event'), row.get('batch_id')
        if row.get('stage') != 'B2' or not batch or name not in ('batch_attempt','batch_validated','batch_reused','batch_failed'):
            continue
        batches[batch] = {**batches.get(batch,{}), **row, 'status':{'batch_attempt':'active', 'batch_validated':'completed',
                                           'batch_reused':'reused', 'batch_failed':'failed'}[name]}
    return {**{state:sum(r['status']==state for r in batches.values())
               for state in ('active','completed','reused','failed')}, 'records':list(batches.values())}


def summary(directory, run_id):
    # The canonical analytics reader rejects partial tails. Keep live polling
    # truthful and defer analytics until that append is complete.
    path = checked_path(directory, 'events.jsonl')
    if not path.exists():
        return None
    try:
        return safe_data(summarize_run(run_id, trace_root=directory.parent))
    except json.JSONDecodeError:
        return None
