import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from platform_lab.service import Metrics, Server


class MetricsTests(unittest.TestCase):
    def test_histogram_is_cumulative(self):
        metrics = Metrics()
        metrics.record(200, 40)
        metrics.record(500, 120)
        self.assertEqual(metrics.buckets, [0, 1, 1, 2, 2, 2, 2])
        self.assertEqual(metrics.errors, 1)
        self.assertIn('le="+Inf"} 2', metrics.render())

    def test_concurrent_updates_are_not_lost(self):
        metrics = Metrics()
        threads = [threading.Thread(target=lambda: [metrics.record(200, 1) for _ in range(100)])
                   for _ in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(metrics.requests, 800)
        self.assertEqual(metrics.buckets[-1], 800)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.flag = Path(self.temp.name) / "not-ready"
        self.server = Server(("127.0.0.1", 0), str(self.flag))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def get(self, path):
        try:
            response = urlopen(self.base + path, timeout=2)
        except HTTPError as exc:
            response = exc
        with response:
            return response.status, response.read().decode()

    def test_live_probe(self):
        self.assertEqual(self.get("/livez"), (200, '{"live": true}'))

    def test_readiness_tracks_flag_and_recovers(self):
        self.assertEqual(self.get("/readyz")[0], 200)
        self.flag.touch()
        self.assertEqual(self.get("/readyz")[0], 503)
        self.assertEqual(self.get("/livez")[0], 200)
        self.flag.unlink()
        self.assertEqual(self.get("/readyz")[0], 200)

    def test_synthetic_error_is_counted(self):
        self.assertEqual(self.get("/work?status=500")[0], 500)
        self.assertEqual(self.get("/work")[0], 200)
        body = self.get("/metrics")[1]
        self.assertIn("platform_work_requests_total 2", body)
        self.assertIn("platform_work_errors_total 1", body)

    def test_bounded_fault_parameters(self):
        for suffix in ["delay_ms=201", "delay_ms=-1", "delay_ms=hello", "status=302"]:
            with self.subTest(suffix=suffix):
                self.assertEqual(self.get("/work?" + suffix)[0], 400)

    def test_unknown_route_and_root(self):
        self.assertEqual(self.get("/missing")[0], 404)
        self.assertEqual(json.loads(self.get("/")[1])["version"], "1.0.0")


if __name__ == "__main__": unittest.main()
