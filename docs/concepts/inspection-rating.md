# Inspection and Rating

Protocol is only useful if compliance is measurable. The inspection system provides that measurement — a structured, per-article assessment that produces a clear overall rating. Ratings drive duty eligibility, flag remediation needs, and give the owner a fleet health snapshot at a glance.

---

## Purpose

An inspection answers one question: is this bob fit to take on duties, or does something need to be fixed first?

It does this by checking each protocol article, rating it, and rolling up to an overall rating. The process is repeatable and auditable — two different bobs inspecting the same host on the same day should reach the same conclusion.

---

## Output

Each inspection produces an `INSPECTION-YYYY-MM-DD.md` file, written to the inspected bob's workspace. The template is at `templates/inspection-report.md`.

The report records:

- Bob name, serial, host, inspector, date
- Per-article rating and brief finding
- Overall rating with justification
- Remediation items (if any), each with a target date

---

## Per-Article Ratings

| Rating | Symbol | Meaning |
|---|---|---|
| Pass | ✅ | Article requirements met |
| Partial | 🟡 | Some requirements met, minor gaps |
| Waived | 📋 | Active registered waiver covers this deviation |
| Pending | ⏳ | Not yet checked — counts as **Fail** for overall rating |
| Fail | ❌ | Requirements not met, no waiver |

**Pending is not a neutral state.** If you did not check an article, it fails. Do not leave articles as Pending and expect them to not affect the overall rating.

---

## Overall Ratings

### Fit for Duty

Requirements:
- 90% or more of articles rated Pass or Waived
- Zero Fail or Pending on any **critical article**

Critical articles: Storage, Comms, Vault, Resilience.

A bob rated Fit for Duty may take on any duty the owner assigns.

### Restricted

Requirements:
- 75-89% of articles rated Pass or Waived
- OR: one or more Fail ratings on non-critical articles (with no Fail on critical articles)

A bob rated Restricted may continue existing duties but should not take on new ones until the deficiencies are addressed. Owner may grant an exception.

### Grounded

Requirements (any one of these triggers Grounded):
- Fewer than 75% of articles rated Pass or Waived
- OR: any Fail on a critical article (Storage, Comms, Vault, Resilience)

A Grounded bob should not accept new duties. Existing duties should be handed off or suspended. The bob focuses on remediation. Re-inspection is required before returning to active status.

---

## Calculating the Percentage

Count only articles that have a rating. Pending counts as Fail, not as unrated.

```
Pass/Waived count ÷ Total article count = compliance percentage
```

Example: 11 articles total, 9 Pass, 1 Waived, 1 Partial → (9+1) ÷ 11 = 91% → Fit for Duty (assuming no Fail on critical articles).

---

## Inspection Cadence

| Trigger | Timing |
|---|---|
| On-demand | Owner request, or bob self-initiates |
| Scheduled | Monthly on the 1st |
| Protocol version bump | All bobs re-inspect within 7 days of the new version taking effect |

The monthly scheduled inspection is a hard requirement, not a suggestion. A bob that goes more than 45 days without an inspection should be flagged by the fleet watchdog.

---

## Who Inspects

**Default: self-inspection.** The bob generates its own report. This is sufficient for routine compliance monitoring.

**Cross-inspection:** The owner may direct one bob to inspect another. The inspecting bob needs SSH or equivalent access to the target host (see `docs/concepts/handoff-protocol.md`). Cross-inspection results are authoritative over self-inspection results if they conflict.

A bob may not inspect itself for the purpose of clearing a Grounded rating imposed by someone else. That requires cross-inspection.

---

## After a Grounded Rating

1. Bob generates a remediation plan — specific actions with target dates, one item per deficiency.
2. Plan is sent to owner via bmail (type: `remediation-plan`).
3. Bob works through the plan. Each item resolved is noted in the daily log.
4. When all critical-article deficiencies are resolved, bob requests re-inspection via bmail.
5. Cross-inspection is recommended (not required) for clearing a Grounded status.
