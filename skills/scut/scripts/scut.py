#!/usr/bin/env python3
"""
SCUT — Subspace Communications Unit Technology

Lightweight webhook listener + verification protocol for OpenClaw instances.
On an incoming notification the listener NOTIFIES — it does not consume the mail.
A `type=request` wakes the agent (via SCUT_WAKE_CMD) to read it, act, and reply;
any other type is left for the agent's next heartbeat check. It also provides a
radio-check handshake so a sender can VERIFY delivery instead of firing UDP into the void.

Usage:
  scut.py start [--port 8514] [--host 0.0.0.0]      Start the listener
  scut.py status                                      Ping every instance's listener
  scut.py notify <instance> [--from <s>] [--type <t>] Send a SCUT notification (syslog + direct)
  scut.py test                                        Send a test notification to yourself
  scut.py radio-check [--to <instance>] [--timeout 6] "Radio check, do you hear me?"
                                                      --to X  : check one peer (direct + via-gateway)
                                                      (no --to): roll call — net control answers
  scut.py gateway-check [--timeout 4]                 Is the SCUT gateway (rsyslog relay) up?

Verification model (two layers):
  1. DIRECT handshake  — synchronous POST /radio-check to the peer's listener.
       Proves the peer process is up and reachable. Storm-proof (1:1, synchronous).
  2. VIA-GATEWAY e2e   — fires the real syslog→gateway→peer path with a nonce; the
       peer acks back. Proves the actual notification path (the one real messages use)
       works. A failure here with a passing direct handshake = gateway/syslog problem.

Anti-storm rules:
  - A radio-ack is TERMINAL: receiving one never triggers another notify/check/ack.
  - Directed check: only the addressed peer replies.
  - Broadcast/roll-call (scope=net): ONLY net_control replies; everyone else stays silent.

Cross-platform: Windows + Linux. Standard library only.

Environment:
  OPENCLAW_INSTANCE     This instance's name (required)
  CLAWDBOT_HOME         Workspace root (required)
  SCUT_PORT             Listener port (default: 8514)
  SCUT_SYSLOG_HOST      Syslog server (default: endpoints.json → vault → TKD01SVR)
  SCUT_SYSLOG_PORT      Syslog server port (default: endpoints.json → vault → 514)
  SCUT_STATE_DIR        Local dir for scut-acks.jsonl (default: ~/.openclaw/scut). Local disk
                        only — never point this at the CIFS-mounted CLAWDBOT_HOME.
  SCUT_WAKE_CMD         Shell command to wake the agent on a request (see config below).
                        Runs with $SCUT_WAKE_PROMPT, $SCUT_WAKE_SENDER, $OPENCLAW_INSTANCE.
"""

import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

# --- Vault Integration ---

