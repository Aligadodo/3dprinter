#!/usr/bin/env python
"""mesh-align.py - Align two meshes by their boundary regions.

Uses ICP (Iterative Closest Point) variant to align boundary surfaces.
Outputs the aligned transformation matrix so the second mesh can be
transformed to fit the first.

Usage:
    python mesh-align.py <mesh_a> <mesh_b> --output PATH [--method icp|surface]
                        [--verbose]
    python mesh-align.py --check
"""

import argparse
import json
import os
import sys
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def find_boundary_vertices(mesh, threshold_radians: float = 0.5):
    """Find vertices on the boundary (sharp edges) of a mesh.

    A vertex is on the boundary if the angle between any two adjacent
    face normals is greater than threshold_radians.
    """
    if not hasattr(mesh, 'face_normals'):
        mesh.process()
    fn = mesh.face_normals

    # For each vertex, collect adjacent face normals
    adjacency = {i: [] for i in range(len(mesh.vertices))}
    for f_idx, face in enumerate(mesh.faces):
        for v in face:
            adjacency[v].append(fn[f_idx])

    boundary_verts = []
    for v_idx, normals in adjacency.items():
        if len(normals) < 2:
            continue
        # Compute angle between each pair of adjacent normals
        is_boundary = False
        for i in range(len(normals)):
            for j in range(i + 1, len(normals)):
                n1, n2 = normals[i], normals[j]
                cos_angle = np.clip(np.dot(n1, n2), -1.0, 1.0)
                angle = np.arccos(cos_angle)
                if angle > threshold_radians:
                    is_boundary = True
                    break
            if is_boundary:
                break
        if is_boundary:
            boundary_verts.append(v_idx)

    return np.array(boundary_verts)


def local_frame(vertices):
    """Compute local coordinate frame from a set of vertices.

    Returns (center, basis_x, basis_y, normal) where:
    - center: centroid of vertices
    - basis_x: direction of maximum variance (X axis)
    - basis_y: direction orthogonal to X in the plane
    - normal: cross product of basis_x and basis_y
    """
    center = vertices.mean(axis=0)
    centered = vertices - center
    # PCA to find principal directions
    cov = centered.T @ centered / len(vertices)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # eigenvectors[:,0] is the smallest eigenvalue direction (plane normal)
    normal = eigenvectors[:, 0]
    normal = normal / np.linalg.norm(normal)
    # Largest variance direction
    basis_x = eigenvectors[:, 2]
    basis_x = basis_x / np.linalg.norm(basis_x)
    # Orthogonal to X and normal
    basis_y = np.cross(normal, basis_x)
    basis_y = basis_y / np.linalg.norm(basis_y)

    return center, basis_x, basis_y, normal


