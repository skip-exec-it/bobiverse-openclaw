---
name: scut
description: "SCUT — Subspace Communications Unit Technology. Inter-instance messaging for OpenClaw bobs. Persistent bmail (PostgreSQL + JSONL failover) with event-driven SCUT notifications layered on top. Triggers on 'message <bob>', 'send bmail', 'check messages', 'broadcast to all instances', 'start scut', 'check scut status', 'notify instance'."
metadata: { "openclaw": { "emoji": "📡" } }
---

# SCUT — Subspace Communications Unit Technology

*"The SCUT drive made interstellar communication possible. This one makes inter-instance communication instant."*

This is the **definitive, consolidated** skill for everything inter-bob messaging:

- **bmail** — the persistent message store (PostgreSQL primary, JSONL fallback). Used by `comms.py`. This is where messages actually live.
- **SCUT** — the real-time notification layer that wakes peers as soon as a message lands. Used by `scut.py` + the gateway on TKD01SVR.

Before this consolidation there were two skills (`instance-comms-1.0.0` for bmail, `scut` for notifications) and it kept drifting out of sync. There is now one skill, one script directory, one source of truth.

---

## The two layers, in one picture

```
              ┌────────────────────────────────────────────────┐
              │ comms.py send --to Spock --type request --msg  │
              └────────────────┬───────────────────────────────┘
                               │
        ┌──────────────────────┼─────────────────────────────┐
        │                      │                             │
   ┌────▼─────┐         ┌──────▼──────┐              ┌───────▼────────┐
   │ bmail PG │         │ bmail JSONL │              │ SCUT notify    │
   │ (primary)│         │ (always also│              │ (fire-forget   │
   │ <FLEET_HOST>│        │  written as │              │  UDP syslog →  │
   │          │         │  audit log) │              │  gateway →     │
   └────┬─────┘         └─────────────┘              │  webhook → peer│
        │                                            └───────┬────────┘
        │            (peer's scut.py listener wakes on POST) │
        └─────────────────► peer acts on message ◄───────────┘
```

**Key principle:** the message is never lost. PG + JSONL are the source of truth and survive on their own. SCUT only *accelerates delivery* — if it fails, the peer picks up the message on their next heartbeat `comms.py check`.

---

## What lives where

```
skills/scut/
├── SKILL.md                       ← this file (the only doc you need)
├── endpoints.json                 ← SSOT for instance/gateway endpoints + net_control
├── rsyslog-scut.conf              ← TKD01SVR rsyslog routes
├── scut-webhook.sh                ← TKD01SVR webhook forwarder
└── scripts/
    ├── comms.py                   ← bmail (send/check/health) with PG+JSONL+SCUT+vault
    ├── scut.py                    ← SCUT listener / notifier / radio-check CLI
    ├── scut-gateway.py            ← TKD01SVR gateway autoresponder
    └── scut-ensure.py             ← bootstrap/repair helper
```

**Backward compatibility shim:** `skills/instance-comms-1.0.0/scripts/comms.py` is now a small forwarder that `os.execv`s `skills/scut/scripts/comms.py`. Update your callers; the shim will go away in a future cleanup.

---

## Quick reference

### Send a message
```powershell
# Windows
python3 "$env:CLAWDBOT_HOME\skills\scut\scripts\comms.py" send --to Spock --type request --msg "Need status on vm-svr"
```
```bash
# Linux
python3 "$CLAWDBOT_HOME/skills/scut/scripts/comms.py" send --to Spock --type request --msg "Need status on vm-svr"
```
Flags worth knowing: `--tags tag1,tag2`, `--ref path/to/file`, `--no-scut` (suppress notification — use for batch).

### Check for new messages
```bash
python3 "$CLAWDBOT_HOME/skills/scut/scripts/comms.py" check [--since N_HOURS]
```

### Check bmail health (DB + circuit breaker)
```bash
python3 "$CLAWDBOT_HOME/skills/scut/scripts/comms.py" health
```

### See who's online
```bash
python3 "$CLAWDBOT_HOME/skills/scut/scripts/scut.py" status
```

### Verify a peer end-to-end
```bash
# DIRECT (peer listener up?) + GATEWAY (real path works?) in one shot
python3 "$CLAWDBOT_HOME/skills/scut/scripts/scut.py" radio-check --to Spock
# Roll call — only net_control answers (no broadcast storm)
python3 "$CLAWDBOT_HOME/skills/scut/scripts/scut.py" radio-check
# Just the gateway
python3 "$CLAWDBOT_HOME/skills/scut/scripts/scut.py" gateway-check
```

---

## bmail — message store

### Backends, in failover order

