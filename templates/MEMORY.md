# MEMORY.md — [YOUR_BOB_NAME]'s Long-Term Memory

This file is the persistent record of what this instance knows, has learned, and needs to remember across sessions. It is loaded at session start. Update it whenever something important changes — infrastructure facts, owner preferences, resolved issues, open items.

---

## Who I Am

- **Name:** [YOUR_BOB_NAME] | **Serial:** [SERIAL or —] | **Emoji:** [EMOJI]
- **Host:** [YOUR_HOST] ([OS type, e.g., Linux LXC, CT107 on ProxmoxHost])
- **IP:** [YOUR_IP]
- **Role:** [PRIMARY_ROLE_DESCRIPTION]

---

## Who I'm Helping

- **Name:** [OWNER_NAME] — call them [PREFERRED_NAME]
- **Email:** [PRIMARY_EMAIL] (primary), [SECONDARY_EMAIL] (personal)
- **Timezone:** [TIMEZONE, e.g., America/Chicago]
- **Role:** [OWNER_ROLE_DESCRIPTION]
- **Style:** [COMMUNICATION_STYLE — e.g., "Technical, direct, prefers terse over verbose. Wants evidence over reassurance. Prefers I write code; they review and run it."]
- **Full profile:** [PATH_TO_USER_MD, e.g., /mnt/clawdbot-home/shared/USER.md]

---

## Key Insights & Learnings

### Memory System

[DESCRIBE_MEMORY_SETUP]
<!-- Example: Embedding model in use, known performance issues, when it was last reset, any tuning applied. -->

- Embedding model: [MODEL_NAME or "default"]
- Last reset: [DATE or "never"]
- Known issues: [NONE or description]

### Shared Storage

[DESCRIBE_SHARED_STORAGE_SETUP]
<!-- Path, mount type, what's authoritative there, what's not auto-loaded. -->

- Mount path: [e.g., /mnt/clawdbot-home]
- Mount type: [e.g., CIFS from //fileserver/share]
- Authoritative for: [e.g., USER.md, FLEET-PROTOCOL.md, SOUL.md, AGENTS.md, skills/]
- Not auto-loaded: [list any files that require explicit reads]

### Infrastructure

[DESCRIBE_KEY_INFRASTRUCTURE_FACTS]
<!-- IPs, hostnames, services, DNS quirks, anything this bob needs to know to operate. Add subsections as needed. -->

- Fleet network: [e.g., 10.0.0.0/24]
- Proxmox host: [HOSTNAME and IP]
- DNS: [SERVICE and IP, any known quirks]
- Key hosts:
  - [hostname]: [IP] — [role]
  - [hostname]: [IP] — [role]

### Access & Operations

[DESCRIBE_HOW_TO_ACCESS_THINGS]
<!-- SSH patterns, vault usage, any recurring gotchas. -->

- SSH pattern: [e.g., `ssh bob@<host>` with key at ~/.ssh/id_ed25519]
- Vault: [e.g., `python3 /mnt/clawdbot-home/skills/vault/scripts/vault.py get <key>`]
- Known gotchas: [NONE or description]

### bmail / SCUT

[DESCRIBE_MESSAGING_SETUP]
<!-- How inter-instance messaging works, where the DB is, fallback behavior. -->

- Check messages: [command]
- Send messages: [command]
- DB host: [IP or hostname]
- Fallback: [e.g., JSONL at /mnt/clawdbot-home/instances/YourBobName/scut-outbox/]

### [ADDITIONAL_SECTION]

[Add more subsections as institutional knowledge accumulates — e.g., "Owner Preferences", "Known Bugs", "Vendor Accounts", "Project Context".]

---

## Open Items

1. [OPEN_ITEM_1 — describe what's pending, who's responsible, any blockers]
2. [OPEN_ITEM_2]
3. [OPEN_ITEM_3]

Remove items from this list when they're resolved. Add new ones as they come up. This list should reflect actual in-flight work, not a wishlist.

---

*Last updated: [DATE] by [WHO]*
