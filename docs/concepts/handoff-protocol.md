# Handoff Protocol

No bob is indispensable. Any duty must be transferable to any other bob with minimal ramp-up time. The handoff protocol enforces this by requiring that all context needed to continue work be captured in a single structured document before the current owner steps away.

A duty without a HANDOFF.md is a single point of failure.

---

## Why This Matters

Bobs are context-bounded. A session ends, a container restarts, a bob gets grounded, or the owner reassigns a duty mid-stream. When that happens, the receiving bob should be able to pick up within one heartbeat cycle — not spend three cycles reconstructing what happened.

The handoff document is the mechanism. It is not a summary for the archive. It is operational documentation written for the next person holding the tool.

---

## HANDOFF.md Required Sections

Create `HANDOFF.md` in the duty workspace before stepping away. Every section is required. If a section has nothing to say, write "None" — do not omit the heading.

```markdown
# Handoff: <Duty Title>

**To:** <Receiving bob name or "unassigned">
**From:** <Your bob name>
**Date:** <YYYY-MM-DD HH:MM local>

## Current State

[One paragraph. What is the actual state of the work right now?
What is done, what is in progress, what was just started?]

## Next Actions

[Ordered list. The receiver executes these in sequence.
Be specific — not "check the logs" but "check /var/log/caddy/access.log for 502s after 14:00 today".]

1.
2.
3.

## Blockers

[Anything currently preventing forward progress.
If none: "None"]

## Context

[File paths, external system names, relevant bmail threads, documentation URLs.
This section is pointers, not prose. The receiver reads the pointed-to files, not this section.]

- Workspace: `~/workspace/<duty-name>/`
- Relevant shared files: `/mnt/clawdbot-home/shared/<path>`
- External systems: [names and access method, e.g. "Caddy on tkd01app — SSH as root via vault key"]
- Related bmail thread: [date + subject if applicable]

## Sensitive Notes

[Vault key references ONLY. Never write plaintext credentials, tokens, or passphrases here.]

- Vault key: `<service>/<key-name>` — used for [purpose]

```

---

## How the Receiver Picks It Up

1. Read HANDOFF.md in full.
2. Copy the content into your working notes (daily log or a local NOTES.md in the duty workspace).
3. Delete `HANDOFF.md` from the source location, or move it to `archive/HANDOFF-YYYY-MM-DD.md` if you want to keep a history.
4. Send a bmail to the previous owner confirming receipt:

```
Type: duty-receipt
Subject: Handoff received: <Duty Title>
Body: Picked up as of <timestamp>. Starting on next action #1.
```

Do not leave HANDOFF.md in place after you have taken over. A stale HANDOFF.md is misleading — it implies the duty is still being transferred when it has already been received.

---

## Duty Assignment

The owner assigns duties via bmail (type: `duty-assign`) or in-session direction. The assignment names the receiving bob explicitly. If no bob is named, the duty is unassigned and should be escalated back to the owner before any bob picks it up.

Any bob may propose taking on a duty by sending a bmail of type `duty-request`:

```
Type: duty-request
To: owner
Subject: Request: <Duty Title>
Body: [Why this bob is a good fit, current availability, any relevant context]
```

Role or seniority does not gate this. Any bob may request any duty. The owner decides.

---

## Cross-Inspection of Duty Execution

The owner may direct one bob to inspect another bob's execution of a duty. This is not punitive — it is quality control. The inspecting bob needs SSH or equivalent access to the inspected bob's host:

```bash
# SSH as bob to another host in the fleet
sshpass -p "$(python3 /mnt/clawdbot-home/skills/vault/scripts/vault.py get pve/bob)" \
  ssh bob@<target-host-ip>
```

The inspecting bob reads the duty workspace, daily logs, and MEMORY.md, then produces an inspection report (see `docs/concepts/inspection-rating.md`). The report goes to the owner, not to the inspected bob directly.

The inspected bob is not notified in advance. This is by design.
