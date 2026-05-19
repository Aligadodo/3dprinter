"""distortion.py — Distortion/abstract effects: emboss, kaleidoscope."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

from web.image_effects import register_effect
from web.image_effects.base import BaseEffect


# ═══════════════════════════════════════════════════════════════════
#  Emboss
# ═══════════════════════════════════════════════════════════════════

@register_effect
class EmbossEffect(BaseEffect):
    name = "emboss"
    label = "Emboss"
    label_zh = "浮雕"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        gray = img.convert("L")

        # Apply emboss filter
        embossed = gray.filter(ImageFilter.EMBOSS)

        # Detail controls emboss depth via contrast
        depth = 0.6 + detail * 0.15
        embossed = ImageEnhance.Contrast(embossed).enhance(depth * 2)

        # Convert back to slight warm gray tone
        result = embossed.convert("RGB")
        return self.blend(img, result, strength)


# ═══════════════════════════════════════════════════════════════════
#  Kaleidoscope
# ═══════════════════════════════════════════════════════════════════

@register_effect
class KaleidoscopeEffect(BaseEffect):
    name = "kaleidoscope"
    label = "Kaleidoscope"
    label_zh = "万花筒"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        segments = max(4, 4 + (detail - 1) * 2)  # 4-22 segments
        w, h = img.size
        size = min(w, h)
        left = (w - size) // 2
        top = (h - size) // 2
        crop = img.crop((left, top, left + size, top + size))
        arr = np.array(crop, dtype=np.float64)
        cx, cy = size / 2.0, size / 2.0

        # Build one wedge and mirror it
        angle_per_seg = 2 * np.pi / segments
        half_seg = angle_per_seg / 2

        result = np.zeros_like(arr)
        yy, xx = np.mgrid[0:size, 0:size]
        dx = xx - cx
        dy = yy - cy
        dist = np.sqrt(dx ** 2 + dy ** 2)
        angle = np.arctan2(dy, dx)

        # Map every point into the first wedge
        wedge_angle = angle % angle_per_seg
        wedge_angle = np.where(wedge_angle > half_seg, angle_per_seg - wedge_angle, wedge_angle)

        # Source coordinates: same distance, mapped angle
        src_angle = angle - (angle % angle_per_seg) + np.where(
            angle % angle_per_seg > half_seg,
            angle_per_seg - (angle % angle_per_seg),
            angle % angle_per_seg
        )
        src_angle = angle - (angle % angle_per_seg) + np.minimum(
            angle % angle_per_seg,
            angle_per_seg - (angle % angle_per_seg)
        )
        # Flip across each wedge boundary
        wedge_idx = np.floor(angle / angle_per_seg)
        wedge_pos = angle - wedge_idx * angle_per_seg
        src_wedge_pos = np.where(wedge_pos > half_seg, angle_per_seg - wedge_pos, wedge_pos)
        src_angle_mapped = wedge_idx * angle_per_seg + src_wedge_pos

        src_x = np.clip((cx + dist * np.cos(src_angle_mapped)).astype(int), 0, size - 1)
        src_y = np.clip((cy + dist * np.sin(src_angle_mapped)).astype(int), 0, size - 1)

        result = arr[src_y, src_x]

        kale = Image.fromarray(result.astype(np.uint8))
        kale = kale.resize((w, h), Image.Resampling.LANCZOS)
        return self.blend(img, kale, strength)
