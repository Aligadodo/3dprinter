"""naming.py — Semantic output filename generation for image effects.

Reads config/image_effect_naming.yaml to produce human-readable output paths.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

_CONFIG: dict | None = None


def _load_config() -> dict:
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG
    config_path = Path(__file__).parent.parent.parent / "config" / "image_effect_naming.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            _CONFIG = yaml.safe_load(f) or {}
    else:
        _CONFIG = {}
    return _CONFIG


def _deduplicate(work_dir: str, basename: str, ext: str = ".png") -> str:
    """Append _1, _2, etc. if the file already exists."""
    candidate = os.path.join(work_dir, f"{basename}{ext}")
    if not os.path.exists(candidate):
        return candidate
    i = 1
    while True:
        candidate = os.path.join(work_dir, f"{basename}_{i}{ext}")
        if not os.path.exists(candidate):
            return candidate
        i += 1


def effect_output_path(input_path: str, work_dir: str, effect_name: str,
                       strength: float = 0.8, detail: int = 5,
                       color_scheme: str = "warm", ext: str = ".png") -> str:
    """Generate a semantic output file path for an effect result.

    Example:
        >>> effect_output_path("/tmp/photo.png", "/out", "pixelate", detail=8)
        "/out/photo_pixel_p8.png"
    """
    cfg = _load_config()
    suffixes = cfg.get("suffixes", {})
    suffix = suffixes.get(effect_name, effect_name)
    base = Path(input_path).stem

    overrides = cfg.get("overrides", {})
    pattern = overrides.get(effect_name, cfg.get("default_pattern", "{base}_{effect}"))

    name = pattern.format(
        base=base,
        effect=suffix,
        strength=f"{strength:.0f}".replace(".", ""),
        detail=str(detail),
        style=effect_name,
        color=color_scheme,
    )

    clean = name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    return _deduplicate(work_dir, clean, ext)
