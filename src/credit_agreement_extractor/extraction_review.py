"""Offline extraction-reference review, deliberately outside model execution.

Run: uv run --no-sync python -m credit_agreement_extractor.extraction_review
The immutable AI draft and original source files are read-only. Only this app's
separate evaluation database is written. No pipeline/provider modules are used.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
from urllib.parse import parse_qs, urlsplit


class Conflict(ValueError):
    """A stale tab or changed source must never overwrite a newer decision."""


def encode(value):
    # Reject NaN/Infinity: these aren't portable JSON reference values.
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


class ReviewWorkspace:
    def __init__(self, root, draft_path):
        self.root = Path(root).resolve()
        self.draft_path = Path(draft_path).resolve()
        raw = self.draft_path.read_bytes()
        self.draft_sha256 = hashlib.sha256(raw).hexdigest()
        self.draft = json.loads(raw)
        if self.draft.get('schema_version') != 'extraction-reference-draft-v1':
            raise ValueError('Unsupported extraction draft format.')
        golden = json.loads((self.root / 'evaluations/golden_documents.json').read_text())
        allowed = {d['id']: d['path'] for d in golden['documents']}
        self.documents, self.facts, self.sources = {}, {}, {}
        for doc in self.draft['documents']:
            doc_id = doc['document_id']
            if doc_id in self.documents or doc.get('source_path') != allowed.get(doc_id):
                raise ValueError('Draft must reference unique approved golden sources.')
            source = (self.root / doc['source_path']).resolve()
            if not source.is_relative_to(self.root / 'raw_documents') or not source.is_file():
                raise ValueError('Invalid source path.')
            if hashlib.sha256(source.read_bytes()).hexdigest() != doc['source_sha256']:
                raise ValueError('Source fingerprint changed; review cannot proceed.')
            self.documents[doc_id], self.sources[doc_id] = doc, source
            for fact in doc['facts']:
                if fact['fact_id'] in self.facts:
                    raise ValueError('Duplicate draft fact ID.')
                self.facts[fact['fact_id']] = (doc_id, fact)
        self.token = secrets.token_urlsafe(32)
        store = self.root / 'evaluations/ground_truth/extraction_reviews'
        if store.is_symlink():
            raise ValueError('Review store may not be a symlink.')
        store.mkdir(parents=True, exist_ok=True)
        self.db = store / f'{self.draft_sha256}.sqlite3'
        if self.db.is_symlink():
            raise ValueError('Review database may not be a symlink.')
        # One immutable row per revision. A transaction serializes competing
        # tabs/processes, and FULL synchronous commits provide durable saves.
        with self.connect() as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS decisions (fact_id TEXT, revision INTEGER, payload TEXT NOT NULL, PRIMARY KEY(fact_id, revision))')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db, timeout=10)
        connection.execute('PRAGMA synchronous=FULL')
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def check_draft(self):
        if hashlib.sha256(self.draft_path.read_bytes()).hexdigest() != self.draft_sha256:
            raise Conflict('Draft changed. Preserve unsaved edits and restart with the new draft.')

    def state(self):
        self.check_draft()
        with self.connect() as connection:
            rows = connection.execute('SELECT payload FROM decisions d WHERE revision=(SELECT MAX(revision) FROM decisions WHERE fact_id=d.fact_id)').fetchall()
        return {'draft': self.draft, 'draft_sha256': self.draft_sha256,
                'decisions': {r['fact_id']: r for row in rows for r in [json.loads(row[0])]},
                'scoring_eligible': False, 'purpose': 'human_reference_review_only'}

    def history(self, fact_id):
        with self.connect() as connection:
            return [json.loads(row[0]) for row in connection.execute('SELECT payload FROM decisions WHERE fact_id=? ORDER BY revision', (fact_id,))]

    def save(self, body):
        self.check_draft()
        if not isinstance(body, dict) or body.get('draft_sha256') != self.draft_sha256:
            raise ValueError('Wrong draft fingerprint.')
        doc_id, fact_id = body.get('document_id'), body.get('fact_id')
        if doc_id not in self.documents or not isinstance(fact_id, str):
            raise ValueError('Unknown document or fact.')
        self.source(doc_id)  # Bind each saved decision to unchanged source bytes.
        revision, decision = body.get('revision'), body.get('decision')
        if type(revision) is not int or revision < 0:
            raise ValueError('Expected a nonnegative integer revision.')
        if decision not in ('approved', 'edited', 'rejected', 'skipped'):
            raise ValueError('Choose approve, edit, reject or skip.')
        notes = body.get('notes', '')
        if not isinstance(notes, str) or len(notes) > 12000:
            raise ValueError('Notes must be text, at most 12,000 characters.')
        is_added = fact_id not in self.facts
        if not is_added:
            owner, fact = self.facts[fact_id]
            if owner != doc_id:
                raise ValueError('Fact belongs to another document.')
            field, evidence = fact['field'], fact['evidence']
            value = body['value'] if decision == 'edited' else fact['proposed_value']
            value_status = ('unresolved' if value is None else 'proposed_supported') if decision == 'edited' else fact.get('value_status', 'proposed_supported')
        else:
            # Browser-generated stable ID lets retries hit the revision check
            # rather than creating duplicate manual facts after a lost response.
            if not re.fullmatch(r'manual-[a-zA-Z0-9-]{1,80}', fact_id):
                raise ValueError('Unknown draft fact ID.')
            field, evidence, value = body.get('field'), body.get('evidence'), body.get('value')
            if not isinstance(field, str) or not field.strip() or len(field) > 300:
                raise ValueError('Provide a field name for the added fact.')
            if not isinstance(evidence, list) or not 1 <= len(evidence) <= 20:
                raise ValueError('Added facts need source evidence.')
            for ev in evidence:
                if not isinstance(ev, dict) or not isinstance(ev.get('source_text'), str) or not ev['source_text'].strip():
                    raise ValueError('Provide a source quote for the added fact.')
                pages = ev.get('pdf_pages', [])
                if not isinstance(pages, list) or any(type(p) is not int or not 1 <= p <= 10000 for p in pages):
                    raise ValueError('PDF pages must be positive integers.')
                if self.sources[doc_id].suffix.lower() == '.pdf' and not pages:
                    raise ValueError('Provide a PDF page for the source quote.')
                if self.sources[doc_id].suffix.lower() != '.pdf' and pages:
                    raise ValueError('HTML sources do not have PDF page numbers.')
                if self.sources[doc_id].suffix.lower() != '.pdf' and not ev.get('item_id'):
                    raise ValueError('Provide an HTML item/section locator.')
            value_status = 'unresolved' if value is None else 'proposed_supported'
        # Validate JSON before acquiring the write transaction.
        encode(value); encode(evidence)
        record = {'document_id': doc_id, 'fact_id': fact_id, 'field': field,
                  'decision': decision, 'value': value, 'value_status': value_status,
                  'notes': notes, 'evidence': evidence, 'is_added': is_added,
                  'draft_sha256': self.draft_sha256,
                  'source_sha256': self.documents[doc_id]['source_sha256'],
                  'reviewer': 'local_human', 'revision': revision + 1,
                  'updated_at': datetime.now(timezone.utc).isoformat(),
                  'approved_for_reference': decision in ('approved', 'edited'),
                  'evidence_validation': 'human_asserted' if is_added else 'draft_evidence_retained'}
        with self.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            previous = connection.execute('SELECT revision, payload FROM decisions WHERE fact_id=? ORDER BY revision DESC LIMIT 1', (fact_id,)).fetchone()
            if (previous[0] if previous else 0) != revision:
                raise Conflict('A newer review exists. Your unsaved text is still here; copy it before reloading.')
            if previous and json.loads(previous[1])['document_id'] != doc_id:
                raise ValueError('Manual fact belongs to another document.')
            connection.execute('INSERT INTO decisions VALUES (?, ?, ?)', (fact_id, revision + 1, encode(record)))
        return record

    def source(self, document_id):
        if document_id not in self.sources:
            raise ValueError('Unknown golden document.')
        source = self.sources[document_id]
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != self.documents[document_id]['source_sha256']:
            raise Conflict('Source changed; refusing to show mismatched evidence.')
        return source, raw


def handler_for(workspace):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, data, kind='application/json', extra=None):
            raw = encode(data).encode() if kind == 'application/json' else data
            self.send_response(status)
            for key, value in {'Content-Type': kind, 'Content-Length': str(len(raw)),
                               'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                               **(extra or {})}.items():
                self.send_header(key, value)
            self.end_headers(); self.wfile.write(raw)

        def valid_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, {'error': 'Local host required.'})
            try:
                url = urlsplit(self.path); query = parse_qs(url.query)
                if url.path == '/':
                    return self.send(200, Path(__file__).with_suffix('.html').read_bytes(), 'text/html; charset=utf-8')
                if url.path == '/api/state':
                    return self.send(200, {**workspace.state(), 'token': workspace.token})
                if url.path == '/api/export':
                    return self.send(200, workspace.state(), extra={'Content-Disposition': 'attachment; filename="extraction-review-decisions.json"'})
                if url.path == '/api/history':
                    return self.send(200, workspace.history(query.get('fact', [''])[0]))
                if url.path in ('/source', '/source-page'):
                    source, raw = workspace.source(query.get('document', [''])[0])
                    pdf = source.suffix.lower() == '.pdf'
                    if url.path == '/source-page':
                        page = int(query.get('page', ['0'])[0])
                        if not pdf or not 1 <= page <= 10000:
                            raise ValueError('Invalid PDF page.')
                        result = subprocess.run(['pdftoppm', '-f', str(page), '-l', str(page), '-singlefile', '-scale-to', '1600', '-png', str(source)], capture_output=True, timeout=30, check=True)
                        return self.send(200, result.stdout, 'image/png')
                    if raw[:2] == b'\x1f\x8b': raw = gzip.decompress(raw)
                    return self.send(200, raw, 'application/pdf' if pdf else 'text/html; charset=utf-8',
                                     extra={} if pdf else {'Content-Security-Policy': "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:"})
                return self.send(404, {'error': 'Unknown route.'})
            except Conflict as error:
                self.send(409, {'error': str(error)})
            except (ValueError, KeyError, OSError, subprocess.SubprocessError):
                self.send(400, {'error': 'Unable to load the requested source or review.'})

        def do_POST(self):
            origin = f"http://{self.headers.get('Host')}"
            if (not self.valid_host() or self.headers.get('Origin') != origin
                    or not secrets.compare_digest(self.headers.get('X-Review-Token', ''), workspace.token)):
                return self.send(403, {'error': 'Same-origin review token required. Reload this app if it restarted.'})
            if self.path != '/api/review':
                return self.send(404, {'error': 'Unknown route.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 250000:
                    raise ValueError('Invalid review size.')
                body = json.loads(self.rfile.read(length))
                return self.send(200, {'review': workspace.save(body)})
            except Conflict as error:
                self.send(409, {'error': str(error)})
            except (ValueError, KeyError, TypeError) as error:
                self.send(400, {'error': str(error)})
            except (OSError, sqlite3.Error):
                self.send(500, {'error': 'Save failed. Keep your edits here and retry; do not navigate away.'})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--draft', type=Path, default=Path('evaluations/ground_truth/extraction_drafts/2026-10-04/reference.draft.json'))
    parser.add_argument('--port', type=int, default=60902)
    args = parser.parse_args()
    draft = args.draft if args.draft.is_absolute() else args.root / args.draft
    workspace = ReviewWorkspace(args.root, draft)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(workspace))
    print(f'Extraction reference review: http://127.0.0.1:{server.server_port}/', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