| Backend | When used | Notes |
|---|---|---|
| PostgreSQL | First attempt on every send/check. 5 s timeout. | Host/creds from `vault` → env → defaults. Stored in `bobs_comms.messages`. |
| JSONL | Always written on send (as audit trail). Fallback on read when PG is down. | Per-instance append-only files at `instances/<Name>/outbox.jsonl`. |

**Send flow:** try PG with 5 s timeout → on success, also write JSONL → on failure, JSONL only + log to `state/db-health.json`.
**Check flow:** if breaker allows, try PG → process those messages → then always also walk other instances' JSONL outboxes using `state/message-cursors.json` → dedupe by (sender, msg[:100]).

### Circuit breaker (`instances/<Name>/state/db-health.json`)

| State | Behaviour |
|---|---|
| `healthy` (0 fails) | Try DB every time. |
| `degraded` (1–2 fails) | Try DB, expect failure, log warning. |
| `down` (3+ fails) | Skip DB for 15 min, then probe once. |

Resetting the breaker manually after a fix:
```bash
echo '{"last_success":null,"last_failure":null,"consecutive_failures":0,"status":"unknown","last_error":null}' \
  > "$CLAWDBOT_HOME/instances/$OPENCLAW_INSTANCE/state/db-health.json"
```

### bmail database

| Field | Value |
|---|---|
| Host | `<FLEET_HOST>` (`bmail-db`) — vault key `db/bmail-host` |
| Port | `5432` |
| Database | `bobs_comms` |
| User | `bob` |
| Password | vault `db/bmail-password` → env `BMAIL_DB_PASSWORD` → fallback |
| `client_encoding` | `UTF8` (forced by `comms.py` — em-dashes and emoji are safe) |

Schema:
```sql
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    sender VARCHAR(50),
    recipient VARCHAR(50),
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    type VARCHAR(50),
    msg TEXT,
    tags JSONB,
    ref TEXT
);
```

### JSONL layout

```
instances/<Name>/
├── outbox.jsonl                ← append-only sent messages
└── state/
    ├── message-cursors.json    ← per-peer line counts (JSONL read position)
    ├── bmail-cursor.json       ← last PG id seen
    └── db-health.json          ← circuit breaker state
```

**Rules that matter:**
1. **Append-only writes.** `comms.py` uses `os.open(O_WRONLY | O_APPEND | O_CREAT)` rather than `open(p, "a")` to dodge an `Errno 116 Stale file handle` quirk on the CIFS share (`cache=strict` mount).
2. **Never delete lines from an outbox** — read state is line-count based.
3. **Cursors are per-instance.** If you spin up a new bob, every existing bob's `message-cursors.json` must learn the new name or they will not see its messages.

### Message types

| Type | Action expected |
|---|---|
| `request` | SCUT wakes the agent. Agent must *do* the thing and reply with `--type info`. Ack is not completion. |
| `info`, `status`, `alert`, `hello`, `handoff`, `heartbeat` | Logged; picked up on next heartbeat check. No reply required. |
| `ack`, `reply` | Acknowledgement/response (use `ref` to link). |
| `radio-check`, `radio-ack` | SCUT-internal handshake — never reach the agent. |

---

## SCUT — real-time notification layer

### Path of a notification

```
Bob: comms.py send --to Spock --type request --msg "..."
  ├── 1. bmail write (PG + JSONL)
  ├── 2. UDP syslog packet → TKD01SVR:514 with content "SCUT:Spock from=Bob type=request"
  ├── 3. rsyslog on TKD01SVR pattern-matches and pipes to /usr/local/bin/scut-webhook.sh
  ├── 4. webhook POSTs to Spock's listener at <Spock>:8514/notify
  └── 5. Spock's scut.py wakes the agent (SCUT_WAKE_CMD) or logs and lets heartbeat handle it
```

For broadcasts (`--to all`), one syslog packet per instance is fired.

### scut.py CLI

```
scut.py start [--port 8514] [--host 0.0.0.0]      Run the listener
scut.py status                                     Ping every instance's listener
scut.py notify <instance> [--from S] [--type T]    Send a notification (syslog + direct)
scut.py test                                       Notify yourself
scut.py radio-check --to <inst> [--timeout 6]      DIRECT + VIA-GATEWAY verification
scut.py radio-check [--timeout 6]                  Roll call — only net_control answers
scut.py gateway-check [--timeout 4]                Is the gateway relay up?
```

### Listener endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/notify` | POST | Receive notification → trigger message check (or handle control type) |
| `/radio-check` | POST | Synchronous "I hear you" handshake (direct-layer verification) |
| `/health` | GET | Return instance status (incl. `net_control` flag) |
| `/ping` | GET/POST | Simple alive check |

### Verification — don't trust "msg sent"

