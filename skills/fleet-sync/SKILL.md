# Fleet-Sync Skill

**Purpose:** Mirror the shared skill library from shared storage into each bob's local workspace. The OpenClaw gateway loads skills from the local mirror, never from the live shared mount.

**Scripts:**
- `../../bootstrap/fleet-sync.sh` (Linux)
- `../../bootstrap/fleet-sync.ps1` (Windows)

**Manifest:** `manifest.json` — controls which paths are synced

## Setup

### Linux (cron)

```bash
# Install
cp ../../bootstrap/fleet-sync.sh /usr/local/bin/fleet-sync.sh
chmod +x /usr/local/bin/fleet-sync.sh

# Add to crontab (offset from heartbeat to avoid collision)
# Example: heartbeat at :00/:30, fleet-sync at :15/:45
(crontab -l; echo "15,45 * * * * CLAWDBOT_HOME=/mnt/fleet-home /usr/local/bin/fleet-sync.sh") | crontab -

# Run once immediately
CLAWDBOT_HOME=/mnt/fleet-home /usr/local/bin/fleet-sync.sh
```

### Windows (Task Scheduler)

```powershell
# Run once to verify
$env:CLAWDBOT_HOME = "C:\path\to\FleetHome"
pwsh -File fleet-sync.ps1

# Schedule via Task Scheduler:
# Action: pwsh.exe -File "C:\path\to\fleet-sync.ps1"
# Trigger: Every 30 minutes
# Run As: your Windows user
```

## Verify

```bash
# Local mirror exists
[ -d "$HOME/.openclaw/workspace/skills" ] && echo "PASS: mirror exists"

# Mirror was updated recently (within 90 min)
find "$HOME/.openclaw/workspace/skills" -maxdepth 1 -type d -mmin -90 | grep -q . \
  && echo "PASS: mirror fresh" || echo "WARN: mirror stale"

# Gateway loads skills from local, not shared mount
openclaw skills list 2>/dev/null | grep -qi '/mnt/' \
  && echo "FAIL: loading from mount" || echo "PASS: loading from local"
```

## Manifest

`manifest.json` controls what gets synced. Default: all of `skills/` and `shared/` from `CLAWDBOT_HOME`.

```json
{
  "sync": [
    { "src": "skills/",  "dst": "skills/",  "delete": true  },
    { "src": "shared/",  "dst": "./",       "delete": false }
  ],
  "exclude": ["__pycache__", "*.pyc", "node_modules", "vault.dat"]
}
```
