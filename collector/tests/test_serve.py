"""Integration checks for authenticated fresh jobs and safe result publication."""
import json
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from serve import Jobs, handler


class LiveCollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'data' / 'snapshots').mkdir(parents=True)
        self.old = {'date': '2026-11-15', 'generated_at': '2026-11-15T10:00:00+02:00',
                    'listings': [{'id': 'old'}], 'sources': {}}
        for file, value in [('latest.json', self.old), ('history.json', {'days': [], 'listings': {}})]:
            (self.root / 'data' / file).write_text(json.dumps(value), encoding='utf-8')
        (self.root / 'data' / 'snapshots' / '2026-11-15.json').write_text(json.dumps(self.old), encoding='utf-8')
        self.release = threading.Event()
        self.calls = []
        self.code = 0

        def runner(command, **kwargs):
            self.calls.append(command)
            self.release.wait(5)
            folder = Path(command[command.index('--data-dir') + 1])
            latest = {**self.old, 'generated_at': '2026-11-15T14:00:00+02:00',
                      'listings': [{'id': 'new', 'in_stock': True}],
                      'sources': {'new': {'status': 'ok'}, 'blocked': {'status': 'error'}}}
            for path, value in [(folder / 'latest.json', latest),
                                (folder / 'history.json', {'days': [], 'listings': {}}),
                                (folder / 'snapshots' / '2026-11-15.json', latest)]:
                path.write_text(json.dumps(value), encoding='utf-8')
            return SimpleNamespace(returncode=self.code)

        self.jobs = Jobs(self.root, runner)
        self.token = 'test-only-random-token-not-a-live-credential'
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.jobs, self.token))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.release.set()
        if self.jobs.active:
            self.finished(self.jobs.active)
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def request(self, path, method='GET', token=None, body=None):
        req = Request(self.base + path, method=method, data=body,
                      headers={'Authorization': 'Bearer ' + (self.token if token is None else token)})
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as e:
            return e.code, json.load(e)

    def finished(self, job_id):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            job = self.jobs.get(job_id)
            if job['status'] != 'running':
                return job
            time.sleep(.01)
        self.fail('Worker did not finish')

    def test_authentication_and_no_path_or_command_inputs(self):
        self.assertEqual(self.request('/api/refresh', 'POST', token='wrong')[0], 401)
        self.assertEqual(self.request('/api/snapshot', token='wrong')[0], 401)
        self.assertEqual(self.request('/data/../../README.md')[0], 404)
        self.assertEqual(self.request('/api/refresh', 'POST', body=b'{"command":"anything"}')[0], 400)
        self.assertIsNone(self.jobs.active)

    def test_duplicate_requests_join_one_real_fresh_job_and_publish_only_when_done(self):
        _, first = self.request('/api/refresh', 'POST')
        _, second = self.request('/api/refresh', 'POST')
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(self.request('/api/snapshot')[1]['latest'], self.old)
        self.release.set()
        done = self.finished(first['id'])
        self.assertEqual(done['status'], 'completed')
        self.assertEqual((done['succeeded'], done['failed'], done['offers']), (1, 1, 1))
        self.assertEqual(len(self.calls), 1)
        self.assertIn('--fresh', self.calls[0])
        snapshot = self.request('/api/snapshot')[1]
        self.assertEqual(snapshot['latest']['listings'], [{'id': 'new', 'in_stock': True}])
        self.assertEqual(json.loads((self.root / 'app/assets/data/latest.json').read_text()), snapshot['latest'])

    def test_failed_collection_keeps_previous_prices_and_allows_retry(self):
        self.code = 1
        _, job = self.request('/api/refresh', 'POST')
        self.release.set()
        self.assertEqual(self.finished(job['id'])['status'], 'failed')
        self.assertEqual(self.request('/api/snapshot')[1]['latest'], self.old)
        _, retry = self.request('/api/refresh', 'POST')
        self.assertNotEqual(retry['id'], job['id'])

    def test_maintenance_recovery_cannot_publish_unverified_old_checkpoints(self):
        self.code = 1
        _, job = self.request('/api/refresh', 'POST')
        self.release.set()
        self.assertEqual(self.finished(job['id'])['status'], 'failed')
        self.jobs.resume(job['id'])
        self.assertEqual(self.jobs.get(job['id'])['status'], 'failed')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.request('/api/snapshot')[1]['latest'], self.old)


if __name__ == '__main__':
    unittest.main()
