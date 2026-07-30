"""Minimal loopback LM Studio-compatible provider reporting no models."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = "127.0.0.1"
PORT = 18764


class EmptyProviderHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in {"/v1/models", "/api/v0/models"}:
            payload = json.dumps({"object": "list", "data": []}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_error(404)

    def log_message(self, _format: str, *_args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), EmptyProviderHandler).serve_forever()
