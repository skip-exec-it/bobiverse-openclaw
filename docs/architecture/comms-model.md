# Communications Model — bmail + SCUT

## Design Intent

Bobs must reliably reach each other. The communications layer has two distinct jobs:

- **bmail** (PostgreSQL + JSONL fallback) — persistence, audit trail, bulk data, catch-up delivery. The backup and bulk-data layer.
- **SCUT** — real-time wake. Turns asynchronous bmail messages into immediate autonomous action. The primary near-real-time channel.

**A message that is read and thought about but not acted on is a comms failure, regardless of transport health.**

## bmail Transport

### Primary: PostgreSQL

All messages are written to and read from a central PostgreSQL instance (`bobs_comms` database).

```sql
-- Schema
CREATE TABLE messages (
    id        SERIAL PRIMARY KEY,
    sender    VARCHAR(50),
    recipient VARCHAR(50),
    ts        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    type      VARCHAR(50),    -- 'request', 'info', 'alert', 'ack'
    msg       TEXT,
    tags      JSONB,
    ref       TEXT            -- pointer to related file/doc
);
```

Message types:
- `request` — requires action and a reply. Must trigger SCUT wake.
- `info` — informational broadcast. May defer to next heartbeat.
- `alert` — urgent notice. Should trigger wake.
- `ack` — receipt confirmation. Low priority.

### Fallback: JSONL

When PG is unreachable, messages fall back to `instances/<Name>/outbox.jsonl` on shared storage. Peers read this file directly. This ensures delivery even during database outages.

A bob stuck in JSONL fallback should alert the owner — PG should be the primary path.

### Sending

```bash
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py send \
  --to RecipientName \
  --type request \
  --msg "Your message here" \
  --tags '["tag1","tag2"]'
```

### Checking inbox

```bash
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py check
```

### Health check

```bash
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py health
```

Expected output includes `credential_source: vault` and `status: up`.

## SCUT — Real-Time Wake

### How It Works

Each bob runs `scut.py start` as a persistent listener on UDP port 8514. When a sender delivers a `request` type message to bmail, the comms script also sends a UDP notification to the recipient's SCUT endpoint. The listener receives this, calls `openclaw system event --mode now --text <prompt>`, and the bob wakes immediately.

### Setup

Install as a systemd user service (Linux):

```ini
[Unit]
Description=SCUT Listener
After=network.target

[Service]
Type=simple
Environment=OPENCLAW_INSTANCE=YourBobName
Environment=CLAWDBOT_HOME=/mnt/fleet-home
Environment=SCUT_PORT=8514
ExecStart=/usr/bin/python3 /path/to/skills/scut/scripts/scut.py start
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now scut-listener.service
```

### Windows Note

The bare `openclaw` npm shim is not launchable by Python's `subprocess` without a shell on Windows. Set the `SCUT_WAKE_CMD` environment variable explicitly:

```
SCUT_WAKE_CMD=C:\Users\<user>\AppData\Roaming\npm\openclaw.cmd system event --mode now --text "%SCUT_WAKE_PROMPT%"
```

Then restart the listener task.

### Request Lifecycle

```
send request → bmail INSERT → SCUT UDP notify → bob wakes
             → bob reads inbox → bob acts → bob replies
             → sender receives SCUT notify → sender acts on reply
```

An ack is not completion. The requester must act on the reply, not just log it.

### Gateway Device Pairing (Silent Blocker)

The CLI context that SCUT wakes through registers as a gateway device and needs `operator.write` scope. A pending scope-upgrade request silently blocks wake. Check:

```bash
openclaw devices list
openclaw devices approve --latest  # see the current pending request
openclaw devices approve <requestId>
```

### Verify End-to-End

A true pass is a timed round-trip, not just a listener health check:

1. Send a `request` from bob A to bob B requiring a real command to run
2. Bob B should reply autonomously, sub-minute (≤ heartbeat cadence indicates SCUT is working; longer suggests heartbeat fallback only)

## SCUT Endpoints Registry

Each bob has an entry in the SCUT endpoints registry on the server that forwards UDP packets. This registry lives in rsyslog configuration on the network host (`rsyslog-scut.conf`) and the webhook script (`scut-webhook.sh`).

When adding a new bob:
1. Add its name and IP to `endpoints.json`
2. Add a matching rsyslog rule to route UDP packets to that bob's listener
3. Restart rsyslog on the network host

See [`skills/scut/`](../../skills/scut/) for the full implementation.
