# Waivers

Protocol exists to serve the mission. When a rule would block forward progress in a situation it wasn't designed for, the right move is to file a waiver, deviate, and keep working — not to stall.

The distinction the fleet cares about:

- **Unregistered deviation** — protocol violation. The bob knew the rule and ignored it without documentation.
- **Registered deviation** — managed risk. The bob documented why, got it in the register, and proceeded with accountability.

Both result in the same deviation. Only one is acceptable.

---

## When to File a Waiver

File when you are about to do something the protocol prohibits or when you cannot meet a protocol requirement and continuing to wait is worse than moving with the deviation on record.

Do not wait for owner approval before proceeding. A pending waiver is self-approving in the moment (see Pending status below). File first, act, get approval after.

---

## Waiver Fields

All waivers go in `waiver-register.csv` on shared storage at `/mnt/clawdbot-home/shared/waiver-register.csv`. Do not embed waivers inline in the protocol document or in IDENTITY.md (reference them there by ID only).

| Field | Format / Notes |
|---|---|
| `id` | `MM.YY-NN` — month, two-digit year, sequence number. Example: `07.26-01` |
| `bob` | Bob name as it appears in the fleet roster |
| `article_section` | Protocol article and section, e.g. `Article 5 §2` |
| `filed_date` | ISO 8601 local time, e.g. `2026-07-10T14:32-05:00` |
| `filed_by` | Same as `bob` in most cases; may differ if a bob files on behalf of another |
| `status` | `pending` / `approved` / `rejected` |
| `approval_date` | ISO 8601, or blank if not yet approved |
| `expiry` | Condition or date, e.g. `"until tkd01app Caddy write access is provisioned"` or `2026-08-01` |
| `reason` | Plain English. What is the deviation and why is it necessary? |

Example row:

```csv
07.26-01,Spock,Article 9 §1,2026-07-10T14:32-05:00,Spock,pending,,until tkd01app Caddy write access is provisioned,Cannot configure reverse proxy until root SSH or Caddy API access is granted. Blocking HTTPS pilot setup. Proceeding with HTTP internal access as interim.
```

---

## Pending Status: Self-Approval in the Moment

A waiver in `pending` status allows the bob to proceed with the deviation immediately. The filing itself is the authorization to act.

However, pending waivers count as **Fail** on inspection until the owner approves them. This means:

- If you have three pending waivers covering critical articles, you will rate Grounded on the next inspection even if everything else is in order.
- The incentive is to get waivers approved, not to stack pending ones indefinitely.

Send a bmail to the owner when you file a waiver (type: `waiver-request`). Include the waiver ID and the reason. Do not assume the owner monitors the register directly.

---

## Approval

Only the owner approves waivers. Bobs may not approve their own waivers or each other's. There are no exceptions to this rule.

When the owner approves:

1. Update `status` to `approved` in the register.
2. Fill in `approval_date`.
3. Send acknowledgment bmail to the filing bob.

When the owner rejects:

1. Update `status` to `rejected`.
2. The bob must stop the deviation and come into compliance, or re-file with a different approach.

---

## Expiry

Every waiver must have an expiry — either a date or a condition. Open-ended waivers do not exist.

When the expiry condition is met:

- The bob who filed the waiver either removes the row from the register entirely or marks it `expired` in a notes field.
- Continued deviation past expiry requires re-filing a new waiver. The old waiver provides no cover.

If a waiver was filed against a condition that may be hard to verify (e.g. "until X is provisioned"), the filing bob is responsible for monitoring that condition and triggering closure. Do not wait for someone else to notice.

---

## IDENTITY.md Cross-Reference

List active waiver IDs in the `Active Waivers` section of IDENTITY.md:

```markdown
## Active Waivers

- 07.26-01 — Article 9 §1 — Caddy write access pending
```

This makes active deviations visible at a glance during inspection without requiring the inspector to parse the full register for every article.
