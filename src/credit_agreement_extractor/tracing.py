"""Local, run-linked telemetry and opt-in evidence snapshots; no server needed."""
from __future__ import annotations

from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from functools import wraps
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from threading import Lock
import time
from uuid import uuid4
from pydantic import BaseModel, SecretStr

_ACTIVE: ContextVar[RunTrace | None] = ContextVar('credit_run_trace', default=None)
_SPAN = ContextVar('credit_span', default=None)
_CONTEXT = ContextVar('credit_trace_context', default={})
_SECRET_FIELDS = {'apikey', 'authorization', 'headers', 'credential', 'credentials', 'token', 'secret', 'password'}
_EVENT_WRITE_LOCK = Lock()


def safe_data(value):
    """Capture data, not executable objects/clients or secret values."""
    if isinstance(value, SecretStr): return '[REDACTED]'
    if is_dataclass(value): return safe_data(asdict(value))
    if isinstance(value, BaseModel): return safe_data(value.model_dump(mode='python'))
    if isinstance(value, dict):
        return {str(k): '[REDACTED]' if re.sub(r'[^a-z]', '', str(k).lower()) in _SECRET_FIELDS
                else safe_data(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [safe_data(v) for v in value]
    if isinstance(value, Path): return str(value)
    if value is None or isinstance(value, (str, int, float, bool)): return value
    return f'<{type(value).__name__}>'


def atomic_json(path: Path, data) -> None:
    """Write a complete JSON file before replacing its destination."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
        temporary.replace(path)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)


class RunTrace:
    def __init__(self, root, run_id, debug):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', run_id):
            raise ValueError('run_id must be a simple identifier, not a path.')
        self.run_id, self.debug = run_id, debug
        self.directory = Path(root) / run_id
        self.directory.mkdir(parents=True, exist_ok=True)

    def event(self, name, data=None):
        # Append one compact metadata event; full text is never added implicitly.
        row = {'run_id':self.run_id, 'span_id':_SPAN.get(), 'event':name,
               'time_unix':time.time(), **safe_data(_CONTEXT.get()), **safe_data(data or {})}
        # Multiple copied contexts (or RunTrace instances sharing a run folder)
        # may append concurrently. Keep each complete line and flush together.
        with _EVENT_WRITE_LOCK:
            with (self.directory / 'events.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')

    def snapshot(self, name, data):
        if self.debug:
            captured = safe_data(data)
            if isinstance(captured, dict):
                context = _CONTEXT.get()
                captured['_trace'] = safe_data({
                    **{key: context[key] for key in
                       ('stage', 'source_sha256', 'batch_id', 'attempt', 'attempt_id')
                       if key in context},
                    'run_id': self.run_id, 'span_id': _SPAN.get(),
                })
            atomic_json(self.directory / 'debug' / f'{name}-{uuid4().hex}.json', captured)

    @contextmanager
    def bind(self, **context):
        token = _CONTEXT.set({**_CONTEXT.get(), **context})
        try: yield
        finally: _CONTEXT.reset(token)

    def artifact_snapshot(self, name, value):
        """Copy generated artifact contents for evals, not just their paths.

        Only explicit artifact path fields are read. Source PDFs, .env files,
        arbitrary paths, and injected clients are never recursively inspected.
        """
        if not self.debug or not is_dataclass(value): return
        contents = {}
        for field, path in asdict(value).items():
            if isinstance(path, Path) and (field.endswith('_path')) and path.suffix in ('.json','.md') and path.is_file():
                text = path.read_text(encoding='utf-8')
                contents[field] = json.loads(text) if path.suffix == '.json' else text
        if contents: self.snapshot(name, contents)


def current_trace():
    return _ACTIVE.get()


def summarize_run(run_id: str, *, trace_root='tmp/runs', debug=False):
    """Read local analytics; unknown usage/cost is explicitly counted.

    Sum provider attempt events, not stage durations or batch events, so nested
    instrumentation cannot accidentally double-count paid requests. Grouping by
    model and stage supports later comparisons without an observability server.
    """
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', run_id): raise ValueError('Invalid run_id.')
    events = [json.loads(line) for line in (Path(trace_root)/run_id/'events.jsonl').read_text().splitlines() if line]
    calls = [e for e in events if e.get('event') == 'llm_attempt']
    failed_spans = {e['span_id'] for e in events if e.get('event')=='stage_finished'
                    and e.get('stage')=='C' and e.get('status')=='failed' and e.get('span_id')}
    failed_batches = {(e.get('source_sha256'),e.get('batch_id'),e.get('attempt'))
                      for e in events if e.get('event')=='batch_failed'}

    def token_count(row, field):
        value = (row.get('usage') or {}).get(field)
        return value if isinstance(value,int) and not isinstance(value,bool) and value>=0 else None

    def failed(row):
        return (row.get('status')=='failed' or row.get('span_id') in failed_spans
                or (row.get('source_sha256'),row.get('batch_id'),row.get('attempt')) in failed_batches)

    def aggregate(rows):
        usage_missing = sum(token_count(r,'input_tokens') is None
                            or token_count(r,'output_tokens') is None for r in rows)
        costs, unknown = {}, 0
        for row in rows:
            cost = row.get('cost') or {}
            if cost.get('kind') in ('estimated','reported') and isinstance(cost.get('amount'),(int,float)) and cost.get('currency'):
                currency = cost['currency']
                costs[currency] = costs.get(currency,0) + cost['amount']
            else: unknown += 1
        return {'request_count':len(rows),'failed_requests':sum(failed(r) for r in rows),
                'retry_requests':sum(r.get('attempt',1)>1 for r in rows),
                'input_tokens':sum(token_count(r,'input_tokens') or 0 for r in rows),
                'output_tokens':sum(token_count(r,'output_tokens') or 0 for r in rows),
                'unknown_usage_requests':usage_missing,'known_cost_by_currency':costs,
                'unknown_cost_requests':unknown,'cost_complete':unknown==0,
                'estimated_cost_requests':sum(r.get('cost',{}).get('kind')=='estimated' for r in rows),
                'total_request_latency_seconds':sum(r.get('latency_seconds',0) for r in rows)}
    result = {'run_id':run_id, **aggregate(calls)}
    for field in ('model','stage','source_sha256'):
        keys = sorted({r.get(field,'unknown') for r in calls})
        result['by_'+field] = {key:aggregate([r for r in calls if r.get(field,'unknown')==key]) for key in keys}
    if debug: atomic_json(Path(trace_root)/run_id/'summary.json',result)
    return result


def traced(stage):
    """Instrument a public wrapper, preserving its original return contract.

    Reuse a context-local trace for nested calls. Separate API calls can share
    an explicit run_id and trace_root to build one linked run folder.
    """
    def decorate(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            trace = current_trace()
            if trace is None:
                trace = RunTrace(kwargs.get('trace_root') or 'tmp/runs',
                                 kwargs.get('run_id') or uuid4().hex, kwargs.get('debug', False))
            token = _ACTIVE.set(trace)
            parent_span = _SPAN.get()
            span = _SPAN.set(uuid4().hex)
            context_token = _CONTEXT.set({**_CONTEXT.get(), 'stage': stage})
            started = time.monotonic()
            try:
                trace.event('stage_started', {'stage':stage,'parent_span_id':parent_span})
                trace.snapshot(stage + '-input', {'args':args, 'kwargs':kwargs})
                for value in args: trace.artifact_snapshot(stage + '-input-artifacts', value)
                result = function(*args, **kwargs)
                trace.snapshot(stage + '-output', result)
                trace.artifact_snapshot(stage + '-output-artifacts', result)
                trace.event('stage_finished', {'stage':stage,'status':'completed',
                                              'latency_seconds':time.monotonic()-started})
                return result
            except Exception as error:
                # Error messages may contain credentials or source snippets.
                trace.event('stage_finished', {'stage':stage,'status':'failed',
                                              'error_type':type(error).__name__,
                                              'latency_seconds':time.monotonic()-started})
                raise
            finally:
                _ACTIVE.reset(token)
                _SPAN.reset(span)
                _CONTEXT.reset(context_token)
        return wrapper
    return decorate
