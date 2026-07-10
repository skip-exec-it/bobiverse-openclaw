---
name: vault
description: "Encrypted credential store for sharing secrets across OpenClaw instances. AES-256 encrypted vault syncs via OneDrive, master key stays local. Triggers on 'get password', 'store API key', 'vault set', 'credentials', 'rotate key'."
metadata: { "openclaw": { "emoji": "🔐" } }
---

# OpenClaw Vault — Encrypted Credential Store

Secrets encrypted at rest, synced across all instances via OneDrive, unlocked only by a local key that never leaves the machine.

## How It Works

```
vault.dat (encrypted, in OneDrive)  ←→  vault.py  ←→  .openclaw-vault-key (local, never synced)
         ↑                                                        ↑
  Safe to sync everywhere              Must be copied manually to each machine
  AES-256-GCM encrypted                256-bit random hex string
  Useless without the key              Useless without the vault
```

**Key split:** The encrypted vault file lives in the shared workspace (`skills/vault/vault.dat`) and syncs via OneDrive. The master decryption key lives at `~/.openclaw-vault-key` on each machine — outside OneDrive, outside git, outside any sync path. Both pieces are required to read secrets.

---

## Quick Reference

### Store a Secret
```powershell
python3 "$env:CLAWDBOT_HOME\skills\vault\scripts\vault.py" set db/bmail-password <BMAIL_PASSWORD> --desc "PostgreSQL bmail-db password"
```

### Retrieve a Secret
```powershell
# Value only (for piping into scripts)
python3 "$env:CLAWDBOT_HOME\skills\vault\scripts\vault.py" get db/bmail-password

# With metadata as JSON
python3 "$env:CLAWDBOT_HOME\skills\vault\scripts\vault.py" get db/bmail-password --json
```

### List All Secrets
```powershell
# Keys only (masked values)
python3 "$env:CLAWDBOT_HOME\skills\vault\scripts\vault.py" list

# Keys with values (careful — prints plaintext!)
python3 "$env:CLAWDBOT_HOME\skills\vault\scripts\vault.py" list --show
```

---

## Commands

```
vault.py init                          Create a new vault + generate master key
vault.py get <key> [--json]            Retrieve a secret
vault.py set <key> <value> [--desc ""] Store or update a secret
vault.py delete <key>                  Remove a secret
vault.py list [--show]                 List keys (--show reveals values)
vault.py export                        Dump all secrets as JSON (backup)
vault.py import <file.json>            Import secrets from JSON backup
vault.py rotate-key                    Re-encrypt vault with a new master key
```

---

## Key Naming Convention

Use `/` as a separator to organize secrets by system:

```
db/bmail-host           → bmail-db
db/bmail-port           → 5432
db/bmail-user           → bob
db/bmail-password       → <BMAIL_PASSWORD>
db/bmail-dbname         → bobs_comms
api/openai-key          → sk-...
api/anthropic-key       → sk-ant-...
api/google-key          → AIza...
scut/syslog-host        → TKD01SVR
scut/syslog-port        → 514
```

This way `vault.py list` gives a clean, scannable inventory.

---

## Using Vault from Other Scripts

### Python — Direct Import
```python
import subprocess, sys

def vault_get(key):
    """Retrieve a secret from the OpenClaw vault."""
    vault_script = os.path.join(
        os.environ.get("CLAWDBOT_HOME", ""),
        "skills", "vault", "scripts", "vault.py"
    )
    result = subprocess.run(
        [sys.executable, vault_script, "get", key],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None
```

### Python — In comms.py, scut.py, etc.
Scripts that need credentials should call `vault_get()` at startup to populate their config:
```python
DB_CONFIG = {
    "host": vault_get("db/bmail-host") or "bmail-db",
    "port": vault_get("db/bmail-port") or "5432",
    "dbname": vault_get("db/bmail-dbname") or "bobs_comms",
    "user": vault_get("db/bmail-user") or "bob",
    "password": vault_get("db/bmail-password") or "",
    "connect_timeout": "5",
}
```
The `or` fallback ensures the script still works if the vault is unavailable — it just won't have the secret.

### PowerShell
```powershell
$dbPassword = python3 "$env:CLAWDBOT_HOME\skills\vault\scripts\vault.py" get db/bmail-password
```

