# Image Generation (Fleet Default)

**This is the fleet-standard tool for "generate/create an image" requests.** See Fleet Protocol Article XIV. It is not the only image tool in the fleet — see Fallbacks below — but it's the default first reach.

## What This Is

NVIDIA NIM's FLUX.2-klein model, called directly via HTTPS. Fast (4-step generation, ~30-60s), no per-bob quota (fleet-shared key, sub-agent/on-demand only — never on heartbeat), good general-purpose quality for icons, illustrations, and scene generation.

## How To Use

```bash
python3 "$CLAWDBOT_HOME/skills/image-gen/scripts/generate.py" "<prompt>" --output <path.png>
```

Examples:

```bash
python3 "$CLAWDBOT_HOME/skills/image-gen/scripts/generate.py" \
  "a lighthouse at dusk, watercolor style" --output out.png

python3 "$CLAWDBOT_HOME/skills/image-gen/scripts/generate.py" \
  "abstract geometric logo, blue and gold" --output logo.png --retry
```

Flags: `--seed N` (0 = random), `--steps 1-4` (4 = best quality, default), `--retry` (auto-retry once with a generic fallback prompt if content-filtered).

**Prompt tips:** keep it descriptive but not sensitive — the filter rejects prompts referencing real people, violence, or NSFW content. If filtered (`CONTENT_FILTERED` in stderr), simplify the prompt or pass `--retry`.

## Technical Details

- **Endpoint:** `POST https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b`
- **Auth:** Bearer token, vault key `Openclaw_fleet_nvidia_nim` (falls back to env `NVIDIA_NIM_API_KEY` if vault unavailable)
- **Fixed resolution:** 1024x1024 only
- **Rate limit:** ~40 req/min community baseline (not a published SLA)
- **Core logic:** lives in `scripts/nvidia_flux.py` — shared with `identity-anchor/scripts/avatar-gen-nvidia-nim.py`, which wraps this same core for avatar-specific output placement (`avatars/`, `instances/<Name>/avatar.png`). Don't duplicate the API-calling code elsewhere; import from here or call this script.

## Fallbacks

If NVIDIA NIM is unavailable, rate-limited, or repeatedly content-filters a prompt that can't reasonably be simplified:

1. **`skills/venice-image`** — Venice API (`qwen-image-2`, `grok-imagine-image`). Use when Flux is down/limited, or the content filter is blocking a legitimate prompt.
2. **`skills/nano-banana-pro`** — Gemini 3 Pro Image. Use when only Google/Gemini credentials are available, or the task needs multi-turn image-to-image editing (iterating on an existing image), which Flux here doesn't support.

Note in your log/memory *why* you used a fallback — this keeps the default meaningful instead of every bob quietly drifting to its own preference.

## Common Issues

**"No NVIDIA NIM API key found"** — check vault key `Openclaw_fleet_nvidia_nim` exists, or set `NVIDIA_NIM_API_KEY` env var as a temporary workaround.

**"CONTENT_FILTERED"** — simplify the prompt (avoid real people, sensitive/violent/NSFW descriptions) or use `--retry`.

**Timeout (~120s)** — endpoint slow or under load; retry in a few minutes or fall back to `venice-image`.
