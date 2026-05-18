#!/usr/bin/env python
"""image-to-relief.py - Convert a 2D image to a 3D-printable bas-relief.

Generates a height-field mesh from image luminance, with optional multi-color
vertex painting for Bambu 4-color (AMS) printing.

Usage:
  python image-to-relief.py photo.jpg                           # STL only
  python image-to-relief.py photo.jpg --colors 4                # STL + colored OBJ
  python image-to-relief.py photo.jpg --width 160 --height 120  # custom size
"""

import argparse, sys, os, json, time
import numpy as np


def _load_and_preprocess(image_path, target_width_mm, target_height_mm,
                         pixel_spacing_mm=0.1):
    """Load image, resize to match physical dimensions at given pixel spacing.

    Returns:
        gray: 2D float array (H×W) of luminance [0, 1]
        rgb: 3D float array (H×W×3) of colors [0, 255]
        phys_width, phys_height: actual physical dimensions in mm
    """
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    iw, ih = img.size
    aspect = iw / ih

    # Fit within target bounds, maintaining aspect ratio
    if aspect > target_width_mm / target_height_mm:
        phys_w = target_width_mm
        phys_h = target_width_mm / aspect
    else:
        phys_h = target_height_mm
        phys_w = target_height_mm * aspect

    # Pixel resolution from physical size
    pixels_w = int(phys_w / pixel_spacing_mm)
    pixels_h = int(phys_h / pixel_spacing_mm)

    img_resized = img.resize((pixels_w, pixels_h), Image.LANCZOS)
    rgb = np.array(img_resized, dtype=np.float32)

    # Luminance (perceptual weights)
    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    gray = gray / 255.0

    return gray, rgb, phys_w, phys_h, pixels_w, pixels_h


def _height_map(gray, max_depth_mm=3.0, detail_strength=0.25,
                smooth_sigma=1.5, invert=True):
    """Convert luminance image to height displacement map.

    Args:
        gray: float array [0, 1], H×W luminance
        max_depth_mm: maximum relief depth in mm
        detail_strength: how much fine detail to preserve (0=none, 1=full)
        smooth_sigma: gaussian blur sigma for base/detail separation
        invert: if True, dark=low light=high (standard relief)
    """
    from scipy.ndimage import gaussian_filter

    if invert:
        values = gray  # lighter = higher
    else:
        values = 1.0 - gray

    # Separate base shape from fine details
    base = gaussian_filter(values, sigma=smooth_sigma)
    detail = values - base  # fine texture

    # Combine: base shape + amplified detail
    combined = base + detail_strength * detail

    # Normalize to [0, max_depth_mm]
    c_min, c_max = combined.min(), combined.max()
    if c_max > c_min:
        combined = (combined - c_min) / (c_max - c_min) * max_depth_mm
    else:
        combined = np.full_like(combined, max_depth_mm * 0.5)

    return combined


