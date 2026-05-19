"""retro.py — Retro/glitch effects: pixelate, sepia, halftone, vintage film."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps

from web.image_effects import register_effect
from web.image_effects.base import BaseEffect


# ═══════════════════════════════════════════════════════════════════
#  Pixelate
# ═══════════════════════════════════════════════════════════════════

@register_effect
class PixelateEffect(BaseEffect):
    name = "pixelate"
    label = "Pixelate"
    label_zh = "像素风"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        pixel_size = max(2, int(2 + (detail / 10) ** 2 * 62))
        w, h = img.size
        small_w, small_h = max(1, w // pixel_size), max(1, h // pixel_size)

        small = img.resize((small_w, small_h), Image.Resampling.NEAREST)
        pixelated = small.resize((w, h), Image.Resampling.NEAREST)
        return self.blend(img, pixelated, strength)


# ═══════════════════════════════════════════════════════════════════
#  Sepia
# ═══════════════════════════════════════════════════════════════════

@register_effect
class SepiaEffect(BaseEffect):
    name = "sepia"
    label = "Sepia"
    label_zh = "怀旧棕褐"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        gray = img.convert("L")
        arr = np.array(gray, dtype=np.float64)

        # Sepia tone matrix
        r = np.clip(arr * 1.10, 0, 255)
        g = np.clip(arr * 0.93, 0, 255)
        b = np.clip(arr * 0.70, 0, 255)

        sepia = np.stack([r, g, b], axis=2).astype(np.uint8)
        result = Image.fromarray(sepia, mode="RGB")

        # Add warm tint if warm color scheme
        if color_scheme == "warm":
            result = ImageEnhance.Color(result).enhance(1.2)

        # Detail controls darkness
        result = ImageEnhance.Brightness(result).enhance(0.85 + detail * 0.02)
        return self.blend(img, result, strength)


# ═══════════════════════════════════════════════════════════════════
#  Halftone
# ═══════════════════════════════════════════════════════════════════

@register_effect
class HalftoneEffect(BaseEffect):
    name = "halftone"
    label = "Halftone"
    label_zh = "网目印刷"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        dot_size = max(2, 2 + detail * 2)
        w, h = img.size

        gray = img.convert("L")
        arr = np.array(gray, dtype=np.float64) / 255.0

        # Scale down by dot_size to create grid
        grid_w, grid_h = w // dot_size, h // dot_size
        result = np.full((h, w, 3), 255.0, dtype=np.float64)

        for gy in range(grid_h):
            for gx in range(grid_w):
                y0, y1 = gy * dot_size, min(h, (gy + 1) * dot_size)
                x0, x1 = gx * dot_size, min(w, (gx + 1) * dot_size)
                patch = arr[y0:y1, x0:x1]
                darkness = 1.0 - np.mean(patch)
                radius = darkness * dot_size * 0.45

                cy, cx = (y0 + y1) / 2, (x0 + x1) / 2
                yy, xx = np.ogrid[y0:y1, x0:x1]
                dist = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
                mask = dist <= radius
                result[y0:y1, x0:x1][mask] = [0, 0, 0]

        halftone_img = Image.fromarray(result.astype(np.uint8), mode="RGB")
        return self.blend(img, halftone_img, strength)


# ═══════════════════════════════════════════════════════════════════
#  Vintage Film
# ═══════════════════════════════════════════════════════════════════

@register_effect
class VintageFilmEffect(BaseEffect):
    name = "vintage_film"
    label = "Vintage Film"
    label_zh = "胶片质感"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        arr = np.array(img, dtype=np.float64)
        h, w = arr.shape[:2]

        # Color cast based on scheme
        color_casts = {
            "warm":  (1.05, 1.00, 0.88),
            "cool":  (0.88, 0.95, 1.05),
            "vivid": (1.10, 0.95, 0.90),
            "muted": (0.95, 0.93, 0.92),
        }
        cast = color_casts.get(color_scheme, color_casts["warm"])
        arr[:, :, 0] *= cast[0]
        arr[:, :, 1] *= cast[1]
        arr[:, :, 2] *= cast[2]

        # Film grain
        np.random.seed(42)
        grain_intensity = 6 + detail * 2
        noise = np.random.normal(0, grain_intensity, arr.shape)
        arr = np.clip(arr + noise, 0, 255)

        # Vignette
        yy, xx = np.ogrid[:h, :w]
        cx, cy = w / 2, h / 2
        max_dist = np.sqrt(cx ** 2 + cy ** 2)
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        vignette = 1.0 - (dist / max_dist) ** 1.5 * 0.35
        arr = arr * vignette[:, :, np.newaxis]

        result = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")
        result = ImageEnhance.Contrast(result).enhance(0.85)
        return self.blend(img, result, strength)
