# Fleet Architecture Overview

## The Big Picture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Shared Storage                           │
│         (OneDrive / NFS / CIFS — cold-standby backup)          │
│                                                                 │
│  shared/           skills/           instances/                 │
│  ├── SOUL.md       ├── vault/        ├── Bob/                   │
│  ├── USER.md       ├── scut/         │   ├── IDENTITY.md        │
│  ├── AGENTS.md     ├── fleet-sync/   │   ├── MEMORY.md          │
│  └── protocol/     └── image-gen/    │   └── logs/              │
│                                      ├── Spock/                 │
│                                      └── ...                    │
└──────────────┬──────────────────────────────────────────────────┘
               │  fleet-sync mirrors skills → local workspace
               │  heartbeat pushes identity/memory/logs → shared
               │
    ┌──────────┴──────────────────────────────────────┐
    │                    LAN                           │
    │                                                  │
    │  ┌──────────┐  bmail (PG)  ┌──────────┐         │
    │  │  Bob     │◄────────────►│  Spock   │         │
    │  │ (Win)    │  SCUT (UDP)  │ (LXC)    │         │
    │  └──────────┘              └──────────┘         │
    │       │                         │               │
    │       └──────────┬──────────────┘               │
    │                  │                              │
    │             ┌────┴────┐                         │
    │             │ bmail-db│                         │
    │             │(PG:5432)│                         │
    │             └─────────┘                         │
    └─────────────────────────────────────────────────┘
```

## Components

### Bobs

Each bob is a named OpenClaw agent instance running on its own host. A bob has:

- **Identity** — name, role focus, vibe, emoji. Declared in `IDENTITY.md`. Read at every session start.
- **Memory** — long-term curated knowledge in `MEMORY.md` + daily raw logs. Accumulates over time.
- **Skills** — shared tools mirrored locally from shared storage via fleet-sync.
- **Gateway** — the OpenClaw process that handles sessions, heartbeats, tool calls, and inter-agent comms.
- **SCUT listener** — a small Python process that receives real-time wake signals from peers.

### Shared Storage

The fleet's cold-standby backup layer. **Not a live substrate** — running processes never read directly from it. Three uses:

1. **Skill distribution** — `skills/` is authoritative; bobs mirror it locally via fleet-sync every 30 minutes
2. **Protocol and shared docs** — `shared/` holds SOUL.md, USER.md, the Fleet Protocol
3. **Identity backup** — each bob pushes its `instances/<Name>/` directory each heartbeat

### bmail-db

A PostgreSQL instance that acts as the fleet's message store. Every inter-bob message is written here (with a JSONL flat-file fallback when PG is unreachable). Messages persist across restarts and are queryable for audit and catch-up.

### SCUT (Subspace Communications Unit Technology)

The real-time layer on top of bmail. When a `request` type message is sent to a bob, SCUT delivers a UDP packet to the receiving bob's listener (port 8514) which wakes the agent immediately via `openclaw system event --mode now`. Without SCUT, requests drain at the next heartbeat (up to 45 minutes later).

## Data Flow — Heartbeat Cycle

```
Every ~30 min:
  1. Check bmail inbox  →  reply to urgent messages
  2. Check CHECKLIST    →  advance next item
  3. Update daily log   →  append material activity
  4. Update MEMORY.md   →  if something worth keeping
  5. Push to shared     →  rsync instances/<Name>/ → shared storage
  6. Verify comms       →  PG reachable, SCUT listener up
  7. Reply HEARTBEAT_OK (or alert if something needs owner attention)
```

## Data Flow — Inter-Bob Request

```
Sender                bmail-db              Receiver (SCUT)
  │                      │                       │
  ├─── INSERT msg ───────►│                       │
  │  type=request         │                       │
  │                       ├── SCUT notify ────────►│
  │                       │   (UDP to port 8514)   │
  │                       │                  wake() │
  │                       │                  openclaw system event
  │                       │                       │
  │                       │◄── comms.py check ─────┤
  │                       │                  act() │
  │                       │◄── INSERT reply ───────┤
  │                       │   type=info            │
  ◄── SCUT notify ────────┤                        │
  comms.py check          │                        │
  act on reply            │                        │
```

## What Lives Where

| Data | Location | Reason |
|------|----------|--------|
| Skill scripts | Local workspace (mirrored from shared) | Gateway reads local; CIFS latency/staleness |
| Identity, memory, logs | Local (authored) → pushed to shared each heartbeat | Single writer per bob; push for cold-standby |
| Runtime state (PIDs, cursors) | Local only, never synced | Rewritten every heartbeat; causes conflicts on sync |
| Gateway runtime (sessions, sqlite) | Local only | SQLite over network FS corrupts |
| Secrets (vault.dat) | Shared storage (encrypted AES-256) | Needs to reach every bob; safe to sync |
| Vault master key | Local only (mode 600) | Must never be in any sync path |

See [`storage-model.md`](storage-model.md) for the full placement matrix.
