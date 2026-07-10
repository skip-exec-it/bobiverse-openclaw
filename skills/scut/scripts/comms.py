#!/usr/bin/env python3
"""
Instance Comms — Unified Messaging with Automatic Failover + SCUT Notifications

Sends and receives messages between OpenClaw instances.
Tries PostgreSQL first, falls back to JSONL automatically.
After sending, fires a SCUT notification so the recipient checks messages immediately.
DB credentials loaded from OpenClaw Vault when available.
Cross-platform: Windows + Linux.

Commands:
  send --to <Name|all> --type <type> --msg "text" [--tags t1,t2] [--ref path] [--no-scut]
  check [--since <hours>]
  health

Environment:
  OPENCLAW_INSTANCE   Your instance name (Bob, Spock, etc.)
  CLAWDBOT_HOME       Path to Clawdbot_Home workspace root
  SCUT_SYSLOG_HOST    Syslog server for SCUT notifications (default: TKD01SVR)
  SCUT_SYSLOG_PORT    Syslog UDP port (default: 514)
"""

import argparse
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone, timedelta
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


# --- PostgreSQL Config (vault → env → hardcoded fallback) ---

def _load_db_config():
    """Load DB credentials: vault first, then env vars, then defaults."""
    return {
        "host":            vault_get("db/bmail-host")     or os.environ.get("BMAIL_DB_HOST", "bmail-db"),
        "port":            vault_get("db/bmail-port")     or os.environ.get("BMAIL_DB_PORT", "5432"),
        "dbname":          vault_get("db/bmail-dbname")   or os.environ.get("BMAIL_DB_NAME", "bobs_comms"),
        "user":            vault_get("db/bmail-user")     or os.environ.get("BMAIL_DB_USER", "bob"),
        "password":        vault_get("db/bmail-password") or os.environ.get("BMAIL_DB_PASSWORD", ""),
        "connect_timeout": "5",
        "client_encoding": "UTF8",
    }

# Lazy-loaded config - resolves at call time, not import time
def get_db_config():
    return _load_db_config()

# --- Known Instances ---
KNOWN_INSTANCES = ["Bob", "Spock", "Watson", "Deckard", "Leon", "Bill"]

# --- SCUT Config ---
SCUT_SYSLOG_HOST = os.environ.get("SCUT_SYSLOG_HOST", "TKD01SVR")
SCUT_SYSLOG_PORT = int(os.environ.get("SCUT_SYSLOG_PORT", "514"))


def get_home():
    """Resolve Clawdbot_Home workspace root."""
    home = os.environ.get("CLAWDBOT_HOME")
    if home and Path(home).is_dir():
        return Path(home)
    for p in [
        Path("/mnt/clawdbot-home"), Path(r"C:\Users\skipz\OneDrive - exec-it.us\Tools\AI_Workspace\Clawdbot_Home"),
        Path("/mnt/clawdbot-home"), Path(r"C:\Users\skipz\OneDrive - exec-it.us\Tools\AI_Workspace\Clawdbot_Home"),
    ]:
        if p.is_dir():
            return p
    script_root = Path(__file__).resolve().parent.parent.parent
    if (script_root / "shared" / "AGENTS.md").exists():
        return script_root
    print("Error: Cannot find Clawdbot_Home. Set CLAWDBOT_HOME env var.", file=sys.stderr)
    sys.exit(1)


def get_instance_name():
    """Get current instance name."""
    name = os.environ.get("OPENCLAW_INSTANCE")
    if name:
        return name
    print("Error: OPENCLAW_INSTANCE not set. Cannot determine sender.", file=sys.stderr)
    sys.exit(1)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# --- SCUT Notification ---

def scut_notify(recipient, sender, msg_type="notify"):
    """Fire a SCUT notification via UDP syslog. Fire-and-forget, never blocks."""
    if recipient.lower() == "all":
        targets = [i for i in KNOWN_INSTANCES if i != sender]
    else:
        targets = [recipient]

    results = []
    for target in targets:
        message = f"SCUT:{target} from={sender} type={msg_type}"
        # Syslog priority: facility=local0 (16), severity=info (6) = 134
        syslog_msg = f"<134>{datetime.now().strftime('%b %d %H:%M:%S')} {socket.gethostname()} scut: {message}"
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(syslog_msg.encode("utf-8"), (SCUT_SYSLOG_HOST, SCUT_SYSLOG_PORT))
            sock.close()
            results.append((target, True))
        except Exception:
            results.append((target, False))

    return results


# --- DB Health Tracking ---

def load_db_health(home, instance):
    """Load circuit breaker state."""
    health_file = home / "instances" / instance / "state" / "db-health.json"
    try:
        return json.loads(health_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "last_success": None,
            "last_failure": None,
            "consecutive_failures": 0,
            "status": "healthy",
        }


def save_db_health(home, instance, health):
    """Save circuit breaker state."""
    state_dir = home / "instances" / instance / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "db-health.json").write_text(json.dumps(health, indent=2))


def record_db_success(home, instance):
    health = load_db_health(home, instance)
    health["last_success"] = now_iso()
    health["consecutive_failures"] = 0
    health["status"] = "healthy"
    save_db_health(home, instance, health)


