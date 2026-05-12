#!/usr/bin/env python
"""mesh-simplify.py - Decimate a 3D mesh to reduce face count while preserving shape.

Usage: python mesh-simplify.py <input_file> [--target-faces N] [--method quadric|cluster]
"""

import argparse, sys, os, json


def simplify_mesh(input_path: str, target_faces: int = 50000, method: str = "quadric"):
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
    original_faces = len(mesh.faces)

    if target_faces >= original_faces:
        log.append(f"Target faces ({target_faces}) >= current ({original_faces}), skipping simplify")
    elif method == "cluster":
        reduction_ratio = target_faces / original_faces
        mesh = mesh.simplify_quadric_decimation(reduction_ratio)
        log.append(f"Cluster simplify: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")
    else:
        reduction = target_faces / original_faces
        mesh = mesh.simplify_quadric_decimation(reduction)
        log.append(f"Quadric decimate: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

    # Export
    base = os.path.splitext(input_path)[0]
    ext = os.path.splitext(input_path)[1] or ".stl"
    out_path = f"{base}_simplified{ext}"
    mesh.export(out_path)
    log.append(f"Exported: {out_path}")

    return {
        "output": out_path,
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "faces_before": original_faces,
        "faces_after": len(mesh.faces),
        "reduction_ratio": round(len(mesh.faces) / original_faces, 3) if original_faces else 1.0,
        "log": log,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Decimate a 3D mesh")
    parser.add_argument("input", help="Input mesh file")
    parser.add_argument("--target-faces", type=int, default=50000, help="Target face count")
    parser.add_argument("--method", choices=["quadric", "cluster"], default="quadric", help="Simplification algorithm")
    args = parser.parse_args()

    result = simplify_mesh(args.input, args.target_faces, args.method)
    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