def _build_relief_mesh(height_map, phys_w, phys_h, base_thickness_mm=0.5):
    """Build a watertight triangular mesh from a height field.

    Front face is the height-displaced surface. Back is a flat plate.
    Four side walls connect front perimeter to back.

    Returns:
        vertices: (N, 3) array
        faces: (M, 3) array of vertex indices
    """
    H, W = height_map.shape
    dx = phys_w / (W - 1)
    dy = phys_h / (H - 1)

    # Vertex grid: front face at z = base_thickness + height
    # Back face at z = 0
    x = np.linspace(0, phys_w, W)
    y = np.linspace(phys_h, 0, H)  # flip Y so image top = mesh top

    xv, yv = np.meshgrid(x, y)
    z_front = base_thickness_mm + height_map
    z_back = np.zeros_like(z_front)

    # Total vertices: H*W for front + H*W for back
    n_per_face = H * W
    verts = np.zeros((n_per_face * 2, 3), dtype=np.float32)

    # Front vertices: indices 0 .. n_per_face-1
    verts[:n_per_face, 0] = xv.ravel()
    verts[:n_per_face, 1] = yv.ravel()
    verts[:n_per_face, 2] = z_front.ravel()

    # Back vertices: indices n_per_face .. 2*n_per_face-1
    verts[n_per_face:, 0] = xv.ravel()
    verts[n_per_face:, 1] = yv.ravel()
    verts[n_per_face:, 2] = z_back.ravel()

    # Front face triangles (vectorized)
    rows = np.arange(H - 1)
    cols = np.arange(W - 1)
    a_grid = rows[:, None] * W + cols[None, :]  # (H-1, W-1)
    a = a_grid.ravel()
    b = a + 1
    c = a + W
    d = c + 1
    tri1 = np.column_stack([a, b, d])
    tri2 = np.column_stack([a, d, c])
    front_faces = np.vstack([tri1, tri2])

    # Back face triangles (reverse winding for outward normals)
    offset = n_per_face
    a_off = a + offset
    b_off = b + offset
    c_off = c + offset
    d_off = d + offset
    tri1b = np.column_stack([a_off, d_off, b_off])
    tri2b = np.column_stack([a_off, c_off, d_off])
    back_faces = np.vstack([tri1b, tri2b])

    # Side walls: bottom edge (row=0)
    b_cols = np.arange(W - 1)
    f0_b = 0 * W + b_cols
    f1_b = 0 * W + b_cols + 1
    b0_b = offset + f0_b
    b1_b = offset + f1_b
    sw_bottom = np.vstack([
        np.column_stack([f0_b, b0_b, b1_b]),
        np.column_stack([f0_b, b1_b, f1_b])
    ])

    # Side walls: top edge (row=H-1)
    f0_t = (H - 1) * W + b_cols
    f1_t = (H - 1) * W + b_cols + 1
    b0_t = offset + f0_t
    b1_t = offset + f1_t
    sw_top = np.vstack([
        np.column_stack([f0_t, f1_t, b1_t]),
        np.column_stack([f0_t, b1_t, b0_t])
    ])

    # Side walls: left edge (col=0)
    l_rows = np.arange(H - 1)
    f0_l = l_rows * W + 0
    f1_l = (l_rows + 1) * W + 0
    b0_l = offset + f0_l
    b1_l = offset + f1_l
    sw_left = np.vstack([
        np.column_stack([f0_l, f1_l, b1_l]),
        np.column_stack([f0_l, b1_l, b0_l])
    ])

    # Side walls: right edge (col=W-1)
    f0_r = l_rows * W + (W - 1)
    f1_r = (l_rows + 1) * W + (W - 1)
    b0_r = offset + f0_r
    b1_r = offset + f1_r
    sw_right = np.vstack([
        np.column_stack([f0_r, b0_r, b1_r]),
        np.column_stack([f0_r, b1_r, f1_r])
    ])

    faces = np.vstack([front_faces, back_faces, sw_bottom, sw_top, sw_left, sw_right]).astype(np.int32)
    front_face_count = len(front_faces)
    return verts, faces, front_face_count


def _quantize_colors(rgb, num_colors):
    """Quantize image to N dominant colors using k-means.

    Returns:
        labels: H×W array of cluster indices [0, num_colors)
        palette: (num_colors, 3) array of RGB values
    """
    from sklearn.cluster import KMeans

    H, W, _ = rgb.shape
    pixels = rgb.reshape(-1, 3)

    # Sample for speed (every 4th pixel)
    sample = pixels[::4]
    km = KMeans(n_clusters=num_colors, random_state=42, n_init=3, max_iter=50)
    km.fit(sample)

    # Predict all pixels
    labels = km.predict(pixels).reshape(H, W)
    palette = km.cluster_centers_.astype(np.uint8)
    return labels, palette


def _export_stl(verts, faces, out_path):
    """Export mesh as binary STL."""
    import struct

    # Ensure vertices are float32
    verts = verts.astype(np.float32)
    faces = faces.astype(np.int32)

    with open(out_path, 'wb') as f:
        f.write(b'\x00' * 80)  # header
        f.write(struct.pack('<I', len(faces)))

        for tri in faces:
            v0, v1, v2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
            # Normal (cross product)
            e1 = v1 - v0
            e2 = v2 - v0
            n = np.cross(e1, e2)
            n = n / (np.linalg.norm(n) + 1e-10)
            f.write(struct.pack('<3f', *n))
            f.write(struct.pack('<3f', *v0))
            f.write(struct.pack('<3f', *v1))
            f.write(struct.pack('<3f', *v2))
            f.write(struct.pack('<H', 0))  # attribute


