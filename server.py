"""
AI Health Symptom Assessment Agent — Local Proxy Server
Serves index.html and proxies IBM WatsonX API calls to avoid CORS restrictions.
Run: python server.py
Then open: http://localhost:8080
"""

import http.server
import urllib.request
import urllib.error
import json
import os

PORT = 8080
DIR  = os.path.dirname(os.path.abspath(__file__))

CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


class ProxyHandler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    # ── silence request logs for cleaner output ──
    def log_message(self, fmt, *args):
        status = args[1] if len(args) > 1 else "?"
        print(f"  {self.command:6s} {self.path[:80]:80s}  [{status}]")

    # ── CORS pre-flight ──
    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()

    # ── Proxy: IBM IAM token ──
    def do_POST(self):
        if self.path.startswith("/proxy/iam"):
            self._proxy_post(
                "https://iam.cloud.ibm.com/identity/token",
                content_type="application/x-www-form-urlencoded",
            )
        elif self.path.startswith("/proxy/watsonx"):
            # Extract Authorization header forwarded from the browser request
            auth = self.headers.get("Authorization", "")
            self._proxy_post(
                "https://us-south.ml.cloud.ibm.com/ml/v1/text/chat?version=2024-05-31",
                content_type="application/json",
                extra_headers={"Authorization": auth, "Accept": "application/json"},
            )
        else:
            self.send_error(404)

    def _proxy_post(self, target_url, content_type, extra_headers=None):
        length  = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(length) if length else b""

        req_headers = {"Content-Type": content_type}
        if extra_headers:
            req_headers.update(extra_headers)

        req = urllib.request.Request(
            target_url, data=payload, headers=req_headers, method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body   = resp.read()
                status = resp.status
        except urllib.error.HTTPError as e:
            body   = e.read()
            status = e.code
        except Exception as e:
            self.send_response(502)
            for k, v in CORS_HEADERS.items():
                self.send_header(k, v)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("=" * 60)
    print("  AI Health Symptom Assessment Agent")
    print(f"  Server running at http://localhost:{PORT}")
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    with http.server.ThreadingHTTPServer(("", PORT), ProxyHandler) as httpd:
        httpd.serve_forever()
