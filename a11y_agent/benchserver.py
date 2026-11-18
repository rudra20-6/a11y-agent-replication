"""Serve bench/app on localhost in a background thread."""

import functools
import http.server
import socket
import threading

from .config import BENCH


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        """A static copy has no server code: a form POST gets the page it targets, not a 501 (the W3C demo's forms,
        D70). Server-side behaviour (validation messages) is therefore missing from local copies."""
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.do_GET()


class _Server(http.server.ThreadingHTTPServer):
    # The default backlog is 5: six browser sessions loading an image-heavy page at once (the W3C demo) overflowed it
    # and Windows refused connections, so two persona agents never started (30 Oct, D70).
    request_queue_size = 128
    daemon_threads = True


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(port: int | None = None, directory=None) -> tuple[str, http.server.ThreadingHTTPServer]:
    port = port or free_port()
    handler = functools.partial(_Quiet, directory=str(directory or BENCH / "app"))
    httpd = _Server(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}/", httpd
