from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


class CacheHeadersTest(unittest.TestCase):
    def test_shell_routes_send_no_cache_headers(self) -> None:
        from app import main as app_main

        with patch('app.main.load_loop_state'):
            with TestClient(app_main.app) as client:
                root = client.get('/')
                script = client.get('/static/js/core/app.js')
                stylesheet = client.get('/static/css/base.css')
                worker = client.get('/sw.js')

        for response in (root, script, stylesheet):
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers.get('Cache-Control'), 'no-cache, no-store, must-revalidate')
            self.assertEqual(response.headers.get('Pragma'), 'no-cache')
            self.assertEqual(response.headers.get('Expires'), '0')

        self.assertEqual(worker.status_code, 200)
        self.assertEqual(worker.headers.get('Cache-Control'), 'no-store')


if __name__ == '__main__':
    unittest.main()
