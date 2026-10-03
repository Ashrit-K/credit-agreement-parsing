"""Single-worker loopback controller for immutable corpus PDFs."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from .tracing import atomic_json, safe_data
from .workbench_data import (SNAPSHOT, checked_path, project_batches, project_stages,
                             read_events, snapshot_metadata, summary)

DEFAULTS = {'model':'deepseek-v4-pro', 'reasoning_effort':'high',
            'classification_model':'deepseek-v4-flash',
            'classification_reasoning_effort':'medium', 'use_hierarchy':True, 'debug':True}
ID = re.compile(r'[A-Za-z0-9_-]{1,100}')


class Workbench:
    def __init__(self, project_root, trace_root=None, pipeline=None):
        self.project_root = Path(project_root).resolve()
        self.corpus = self.project_root / 'raw_documents' / 'pdf'
        if self.corpus.is_symlink() or (self.project_root / 'raw_documents').is_symlink():
            raise ValueError('Corpus must not be symbolic links')
        requested = Path(trace_root) if trace_root is not None else self.project_root / 'tmp/runs'
        if not requested.is_absolute():
            requested = self.project_root / requested
        if any(p.is_symlink() for p in (requested, *requested.parents)):
            raise ValueError('Trace root must not contain symbolic links')
        self.trace_root = requested.resolve()
        self.trace_root.mkdir(parents=True, exist_ok=True)
        self.pipeline = pipeline
        self.token = secrets.token_urlsafe(32)
        self._lock = threading.Lock()
        self._active = None
        self._history_cache = {}
        self._source_hashes = None
        lock_path = checked_path(self.trace_root,'.workbench.lock')
        self._owner_lock = os.fdopen(os.open(lock_path,os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,0o600),'r+')
        try:
            fcntl.flock(self._owner_lock.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._owner_lock.close()
            raise RuntimeError('Another workbench owns this trace root') from None
        try:
            for folder in self.trace_root.iterdir():
                if folder.is_dir() and not folder.is_symlink() and ID.fullmatch(folder.name):
                    job = self._job(folder)
                    if job and job.get('status') in ('running', 'queued'):
                        job['status'] = 'interrupted'
                        atomic_json(checked_path(folder,'job.json'), job)
        except Exception:
            self._owner_lock.close()
            raise

    def close(self):
        """Release ownership only after this controller's worker has stopped."""
        with self._lock:
            if self._active is not None:
                raise RuntimeError('A document job is still running')
            self._owner_lock.close()

    def documents(self):
        if not self.corpus.exists():
            return []
        return [{'document_id':p.name, 'name':p.name, 'size_bytes':p.stat().st_size}
                for p in sorted(self.corpus.glob('*.pdf')) if p.is_file() and not p.is_symlink()]

    def source_path(self, document_id):
        path = checked_path(self.corpus, document_id)
        if document_id not in {d['document_id'] for d in self.documents()}:
            raise FileNotFoundError('Unknown registered PDF')
        return path

    def _directory(self, run_id):
        if not isinstance(run_id,str) or not ID.fullmatch(run_id):
            raise ValueError('Invalid run identifier')
        folder = checked_path(self.trace_root,run_id)
        if not folder.is_dir():
            raise FileNotFoundError('Unknown run')
        return folder

    def _job(self, folder):
        path = checked_path(folder,'job.json')
        return safe_data(json.loads(path.read_text())) if path.is_file() else None

    def _history_job(self, folder, events):
        debug = checked_path(folder,'debug')
        event_path = checked_path(folder,'events.jsonl')
        signature = (folder.stat().st_mtime_ns,
                     debug.stat().st_mtime_ns if debug.exists() else None,
                     event_path.stat().st_mtime_ns if event_path.exists() else None)
        cached = self._history_cache.get(folder.name)
        if cached and cached[0] == signature:
            return dict(cached[1])
        document_id = None
        metadata_list = snapshot_metadata(folder)
        for metadata in metadata_list:
            if not metadata['filename'].startswith('A-input-') or metadata['filename'].startswith('A-input-artifacts-'):
                continue
            captured = self.snapshot(folder.name, metadata['filename'])
            args = captured.get('args',[]) if isinstance(captured,dict) else []
            if not args or not isinstance(args[0],str):
                continue
            candidate = Path(args[0])
            if not candidate.is_absolute():
                candidate = self.project_root/candidate
            try:
                registered = self.source_path(candidate.name)
                if candidate.absolute() == registered.absolute():
                    document_id = registered.name
                    break
            except (ValueError,FileNotFoundError):
                continue
        if document_id is None:
            for metadata in metadata_list:
                name = metadata['filename']
                if not name.startswith(('D1-input-','D1-output-','D4-output-')) or '-artifacts-' in name:
                    continue
                captured = self.snapshot(folder.name,name)
                if not isinstance(captured,dict):
                    continue
                digests = [captured.get('document_id')]
                if name.startswith('D1-input-'):
                    digests += [arg.get('source_sha256') for arg in captured.get('args',[]) if isinstance(arg,dict)]
                for digest in digests:
                    if not isinstance(digest,str) or not re.fullmatch(r'[a-f0-9]{64}',digest):
                        continue
                    if self._source_hashes is None:
                        hashes = {}
                        for document in self.documents():
                            path = self.source_path(document['document_id'])
                            hasher = hashlib.sha256()
                            with path.open('rb') as stream:
                                for block in iter(lambda:stream.read(1024*1024),b''):
                                    hasher.update(block)
                            hashes[hasher.hexdigest()] = document['document_id']
                        self._source_hashes = hashes
                    document_id = self._source_hashes.get(digest)
                    if document_id is not None:
                        break
                if document_id is not None:
                    break
        result = {'run_id':folder.name,'status':'historical','document_id':document_id,
                'settings':None,'started_at':None,'error_type':None,
                'pipeline_layout':next((e['pipeline_layout'] for e in events if 'pipeline_layout' in e),None)}
        self._history_cache[folder.name] = (signature,result)
        return dict(result)

    def runs(self):
        result = []
        for folder in sorted(self.trace_root.iterdir(), key=lambda p:p.name, reverse=True):
            if folder.is_dir() and not folder.is_symlink() and ID.fullmatch(folder.name):
                job = self._job(folder)
                events = read_events(folder)
                row = dict(job or self._history_job(folder,events))
                row['pipeline_layout'] = next((e['pipeline_layout'] for e in events if 'pipeline_layout' in e), None)
                if row.get('document_id'):
                    try:
                        self.source_path(row['document_id'])
                    except (ValueError,FileNotFoundError):
                        row['document_id'] = None
                result.append(row)
        return result

    def start_job(self, settings):
        from .llm import MODEL_ROUTES
        if not isinstance(settings,dict) or set(settings)-set(DEFAULTS)-{'document_id'}:
            raise ValueError('Unknown run setting')
        document_id = settings.get('document_id')
        if not isinstance(document_id,str):
            raise ValueError('A registered PDF is required')
        path = self.source_path(document_id)
        options = {**DEFAULTS, **{k:v for k,v in settings.items() if k in DEFAULTS}}
        for field in ('use_hierarchy','debug'):
            if not isinstance(options[field],bool):
                raise ValueError('Boolean setting required')
        for field in ('model','classification_model'):
            if not isinstance(options[field],str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',options[field]):
                raise ValueError('Invalid model identifier')
            if options[field] not in MODEL_ROUTES:
                raise ValueError('Model has no configured API route')
        for field in ('reasoning_effort','classification_reasoning_effort'):
            if options[field] not in ('none','minimal','low','medium','high','xhigh'):
                raise ValueError('Invalid reasoning effort')
        for model, effort in [('model','reasoning_effort'),
                             ('classification_model','classification_reasoning_effort')]:
            if MODEL_ROUTES[options[model]] == 'messages' and options[effort] not in ('none','high'):
                raise ValueError('Messages accepts only none or high reasoning')
        with self._lock:
            if self._owner_lock.closed:
                raise RuntimeError('Workbench is closed')
            if self._active is not None:
                raise RuntimeError('A document job is already running')
            run_id = uuid4().hex
            folder = checked_path(self.trace_root,run_id)
            folder.mkdir()
            job = {'run_id':run_id,'status':'running','document_id':document_id,'settings':options,
                   'started_at':datetime.now(timezone.utc).isoformat(),'error_type':None}
            atomic_json(checked_path(folder,'job.json'),job)
            self._active = run_id
            try:
                threading.Thread(target=self._worker,args=(job,path),daemon=True).start()
            except Exception as error:
                self._active = None
                job.update(status='failed',error_type=type(error).__name__)
                atomic_json(checked_path(folder,'job.json'),job)
                raise
            return dict(job)

    def _worker(self, job, path):
        folder = self._directory(job['run_id'])
        record = {**job}
        try:
            pipeline = self.pipeline
            if pipeline is None:
                from .runner import run_pipeline
                pipeline = run_pipeline
            result = pipeline(path, **job['settings'], run_id=job['run_id'],
                              trace_root=self.trace_root, generated_root=self.project_root/'tmp')
            atomic_json(checked_path(folder,'result.json'),safe_data(result))
            record['status'] = 'completed'
        except Exception as error:
            record.update(status='failed',error_type=type(error).__name__)
        finally:
            with self._lock:
                try:
                    atomic_json(checked_path(folder,'job.json'),record)
                finally:
                    self._active = None

    def snapshot(self, run_id, name):
        if not isinstance(name,str) or not SNAPSHOT.fullmatch(name):
            raise ValueError('Unknown snapshot name')
        debug = checked_path(self._directory(run_id),'debug')
        path = checked_path(debug,name)
        if not path.is_file():
            raise FileNotFoundError('Snapshot unavailable')
        return safe_data(json.loads(path.read_text()))

    def run_data(self, run_id):
        folder = self._directory(run_id)
        job = self._job(folder)
        events = read_events(folder)
        if job is None:
            job = self._history_job(folder,events)
        snapshots = snapshot_metadata(folder)
        result_path = checked_path(folder,'result.json')
        result = safe_data(json.loads(result_path.read_text())) if result_path.is_file() else None
        if result is None:
            for stage in ('D4','D1'):
                candidates = [s for s in snapshots if s['filename'].startswith(stage+'-output-')
                              and not s['filename'].startswith(stage+'-output-artifacts-')]
                if candidates:
                    result = self.snapshot(run_id,candidates[-1]['filename'])
                    break
        return {'run_id':run_id,'job':job,'events':events,'stages':project_stages(events,job),
                'snapshots':snapshots,'summary':summary(folder,run_id),'result':result,
                'batches':project_batches(events)}

    def review(self, run_id):
        from . import review
        folder = self._directory(run_id)
        data = {'run_id':run_id,'events':read_events(folder), 'snapshots':[
            {**s,'data':self.snapshot(run_id,s['filename'])} for s in snapshot_metadata(folder)]}
        return review.render_run_review(data)


def make_server(workbench, port=0):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def respond(self,status,data,content_type='application/json'):
            body = json.dumps(data).encode() if content_type=='application/json' else data
            if isinstance(body,str):
                body = body.encode()
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def do_GET(self):
            if not self.valid_host():
                return self.respond(403,{'error_type':'Forbidden'})
            try:
                parts = unquote(urlsplit(self.path).path).split('/')[1:]
                if parts == ['']:
                    return self.respond(200,Path(__file__).with_name('workbench.html').read_text(),'text/html; charset=utf-8')
                if parts == ['api','config']:
                    from .llm import MODEL_ROUTES
                    return self.respond(200,{'token':workbench.token,'defaults':DEFAULTS,'models':MODEL_ROUTES,
                        'routes':{'documents':'/api/documents','runs':'/api/runs','config':'/api/config'}})
                if parts == ['api','documents']:
                    return self.respond(200,workbench.documents())
                if parts == ['api','runs']:
                    return self.respond(200,workbench.runs())
                if len(parts)==4 and parts[:2]==['api','documents'] and parts[3]=='pdf':
                    return self.respond(200,workbench.source_path(parts[2]).read_bytes(),'application/pdf')
                if len(parts)==3 and parts[:2]==['api','runs']:
                    return self.respond(200,workbench.run_data(parts[2]))
                if len(parts)==5 and parts[:2]==['api','runs'] and parts[3]=='snapshots':
                    return self.respond(200,workbench.snapshot(parts[2],parts[4]))
                if len(parts)==4 and parts[:2]==['api','runs'] and parts[3]=='review':
                    return self.respond(200,workbench.review(parts[2]),'text/html; charset=utf-8')
                self.respond(404,{'error_type':'NotFound'})
            except (ValueError,FileNotFoundError) as error:
                self.respond(400 if isinstance(error,ValueError) else 404,{'error_type':type(error).__name__})
            except Exception:
                self.respond(500,{'error_type':'ReadError'})

        def do_POST(self):
            origin = f'http://127.0.0.1:{self.server.server_port}'
            if not self.valid_host() or self.headers.get('Origin')!=origin or not secrets.compare_digest(
                    self.headers.get('X-Workbench-Token',''),workbench.token):
                return self.respond(403,{'error_type':'Forbidden'})
            if urlsplit(self.path).path != '/api/runs':
                return self.respond(404,{'error_type':'NotFound'})
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 16384:
                    raise ValueError('Invalid request size')
                settings = json.loads(self.rfile.read(length))
                self.respond(202,workbench.start_job(settings))
            except RuntimeError:
                self.respond(409,{'error_type':'JobAlreadyRunning'})
            except (ValueError,FileNotFoundError,TypeError):
                self.respond(400,{'error_type':'InvalidRequest'})
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=60900)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[2]
    workbench = Workbench(project)
    server = None
    try:
        server = make_server(workbench,args.port)
        print(f'Pipeline workbench: http://127.0.0.1:{server.server_port}')
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.server_close()
        try:
            workbench.close()
        except RuntimeError:
            # Process exit releases the lock; never unlock an active worker.
            pass


if __name__ == '__main__':
    main()
