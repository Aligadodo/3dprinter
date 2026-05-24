"""Color-to-height mapping with Floyd-Steinberg error diffusion.

Converts image pixels to Z-height values by matching each pixel to the
nearest virtual swatch color. Floyd-Steinberg dithering smooths transitions
between discrete layer heights, preventing visible stair-step banding.

Reference: Kromacut block-aware Floyd-Steinberg, HueForge Mesh Core.
"""

import json as _json
import numpy as np

from .color_blending import rgb_to_lab_batch


def _emit_progress(stage, pct=None, message=""):
    """Write a structured progress event to stdout for the scheduler."""
    data = {"event": "progress", "stage": stage, "message": message}
    if pct is not None:
        data["percent"] = pct
    print(_json.dumps(data, ensure_ascii=False), flush=True)


def map_colors_to_height(image_rgb, swatches, max_height_mm, layer_height=0.08,
                         dither_strength=0.8, lithophane=False):
    """Map each image pixel to a Z-height by matching to nearest swatch color.

    Uses vectorized CIE76 (Euclidean distance in Lab space) for speed.
    For well-separated filament swatches this produces the same match
    result as CIEDE2000 99%+ of the time.

    Args:
        image_rgb: H×W×3 float array [0, 255].
        swatches: List of {z_mm, rgb, top_filament_index} from
                 generate_virtual_swatches().
        max_height_mm: Maximum Z height (maps to brightest/last swatch).
        layer_height: mm per printed layer.
        dither_strength: Floyd-Steinberg error diffusion amount [0, 1].
        lithophane: If True, invert mapping (light pixels = thin).

    Returns:
        height_map: H×W float array of Z heights in mm.
    """
    H, W = image_rgb.shape[:2]
    n_pixels = H * W
    pixels = image_rgb.reshape(-1, 3) / 255.0  # normalize to [0, 1]

    # Precompute swatch Lab colors and Z heights
    swatch_rgbs = np.array([s["rgb"] for s in swatches], dtype=np.float64)
    swatch_labs = rgb_to_lab_batch(swatch_rgbs)  # (M, 3)
    swatch_heights = np.array([s["z_mm"] for s in swatches], dtype=np.float32)
    n_swatches = len(swatches)

    # Vectorized per-pixel matching in batches (memory-efficient)
    BATCH = 20000
    height_indices = np.zeros(n_pixels, dtype=np.int32)

    _emit_progress("matching", pct=0,
                   message=f"Mapping {n_pixels} pixels to {n_swatches} swatches...")

    for start in range(0, n_pixels, BATCH):
        end = min(start + BATCH, n_pixels)
        batch = pixels[start:end]

        # Convert batch to Lab
        batch_labs = rgb_to_lab_batch(batch)  # (B, 3)

        # CIE76: Euclidean distance in Lab space
        diff = batch_labs[:, None, :] - swatch_labs[None, :, :]  # (B, M, 3)
        dists = np.sqrt((diff ** 2).sum(axis=2))  # (B, M)

        height_indices[start:end] = np.argmin(dists, axis=1)

        # Progress every 25% (suppress at 100% — final message comes from caller)
        pct = int(end / n_pixels * 100)
        if pct % 25 == 0 and pct < 100 and end == n_pixels // (100 // pct):
            _emit_progress("matching", pct=pct,
                           message=f"Color matching {pct}%...")

    height_map = swatch_heights[height_indices].astype(np.float32)

    # Apply Floyd-Steinberg error diffusion on the HEIGHTS
    if dither_strength > 0.001:
        _emit_progress("dithering", pct=0,
                       message=f"Dithering {n_pixels} pixels...")
        height_map = _floyd_steinberg_height(
            height_map, height_indices, swatches,
            H, W, dither_strength)

    # The Beer-Lambert optical model maps bright pixels to low Z
    # (backlight passes through thin layers) — this is the natural
    # lithophane behavior. For relief (front-lit, reflective viewing),
    # we invert so bright areas are raised (prominent).
    if not lithophane:
        height_map = max_height_mm - height_map

    # Clamp to valid range
    height_map = np.clip(height_map, 0, max_height_mm)

    return height_map.reshape(H, W)


