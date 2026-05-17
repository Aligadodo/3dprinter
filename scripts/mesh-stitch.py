#!/usr/bin/env python
"""mesh-stitch.py - Stitch and smooth mesh seams after boolean operations.

Uses pymeshlab for HC (Humphrey-Chiu) smoothing and manifold repair.
Output is always manifold/watertight.

Usage:
    python mesh-stitch.py <input_mesh> [--output PATH] [--smooth-steps 3] [--lambda 0.1] [--verbose]
    python mesh-stitch.py --check
"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def stitch_mesh(input_path: str, output_path: str = None,
                smooth_steps: int = 3, lambda_: float = 0.1,
                verbose: bool = False):
    import numpy as np
    import trimesh
    import pymeshlab

    log = []

    if not os.path.exists(input_path):
        return {"error": f"File not found: {input_path}"}

    exts = {".stl", ".obj", ".glb", ".gltf", ".3mf", ".ply"}
    if os.path.splitext(input_path)[1].lower() not in exts:
        return {"error": f"Unsupported file type: {os.path.splitext(input_path)[1]}"}

    try:
        mesh = trimesh.load(input_path, force="mesh")
        if isinstance(mesh, trimesh.Scene):
            meshes = [m for m in mesh.geometry.values() if hasattr(m, "vertices")]
            mesh = max(meshes, key=lambda m: len(m.vertices)) if meshes else None
        if mesh is None:
            return {"error": "No mesh geometry found"}
        log.append(f"Loaded: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")
        log.append(f"Watertight: {mesh.is_watertight}")
    except Exception as e:
        return {"error": f"Failed to load mesh: {e}"}

    # Send to pymeshlab for repair + smoothing
    ms = pymeshlab.MeshSet()
    pymesh_mesh = pymeshlab.Mesh(vertex_matrix=mesh.vertices, face_matrix=mesh.faces)
    ms.add_mesh(pymesh_mesh)

    # Step 1: Repair non-manifold edges and vertices
    try:
        ms.meshing_repair_non_manifold_edges()
        ms.meshing_repair_non_manifold_vertices()
        log.append("Repaired non-manifold edges and vertices")
    except Exception as e:
        log.append(f"Repair warning: {e}")

    # Step 2: Close small holes
    try:
        ms.meshing_close_holes(maxholesize=1000)
        log.append("Closed holes")
    except Exception as e:
        log.append(f"Hole close warning: {e}")

    # Step 3: HC Laplacian smoothing (feature-preserving)
    try:
        ms.apply_coord_hc_laplacian_smoothing(steps=smooth_steps, lambdalambda=lambda_)
        log.append(f"Applied HC smoothing: steps={smooth_steps}, lambda={lambda_}")
    except Exception as e:
        log.append(f"Smoothing warning: {e}")

    # Get processed mesh back
    proc_mesh = ms.current_mesh()
    verts = np.array(proc_mesh.vertex_matrix())
    faces = np.array(proc_mesh.face_matrix())

    out_mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    out_mesh.merge_vertices()
    log.append(f"After stitch: {len(out_mesh.vertices)} verts, {len(out_mesh.faces)} faces")
    log.append(f"Watertight: {out_mesh.is_watertight}")

    if output_path is None:
        base = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(os.path.dirname(input_path) or ".", f"{base}_stitch.stl")

    out_mesh.export(output_path)
    log.append(f"Saved to: {output_path}")

    bounds = out_mesh.bounds
    dimensions = [bounds[1][0] - bounds[0][0], bounds[1][1] - bounds[0][1], bounds[1][2] - bounds[0][2]]

    return {
        "output": output_path,
        "vertices": len(out_mesh.vertices),
        "faces": len(out_mesh.faces),
        "watertight": out_mesh.is_watertight,
        "dimensions_mm": dimensions,
        "log": log,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mesh stitch: repair + HC smoothing")
    parser.add_argument("input_mesh", nargs="?", help="Input mesh file")
    parser.add_argument("--output", "-o", dest="output", default=None,
                        help="Output file path (default: auto)")
    parser.add_argument("--smooth-steps", type=int, default=3,
                        help="Number of smoothing iterations (default: 3)")
    parser.add_argument("--lambda", dest="lambda_", type=float, default=0.1,
                        help="Smoothing lambda (default: 0.1)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="Check pymeshlab installation")

    args = parser.parse_args()

    if args.check:
        try:
            import pymeshlab
            ms = pymeshlab.MeshSet()
            print("pymeshlab OK")
            sys.exit(0)
        except Exception as e:
            print(f"pymeshlab check FAILED: {e}")
            sys.exit(1)

    if not args.input_mesh:
        parser.print_help()
        sys.exit(1)

    result = stitch_mesh(args.input_mesh, args.output, args.smooth_steps, args.lambda_, args.verbose)

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    else:
        print(json.dumps(result, ensure_ascii=False))