"""Watertight height-field mesh builder for multi-color reliefs.

Builds a triangular mesh from a height map: front face follows the height
profile, back face is a flat plate, and four perimeter walls connect them.
Reuses the proven mesh topology from image-to-relief.py.

Overhang prevention: limit_overhang_slope() constrains the height map
gradient so no adjacent pixels create an overhang exceeding the printer's
safe angle (default 50°). Applied automatically before mesh construction.
"""

import numpy as np


def limit_overhang_slope(height_map, pixel_spacing_mm, max_overhang_deg=50.0,
                         layer_height=0.08):
    """Clamp height map gradient to prevent printing overhangs.

    In FDM printing, a layer must be supported by the layer below it.
    For a height-field mesh, this means: |dz/dx| ≤ pixel_spacing * tan(θ_max)
    where θ_max is the maximum safe overhang angle (~50° for PLA).

    Algorithm: iterative downhill clamping. For each pixel, if the height
    difference to any neighbor exceeds the safe limit, the higher pixel is
    lowered. Iterates until convergence (max 50 passes).

    Args:
        height_map: H×W float array of Z heights in mm.
        pixel_spacing_mm: Physical mm between adjacent pixel centers.
        max_overhang_deg: Maximum safe overhang angle in degrees.
        layer_height: Layer height in mm (quantizes output for slicer alignment).

    Returns:
        Limited height_map with same shape. Preserves the original range
        approximately — only steep transitions are softened.
    """
    import numpy as np

    H, W = height_map.shape
    max_dz = pixel_spacing_mm * np.tan(np.radians(max_overhang_deg))

    # Quantize before clamping so the constraint operates on values the
    # slicer can actually produce. Otherwise final rounding can undo the
    # gradient limit (e.g. two values at 0.12 & 0.20 → round to 0.08 & 0.24,
    # doubling the step beyond max_dz).
    rh = max(layer_height, 1e-4)
    hmap = np.round(height_map.copy() / rh) * rh
    hmap = hmap.astype(np.float64)

    # Iterative downhill clamping: propagate height reductions from steep edges
    for iteration in range(50):
        changed = False

        # Pass 1: left-to-right, top-to-bottom
        for y in range(H):
            for x in range(W):
                cur = hmap[y, x]
                limit_hi = cur + max_dz
                limit_lo = cur - max_dz

                # Check right neighbor
                if x + 1 < W:
                    if hmap[y, x + 1] > limit_hi:
                        hmap[y, x + 1] = limit_hi
                        changed = True
                    elif hmap[y, x + 1] < limit_lo:
                        hmap[y, x] = hmap[y, x + 1] + max_dz
                        changed = True

                # Check bottom neighbor
                if y + 1 < H:
                    if hmap[y + 1, x] > limit_hi:
                        hmap[y + 1, x] = limit_hi
                        changed = True
                    elif hmap[y + 1, x] < limit_lo:
                        hmap[y, x] = hmap[y + 1, x] + max_dz
                        changed = True

        # Pass 2: right-to-left, bottom-to-top (symmetric propagation)
        for y in range(H - 1, -1, -1):
            for x in range(W - 1, -1, -1):
                cur = hmap[y, x]
                limit_hi = cur + max_dz
                limit_lo = cur - max_dz

                if x > 0:
                    if hmap[y, x - 1] > limit_hi:
                        hmap[y, x - 1] = limit_hi
                        changed = True
                    elif hmap[y, x - 1] < limit_lo:
                        hmap[y, x] = hmap[y, x - 1] + max_dz
                        changed = True

                if y > 0:
                    if hmap[y - 1, x] > limit_hi:
                        hmap[y - 1, x] = limit_hi
                        changed = True
                    elif hmap[y - 1, x] < limit_lo:
                        hmap[y, x] = hmap[y - 1, x] + max_dz
                        changed = True

        if not changed:
            break

    hmap = np.clip(hmap, 0, height_map.max())

    # Recover overall brightness by proportional scaling
    orig_range = height_map.max() - height_map.min()
    new_range = hmap.max() - hmap.min()
    if new_range > 0 and orig_range > 0:
        scale = orig_range / new_range
        if scale > 1.0:
            hmap = hmap * min(scale, 1.15)  # allow mild recovery, don't overshoot

    # Re-quantize to layer boundaries after scaling
    hmap = np.round(hmap / rh) * rh

    # Re-run iterative clamping on quantized values. Scaling + rounding can
    # push values across rounding boundaries, creating steps of 2*layer_height
    # where the pre-quantization gap was ≤ max_dz. Two symmetric passes ensure
    # all four neighbor directions converge.
    for _ in range(20):
        changed = False
        for y in range(H):
            for x in range(W):
                cur = hmap[y, x]
                limit_hi = cur + max_dz
                limit_lo = cur - max_dz
                if x + 1 < W:
                    if hmap[y, x + 1] > limit_hi:
                        hmap[y, x + 1] = limit_hi; changed = True
                    elif hmap[y, x + 1] < limit_lo:
                        hmap[y, x] = hmap[y, x + 1] + max_dz; changed = True
                if y + 1 < H:
                    if hmap[y + 1, x] > limit_hi:
                        hmap[y + 1, x] = limit_hi; changed = True
                    elif hmap[y + 1, x] < limit_lo:
                        hmap[y, x] = hmap[y + 1, x] + max_dz; changed = True
        for y in range(H - 1, -1, -1):
            for x in range(W - 1, -1, -1):
                cur = hmap[y, x]
                limit_hi = cur + max_dz
                limit_lo = cur - max_dz
                if x > 0:
                    if hmap[y, x - 1] > limit_hi:
                        hmap[y, x - 1] = limit_hi; changed = True
                    elif hmap[y, x - 1] < limit_lo:
                        hmap[y, x] = hmap[y, x - 1] + max_dz; changed = True
                if y > 0:
                    if hmap[y - 1, x] > limit_hi:
                        hmap[y - 1, x] = limit_hi; changed = True
                    elif hmap[y - 1, x] < limit_lo:
                        hmap[y, x] = hmap[y - 1, x] + max_dz; changed = True

    return hmap.astype(np.float32)


