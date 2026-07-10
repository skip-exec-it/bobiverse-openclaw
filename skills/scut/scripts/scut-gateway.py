#!/usr/bin/env python3
"""
scut-gateway.py — SCUT Gateway Autoresponder (runs on TKD01SVR only)

The SCUT gateway (rsyslog relay) is otherwise invisible: a sender fires a UDP
syslog packet and gets no feedback. This adds a small, reliable TCP responder so
any bob can confirm the gateway is actually up and relaying — and it surfaces the
central relay log the gateway already keeps.

Endpoints:
  GET /health     Gateway status: rsyslog active, webhook present, relay counts
  GET /ping       {"status":"pong","role":"scut-gateway"}
  GET /log?n=50   Last n lines of the relay log (default 50, max 500)

Health JSON:
  {
    "role": "scut-gateway", "status": "up", "host": "<hostname>",
    "rsyslog": "active|inactive|unknown",
    "webhook": "present|missing",
    "relays_total": <int>, "relays_last_hour": <int>,
    "errors_last_hour": <int>, "last_relay": "<iso ts or line>"
  }

Run as a systemd service (see SKILL.md → Deployment). Listens on :8515 by default.

Env:
  SCUT_GATEWAY_PORT     default 8515
  SCUT_LOG              default /var/log/scut.log
  SCUT_WEBHOOK_LOG      default /var/log/scut-webhook.log
  SCUT_ERROR_LOG        default /var/log/scut-errors.log
  SCUT_WEBHOOK_BIN      default /usr/local/bin/scut-webhook.sh
"""

import http.server
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PORT = int(os.environ.get("SCUT_GATEWAY_PORT", "8515"))
SCUT_LOG = Path(os.environ.get("SCUT_LOG", "/var/log/scut.log"))
WEBHOOK_LOG = Path(os.environ.get("SCUT_WEBHOOK_LOG", "/var/log/scut-webhook.log"))
ERROR_LOG = Path(os.environ.get("SCUT_ERROR_LOG", "/var/log/scut-errors.log"))
WEBHOOK_BIN = Path(os.environ.get("SCUT_WEBHOOK_BIN", "/usr/local/bin/scut-webhook.sh"))


def rsyslog_state():
    try:
        r = subprocess.run(["systemctl", "is-active", "rsyslog"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or "unknown"
    except Exception:
        # Fallback: is a rsyslogd process running?
        try:
            r = subprocess.run(["pgrep", "-x", "rsyslogd"], capture_output=True, timeout=5)
            return "active" if r.returncode == 0 else "inactive"
        except Exception:
            return "unknown"


def _tail(path: Path, n: int):
    if not path.exists():
        return []
    try:
        # Simple, robust tail for modest log sizes.
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-n:]
    except OSError:
        return []


def _count_recent(path: Path, within_seconds: int):
    """Count log lines whose leading ISO/syslog timestamp is within the window. Best-effort."""
    if not path.exists():
        return 0, None
    now = time.time()
    total = 0
    last = None
    iso_re = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")
    for line in _tail(path, 2000):
        last = line
        m = iso_re.search(line)
        if not m:
            continue
        try:
            ts = datetime.fromisoformat(m.group(1)).timestamp()
            if now - ts <= within_seconds:
                total += 1
        except ValueError:
            continue
    return total, last


def build_health():
    relays_total = len(_tail(SCUT_LOG, 100000)) if SCUT_LOG.exists() else 0
    relays_hr, last_relay = _count_recent(WEBHOOK_LOG if WEBHOOK_LOG.exists() else SCUT_LOG, 3600)
    errors_hr, _ = _count_recent(ERROR_LOG, 3600)
    return {
        "role": "scut-gateway",
        "status": "up",
        "host": socket.gethostname(),
        "rsyslog": rsyslog_state(),
        "webhook": "present" if WEBHOOK_BIN.exists() else "missing",
        "relays_total": relays_total,
        "relays_last_hour": relays_hr,
        "errors_last_hour": errors_hr,
        "last_relay": (last_relay or "-")[-200:],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class GatewayHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/ping":
            self._respond(200, {"status": "pong", "role": "scut-gateway"})
        elif self.path == "/health":
            self._respond(200, build_health())
        elif self.path.startswith("/log"):
            n = 50
            m = re.search(r"[?&]n=(\d+)", self.path)
            if m:
                n = max(1, min(500, int(m.group(1))))
            src = WEBHOOK_LOG if WEBHOOK_LOG.exists() else SCUT_LOG
            self._respond(200, {"source": str(src), "lines": _tail(src, n)})
        else:
            self._respond(404, {"error": "unknown endpoint"})

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, fmt, *args):
        pass


def main():
    host = "0.0.0.0"
    server = http.server.HTTPServer((host, PORT), GatewayHandler)
    print("SCUT Gateway Autoresponder")
    print(f"Host:      {socket.gethostname()}")
    print(f"Listening: http://{host}:{PORT}  (GET /health, /ping, /log?n=)")
    print(f"Watching:  {SCUT_LOG}, {WEBHOOK_LOG}")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
