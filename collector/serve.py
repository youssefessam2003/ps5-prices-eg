"""Private localhost companion: phone requests a full fresh collection over ADB.

No arbitrary commands, filesystem browsing, or public network listener. A build-
specific bearer token is required for every API and data request.
"""
import argparse
import hmac
import json
import re
import shutil
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from collect import ROOT, collection_lock, now, write_json


class Jobs:
    def __init__(self, root=ROOT, runner=subprocess.run, recover=True):
        self.root = Path(root)
        self.folder = self.root / 'logs' / 'refresh-jobs'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.runner = runner
        self.lock = threading.Lock()
        self.active = None
        # A restarted service must not claim that an interrupted job is running.
        for path in self.folder.glob('*/job.json') if recover else []:
            job = json.loads(path.read_text(encoding='utf-8'))
            if job.get('status') == 'running':
                job.update(status='failed', error='The price service restarted. Please retry the price check.')
                write_json(path, job)

    def get(self, job_id):
        if not re.fullmatch(r'[a-f0-9]{32}', job_id or ''):
            return None
        path = self.folder / job_id / 'job.json'
        if not path.exists():
            return None
        job = json.loads(path.read_text(encoding='utf-8'))
        progress = path.with_name('progress.json')
        if job['status'] == 'running' and progress.exists():
            details = json.loads(progress.read_text(encoding='utf-8'))
            job.update({k: details.get(k) for k in ('completed', 'total', 'current_source')})
        return job

    def start(self):
        with self.lock:
            if self.active:
                current = self.get(self.active)
                if current and current['status'] == 'running':
                    return current
            job_id = uuid.uuid4().hex
            folder = self.folder / job_id
            folder.mkdir()
            job = {'id': job_id, 'status': 'running', 'completed': 0,
                   'current_source': None, 'started_at': now().isoformat(timespec='seconds')}
            # Count the configured automatic sources, never hardcode app coverage.
            from sources import SOURCES
            job['total'] = sum(s['kind'] != 'manual' for s in SOURCES)
            write_json(folder / 'job.json', job)
            self.active = job_id
            threading.Thread(target=self._run, args=(job,), daemon=True).start()
            return dict(job)

    def resume(self, job_id):
        """Maintenance recovery of this job's verified checkpoints, not old prices."""
        job = self.get(job_id)
        if not job or job['status'] != 'failed':
            raise RuntimeError('Only a failed job with fresh checkpoints can be resumed')
        job.update(status='running', resumed_at=now().isoformat(timespec='seconds'))
        job.pop('error', None)
        job.pop('finished_at', None)
        write_json(self.folder / job_id / 'job.json', job)
        self.active = job_id
        self._run(job, resume=True)

    def _run(self, job, resume=False):
        folder = self.folder / job['id']
        candidate = folder / 'data'
        try:
            # Preserve past daily history and previously discovered URLs. --fresh
            # discards every old price/availability observation for today's run.
            if not resume:
                shutil.copytree(self.root / 'data' / 'snapshots', candidate / 'snapshots')
            command = [sys.executable, str(self.root / 'collector' / 'collect.py'),
                       '--headed', '--data-dir', str(candidate),
                       '--progress-file', str(folder / 'progress.json')]
            if resume:
                from sources import SOURCES
                day = now().date().isoformat()
                saved = json.loads((candidate / 'snapshots' / (day + '.json')).read_text(encoding='utf-8'))
                automatic = {s['id'] for s in SOURCES if s['kind'] != 'manual'}
                if not set(saved['sources']).issubset(automatic):
                    raise RuntimeError('Checkpoint contains sources outside this collection')
                observations = [s.get('fetched_at', '') for s in saved['sources'].values()]
                observations.extend(i.get('seen_at', '') for i in saved['listings'])
                if not observations or any(t < job['started_at'] for t in observations):
                    raise RuntimeError('Checkpoint is not from this fresh job; start a new check instead')
                remaining = [s['id'] for s in SOURCES if s['kind'] != 'manual' and s['id'] not in saved['sources']]
                if remaining:
                    command.extend(['--only', *remaining, '--progress-offset', str(len(saved['sources'])),
                                    '--progress-total', str(job['total'])])
                else:
                    command.append('--build-only')
            else:
                command.append('--fresh')
            with (folder / 'collector.log').open('a' if resume else 'w', encoding='utf-8') as log:
                result = self.runner(command, cwd=self.root, stdout=log, stderr=subprocess.STDOUT,
                                     timeout=3600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                raise RuntimeError('The price check could not finish. Previous prices are still available; retry the check.')
            latest = json.loads((candidate / 'latest.json').read_text(encoding='utf-8'))
            history = json.loads((candidate / 'history.json').read_text(encoding='utf-8'))
            statuses = latest['sources']
            succeeded = sum(s['status'] == 'ok' for s in statuses.values())
            if not succeeded or not latest['listings']:
                raise RuntimeError('No fresh console prices could be verified. Previous prices are still available.')
            with collection_lock(self.root):
                snap_name = latest['date'] + '.json'
                snapshot = json.loads((candidate / 'snapshots' / snap_name).read_text(encoding='utf-8'))
                # Publish latest last; clients see the last complete result during
                # collection and receive both files under the publication lock.
                with self.lock:
                    for dest, value in [
                        (self.root / 'data' / 'snapshots' / snap_name, snapshot),
                        (self.root / 'data' / 'history.json', history),
                        (self.root / 'app' / 'assets' / 'data' / 'history.json', history),
                        (self.root / 'app' / 'assets' / 'data' / 'latest.json', latest),
                        (self.root / 'data' / 'latest.json', latest),
                    ]:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        options = {'separators': (',', ':')} if dest.name == 'history.json' else {'indent': 1}
                        write_json(dest, value, **options)
            job.update(status='completed', completed=job['total'], current_source=None,
                       offers=len(latest['listings']), in_stock=sum(i['in_stock'] for i in latest['listings']),
                       succeeded=succeeded, failed=len(statuses) - succeeded,
                       generated_at=latest['generated_at'])
        except Exception as e:
            job.update(status='failed', error=str(e) if isinstance(e, RuntimeError) else
                       'The price check was interrupted. Previous prices are still available; please retry.')
        finally:
            job['finished_at'] = now().isoformat(timespec='seconds')
            write_json(folder / 'job.json', job)


def handler(jobs, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def authorized(self):
            supplied = self.headers.get('Authorization', '')
            if not hmac.compare_digest(supplied.encode(), ('Bearer ' + token).encode()):
                self.send_json({'error': 'Unauthorized'}, 401)
                return False
            return True

        def send_json(self, value, status=200):
            body = json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if not self.authorized():
                return
            if urlsplit(self.path).path != '/api/refresh':
                self.send_json({'error': 'Not found'}, 404)
                return
            # This endpoint accepts no source IDs, commands, URLs or other inputs.
            if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Length', '0') != '0':
                self.send_json({'error': 'This request must have an empty body'}, 400)
                return
            self.send_json(jobs.start(), 202)

        def do_GET(self):
            if not self.authorized():
                return
            path = urlsplit(self.path).path
            if path == '/api/health':
                self.send_json({'status': 'ok'})
            elif path == '/api/snapshot':
                with jobs.lock:
                    self.send_json({name: json.loads((jobs.root / 'data' / (name + '.json')).read_text(encoding='utf-8'))
                                    for name in ('latest', 'history')})
            elif path == '/api/jobs/active':
                self.send_json(jobs.get(jobs.active) if jobs.active else None)
            elif path.startswith('/api/jobs/'):
                job = jobs.get(path.rsplit('/', 1)[-1])
                self.send_json(job if job else {'error': 'Not found'}, 200 if job else 404)
            elif path in ('/data/latest.json', '/data/history.json'):
                with jobs.lock:
                    file = jobs.root / 'data' / path.rsplit('/', 1)[-1]
                    self.send_json(json.loads(file.read_text(encoding='utf-8')))
            else:
                self.send_json({'error': 'Not found'}, 404)

    return Handler


def maintain_bridge(device, port):
    """Restore the mapping if this already-authorized ADB connection reconnects."""
    while True:
        try:
            subprocess.run(['adb', '-s', device, 'reverse', f'tcp:{port}', f'tcp:{port}'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except (OSError, subprocess.TimeoutExpired):
            pass
        threading.Event().wait(20)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True, help='Private --dart-define-from-file JSON shared with this APK')
    parser.add_argument('--device', help='Already-connected adb serial for automatic reverse-port mapping')
    parser.add_argument('--resume-job', help='Recover only this failed job from its verified fresh checkpoints, then exit')
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    url = urlsplit(config['COLLECTOR_URL'])
    if url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port:
        parser.error('This companion only listens on http://127.0.0.1:<port>')
    token = config['COLLECTOR_TOKEN']
    if not isinstance(token, str) or len(token) < 32:
        parser.error('A random token of at least 32 characters is required')
    if args.resume_job:
        Jobs(recover=False).resume(args.resume_job)
        return
    server = ThreadingHTTPServer(('127.0.0.1', url.port), handler(Jobs(), token))
    if args.device:
        threading.Thread(target=maintain_bridge, args=(args.device, url.port), daemon=True).start()
    print(f'Price companion ready on localhost:{url.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
