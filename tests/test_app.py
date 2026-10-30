import os
import unittest
from unittest.mock import patch
from core import parse_prefill, build_url, form_url, pick_rows
from app import app, state

URL = 'https://docs.google.com/forms/d/e/example123/viewform'
PREFILL = URL + '?entry.123=First&entry.123=Second&entry.456=Hello%20world'


class CoreTests(unittest.TestCase):
    def test_multiselect_roundtrip(self):
        rows = parse_prefill(PREFILL, URL)
        self.assertEqual(rows[0]['answers'], ['First', 'Second'])
        self.assertEqual(parse_prefill(build_url(URL, rows), URL), rows)

    def test_rejects_ssrf_and_invalid_hosts(self):
        for url in ['http://localhost/', 'https://docs.google.com.evil.com/forms/d/e/x/viewform',
                    'https://docs.google.com@evil.com/forms/d/e/x/viewform',
                    'https://docs.google.com/forms/d/e/x/edit']:
            with self.assertRaises(ValueError):
                form_url(url)

    def test_random_rows_pick_one_and_vary(self):
        rows = [{'id': 'entry.1', 'mode': 'random', 'answers': ['a', 'b', 'c']}, {'id': 'entry.2', 'answers': ['x', 'y']}]
        picks = [pick_rows(rows) for _ in range(50)]
        self.assertTrue(all(len(p[0]['answers']) == 1 and p[1]['answers'] == ['x', 'y'] for p in picks))
        self.assertGreater(len({p[0]['answers'][0] for p in picks}), 1)

    def test_subset_rows_pick_one_to_three(self):
        rows = [{'id': 'entry.1', 'mode': 'subset', 'answers': ['a', 'b', 'c', 'd', 'e']}]
        sizes = {len(pick_rows(rows)[0]['answers']) for _ in range(100)}
        self.assertTrue(sizes <= {1, 2, 3} and len(sizes) > 1)

    def test_mismatched_forms(self):
        with self.assertRaises(ValueError):
            parse_prefill(PREFILL, URL.replace('example123', 'other'))

    def test_missing_entries(self):
        with self.assertRaises(ValueError):
            parse_prefill(URL, URL)

    def test_duplicate_id(self):
        rows = parse_prefill(PREFILL, URL)
        with self.assertRaises(ValueError):
            build_url(URL, [rows[0], rows[0]])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, APP_PASSWORD='correct-password-for-test')
        self.env.start()
        app.config['TESTING'] = True
        self.client = app.test_client()
        state.update(status='idle', completed=0, total=0, logs=[])

    def tearDown(self):
        self.env.stop()

    def login(self):
        self.client.post('/login', json={'password': 'correct-password-for-test'})
        with self.client.session_transaction() as s:
            return {'X-CSRF-Token': s['csrf']}

    def payload(self):
        return dict(url=URL, prefill=PREFILL, rows=parse_prefill(PREFILL, URL),
                    count=1, owned=True, mode='preview', confirmation='Your response has been recorded.')

    def test_login_and_auth(self):
        self.assertEqual(self.client.get('/api/status').status_code, 401)
        self.assertEqual(self.client.post('/login', json={'password': 'wrong'}).status_code, 401)
        self.login()
        self.assertEqual(self.client.get('/api/status').status_code, 200)

    def test_csrf(self):
        self.login()
        self.assertEqual(self.client.post('/api/cancel', json={}).status_code, 403)

    @patch('app.fetch_questions', return_value={'entry.123': {'label': '1. Q', 'type': 4, 'options': ['First', 'Second', 'Third']}})
    def test_import(self, _fetch):
        h = self.login()
        r = self.client.post('/api/import', headers=h, json={'url': URL, 'prefill': PREFILL})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json['rows']), 2)
        self.assertEqual(r.json['rows'][0]['options'], ['First', 'Second', 'Third'])

    def test_invalid_counts_and_owner(self):
        h = self.login()
        for key, value in [('count', 0), ('count', 101), ('count', True), ('owned', False), ('mode', 'bad')]:
            d = self.payload(); d[key] = value
            self.assertEqual(self.client.post('/api/start', headers=h, json=d).status_code, 400)

    def test_job_starts_and_rejects_overlap(self):
        h = self.login()
        with patch('app.threading.Thread') as thread:
            self.assertEqual(self.client.post('/api/start', headers=h, json=self.payload()).status_code, 200)
            thread.return_value.start.assert_called_once()
            self.assertEqual(self.client.post('/api/start', headers=h, json=self.payload()).status_code, 409)
        self.assertEqual(self.client.post('/api/cancel', headers=h, json={}).status_code, 200)

    def test_home_and_export(self):
        self.login()
        self.assertIn(b'FormDesk', self.client.get('/').data)
        self.assertTrue(self.client.get('/api/session').json['signed_in'])
        self.assertIn(b'UTC time,Event', self.client.get('/api/log.csv').data)


if __name__ == '__main__':
    unittest.main()
