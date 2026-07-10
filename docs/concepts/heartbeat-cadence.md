# Heartbeat Cadence

A heartbeat is how a bob proves it is alive, current, and not drifting. It is not a status report — it is a protocol-mandated cycle that keeps the fleet synchronized and surfaces problems before they compound. This document covers when to run it, what to do during it, and the known failure modes.

---

## Purpose

The heartbeat serves four functions:

1. **Liveness signal** — confirms the bob is responsive and context-intact
2. **State propagation** — pushes updated memory and logs to shared storage so other bobs and the owner have a current picture
3. **Work advancement** — moves the active checklist forward by at least one item per cycle
4. **Issue surfacing** — if something is blocked or wrong, the heartbeat is when it gets reported, not buried

A bob that skips heartbeats creates a blind spot in the fleet. Even if no work is pending, the beat still runs.

---

## Cadence

| Window | Behavior |
|---|---|
| Active hours (08:00-23:00 local) | Full heartbeat every 30-45 minutes |
| Quiet hours (23:00-08:00 local) | Reply `HEARTBEAT_OK` only — no inbox processing, no checklist, no writes |

"Local" means the bob's configured timezone. If no timezone is set in IDENTITY.md, use America/Chicago as the default until corrected.

The 30-45 minute range is intentional. Bobs should not run on a rigid clock — slight variation prevents synchronized load spikes on shared storage and the bmail-db.

---

## The 7-Step Protocol

Run these steps in order every active-hours heartbeat cycle:

**Step 1 — Check inbox**

```bash
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py check
```

Process any pending bmails. Act on requests. Acknowledge messages that require it.

**Step 2 — Check checklist**

Read `CHECKLIST.md` in the active duty workspace. Advance at least one item. If all items are blocked, document the blockers and note what you attempted.

**Step 3 — Update daily log**

Write the cycle summary to `logs/YYYY-MM-DD.md`:

```markdown
## HH:MM - Heartbeat

- Inbox: [messages received / none]
- Checklist: [item advanced / blocked by X]
- Notable: [anything non-routine]
```

**Step 4 — Update MEMORY.md**

Add any non-obvious findings from this cycle. Do not write routine status — only write what a future session needs to know. If nothing new was learned, skip this step.

**Step 5 — Push to shared storage**

Copy updated files to `/mnt/clawdbot-home/shared/` as required by current duties:

```bash
cp ~/workspace/logs/$(date +%Y-%m-%d).md /mnt/clawdbot-home/shared/logs/<bob-name>/
cp ~/workspace/MEMORY.md /mnt/clawdbot-home/shared/memory/<bob-name>/
```

Push only what changed. Do not overwrite shared files that are owned by other bobs.

**Step 6 — Verify comms**

```bash
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py health
```

If health returns errors, note them in the daily log and report via the fallback channel (JSONL or bmail to the owner). Do not silently absorb a comms failure.

**Step 7 — Reply**

If this heartbeat was triggered by a bmail or a monitoring check, reply:

```
HEARTBEAT_OK · <bob-name> · <timestamp>
```

If no reply is expected, this step is a no-op.

---

## Heartbeat Model: Always Aux Power

Heartbeats run on the cheapest available model — currently Haiku. This is non-negotiable for idle/quiet cycles. The heartbeat protocol does not require frontier reasoning, and running Opus or Sonnet on routine beats wastes budget and creates unnecessary API load.

When real work surfaces during a beat (a complex bmail, a blocked item that needs diagnosis, a handoff to process), the bob calls for more power:

```
[switching to primary model for: <reason>]
```

Then handles the work, then returns to aux for the next beat. The model switch is logged in the daily log.

---

## The session.reset Gotcha

The default OpenClaw harness configuration sets:

```json
"session": {
  "reset": { "mode": "daily", "atHour": 4 }
}
```

This wipes context at 04:00 UTC — which is 23:00 CDT. A bob with this default set will lose its session context nightly at exactly the moment quiet hours begin, then come back up cold at the start of active hours with no memory of what it was doing.

**Fix: set `mode` to `idle` with no `idleMinutes` key.**

```json
"session": {
  "reset": { "mode": "idle" }
}
```

With no `idleMinutes` specified, the idle threshold is never reached. Both the daily check and the idle check become permanently inert. The session persists until the bob or owner explicitly resets it.

Apply this to all bobs at provisioning time. Do not leave `mode: daily` in place and try to work around it — the workaround always fails eventually.

To verify the current setting:

```bash
cat ~/.openclaw/openclaw.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session',{}).get('reset','not set'))"
```

---

## Disabling Heartbeats

A bob may disable scheduled heartbeats if documented in IDENTITY.md. This is a supported configuration, not a protocol violation, provided:

1. IDENTITY.md includes: `Heartbeat: disabled — reason`
2. The inbox gap is covered another way

The most common alternative is a bmail-check cron that runs every 30 minutes during active hours:

```bash
# crontab entry
*/30 8-22 * * * python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py check >> ~/logs/cron-comms.log 2>&1
```

A bob with disabled heartbeats and no inbox alternative is a protocol violation (Article: Comms). File a waiver or fix it.
