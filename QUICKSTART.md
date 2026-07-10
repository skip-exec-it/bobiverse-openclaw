# Quick Start — Build Your First Bob

This guide takes you from zero to a running fleet bob. By the end you'll have one agent online, communicating, and heartbeating.

## Prerequisites

- [OpenClaw](https://openclaw.ai) installed on your host
- Python 3.9+ with `psycopg2` (`pip install psycopg2-binary`)
- A PostgreSQL instance for bmail (can be local; see [`docs/architecture/comms-model.md`](docs/architecture/comms-model.md))
- A shared storage mount (NFS, CIFS/SMB, or local directory — OneDrive on Windows)
- An AI provider account (OpenRouter free tier is enough to start)

---

## Step 1 — Set up shared storage

The fleet uses shared storage as a cold-standby backup and skill distribution layer. All bobs read from the same shared skill library; each bob writes its identity and memory locally and pushes to shared storage each heartbeat.

```
<SHARED_ROOT>/
├── shared/          ← Protocol docs, SOUL.md, USER.md, skills
├── skills/          ← Shared skill library (mirrored locally by fleet-sync)
└── instances/
    └── <Name>/      ← Per-bob identity, memory, logs (pushed each heartbeat)
```

On Linux: mount as `/mnt/fleet-home` (CIFS/NFS) or set `CLAWDBOT_HOME` to a local directory.
On Windows: a OneDrive-synced folder works well.

Set the environment variable:
```bash
export CLAWDBOT_HOME=/mnt/fleet-home   # Linux
# or
$env:CLAWDBOT_HOME="C:\Users\you\OneDrive\FleetHome"  # Windows
```

Add it to your shell profile or systemd unit so it persists.

---

## Step 2 — Set up the vault

The vault stores fleet secrets (bmail password, API keys) encrypted at rest. The master key lives only on the bob's local disk — never in shared storage.

```bash
# Generate a vault key (64 hex chars)
python3 -c "import secrets; print(secrets.token_hex(32))" > ~/.openclaw-vault-key
chmod 600 ~/.openclaw-vault-key

# Initialize vault
python3 $CLAWDBOT_HOME/skills/vault/scripts/vault.py set db/bmail-host <your-pg-host>
python3 $CLAWDBOT_HOME/skills/vault/scripts/vault.py set db/bmail-port 5432
python3 $CLAWDBOT_HOME/skills/vault/scripts/vault.py set db/bmail-dbname bobs_comms
python3 $CLAWDBOT_HOME/skills/vault/scripts/vault.py set db/bmail-user bob
python3 $CLAWDBOT_HOME/skills/vault/scripts/vault.py set db/bmail-password <your-pg-password>
```

See [`skills/vault/`](skills/vault/) for full vault documentation.

---

## Step 3 — Create the bmail database

```sql
CREATE DATABASE bobs_comms;
\c bobs_comms

CREATE TABLE messages (
    id        SERIAL PRIMARY KEY,
    sender    VARCHAR(50),
    recipient VARCHAR(50),
    ts        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    type      VARCHAR(50),
    msg       TEXT,
    tags      JSONB,
    ref       TEXT
);
```

---

## Step 4 — Name your bob and create its identity

Pick a name. Copy the templates:

```bash
export OPENCLAW_INSTANCE=YourBobName
mkdir -p $CLAWDBOT_HOME/instances/$OPENCLAW_INSTANCE/logs

cp templates/IDENTITY.md $CLAWDBOT_HOME/instances/$OPENCLAW_INSTANCE/IDENTITY.md
cp templates/MEMORY.md   $CLAWDBOT_HOME/instances/$OPENCLAW_INSTANCE/MEMORY.md
cp templates/SOUL.md     ~/.openclaw/workspace/SOUL.md
cp templates/AGENTS.md   ~/.openclaw/workspace/AGENTS.md
cp templates/USER.md     ~/.openclaw/workspace/USER.md
```

Edit `IDENTITY.md` — fill in the name, role, host, and vibe. This file is who your bob claims to be. It's read at every session start.

---

## Step 5 — Configure OpenClaw

Edit `~/.openclaw/openclaw.json`. Key settings:

```json5
{
  "workspace": "/home/bob/.openclaw/workspace",   // local path, never the shared mount
  "agents": {
    "defaults": {
      "model": {
        "primary": "openrouter/google/gemma-4-31b-it:free",
        "fallbacks": ["openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"]
      },
      "heartbeat": {
        "model": "openrouter/google/gemma-4-31b-it:free"  // cheapest available
      }
    }
  },
  "session": {
    "reset": { "mode": "idle" }  // prevents nightly context wipe
  }
}
```

See [`docs/architecture/model-policy.md`](docs/architecture/model-policy.md) for model selection guidance.

---

## Step 6 — Set up fleet-sync

Fleet-sync mirrors the shared skill library to your local workspace so the gateway loads skills from disk, not the live mount.

```bash
# Install cron (Linux)
cp bootstrap/fleet-sync.sh /usr/local/bin/fleet-sync.sh
chmod +x /usr/local/bin/fleet-sync.sh
(crontab -l; echo "*/30 * * * * CLAWDBOT_HOME=$CLAWDBOT_HOME /usr/local/bin/fleet-sync.sh") | crontab -

# Run once now
/usr/local/bin/fleet-sync.sh
```

---

## Step 7 — Start the SCUT listener

SCUT is the real-time wake mechanism. When a peer sends a request, SCUT wakes your bob immediately rather than waiting for the next heartbeat.

```bash
# Install as a systemd user service (Linux)
cp bootstrap/systemd/scut-listener.service ~/.config/systemd/user/
# Edit it: set OPENCLAW_INSTANCE=YourBobName

systemctl --user daemon-reload
systemctl --user enable --now scut-listener.service
```

Verify: `ss -tlnp | grep 8514` should show a listener.

---

## Step 8 — Start the gateway

```bash
openclaw gateway start
# or as a systemd user service:
cp bootstrap/systemd/openclaw-gateway.service ~/.config/systemd/user/
systemctl --user enable --now openclaw-gateway.service
```

---

## Step 9 — Send your first heartbeat

In a session with your bob, say:
> "Run your first heartbeat."

A healthy heartbeat:
1. Checks the bmail inbox
2. Reviews the CHECKLIST
3. Updates the daily log
4. Pushes identity/memory/logs to shared storage
5. Replies `HEARTBEAT_OK`

---

## Next Steps

- Add more bobs: follow [`docs/guides/provisioning-a-bob.md`](docs/guides/provisioning-a-bob.md) or use `bootstrap/clone-a-bob.sh` for LXC clones
- Read the full Protocol: [`docs/protocol/fleet-protocol.md`](docs/protocol/fleet-protocol.md)
- Run an inspection: [`docs/concepts/inspection-rating.md`](docs/concepts/inspection-rating.md)