def _floyd_steinberg_height(height_map, indices, swatches,
                            H, W, strength):
    """Block-aware Floyd-Steinberg error diffusion on Z-height values.

    Instead of dithering on the color, we dither the height assignment:
    quantization error in Z is distributed to neighboring pixels, causing
    them to shift to adjacent swatch heights. This creates a stippled
    transition pattern instead of sharp stair-steps.

    Block-aware: preserves edges between different top-filament regions.
    """
    height_map = height_map.copy().astype(np.float64)
    indices = indices.copy()

    # Floyd-Steinberg kernel (÷16)
    #        X   7
    #   3   5   1
    kernel = [(0, 1, 7.0 / 16.0),
              (1, -1, 3.0 / 16.0),
              (1, 0, 5.0 / 16.0),
              (1, 1, 1.0 / 16.0)]

    last_pct = -1
    for y in range(H):
        # Progress every 25% of rows
        pct = int(y / H * 100)
        if pct >= last_pct + 25:
            last_pct = pct
            _emit_progress("dithering", pct=pct,
                           message=f"Dithering {pct}%...")

        for x in range(W):
            idx = y * W + x
            current_z = height_map[idx]
            current_idx = indices[idx]

            # Find the two nearest swatch heights
            lower_z, upper_z = _find_neighbor_heights(
                current_z, current_idx, swatches, indices, x, y, W, H)

            if lower_z is None or upper_z is None:
                continue

            # Quantize: pick the closer neighbor
            if abs(current_z - lower_z) < abs(current_z - upper_z):
                quantized = lower_z
            else:
                quantized = current_z  # stay at current swatch

            z_error = (current_z - quantized) * strength

            if abs(z_error) < 1e-10:
                continue

            height_map[idx] = quantized

            # Diffuse error to neighbors
            current_top = swatches[current_idx]["top_filament_index"]
            for dy, dx, weight in kernel:
                ny, nx = y + dy, x + dx
                if 0 <= ny < H and 0 <= nx < W:
                    n_idx = ny * W + nx
                    # Block-aware: don't diffuse across filament boundaries
                    n_top = swatches[indices[n_idx]]["top_filament_index"]
                    if current_top != n_top:
                        continue
                    height_map[n_idx] += z_error * weight

    return height_map.astype(np.float32)


def _find_neighbor_heights(z, swatch_idx, swatches, indices, x, y, W, H):
    """Find the nearest lower and upper swatch heights in the same filament region."""
    current_fil = swatches[swatch_idx]["top_filament_index"]

    # Collect heights from swatches with the same top filament
    same_fil_heights = sorted(set(
        s["z_mm"] for s in swatches
        if s["top_filament_index"] == current_fil
    ))

    if len(same_fil_heights) < 2:
        return same_fil_heights[0] if same_fil_heights else None, None

    lower = None
    upper = None
    for h in same_fil_heights:
        if h <= z:
            lower = h
        if h >= z and upper is None:
            upper = h

    return lower, upper


def floyd_steinberg_dither(height_map, layer_height, strength=0.8):
    """Standalone Floyd-Steinberg dithering on an already-computed height map.

    This is a simplified version that treats height quantization directly.
    """
    H, W = height_map.shape
    hmap = height_map.copy().astype(np.float64)

    kernel = [(0, 1, 7.0 / 16.0),
              (1, -1, 3.0 / 16.0),
              (1, 0, 5.0 / 16.0),
              (1, 1, 1.0 / 16.0)]

    for y in range(H):
        for x in range(W):
            old = hmap[y, x]
            # Quantize to nearest layer_height boundary
            new_val = round(old / layer_height) * layer_height
            error = (old - new_val) * strength
            hmap[y, x] = new_val

            if abs(error) < 1e-10:
                continue

            for dy, dx, weight in kernel:
                ny, nx = y + dy, x + dx
                if 0 <= ny < H and 0 <= nx < W:
                    hmap[ny, nx] += error * weight

    return hmap.astype(np.float32)