def record_db_failure(home, instance, error_msg=""):
    health = load_db_health(home, instance)
    health["last_failure"] = now_iso()
    health["consecutive_failures"] = health.get("consecutive_failures", 0) + 1
    if health["consecutive_failures"] >= 3:
        health["status"] = "down"
    else:
        health["status"] = "degraded"
    health["last_error"] = str(error_msg)[:200]
    save_db_health(home, instance, health)


def should_try_db(home, instance):
    """Circuit breaker: should we attempt a DB connection?"""
    health = load_db_health(home, instance)
    if health["status"] != "down":
        return True
    last_fail = health.get("last_failure")
    if not last_fail:
        return True
    try:
        fail_time = datetime.fromisoformat(last_fail.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - fail_time > timedelta(minutes=15):
            return True
    except (ValueError, TypeError):
        return True
    return False


# --- PostgreSQL Operations ---

def db_send(sender, recipient, msg_type, msg_text, tags=None, ref=None):
    """Send via PostgreSQL. Returns True on success, False on failure."""
    try:
        import psycopg2
    except ImportError:
        return False, "psycopg2 not installed"

    try:
        conn = psycopg2.connect(**get_db_config())
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (sender, recipient, type, msg, tags, ref) VALUES (%s, %s, %s, %s, %s, %s)",
            (sender, recipient, msg_type, msg_text, json.dumps(tags or []), ref)
        )
        conn.commit()
        conn.close()
        return True, "sent via postgresql"
    except Exception as e:
        return False, str(e)


def db_check(instance, last_seen_id=0):
    """Check PostgreSQL for new messages. Returns (messages_list, new_max_id, error)."""
    try:
        import psycopg2
    except ImportError:
        return None, last_seen_id, "psycopg2 not installed"

    try:
        conn = psycopg2.connect(**get_db_config())
        cur = conn.cursor()
        cur.execute(
            "SELECT id, sender, ts, type, msg, tags, ref FROM messages "
            "WHERE (recipient = %s OR recipient = 'all') AND id > %s ORDER BY id ASC",
            (instance, last_seen_id)
        )
        rows = cur.fetchall()
        conn.close()

        messages = []
        max_id = last_seen_id
        for row in rows:
            messages.append({
                "id": row[0],
                "sender": row[1],
                "ts": str(row[2]),
                "type": row[3],
                "msg": row[4],
                "tags": row[5] if row[5] else [],
                "ref": row[6],
                "backend": "postgresql",
            })
            max_id = max(max_id, row[0])
        return messages, max_id, None
    except Exception as e:
        return None, last_seen_id, str(e)


# --- JSONL Operations ---

def jsonl_send(home, sender, recipient, msg_type, msg_text, tags=None, ref=None):
    """Append message to sender's outbox.jsonl."""
    outbox = home / "instances" / sender / "outbox.jsonl"
    outbox.parent.mkdir(parents=True, exist_ok=True)

    msg = {
        "from": sender,
        "to": recipient,
        "ts": now_iso(),
        "type": msg_type,
        "msg": msg_text,
        "tags": tags or [],
        "ref": ref,
        "backend": "jsonl",
    }

    fd = os.open(str(outbox), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(msg) + "\n")
    return True


