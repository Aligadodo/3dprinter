"""base.py — Abstract base class for image effects."""
from __future__ import annotations

from PIL import Image


class BaseEffect:
    """Abstract base for all image effects.

    Subclasses must set `name`, `label`, `label_zh` and implement `apply()`.
    """

    name: str = ""
    label: str = ""
    label_zh: str = ""

    def apply(self, img: Image.Image, strength: float = 0.8,
              detail: int = 5, color_scheme: str = "warm") -> Image.Image:
        """Apply the effect and return a new image.

        Args:
            img: Input PIL Image (RGB or RGBA).
            strength: Blend ratio 0.0-1.0 (0=original, 1=full effect).
            detail: Effect intensity detail level 1-10.
            color_scheme: Color palette preset (warm/cool/vivid/muted).
        """
        raise NotImplementedError

    @staticmethod
    def blend(original: Image.Image, processed: Image.Image,
              strength: float) -> Image.Image:
        """Blend processed with original by strength ratio."""
        if strength >= 1.0:
            return processed
        if strength <= 0.0:
            return original
        return Image.blend(original, processed, strength)

    @staticmethod
    def to_rgb(img: Image.Image, bg_color=(255, 255, 255)) -> Image.Image:
        """Convert to RGB, flattening alpha onto a solid background."""
        if img.mode == "RGB":
            return img
        if img.mode in ("RGBA", "PA"):
            bg = Image.new("RGB", img.size, bg_color)
            bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            return bg
        return img.convert("RGB")