def _export_colored_obj(verts, faces, labels, palette, out_path):
    """Export mesh as OBJ with vertex colors mapped from quantized labels.

    Uses vc (vertex color) extension: each 'v' line is immediately followed
    by a 'vc' line with the RGB color. Face indices reference the vertex number
    (both v and vc share the same index space). Front face gets per-vertex
    colors; back face vertices have no vc line (colorless).
    """
    verts = verts.astype(np.float32)
    H, W = labels.shape

    with open(out_path, 'w') as f:
        f.write("# Bas-relief with vertex colors (vc extension)\n")
        f.write(f"# Palette: {palette.tolist()}\n")
        f.write(f"mtllib relief_colors.mtl\n")
        f.write(f"o Relief\n")

        n_front = H * W
        for i in range(len(verts)):
            v = verts[i]
            f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
            # Front-face vertices (indices 0..n_front-1) get per-vertex color
            if i < n_front:
                row, col = divmod(i, W)
                c_idx = labels[row, col]
                c = palette[c_idx] / 255.0
                f.write(f"vc {c[0]:.4f} {c[1]:.4f} {c[2]:.4f}\n")

        for tri in faces:
            f.write(f"f {tri[0]+1} {tri[1]+1} {tri[2]+1}\n")

    mtl_path = out_path.replace('.obj', '.mtl')
    with open(mtl_path, 'w') as f:
        f.write("newmtl ReliefMaterial\n")
        f.write("Ka 1.0 1.0 1.0\n")
        f.write("Kd 1.0 1.0 1.0\n")
        f.write("d 1.0\n")


def _export_color_preview(labels, palette, out_path):
    """Export a PNG preview showing the color regions."""
    from PIL import Image
    H, W = labels.shape
    img_arr = np.zeros((H, W, 3), dtype=np.uint8)
    for c in range(len(palette)):
        img_arr[labels == c] = palette[c]
    Image.fromarray(img_arr).save(out_path)