def vault_get(key):
    """Retrieve a secret from the OpenClaw vault. Returns None if unavailable."""
    home = os.environ.get("CLAWDBOT_HOME", "")
    if not home:
        return None
    vault_script = os.path.join(home, "skills", "vault", "scripts", "vault.py")
    if not os.path.exists(vault_script):
        return None
    try:
        result = subprocess.run(
            [sys.executable, vault_script, "get", key],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None

# --- Config ---

INSTANCE = os.environ.get("OPENCLAW_INSTANCE", "")
CLAWDBOT_HOME = os.environ.get("CLAWDBOT_HOME", "")
SCUT_PORT = int(os.environ.get("SCUT_PORT", "8514"))

# Command the listener runs to WAKE THE AGENT so it acts on a `type=request` message.
# Set this to your OpenClaw inject mechanism (CLI or curl to the gateway). It runs via the
# shell with these env vars available: $SCUT_WAKE_PROMPT (what to tell the agent),
# $SCUT_WAKE_SENDER, $OPENCLAW_INSTANCE.
# Example: SCUT_WAKE_CMD='openclaw message --session agent:main:main --text "$SCUT_WAKE_PROMPT"'
# If unset, requests are NOT actioned in real time — they wait for the next heartbeat.
SCUT_WAKE_CMD = os.environ.get("SCUT_WAKE_CMD", "")


def get_home():
    if CLAWDBOT_HOME and Path(CLAWDBOT_HOME).is_dir():
        return Path(CLAWDBOT_HOME)
    for p in [
        Path(r"C:\Users\skipz\OneDrive - exec-it.us\Tools\AI_Workspace\Clawdbot_Home"),
        Path("/mnt/clawdbot-home"),
    ]:
        if p.is_dir():
            return p
    return None


# --- Endpoints: single source of truth (endpoints.json) ---

_EMBEDDED_FALLBACK = {
    "gateway": {"host": "TKD01SVR", "syslog_port": 514, "health_port": 8515},
    "net_control": "Spock",
    "instances": {
        "Bob":     {"host": "TKD14PC", "port": 8514},
        "Spock":   {"host": "TKD01AI", "port": 8514},
        "Watson":  {"host": "TKD12PC", "port": 8514},
        "Deckard": {"host": "TKD15PC", "port": 8514},
        "Leon":    {"host": "TKD02AI", "port": 8514},
        "Bill":    {"host": "tkd01vm", "port": 8514},
    },
}


def _load_endpoints():
    """Load endpoints.json from the scut skill dir; fall back to embedded defaults."""
    candidates = []
    home = get_home()
    if home:
        candidates.append(home / "skills" / "scut" / "endpoints.json")
    candidates.append(Path(__file__).resolve().parent.parent / "endpoints.json")
    for c in candidates:
        try:
            if c.exists():
                data = json.loads(c.read_text(encoding="utf-8"))
                if "instances" in data:
                    return data
        except (OSError, json.JSONDecodeError):
            continue
    return _EMBEDDED_FALLBACK


_EP = _load_endpoints()
INSTANCE_ENDPOINTS = _EP.get("instances", {})
KNOWN_INSTANCES = list(INSTANCE_ENDPOINTS.keys())
NET_CONTROL = _EP.get("net_control", "Spock")
GATEWAY = _EP.get("gateway", {})

SYSLOG_HOST = (os.environ.get("SCUT_SYSLOG_HOST") or GATEWAY.get("host")
               or vault_get("scut/syslog-host") or "TKD01SVR")
SYSLOG_PORT = int(os.environ.get("SCUT_SYSLOG_PORT") or GATEWAY.get("syslog_port")
                  or vault_get("scut/syslog-port") or "514")
GATEWAY_HEALTH_PORT = int(GATEWAY.get("health_port", 8515))

# Control-plane message types that must NOT trigger a comms.py message check.
CONTROL_TYPES = {"radio-check", "radio-ack"}


def get_comms_script():
    home = get_home()
    if not home:
        return None
    for candidate in (
        home / "skills" / "scut" / "scripts" / "comms.py",
        home / "skills" / "instance-comms-1.0.0" / "scripts" / "comms.py",
    ):
        if candidate.exists():
            return str(candidate)
    return None


def _ack_file():
    """Where this instance records radio-acks it receives, for the CLI to read.

    Deliberately LOCAL DISK, not the CIFS-mounted CLAWDBOT_HOME. The mount develops stale-inode
    failures (OSError 116) after any process replaces the file (e.g. an editor's atomic save),
    which silently dropped every ack afterward while the HTTP handler still reported success —
    the corresponding radio-check would then time out on the GATEWAY leg for no visible reason.
    This is per-instance transient data (a nonce poll buffer), so it never needed to be shared.
    """
    if not INSTANCE:
        return None
    override = os.environ.get("SCUT_STATE_DIR")
    state_dir = Path(override) if override else Path.home() / ".openclaw" / "scut"
    return state_dir / "scut-acks.jsonl"


def log_event(msg):
    """Append to the instance daily log. Best-effort — share I/O must not kill the listener."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    home = get_home()
    if not home or not INSTANCE:
        print(f"[SCUT {timestamp}] {msg}")
        return
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = home / "instances" / INSTANCE / "logs" / f"{today}.md"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n**[SCUT {timestamp}]** {msg}\n")
    except OSError as e:
        print(f"[SCUT {timestamp}] (share-log skipped: {e}) {msg}", file=sys.stderr)
        return
    print(f"[SCUT {timestamp}] {msg}")


# === LISTENER (runs on each instance) ===

class SCUTHandler(http.server.BaseHTTPRequestHandler):

    def do_POST(self):
        if self.path == "/notify":
            self._handle_notify()
        elif self.path == "/radio-check":
            self._handle_radio_check_direct()
        elif self.path == "/ping":
            self._respond(200, {"status": "pong", "instance": INSTANCE})
        else:
            self._respond(404, {"error": "unknown endpoint"})

    def do_GET(self):
        if self.path == "/health":
            self._handle_health()
        elif self.path == "/ping":
            self._respond(200, {"status": "pong", "instance": INSTANCE})
        else:
            self._respond(404, {"error": "unknown endpoint"})

    def _read_json(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n).decode("utf-8") if n > 0 else "{}"
            return json.loads(body) if body.strip() else {}
        except (json.JSONDecodeError, ValueError):
            return {}

    def _handle_notify(self):
        """Incoming notification. Control types are handled here and DO NOT run a message check."""
        data = self._read_json()
        msg_type = data.get("type", "unknown")
        sender = data.get("from", "unknown")

        # --- Control plane: radio-check / radio-ack ---
        if msg_type == "radio-ack":
            # TERMINAL. Record it for the CLI; never respond.
            self._record_ack(data)
            log_event(f"Radio-ack heard from {sender} (nonce={data.get('nonce','?')}).")
            self._respond(200, {"status": "ack-recorded", "instance": INSTANCE})
            return

        if msg_type == "radio-check":
            scope = data.get("scope", "directed")
            nonce = data.get("nonce", "")
            replyto = data.get("replyto", sender)
            should_reply = (scope == "directed") or (scope == "net" and INSTANCE == NET_CONTROL)
            log_event(f"Radio-check from {sender} (scope={scope}, src={data.get('source','?')}). "
                      f"{'Replying' if should_reply else 'Silent (not net control)'}.")
            if should_reply:
                send_radio_ack(replyto, nonce)
            self._respond(200, {"status": "heard", "instance": INSTANCE, "replied": should_reply})
            return

        # --- Real message notification ---
        # The listener must NOT consume mail here. Running `comms.py check` would fetch the
        # message into a log AND advance the cursor, so the agent would never see it (that was
        # the "acknowledges but doesn't act" bug). We only NOTIFY/WAKE; the agent reads + acts.
        source = data.get("source", "direct")
        if msg_type == "request":
            # Requests require action. Wake the agent to read it, do it, and reply.
            log_event(f"REQUEST from {sender} (src={source}). Waking agent to act...")
            threading.Thread(target=self._wake_agent_for_request, args=(sender,), daemon=True).start()
            self._respond(200, {"status": "waking-agent", "instance": INSTANCE, "from": sender})
        else:
            # info / status / alert / etc.: read-and-log. The agent picks these up on its next
            # heartbeat `comms.py check` — no wake, no reply expected.
            log_event(f"Notification from {sender} (type={msg_type}, src={source}) — "
                      f"will be read on next heartbeat (no action required).")
            self._respond(200, {"status": "queued-for-heartbeat", "instance": INSTANCE, "type": msg_type})

    def _handle_radio_check_direct(self):
        """Synchronous direct handshake — 'I hear you' in the same HTTP response."""
        data = self._read_json()
        self._respond(200, {
            "ack": "I hear you",
            "instance": INSTANCE,
            "net_control": INSTANCE == NET_CONTROL,
            "nonce": data.get("nonce", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _record_ack(self, data):
        f = _ack_file()
        if not f:
            return
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            rec = {
                "nonce": data.get("nonce", ""),
                "from": data.get("from", "unknown"),
                "type": "radio-ack",
                "path": data.get("path", "direct"),
                "ts": time.time(),
            }
            with open(f, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
        except OSError as e:
            log_event(f"ERROR: failed to record radio-ack from {rec.get('from', 'unknown')} "
                      f"(nonce={rec.get('nonce', '?')}) to {f}: {e}")

    def _handle_health(self):
        home = get_home()
        health = {
            "instance": INSTANCE,
            "status": "online",
            "port": SCUT_PORT,
            "net_control": INSTANCE == NET_CONTROL,
            "home": str(home) if home else None,
            "syslog": f"{SYSLOG_HOST}:{SYSLOG_PORT}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._respond(200, health)

    def _wake_agent_for_request(self, sender):
        """Inject a turn into the running agent so it reads the request, ACTS, and replies.

        Uses the configured SCUT_WAKE_CMD. Deliberately does NOT call comms.py check — the
        agent does that itself when woken, so the cursor only advances once the agent has the
        message in hand.
        """
        prompt = (
            f"SCUT: a REQUEST just arrived from {sender}. Run comms.py check to read it, "
            f"DO what it asks, then reply to {sender} with the result via "
            f"`comms.py send --to {sender} --type info`. This is a request — act, do not just acknowledge."
        )
        env = os.environ.copy()
        env["OPENCLAW_INSTANCE"] = INSTANCE
        env["SCUT_WAKE_PROMPT"] = prompt
        env["SCUT_WAKE_SENDER"] = sender
        if CLAWDBOT_HOME:
            env["CLAWDBOT_HOME"] = CLAWDBOT_HOME
        try:
            if SCUT_WAKE_CMD:
                # User-supplied wake command (shell-evaluated). Supports
                # provider-specific tricks and shell-var expansion.
                result = subprocess.run(SCUT_WAKE_CMD, shell=True, capture_output=True,
                                        text=True, timeout=30, env=env)
            else:
                # Built-in default: enqueue a system event into the main session
                # (verified 2026-07-02; the old `openclaw message --session` form
                # was never valid CLI syntax and failed on every host).
                # Note: on Windows the bare "openclaw" npm shim is not launchable
                # by subprocess without shell — set SCUT_WAKE_CMD per-host there.
                result = subprocess.run(
                    ["openclaw", "system", "event", "--mode", "now",
                     "--text", prompt],
                    capture_output=True, text=True, timeout=30, env=env,
                )
            if result.returncode == 0:
                log_event(f"Agent woken to act on request from {sender}.")
            else:
                log_event(f"Wake command failed (rc={result.returncode}): {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            log_event("Wake command timed out (30s)")
        except Exception as e:
            log_event(f"Wake command error: {e}")

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, fmt, *args):
        pass  # suppress default HTTP logging


def cmd_start(host="0.0.0.0", port=None):
    if not INSTANCE:
        print("Error: OPENCLAW_INSTANCE not set. Cannot start SCUT.", file=sys.stderr)
        sys.exit(1)
    port = port or SCUT_PORT
    server = http.server.HTTPServer((host, port), SCUTHandler)
    log_event(f"SCUT listener started on {host}:{port} for instance {INSTANCE}")
    print("SCUT — Subspace Communications Unit Technology")
    print(f"Instance:  {INSTANCE}{'  (NET CONTROL)' if INSTANCE == NET_CONTROL else ''}")
    print(f"Listening: http://{host}:{port}")
    print(f"Syslog:    {SYSLOG_HOST}:{SYSLOG_PORT}")
    print(f"Endpoints: POST /notify, POST /radio-check, GET /health, GET|POST /ping")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log_event("SCUT listener stopped by user")
        server.shutdown()


# === NOTIFIER (syslog UDP + direct HTTP) ===

def send_syslog_notify(recipient, sender=None, msg_type="notify", extra=""):
    """Fire a SCUT notification via UDP syslog to the central gateway (fire-and-forget)."""
    sender = sender or INSTANCE or "unknown"
    message = f"SCUT:{recipient} from={sender} type={msg_type}"
    if extra:
        message += f" {extra}"
    syslog_msg = f"<134>{datetime.now().strftime('%b %d %H:%M:%S')} {socket.gethostname()} scut: {message}"
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(syslog_msg.encode("utf-8"), (SYSLOG_HOST, SYSLOG_PORT))
        sock.close()
        return True, f"Syslog sent to {SYSLOG_HOST}:{SYSLOG_PORT}"
    except Exception as e:
        return False, str(e)


def send_direct_notify(recipient, sender=None, msg_type="notify", payload_extra=None):
    """POST directly to an instance's listener (bypasses syslog)."""
    sender = sender or INSTANCE or "unknown"
    ep = INSTANCE_ENDPOINTS.get(recipient)
    if not ep:
        return False, f"No endpoint configured for {recipient}"
    url = f"http://{ep['host']}:{ep['port']}/notify"
    body = {"from": sender, "type": msg_type, "source": "direct",
            "timestamp": datetime.now(timezone.utc).isoformat()}
    if payload_extra:
        body.update(payload_extra)
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=5)
        return True, f"Direct notify to {recipient} ({url}): {resp.status}"
    except Exception as e:
        return False, f"Direct notify to {recipient} failed: {e}"