def align_meshes(mesh_a_path: str, mesh_b_path: str, output_path: str = None,
                 method: str = "surface", verbose: bool = False):
    import trimesh
    import numpy as np
    from scipy.spatial import KDTree

    log = []

    if not os.path.exists(mesh_a_path):
        return {"error": f"File not found: {mesh_a_path}"}
    if not os.path.exists(mesh_b_path):
        return {"error": f"File not found: {mesh_b_path}"}

    try:
        mesh_a = trimesh.load(mesh_a_path, force="mesh")
        mesh_b = trimesh.load(mesh_b_path, force="mesh")
        if isinstance(mesh_a, trimesh.Scene):
            meshes_a = [m for m in mesh_a.geometry.values() if hasattr(m, "vertices")]
            mesh_a = max(meshes_a, key=lambda m: len(m.vertices)) if meshes_a else None
        if isinstance(mesh_b, trimesh.Scene):
            meshes_b = [m for m in mesh_b.geometry.values() if hasattr(m, "vertices")]
            mesh_b = max(meshes_b, key=lambda m: len(m.vertices)) if meshes_b else None
        if not mesh_a or not mesh_b:
            return {"error": "Failed to load meshes"}
    except Exception as e:
        return {"error": f"Failed to load meshes: {e}"}

    log.append(f"mesh_a: {len(mesh_a.vertices)} verts, {len(mesh_a.faces)} faces")
    log.append(f"mesh_b: {len(mesh_b.vertices)} verts, {len(mesh_b.faces)} faces")

    # Step 1: Find boundary vertices
    boundary_a = find_boundary_vertices(mesh_a)
    boundary_b = find_boundary_vertices(mesh_b)
    log.append(f"Boundary verts: a={len(boundary_a)}, b={len(boundary_b)}")

    if len(boundary_a) < 3 or len(boundary_b) < 3:
        return {"error": "Not enough boundary vertices for alignment"}

    # Step 2: Compute local frames
    verts_a = mesh_a.vertices[boundary_a]
    verts_b = mesh_b.vertices[boundary_b]

    center_a, bx_a, by_a, normal_a = local_frame(verts_a)
    center_b, bx_b, by_b, normal_b = local_frame(verts_b)
    log.append(f"Frame A: center={center_a}, normal={normal_a}")
    log.append(f"Frame B: center={center_b}, normal={normal_b}")

    # Build transformation matrix: R @ (v - center_b) + center_a
    # Align B's X axis to A's X axis in the plane perpendicular to A's normal
    # First, align normals: rotate around cross product
    cross = np.cross(normal_b, normal_a)
    cross_norm = np.linalg.norm(cross)
    if cross_norm > 1e-6:
        angle = np.arccos(np.clip(np.dot(normal_b, normal_a), -1, 1))
        axis = cross / cross_norm
        # Rodrigues rotation formula
        K = np.array([
            [0, -axis[2], axis[1]],
            [axis[2], 0, -axis[0]],
            [-axis[1], axis[0], 0]
        ])
        R_align_normal = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)
    else:
        R_align_normal = np.eye(3)

    # Now align B's basis_x to A's basis_x projected onto the plane
    bx_a_proj = bx_a - np.dot(bx_a, normal_a) * normal_a
    if np.linalg.norm(bx_a_proj) > 1e-6:
        bx_a_proj = bx_a_proj / np.linalg.norm(bx_a_proj)
    else:
        bx_a_proj = bx_a

    by_a_proj = by_a - np.dot(by_a, normal_a) * normal_a
    if np.linalg.norm(by_a_proj) > 1e-6:
        by_a_proj = by_a_proj / np.linalg.norm(by_a_proj)
    else:
        by_a_proj = by_a

    bx_b_rot = R_align_normal @ bx_b
    by_b_rot = R_align_normal @ by_b

    # Complete rotation: align (bx_b_rot, by_b_rot) to (bx_a_proj, by_a_proj)
    # Using Gram-Schmidt on the target plane
    x_axis = bx_a_proj
    y_axis = by_a_proj - np.dot(by_a_proj, x_axis) * x_axis
    y_axis_norm = np.linalg.norm(y_axis)
    if y_axis_norm > 1e-6:
        y_axis = y_axis / y_axis_norm
    else:
        y_axis = by_a_proj
    z_axis = np.cross(x_axis, y_axis)

    R_target = np.column_stack([x_axis, y_axis, z_axis])

    bx_b_final = bx_b_rot
    by_b_final = by_b_rot - np.dot(by_b_rot, normal_a) * normal_a
    by_b_final_norm = np.linalg.norm(by_b_final)
    if by_b_final_norm > 1e-6:
        by_b_final = by_b_final / by_b_final_norm
    else:
        by_b_final = by_b_final

    z_b_final = np.cross(bx_b_final, by_b_final)
    z_b_final_norm = np.linalg.norm(z_b_final)
    if z_b_final_norm < 1e-6:
        z_b_final = normal_a
    else:
        z_b_final = z_b_final / z_b_final_norm

    R_b = np.column_stack([bx_b_final, by_b_final, z_b_final])
    R_final = R_target @ R_b.T

    # Translation: move center_b to center_a
    t_final = center_a - R_final @ center_b

    # Build 4x4 transformation matrix (column-major for trimesh)
    T = np.eye(4)
    T[:3, :3] = R_final
    T[:3, 3] = t_final

    log.append(f"Transform: R=\n{R_final}, t={t_final}")

    # Apply transform to mesh_b
    aligned_mesh = mesh_b.copy()
    aligned_mesh.apply_transform(T)
    log.append(f"Aligned mesh: {len(aligned_mesh.vertices)} verts")

    if output_path is None:
        base = os.path.splitext(os.path.basename(mesh_b_path))[0]
        output_path = os.path.join(os.path.dirname(mesh_b_path) or ".", f"{base}_aligned.stl")

    aligned_mesh.export(output_path)
    log.append(f"Saved to: {output_path}")

    # Compute distance between boundary surfaces as quality metric
    tree_a = KDTree(mesh_a.vertices)
    distances_b, _ = tree_a.query(aligned_mesh.vertices[boundary_b], k=1)
    mean_dist = float(np.mean(distances_b))
    max_dist = float(np.max(distances_b))
    log.append(f"Boundary distance: mean={mean_dist:.4f}, max={max_dist:.4f}")

    # Return transform in flattened form
    return {
        "output": output_path,
        "transform_matrix": T.flatten().tolist(),  # row-major: [r00,r01,r02,r03,r10,...,r33]
        "mean_distance": mean_dist,
        "max_distance": max_dist,
        "vertices": len(aligned_mesh.vertices),
        "faces": len(aligned_mesh.faces),
        "log": log,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Align mesh B to mesh A by boundary surfaces")
    parser.add_argument("mesh_a", nargs="?", help="Target mesh (the opening/feature to align to)")
    parser.add_argument("mesh_b", nargs="?", help="Source mesh (the part to transform)")
    parser.add_argument("--output", "-o", dest="output", default=None,
                        help="Output path for aligned mesh_b")
    parser.add_argument("--method", "-m", default="surface",
                        choices=["surface", "icp"],
                        help="Alignment method (default: surface)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="Check dependencies")

    args = parser.parse_args()

    if args.check:
        try:
            import trimesh, numpy as np, scipy
            print("trimesh, numpy, scipy OK")
            sys.exit(0)
        except Exception as e:
            print(f"Check FAILED: {e}")
            sys.exit(1)

    if not args.mesh_a or not args.mesh_b:
        parser.print_help()
        sys.exit(1)

    result = align_meshes(args.mesh_a, args.mesh_b, args.output, args.method, args.verbose)

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    else:
        print(json.dumps(result, ensure_ascii=False))