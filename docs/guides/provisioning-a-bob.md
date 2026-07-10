# Provisioning a Bob from Scratch

This guide covers manually provisioning a new bob instance on a fresh Linux host. Use this when you need a clean start — not a clone of an existing instance. For cloning an existing bob, see `clone-a-bob.md`.

---

## Prerequisites

- Fresh Linux host (LXC container or VM), SSH accessible
- OpenClaw installed on the host OS
- Shared storage mounted (e.g., `/mnt/clawdbot-home`) with access to skills, templates, and vault scripts
- Vault key for the fleet (see step 3 — generate a new one for this instance)
- Decided on: instance name (e.g., `Milo`), hostname (e.g., `tkd04ai`), serial (optional)

---

## Step 1: OS User Setup

Every bob runs as OS user `bob`. This is the same username on every Linux host in the fleet. Instance identity is NOT carried by the OS username — it's carried by the hostname and the `OPENCLAW_INSTANCE` environment variable.

```bash
# As root on the new host:
useradd -m -s /bin/bash bob
passwd bob            # set a strong password or use SSH keys
usermod -aG sudo bob  # if the host needs bob to run sudo commands
```

Verify:
```bash
id bob
ls /home/bob
```

---

## Step 2: Environment Variables

Set `CLAWDBOT_HOME` and `OPENCLAW_INSTANCE` in two places: the shell profile AND the systemd unit (added in a later step). Both are required — the shell profile covers interactive sessions; the systemd unit covers the daemon.

**Shell profile** (`/home/bob/.bashrc` or `.profile`):
```bash
export CLAWDBOT_HOME=/mnt/clawdbot-home
export OPENCLAW_INSTANCE=YourBobName   # e.g., Milo
```

Reload:
```bash
source /home/bob/.bashrc
```

Confirm:
```bash
echo $CLAWDBOT_HOME
echo $OPENCLAW_INSTANCE
```

---

## Step 3: Vault Key

Each bob has its own vault key — a 64-character hex string stored locally. This key unlocks the fleet vault for this instance. It must never be placed in shared storage.

Generate and write the key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))" > /home/bob/.openclaw-vault-key
chmod 600 /home/bob/.openclaw-vault-key
chown bob:bob /home/bob/.openclaw-vault-key
```

Verify permissions:
```bash
ls -la /home/bob/.openclaw-vault-key
# Should show: -rw------- 1 bob bob ...
```

> **Never copy this file to shared storage.** If you need to back it up, do so in a separate, access-controlled location (e.g., a password manager or offline key store). The key can be redistributed manually if the host is lost.

---

## Step 4: Install OpenClaw

Follow the standard OpenClaw install for your platform. As user `bob`:

```bash
# Download and run the installer (adjust URL/version as needed)
curl -fsSL https://install.openclaw.ai | bash

# Or install from a local package:
openclaw install
```

After install, confirm the binary is available:
```bash
openclaw --version
```

Initialize the OpenClaw workspace:
```bash
openclaw init
```

This creates `/home/bob/.openclaw/` with the default directory structure.

---

## Step 5: Configure openclaw.json

Edit `/home/bob/.openclaw/openclaw.json` to set this instance's identity and port:

```json
{
  "instance": "YourBobName",
  "port": 3100,
  "clawdbotHome": "/mnt/clawdbot-home"
}
```

Adjust `port` if this host shares a network range with other bobs and ports need to be distinct.

---

## Step 6: Fleet-Sync

Fleet-sync mirrors shared skills and configuration from shared storage to the local workspace.

Copy the fleet-sync script from shared storage:
```bash
cp $CLAWDBOT_HOME/scripts/fleet-sync.sh /home/bob/.openclaw/scripts/
chmod +x /home/bob/.openclaw/scripts/fleet-sync.sh
```

Configure it if it has a local config (e.g., set `INSTANCE_NAME`, confirm `CLAWDBOT_HOME`).

Run once to populate skills:
```bash
/home/bob/.openclaw/scripts/fleet-sync.sh
```

Verify skills are present:
```bash
ls $CLAWDBOT_HOME/skills/
```

---

## Step 7: bmail / SCUT Setup

bmail (SCUT — Subspace Communications Unit Technology) is the inter-instance messaging system. It uses a PostgreSQL backend with a JSONL fallback.

**Install the Python dependency:**
```bash
pip3 install psycopg2-binary
```

**Set vault keys for the database:**
```bash
python3 $CLAWDBOT_HOME/skills/vault/scripts/vault.py set db/host <postgres-host>
python3 $CLAWDBOT_HOME/skills/vault/scripts/vault.py set db/port 5432
python3 $CLAWDBOT_HOME/skills/vault/scripts/vault.py set db/name <database-name>
python3 $CLAWDBOT_HOME/skills/vault/scripts/vault.py set db/user <username>
python3 $CLAWDBOT_HOME/skills/vault/scripts/vault.py set db/password <password>
```

**Verify connectivity:**
```bash
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py health
```

Expected output: `OK` or a summary showing Postgres connected and JSONL fallback path.

---

## Step 8: SCUT Listener (systemd)

The SCUT listener runs as a systemd service so it persists across reboots and receives incoming messages.

Create the service file at `/etc/systemd/system/scut-listener.service`:

```ini
[Unit]
Description=SCUT Listener for %i
After=network.target

[Service]
User=bob
EnvironmentFile=/etc/openclaw-env
Environment=OPENCLAW_INSTANCE=YourBobName
Environment=CLAWDBOT_HOME=/mnt/clawdbot-home
ExecStart=/usr/bin/python3 /mnt/clawdbot-home/skills/scut/scripts/listener.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

> **Important:** Set `OPENCLAW_INSTANCE` in the unit, not just in the shell profile. The daemon does not inherit shell environment.

Enable and start:
```bash
systemctl daemon-reload
systemctl enable scut-listener
systemctl start scut-listener
systemctl status scut-listener
```

---

## Step 9: Identity Files

Copy templates from shared storage:
```bash
cp $CLAWDBOT_HOME/templates/IDENTITY.md /home/bob/.openclaw/workspace/instances/YourBobName/IDENTITY.md
cp $CLAWDBOT_HOME/templates/SOUL.md     /home/bob/.openclaw/workspace/instances/YourBobName/SOUL.md
cp $CLAWDBOT_HOME/templates/MEMORY.md   /home/bob/.openclaw/workspace/memory/MEMORY.md
```

Edit `IDENTITY.md` and fill in:
- Name and serial
- Host and IP
- Role focus
- Vibe and emoji
- Heartbeat offset and interval

Edit `MEMORY.md` and fill in:
- Who this bob is
- Who they're helping (owner info)
- Any known infrastructure facts relevant to this instance

---

## Step 10: First Heartbeat

Start OpenClaw:
```bash
openclaw start
```

Trigger a manual heartbeat or send a test message from another bob:
```bash
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py send --to YourBobName --message "ping"
```

Check that the message was received:
```bash
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py check
```

---

## Step 11: Protocol Inspection

Once the instance is stable (running for at least one heartbeat cycle), run a protocol inspection against FLEET-PROTOCOL.md. Use the `inspection-report.md` template in `templates/`.

Check the 14 articles and file the completed report in:
```
$CLAWDBOT_HOME/instances/YourBobName/inspection-reports/
```

Resolve any findings rated FAIL or WARN before the instance takes on live duties.
