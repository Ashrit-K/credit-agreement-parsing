"""Local human annotation UI. Human labels have no path into model execution.

Run with ``uv run python -m credit_agreement_extractor.annotation``. This module
reads source conversions and writes only the separate evaluation label store.
It never imports B2, B3, model transport, or a provider credential. Conversely,
pipeline modules do not import this module or read the evaluation directory.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
from threading import RLock
from urllib.parse import parse_qs, urlsplit

from .topic_taxonomy import VOCABULARY, TOPIC_DEFINITIONS, TAXONOMY_VERSION


class RevisionConflict(ValueError):
    """Another tab has saved a newer revision of this passage."""


def build_annotation_document(canonical, hierarchy, *, source_sha256, name, document_id):
    """Create passage views from canonical reading order, without model guesses.

    One canonical leaf is one review unit. Tables retain all their cells; source
    pages and headings remain context. Chunks are an LLM batching concern, not
    a restriction on how precisely a human can label original passages.
    """
    if hierarchy.get('source_sha256') != source_sha256:
        raise ValueError('Hierarchy source identity differs from the source document.')
    index = {i['self_ref']: i for collection in ('texts', 'tables', 'pictures', 'form_items', 'key_value_items')
             for i in canonical.get(collection, [])}
    passages = []
    for ref in hierarchy['reading_order']:
        item, context = index[ref], hierarchy['items'][ref]
        text = item.get('orig') or item.get('text') or ''
        data = item.get('data', {})
        table = [[cell.get('text', '') for cell in row] for row in data.get('grid', [])]
        if not table and data.get('table_cells'):
            rows = {}
            for cell in data['table_cells']:
                rows.setdefault(cell.get('start_row_offset', 0), []).append(cell.get('text', ''))
            table = [rows[row] for row in sorted(rows)]
        if not text.strip() and not table:
            continue  # Empty image containers cannot be reviewed as text.
        passages.append({'item_id': ref, 'text': text, 'table': table,
                         'label': item.get('label', 'text'), 'pages': context.get('pages', []),
                         'heading_path': context.get('heading_path', []),
                         'container_path': context.get('container_path', [])})
    # A changed conversion produces a different catalog. Prior human decisions
    # stay attached to their original evidence instead of silently drifting.
    digest = hashlib.sha256(json.dumps(passages, sort_keys=True).encode()).hexdigest()
    return {'document_id': document_id, 'name': name, 'source_sha256': source_sha256,
            'catalog_sha256': digest, 'passages': passages}


class AnnotationStore:
    """Atomic, versioned human decisions outside all pipeline artifact roots."""
    def __init__(self, root):
        self.root = Path(root)
        self.lock = RLock()

    def _path(self, document):
        import re
        source, catalog = document['source_sha256'], document['catalog_sha256']
        if not all(re.fullmatch(r'[a-f0-9]{64}', value) for value in (source, catalog)):
            raise ValueError('Invalid source or catalog fingerprint.')
        return self.root / f'{source}-{catalog}.json'

    def load(self, document):
        with self.lock:
            path = self._path(document)
            if path.is_symlink():
                raise ValueError('Annotation file cannot be a symlink.')
            if path.exists():
                result = json.loads(path.read_text())
                if (result.get('schema_version') != 1 or result.get('taxonomy_version') not in ('credit-topics-v1', TAXONOMY_VERSION)
                        or result.get('source_sha256') != document['source_sha256']
                        or result.get('catalog_sha256') != document['catalog_sha256']):
                    raise ValueError('Stored annotations do not match this evidence and taxonomy.')
                # Additive compatibility view only: loading never rewrites the
                # user's file. Old negatives cover only the old vocabulary;
                # absence of the new label means unknown, not a negative label.
                legacy = result['taxonomy_version'] == 'credit-topics-v1'
                for record in result['annotations'].values():
                    if 'reviewed_topics' not in record:
                        record['reviewed_topics'] = [t for t in VOCABULARY
                                                    if not legacy or t != 'contract_definitions'] if record.get('reviewed') else []
                result['taxonomy_version'] = TAXONOMY_VERSION
                return result
            return {'schema_version': 1, 'purpose': 'human_evaluation_only',
                    'taxonomy_version': TAXONOMY_VERSION, 'document_id': document['document_id'],
                    'source_sha256': document['source_sha256'],
                    'catalog_sha256': document['catalog_sha256'], 'annotations': {}}

    def save(self, document, item_id, topics, *, revision, notes=''):
        with self.lock:
            if item_id not in {p['item_id'] for p in document['passages']}:
                raise ValueError('Passage is not in this document catalog.')
            if (not isinstance(topics, list) or not all(isinstance(t, str) for t in topics)
                    or len(set(topics)) != len(topics) or not set(topics) <= set(VOCABULARY)):
                raise ValueError('Select unique approved topic IDs.')
            if type(revision) is not int or revision < 0 or not isinstance(notes, str) or len(notes) > 4000:
                raise ValueError('Invalid annotation revision or notes.')
            result = self.load(document)
            previous = result['annotations'].get(item_id, {})
            if previous.get('revision', 0) != revision:
                raise RevisionConflict('A newer review exists. Reload before saving.')
            record = {'reviewed': True, 'topics': [t for t in VOCABULARY if t in topics],
                      'reviewed_topics': list(VOCABULARY),
                      'notes': notes, 'revision': revision + 1,
                      'updated_at': datetime.now(timezone.utc).isoformat()}
            result['annotations'][item_id] = record
            # Temporary sibling + replace gives a durable completed save; never
            # write human labels to converted/, stage_b/, or a model trace.
            from .tracing import atomic_json
            atomic_json(self._path(document), result)
            return record


class AnnotationWorkspace:
    """Allowlisted golden sources, local conversion jobs, and human label storage."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        manifest = json.loads((self.root/'evaluations/golden_documents.json').read_text())
        self.documents = manifest['documents']
        self.sources = {}
        for doc in self.documents:
            path = (self.root/doc['path']).resolve()
            if not path.is_relative_to(self.root/'raw_documents') or not path.is_file():
                raise ValueError('Golden source must be an existing corpus file.')
            if doc['id'] in self.sources:
                raise ValueError('Golden document IDs must be unique.')
            self.sources[doc['id']] = path
        self.store = AnnotationStore(self.root/'evaluations/ground_truth')
        self.catalogs, self.jobs = {}, {}
        self.lock = RLock()
        self.pool = ThreadPoolExecutor(max_workers=1)

    def render_page(self, document_id, page):
        """Render the actual PDF page, independent of browser PDF plug-ins."""
        source = self.source(document_id)
        if source.suffix.lower() != '.pdf' or type(page) is not int or page < 1:
            raise ValueError('A PDF and positive page number are required.')
        document = self.catalog(document_id)
        if document is None or page not in {n for p in document['passages'] for n in p['pages']}:
            raise ValueError('Page is not present in this document catalog.')
        result = subprocess.run(['pdftoppm', '-f', str(page), '-l', str(page),
                                 '-singlefile', '-scale-to', '1600', '-png', str(source)],
                                capture_output=True, check=True, timeout=30)
        return result.stdout

    def source(self, document_id):
        if document_id not in self.sources:
            raise ValueError('Unknown golden document ID.')
        return self.sources[document_id]

    def catalog(self, document_id):
        with self.lock:
            if document_id in self.catalogs:
                return self.catalogs[document_id]
        source = self.source(document_id)
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        converted = self.root/'tmp/converted'/source_hash
        required = ['manifest.json', 'document.docling.json', 'document.hierarchy.json', 'document.md']
        if not all((converted/name).is_file() for name in required):
            return None
        manifest = json.loads((converted/'manifest.json').read_text())
        if manifest.get('status') != 'completed' or manifest.get('source', {}).get('sha256') != source_hash:
            return None
        document = build_annotation_document(
            json.loads((converted/'document.docling.json').read_text()),
            json.loads((converted/'document.hierarchy.json').read_text()),
            source_sha256=source_hash, name=source.name, document_id=document_id)
        with self.lock:
            self.catalogs[document_id] = document
        return document

    def prepare(self, document_id):
        source = self.source(document_id)
        with self.lock:
            job = self.jobs.get(document_id)
            if job and job['status'] == 'preparing':
                return job
            self.jobs[document_id] = {'status': 'preparing'}

        def convert():
            try:
                # Source-only Stage A conversion. No model classification or
                # human labels are supplied to this function.
                from .conversion import convert_document
                # Keep historical source catalogs stable. A10 ablations belong
                # to candidate runs, not to implicit ground-truth migrations.
                convert_document(source, output_root=self.root/'tmp/converted',
                                 use_hierarchy=True,
                                 trace_root=self.root/'tmp/runs')
                self.catalog(document_id)
                status = {'status': 'ready'}
            except Exception as error:
                status = {'status': 'failed', 'error': f'Local conversion failed ({type(error).__name__}).'}
            with self.lock:
                self.jobs[document_id] = status
        self.pool.submit(convert)
        return {'status': 'preparing'}


