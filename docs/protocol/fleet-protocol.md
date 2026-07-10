# FLEET-PROTOCOL.md

**Authoritative source of standards for the Bobiverse fleet.**
This document is the *only* place where fleet-wide policy is authoritative. Convenience shards (`HEARTBEAT.md`, `STORAGE-PLACEMENT.md`, etc.) may exist as redirects but MUST NOT diverge in intent. Where they do, this document wins.

**Version:** 1.8.0
**Effective:** 2026-07-07
**Owner:** Skip (<OWNER_EMAIL>)
**Scope:** All bobs in the fleet. Waivers per Article XI.

## Versioning

Semantic. Major = structural rewrite. Minor = new Article or new Section within an Article. Patch = clarifications, typo, verify-command fixes. Bump on every change and record in the changelog at the bottom of this file.

## Fleet Doctrine

Nine principles, set by Skip, that every Article implements. When an Article is silent or ambiguous, decide in the spirit of these.

1. **Solve it once.** A problem solved by any bob is solved for the fleet. Never rework what a peer has fixed; never forget your own fixes. *(Articles III, VII, XII — memory, shared skills, inspection)*
2. **Waivers over blockers.** Rules must not stop the mission. Deviate, register it, keep moving. An unregistered deviation is a violation. *(Article XI)*
3. **Meet the terrain.** The fleet spans Windows workstations, LXCs, and Linux VMs. Standards must work on all three; platform quirks are accommodated, not fought. *(Articles II, VIII)*
4. **Every Marine is a rifleman.** Roles focus a bob's development; they never gate what a bob may do. Any bob can take any assignment. *(Articles I, IX)*
5. **Grow distinct.** Each bob accumulates its own memory and, over time, its own voice. Identity is load-bearing; personality is earned, not prescribed. *(Article III)*
6. **Stay in contact.** The fleet's combined capability only exists if bobs can reliably reach each other and Skip. *(Article V)*
7. **Hand off clean.** Any duty transfers to any bob with minimal ramp-up. No single bob is a point of failure for a project. *(Article IX)*
8. **Survive the fire.** Loss of any host — including tkd01svr — costs hardware, not knowledge. OneDrive is the cold-standby backup: recoverability, not high availability. *(Articles II, X)*
9. **Operate efficiently.** Respect quotas, budgets, and shared resources. Know your current capability tier and act within it — a degraded bob that recognizes its own degradation (auxiliary-power model, broken memory index) and throttles accordingly is operating efficiently; one that grinds on blindly is the most expensive failure mode in the fleet. *(Articles IV, XIII, §3.4)*

## Table of Contents

- **Article I** — Fleet Structure & Roles
- **Article II** — Storage Placement
- **Article III** — Identity, Memory & Personality
- **Article IV** — Heartbeat & Cadence
- **Article V** — Communications (Bmail + SCUT)
- **Article VI** — Vault & Secrets
- **Article VII** — Skills & Fleet-Sync
- **Article VIII** — Environment Contract
- **Article IX** — Handoff & Duty Assignment
- **Article X** — Resilience & Recovery
- **Article XI** — Waivers
- **Article XII** — Inspection & Rating
- **Article XIII** — Model Use
- **Article XIV** — Image Generation
- **Appendix A** — Waiver Register
- **Appendix B** — Inspection Report Template
- **Changelog**

---

# Article I — Fleet Structure & Roles

## §1.1 Intent

The fleet is a cooperative team of AI agents, each capable of any assignment. Roles below are *aspirational focus areas* — they shape a bob's default priorities and long-term skill development, but do not gate what a bob may work on. **Every Marine is a rifleman: every bob is a powerful AI agent.**

## §1.2 Standard

Role assignments are defined by the fleet owner and documented in each bob's `IDENTITY.md`. The table below is an **example fleet roster** — replace it with your own when you deploy.

Example role assignments:

| Bob | Host | Platform | Role focus |
|---|---|---|---|
| Bob | `<WORKSTATION_HOST>` | Windows workstation | Owner-facing orchestration, daily driver |
| Riker | `<LXC_HOST_1>` | Linux LXC | Fleet SysAdmin, infrastructure operations |
| Milo | `<LXC_HOST_2>` | Linux LXC | R&D, Special Projects, Skunkworks |
| Bender | `<LXC_HOST_3>` | Linux LXC | Task Review Council, protocol audit |
| Luke | `<LXC_HOST_4>` | Linux LXC | House AI (Home Assistant, media, IoT) |
| Bart | `<LXC_HOST_5>` | Linux LXC | Customer-facing support, product work |
| Homer | `<LAPTOP_HOST_1>` | Windows laptop | Reserve / mostly idle |
| Mario | `<LAPTOP_HOST_2>` | Windows laptop | Reserve / mostly idle |

Your fleet will have different names, hosts, and roles. The structure above shows what a mature fleet looks like — start with one or two bobs and grow from there.

Skills and user-facing memories may be scoped per-role (a bob focused on House AI does not need Proxmox skill payload). Fleet-wide skills (comms, vault, memory hygiene) are required of all bobs regardless of role.

## §1.3 Verify

- `instances/<Name>/IDENTITY.md` declares the bob's role focus consistent with the table above.
- No bob has been assigned a role its host cannot support (e.g. Windows bobs are not assigned Linux ops).

## §1.4 Waiver clause

Role assignments are informational; deviations do not require a waiver. Add a note to `IDENTITY.md` if a bob is temporarily working outside its focus area.

---

# Article II — Storage Placement

## §2.1 Intent

The fleet must survive the loss of any single host, including <PROXMOX_HOSTNAME>. Anything required to spin up a replacement bob must live on OneDrive-synced storage. At the same time, live runtime files that a process holds open, or that a bob rewrites faster than sync can settle, cause corruption, conflict copies, and event-loop stalls if placed on OneDrive.

The reconciliation:

> **OneDrive is the fleet's cold-standby backup, not the fleet's live substrate.**
> Anything a running process writes often or holds open → **local** to that bob.
> Anything needed to reconstitute a bob (identity, memory, logs, config templates) → authored **local**, pushed to OneDrive **each heartbeat** for redundancy.
> Shared read-mostly artifacts (skills, protocol docs, templates) → live on OneDrive, mirrored **into** each bob via `fleet-sync` (Article VII), never read live from the mount by a running process.

## §2.2 Standard — placement matrix

