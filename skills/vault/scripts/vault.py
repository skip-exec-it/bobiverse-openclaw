#!/usr/bin/env python3
"""
OpenClaw Vault — Encrypted Credential Store

AES-256 encrypted JSON vault for sharing secrets across OpenClaw instances.
The vault file syncs via OneDrive; the master key stays local per machine.

Commands:
  vault.py init                          Create a new vault with a generated key
  vault.py get <key>                     Retrieve a secret (prints value only)
  vault.py get <key> --json              Retrieve with metadata as JSON
  vault.py set <key> <value> [--desc ""] Store/update a secret
  vault.py delete <key>                  Remove a secret
  vault.py list                          List all secret keys (no values)
  vault.py list --show                   List keys with values (careful!)
  vault.py export                        Dump all secrets as JSON (for backup)
  vault.py import <file.json>            Import secrets from JSON backup
  vault.py rotate-key                    Re-encrypt vault with a new key

Environment:
  OPENCLAW_VAULT_KEY      Master key (hex string) — overrides key file
  OPENCLAW_VAULT_KEYFILE  Path to key file (default: ~/.openclaw-vault-key)
  OPENCLAW_VAULT_FILE     Path to vault.dat (default: skills/vault/vault.dat)
  CLAWDBOT_HOME           Workspace root

Requirements: Python 3.8+ with standard library only (uses hashlib + AES-CTR via XOR)
              For proper AES: pip install cryptography (optional, auto-detected)

Security notes:
  - The master key file (~/.openclaw-vault-key) must NEVER be in OneDrive or git
  - vault.dat is safe to sync — it's encrypted at rest
  - Key rotation generates a new key and re-encrypts everything
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- Config ---

CLAWDBOT_HOME = os.environ.get("CLAWDBOT_HOME", "")

def _default_keyfile():
    """Default key file location — in user's home, NOT in shared workspace."""
    return Path.home() / ".openclaw-vault-key"

def _default_vaultfile():
    """Default vault file — in shared workspace."""
    if CLAWDBOT_HOME:
        return Path(CLAWDBOT_HOME) / "skills" / "vault" / "vault.dat"
    # Fallback: relative to script
    return Path(__file__).resolve().parent.parent / "vault.dat"

KEYFILE = Path(os.environ.get("OPENCLAW_VAULT_KEYFILE", str(_default_keyfile())))
VAULTFILE = Path(os.environ.get("OPENCLAW_VAULT_FILE", str(_default_vaultfile())))


# --- Crypto Layer ---
# Uses the `cryptography` package if available (proper AES-GCM).
# Falls back to HMAC-based encryption if not installed (still secure, just slower).

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def derive_key(master_key_hex: str) -> bytes:
    """Derive a 256-bit encryption key from the master key using PBKDF2."""
    master_bytes = bytes.fromhex(master_key_hex.strip())
    # Use a fixed salt (since the master key is already high-entropy random)
    salt = b"openclaw-vault-v1"
    return hashlib.pbkdf2_hmac("sha256", master_bytes, salt, 100_000)


