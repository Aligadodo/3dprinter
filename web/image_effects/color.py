"""color.py — Color treatment effects: posterize, duotone, macaron, neon."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps

from web.image_effects import register_effect
from web.image_effects.base import BaseEffect


# ═══════════════════════════════════════════════════════════════════
#  Posterize
# ═══════════════════════════════════════════════════════════════════

@register_effect
class PosterizeEffect(BaseEffect):
    name = "posterize"
    label = "Posterize"
    label_zh = "海报化"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        levels = max(2, int(18 - detail * 1.6))
        # Reduce to fewer colors via quantization for smoother poster effect
        result = img.quantize(colors=levels * 4, method=Image.Quantize.MEDIANCUT)
        result = result.convert("RGB")
        # Posterize each channel for poster look
        bits = max(1, int(np.log2(levels)) + 1)
        result = ImageOps.posterize(result, bits)
        return self.blend(img, result, strength)


# ═══════════════════════════════════════════════════════════════════
#  Duotone
# ═══════════════════════════════════════════════════════════════════

@register_effect
class DuotoneEffect(BaseEffect):
    name = "duotone"
    label = "Duotone"
    label_zh = "双色调"

    # Color scheme presets: (dark_tone, light_tone) as (R, G, B)
    PRESETS = {
        "warm":  ((60, 30, 10),  (255, 240, 220)),
        "cool":  ((10, 30, 80),  (220, 235, 255)),
        "vivid": ((80, 10, 140), (255, 220, 60)),
        "muted": ((70, 65, 60),  (235, 225, 215)),
    }

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        gray = img.convert("L")
        arr = np.array(gray, dtype=np.float64) / 255.0

        dark, light = self.PRESETS.get(color_scheme, self.PRESETS["warm"])

        result = np.zeros((*arr.shape, 3), dtype=np.float64)
        for ch in range(3):
            result[:, :, ch] = dark[ch] + (light[ch] - dark[ch]) * arr

        # Detail controls contrast of mapping
        if detail != 5:
            mid = 0.5
            shift = (detail - 5) * 0.03
            arr_adj = np.clip(arr + shift * (1 - abs(arr - mid) * 2), 0, 1)
            for ch in range(3):
                result[:, :, ch] = dark[ch] + (light[ch] - dark[ch]) * arr_adj

        result = Image.fromarray(np.clip(result, 0, 255).astype(np.uint8), mode="RGB")
        return self.blend(img, result, strength)


# ═══════════════════════════════════════════════════════════════════
#  Macaron (Pastel soft colors)
# ═══════════════════════════════════════════════════════════════════

@register_effect
class MacaronEffect(BaseEffect):
    name = "macaron"
    label = "Macaron"
    label_zh = "马卡龙"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        arr = np.array(img, dtype=np.float64)

        # Reduce contrast
        mean = arr.mean(axis=(0, 1), keepdims=True)
        contrast_factor = 0.55 + detail * 0.02
        arr = mean + (arr - mean) * contrast_factor

        # Shift toward pastel: blend with white, preserve hue
        pastel_factor = 0.25 + detail * 0.03
        arr = arr * (1 - pastel_factor) + 255 * pastel_factor

        # Soften slightly
        result = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        result = result.filter(ImageFilter.GaussianBlur(radius=0.7))

        # Slightly boost brightness
        result = ImageEnhance.Brightness(result).enhance(1.05)

        # Color scheme influences tint
        tints = {
            "warm":  (1.03, 1.00, 0.97),
            "cool":  (0.97, 1.00, 1.03),
            "vivid": (1.02, 1.00, 1.02),
            "muted": (0.98, 0.98, 0.98),
        }
        tint = tints.get(color_scheme, tints["warm"])
        tinted = np.array(result, dtype=np.float64)
        for ch in range(3):
            tinted[:, :, ch] = np.clip(tinted[:, :, ch] * tint[ch], 0, 255)
        result = Image.fromarray(tinted.astype(np.uint8))

        return self.blend(img, result, strength)


# ═══════════════════════════════════════════════════════════════════
#  Neon
# ═══════════════════════════════════════════════════════════════════

@register_effect
class NeonEffect(BaseEffect):
    name = "neon"
    label = "Neon"
    label_zh = "霓虹"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        arr = np.array(img, dtype=np.float64)

        # Boost saturation heavily
        saturated = ImageEnhance.Color(img).enhance(2.0 + detail * 0.2)

        # Detect edges for glow
        gray = img.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edges_blurred = edges.filter(ImageFilter.GaussianBlur(radius=2 + detail * 0.5))
        glow_mask = np.array(edges_blurred, dtype=np.float64) / 255.0

        # Enhance glow with color scheme tint
        glow_colors = {
            "warm":  (1.0, 0.5, 0.3),
            "cool":  (0.3, 0.6, 1.0),
            "vivid": (1.0, 0.2, 0.8),
            "muted": (0.5, 0.7, 0.5),
        }
        glow = glow_colors.get(color_scheme, glow_colors["warm"])

        # Darken non-edge areas, add glow to edges
        sat_arr = np.array(saturated, dtype=np.float64)
        dark_factor = 0.5 - detail * 0.03
        result_arr = sat_arr * (dark_factor + glow_mask[:, :, np.newaxis] * (1.0 - dark_factor))
        for ch in range(3):
            result_arr[:, :, ch] += glow_mask * glow[ch] * 60

        result = Image.fromarray(np.clip(result_arr, 0, 255).astype(np.uint8))
        result = ImageEnhance.Contrast(result).enhance(1.2)
        return self.blend(img, result, strength)
