#!/usr/bin/env python
"""mesh-scale.py - Uniformly scale a 3D mesh to a target size.

Usage: python mesh-scale.py <input_file> [--scale F] [--target-width F] [--uniform]
"""

import argparse, sys, os, json


def scale_mesh(input_path: str, scale_factor: float = 1.0, target_width: float = 0.0, uniform: bool = True):
    import trimesh
    import numpy as np

    if not os.path.exists(input_path):
        return {"error": f"File not found: {input_path}"}

    log = []
    mesh = trimesh.load(input_path, force="mesh")

    if isinstance(mesh, trimesh.Scene):
        meshes = [m for m in mesh.geometry.values() if hasattr(m, "vertices")]
        if not meshes:
            return {"error": "No mesh geometry found in scene"}
        mesh = max(meshes, key=lambda m: len(m.vertices))
        log.append(f"Scene detected - using largest body")

    bounds = mesh.bounds
    dims = bounds[1] - bounds[0]
    log.append(f"Loaded: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")
    log.append(f"Original size (X,Y,Z): {dims[0]:.1f}, {dims[1]:.1f}, {dims[2]:.1f}")

    # Determine scale factor
    if target_width > 0:
        current_width = float(max(dims[0], dims[1]))
        scale_factor = target_width / current_width if current_width > 0 else 1.0
        log.append(f"Target width: {target_width}mm, current max XY: {current_width:.1f}mm, scale: {scale_factor:.3f}")

    if scale_factor != 1.0:
        if uniform:
            mesh.apply_scale(scale_factor)
        else:
            # Non-uniform: scale Z separately?
            mesh.apply_scale(scale_factor)

        new_bounds = mesh.bounds
        new_dims = new_bounds[1] - new_bounds[0]
        log.append(f"Scaled by {scale_factor:.3f}x")
        log.append(f"New size (X,Y,Z): {new_dims[0]:.1f}, {new_dims[1]:.1f}, {new_dims[2]:.1f}")
    else:
        log.append("No scaling applied (factor=1.0)")

    base = os.path.splitext(input_path)[0]
    ext = os.path.splitext(input_path)[1] or ".stl"
    out_path = f"{base}_scaled{ext}"
    mesh.export(out_path)
    log.append(f"Exported: {out_path}")

    return {
        "output": out_path,
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "scale_factor": scale_factor,
        "original_dims": [round(float(d), 1) for d in dims],
        "log": log,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scale a 3D mesh")
    parser.add_argument("input", help="Input mesh file")
    parser.add_argument("--scale", type=float, default=1.0, help="Uniform scale factor (0.01-100)")
    parser.add_argument("--target-width", type=float, default=0.0, help="Target max XY dimension in mm (0=no limit)")
    parser.add_argument("--uniform", type=bool, default=True, help="Uniform scaling")
    args = parser.parse_args()

    result = scale_mesh(args.input, args.scale, args.target_width, args.uniform)
    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
