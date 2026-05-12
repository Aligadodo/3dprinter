"""text-to-image.py - Generate an image from a text prompt via cloud AI API.

Usage:
  python scripts/text-to-image.py "A serene mountain landscape" --provider openai --size 1024x1024
  python scripts/text-to-image.py "一只橘猫在窗台上晒太阳" --provider stability

Output: prints JSON with the image path to stdout.
"""

import argparse
import asyncio
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from web.providers import get_provider, list_providers, OUTPUT_DIR


async def main():
    parser = argparse.ArgumentParser(description="Text-to-Image Generator")
    parser.add_argument("prompt", help="Text prompt for image generation")
    parser.add_argument("--provider", default="volcengine", choices=["volcengine", "zhipu", "openai", "stability"], help="AI provider")
    parser.add_argument("--size", default="", help="Image size (e.g. 1024x1024)")
    parser.add_argument("--list-providers", action="store_true", help="List available providers and exit")
    args = parser.parse_args()

    if args.list_providers:
        providers = list_providers()
        print(json.dumps({"event": "providers", "providers": providers}, ensure_ascii=False))
        return

    provider = get_provider(args.provider)
    if not provider:
        print(json.dumps({"event": "error", "error": f"Provider '{args.provider}' not found or not enabled"}, ensure_ascii=False))
        sys.exit(1)

    print(json.dumps({"event": "progress", "percent": 10, "message": f"Generating image with {args.provider}..."}, ensure_ascii=False))

    try:
        result = await provider.generate(args.prompt, args.size)
    except Exception as e:
        print(json.dumps({"event": "error", "error": str(e)}, ensure_ascii=False))
        sys.exit(1)

    print(json.dumps({"event": "progress", "percent": 100, "message": "Image generated"}, ensure_ascii=False))
    print(json.dumps({
        "output": result.image_path,
        "provider": result.provider,
        "width": result.width,
        "height": result.height,
        "prompt": args.prompt,
        "revised_prompt": result.revised_prompt,
    }, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
