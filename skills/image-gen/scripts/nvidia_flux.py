#!/usr/bin/env python3
"""
NVIDIA NIM FLUX.2-klein core — shared image-generation logic.

Not a CLI. Imported by generate.py (this skill, general-purpose) and by
identity-anchor/scripts/avatar-gen-nvidia-nim.py (avatar-specific wrapper),
so the API-calling code lives in exactly one place (Fleet Doctrine #1).

Endpoint:
  POST https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b

Schema constraints:
  - height, width: 1024 (only supported resolution)
  - cfg_scale: MUST be exactly 1 (schema rejects <1 and >1 despite docs implying a range)
  - steps: 1-4 (4 recommended for quality)
  - seed: int (0 = random)

Response:
  {"artifacts": [{"base64": "<png or empty>", "finishReason": "SUCCESS|CONTENT_FILTERED", "seed": int}]}
"""

import base64
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

NVIDIA_NIM_ENDPOINT = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b"

FALLBACK_PROMPTS = {
    "minimal": "Simple geometric icon. Abstract shapes, 1-2 colors, centered square.",
    "retro": "Retro sci-fi icon. Bold outlines, limited palette.",
    "tech": "Minimalist technology icon. Clean lines, futuristic aesthetic.",
    "abstract": "Abstract geometric shape. Centered, distinctive color.",
}


def get_home():
    """Locate Clawdbot_Home."""
    ch = os.environ.get("CLAWDBOT_HOME", "")
    if ch and Path(ch).is_dir():
        return Path(ch)
    for p in [
        Path(r"C:\Users\skipz\OneDrive - exec-it.us\Tools\AI_Workspace\Clawdbot_Home"),
        Path("/mnt/clawdbot-home"),
    ]:
        if p.is_dir():
            return p
    return None


def get_nvidia_nim_key():
    """Get NVIDIA NIM API key from vault (Openclaw_fleet_nvidia_nim), else env fallback."""
    try:
        home = get_home()
        vault_py = home / "skills" / "vault" / "scripts" / "vault.py" if home else None
        if vault_py and vault_py.exists():
            import subprocess
            result = subprocess.run(
                [sys.executable, str(vault_py), "get", "Openclaw_fleet_nvidia_nim"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
    except Exception:
        pass
    return os.environ.get("NVIDIA_NIM_API_KEY", "")


def call_nvidia_nim(prompt, seed=0, steps=4):
    """Call NVIDIA NIM FLUX.2-klein. Returns (response_dict, error_str)."""
    api_key = get_nvidia_nim_key()
    if not api_key:
        return None, "No NVIDIA NIM API key found (vault Openclaw_fleet_nvidia_nim or env NVIDIA_NIM_API_KEY)"

    payload = {
        "prompt": prompt,
        "height": 1024,
        "width": 1024,
        "cfg_scale": 1,
        "samples": 1,
        "seed": seed,
        "steps": steps,
    }

    req = urllib.request.Request(
        NVIDIA_NIM_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=120)
        return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        return None, f"HTTP {e.code}: {error_body[:500]}"
    except Exception as e:
        return None, str(e)


def extract_image(response):
    """Extract PNG bytes from an NVIDIA NIM response. Returns (bytes_or_None, error_or_None)."""
    if not response or "artifacts" not in response:
        return None, "No artifacts in response"

    artifact = response["artifacts"][0]
    finish_reason = artifact.get("finishReason", "UNKNOWN")

    if finish_reason == "CONTENT_FILTERED":
        return None, "CONTENT_FILTERED"

    b64_data = artifact.get("base64", "")
    if not b64_data:
        return None, f"Empty base64 (finishReason={finish_reason})"

    try:
        return base64.b64decode(b64_data), None
    except Exception as e:
        return None, f"Base64 decode failed: {e}"