def handler_for(workspace):
    """HTTP surface exposes only allowlisted sources and annotation endpoints."""
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, data, kind='application/json', extra=None):
            body = json.dumps(data).encode() if kind == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            try:
                route = urlsplit(self.path)
                doc_id = parse_qs(route.query).get('document', [''])[0]
                if route.path in ('/', '/annotation.html'):
                    return self.send(200, Path(__file__).with_name('annotation.html').read_bytes(), 'text/html; charset=utf-8')
                if route.path == '/api/documents':
                    return self.send(200, {'documents': workspace.documents,
                                          'taxonomy_version': TAXONOMY_VERSION,
                                          'topics': TOPIC_DEFINITIONS})
                if route.path == '/source-page':
                    page = int(parse_qs(route.query).get('page', ['0'])[0])
                    return self.send(200, workspace.render_page(doc_id, page), 'image/png')
                if route.path == '/source':
                    source = workspace.source(doc_id)
                    body = source.read_bytes()
                    if body[:2] == b'\x1f\x8b':
                        body = gzip.decompress(body)
                    kind = 'application/pdf' if source.suffix.lower() == '.pdf' else 'text/html; charset=utf-8'
                    return self.send(200, body, kind)
                if route.path in ('/api/document', '/api/export'):
                    document = workspace.catalog(doc_id)
                    if document is None:
                        return self.send(202, workspace.jobs.get(doc_id, {'status': 'not_prepared'}))
                    annotations = workspace.store.load(document)
                    if route.path == '/api/export':
                        return self.send(200, annotations, extra={'Content-Disposition': f'attachment; filename="gold-labels-{doc_id}.json"'})
                    return self.send(200, {'status': 'ready', 'document': document,
                                          'annotations': annotations['annotations']})
                self.send(404, {'error': 'Unknown route.'})
            except (ValueError, KeyError, OSError, subprocess.SubprocessError):
                self.send(400, {'error': 'Document or saved annotations could not be loaded.'})

        def do_POST(self):
            # A different website cannot use a user's browser to write reviews.
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                return self.send(403, {'error': 'Cross-origin annotation writes are blocked.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 32768:
                    raise ValueError('Invalid request size.')
                body = json.loads(self.rfile.read(length))
                if self.path == '/api/prepare':
                    return self.send(202, workspace.prepare(body['document_id']))
                if self.path != '/api/annotation':
                    return self.send(404, {'error': 'Unknown route.'})
                # Old browser tabs have not shown the new topic. Refuse their
                # saves rather than claiming the unseen category was reviewed.
                if body.get('taxonomy_version') != TAXONOMY_VERSION:
                    raise RevisionConflict('Topic list changed. Copy any unsaved notes, then reload before saving.')
                document = workspace.catalog(body['document_id'])
                if document is None or body['catalog_sha256'] != document['catalog_sha256']:
                    raise ValueError('Source catalog changed. Reload the document.')
                record = workspace.store.save(document, body['item_id'], body['topics'],
                                               revision=body['revision'], notes=body.get('notes', ''))
                self.send(200, {'annotation': record})
            except RevisionConflict as error:
                self.send(409, {'error': str(error)})
            except (ValueError, KeyError, TypeError):
                self.send(400, {'error': 'Invalid annotation or document request.'})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--port', type=int, default=60901)
    options = parser.parse_args()
    workspace = AnnotationWorkspace(options.root)
    server = ThreadingHTTPServer(('127.0.0.1', options.port), handler_for(workspace))
    print(f'Human annotation: http://localhost:{server.server_port}/', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        workspace.pool.shutdown(wait=False)


if __name__ == '__main__':
    main()
