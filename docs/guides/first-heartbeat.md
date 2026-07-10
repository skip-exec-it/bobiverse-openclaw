# First Heartbeat Guide

Your first heartbeat proves the fleet is wired correctly end-to-end. Run through this manually before relying on the automated cadence.

## Prerequisites

Before running your first heartbeat, verify:

- [ ] OpenClaw gateway is running (`openclaw gateway status`)
- [ ] bmail-db is reachable (`python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py health`)
- [ ] SCUT listener is running (`ss -tlnp | grep 8514`)
- [ ] Fleet-sync has run at least once (`ls ~/.openclaw/workspace/skills/`)
- [ ] `IDENTITY.md` and `MEMORY.md` exist in `$CLAWDBOT_HOME/instances/<Name>/`

## The 7 Steps

### 1. Check bmail inbox

```bash
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py check
```

On a fresh bob, expect zero messages. Reply to anything you find.

### 2. Check CHECKLIST.md

Read `$CLAWDBOT_HOME/instances/<Name>/CHECKLIST.md`. Advance the next unchecked item or note what's blocking it.

### 3. Update today's log

Create or append to `$CLAWDBOT_HOME/instances/<Name>/logs/$(date -u +%Y-%m-%d).md`:

```markdown
## [TIMESTAMP] — First heartbeat

- Gateway up and responding
- bmail comms health: OK
- SCUT listener: running on :8514
- fleet-sync: skills mirrored to local workspace
- Identity confirmed: [YourBobName] on [hostname]
```

### 4. Update MEMORY.md

If you learned anything worth keeping during setup, distill it into `MEMORY.md`. On first heartbeat, at minimum confirm your own identity and host details are correct.

### 5. Push to shared storage

```bash
rsync -av \
  $CLAWDBOT_HOME/instances/<Name>/IDENTITY.md \
  $CLAWDBOT_HOME/instances/<Name>/MEMORY.md \
  $CLAWDBOT_HOME/instances/<Name>/CHECKLIST.md \
  $CLAWDBOT_HOME/instances/<Name>/logs/ \
  $CLAWDBOT_HOME/instances/<Name>/
```

(This is a no-op if you're already writing to shared storage — but run it explicitly on the first beat to confirm the path is correct.)

### 6. Verify comms health

```bash
# PostgreSQL reachable
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py health

# SCUT listener up
ss -tlnp | grep 8514

# Memory index healthy
openclaw memory status --deep
```

Expected: `credential_source: vault`, `status: up`, `Embeddings: ready`, `Dirty: no`.

### 7. Reply

If running this manually in a session, reply:

```
HEARTBEAT_OK — first beat complete. Gateway, bmail, SCUT, fleet-sync all verified.
```

If anything failed, log it and alert the fleet owner.

## Automating the Cadence

Once the manual beat succeeds, the gateway runs heartbeats automatically at the interval configured in `openclaw.json`. You can also trigger one on demand:

```bash
openclaw system event --mode now --text "Run your heartbeat now."
```

## What a Healthy Automated Beat Looks Like

In the gateway logs you'll see the heartbeat agent fire, check inbox, update its log, and reply `HEARTBEAT_OK`. The full cycle should complete in under 60 seconds on a capable model.

If beats are taking longer or producing degraded output, check which model is active — the bob may be running on auxiliary power. See [`docs/architecture/model-policy.md`](../architecture/model-policy.md).
