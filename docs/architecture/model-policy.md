# Model Use Policy

## Prime Rule: Assume Free

**No bob may assume it can use a paid model.** The default for every bob is free models only. Any paid model is a case-by-case grant from the fleet owner. Grants are volatile — read the current grant state from the live fleet config, not from memory or documentation.

This is not a cost-cutting measure. It's an operational discipline: a fleet that depends on paid access breaks the moment that access is revoked, rate-limited, or the budget runs out. A fleet that runs on free models by default is structurally resilient.

## Provider Routing

```
Free OpenRouter models   → default for all bobs
Paid model (e.g. claude) → explicit per-bob grant only
Direct provider API keys → off-limits fleet-wide (bills per-request)
```

**Never use a direct Anthropic (or other paid provider) API key.** If subscription-based CLI access fails, fall back to a different free-tier provider — not a direct API key.

## Cascade Structure

Each bob's model config follows a cascade:

```
primary model      ← best available for this bob's grant level
  ↓ (on failure/429)
mid-tier fallback  ← reliable free model
  ↓
auxiliary power    ← last resort
```

**Auxiliary power = life support, not normal ops.** A bob on its last fallback model should:
- Complete heartbeat acks, logging, simple relays
- Alert the owner that it is degraded
- Pause complex tasks, code changes, protocol edits, anything requiring judgment

A bob producing incoherent output may simply be running on auxiliary power. Check the active model first.

## Heartbeat Model (Aux Power for Beats)

Heartbeats run on the lowest-cost model available to the bob. Left unset, the heartbeat inherits the main session's model — if that's a frontier model, every idle poll burns the shared pool.

**Set the heartbeat model explicitly:**

```json5
// In openclaw.json under agents.list[n] (the "main" agent entry):
{
  "heartbeat": {
    "model": "openrouter/google/gemma-4-31b-it:free"  // or cheapest available
  }
}
```

When a heartbeat surfaces real work (a SCUT request, a multi-step task), the aux model should wake the main model rather than attempting complex work itself.

## Rate-Limit Discipline

Free models are shared, quota-capped resources:

- **Batch work** — don't make 20 sequential calls when one call + post-processing achieves the same result
- **Back off on 429s** — don't retry in a tight loop; wait and try again
- **Shared org-quota providers (Groq, Mistral, etc.) are sub-agent/on-demand only** — never put them in a heartbeat chain or default fallback. Heartbeats run on a schedule and will drain the org-wide daily quota, starving on-demand work.

## Verify

```bash
# No direct paid-provider API key in live config
grep -q 'sk-ant-' ~/.openclaw/openclaw.json && echo "FAIL: direct API key present" || echo "PASS"

# No shared org-quota key in heartbeat or default chain
python3 - <<'EOF'
import json, os
cfg = json.load(open(os.path.expanduser('~/.openclaw/openclaw.json')))
banned = ('groq/', 'mistral/')
chains = json.dumps([cfg.get('heartbeat', {}), cfg.get('agents', {}).get('defaults', {})])
print("FAIL: banned provider in chain" if any(b in chains for b in banned) else "PASS")
EOF
```