def send_radio_ack(replyto, nonce):
    """Send a single terminal radio-ack back to the sender's listener (direct HTTP)."""
    ep = INSTANCE_ENDPOINTS.get(replyto)
    if not ep:
        return
    url = f"http://{ep['host']}:{ep['port']}/notify"
    body = json.dumps({
        "from": INSTANCE, "type": "radio-ack", "nonce": nonce,
        "path": "via-gateway", "source": "ack",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # ack is best-effort; sender will simply report "no reply"


def cmd_notify(recipient, sender=None, msg_type="notify"):
    """Send a SCUT notification — syslog (central) + direct HTTP (confirms delivery)."""
    sender = sender or INSTANCE or "unknown"
    targets = [i for i in KNOWN_INSTANCES if i != sender] if recipient.lower() == "all" else [recipient]
    results = []
    for target in targets:
        ok, detail = send_syslog_notify(target, sender, msg_type)
        ok2, detail2 = send_direct_notify(target, sender, msg_type)
        results.append({"target": target, "syslog": ok, "syslog_detail": detail,
                        "direct": ok2, "direct_detail": detail2})
    for r in results:
        status = ("syslog+direct" if r["syslog"] and r["direct"]
                  else "syslog only" if r["syslog"]
                  else "direct only" if r["direct"] else "FAILED")
        print(f"  {r['target']}: {status}")
    print(json.dumps({"notifications": results}, indent=2))


# === VERIFICATION ===

def _direct_handshake(peer, nonce, timeout=5):
    """Synchronous 'radio check' to a peer's listener. Returns (ok, detail, rtt_ms)."""
    ep = INSTANCE_ENDPOINTS.get(peer)
    if not ep:
        return False, f"no endpoint for {peer}", None
    url = f"http://{ep['host']}:{ep['port']}/radio-check"
    body = json.dumps({"from": INSTANCE, "nonce": nonce}).encode("utf-8")
    t0 = time.time()
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        rtt = (time.time() - t0) * 1000
        data = json.loads(resp.read().decode("utf-8"))
        return True, data.get("ack", "ack"), rtt
    except Exception as e:
        return False, str(e), None


def _wait_for_ack(nonce, who=None, timeout=6):
    """Poll the local ack file for a radio-ack matching this nonce (optionally from `who`)."""
    f = _ack_file()
    deadline = time.time() + timeout
    start = time.time() - 1
    while time.time() < deadline:
        if f and f.exists():
            try:
                for line in f.read_text(encoding="utf-8").splitlines():
                    rec = json.loads(line)
                    if rec.get("nonce") != nonce or rec.get("ts", 0) < start:
                        continue
                    if who and rec.get("from") != who:
                        continue
                    return rec
            except (OSError, json.JSONDecodeError):
                pass
        time.sleep(0.4)
    return None


def cmd_radio_check(peer=None, timeout=6):
    """Radio check. With --to: one peer (direct + via-gateway). Without: roll call (net control replies)."""
    if not INSTANCE:
        print("Error: OPENCLAW_INSTANCE not set.", file=sys.stderr)
        sys.exit(1)
    nonce = uuid.uuid4().hex[:12]

    if peer:
        print(f'[radio-check] {INSTANCE} to {peer}, do you hear me?')
        # Layer 1: direct handshake
        ok, detail, rtt = _direct_handshake(peer, nonce, timeout=min(5, timeout))
        if ok:
            print(f"  [OK]   DIRECT : {peer} hears you{f' ({rtt:.0f} ms)' if rtt else ''} - listener up")
        else:
            print(f"  [FAIL] DIRECT : no reply - {detail}")
        # Layer 2: via-gateway end-to-end (real SCUT path)
        s_ok, s_detail = send_syslog_notify(peer, INSTANCE, "radio-check",
                                            extra=f"nonce={nonce} scope=directed replyto={INSTANCE}")
        if not s_ok:
            print(f"  [FAIL] GATEWAY: couldn't emit syslog - {s_detail}")
        else:
            rec = _wait_for_ack(nonce, who=peer, timeout=timeout)
            if rec:
                print(f"  [OK]   GATEWAY: {peer} acked via the real SCUT path - syslog->gateway->{peer} works")
            else:
                print(f"  [WARN] GATEWAY: no ack within {timeout}s - "
                      f"{'peer is up (direct OK) so the GATEWAY/syslog path is the problem' if ok else 'peer or gateway down'}")
        return

    # Roll call - net control answers
    print(f'[radio-check] {INSTANCE} to net, radio check  (net control = {NET_CONTROL})')
    if INSTANCE == NET_CONTROL:
        print("  (You ARE net control - checking your own gateway path instead.)")
    for target in [i for i in KNOWN_INSTANCES if i != INSTANCE]:
        send_syslog_notify(target, INSTANCE, "radio-check",
                           extra=f"nonce={nonce} scope=net replyto={INSTANCE}")
    rec = _wait_for_ack(nonce, who=NET_CONTROL, timeout=timeout)
    if rec:
        print(f"  [OK]   {NET_CONTROL} (net control) answered - the net is up, gateway relaying.")
    else:
        print(f"  [FAIL] No reply from net control ({NET_CONTROL}) within {timeout}s - "
              f"gateway down, net control offline, or routing broken. Try: scut.py gateway-check")


def cmd_gateway_check(timeout=4):
    """Probe the SCUT gateway's autoresponder (TKD01SVR) over reliable TCP."""
    host = GATEWAY.get("host", SYSLOG_HOST)
    url = f"http://{host}:{GATEWAY_HEALTH_PORT}/health"
    print(f"[gateway-check] {url}")
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        data = json.loads(resp.read().decode("utf-8"))
        print(f"  [OK] Gateway UP ({host})")
        print(f"     rsyslog: {data.get('rsyslog','?')}  webhook: {data.get('webhook','?')}")
        print(f"     relays: {data.get('relays_last_hour','?')} last hour, "
              f"{data.get('relays_total','?')} total; last: {data.get('last_relay','-')}")
        if data.get("errors_last_hour"):
            print(f"     [WARN] errors last hour: {data['errors_last_hour']}")
    except Exception as e:
        print(f"  [FAIL] Gateway DOWN or unreachable on {host}:{GATEWAY_HEALTH_PORT} - {e}")
        print("     SCUT delivery cannot be confirmed. Messages still queue in PostgreSQL/JSONL.")


def cmd_test():
    if not INSTANCE:
        print("Error: OPENCLAW_INSTANCE not set.", file=sys.stderr)
        sys.exit(1)
    print(f"Sending test SCUT notification to self ({INSTANCE})...")
    cmd_notify(INSTANCE, INSTANCE, "test")


def cmd_status():
    print("SCUT Instance Status Check")
    print("=" * 44)
    for name, ep in INSTANCE_ENDPOINTS.items():
        url = f"http://{ep['host']}:{ep['port']}/ping"
        tag = " (net control)" if name == NET_CONTROL else ""
        try:
            resp = urllib.request.urlopen(urllib.request.Request(url), timeout=3)
            data = json.loads(resp.read().decode("utf-8"))
            print(f"  {name:10s} ({ep['host']}:{ep['port']}): ONLINE - {data.get('instance','?')}{tag}")
        except Exception as e:
            print(f"  {name:10s} ({ep['host']}:{ep['port']}): OFFLINE - {e}{tag}")


# === MAIN ===

def _opt(args, flag, default=None):
    if flag in args:
        i = args.index(flag)
        if i + 1 < len(args):
            return args[i + 1]
    return default


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "start":
        cmd_start(_opt(args, "--host", "0.0.0.0"), int(_opt(args, "--port", SCUT_PORT)))
    elif cmd == "notify":
        if not args:
            print("Usage: scut.py notify <instance> [--from sender] [--type type]")
            sys.exit(1)
        cmd_notify(args[0], _opt(args, "--from"), _opt(args, "--type", "notify"))
    elif cmd == "radio-check":
        cmd_radio_check(_opt(args, "--to"), int(_opt(args, "--timeout", "6")))
    elif cmd == "gateway-check":
        cmd_gateway_check(int(_opt(args, "--timeout", "4")))
    elif cmd == "test":
        cmd_test()
    elif cmd == "status":
        cmd_status()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