def build_multi_color_mesh(height_map, phys_width_mm, phys_height_mm,
                           base_thickness_mm=0.6,
                           pixel_spacing_mm=None,
                           limit_overhang=True):
    """Build a watertight triangular mesh from a multi-color height field.

    Args:
        height_map: H×W float array of Z heights in mm (above base).
        phys_width_mm: Physical X dimension of the mesh in mm.
        phys_height_mm: Physical Y dimension of the mesh in mm.
        base_thickness_mm: Flat base plate thickness in mm.

    Returns:
        vertices: (N, 3) float32 array.
        faces: (M, 3) int32 array of vertex indices.
    """
    H, W = height_map.shape

    # Overhang prevention: clamp height map gradient to safe overhang angle
    if limit_overhang and pixel_spacing_mm is not None:
        height_map = limit_overhang_slope(height_map, pixel_spacing_mm)

    dx = phys_width_mm / max(W - 1, 1)
    dy = phys_height_mm / max(H - 1, 1)

    n_front = H * W
    n_total = n_front * 2

    # Vertex grid coordinates
    x = np.linspace(0, phys_width_mm, W, dtype=np.float32)
    y = np.linspace(phys_height_mm, 0, H, dtype=np.float32)  # flip Y

    xv, yv = np.meshgrid(x, y)
    z_front = base_thickness_mm + height_map.astype(np.float32)
    z_back = np.zeros_like(z_front, dtype=np.float32)

    verts = np.zeros((n_total, 3), dtype=np.float32)

    # Front face: indices [0, n_front)
    verts[:n_front, 0] = xv.ravel()
    verts[:n_front, 1] = yv.ravel()
    verts[:n_front, 2] = z_front.ravel()

    # Back face: indices [n_front, 2*n_front)
    verts[n_front:, 0] = xv.ravel()
    verts[n_front:, 1] = yv.ravel()
    verts[n_front:, 2] = z_back.ravel()

    # Build faces (vectorized)
    faces_list = []

    # Front face triangles
    rows = np.arange(H - 1, dtype=np.int32)
    cols = np.arange(W - 1, dtype=np.int32)
    a_grid = rows[:, None] * W + cols[None, :]
    a = a_grid.ravel()
    b = a + 1
    c = a + W
    d = c + 1
    tri1 = np.column_stack([a, b, d])
    tri2 = np.column_stack([a, d, c])
    faces_list.append(tri1)
    faces_list.append(tri2)

    # Back face triangles (reversed winding)
    offset = n_front
    a_off = a + offset
    b_off = b + offset
    c_off = c + offset
    d_off = d + offset
    tri1b = np.column_stack([a_off, d_off, b_off])
    tri2b = np.column_stack([a_off, c_off, d_off])
    faces_list.append(tri1b)
    faces_list.append(tri2b)

    # Bottom edge wall (y = phys_height, row = 0)
    b_cols = np.arange(W - 1, dtype=np.int32)
    f0_b = b_cols
    f1_b = b_cols + 1
    b0_b = offset + f0_b
    b1_b = offset + f1_b
    faces_list.append(np.column_stack([f0_b, b0_b, b1_b]))
    faces_list.append(np.column_stack([f0_b, b1_b, f1_b]))

    # Top edge wall (y = 0, row = H-1)
    row_offset = (H - 1) * W
    f0_t = row_offset + b_cols
    f1_t = row_offset + b_cols + 1
    b0_t = offset + f0_t
    b1_t = offset + f1_t
    faces_list.append(np.column_stack([f0_t, f1_t, b1_t]))
    faces_list.append(np.column_stack([f0_t, b1_t, b0_t]))

    # Left edge wall (x = 0)
    l_rows = np.arange(H - 1, dtype=np.int32)
    f0_l = l_rows * W
    f1_l = (l_rows + 1) * W
    b0_l = offset + f0_l
    b1_l = offset + f1_l
    faces_list.append(np.column_stack([f0_l, f1_l, b1_l]))
    faces_list.append(np.column_stack([f0_l, b1_l, b0_l]))

    # Right edge wall (x = phys_width)
    f0_r = l_rows * W + (W - 1)
    f1_r = (l_rows + 1) * W + (W - 1)
    b0_r = offset + f0_r
    b1_r = offset + f1_r
    faces_list.append(np.column_stack([f0_r, b0_r, b1_r]))
    faces_list.append(np.column_stack([f0_r, b1_r, f1_r]))

    faces = np.vstack(faces_list).astype(np.int32)

    return verts, faces
