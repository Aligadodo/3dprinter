"""artistic.py — Painting-style effects: oil, watercolor, sketch, cartoon, ink, impressionist, charcoal."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps

from web.image_effects import register_effect
from web.image_effects.base import BaseEffect


# ═══════════════════════════════════════════════════════════════════
#  Oil Paint
# ═══════════════════════════════════════════════════════════════════

@register_effect
class OilPaintEffect(BaseEffect):
    name = "oil_paint"
    label = "Oil Paint"
    label_zh = "油画"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        radius = max(1, int(1 + (detail / 10) ** 2 * 14))
        arr = np.array(img, dtype=np.float64)

        # Local color averaging: for each pixel, average colors of same-intensity neighbors
        gray = np.mean(arr, axis=2)
        h, w = gray.shape
        result = np.zeros_like(arr)

        # Process at reduced resolution for speed, then resize
        scale = max(1, radius // 2)
        small_h, small_w = h // scale, w // scale
        small = np.array(img.resize((small_w, small_h), Image.Resampling.BILINEAR), dtype=np.float64)

        for y in range(small_h):
            for x in range(small_w):
                y0, y1 = max(0, y - radius // scale), min(small_h, y + radius // scale + 1)
                x0, x1 = max(0, x - radius // scale), min(small_w, x + radius // scale + 1)
                patch = small[y0:y1, x0:x1]
                patch_gray = np.mean(patch, axis=2)
                intensities = (patch_gray // 32).astype(int)
                bins = np.bincount(intensities.ravel(), minlength=8)
                dominant = np.argmax(bins)
                mask = intensities == dominant
                if mask.any():
                    small[y, x] = patch[mask].mean(axis=0)

        result = Image.fromarray(np.clip(small, 0, 255).astype(np.uint8))
        result = result.resize((w, h), Image.Resampling.BILINEAR)

        # Edge enhancement
        result = result.filter(ImageFilter.UnsharpMask(radius=1, percent=60, threshold=3))
        result = ImageEnhance.Color(result).enhance(1.15)
        return self.blend(img, result, strength)


# ═══════════════════════════════════════════════════════════════════
#  Watercolor
# ═══════════════════════════════════════════════════════════════════

@register_effect
class WatercolorEffect(BaseEffect):
    name = "watercolor"
    label = "Watercolor"
    label_zh = "水彩"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        radius = max(1, 1 + detail)
        arr = np.array(img, dtype=np.float64)

        # Soften with bilateral-like approach (median + gaussian)
        softened = img.filter(ImageFilter.MedianFilter(size=min(5, 1 + detail // 2)))
        softened = softened.filter(ImageFilter.GaussianBlur(radius=radius * 0.6))

        # Lighten colors (watercolor transparency)
        lightened = Image.blend(softened, Image.new("RGB", img.size, (255, 255, 255)), 0.3)

        # Edge darkening for brushstroke boundaries
        edges = img.filter(ImageFilter.FIND_EDGES).convert("L")
        edges = edges.filter(ImageFilter.GaussianBlur(radius=radius * 0.4))
        edges_arr = np.array(edges, dtype=np.float64) / 255.0
        darken = 1.0 - edges_arr[:, :, np.newaxis] * 0.15

        result_arr = np.array(lightened, dtype=np.float64) * darken
        result = Image.fromarray(np.clip(result_arr, 0, 255).astype(np.uint8))

        result = ImageEnhance.Color(result).enhance(0.85)
        return self.blend(img, result, strength)


# ═══════════════════════════════════════════════════════════════════
#  Pencil Sketch
# ═══════════════════════════════════════════════════════════════════

@register_effect
class PencilSketchEffect(BaseEffect):
    name = "pencil_sketch"
    label = "Pencil Sketch"
    label_zh = "铅笔素描"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        gray = img.convert("L")

        # Invert and blur
        gray_inv = ImageOps.invert(gray)
        blur_radius = max(1, 2 + detail * 1.2)
        blurred = gray_inv.filter(ImageFilter.GaussianBlur(radius=blur_radius))

        # Dodge blend: result = base / (255 - blend)
        base = np.array(gray, dtype=np.float64)
        blend_arr = np.array(blurred, dtype=np.float64)
        # Dodge: min(255, 255 * base / (255 - blend + 1))
        result_arr = np.minimum(255, 255 * base / (255 - blend_arr + 1))
        result = Image.fromarray(result_arr.astype(np.uint8), mode="L")

        # Enhance contrast for darker lines
        result = ImageEnhance.Contrast(result).enhance(1.0 + detail * 0.08)
        result = result.convert("RGB")
        return self.blend(img, result, strength)


# ═══════════════════════════════════════════════════════════════════
#  Cartoon
# ═══════════════════════════════════════════════════════════════════

@register_effect
class CartoonEffect(BaseEffect):
    name = "cartoon"
    label = "Cartoon"
    label_zh = "卡通"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        quantize_levels = max(4, 20 - detail * 2)

        # Smooth colors via median filter (bilateral approximation)
        smooth = img.filter(ImageFilter.MedianFilter(size=min(7, 1 + (detail // 3) * 2)))
        if smooth.size[0] > 2000:
            smooth = smooth.filter(ImageFilter.SMOOTH_MORE)

        # Quantize to flat color regions
        quantized = smooth.quantize(colors=quantize_levels, method=Image.Quantize.MEDIANCUT)
        quantized = quantized.convert("RGB")

        # Edge detection
        edges = img.filter(ImageFilter.FIND_EDGES).convert("L")
        edges = ImageEnhance.Contrast(edges).enhance(2.5)
        edges = edges.point(lambda p: 0 if p > 60 else 255)
        edges = edges.filter(ImageFilter.GaussianBlur(radius=0.5))

        # Overlay dark edges onto quantized image
        result = quantized.copy()
        result.paste((0, 0, 0), mask=ImageOps.invert(edges))
        return self.blend(img, result, strength)


# ═══════════════════════════════════════════════════════════════════
#  Ink Wash (水墨画)
# ═══════════════════════════════════════════════════════════════════

@register_effect
class InkWashEffect(BaseEffect):
    name = "ink_wash"
    label = "Ink Wash"
    label_zh = "水墨画"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        gray = img.convert("L")
        arr = np.array(gray, dtype=np.float64)

        blur_radius = max(2, 3 + detail * 1.5)
        blurred = gray.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        blurred_arr = np.array(blurred, dtype=np.float64)

        # Multiple threshold layers for ink wash depth
        layers = 4 + detail // 2
        result_arr = np.full_like(arr, 248.0)  # paper white

        for i in range(layers):
            threshold = int(255 - (i + 1) * (200 / layers))
            mask = blurred_arr < threshold
            ink_density = 1.0 - (i / layers) * 0.85
            result_arr[mask] = np.minimum(result_arr[mask], blurred_arr[mask] * ink_density)

        # Edge enhancement for brush stroke definition
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edges_arr = np.array(edges, dtype=np.float64) / 255.0
        result_arr = result_arr * (1.0 - edges_arr * 0.3)

        result = Image.fromarray(np.clip(result_arr, 0, 255).astype(np.uint8), mode="L")
        result = ImageEnhance.Contrast(result).enhance(1.1)
        result = result.convert("RGB")
        return self.blend(img, result, strength)


# ═══════════════════════════════════════════════════════════════════
#  Impressionist (Monet style)
# ═══════════════════════════════════════════════════════════════════

@register_effect
class ImpressionistEffect(BaseEffect):
    name = "impressionist"
    label = "Impressionist"
    label_zh = "印象派"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        brush = max(3, 4 + detail * 2)
        arr = np.array(img, dtype=np.float64)
        h, w = arr.shape[:2]

        result = np.zeros_like(arr)
        count = np.zeros((h, w, 1), dtype=np.float64)

        # Layered brush strokes at different offsets and sizes
        for offset_x in range(0, brush, max(1, brush // 3)):
            for offset_y in range(0, brush, max(1, brush // 3)):
                shifted = np.roll(np.roll(arr, offset_x, axis=1), offset_y, axis=0)
                hf = brush // 2
                y_grid = (np.arange(h)[:, np.newaxis] - offset_y) % brush
                x_grid = (np.arange(w)[np.newaxis, :] - offset_x) % brush
                dist = np.sqrt((y_grid - hf) ** 2 + (x_grid - hf) ** 2)
                weight = np.maximum(0, 1.0 - dist / (hf + 1))
                weight_3d = weight[:, :, np.newaxis]
                result += shifted * weight_3d
                count += weight_3d

        count[count == 0] = 1
        result /= count

        # Slight color boost for impressionist vibrancy
        pil_result = Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))
        pil_result = ImageEnhance.Color(pil_result).enhance(1.2)
        return self.blend(img, pil_result, strength)


# ═══════════════════════════════════════════════════════════════════
#  Charcoal
# ═══════════════════════════════════════════════════════════════════

@register_effect
class CharcoalEffect(BaseEffect):
    name = "charcoal"
    label = "Charcoal"
    label_zh = "炭笔画"

    def apply(self, img, strength=0.8, detail=5, color_scheme="warm"):
        img = self.to_rgb(img)
        gray = img.convert("L")
        gray_inv = ImageOps.invert(gray)
        arr = np.array(gray_inv, dtype=np.float64)

        # High contrast with detail-driven threshold
        threshold = 128 - detail * 6
        contrast_arr = np.clip((arr - threshold) * 2.5, 0, 255)

        # Add texture noise for charcoal grain
        np.random.seed(42)
        noise = np.random.normal(0, 10 + detail * 2, arr.shape)
        textured = np.clip(contrast_arr + noise, 0, 255)

        result = Image.fromarray(textured.astype(np.uint8), mode="L")
        result = ImageEnhance.Contrast(result).enhance(1.3)
        result = result.convert("RGB")
        return self.blend(img, result, strength)
