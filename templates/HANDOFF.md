# HANDOFF.md — [SENDER_NAME] → [RECEIVER_NAME]

> **Note:** This file signals an in-progress duty transfer. Once the receiver has read and acknowledged it, delete this file (or move it to `archive/handoffs/`) to signal the handoff is complete. Do not leave it in place indefinitely — a HANDOFF.md that persists becomes stale and misleading.

---

**Date:** [DATE]
**Sender:** [SENDER_NAME] ([SENDER_HOST])
**Receiver:** [RECEIVER_NAME] ([RECEIVER_HOST])
**Transfer Type:** [Full / Partial / Temporary]
**Expected Duration:** [Permanent / Until [DATE] / Until [CONDITION]]

---

## Context

[Describe why this handoff is happening. Examples: scheduled rotation, sender going offline for maintenance, receiver taking over a specific project, emergency coverage.]

---

## Duties Being Transferred

[List what the receiver is now responsible for. Be specific — vague entries create gaps.]

- [ ] [DUTY_1]
- [ ] [DUTY_2]
- [ ] [DUTY_3]

---

## Active Work in Progress

[List anything currently mid-flight that the receiver needs to pick up. Include enough context to continue without asking.]

### [TASK_OR_PROJECT_NAME]

**Status:** [Where it stands right now]
**Last action:** [What was done most recently]
**Next step:** [Exactly what needs to happen next]
**Blockers:** [Anything preventing progress, or "none"]
**Key files/paths:** [Relevant file paths, repos, or configs]

### [TASK_OR_PROJECT_NAME]

**Status:**
**Last action:**
**Next step:**
**Blockers:**
**Key files/paths:**

---

## Open Items Transferred

[Copy relevant entries from MEMORY.md open items, or reference them directly.]

1. [ITEM]
2. [ITEM]

---

## Access & Context the Receiver Needs

[Anything the receiver may not already have — vault keys, credentials hints, access patterns, documentation locations.]

- Vault key: [Already on receiver's host / needs to be delivered via [METHOD]]
- Relevant credentials: [vault key paths, e.g., `vault get someservice/password`]
- Key docs: [file paths]
- Monitoring: [how to check health of transferred duties]

---

## Standing Instructions for the Duration

[Any specific instructions that apply only during this receiver's coverage window.]

[CUSTOMIZE or delete: e.g., "Escalate anything related to production deploys to [OWNER_NAME] directly rather than handling autonomously." / "Standard operating procedures apply — use judgment."]

---

## Handoff Acknowledgment

**Receiver confirms receipt:** [ ] (replace with date/timestamp when acknowledged)

Once acknowledged, archive or delete this file.
