"""Tests for the HTTP helper, against a local server."""

import gzip
import http.server
import threading

import pytest

from yavapy_harvester import shared

BODY = b"hello " * 100


class Handler(http.server.BaseHTTPRequestHandler):
    """Answer gzip when asked, and plain on /plain."""

    def do_GET(self):
        """Serve BODY, gzipped only when the client asks and the path allows."""
        if self.path == "/missing":
            self.send_error(404)
            return
        zipped = "gzip" in self.headers.get("Accept-Encoding", "") and self.path != "/plain"
        if self.path == "/zipped" and not zipped:
            self.send_error(406)
            return
        body = gzip.compress(BODY) if zipped else BODY
        self.send_response(200)
        if zipped:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        """Keep the test output quiet."""


@pytest.fixture
def server():
    """Run a local server for one test and return its base URL."""
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def test_gzipped_answer_is_unpacked(server):
    """A server that gzips gets asked to, and the body comes back plain."""
    assert shared.get(f"{server}/zipped") == BODY


def test_plain_answer_passes_through(server):
    """A server that ignores the request for gzip still works."""
    assert shared.get(f"{server}/plain") == BODY


def test_missing_page_is_none(server):
    """A 404 answers None."""
    assert shared.get(f"{server}/missing") is None