### Bash
```bash
db_password=$(python3 "$CLAWDBOT_HOME/skills/vault/scripts/vault.py" get db/bmail-password)
```

---

## Initial Setup

### Step 1: Initialize the Vault (once, on any machine)
```powershell
python3 "$env:CLAWDBOT_HOME\skills\vault\scripts\vault.py" init
```
This creates:
- `~/.openclaw-vault-key` — local master key (256-bit hex)
- `skills/vault/vault.dat` — encrypted (empty) vault

### Step 2: Store Initial Secrets
```powershell
python3 vault.py set db/bmail-host bmail-db --desc "PostgreSQL bmail-db host (DNS)"
python3 vault.py set db/bmail-port 5432 --desc "PostgreSQL bmail-db port"
python3 vault.py set db/bmail-user bob --desc "PostgreSQL bmail-db user"
python3 vault.py set db/bmail-password <BMAIL_PASSWORD> --desc "PostgreSQL bmail-db password"
python3 vault.py set db/bmail-dbname bobs_comms --desc "PostgreSQL bmail-db database name"
```

### Step 3: Copy Key to Other Machines
The master key must be manually copied (NOT via OneDrive) to each instance:

```powershell
# On first machine — display the key
type "$env:USERPROFILE\.openclaw-vault-key"

# On other machines — paste it
Set-Content "$env:USERPROFILE\.openclaw-vault-key" "paste-the-hex-key-here"
```

Or for Linux:
```bash
echo "paste-the-hex-key-here" > ~/.openclaw-vault-key
chmod 600 ~/.openclaw-vault-key
```

**Secure transfer options:** USB stick, KeePass shared entry, encrypted email, or SSH from one machine to another.

### Step 4: Verify on Each Machine
```powershell
python3 "$env:CLAWDBOT_HOME\skills\vault\scripts\vault.py" list
```
Should show all stored keys. If it fails, the key file is missing or wrong.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCLAW_VAULT_KEY` | (none) | Master key as hex string — overrides key file |
| `OPENCLAW_VAULT_KEYFILE` | `~/.openclaw-vault-key` | Path to local key file |
| `OPENCLAW_VAULT_FILE` | `$CLAWDBOT_HOME/skills/vault/vault.dat` | Path to encrypted vault |
| `CLAWDBOT_HOME` | (required) | Workspace root |

---

## Security Model

| Property | Detail |
|----------|--------|
| Encryption | AES-256-GCM (with `cryptography` package) or HMAC-CTR-SHA256 (stdlib fallback) |
| Key derivation | PBKDF2-SHA256, 100,000 iterations |
| Master key | 256-bit random, stored at `~/.openclaw-vault-key` |
| Key file permissions | Windows: `icacls` restricted to current user. Linux: `chmod 600` |
| Vault file | Encrypted at rest, safe to sync via OneDrive/git |
| Atomic writes | Write to `.tmp`, rename — prevents corruption on crash |
| Key rotation | `rotate-key` generates a new key and re-encrypts everything |

---

## Key Rotation

If a key may be compromised, or periodically for hygiene:

```powershell
python3 "$env:CLAWDBOT_HOME\skills\vault\scripts\vault.py" rotate-key
```

This generates a new 256-bit master key, re-encrypts the vault, and saves the new key locally. **You must then copy the new key to all other instance machines** — the old key no longer works.

---

## Disaster Recovery

### Lost a machine's key file
Copy from another machine that still has it. The vault.dat is the same everywhere (OneDrive synced).

### All key files lost
If you still have a `vault.py export` backup (plaintext JSON), you can:
1. Run `vault.py init` to create a new vault with a new key
2. Run `vault.py import backup.json` to restore secrets
3. Copy the new key to all machines

### Vault.dat corrupted
The `.dat` file is atomic-written (tmp + rename), so corruption is unlikely. If it happens:
1. Check OneDrive version history for a previous copy
2. Or restore from `vault.py export` backup

---

## What NOT to Store

- The master key itself (circular dependency)
- Temporary tokens that expire in minutes (not worth the overhead)
- Secrets that only one instance needs and never shares (use local env vars instead)

**DO store:** Database passwords, API keys, shared service credentials, webhook secrets — anything multiple instances need access to.