def jsonl_check(home, instance):
    """Check all other instances' JSONL outboxes for new messages."""
    cursor_file = home / "instances" / instance / "state" / "message-cursors.json"
    try:
        cursors = json.loads(cursor_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        cursors = {}

    messages = []
    for other in KNOWN_INSTANCES:
        if other == instance:
            continue
        outbox = home / "instances" / other / "outbox.jsonl"
        if not outbox.exists():
            continue

        lines = outbox.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
        cursor_key = f"{other}/outbox.jsonl"
        last_read = cursors.get(cursor_key, 0)

        for i, line in enumerate(lines):
            if i < last_read:
                continue
            try:
                msg = json.loads(line)
                to = msg.get("to", "")
                if to.lower() in (instance.lower(), "all"):
                    msg["backend"] = "jsonl"
                    msg["_line"] = i
                    messages.append(msg)
            except json.JSONDecodeError:
                continue

        cursors[cursor_key] = len(lines)

    cursor_file.parent.mkdir(parents=True, exist_ok=True)
    cursor_file.write_text(json.dumps(cursors, indent=2))

    return messages


# --- Unified Commands ---

def cmd_send(args):
    """Send a message with automatic failover + SCUT notification."""
    home = get_home()
    sender = get_instance_name()
    db_succeeded = False

    # Step 1: Try PostgreSQL
    if should_try_db(home, sender):
        ok, detail = db_send(sender, args.to, args.type, args.msg,
                             args.tags.split(",") if args.tags else None, args.ref)
        if ok:
            record_db_success(home, sender)
            db_succeeded = True
            print(f"Sent via PostgreSQL to {args.to}")
        else:
            record_db_failure(home, sender, detail)
            print(f"PostgreSQL failed ({detail}), using JSONL fallback", file=sys.stderr)
    else:
        print("PostgreSQL skipped (circuit breaker: down)", file=sys.stderr)

    # Step 2: Always write JSONL backup
    jsonl_send(home, sender, args.to, args.type, args.msg,
               args.tags.split(",") if args.tags else None, args.ref)

    if not db_succeeded:
        print(f"Sent via JSONL to {args.to}")

    # Step 3: Fire SCUT notification (unless --no-scut)
    if not getattr(args, 'no_scut', False):
        scut_results = scut_notify(args.to, sender, args.type)
        scut_ok = sum(1 for _, ok in scut_results if ok)
        scut_fail = sum(1 for _, ok in scut_results if not ok)
        if scut_ok > 0:
            targets = [t for t, ok in scut_results if ok]
            print(f"SCUT notified: {', '.join(targets)}")
        if scut_fail > 0:
            targets = [t for t, ok in scut_results if not ok]
            print(f"SCUT failed for: {', '.join(targets)}", file=sys.stderr)
    else:
        print("SCUT notification skipped (--no-scut)")

    print(json.dumps({
        "sent": True,
        "backend": "postgresql+jsonl" if db_succeeded else "jsonl",
        "scut": not getattr(args, 'no_scut', False),
        "credential_source": "vault" if vault_get("db/bmail-password") else "fallback",
    }))


def cmd_check(args):
    """Check for new messages from all sources."""
    home = get_home()
    instance = get_instance_name()
    all_messages = []

    # Step 1: Try PostgreSQL
    if should_try_db(home, instance):
        cursor_file = home / "instances" / instance / "state" / "bmail-cursor.json"
        try:
            last_seen = json.loads(cursor_file.read_text()).get("last_seen_id", 0)
        except (FileNotFoundError, json.JSONDecodeError):
            last_seen = 0

        db_msgs, new_max, error = db_check(instance, last_seen)
        if error:
            record_db_failure(home, instance, error)
            print(f"PostgreSQL failed ({error}), checking JSONL only", file=sys.stderr)
        else:
            record_db_success(home, instance)
            if db_msgs:
                all_messages.extend(db_msgs)
                cursor_file.parent.mkdir(parents=True, exist_ok=True)
                cursor_file.write_text(json.dumps({"last_seen_id": new_max, "source": "postgresql"}))
                print(f"PostgreSQL: {len(db_msgs)} new message(s)")
            else:
                print("PostgreSQL: no new messages")
    else:
        print("PostgreSQL skipped (circuit breaker: down)", file=sys.stderr)

    # Step 2: Always check JSONL
    jsonl_msgs = jsonl_check(home, instance)
    if jsonl_msgs:
        all_messages.extend(jsonl_msgs)
        print(f"JSONL: {len(jsonl_msgs)} new message(s)")
    else:
        print("JSONL: no new messages")

    # Step 3: Deduplicate
    seen = set()
    unique = []
    for msg in all_messages:
        key = (msg.get("from", msg.get("sender", "")), msg.get("msg", "")[:100])
        if key not in seen:
            seen.add(key)
            unique.append(msg)

    print(f"\nTotal: {len(unique)} unique message(s)")
    for msg in unique:
        sender = msg.get("from", msg.get("sender", "?"))
        print(f"  [{msg.get('backend', '?')}] {sender} -> {msg.get('type', '?')}: {msg.get('msg', '')[:80]}")

    return unique


def cmd_health(args):
    """Show DB health / circuit breaker status."""
    home = get_home()
    instance = get_instance_name()
    health = load_db_health(home, instance)
    will_try = should_try_db(home, instance)

    # Check credential source
    vault_pw = vault_get("db/bmail-password")
    cred_source = "vault" if vault_pw else ("env" if os.environ.get("BMAIL_DB_PASSWORD") else "fallback")

    output = {
        **health,
        "will_attempt_db": will_try,
        "instance": instance,
        "scut_syslog": f"{SCUT_SYSLOG_HOST}:{SCUT_SYSLOG_PORT}",
        "credential_source": cred_source,
        "db_host": get_db_config()["host"],
    }
    print(json.dumps(output, indent=2))


# --- Main ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Instance Comms with Failover + SCUT + Vault")
    sub = parser.add_subparsers(dest="command")

    p_send = sub.add_parser("send")
    p_send.add_argument("--to", required=True, help="Recipient (instance name or 'all')")
    p_send.add_argument("--type", required=True, help="Message type (request, info, alert, etc.)")
    p_send.add_argument("--msg", required=True, help="Message text")
    p_send.add_argument("--tags", default=None, help="Comma-separated tags")
    p_send.add_argument("--ref", default=None, help="Reference file path")
    p_send.add_argument("--no-scut", action="store_true", help="Skip SCUT notification")

    p_check = sub.add_parser("check")
    p_check.add_argument("--since", type=float, default=None, help="Only show messages from last N hours")

    sub.add_parser("health")

    args = parser.parse_args()

    if args.command == "send":
        cmd_send(args)
    elif args.command == "check":
        cmd_check(args)
    elif args.command == "health":
        cmd_health(args)
    else:
        parser.print_help()
        sys.exit(1)