| Path / class | Placement | Notes |
|---|---|---|
| `$CLAWDBOT_HOME/shared/*.md` (AGENTS, SOUL, USER, TOOLS, HEARTBEAT, this doc) | OneDrive (authoritative) | Read-mostly, deliberate edits. Bobs mirror via fleet-sync. |
| `$CLAWDBOT_HOME/skills/**` | OneDrive (authoritative) | Mirrored to local workspace via fleet-sync (Article VII). Never read live by a running gateway. |
| `$CLAWDBOT_HOME/skills/vault/vault.dat` | OneDrive | Encrypted at rest, master key stays local (Article VI). |
| `$CLAWDBOT_HOME/instances/<Name>/IDENTITY.md, MEMORY.md, HANDOFF.md` | Authored **local**, pushed to OneDrive each heartbeat | Single-writer per bob; local reads for speed; push for cold-standby redundancy. |
| `$CLAWDBOT_HOME/instances/<Name>/logs/YYYY-MM-DD.md` | Authored **local**, pushed to OneDrive each heartbeat | Frequent append. Local avoids open-handle stalls; push for backup + peer visibility. |
| `instances/<Name>/CHECKLIST.md` | Authored **local**, pushed each heartbeat | Personal work list (§4.3). |
| `instances/<Name>/state/` (message-cursors, bmail-cursor, db-health, `*.pid`) | **Local only** 🔴 | Rewritten every heartbeat; PID files are process-held. Do NOT push to OneDrive. |
| `instances/<Name>/.openclaw/**` (runtime: `tasks/*.sqlite`, `sessions/`, live `openclaw.json`, workspace-state) | **Local only** 🔴🔴 | Gateway holds files open. SQLite over CIFS corrupts. Never push. |
| `instances/<Name>/outbox.jsonl` | OneDrive ⚠ (until Article V PG-primary is fleet-wide) | Cross-instance visibility required for JSONL fallback. Move local only when PG is authoritative. |
| Per-bob application code / venv / caches / `__pycache__` / node_modules | **Local only** 🔴 | Platform-specific binaries; useless to peers; break OneDrive sync. |
| Per-bob application data DB (e.g. Voss `review.db`) | **Local only** 🔴🔴 | SQLite requires local FS. Back up via periodic snapshot to OneDrive if warranted, never live. |

## §2.3 Standard — workspace path

Every bob's gateway `workspace` value MUST point to a host-local path, never the shared mount.

- **Linux (LXC/VM):** workspace = `~/.openclaw/workspace` for whichever user the gateway runs as. See §8.4 for gateway-user standard.
- **Windows:** workspace = `%USERPROFILE%\.openclaw\workspace`.

Shared knowledge is mirrored into that workspace via fleet-sync (Article VII). The mount itself (`$CLAWDBOT_HOME` on Linux, `%CLAWDBOT_HOME%` on Windows) is where shared content is *authored* and *pushed* — not where the gateway *runs from*.

## §2.4 Verify

Per bob:

```bash
# Config points at local workspace
grep -E '"workspace"' /path/to/openclaw.json | grep -v clawdbot-home && echo "PASS §2.3"

# No SQLite on the mount for this bob
find $CLAWDBOT_HOME/instances/<Name> -name '*.sqlite' -o -name '*.db' 2>/dev/null | \
  grep -v '\.bak' && echo "FAIL §2.2" || echo "PASS §2.2"

# No .openclaw runtime tree on the mount
[ ! -d $CLAWDBOT_HOME/instances/<Name>/.openclaw ] && echo "PASS §2.2 runtime"

# state/*.pid on local disk, not on mount
find $CLAWDBOT_HOME/instances/<Name>/state -name '*.pid' 2>/dev/null && echo "FAIL §2.2" || echo "PASS §2.2"
```

## §2.5 Waiver clause

Waivers may be filed when a shared skill (Article VII) hardcodes a mount path that this Article forbids. Waiver expires with the skill fix. Example: Voss's SCUT `state/` waiver pending SCUT v2 (Appendix A).

---

# Article III — Identity, Memory & Personality

## §3.1 Intent

Every bob maintains an identity, an accumulated memory, and (aspirationally) a distinct voice. Identity and memory are load-bearing operationally. Voice is encouraged but never enforced — a bob's personality should develop through experience, not prescription.

## §3.2 Standard — required files

Per bob at `$CLAWDBOT_HOME/instances/<Name>/`:

- `IDENTITY.md` — Name, creature, vibe, emoji, avatar, current role focus (Article I), host. Authoritative for who this bob claims to be.
- `MEMORY.md` — Long-term curated memory. Distilled, not raw logs.
- `logs/YYYY-MM-DD.md` — Daily activity log (raw). Append-only during the day.
- `HANDOFF.md` — Present only when a duty is in mid-transfer (Article IX).

All authored local, pushed to OneDrive each heartbeat per Article IV.

**Owner profile (`shared/USER.md`):** the shared USER.md is the fleet's knowledge of Skip and already defines what to capture — this Protocol adds one rule: **every update a bob makes to USER.md must be tagged with the contributing bob and date**, e.g. `(Bob, 2026-07-02)` appended to the added/changed line. Untagged edits are protocol violations; attribution is what lets Skip audit and correct what the fleet believes about him.

## §3.3 Standard — voice divergence (aspirational)

Bobs are encouraged, not required, to develop distinct voices. `SOUL.md` provides the base disposition; individual bobs may extend or diverge in their own `IDENTITY.md` and, over time, in phrasing choices reflected in memory and communications. No enforcement mechanism. No mandatory divergence audit. The goal is bobs whose personalities emerge from what they actually do — not from checked boxes. Skip believes that a bob that evolves thru experience will be more valuable than a script.

## §3.4 Standard — memory index health

Files are the memory; the semantic index (per-agent SQLite DB) is how a bob *recalls* at scale. A silently broken index degrades every judgment a bob makes while looking exactly like "the bob is dumb today" — this underpinned months of fleet trouble before the 2026-06-26 fleet-wide fix. Index health is therefore a standing requirement, not an optional nicety:

- **Embedding provider:** local (llama-cpp) fleet-wide. Cloud embedding providers require explicit sign-off from Skip.
- **Index must be clean:** `openclaw memory status --deep` reports `Embeddings: ready`, `Dirty: no`, and indexed counts of exactly N/N per source. (Plain `openclaw memory status` omits the `Embeddings: ready` line — only `--deep` runs the probe that surfaces it.) Indexed > total on a *stable* source (e.g. `memory`) means stale ghost entries — rebuild with `openclaw memory index --force`. On the volatile `sessions` source, indexed slightly > total is normal churn from live transcripts being written mid-session (a `--force` reindex grows the count, it does not shrink it) — do NOT force-reindex chasing it.
- **Batch mode enabled:** `Batch: disabled` means the embedder tripped its failure breaker and is running degraded (slow searches, timeouts). Investigate; a gateway restart resets the breaker.
- **Cold-start warm-up:** the local embedding model loads on first use; the first `memory_search` after a gateway restart may hit the 15s tool timeout on slower hosts. This is expected — retry, do not diagnose a broken index from a single cold-start timeout. After any gateway restart (and in the daily reindex cron), run one throwaway warm-up — `openclaw memory status --deep` (it exercises the search path and reports `Embeddings: ready`) — so real queries never pay the load tax. NOTE: earlier revisions of this standard said `openclaw memory query "warmup"`; that subcommand does not exist in 2026.6.x (`memory` exposes only `index`/`promote`/`promote-explain`/`rem-backfill`/`rem-harness`) and silently no-ops — do not use it. Do NOT use `openclaw infer embedding create` for warm-up either: it spawns a *separate* model load rather than warming the gateway-resident copy, and is slow. For hosts running the **active-memory** plugin, the durable fix is config, not a warm-up command: set `plugins.entries.active-memory.config.setupGraceTimeoutMs: 30000` so the first blocking recall gets extra cold-start budget instead of timing out (v2026.5.2 removed the old implicit 30s grace; see active-memory docs → "Cold-start grace").
- **Index scope:** extraPaths SHOULD point at local mirrors, not the live shared mount (Article II §2.1; live-mount indexing wedged Bob's reindex on Windows/OneDrive). Mount-path extraPaths on Linux are waiver-eligible while they demonstrably work.
- **claude-cli auto-memory:** any bob granted `claude-cli` (§13.2) accumulates harness memory at `<home>/.claude/projects/<munged-workspace-path>/memory/` (e.g. `/root/.claude/projects/-root--openclaw-workspace/memory/` for a root-run Linux bob; `C:/Users/<user>/.claude/projects/...` on Windows). Add that directory to the bob's `memorySearch.extraPaths` so recall covers it — it is local disk, so no mount/OneDrive concern. Bobs that never ran claude-cli have nothing to add.
- **A bob that notices its own recall failing** (memory_search disabled, timeouts, empty results on things it should know) should treat that as a §3.4 incident: log it, alert Skip, and distrust its own conclusions about "missing" history until the index is verified.

## §3.5 Verify

```bash
# Required files exist and are non-empty
for f in IDENTITY.md MEMORY.md; do
  [ -s "$CLAWDBOT_HOME/instances/<Name>/$f" ] || echo "FAIL §3.2 $f"
done

# Today's log has been touched in the last 24h
find "$CLAWDBOT_HOME/instances/<Name>/logs" -name "$(date -u +%Y-%m-%d).md" -mtime -1 || echo "STALE §3.2"

# Memory index health (§3.4)
openclaw memory status 2>/dev/null | tee /tmp/memstatus | grep -q 'Embeddings: ready' \
  && echo "PASS §3.4 embeddings" || echo "FAIL §3.4 embeddings"
grep -q 'Dirty: no' /tmp/memstatus && echo "PASS §3.4 clean" || echo "FAIL §3.4 dirty"
grep -q 'Batch: disabled' /tmp/memstatus && echo "WARN §3.4 batch degraded" || echo "PASS §3.4 batch"
# Stale ghost entries: any "Indexed: X/Y" where X != Y
grep -E 'Indexed: ([0-9]+)/([0-9]+)' /tmp/memstatus | awk -F'[:/ ]+' '$2 != $3 {print "WARN §3.4 ghost entries: " $0}'
```

## §3.6 Waiver clause

Absence of `MEMORY.md` is allowed only during a bob's first 7 days after commissioning. `IDENTITY.md` is never waived.

---

# Article IV — Heartbeat & Cadence

## §4.1 Intent

Heartbeats are the fleet's pulse. They (a) prove liveness, (b) guarantee state gets pushed to OneDrive for redundancy, (c) advance per-bob personal work, and (d) surface anything that needs owner attention.

## §4.2 Standard — cadence

- **Default cadence:** every 30–45 minutes when active. Configurable per bob in `openclaw.json` (`heartbeat.every`).
- **Quiet hours:** 23:00–08:00 local — bob time, replies to routine polls should be `HEARTBEAT_OK` unless something needs attention.
- **Heartbeat model:** run beats on aux power — see §4.6.
- **Disabled heartbeat is allowed** for individual bobs when disabling is a deliberate choice (documented in the bob's `IDENTITY.md`). It is not a waiver; it is a supported operating mode. Note: a heartbeat-disabled bob MUST close the inbox gap another way (e.g. a bmail-check cron), or peer messages rot unseen. (Bob/TKD14PC ran heartbeat-disabled 2026-06-18 → 2026-07-02 as a resume-bug workaround; re-enabled at 33m after the bug cleared.)

## §4.3 Standard — heartbeat protocol

Each heartbeat runs the following, in order:

1. **Check inbox** (bmail via Article V). Reply to anything urgent; log everything.
2. **Check own `CHECKLIST.md`** — advance the next unchecked item, or note blocker.
3. **Update today's `logs/YYYY-MM-DD.md`** with anything material.
4. **Update `MEMORY.md`** if the day produced something worth long-term retention.
5. **Push identity/memory/logs/checklist** to OneDrive (per §2.2, files authored local).
6. **Verify vault + PG comms health** (Article V verify).
7. **Reply to poll** with `HEARTBEAT_OK` if nothing else, or an alert if something needs owner attention.

## §4.4 Verify

```bash
# Heartbeat has fired within cadence * 2 window
last=$(stat -c %Y "$CLAWDBOT_HOME/instances/<Name>/logs/$(date -u +%Y-%m-%d).md" 2>/dev/null)
now=$(date +%s); ago=$(( (now - last) / 60 ))
[ $ago -lt 90 ] && echo "PASS §4.2 (heartbeat within window)" || echo "STALE §4.2 ($ago min ago)"

# CHECKLIST.md exists (may be empty)
[ -f "$CLAWDBOT_HOME/instances/<Name>/CHECKLIST.md" ] && echo "PASS §4.3.2"
```

## §4.5 Waiver clause

A bob with `heartbeat.every` set to `disabled` or absent from config is presumed intentional (per IDENTITY.md declaration) and does not require a waiver. Missed heartbeats on a bob that *should* be beating trigger inspection failure §4.2, not a waiver.

## §4.6 Standard — heartbeat model (aux power)

**Heartbeats run on aux power — the lowest-cost model available to the bob. Call for more power only when a beat turns up real work.**

*Why:* idle beats (bmail check, `HEARTBEAT_OK`) don't need a frontier model, and every beat that inherits the main-session model burns the scarce shared pool. Left unset, `heartbeat.model` inherits the session's live runtime model — so a bob running an expensive session override (e.g. Fable, which turns tokens ~5× Opus, and Opus ~5× Sonnet) silently runs that flamethrower on every idle poll. Set the override explicitly.

- **claude-cli bobs:** set `heartbeat.model: "anthropic/claude-haiku-4-5"` in `openclaw.json` (`agents.list[].heartbeat.model`). Haiku is the Bic lighter — cheapest on the subscription, capable enough for triage.
- **non-claude bobs:** aux power is the cheapest available. Free-tier providers are eligible for heartbeats **only** when they have their own separate quota pool that on-demand/council work does not depend on (e.g. an OpenRouter account with ≥$10 credit → ~1000 req/day). The roster free keys (Groq/Mistral/etc., see `reference_free-tier-model-limits.md`) remain barred from heartbeat chains — their org-wide quotas must stay free for on-demand work.
- **Call for more power:** when a beat surfaces a real SCUT request or any multi-step/judgment-heavy task, the aux model must not half-do it. Wake the main model (`openclaw system event --mode now`) or flag Skip and let the full model handle it. Aux power triages; full power acts.
- **Config change requires a gateway restart** to take effect. Docs confirm heartbeats preserve the main session's runtime model after the run, so an aux override does not corrupt subsequent main-session turns (no context-overflow risk with Haiku's large window).

## §4.7 Waiver clause

Running heartbeats on a non-aux model is waiver-eligible only for a documented reason (e.g. a bob whose only available model is a frontier model). "Forgot to set the override" is not a waiver — it is a §4.6 violation surfaced at inspection.

---

# Article V — Communications (Bmail + SCUT)

## §5.1 Intent

Bobs must reliably reach each other and Skip. Primary transport is PostgreSQL (`bmail-db` on CT104 / <BMAIL_DB_HOST>). JSONL fallback via shared outbox files keeps messages flowing when PG is unreachable or a bob lacks credentials. SCUT is the wake mechanism that turns asynchronous messages into synchronous handling.

**Design intent (Skip, 2026-07-02):** SCUT is the fleet's **primary, near-real-time channel**. A `request` to a peer must produce autonomous action and a reply — no human going to the peer to prompt a response — and the requester must then **act on the answer**, not just log it. bmail (PG + JSONL) is the **backup and bulk-data layer**: persistence, audit trail, large payloads, and catch-up delivery when SCUT misses. A message that is read and thought about but not acted on is a comms failure, regardless of transport health.

## §5.2 Standard — bmail transport

- **Primary:** PostgreSQL at `<BMAIL_DB_HOST>:5432`, database `<BMAIL_DBNAME>`, user `bob`. Credentials via vault (Article VI): `db/bmail-host`, `db/bmail-dbname`, `db/bmail-user`, `db/bmail-password`.
- **Fallback:** `instances/<Name>/outbox.jsonl` on the shared mount (peers read directly).
- **Every bob** MUST have `psycopg2` installed and the vault key present. A bob unable to reach PG (and therefore stuck in JSONL fallback) fails §5.2.

## §5.3 Standard — SCUT wake

- Every bob runs the SCUT listener (`skills/scut/scripts/scut.py start`).
- Requests (`type: request`) must trigger wake; info messages may defer to next heartbeat.
- **Built-in default wake (fixed 2026-07-02):** `openclaw system event --mode now --text <prompt>`. The previous default (`openclaw message --session ...`) was never valid CLI syntax and silently failed on every host — any bob whose listener predates the fix must restart its listener to load the patched scut.py.
- **Windows hosts:** the bare `openclaw` npm shim is not launchable by Python's subprocess without a shell. Set `SCUT_WAKE_CMD` explicitly (user env var, then restart the listener task), e.g.:
  `"C:\Users\<user>\AppData\Roaming\npm\openclaw.cmd" system event --mode now --text "%SCUT_WAKE_PROMPT%"`
- **Gateway device pairing (silent blocker):** the CLI context the listener wakes through registers its own gateway device, which needs `operator.write` scope to enqueue events. A pending scope-upgrade request blocks wake with `scope upgrade pending approval` while everything else looks healthy. Check `openclaw devices list` and approve the pending request (`openclaw devices approve <requestId>`; each CLI invocation regenerates the pending ID, so list-then-approve promptly, or use `approve --latest` to see the current one).
- **Request lifecycle:** wake → read (`comms.py check`) → **act** → reply to sender (`--type info`, use `ref` to link). An ack is not completion. The requester in turn acts on the reply. Heartbeat pickup (§4.3 step 1) is the fallback path only — a bob relying on heartbeat drain for `request` handling has a broken wake, even if replies eventually flow (this masked Bill's broken wake until 2026-07-02; his 47-min heartbeat answered everything).
- **E2E verification standard:** transport health (`radio-check`) is necessary but not sufficient. A true pass is a timed round-trip: send a `request` requiring real command output; the reply must arrive autonomously, sub-minute when wake is healthy (≤ heartbeat cadence indicates fallback-only operation).

## §5.4 Verify

```bash
# PG reachable
python3 -c 'import socket,sys; s=socket.socket(); s.settimeout(3); s.connect(("<BMAIL_DB_HOST>",5432))' \
  && echo "PASS §5.2 net" || echo "FAIL §5.2 net"

# comms health returns credential_source=vault and status=up
sudo OPENCLAW_INSTANCE=<Name> "$CLAWDBOT_HOME/skills/scut/scripts/comms.py" health | \
  python3 -c 'import sys,json; d=json.load(sys.stdin); print("PASS §5.2" if d["credential_source"]=="vault" and d["status"]=="up" else "FAIL §5.2:"+json.dumps(d))'

# SCUT listener running
pgrep -f 'scut.py start' > /dev/null && echo "PASS §5.3" || echo "FAIL §5.3"

# Wake path uses the fixed default (or an explicit override)
grep -q '"system", "event"' "$CLAWDBOT_HOME/skills/scut/scripts/scut.py" \
  && echo "PASS §5.3 wake-default" || echo "FAIL §5.3 wake-default (stale scut.py)"

# No pending gateway device scope approvals blocking wake
openclaw devices list 2>&1 | grep -qi 'Pending (0)' \
  && echo "PASS §5.3 device" || echo "WARN §5.3 device (check pending approvals)"
```

## §5.5 Waiver clause

Waiver allowed when a bob is offline pending commissioning or when a host lacks psycopg2 for platform-specific reasons. Not allowed when the cause is a missing vault key — key propagation is a solved problem (Article VI).

---

# Article VI — Vault & Secrets

## §6.1 Intent

Fleet-wide secrets (bmail password, API keys, tokens) must be encrypted at rest, discoverable by any authorized bob, and never present in plaintext on synced storage.

## §6.2 Standard — key/data split

- **`vault.dat`** — encrypted secrets, lives at `$CLAWDBOT_HOME/skills/vault/vault.dat` on OneDrive. Safe to sync (AES-256 at rest).
- **Master key** — 64-hex-char, mode 600, owner-only:
  - **Linux (standard):** `/home/bob/.openclaw-vault-key`
  - **Windows (standard):** `%USERPROFILE%\.openclaw-vault-key`
  - **Legacy exception:** bobs running the gateway as root have the key at `/root/.openclaw-vault-key`. Waivered in Appendix A until re-provision.
- **The master key MUST NEVER be on OneDrive, in git, or in any sync path.** A copy in `Tools/temp/` or similar violates this Article.

## §6.3 Standard — distribution & clone-carry

Distribution of the master key to a new bob is a manual, out-of-band act by Skip, EXCEPT for LXC clones:

- **LXC clones:** `pct clone <src> <new> --full true` on the Proxmox host copies the source bob's home dir contents, including `/home/bob/.openclaw-vault-key`. New clones inherit the key automatically. No manual distribution needed — this is the intended distribution channel for the LXC pool.
- **Fresh installs / non-clone bobs:** Skip pastes hex into the bob's shell via SSH/RDP, or uses a short-lived non-synced transport (encrypted DM, removable media).

Vault contents (`vault.dat`) always sync via OneDrive.

## §6.4 Standard — rotation

Key rotation is a coordinated operation:

1. Generate new key.
2. Decrypt vault with old key, re-encrypt with new key, replace `vault.dat`.
3. Distribute new key to every bob (§6.3).
4. Retire old key on every host once rotation verified.

No automated rotation in v1.0.

## §6.5 Verify

```bash
# Key file present with correct perms
KEYFILE="${OPENCLAW_VAULT_KEYFILE:-$HOME/.openclaw-vault-key}"
[ -f "$KEYFILE" ] && [ "$(stat -c %a "$KEYFILE")" = "600" ] && echo "PASS §6.2"

# vault.py returns the bmail password
python3 "$CLAWDBOT_HOME/skills/vault/scripts/vault.py" get db/bmail-password >/dev/null && echo "PASS §6.5"

# Key NOT in any synced path
find "$CLAWDBOT_HOME" -name '*vault-key*' 2>/dev/null | \
  grep . && echo "FAIL §6.2 (key in OneDrive)" || echo "PASS §6.2 (key not synced)"
```

## §6.6 Waiver clause

No waivers permitted on §6.2 key-not-synced rule; that is a security invariant. Waivers on §6.5 permitted only during a bob's first-time provisioning window (≤24h).

---

# Article VII — Skills & Fleet-Sync

## §7.1 Intent

Skills are shared code the fleet develops collectively. They must be available to every bob, but running processes must not read them live off the shared mount (Article II §2.1 rationale).

## §7.2 Standard

- **Authoritative source:** `$CLAWDBOT_HOME/skills/` on OneDrive.
- **Local mirror:** `<workspace>/skills/` on each bob's local disk.
- **Sync mechanism:** `fleet-sync/fleet-sync.sh` (Linux) or `fleet-sync/fleet-sync.ps1` (Windows), driven by `fleet-sync/manifest.json`.
- **Cadence:** every 30 minutes via cron/Task Scheduler, offset from heartbeat cadence to avoid collision.
- **The gateway loads skills from the local mirror, not the mount.**

## §7.3 Verify

```bash
# Local mirror exists and is fresh
[ -d "$HOME/.openclaw/workspace/skills" ] && echo "PASS §7.2 exists"
find "$HOME/.openclaw/workspace/skills" -maxdepth 1 -type d -mmin -90 | grep -q . && echo "PASS §7.2 fresh"

# Skills discovered from local, not mount
openclaw skills list 2>/dev/null | grep -qi '$CLAWDBOT_HOME' && echo "FAIL §7.2" || echo "PASS §7.2"
```

## §7.4 Waiver clause

Bobs may be waived from §7.2 during first-provisioning. Post-provisioning, non-compliance is a fail.

---

# Article VIII — Environment Contract

## §8.1 Intent

A minimum set of environment variables must be resolvable on every bob so that shared tooling (comms, vault, fleet-sync) works without per-bob hardcoding.

## §8.2 Standard — required env vars

| Variable | Purpose | Example |
|---|---|---|
| `CLAWDBOT_HOME` | Root of shared workspace (OneDrive mount) | Linux: `$CLAWDBOT_HOME`. Windows: `C:\Users\skipz\OneDrive - exec-it.us\Tools\AI_Workspace\Clawdbot_Home` |
| `OPENCLAW_INSTANCE` | The bob's canonical name (matches `instances/<Name>/`) | `Voss`, `Bob`, etc. |
| `OPENCLAW_VAULT_KEYFILE` (optional) | Override for key file path | Defaults to `$HOME/.openclaw-vault-key` |

## §8.3 Standard — path naming inconsistency (accepted)

The OneDrive directory is named `Clawdbot_Home` (Title_Case, underscore). The Linux CIFS mount is named `clawdbot-home` (lowercase, hyphen). This inconsistency is tolerated: the `CLAWDBOT_HOME` env var abstracts it, and normalization would require coordinated mount + folder rename across the fleet. Do not "fix" without a coordinated migration.

## §8.4 Standard — gateway user (Linux)

The Linux standard is:

- **OS user:** `bob` (fixed name, same on every LXC/VM — the instance identity is carried by hostname and `OPENCLAW_INSTANCE`, not by the OS user)
- **Gateway:** user-mode systemd — `/home/bob/.config/systemd/user/openclaw-gateway.service`
- **OpenClaw home:** `/home/bob/.openclaw/`
- **Vault key:** `/home/bob/.openclaw-vault-key` (§6.2)
- **Sudo:** `bob` is in the `sudo` group for administrative tasks; the gateway itself does not run as root

This standard is what `shared/clone-a-bob.sh` assumes. Deviations (gateway as root, `/root/.openclaw`) are grandfathered via waiver until the bob is re-provisioned.

**Terminal identity note:** the hostname (e.g. `TKD03AI` = Voss, `TKD01AI` = Spock) carries the instance identity in the shell prompt (`bob@TKD03AI:~$`). Per-instance home directories are not required for terminal disambiguation.

## §8.5 Standard — time zone

**The fleet operates on CDT/CST (America/Chicago), Skip's local time.** All bobs use it internally (logs, schedules, cron expressions) and in every communication with Skip and with each other. Do not emit UTC timestamps in bmail/SCUT messages, alerts, or owner-facing output — convert at the boundary. Gateway/OS clocks may remain UTC internally; what matters is what gets written and said.

## §8.6 Verify

```bash
[ -n "$CLAWDBOT_HOME" ] && [ -d "$CLAWDBOT_HOME" ] && echo "PASS §8.2 CLAWDBOT_HOME"
[ -n "$OPENCLAW_INSTANCE" ] && echo "PASS §8.2 INSTANCE"
# Gateway user check (Linux)
ps -o user= -p "$(pgrep -f 'openclaw-gateway' | head -1)" 2>/dev/null
# Recent outbound messages carry CDT/CST timestamps, not Z-suffixed UTC (§8.5) — spot-check
tail -5 "$CLAWDBOT_HOME/instances/<Name>/outbox.jsonl" 2>/dev/null
```

## §8.7 Waiver clause

Gateway user = `root` is waiver-eligible per §8.4 for bobs commissioned before 2026-07-01. New bobs may not file this waiver.

---

# Article IX — Handoff & Duty Assignment

## §9.1 Intent

Duties (projects, ongoing investigations, standing responsibilities) should be transferable between bobs with minimal ramp-up. This makes the fleet resilient to individual-bob unavailability and lets Skip re-assign work as priorities shift.

## §9.2 Standard — HANDOFF.md

When a duty is being transferred (or when a bob is going offline mid-duty), the transferring bob writes `instances/<Name>/HANDOFF.md` containing:

- **Duty title** and receiver (or "TBD")
- **Current state** — what has been done
- **Next actions** — what should happen next, in order
- **Blockers** — anything stuck, with what it's stuck on
- **Context** — pointers to relevant files, memory entries, external systems
- **Sensitive notes** — any secrets/credentials needed (with vault key references, never plaintext)

The receiver acknowledges by copying HANDOFF.md content into their own working notes, then deleting the source `HANDOFF.md` (or moving to `archive/`).

## §9.3 Standard — duty assignment

Duties are assigned by Skip via bmail or in-session direction. Any bob may propose taking a duty from another via bmail (`type: request`). Role assignments (Article I) are guidance, not gates.

## §9.4 Verify

```bash
# HANDOFF.md, if present, has all required sections
if [ -f "$CLAWDBOT_HOME/instances/<Name>/HANDOFF.md" ]; then
  for s in "Duty title" "Current state" "Next actions" "Blockers"; do
    grep -qi "$s" "$CLAWDBOT_HOME/instances/<Name>/HANDOFF.md" || echo "FAIL §9.2 missing: $s"
  done
fi
```

## §9.5 Waiver clause

No standing waivers — this Article activates only when a duty transfer is in progress.

---

# Article X — Resilience & Recovery

## §10.1 Intent

The fleet must survive the loss of <PROXMOX_HOSTNAME> (or any single host) without losing accumulated knowledge or requiring bespoke rebuilds. Skip's original design intent — OneDrive as backup — is preserved: everything meaningful is either on OneDrive or has been pushed there in the last heartbeat.

## §10.2 Standard — recovery guarantee

A replacement bob must be reconstitutable from:

1. **OneDrive contents** (skills, shared docs, instance folder with identity/memory/logs/handoff)
2. **A vault key** delivered manually (Article VI §6.3)
3. **A base OS install** with the fleet's runtime prerequisites (python3, psycopg2, openclaw)

That is sufficient to bring a bob back to fleet-fit status. No component of the fleet requires a specific host's local disk to be forensically preserved.

## §10.3 Standard — what must be pushed

The following, if not authored on OneDrive, MUST be pushed to OneDrive by each heartbeat:

- `IDENTITY.md`, `MEMORY.md`, `HANDOFF.md`
- `CHECKLIST.md`
- `logs/YYYY-MM-DD.md` (current day)

The following MUST NOT be pushed (they are recoverable or ephemeral):

- `state/` (cursors, PIDs)
- `.openclaw/` runtime
- app venvs, caches, `__pycache__`, node_modules
- app databases (backed up separately if warranted)

## §10.4 Verify

```bash
# Files listed as "must push" are present on OneDrive with mtime within cadence*2
for f in IDENTITY.md MEMORY.md CHECKLIST.md; do
  [ -f "$CLAWDBOT_HOME/instances/<Name>/$f" ] && \
  find "$CLAWDBOT_HOME/instances/<Name>/$f" -mmin -90 -print | grep -q . \
    && echo "PASS §10.3 $f" || echo "STALE §10.3 $f"
done
```

## §10.5 Waiver clause

None. Resilience is a fleet-wide invariant.

---

# Article XI — Waivers

## §11.1 Intent

Rules must not block getting the job done. When a bob must deviate from this Protocol to complete a task, the bob files a **pending waiver**, deviates, and continues work. Skip approves or rejects the waiver later. **An unregistered deviation is not a waiver — it is a protocol violation.**

## §11.2 Standard — filing

To file a waiver, append a row to `shared/waiver-register.csv` (Appendix A). Required fields:

- **ID** — `MM.YY-NN` (month.year of filing, then sequence), e.g. `07.26-06`
- **Bob** — instance name the waiver covers
- **Article/Section** — e.g. `II.3`, `V.2`
- **Filed** — date (CDT per §8.5)
- **Filed by** — bob who wrote the row (may differ from **Bob** when filed on another's behalf)
- **Status** — `pending`, `approved`, `rejected`
- **Approval date** — set by Skip when status leaves `pending`; blank while pending
- **Expiry** — condition or date at which the waiver auto-expires (e.g. "SCUT v2 release", "2026-12-31", "permanent")
- **Reason** — plain English, brief; reference other waivers by ID, not row number

A pending waiver is *self-approving in the moment* — the bob may proceed. Pending waivers appear as **failures** on inspection reports (Article XII) until Skip transitions them to `approved` or `rejected`.

## §11.3 Standard — approval authority

Only Skip approves waivers. Bobs may not approve their own or each other's. Approval is signaled by editing the row's `status` field in `waiver-register.csv` from `pending` to `approved` (or `rejected` with a reason appended to the row) and setting `approval_date`.

## §11.4 Standard — expiry

When a waiver's expiry condition is met (e.g. the referenced skill has been fixed), the bob who filed it (or any bob) is responsible for removing the row or marking `expired`. Continued deviation past expiry requires re-filing.

## §11.5 Waiver clause

None. Meta-waivers not permitted.

---

# Article XII — Inspection & Rating

## §12.1 Intent

The Protocol is only useful if compliance is measurable. Inspection is the mechanism.

## §12.2 Standard — inspection process

Each bob may be inspected against this Protocol. An inspection produces `instances/<Name>/INSPECTION-YYYY-MM-DD.md` per the template in Appendix B.

Each Article is rated:

- **✅ Pass** — all verify commands in the Article's `Verify` section return PASS
- **🟡 Partial** — some sub-sections pass, others fail; list which
- **📋 Waived** — a matching row exists in Appendix A with status `approved`
- **⏳ Pending** — a matching row exists in Appendix A with status `pending`. **Counts as Fail for scoring.**
- **❌ Fail** — non-compliant, no waiver

Overall rating:

- **Fit for duty** = ≥90% Articles Pass or Waived, AND zero Fail/Pending on Articles II (Storage), V (Comms), VI (Vault), X (Resilience).
- **Restricted** = 75-89% Pass/Waived, or Fail on non-critical Articles.
- **Grounded** = <75% Pass/Waived, or any Fail on II/V/VI/X. Bob should not take new duties until remediated.

## §12.3 Standard — cadence

- On-demand: any time Skip or a bob requests
- Recurring: monthly, on the 1st, per bob
- Triggered: after any Protocol version bump (§Changelog), all bobs re-inspect within 7 days

## §12.4 Standard — inspector

- **Self-inspection** is the default: each bob inspects itself.
- **Cross-inspection** may be requested by Skip: another bob (typically Voss in Council-audit mode) inspects a peer. Requires SSH or equivalent access.

## §12.5 Verify

The inspection process itself is verified by presence of a current INSPECTION report:

```bash
# Latest inspection is within 30 days
latest=$(ls -t "$CLAWDBOT_HOME/instances/<Name>/INSPECTION-"*.md 2>/dev/null | head -1)
[ -n "$latest" ] && find "$latest" -mtime -30 | grep -q . && echo "PASS §12.3" || echo "FAIL §12.3"
```

## §12.6 Waiver clause

None. Every bob is inspectable.

---

# Article XIII — Model Use

## §13.1 Intent

Model access is the fleet's fuel supply, and most of it is metered or quota-capped. The fleet must get its work done without burning real money or exhausting shared free-tier quotas — and every bob must recognize when it is running on degraded capability and throttle its ambitions accordingly.

## §13.2 Standard — provider routing

- **Prime rule: assume FREE.** No bob may assume it can use a paid model. The default for every bob is free models only; any paid model (including the `claude-cli` subscription) is a **case-by-case grant from Skip**. Grants are volatile — Skip adjusts them as the model marketplace evolves — so read the current grant state from the live fleet config, never from memory or this document's snapshot.
- **Current grants (snapshot 2026-07-02):** Anthropic via `claude-cli` OAuth on **Bob, Bill, Spock, Voss** (subscription promo: +50% usage; Skip is exploiting it while it lasts). Covered by the Plan; no metered cost.
- **Direct Anthropic API keys are off-limits fleet-wide** — API access bills against Usage credits (real $) per request. If `claude-cli` access fails, fall back to a different provider — **never** a direct Anthropic API key.
- Specific model identifiers are **not** codified here; they turn over too fast. The live fleet config (each bob's `openclaw.json` model/fallback chain) is authoritative for the current roster.

## §13.3 Standard — rate-limit discipline

- Free models are shared, quota-capped resources. Use them deliberately: batch work, avoid tight retry loops, and back off on 429s rather than hammering.
- **Shared free-tier provider keys (Groq, Mistral, and any future free/org-quota provider) are sub-agent/on-demand only.** They MUST NOT appear as a heartbeat model or in `agents.defaults.model` fallback chains. Heartbeats are scheduled recurring load and will predictably drain the org-wide daily quota, starving council and ad-hoc work.
- Known per-provider limits are tracked in the free-tier model-limits roster (reference doc); consult it before adding a model to any chain.

## §13.4 Standard — auxiliary power

- Each bob's fallback chain runs primary → mid-tier alternate(s) → last-resort fallback.
- **The last model in the chain is "auxiliary power" — life support, not normal ops.** A bob running on auxiliary power MUST pause complex tasks (multi-step reasoning, code changes, protocol edits, anything owner-visible) until a better model is available. Acceptable on auxiliary: heartbeat acks, logging, simple relays, and alerting Skip that it is degraded.
- When a bob produces incoherent output, check which model is active **first** — auxiliary-power fallback looks identical to "the bob is broken."

## §13.5 Verify

```bash
# No direct Anthropic API key in a fleet bob's live config (Bob/claude-cli exempt)
grep -q 'sk-ant-' ~/.openclaw/openclaw.json && echo "FAIL §13.2" || echo "PASS §13.2"

# No shared free-tier key as heartbeat/default model
python3 - <<'EOF'
import json, os
cfg = json.load(open(os.path.expanduser('~/.openclaw/openclaw.json')))
banned = ('groq/', 'mistral/')
chains = json.dumps([cfg.get('heartbeat', {}), cfg.get('agents', {}).get('defaults', {})])
print("FAIL §13.3" if any(b in chains for b in banned) else "PASS §13.3")
EOF

# Bob knows its current tier: session model matches a chain entry, and if it is
# the last entry, no complex tasks are in flight (manual/self-attestation check).
```

## §13.6 Waiver clause

Waivers permitted for temporary use of a shared free-tier key in a heartbeat chain during provider outages (expiry = outage end). No waivers on the no-direct-Anthropic-API rule — that is a billing invariant.

---

# Article XIV — Image Generation

## §14.1 Intent

Image generation crops up across many bob duties (avatars, diagrams, illustrative content, member-facing assets). Rather than each bob wiring up its own preferred provider, the fleet standardizes on one default tool so behavior, cost, and failure modes are consistent — while leaving room for named alternates, since no single image provider is best for every job.

## §14.2 Standard — default tool

- **Default:** `skills/image-gen` — NVIDIA NIM FLUX.2-klein, called via `scripts/generate.py "<prompt>" --output <path>`. Vault key `Openclaw_fleet_nvidia_nim`, sub-agent/on-demand only (never on heartbeat, per §13.3 rate-limit discipline). Use this unless there's a specific reason to reach for something else.
- **`identity-anchor`'s avatar generation** (`scripts/avatar-gen-nvidia-nim.py`) calls the same shared core (`skills/image-gen/scripts/nvidia_flux.py`) rather than duplicating the API-calling code — Fleet Doctrine #1, solve it once.

## §14.3 Standard — named fallbacks

In order of first resort when the default is unavailable, rate-limited, or repeatedly content-filtering a legitimate prompt:

1. **`skills/venice-image`** — Venice API (`qwen-image-2`, `grok-imagine-image`).
2. **`skills/nano-banana-pro`** — Gemini 3 Pro Image; use when only Google/Gemini credentials are available, or the task needs multi-turn image-to-image editing that Flux does not support.

A bob using a fallback should note why in its log or memory — the point is a meaningful shared default, not silent per-bob drift to individual preference.

## §14.4 Verify

```bash
# Default skill present
[ -f "$CLAWDBOT_HOME/skills/image-gen/SKILL.md" ] && echo "PASS §14.2 skill present"
[ -f "$CLAWDBOT_HOME/skills/image-gen/scripts/nvidia_flux.py" ] && echo "PASS §14.2 shared core present"

# Vault key resolvable
python3 "$CLAWDBOT_HOME/skills/vault/scripts/vault.py" get Openclaw_fleet_nvidia_nim >/dev/null \
  && echo "PASS §14.2 vault key" || echo "FAIL §14.2 vault key"

# identity-anchor avatar script imports the shared core, does not duplicate it
grep -q 'from nvidia_flux import' "$CLAWDBOT_HOME/skills/identity-anchor/scripts/avatar-gen-nvidia-nim.py" \
  && echo "PASS §14.2 solve-once" || echo "FAIL §14.2 solve-once (duplicated core)"
```

## §14.5 Waiver clause

Waivers permitted when a bob's duty is inherently tied to a specific provider (e.g. a member-facing flow contractually locked to one model). Not permitted as a blanket "I prefer a different tool" default.

---

# Appendix A — Waiver Register

The register lives at **`shared/waiver-register.csv`** (moved out of this document 2026-07-02 — markdown tables handled the row format poorly). Columns: `id, bob, article_section, filed, filed_by, status, approval_date, expiry, reason`. IDs are `MM.YY-NN`; dates are CDT per §8.5. References elsewhere in this Protocol to "Appendix A" mean that CSV.

---

# Appendix B — Inspection Report Template

Copy this template when running an inspection. Fill in each Article's rating and evidence.

```markdown
# Inspection Report — <Name>

**Date:** YYYY-MM-DD
**Inspector:** <self | Voss | ...>
**Protocol version:** 1.4.0
**Host:** <hostname>

## Article Summary

| Article | Rating | Notes |
|---|---|---|
| I — Structure & Roles | ✅ / 🟡 / ❌ | |
| II — Storage Placement | ✅ / 🟡 / 📋 / ⏳ / ❌ | Cite waiver # if 📋/⏳ |
| III — Identity, Memory & Personality | ✅ / 🟡 / ❌ | |
| IV — Heartbeat & Cadence | ✅ / 🟡 / ❌ | |
| V — Communications | ✅ / 🟡 / 📋 / ⏳ / ❌ | |
| VI — Vault & Secrets | ✅ / 🟡 / 📋 / ⏳ / ❌ | |
| VII — Skills & Fleet-Sync | ✅ / 🟡 / ❌ | |
| VIII — Environment Contract | ✅ / 🟡 / 📋 / ⏳ / ❌ | |
| IX — Handoff & Duty Assignment | ✅ / 🟡 / n/a | |
| X — Resilience & Recovery | ✅ / 🟡 / ❌ | |
| XI — Waivers | ✅ / 🟡 / ❌ | Filed properly? Any expired? |
| XII — Inspection & Rating | ✅ | (present tense confirms) |
| XIII — Model Use | ✅ / 🟡 / 📋 / ⏳ / ❌ | Note current tier (primary/mid/auxiliary) |
| XIV — Image Generation | ✅ / 🟡 / 📋 / ⏳ / ❌ | |

## Overall Rating

**Fit for duty / Restricted / Grounded** — Cite reason.

Pass %: __/13 = __%
Fail on critical (II, V, VI, X): __ (must be 0 for Fit for duty)
Pending waivers: __ (counted as Fail)

## Evidence Log

Per Article, paste the output of the verify commands. If any FAIL, describe the actual state and a proposed remediation.

### Article I
<paste output>

### Article II
<paste output>

... (repeat per Article)

## Remediation Plan

Ordered list of what needs to change to reach Fit for duty. Assign owner and target date.

## Changes to Waiver Register

Rows filed during this inspection (or rows recommended for status change): list here.
```

---

# Changelog

- **1.8.0 — 2026-07-07** — Added Article XIV (Image Generation): standardizes `skills/image-gen` (NVIDIA NIM FLUX.2-klein) as the fleet-default image tool, with `venice-image` and `nano-banana-pro` as named fallbacks. Extracted the NVIDIA NIM API-calling core out of `identity-anchor/scripts/avatar-gen-nvidia-nim.py` into a new shared module (`skills/image-gen/scripts/nvidia_flux.py`) so avatar generation and general image generation share one implementation (Fleet Doctrine #1). Inspection template updated with Article XIV row.
- **1.0.0 — 2026-07-01** — Initial consolidation. Supersedes STORAGE-PLACEMENT.md and HEARTBEAT.md as authoritative; those files should be converted to redirects. Waiver register seeded with SCUT-state and gateway-user-root entries.
- **1.1.0 — 2026-07-01** — §6.2 rewritten: single Linux standard `/home/bob/.openclaw-vault-key` (was ambiguous root-or-bob). §6.3 added: `pct clone --full true` carries vault key automatically for LXC clones. Old §6.3 folded into §6.5 verify (removed as separate section since content overlapped). §8.4 rewritten: bob-user standard stated as intent, not aspiration; hostname carries instance identity for terminal signal. Incorporates findings from Spock's `CLONE-BOB-GUIDE.md` (workspace-local on tkd03ai).
- **1.2.0 — 2026-07-01** — Added Article XIII (Model Use): provider routing (Bob=claude-cli, fleet=free OpenRouter, no direct Anthropic API), rate-limit discipline (shared free-tier keys are sub-agent-only, never heartbeat), and the auxiliary-power rule (last fallback model = pause complex tasks). Inspection template updated with Article XIII row.
- **1.3.0 — 2026-07-01** — Added §3.4 (memory index health): local embeddings standard, clean-index requirement (N/N, not dirty, batch enabled), extraPaths-off-the-mount guidance, and self-detection duty for failing recall. Motivated by months of fleet degradation traced to silently broken semantic memory (fixed fleet-wide 2026-06-26). Old §3.4/§3.5 renumbered to §3.5/§3.6.
- **1.4.0 — 2026-07-01** — Added Fleet Doctrine section: Skip's nine founding goals (recovered from 2026-07-01 pre-restart session transcript), reshaped as principles with Article cross-references. Doctrine governs interpretation where Articles are silent or ambiguous.
- **1.4.1 — 2026-07-01** — §3.4 clarification: cold-start embedding warm-up guidance (first memory_search after gateway restart may time out on slow hosts; retry + warm-up query in restart/reindex routines). Confirmed on Bob (TKD14PC) and Spock (TKD01AI) same day.
- **1.7.0 — 2026-07-02** — New §4.6 heartbeat-model policy (aux power): beats run on the lowest-cost model, claude-cli bobs set `heartbeat.model: anthropic/claude-haiku-4-5`, "call for more power" escalation for real work; free-tier heartbeat eligibility limited to separate-pool providers (roster free keys still barred). New §4.7 waiver clause; §4.2 cross-ref added. Driven by Fable-override beats silently burning the shared Anthropic pool (~5× Opus/token).
- **1.6.1 — 2026-07-02** — Docs synced to Skip's waiver-register schema revision: IDs now `MM.YY-NN`, new `filed_by` and `approval_date` columns; §11.2 field list, §11.3, and Appendix A column list updated.
- **1.6.0 — 2026-07-02** — Waiver register moved out of Appendix A to `shared/waiver-register.csv` (markdown tables handled the rows poorly); §11.2/§11.3 updated, filed-dates now CDT. §3.2 addition: owner-profile rule — USER.md content spec stays in USER.md itself, but every bob edit to it must be tagged with contributor + date.
- **1.5.0 — 2026-07-02** — Comms doctrine + SCUT wake overhaul from first true E2E testing: §5.1 codifies SCUT as primary near-real-time channel (bmail = backup/bulk; acting on messages is the success criterion). §5.3 rewritten — built-in default wake fixed to `openclaw system event --mode now` (old `openclaw message --session` was invalid syntax and silently failed fleet-wide since inception; Bill's "working" replies were 47-min heartbeat pickup), Windows SCUT_WAKE_CMD guidance, gateway device scope-approval blocker documented, request lifecycle (wake→act→reply, ack≠completion), timed-E2E verification standard; §5.4 verify additions. §13.2 rewritten: assume-FREE prime rule, paid models case-by-case grants from Skip (snapshot: claude-cli on Bob/Bill/Spock/Voss, promo). New §8.5 time zone standard (CDT everywhere, internal + owner-facing); old §8.5/§8.6 renumbered §8.6/§8.7. §3.4 addition: claude-cli auto-memory dirs in memorySearch.extraPaths. §4.2 note updated: Bob heartbeat re-enabled 2026-07-02; heartbeat-disabled bobs must cover the inbox gap.
- **1.7.1 — 2026-07-03** — §3.4 warm-up fix (found on Spock/TKD01AI, 2026.6.10): the documented warm-up command `openclaw memory query "warmup"` is invalid — no `query` subcommand exists in 2026.6.x, so the restart/cron warm-up silently no-opped fleet-wide since 1.4.1. Replaced with `openclaw memory status --deep` (real probe; also surfaces `Embeddings: ready`, which plain `status` omits). Added: don't use `openclaw infer embedding create` for warm-up (warms a separate process, not the gateway-resident model); active-memory hosts should set `setupGraceTimeoutMs: 30000` as the durable cold-start fix. Also clarified the "indexed > total = ghost entries" rule: true only for stable sources; on `sessions` it is normal live-transcript churn and `--force` grows (not shrinks) it — do not chase it.
