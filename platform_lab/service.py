"""Dependency-free HTTP service with probes, metrics, and bounded fault injection."""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
from pathlib import Path
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

LOG = logging.getLogger("platform_lab")
BUCKETS = (10, 50, 100, 250, 500, 1000, math.inf)


class Metrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.started = time.monotonic()
        self.requests = 0
        self.errors = 0
        self.duration_sum = 0.0
        self.buckets = [0] * len(BUCKETS)

    def record(self, status: int, milliseconds: float):
        with self.lock:
            self.requests += 1
            self.errors += int(status >= 500)
            self.duration_sum += milliseconds
            for i, bound in enumerate(BUCKETS):
                self.buckets[i] += int(milliseconds <= bound)

    def render(self) -> str:
        with self.lock:
            lines = ["# TYPE platform_work_requests_total counter",
                     f"platform_work_requests_total {self.requests}",
                     "# TYPE platform_work_errors_total counter",
                     f"platform_work_errors_total {self.errors}",
                     "# TYPE platform_work_duration_milliseconds histogram"]
            for bound, count in zip(BUCKETS, self.buckets):
                label = "+Inf" if math.isinf(bound) else str(bound)
                lines.append(f'platform_work_duration_milliseconds_bucket{{le="{label}"}} {count}')
            lines += [f"platform_work_duration_milliseconds_sum {self.duration_sum:.6f}",
                      f"platform_work_duration_milliseconds_count {self.requests}",
                      "# TYPE platform_uptime_seconds gauge",
                      f"platform_uptime_seconds {time.monotonic() - self.started:.3f}"]
            return "\n".join(lines) + "\n"


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, not_ready_file: str = "/tmp/platform-not-ready"):
        super().__init__(address, Handler)
        self.metrics = Metrics()
        self.not_ready_file = Path(not_ready_file)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status: int, body, content_type="application/json"):
        data = (json.dumps(body).encode() if isinstance(body, dict) else body.encode())
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        route = urlsplit(self.path)
        if route.path == "/livez":
            return self.reply(200, {"live": True})
        if route.path == "/readyz":
            ready = not self.server.not_ready_file.exists()
            return self.reply(200 if ready else 503, {"ready": ready})
        if route.path == "/metrics":
            return self.reply(200, self.server.metrics.render(), "text/plain; version=0.0.4")
        if route.path == "/":
            return self.reply(200, {"service": "cloud-platform-lab", "version": "1.0.0",
                                    "routes": ["/livez", "/readyz", "/metrics", "/work"]})
        if route.path != "/work":
            return self.reply(404, {"error": "not found"})
        started = time.perf_counter()
        status = 200
        try:
            query = parse_qs(route.query)
            delay = int(query.get("delay_ms", ["0"])[0])
            status = int(query.get("status", ["200"])[0])
            if not 0 <= delay <= 200 or status not in (200, 500):
                raise ValueError("delay_ms must be 0..200 and status must be 200 or 500")
            time.sleep(delay / 1000)
            self.reply(status, {"ok": status == 200, "synthetic": True})
        except ValueError as exc:
            status = 400
            self.reply(status, {"error": str(exc)})
        finally:
            duration = (time.perf_counter() - started) * 1000
            self.server.metrics.record(status, duration)
            LOG.info(json.dumps({"event": "request", "route": "/work", "status": status,
                                 "duration_ms": round(duration, 3)}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    server = Server((args.host, args.port), os.getenv("NOT_READY_FILE", "/tmp/platform-not-ready"))
    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
