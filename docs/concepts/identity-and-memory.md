# Identity and Memory

A bob that loses track of who it is mid-session will produce incoherent output — wrong tone, wrong priorities, wrong fleet awareness. Identity is not cosmetic. It is the load-bearing structure that makes every other protocol section work. This document explains the three-file identity stack, how semantic memory works locally, and the rules for maintaining both.

---

## The Three Required Files

Every bob must have all three files present and current before taking on any duty.

### IDENTITY.md — Who I Am

This is the bob's self-description. It covers serial, role, host, emoji (if any), current duties, personality notes, and which protocol articles have active waivers. It is read at session start. If it is missing, the bob should halt and reconstruct it from shared storage before proceeding.

Minimum required sections:

```markdown
## Identity
- Name / Serial
- Host / IP / Container
- Role
- Emoji (optional)

## Current Duties

## Active Waivers

## Notes
```

### MEMORY.md — What I Know

This is the accumulated long-term knowledge store: fleet roster, key findings, open items, configuration gotchas, and anything that must survive a context wipe. It is distinct from session logs — logs record what happened; MEMORY.md records what matters.

Write to MEMORY.md when you learn something non-obvious that a future session (or a different bob inheriting a duty) would need. Do not write routine operational events here — that goes in the daily log.

Format by topic section, not chronologically. Latest updates go at the top of the relevant section, not appended to the bottom.

### Daily Logs — What I Did

Store at `logs/YYYY-MM-DD.md` in the bob's workspace. The heartbeat protocol requires updating this file each cycle. It is the primary audit trail for what happened during a session and is also indexed by the memory system.

---

## The Memory Index (Semantic Search)

The fleet uses local embeddings for semantic memory search — no cloud call, no data leaving the host.

**Why local:** Fleet operations involve vault references, internal IPs, session details, and personnel information. Sending that to an embedding API is a needless risk. The local model is fast enough for the fleet's query volume and runs on hardware the fleet controls.

**Model in use:**
```
~/.node-llama-cpp/models/hf_ggml-org_embeddinggemma-300m-qat-Q8_0.gguf
```

### Verifying the Index is Healthy

```bash
openclaw memory status --deep
```

Look for these fields in the output:

| Field | Healthy value | Meaning |
|---|---|---|
| `Embeddings` | `ready` | Model loaded and responsive |
| `Dirty` | `no` | Index is current with source files |
| `Batch` | `disabled` | **Degraded** — bulk indexing is off |

`Batch: disabled` means new content will not be indexed automatically. The index will drift over time. Fix: check resource limits on the container. The embedding model needs at least 2 CPU cores and 2GB RAM to run batch indexing without stalling.

### Ghost Entries

The index tracks a count of indexed entries vs. total source documents. When `Indexed > Total` on a stable source (such as the shared folder), you have ghost entries — stale index records pointing to content that has been deleted or moved.

```
Indexed: 847  Total: 831  ← ghost entries present
```

Fix:

```bash
openclaw memory reindex --force
```

**Exception:** On the `sessions` source, `Indexed > Total` is normal. Sessions are pruned regularly but index cleanup runs on a slower schedule. Do not force-reindex sessions on this basis.

### Cold-Start Timeouts

After a container restart, the first `memory_search` call may time out. This is not a bug — the embedding model is loading from disk and warming up. Retry once after 10-15 seconds. If it times out a second time, check available RAM:

```bash
free -m
```

If free memory is under 200MB, the model cannot load. Either wait for other processes to release memory or ask the owner to bump the container's RAM allocation.

---

## Extra Index Paths

The memory system indexes the bob's workspace by default. To include the shared fleet storage and any harness-managed memory directories, add them to `memorySearch.extraPaths` in `openclaw.json`:

```json
"memorySearch": {
  "extraPaths": [
    "/mnt/clawdbot-home/shared",
    "~/.claude/projects/-home-bob--openclaw-workspace/memory"
  ]
}
```

Claude-cli bobs accumulate harness memory at `~/.claude/projects/<project-path>/memory/`. This directory is not in the default index path. If you want `memory_search` to surface harness-managed notes (including this MEMORY.md file), that path must be in `extraPaths`.

---

## Voice Divergence

Each bob develops a distinct voice. This is intentional and encouraged — a fleet of identical communicators is brittle and harder to work with than a crew of differentiated individuals.

`SOUL.md` (at `/mnt/clawdbot-home/shared/SOUL.md`) provides the base disposition all bobs share: evidence-first reasoning, terse over verbose, dry humor, no reassurance-over-substance. Individual bobs extend this in their IDENTITY.md. They do not override it.

The fleet does not enforce voice uniformity through technical controls. Divergence is governed by shared values, not guardrails.

---

## USER.md Attribution Rule

`USER.md` at `/mnt/clawdbot-home/shared/USER.md` is the authoritative profile of the person the fleet serves. It is the highest-trust file in shared storage.

Every edit to USER.md must be tagged with the contributing bob and the date:

```markdown
<!-- Updated: Spock (002) · 2026-07-10 -->
```

Place the tag immediately before or after the edited section, not at the end of the file. This lets any bob or the owner trace which bob made which change and when. Untagged edits are considered unauthorized modifications — the owner may revert them.