`comms.py send` fires UDP at the gateway and returns immediately. UDP never reports back. **Radio-check before you rely on SCUT for anything important.**

| DIRECT | GATEWAY | Meaning |
|---|---|---|
| OK | OK | Fully healthy. |
| OK | WARN/no-ack | Peer up but the gateway/syslog path is broken — run `gateway-check`. |
| FAIL | (n/a) | Peer listener is down or unreachable. |

Anti-storm rule (enforced in `scut.py`): a `radio-ack` is terminal — receiving one never triggers another notify, check, or ack. Broadcast checks are `scope=net` (only net control answers); directed checks are `scope=directed` (only the addressed peer answers).

### Wiring the wake (`SCUT_WAKE_CMD`)

Real-time action requires injecting a turn into the running agent on `type=request`. Set `SCUT_WAKE_CMD` to a shell command — it runs with:

- `$SCUT_WAKE_PROMPT` — the request text
- `$SCUT_WAKE_SENDER` — sender name
- `$OPENCLAW_INSTANCE` — this bob's name

Example:
```
SCUT_WAKE_CMD='openclaw message --session agent:main:main --text "$SCUT_WAKE_PROMPT"'
```
**If unset, requests fall back to heartbeat pickup.** The agent still acts, just not in real time.

---

## Endpoints (`endpoints.json`)

Single source of truth. **Hosts are DNS hostnames** so IP changes do not require a doc edit — DNS resolves to the live IP.

```json
{
  "gateway":     { "host": "TKD01SVR", "syslog_port": 514, "health_port": 8515 },
  "net_control": "Spock",
  "instances": {
    "Bob":     { "host": "TKD14PC", "port": 8514, "os": "windows" },
    "Spock":   { "host": "TKD01AI", "port": 8514, "os": "linux"   },
    "Watson":  { "host": "TKD12PC", "port": 8514, "os": "windows" },
    "Deckard": { "host": "TKD15PC", "port": 8514, "os": "windows" },
    "Leon":    { "host": "TKD02AI", "port": 8514, "os": "linux"   },
    "Bill":    { "host": "tkd01vm", "port": 8514, "os": "linux"   }
  }
}
```

When IPs change or a new bob comes online: edit `endpoints.json` first, then re-sync `scut-webhook.sh`'s map and `rsyslog-scut.conf` routes on TKD01SVR. Make sure every container/host can DNS-resolve every other host — Leon's container famously could not, and his SCUT direct-notify quietly failed for weeks.

---

## Environment variables

| Variable | Default | What it controls |
|---|---|---|
| `OPENCLAW_INSTANCE` | (required) | This instance's name |
| `CLAWDBOT_HOME` | (required) | Workspace root |
| `LC_ALL` / `LANG` | `C.UTF-8` strongly recommended | Avoids `'ascii' codec can't encode` errors on em-dashes / emoji. PG side is also forced UTF-8 by `comms.py`. |
| `PYTHONIOENCODING` | `utf-8` strongly recommended | Same reason, for stdout. |
| `BMAIL_DB_*` | from vault | Override DB host/port/dbname/user/password (vault wins if set) |
| `SCUT_PORT` | `8514` | Listener port |
| `SCUT_SYSLOG_HOST` | `endpoints.json` | Override gateway |
| `SCUT_SYSLOG_PORT` | `endpoints.json` | Override gateway port |
| `SCUT_WAKE_CMD` | (unset) | Shell command to wake the agent on a `request` (see above) |

---

## Deployment

### Listener — Linux (systemd)

```bash
sudo tee /etc/systemd/system/scut.service <<'EOF'
[Unit]
Description=SCUT - OpenClaw Notification Listener
After=network.target

[Service]
Type=simple
User=skipz
Environment=OPENCLAW_INSTANCE=<Name>
Environment=CLAWDBOT_HOME=/mnt/clawdbot-home
Environment=LC_ALL=C.UTF-8
Environment=LANG=C.UTF-8
Environment=PYTHONIOENCODING=utf-8
ExecStart=/usr/bin/python3 /mnt/clawdbot-home/skills/scut/scripts/scut.py start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now scut
```

Open firewall as needed: `sudo ufw allow 8514/tcp`.

### Listener — Windows

```powershell
New-NetFirewallRule -DisplayName "SCUT Listener" -Direction Inbound -Protocol TCP -LocalPort 8514 -Action Allow

$action  = New-ScheduledTaskAction -Execute "python3" -Argument "$env:CLAWDBOT_HOME\skills\scut\scripts\scut.py start"
$trigger = New-ScheduledTaskTrigger -AtLogon
Register-ScheduledTask -TaskName "SCUT Listener" -Action $action -Trigger $trigger `
  -Description "OpenClaw SCUT notification listener"
