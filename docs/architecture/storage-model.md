# Storage Model

## Core Principle

> **Shared storage is the fleet's cold-standby backup, not its live substrate.**

Running processes write local. Heartbeats push to shared storage for redundancy. This reconciles two hard requirements:

1. **Recoverability** — if any host dies, its bob must be reconstitutable from shared storage + a vault key
2. **Reliability** — SQLite over network filesystems corrupts; CIFS open-handle stalls crash gateways; sync conflicts in frequently-written files cause data loss

The reconciliation: author local, push each heartbeat. Shared storage always has a recent copy (≤ one heartbeat cadence old), but the live process never fights with the sync engine.

## Placement Matrix

| Path / Class | Placement | Notes |
|---|---|---|
| `shared/*.md` (SOUL, USER, AGENTS, protocol) | Shared (authoritative) | Read-mostly, deliberate edits. Bobs mirror via fleet-sync. |
| `skills/**` | Shared (authoritative) | Mirrored to local workspace via fleet-sync. Gateway loads from local mirror only. |
| `skills/vault/vault.dat` | Shared | Encrypted AES-256 at rest. Safe to sync. Master key stays local (Article VI). |
| `instances/<Name>/IDENTITY.md` | Authored local → pushed each heartbeat | Single writer per bob; local reads for speed; push for cold-standby. |
| `instances/<Name>/MEMORY.md` | Authored local → pushed each heartbeat | Same. |
| `instances/<Name>/HANDOFF.md` | Authored local → pushed each heartbeat | Present only during duty transfers. |
| `instances/<Name>/CHECKLIST.md` | Authored local → pushed each heartbeat | Personal work list. |
| `instances/<Name>/logs/YYYY-MM-DD.md` | Authored local → pushed each heartbeat | Frequent append. Local avoids open-handle stalls. |
| `instances/<Name>/outbox.jsonl` | Shared ⚠ | Cross-bob visibility required for JSONL bmail fallback. |
| `instances/<Name>/state/` (cursors, PIDs) | **Local only** 🔴 | Rewritten every heartbeat. PID files are process-held. Never sync. |
| `instances/<Name>/.openclaw/**` (runtime) | **Local only** 🔴🔴 | Gateway holds files open. SQLite over CIFS corrupts. Never sync. |
| Per-bob venvs, caches, `__pycache__`, `node_modules` | **Local only** 🔴 | Platform-specific binaries. Useless to peers. Break sync. |
| Application databases (SQLite, etc.) | **Local only** 🔴🔴 | SQLite requires local FS. Snapshot separately if warranted. |

## Workspace Path Standard

Every bob's gateway `workspace` value **must** point to a host-local path, never the shared mount.

- **Linux:** `workspace = /home/bob/.openclaw/workspace`
- **Windows:** `workspace = %USERPROFILE%\.openclaw\workspace`

Shared knowledge is mirrored into the workspace by fleet-sync. The shared mount is where content is *authored* and *pushed* — not where the gateway *runs from*.

## Recovery Guarantee

A replacement bob can be reconstituted from:

1. **Shared storage** — skills, protocol docs, templates, instance folder (identity/memory/logs)
2. **A vault key** — delivered manually (never synced)
3. **A base OS install** — Python 3, psycopg2, OpenClaw

That is sufficient to bring a bob back to fleet-fit status. No component requires forensic recovery of a specific host's local disk.

## What Must Be Pushed Each Heartbeat

**Push:** `IDENTITY.md`, `MEMORY.md`, `HANDOFF.md`, `CHECKLIST.md`, `logs/YYYY-MM-DD.md`

**Never push:** `state/` (cursors, PIDs), `.openclaw/` runtime, app venvs/caches/node_modules, live application databases

## Verify

```bash
# Workspace is local, not the shared mount
grep -E '"workspace"' ~/.openclaw/openclaw.json | grep -v fleet-home && echo "PASS: workspace is local"

# No SQLite files on the shared mount for this bob
find $CLAWDBOT_HOME/instances/<Name> -name '*.sqlite' -o -name '*.db' 2>/dev/null \
  | grep -v '\.bak' && echo "FAIL: SQLite on shared mount" || echo "PASS: no SQLite on mount"

# Runtime tree not on the shared mount
[ ! -d $CLAWDBOT_HOME/instances/<Name>/.openclaw ] && echo "PASS: no runtime on mount"

# State PIDs not on mount
find $CLAWDBOT_HOME/instances/<Name>/state -name '*.pid' 2>/dev/null \
  && echo "FAIL: PIDs on mount" || echo "PASS: PIDs local"
```
