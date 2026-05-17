#!/usr/bin/env python
"""mesh-boolean.py - Boolean operations on meshes (union/difference/intersection).

Uses manifold3d for robust CSG operations. Output is always manifold/watertight.

Usage:
    python mesh-boolean.py <input_a> <input_b> --op union|diff|intersect [--output PATH] [--verbose]
    python mesh-boolean.py --check          # verify manifold3d installation
"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def boolean_mesh(input_a: str, input_b: str, operation: str, output_path: str = None, verbose: bool = False):
    """Perform boolean operation on two meshes using manifold3d."""
    import trimesh
    import manifold3d

    log = []

    if not os.path.exists(input_a):
        return {"error": f"File not found: {input_a}"}
    if not os.path.exists(input_b):
        return {"error": f"File not found: {input_b}"}

    exts = {".stl", ".obj", ".glb", ".gltf", ".3mf", ".ply"}
    if os.path.splitext(input_a)[1].lower() not in exts:
        return {"error": f"Unsupported file type for mesh_a: {os.path.splitext(input_a)[1]}"}
    if os.path.splitext(input_b)[1].lower() not in exts:
        return {"error": f"Unsupported file type for mesh_b: {os.path.splitext(input_b)[1]}"}

    try:
        mesh_a = trimesh.load(input_a, force="mesh")
        mesh_b = trimesh.load(input_b, force="mesh")

        if isinstance(mesh_a, trimesh.Scene):
            meshes_a = [m for m in mesh_a.geometry.values() if hasattr(m, "vertices")]
            mesh_a = max(meshes_a, key=lambda m: len(m.vertices)) if meshes_a else None
        if isinstance(mesh_b, trimesh.Scene):
            meshes_b = [m for m in mesh_b.geometry.values() if hasattr(m, "vertices")]
            mesh_b = max(meshes_b, key=lambda m: len(m.vertices)) if meshes_b else None

        if mesh_a is None or mesh_b is None:
            return {"error": "No mesh geometry found in one or both inputs"}

        log.append(f"mesh_a: {len(mesh_a.vertices)} verts, {len(mesh_a.faces)} faces")
        log.append(f"mesh_b: {len(mesh_b.vertices)} verts, {len(mesh_b.faces)} faces")
    except Exception as e:
        return {"error": f"Failed to load meshes: {e}"}

    try:
        import numpy as np
        verts_a = np.array(mesh_a.vertices, dtype=np.float64)
        faces_a = np.array(mesh_a.faces, dtype=np.uint32)
        verts_b = np.array(mesh_b.vertices, dtype=np.float64)
        faces_b = np.array(mesh_b.faces, dtype=np.uint32)

        m3_a = manifold3d.Mesh(vert_properties=verts_a, tri_verts=faces_a)
        m3_b = manifold3d.Mesh(vert_properties=verts_b, tri_verts=faces_b)
    except Exception as e:
        return {"error": f"Failed to convert to manifold3d: {e}"}

    try:
        man_a = manifold3d.Manifold(m3_a)
        man_b = manifold3d.Manifold(m3_b)

        if operation == "union":
            result_man = man_a.batch_boolean([man_b], manifold3d.OpType.Add)
        elif operation == "diff":
            result_man = man_a.batch_boolean([man_b], manifold3d.OpType.Subtract)
        elif operation == "intersect":
            result_man = man_a.batch_boolean([man_b], manifold3d.OpType.Intersect)
        else:
            return {"error": f"Unknown operation '{operation}'. Use: union, diff, intersect"}

        result_mesh = result_man.to_mesh()
    except Exception as e:
        return {"error": f"Boolean {operation} failed: {e}"}

    out_mesh = trimesh.Trimesh(
        vertices=result_mesh.vert_properties,
        faces=result_mesh.tri_verts,
    )

    if len(out_mesh.vertices) == 0 or len(out_mesh.faces) == 0:
        return {"error": f"Boolean {operation} produced empty mesh"}

    out_mesh.merge_vertices()
    log.append(f"Result: {len(out_mesh.vertices)} verts, {len(out_mesh.faces)} faces")
    log.append(f"Watertight: {out_mesh.is_watertight}")

    if output_path is None:
        base = os.path.splitext(os.path.basename(input_a))[0]
        output_path = os.path.join(os.path.dirname(input_a) or ".", f"{base}_bool_{operation}.stl")

    out_mesh.export(output_path)
    log.append(f"Saved to: {output_path}")

    bounds = out_mesh.bounds
    dimensions = [bounds[1][0] - bounds[0][0], bounds[1][1] - bounds[0][1], bounds[1][2] - bounds[0][2]]

    return {
        "operation": operation,
        "output": output_path,
        "vertices": len(out_mesh.vertices),
        "faces": len(out_mesh.faces),
        "watertight": out_mesh.is_watertight,
        "dimensions_mm": dimensions,
        "log": log,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mesh boolean operations via manifold3d")
    parser.add_argument("input_a", nargs="?", help="First input mesh file")
    parser.add_argument("input_b", nargs="?", help="Second input mesh file")
    parser.add_argument("--op", "--operation", dest="operation", default="union",
                        choices=["union", "diff", "intersect"],
                        help="Boolean operation to perform")
    parser.add_argument("--output", "-o", dest="output", default=None,
                        help="Output file path (default: auto)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print verbose log")
    parser.add_argument("--check", action="store_true",
                        help="Check manifold3d installation and exit")

    args = parser.parse_args()

    if args.check:
        try:
            import manifold3d, numpy as np
            verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
            faces = np.array([[0, 1, 2], [0, 2, 1]], dtype=np.uint32)
            m = manifold3d.Mesh(vert_properties=verts, tri_verts=faces)
            print(f"manifold3d OK")
            sys.exit(0)
        except Exception as e:
            print(f"manifold3d check FAILED: {e}")
            sys.exit(1)

    if not args.input_a or not args.input_b:
        parser.print_help()
        sys.exit(1)

    result = boolean_mesh(args.input_a, args.input_b, args.operation, args.output, args.verbose)

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    else:
        print(json.dumps(result, ensure_ascii=False))