def encrypt(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt with AES-256-GCM (if available) or HMAC-CTR fallback."""
    if HAS_CRYPTO:
        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        return b"AES1" + nonce + ciphertext
    else:
        # Fallback: XOR stream cipher from HMAC-SHA256 (not ideal but works)
        nonce = secrets.token_bytes(16)
        stream = _hmac_stream(key, nonce, len(plaintext))
        ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream))
        mac = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
        return b"HMC1" + nonce + mac + ciphertext


def decrypt(data: bytes, key: bytes) -> bytes:
    """Decrypt vault data."""
    if data[:4] == b"AES1":
        if not HAS_CRYPTO:
            print("Error: Vault was encrypted with AES-GCM but 'cryptography' package is not installed.", file=sys.stderr)
            print("Install it: pip install cryptography", file=sys.stderr)
            sys.exit(1)
        nonce = data[4:16]
        ciphertext = data[16:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    elif data[:4] == b"HMC1":
        nonce = data[4:20]
        mac = data[20:52]
        ciphertext = data[52:]
        expected_mac = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected_mac):
            raise ValueError("Vault decryption failed — wrong key or corrupted file")
        stream = _hmac_stream(key, nonce, len(ciphertext))
        return bytes(a ^ b for a, b in zip(ciphertext, stream))
    else:
        raise ValueError(f"Unknown vault format: {data[:4]!r}")


def _hmac_stream(key: bytes, nonce: bytes, length: int) -> bytes:
    """Generate a pseudorandom byte stream using HMAC-SHA256 in counter mode."""
    stream = b""
    counter = 0
    while len(stream) < length:
        block = hmac.new(key, nonce + struct.pack(">I", counter), hashlib.sha256).digest()
        stream += block
        counter += 1
    return stream[:length]


# --- Key Management ---

def generate_master_key() -> str:
    """Generate a 256-bit random master key as hex string."""
    return secrets.token_hex(32)


def load_master_key() -> str:
    """Load master key from env var or key file."""
    # Method 1: Environment variable
    env_key = os.environ.get("OPENCLAW_VAULT_KEY")
    if env_key and len(env_key.strip()) >= 32:
        return env_key.strip()

    # Method 2: Key file
    if KEYFILE.exists():
        key = KEYFILE.read_text().strip()
        if len(key) >= 32:
            return key

    print(f"Error: No vault key found.", file=sys.stderr)
    print(f"  Set OPENCLAW_VAULT_KEY env var, or create key file at: {KEYFILE}", file=sys.stderr)
    print(f"  Run 'vault.py init' to create a new vault with a generated key.", file=sys.stderr)
    sys.exit(1)


def save_master_key(key_hex: str):
    """Save master key to local key file with restricted permissions."""
    KEYFILE.parent.mkdir(parents=True, exist_ok=True)

    if os.name == 'nt':
        # Windows: write file, then restrict ACL via icacls
        KEYFILE.write_text(key_hex)
        username = os.environ.get("USERNAME", "skipz")
        os.system(f'icacls "{KEYFILE}" /inheritance:r /grant:r "{username}:F" >nul 2>&1')
    else:
        # Linux: create with restricted permissions
        fd = os.open(str(KEYFILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(key_hex)

    print(f"Master key saved to: {KEYFILE}")
    print(f"  This file must NEVER be shared, synced, or committed to git.")


# --- Vault Operations ---

def load_vault(key: bytes) -> dict:
    """Load and decrypt the vault."""
    if not VAULTFILE.exists():
        return {"secrets": {}, "metadata": {"created": now_iso(), "version": 1}}

    data = VAULTFILE.read_bytes()
    plaintext = decrypt(data, key)
    return json.loads(plaintext.decode("utf-8"))


def save_vault(vault: dict, key: bytes):
    """Encrypt and save the vault."""
    VAULTFILE.parent.mkdir(parents=True, exist_ok=True)
    vault["metadata"]["updated"] = now_iso()
    plaintext = json.dumps(vault, indent=2).encode("utf-8")
    encrypted = encrypt(plaintext, key)

    # Atomic write
    tmp = VAULTFILE.with_suffix(".tmp")
    tmp.write_bytes(encrypted)
    if os.name == 'nt' and VAULTFILE.exists():
        VAULTFILE.unlink()
    tmp.rename(VAULTFILE)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# --- Commands ---

def cmd_init():
    """Create a new vault with a generated master key."""
    if VAULTFILE.exists():
        print(f"Vault already exists at: {VAULTFILE}")
        print("Use 'rotate-key' to change the key, or delete vault.dat to start fresh.")
        sys.exit(1)

    master_key = generate_master_key()
    save_master_key(master_key)

    key = derive_key(master_key)
    vault = {
        "secrets": {},
        "metadata": {
            "created": now_iso(),
            "version": 1,
            "crypto": "AES-256-GCM" if HAS_CRYPTO else "HMAC-CTR-SHA256",
        }
    }
    save_vault(vault, key)

    print(f"\nVault created at: {VAULTFILE}")
    print(f"Key saved to: {KEYFILE}")
    print(f"Encryption: {'AES-256-GCM' if HAS_CRYPTO else 'HMAC-CTR (install cryptography for AES)'}")
    print(f"\nNext: Copy {KEYFILE} to each instance machine (securely, not via OneDrive).")
    print(f"      Then set secrets: vault.py set db/bmail-password <BMAIL_PASSWORD>")


def cmd_get(secret_key, as_json=False):
    """Retrieve a secret."""
    master = load_master_key()
    key = derive_key(master)
    vault = load_vault(key)

    if secret_key not in vault["secrets"]:
        print(f"Error: Secret '{secret_key}' not found.", file=sys.stderr)
        sys.exit(1)

    entry = vault["secrets"][secret_key]
    if as_json:
        print(json.dumps(entry))
    else:
        print(entry["value"])


def cmd_set(secret_key, value, description=""):
    """Store or update a secret."""
    master = load_master_key()
    key = derive_key(master)
    vault = load_vault(key)

    is_update = secret_key in vault["secrets"]
    vault["secrets"][secret_key] = {
        "value": value,
        "description": description,
        "updated": now_iso(),
        "updated_by": os.environ.get("OPENCLAW_INSTANCE", os.environ.get("COMPUTERNAME", "unknown")),
    }
    save_vault(vault, key)
    action = "Updated" if is_update else "Stored"
    print(f"{action}: {secret_key}")


def cmd_delete(secret_key):
    """Remove a secret."""
    master = load_master_key()
    key = derive_key(master)
    vault = load_vault(key)

    if secret_key not in vault["secrets"]:
        print(f"Error: Secret '{secret_key}' not found.", file=sys.stderr)
        sys.exit(1)

    del vault["secrets"][secret_key]
    save_vault(vault, key)
    print(f"Deleted: {secret_key}")


def cmd_list(show_values=False):
    """List all secret keys."""
    master = load_master_key()
    key = derive_key(master)
    vault = load_vault(key)

    if not vault["secrets"]:
        print("Vault is empty.")
        return

    print(f"Vault: {len(vault['secrets'])} secret(s)")
    print(f"Crypto: {vault.get('metadata', {}).get('crypto', 'unknown')}")
    print("-" * 50)
    for k, v in sorted(vault["secrets"].items()):
        desc = v.get("description", "")
        if show_values:
            print(f"  {k:30s} = {v['value']}")
            if desc:
                print(f"  {'':30s}   ({desc})")
        else:
            masked = v["value"][:2] + "***" if len(v["value"]) > 2 else "***"
            line = f"  {k:30s} [{masked}]"
            if desc:
                line += f"  — {desc}"
            print(line)


def cmd_export():
    """Export all secrets as JSON (for backup)."""
    master = load_master_key()
    key = derive_key(master)
    vault = load_vault(key)
    print(json.dumps(vault["secrets"], indent=2))


def cmd_import(filepath):
    """Import secrets from a JSON file."""
    master = load_master_key()
    key = derive_key(master)
    vault = load_vault(key)

    with open(filepath) as f:
        new_secrets = json.loads(f.read())

    count = 0
    for k, v in new_secrets.items():
        if isinstance(v, dict) and "value" in v:
            vault["secrets"][k] = v
        elif isinstance(v, str):
            vault["secrets"][k] = {"value": v, "description": "", "updated": now_iso()}
        count += 1

    save_vault(vault, key)
    print(f"Imported {count} secret(s)")


def cmd_rotate_key():
    """Generate a new key and re-encrypt the vault."""
    old_master = load_master_key()
    old_key = derive_key(old_master)
    vault = load_vault(old_key)

    new_master = generate_master_key()
    new_key = derive_key(new_master)
    save_vault(vault, new_key)
    save_master_key(new_master)

    print(f"Key rotated. New key saved to: {KEYFILE}")
    print(f"IMPORTANT: Copy the new key file to ALL instance machines.")


# --- Main ---

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init":
        cmd_init()
    elif cmd == "get":
        if len(sys.argv) < 3:
            print("Usage: vault.py get <key> [--json]"); sys.exit(1)
        cmd_get(sys.argv[2], "--json" in sys.argv)
    elif cmd == "set":
        if len(sys.argv) < 4:
            print("Usage: vault.py set <key> <value> [--desc \"description\"]"); sys.exit(1)
        desc = ""
        for i, arg in enumerate(sys.argv):
            if arg == "--desc" and i + 1 < len(sys.argv):
                desc = sys.argv[i + 1]
        cmd_set(sys.argv[2], sys.argv[3], desc)
    elif cmd == "delete":
        if len(sys.argv) < 3:
            print("Usage: vault.py delete <key>"); sys.exit(1)
        cmd_delete(sys.argv[2])
    elif cmd == "list":
        cmd_list("--show" in sys.argv)
    elif cmd == "export":
        cmd_export()
    elif cmd == "import":
        if len(sys.argv) < 3:
            print("Usage: vault.py import <file.json>"); sys.exit(1)
        cmd_import(sys.argv[2])
    elif cmd == "rotate-key":
        cmd_rotate_key()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
