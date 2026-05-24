"""Watertight height-field mesh builder for multi-color reliefs.

Builds a triangular mesh from a height map: front face follows the height
profile, back face is a flat plate, and four perimeter walls connect them.
Reuses the proven mesh topology from image-to-relief.py.
"""

import numpy as np


def build_multi_color_mesh(height_map, phys_width_mm, phys_height_mm,
                           base_thickness_mm=0.6):
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
