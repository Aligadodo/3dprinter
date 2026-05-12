#!/usr/bin/env python
"""mesh-smooth.py - Apply Taubin or Laplacian smoothing to a 3D mesh.

Usage: python mesh-smooth.py <input_file> [--iterations N] [--lambda F] [--mu F]
"""

import argparse, sys, os, json


def smooth_mesh(input_path: str, iterations: int = 3, lamb: float = 0.5, mu: float = -0.53):
    import trimesh

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

    log.append(f"Loaded: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

    # Taubin smoothing (lambda > 0, mu < 0 prevents shrinkage)
    try:
        import trimesh.smoothing
        mesh = trimesh.smoothing.filter_taubin(mesh, iterations=iterations, lamb=lamb, nu=mu)
    except (AttributeError, ImportError):
        # Fallback: use vertices Laplacian directly
        import numpy as np
        for _ in range(iterations):
            lap = trimesh.smoothing.laplacian_calculation(mesh)
            mesh.vertices = mesh.vertices + lamb * lap

    log.append(f"Smoothed: {iterations} iterations (λ={lamb}, μ={mu})")
    log.append(f"Result: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

    base = os.path.splitext(input_path)[0]
    ext = os.path.splitext(input_path)[1] or ".stl"
    out_path = f"{base}_smoothed{ext}"
    mesh.export(out_path)
    log.append(f"Exported: {out_path}")

    return {
        "output": out_path,
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "iterations": iterations,
        "lambda": lamb,
        "mu": mu,
        "log": log,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smooth a 3D mesh")
    parser.add_argument("input", help="Input mesh file")
    parser.add_argument("--iterations", type=int, default=3, help="Smoothing iterations (1-20)")
    parser.add_argument("--lambda", dest="lambda_", type=float, default=0.5, help="Taubin lambda (0.0-1.0)")
    parser.add_argument("--mu", type=float, default=-0.53, help="Taubin mu (-1.0-0.0)")
    args = parser.parse_args()

    result = smooth_mesh(args.input, args.iterations, args.lambda_, args.mu)
    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
