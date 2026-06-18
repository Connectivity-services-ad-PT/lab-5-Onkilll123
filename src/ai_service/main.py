"""
FIT4110 Lab 05 — AI Service mock for team-gate
Provides /health and /predict endpoints (dummy risk assessment).
"""
import json
import random
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 9000

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress access log

    def send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "ok", "service": "gate-ai-mock", "version": "0.5.0"})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/predict":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            card_id = body.get("card_id", "")
            # Simple mock: expired cards → high risk
            if "EXPIRED" in card_id.upper():
                risk = "high"
            else:
                risk = random.choice(["low", "low", "low", "medium"])
            self.send_json(200, {
                "card_id": card_id,
                "risk_level": risk,
                "model": "gate-risk-mock-v1",
                "confidence": round(random.uniform(0.75, 0.99), 2),
            })
        else:
            self.send_json(404, {"error": "not found"})

if __name__ == "__main__":
    print(f"[AI Service] Starting on port {PORT}...")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()