def image_to_relief(image_path, width_mm=160.0, height_mm=120.0,
                    max_depth_mm=3.0, base_thickness_mm=0.5,
                    detail_strength=0.25, num_colors=0,
                    pixel_spacing_mm=0.08, lithophane=False):
    """Main pipeline: image → height map → mesh → export.

    Args:
        lithophane: If True, generate a backlit lithophane (thin=light areas,
                    thick=dark areas). Uses inverted height map and flatter profile.
    """
    log = []

    if not os.path.exists(image_path):
        return {"error": f"Image not found: {image_path}"}

    # Stage 1: Load and preprocess
    gray, rgb, phys_w, phys_h, pw, ph = _load_and_preprocess(
        image_path, width_mm, height_mm, pixel_spacing_mm)
    log.append(f"Image resized to {pw}×{ph} px")
    log.append(f"Physical size: {phys_w:.1f}×{phys_h:.1f} mm")
    log.append(f"Luminance range: [{gray.min():.3f}, {gray.max():.3f}]")

    # Stage 2: Height map
    t0 = time.time()
    if lithophane:
        # Lithophane: light areas = thin (more light passes through)
        # invert=False means light=low height
        hm = _height_map(gray, max_depth_mm=max_depth_mm,
                         detail_strength=detail_strength * 0.6,
                         invert=False)
    else:
        hm = _height_map(gray, max_depth_mm=max_depth_mm,
                         detail_strength=detail_strength)
    log.append(f"Height map: {hm.min():.2f}–{hm.max():.2f} mm")
    log.append(f"Height map computed in {time.time()-t0:.1f}s")

    # Stage 3: Build mesh
    t0 = time.time()
    verts, faces, front_face_count = _build_relief_mesh(hm, phys_w, phys_h,
                                      base_thickness_mm=base_thickness_mm)
    total_thickness = base_thickness_mm + max_depth_mm
    log.append(f"Mesh: {len(verts)} verts, {len(faces)} faces")
    log.append(f"Total thickness: {total_thickness:.2f} mm")
    log.append(f"Mesh built in {time.time()-t0:.1f}s")

    # Stage 4: Color export (before decimation — needs original vertex order)
    base = os.path.splitext(os.path.basename(image_path))[0]
    img_dir = os.path.dirname(os.path.abspath(image_path))
    if lithophane:
        out_dir = os.path.join(img_dir, "lithophane")
    else:
        out_dir = os.path.join(img_dir, "relief")
    os.makedirs(out_dir, exist_ok=True)

    result = {}

    # Always generate height map preview (grayscale depth visualization)
    from PIL import Image
    H, W = hm.shape
    hm_vis = ((hm - hm.min()) / (hm.max() - hm.min() + 1e-10) * 255).astype(np.uint8)
    preview_path = os.path.join(out_dir, f"{base}_preview.png")
    Image.fromarray(hm_vis, mode='L').save(preview_path)
    log.append(f"Height preview: {preview_path}")
    result["preview"] = preview_path

    if num_colors > 0:
        log.append(f"Quantizing to {num_colors} colors...")
        labels, palette = _quantize_colors(rgb, num_colors)
        log.append(f"Palette: {palette.tolist()}")

        color_preview_path = os.path.join(out_dir, f"{base}_colors.png")
        _export_color_preview(labels, palette, color_preview_path)
        log.append(f"Color preview: {color_preview_path}")

        # Export colored OBJ from front-face portion only (pre-decimation)
        obj_path = os.path.join(out_dir, f"{base}_relief_colored.obj")
        _export_colored_obj(verts[:H*W], faces[:front_face_count],
                           labels, palette, obj_path)
        log.append(f"Colored OBJ: {obj_path}")

        result["color_preview"] = color_preview_path
        result["colored_obj"] = obj_path
        result["palette"] = palette.tolist()
        result["num_colors"] = num_colors

    # Stage 5: Decimate full mesh to manageable size for STL
    t0 = time.time()
    try:
        import trimesh
        tm = trimesh.Trimesh(verts, faces)
        target_faces = min(300000, len(faces) // 2)
        if len(faces) > target_faces:
            tm = tm.simplify_quadric_decimation(face_count=target_faces)
            verts = np.array(tm.vertices, dtype=np.float32)
            faces = np.array(tm.faces, dtype=np.int32)
            log.append(f"Decimated to {len(verts)} verts, {len(faces)} faces in {time.time()-t0:.1f}s")
    except Exception as e:
        log.append(f"Decimation skipped: {e}")

    # Stage 6: Export STL
    stl_path = os.path.join(out_dir, f"{base}_relief.stl")
    _export_stl(verts, faces, stl_path)
    stl_mb = os.path.getsize(stl_path) / 1024**2
    log.append(f"STL exported: {stl_path} ({stl_mb:.1f} MB)")

    # Only keep STL-related fields; color fields are already in result from Stage 4
    result["stl"] = stl_path
    result["width_mm"] = round(phys_w, 1)
    result["height_mm"] = round(phys_h, 1)
    result["thickness_mm"] = round(total_thickness, 2)
    result["min_thickness_mm"] = round(base_thickness_mm, 2)
    result["max_thickness_mm"] = round(total_thickness, 2)
    result["lithophane"] = lithophane
    result["decimated_vertices"] = len(verts)
    result["decimated_faces"] = len(faces)
    result["log"] = log

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert a 2D image to a 3D-printable bas-relief")
    parser.add_argument("image", help="Input image path")
    parser.add_argument("--width", type=float, default=160.0,
                        help="Target width in mm (default: 160)")
    parser.add_argument("--height", type=float, default=120.0,
                        help="Target height in mm (default: 120)")
    parser.add_argument("--max-depth", type=float, default=3.0,
                        help="Max relief depth in mm (default: 3.0)")
    parser.add_argument("--base-thickness", type=float, default=0.5,
                        help="Minimum base thickness in mm (default: 0.5)")
    parser.add_argument("--detail", type=float, default=0.25,
                        help="Detail preservation strength 0-1 (default: 0.25)")
    parser.add_argument("--colors", type=int, default=0,
                        help="Quantize to N colors for multi-color printing (0=mono)")
    parser.add_argument("--pixel-spacing", type=float, default=0.08,
                        help="Pixel spacing in mm (default: 0.08)")
    parser.add_argument("--lithophane", action="store_true",
                        help="Generate backlit lithophane (thin=light, thick=dark)")
    args = parser.parse_args()

    print(json.dumps({
        "width_mm": args.width,
        "height_mm": args.height,
        "max_depth_mm": args.max_depth,
        "colors": args.colors,
    }, indent=2))

    # Lithophane auto-defaults: thinner for better light transmission
    max_depth = args.max_depth
    base_thick = args.base_thickness
    pixel_sp = args.pixel_spacing
    if args.lithophane:
        if max_depth == 3.0:    # user didn't override default
            max_depth = 2.0     # lithophane: 2mm variation is plenty
        if base_thick == 0.5:   # user didn't override default
            base_thick = 0.6    # lithophane: 0.6mm min for structural + light
        if pixel_sp == 0.08:    # user didn't override default
            pixel_sp = 0.15     # lithophane: fine detail less critical

    result = image_to_relief(
        args.image,
        width_mm=args.width,
        height_mm=args.height,
        max_depth_mm=max_depth,
        base_thickness_mm=base_thick,
        detail_strength=args.detail,
        num_colors=args.colors,
        pixel_spacing_mm=pixel_sp,
        lithophane=args.lithophane,
    )

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
