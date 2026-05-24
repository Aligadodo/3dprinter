"""FlatForge mode: separate thin STL per color for face-down printing.

Each color region becomes an independent flat sheet (0.6-1.0mm thick).
All sheets are printed face-down → build plate texture = smooth surface.
User manually assembles the parts like a puzzle.

Algorithm:
  1. K-means color quantization → N dominant colors
  2. Generate binary mask per color cluster
  3. Morphological cleanup (close holes, remove small islands)
  4. Each mask → extruded 2D shape → independent STL
  5. Optional alignment frame + connectors
  6. Assembly guide (PNG with labeled regions)
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import binary_closing, binary_erosion, binary_dilation
from scipy.ndimage import label as nd_label


def quantize_colors(rgb, num_colors):
    """K-means color quantization → per-pixel labels + palette.

    Returns:
        labels: H×W int array of cluster indices [0, num_colors)
        palette: (num_colors, 3) uint8 array of RGB values
    """
    from sklearn.cluster import KMeans

    H, W = rgb.shape[:2]
    pixels = rgb.reshape(-1, 3)
    sample = pixels[::4]  # subsample for speed
    km = KMeans(n_clusters=num_colors, random_state=42, n_init=3, max_iter=50)
    km.fit(sample)
    labels = km.predict(pixels).reshape(H, W)
    palette = np.clip(km.cluster_centers_, 0, 255).astype(np.uint8)
    return labels, palette


def _clean_mask(mask, min_area_px=16, close_radius=2):
    """Morphological cleanup: close small holes, remove tiny islands.

    Args:
        mask: H×W bool array.
        min_area_px: Minimum connected component area in pixels.
        close_radius: Morphological closing radius in pixels.

    Returns:
        Cleaned H×W bool array.
    """
    # Close small holes
    if close_radius > 0:
        selem = np.ones((close_radius * 2 + 1, close_radius * 2 + 1), dtype=bool)
        mask = binary_closing(mask, structure=selem, iterations=1)

    # Remove small islands
    labeled, n_features = nd_label(mask)
    for i in range(1, n_features + 1):
        if np.sum(labeled == i) < min_area_px:
            mask[labeled == i] = False

    return mask


def _mask_to_outline(mask, simplify_tolerance=0.5):
    """Extract polygon outline from binary mask.

    Returns:
        List of (N, 2) float arrays, each a polygon contour in pixel coords.
    """
    from skimage import measure
    contours = measure.find_contours(mask.astype(float), 0.5)
    return contours


def _extrude_mask_to_mesh(mask, phys_w, phys_h, thickness_mm, base_z=0.0):
    """Extrude a binary mask into a watertight 3D mesh (flat sheet).

    The mesh is a simple extrusion: top surface at base_z + thickness,
    bottom surface at base_z, side walls connecting them.

    Args:
        mask: H×W bool array.
        phys_w, phys_h: Physical dimensions in mm.
        thickness_mm: Extrusion thickness in mm.
        base_z: Base Z coordinate in mm.

    Returns:
        verts: (N, 3) float32 array.
        faces: (M, 3) int32 array.
    """
    H, W = mask.shape

    # Find all True pixel coordinates
    rows, cols = np.where(mask)
    if len(rows) == 0:
        return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.int32)

    dx = phys_w / W
    dy = phys_h / H

    # Build per-pixel quads: each pixel → 2 triangles on top, 2 on bottom
    x0 = cols * dx
    y0 = (H - 1 - rows) * dy  # flip Y
    x1 = x0 + dx
    y1 = y0 + dy

    verts_list = []
    faces_list = []
    offset = 0

    # For each True pixel, create a rectangular prism
    for i in range(len(rows)):
        # 8 vertices per prism (4 top, 4 bottom)
        v = np.array([
            [x0[i], y0[i], base_z],                    # 0: bottom-left-bottom
            [x1[i], y0[i], base_z],                    # 1: bottom-right-bottom
            [x1[i], y1[i], base_z],                    # 2: top-right-bottom
            [x0[i], y1[i], base_z],                    # 3: top-left-bottom
            [x0[i], y0[i], base_z + thickness_mm],     # 4: bottom-left-top
            [x1[i], y0[i], base_z + thickness_mm],     # 5: bottom-right-top
            [x1[i], y1[i], base_z + thickness_mm],     # 6: top-right-top
            [x0[i], y1[i], base_z + thickness_mm],     # 7: top-left-top
        ], dtype=np.float32)
        verts_list.append(v)

        # 12 triangles per prism (2 per face × 6 faces)
        o = offset
        f = np.array([
            # Top face (z+)
            [o+4, o+5, o+6], [o+4, o+6, o+7],
            # Bottom face (z-)
            [o+0, o+2, o+1], [o+0, o+3, o+2],
            # Front face (y-)
            [o+0, o+1, o+5], [o+0, o+5, o+4],
            # Back face (y+)
            [o+3, o+6, o+2], [o+3, o+7, o+6],
            # Left face (x-)
            [o+0, o+4, o+7], [o+0, o+7, o+3],
            # Right face (x+)
            [o+1, o+2, o+6], [o+1, o+6, o+5],
        ], dtype=np.int32)
        faces_list.append(f)
        offset += 8

    verts = np.vstack(verts_list)
    faces = np.vstack(faces_list)
    return verts, faces


def _generate_alignment_frame(phys_w, phys_h, thickness_mm=1.2,
                              border_width_mm=3.0, gap_mm=0.15):
    """Generate alignment frame: border with corner markers.

    The frame helps users align color pieces during assembly.
    Prints as a separate STL, same thickness as the pieces.

    Returns:
        verts, faces or (None, None) if too small.
    """
    if phys_w < 10 or phys_h < 10:
        return None, None

    bw = border_width_mm
    gap = gap_mm

    # Outer rectangle (frame outer edge)
    outer_w = phys_w + 2 * (bw + gap)
    outer_h = phys_h + 2 * (bw + gap)
    inner_w = phys_w + 2 * gap
    inner_h = phys_h + 2 * gap

    # Build as 4 rectangular strips (top, bottom, left, right)
    strips = []

    # Top strip
    strips.append((0, inner_h, outer_w, outer_h))
    # Bottom strip
    strips.append((0, 0, outer_w, bw + gap))
    # Left strip
    strips.append((0, 0, bw + gap, outer_h))
    # Right strip
    strips.append((inner_w, 0, outer_w, outer_h))

    verts_list = []
    faces_list = []
    offset = 0

    for x0, y0, x1, y1 in strips:
        v = np.array([
            [x0, y0, 0],                      # 0
            [x1, y0, 0],                      # 1
            [x1, y1, 0],                      # 2
            [x0, y1, 0],                      # 3
            [x0, y0, thickness_mm],           # 4
            [x1, y0, thickness_mm],           # 5
            [x1, y1, thickness_mm],           # 6
            [x0, y1, thickness_mm],           # 7
        ], dtype=np.float32)
        verts_list.append(v)

        o = offset
        f = np.array([
            [o+4, o+5, o+6], [o+4, o+6, o+7],
            [o+0, o+2, o+1], [o+0, o+3, o+2],
            [o+0, o+1, o+5], [o+0, o+5, o+4],
            [o+3, o+6, o+2], [o+3, o+7, o+6],
            [o+0, o+4, o+7], [o+0, o+7, o+3],
            [o+1, o+2, o+6], [o+1, o+6, o+5],
        ], dtype=np.int32)
        faces_list.append(f)
        offset += 8

    verts = np.vstack(verts_list)
    faces = np.vstack(faces_list)
    return verts, faces


def _export_binary_stl(verts, faces, out_path):
    """Export mesh as binary STL."""
    import struct

    verts = verts.astype(np.float32)
    faces = faces.astype(np.int32)

    with open(out_path, 'wb') as f:
        f.write(b'\x00' * 80)
        f.write(struct.pack('<I', len(faces)))
        for tri in faces:
            v0, v1, v2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
            e1 = v1 - v0
            e2 = v2 - v0
            n = np.cross(e1, e2)
            n = n / (np.linalg.norm(n) + 1e-10)
            f.write(struct.pack('<3f', *n))
            f.write(struct.pack('<3f', *v0))
            f.write(struct.pack('<3f', *v1))
            f.write(struct.pack('<3f', *v2))
            f.write(struct.pack('<H', 0))


def _generate_assembly_guide(out_path, masks, palette, phys_w, phys_h,
                             thickness_mm, gap_mm):
    """Generate assembly guide PNG showing labeled color regions.

    Args:
        out_path: Output PNG path.
        masks: List of H×W bool arrays, one per color.
        palette: (num_colors, 3) uint8 RGB array.
        phys_w, phys_h: Physical dimensions in mm.
        thickness_mm: Per-piece thickness.
        gap_mm: Gap tolerance.
    """
    H, W = masks[0].shape
    scale = min(800 / phys_w, 600 / phys_h)
    guide_w = int(phys_w * scale)
    guide_h = int(phys_h * scale)

    # Composite image: each mask color fill
    bg = np.full((H, W, 3), 255, dtype=np.uint8)
    for i, mask in enumerate(masks):
        bg[mask] = palette[i]

    img = Image.fromarray(bg).resize((guide_w, guide_h), Image.NEAREST)
    draw = ImageDraw.Draw(img)

    # Labels
    for i in range(len(masks)):
        mask = masks[i]
        rows, cols = np.where(mask)
        if len(rows) == 0:
            continue
        cy = int(rows.mean() * scale)
        cx = int(cols.mean() * scale)
        color_hex = '#{:02x}{:02x}{:02x}'.format(*palette[i])
        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except (OSError, IOError):
            font = ImageFont.load_default()
        draw.text((cx, cy), f"Part {i+1}\n{color_hex}", fill="black", anchor="mm", font=font)

    # Title and legend
    try:
        title_font = ImageFont.truetype("arial.ttf", 14)
    except (OSError, IOError):
        title_font = ImageFont.load_default()

    # Add padding for title area
    padded = Image.new("RGB", (guide_w + 20, guide_h + 80), (255, 255, 255))
    padded.paste(img, (10, 70))
    draw_pad = ImageDraw.Draw(padded)
    draw_pad.text((10, 5), f"FlatForge Assembly Guide — {phys_w:.0f}×{phys_h:.0f}mm, {thickness_mm:.1f}mm thick", fill="black", font=title_font)
    draw_pad.text((10, 25), f"Gap tolerance: {gap_mm:.2f}mm | Print face-down on textured plate", fill="gray", font=title_font)
    draw_pad.text((10, 45), "Assembly: place each part in the alignment frame, glue if desired", fill="gray", font=title_font)

    padded.save(out_path)


def generate_flatforge(image_path, num_colors=4, thickness_mm=0.8,
                       gap_tolerance_mm=0.1, min_region_area_mm2=4.0,
                       target_width_mm=160.0, target_height_mm=120.0,
                       pixel_spacing_mm=0.1, connectors=True):
    """Generate separate thin sheets per color for face-down printing.

    Args:
        image_path: Path to input image.
        num_colors: Number of colors to quantize to.
        thickness_mm: Thickness of each flat sheet.
        gap_tolerance_mm: Gap between adjacent pieces.
        min_region_area_mm2: Minimum region area to keep (filters noise).
        target_width_mm, target_height_mm: Physical output size.
        pixel_spacing_mm: Physical mm per pixel.
        connectors: Whether to generate alignment frame.

    Returns:
        dict with keys: parts, alignment_frame_stl, assembly_guide, log
    """
    log = []

    # Load image
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
    log.append(f"Image: {pixels_w}×{pixels_h} px, {phys_w:.1f}×{phys_h:.1f} mm")

    # Quantize
    labels, palette = quantize_colors(rgb, num_colors)
    log.append(f"Palette: {palette.tolist()}")

    # Generate masks
    min_area_px = int(min_region_area_mm2 / (pixel_spacing_mm ** 2))
    masks = []
    for c in range(num_colors):
        mask = (labels == c)
        mask = _clean_mask(mask, min_area_px=min_area_px)
        masks.append(mask)
        area_pct = mask.mean() * 100
        log.append(f"  Color {c} ({palette[c].tolist()}): {area_pct:.1f}% area")

    # Generate STL per mask
    import os as _os
    base = _os.path.splitext(_os.path.basename(image_path))[0]
    out_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                            "..", "..", "output", "flatforge", base)
    _os.makedirs(out_dir, exist_ok=True)
    log.append(f"Output: {out_dir}")

    parts = []
    for c in range(num_colors):
        mask = masks[c]
        if not mask.any():
            log.append(f"  Skipping empty color {c}")
            continue

        verts, faces = _extrude_mask_to_mesh(mask, phys_w, phys_h, thickness_mm)
        if len(verts) == 0:
            continue

        stl_path = _os.path.join(out_dir, f"{base}_part{c+1:02d}.stl")
        _export_binary_stl(verts, faces, stl_path)

        color_hex = '#{:02x}{:02x}{:02x}'.format(*palette[c])
        parts.append({
            "color_index": c,
            "color_hex": color_hex,
            "stl_path": stl_path,
            "region_area_pct": round(mask.mean() * 100, 1),
            "faces": len(faces),
        })
        stl_mb = _os.path.getsize(stl_path) / 1024**2
        log.append(f"  Part {c+1}: {stl_path} ({stl_mb:.1f} MB)")

    # Alignment frame
    frame_stl = None
    if connectors:
        frame_verts, frame_faces = _generate_alignment_frame(
            phys_w, phys_h, thickness_mm=thickness_mm, gap_mm=gap_tolerance_mm)
        if frame_verts is not None:
            frame_stl = _os.path.join(out_dir, f"{base}_frame.stl")
            _export_binary_stl(frame_verts, frame_faces, frame_stl)
            log.append(f"  Frame: {frame_stl}")

    # Assembly guide
    guide_path = _os.path.join(out_dir, f"{base}_assembly.png")
    _generate_assembly_guide(guide_path, masks, palette, phys_w, phys_h,
                             thickness_mm, gap_tolerance_mm)
    log.append(f"  Assembly guide: {guide_path}")

    return {
        "parts": parts,
        "alignment_frame_stl": frame_stl,
        "assembly_guide": guide_path,
        "phys_width_mm": round(phys_w, 1),
        "phys_height_mm": round(phys_h, 1),
        "thickness_mm": thickness_mm,
        "gap_tolerance_mm": gap_tolerance_mm,
        "num_colors": num_colors,
        "palette": palette.tolist(),
        "log": log,
    }