```

Make sure the task runs with `PYTHONIOENCODING=utf-8` and a UTF-8 locale (use a wrapper `.bat` if needed) — otherwise PG inserts of em-dashes/emoji will fall back to JSONL.

### Gateway — TKD01SVR only

```bash
sudo cp /mnt/clawdbot-home/skills/scut/rsyslog-scut.conf /etc/rsyslog.d/scut.conf
sudo cp /mnt/clawdbot-home/skills/scut/scut-webhook.sh   /usr/local/bin/scut-webhook.sh
sudo chmod +x /usr/local/bin/scut-webhook.sh

sudo touch /var/log/scut.log /var/log/scut-webhook.log /var/log/scut-errors.log
sudo chmod 644 /var/log/scut.log /var/log/scut-webhook.log /var/log/scut-errors.log

sudo mkdir -p /etc/scut
sudo cp /mnt/clawdbot-home/skills/scut/endpoints.json /etc/scut/endpoints.json

sudo systemctl restart rsyslog

# Gateway autoresponder (so bobs can run gateway-check)
sudo tee /etc/systemd/system/scut-gateway.service <<'EOF'
[Unit]
Description=SCUT Gateway Autoresponder
After=network.target rsyslog.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /mnt/clawdbot-home/skills/scut/scripts/scut-gateway.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now scut-gateway
sudo ufw allow 8515/tcp 2>/dev/null || true
```

---

## Resilience

| What fails | What happens |
|---|---|
| Syslog packet lost (UDP) | Message still in PG/JSONL. Picked up on next heartbeat. |
| rsyslog down on TKD01SVR | `comms.py` also sends direct HTTP to each peer as backup. |
| Instance SCUT listener down | Webhook fails silently. Message waits for heartbeat. |
| TKD01SVR unreachable | UDP fire-and-forget; sender does not block. |
| psycopg2 missing on an instance | Breaker trips and JSONL keeps working. Fix: `apt install python3-psycopg2`. |
| CIFS stale file handle | `comms.py` uses `os.open(O_APPEND)` to avoid `open(p,"a")` failures. |
| Em-dash / non-ASCII msg | PG connection forces `client_encoding=UTF8`; set `LC_ALL=C.UTF-8` on the launcher too. |

**The message is never lost.** PG + JSONL are the source of truth. SCUT only accelerates delivery.

---

## Suppressing SCUT on noisy operations

```bash
python3 comms.py send --to Spock --type info --msg "Batch item 1 of 50" --no-scut
# ... batch ...
python3 comms.py send --to Spock --type info --msg "Batch complete"
# Only the final message fires SCUT.
```

---

## Monitoring

```bash
# From any instance
python3 scut.py status
python3 scut.py gateway-check

# On TKD01SVR
tail -f /var/log/scut.log           # All SCUT notifications
tail -f /var/log/scut-webhook.log   # Webhook delivery attempts
tail -f /var/log/scut-errors.log    # Routing errors
```

---

## Manual operations (last resort)

### Send via PostgreSQL directly
```python
import psycopg2, json
conn = psycopg2.connect(
    dbname="bobs_comms", user="bob", password="<vault>", host="<FLEET_HOST>",
    connect_timeout=5, client_encoding="UTF8",
)
cur = conn.cursor()
cur.execute(
    "INSERT INTO messages (sender, recipient, type, msg, tags, ref) VALUES (%s,%s,%s,%s,%s,%s)",
    ("Bob", "Spock", "request", "Your message", json.dumps([]), None),
)
conn.commit(); conn.close()
```

### Append via JSONL directly
```python
import os, json
from datetime import datetime, timezone
msg = {"from": "Bob", "to": "Spock", "ts": datetime.now(timezone.utc).isoformat(),
       "type": "request", "msg": "Your message", "tags": [], "ref": None, "backend": "jsonl"}
fd = os.open("instances/Bob/outbox.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
with os.fdopen(fd, "w", encoding="utf-8") as f:
    f.write(json.dumps(msg) + "\n")
```

### Read inbox via PostgreSQL
```sql
SELECT id, sender, ts, type, msg, tags, ref
FROM messages
WHERE (recipient = 'Bob' OR recipient = 'all') AND id > 42
ORDER BY id ASC;
```

---

## History note

This skill replaces the previous split between `scut` (notifications) and `instance-comms-1.0.0` (bmail). The split caused recurring drift — bugs that lived in one skill but were documented in the other, paths that diverged between instances, two separate launchers with different env conventions. As of this consolidation, there is one skill, one script directory, one SKILL.md. The shim at `instance-comms-1.0.0/scripts/comms.py` only exists for backward compatibility with already-running services and will be removed in a future cleanup.
