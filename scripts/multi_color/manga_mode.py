"""Manga/line-art mode for multi-color relief generation.

Converts line-art images (comic scans, ink drawings) to height fields
optimized for filament painting: thin dark layers over the lines, thick
light layers over background areas.

Algorithm:
  1. Adaptive binarization (Otsu threshold)
  2. Edge detection (Sobel gradient magnitude)
  3. Distance transform for line-width estimation
  4. Height mapping: background=max_depth, lines=0, transition via distance
  5. Color assignment: 2-3 filaments (dark→light stacking)
"""

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, sobel, gaussian_filter


def otsu_threshold(gray):
    """Compute Otsu's threshold for grayscale image.

    Returns the threshold value and binary mask (True=foreground/line).
    """
    hist, _ = np.histogram(gray.ravel(), bins=256, range=(0, 256))
    hist = hist.astype(np.float64)
    total = hist.sum()
    if total == 0:
        return 128, gray > 128

    sum_all = np.dot(np.arange(256), hist)
    sum_b = 0.0
    w_b = 0.0
    max_var = 0.0
    best_t = 128

    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var_between = w_b * w_f * (m_b - m_f) ** 2
        if var_between > max_var:
            max_var = var_between
            best_t = t

    return best_t, gray > best_t


def estimate_line_width(binary_mask):
    """Estimate local line width using distance transform.

    Args:
        binary_mask: H×W boolean array, True=line (foreground).

    Returns:
        line_width: H×W float array, estimated line thickness in pixels.
        dist: H×W float array, signed distance to line edges.
    """
    # Distance transform: distance from each pixel to nearest line pixel
    dist_to_line = distance_transform_edt(~binary_mask)  # distance to off-line
    dist_to_bg = distance_transform_edt(binary_mask)     # distance to on-line

    # Signed distance: positive inside lines, negative outside
    signed_dist = dist_to_line.copy()
    signed_dist[binary_mask] = -dist_to_bg[binary_mask]

    # Line width estimate: 2 * distance from line center to edge
    # Approximate by distance transform within line regions
    line_width = np.zeros_like(dist_to_line)
    line_width[binary_mask] = dist_to_bg[binary_mask] * 2  # inside lines
    line_width = gaussian_filter(line_width, sigma=2.0)

    return line_width, signed_dist


def build_manga_height_map(binary_mask, signed_dist, line_width,
                           max_depth_mm=2.0, base_thickness_mm=0.6,
                           edge_transition_px=3.0, invert=False):
    """Build height map optimized for manga line art.

    Lines (foreground) → low height (dark color shows through)
    Background → high height (light color on top)

    The transition zone at line edges is determined by line width:
    thinner lines get narrower transition, thicker lines get wider.

    Args:
        binary_mask: H×W bool (True=line).
        signed_dist: H×W float signed distance field.
        line_width: H×W float estimated line width.
        max_depth_mm: Maximum Z difference.
        base_thickness_mm: Base plate thickness.
        edge_transition_px: Base transition width in pixels.
        invert: If True, background=dark, lines=light (negative effect).

    Returns:
        height_map: H×W float array of Z heights in mm (above base).
    """
    H, W = binary_mask.shape

    # Base height: background = max_depth (thick light covering)
    # Line interiors = 0 (thin, dark shows through)
    if invert:
        base_height = np.where(binary_mask, max_depth_mm, 0.0)
    else:
        base_height = np.where(binary_mask, 0.0, max_depth_mm)

    # Edge transition: use signed distance to create smooth ramp at line edges
    # transition_scale adapts to local line width
    transition_scale = edge_transition_px * np.clip(line_width / 2.0, 0.5, 3.0)
    # Avoid division by zero
    transition_scale = np.maximum(transition_scale, 0.5)

    # Sigmoid transition: smooth step from 0 to max_depth across edges
    ramp = 1.0 / (1.0 + np.exp(-signed_dist / transition_scale))

    if invert:
        height_map = ramp * max_depth_mm
    else:
        height_map = (1.0 - ramp) * max_depth_mm

    return height_map


