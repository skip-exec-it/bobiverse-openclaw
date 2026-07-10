#!/usr/bin/env python3
"""
General-purpose image generation — NVIDIA NIM FLUX.2-klein (fleet default).

This is the fleet's standard tool for "generate me an image" requests
(Fleet Protocol Article XIV). For avatar generation specifically, use
identity-anchor's avatar-gen-nvidia-nim.py, which wraps this same core
and also handles instance-directory placement.

Usage:
  generate.py "<prompt>" --output <path.png> [--seed N] [--steps 1-4] [--retry]

Examples:
  generate.py "a lighthouse at dusk, watercolor style" --output out.png
  generate.py "abstract geometric logo" --output logo.png --retry

If the model content-filters the prompt (finishReason=CONTENT_FILTERED),
rerun with a simpler prompt, or pass --retry to auto-retry once with a
generic fallback prompt.

If NVIDIA NIM is unavailable/rate-limited/repeatedly filtering, fall back to:
  - skills/venice-image  (Venice API — qwen-image-2, grok-imagine-image)
  - skills/nano-banana-pro (Gemini 3 Pro Image — supports image-to-image editing)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from nvidia_flux import call_nvidia_nim, extract_image, FALLBACK_PROMPTS  # noqa: E402


def cmd_generate(prompt, output, seed=0, steps=4, retry_on_filter=False):
    print(f"Generating image...")
    print(f"  Prompt: {prompt}")

    result, err = call_nvidia_nim(prompt, seed=seed, steps=steps)
    if err:
        print(f"[FAIL] API error: {err}", file=sys.stderr)
        return 1

    image_bytes, extract_err = extract_image(result)

    if extract_err == "CONTENT_FILTERED":
        if retry_on_filter:
            print("  (content filtered, retrying with simplified prompt)")
            result, err = call_nvidia_nim(FALLBACK_PROMPTS["abstract"], seed=seed, steps=steps)
            if err:
                print(f"[FAIL] Retry failed: {err}", file=sys.stderr)
                return 1
            image_bytes, extract_err = extract_image(result)

        if extract_err:
            print(f"[FAIL] {extract_err}", file=sys.stderr)
            print("  Try simplifying the prompt, or fall back to skills/venice-image.", file=sys.stderr)
            return 1
    elif extract_err:
        print(f"[FAIL] Extraction failed: {extract_err}", file=sys.stderr)
        return 1

    if not image_bytes:
        print("[FAIL] No image data generated.", file=sys.stderr)
        return 1

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(image_bytes)
    print(f"\n[OK] Saved: {out_path}")
    print(f"  Size: {len(image_bytes):,} bytes")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 1 or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if args and args[0] in ("-h", "--help") else 1)

    prompt = args[0]
    output = None
    seed = 0
    steps = 4
    retry = False

    i = 1
    while i < len(args):
        if args[i] == "--output" and i + 1 < len(args):
            output = args[i + 1]
            i += 2
        elif args[i] == "--seed" and i + 1 < len(args):
            seed = int(args[i + 1])
            i += 2
        elif args[i] == "--steps" and i + 1 < len(args):
            steps = int(args[i + 1])
            i += 2
        elif args[i] == "--retry":
            retry = True
            i += 1
        else:
            i += 1

    if not output:
        print("Error: --output <path> is required", file=sys.stderr)
        sys.exit(1)

    sys.exit(cmd_generate(prompt, output, seed=seed, steps=steps, retry_on_filter=retry))