def process_manga(image_path, dark_filament=None, light_filament=None,
                  mid_filament=None, max_depth_mm=2.0, base_thickness_mm=0.6,
                  line_width_scale=1.0, invert=False, pixel_spacing_mm=0.1,
                  target_width_mm=160.0, target_height_mm=120.0,
                  layer_height=0.08, dither_strength=0.5):
    """Convert line art to multi-color relief with height-field mesh.

    Args:
        image_path: Path to input image (comic scan, ink drawing, etc.).
        dark_filament: Dict {color, name, td} for dark (line) filament.
                       If None, auto-selects Black PLA.
        light_filament: Dict for light (background) filament.
                        If None, auto-selects White PLA.
        mid_filament: Optional middle-gray filament for 3-color mode.
        max_depth_mm: Maximum relief depth (line-to-background delta).
        base_thickness_mm: Minimum plate thickness.
        line_width_scale: 0.5=thinner lines, 2.0=thicker lines.
        invert: If True, white lines on dark background (negative).
        pixel_spacing_mm: Physical mm per pixel.
        target_width_mm, target_height_mm: Physical output size.
        layer_height: mm per printed layer.
        dither_strength: Floyd-Steinberg dithering [0, 1].

    Returns:
        dict with keys: height_map, mesh_verts, mesh_faces, filament_info,
        swaps, total_thickness_mm, log
    """
    log = []

    # ── Load image ──
    img = Image.open(image_path).convert("RGB")
    iw, ih = img.size
    aspect = iw / ih

    if aspect > target_width_mm / target_height_mm:
        phys_w = target_width_mm
        phys_h = target_width_mm / aspect
    else:
        phys_h = target_height_mm
        phys_w = target_height_mm * aspect

    pixels_w = int(phys_w / pixel_spacing_mm)
    pixels_h = int(phys_h / pixel_spacing_mm)

    img_resized = img.resize((pixels_w, pixels_h), Image.LANCZOS)
    rgb = np.array(img_resized, dtype=np.float32)
    log.append(f"Image: {pixels_w}x{pixels_h} px, {phys_w:.1f}x{phys_h:.1f} mm")

    # ── Convert to grayscale ──
    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    log.append(f"Grayscale range: [{gray.min():.0f}, {gray.max():.0f}]")

    # ── Otsu binarization ──
    thresh, binary_mask = otsu_threshold(gray)
    log.append(f"Otsu threshold: {thresh}")

    # Apply line width scale to the binary mask (dilate/erode)
    if line_width_scale > 1.0:
        from scipy.ndimage import binary_dilation
        iters = int((line_width_scale - 1.0) * 5)
        if iters > 0:
            binary_mask = binary_dilation(binary_mask, iterations=iters)
    elif line_width_scale < 1.0:
        from scipy.ndimage import binary_erosion
        iters = int((1.0 / line_width_scale - 1.0) * 5)
        if iters > 0:
            binary_mask = binary_erosion(binary_mask, iterations=min(iters, 10))

    log.append(f"Line width scale: {line_width_scale}x")

    # ── Line width estimation ──
    line_width, signed_dist = estimate_line_width(binary_mask)
    log.append(f"Estimated line width: {line_width[binary_mask].mean():.1f} px")

    # ── Build height map ──
    height_map = build_manga_height_map(
        binary_mask, signed_dist, line_width,
        max_depth_mm=max_depth_mm,
        base_thickness_mm=base_thickness_mm,
        edge_transition_px=3.0 / pixel_spacing_mm,
        invert=invert)
    log.append(f"Height map: [{height_map.min():.2f}, {height_map.max():.2f}] mm")

    # ── Filaments ──
    if dark_filament is None:
        dark_filament = {"color": "#000000", "name": "Black PLA", "td": 0.6}
    if light_filament is None:
        light_filament = {"color": "#FFFFFF", "name": "White PLA", "td": 4.4}

    if mid_filament:
        filaments = [dark_filament, mid_filament, light_filament]
        # 3-color: dark foundation → mid transition → light top
        foundation_t = min(dark_filament["td"] * 1.3, max_depth_mm * 0.3)
        mid_t = max_depth_mm * 0.3
        top_t = max_depth_mm - foundation_t - mid_t
        if top_t < 0:
            top_t = max_depth_mm * 0.4
            mid_t = max(0, max_depth_mm - foundation_t - top_t)
        assignments = [
            {"filament_index": 0, "thickness": foundation_t},
            {"filament_index": 1, "thickness": mid_t},
            {"filament_index": 2, "thickness": top_t},
        ]
    else:
        filaments = [dark_filament, light_filament]
        foundation_t = min(dark_filament["td"] * 1.3, max_depth_mm * 0.4)
        top_t = max_depth_mm - foundation_t
        assignments = [
            {"filament_index": 0, "thickness": foundation_t},
            {"filament_index": 1, "thickness": top_t},
        ]

    # ── Build mesh ──
    from .mesh_builder import build_multi_color_mesh
    verts, faces = build_multi_color_mesh(
        height_map, phys_w, phys_h, base_thickness_mm,
        pixel_spacing_mm=pixel_spacing_mm)
    log.append(f"Mesh: {len(verts)} verts, {len(faces)} faces")

    # ── Build swaps ──
    swaps = _build_manga_swaps(assignments, filaments, layer_height)

    total_thickness = base_thickness_mm + max_depth_mm

    return {
        "height_map": height_map,
        "mesh_verts": verts,
        "mesh_faces": faces,
        "filament_info": filaments,
        "swaps": swaps,
        "total_thickness_mm": total_thickness,
        "base_thickness_mm": base_thickness_mm,
        "phys_width_mm": round(phys_w, 1),
        "phys_height_mm": round(phys_h, 1),
        "log": log,
    }


def _build_manga_swaps(assignments, filaments, layer_height):
    """Build filament swap list from layer assignments."""
    swaps = []
    current_z = 0.0
    for i, a in enumerate(assignments):
        if i == 0 or a["filament_index"] != assignments[i - 1]["filament_index"]:
            fi = a["filament_index"]
            swaps.append({
                "z_mm": round(current_z, 3),
                "layer_number": int(current_z / layer_height) + 1,
                "filament_index": fi,
                "filament_name": filaments[fi]["name"],
                "color": filaments[fi]["color"],
            })
        current_z += a["thickness"]
    return swaps
