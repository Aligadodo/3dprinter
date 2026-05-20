#!/usr/bin/env python
"""mesh-cut.py - Cut a mesh with a plane using trimesh slice_plane.

Usage:
    python mesh-cut.py <input_mesh> --plane-co X,Y,Z --plane-no NX,NY,NZ
                        [--fill] [--output-base PATH] [--verbose]
"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def cut_mesh_plane(input_path: str, plane_co: list, plane_no: list,
                   fill: bool = True, output_base: str = None, verbose: bool = False):
    import numpy as np
    import trimesh

    if not os.path.exists(input_path):
        return {"error": f"File not found: {input_path}"}

    log = []
    log.append(f"Input: {input_path}")
    log.append(f"Plane: co={plane_co}, no={plane_no}, fill={fill}")

    # Load mesh
    try:
        mesh = trimesh.load(input_path, force="mesh")
        if isinstance(mesh, trimesh.Scene):
            meshes = [m for m in mesh.geometry.values() if hasattr(m, "vertices")]
            mesh = max(meshes, key=lambda m: len(m.vertices)) if meshes else None
        if mesh is None:
            return {"error": "Failed to extract mesh from file"}
    except Exception as e:
        return {"error": f"Failed to load mesh: {e}"}

    log.append(f"Mesh: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

    # Normalize plane normal
    p = np.array(plane_co, dtype=np.float64)
    n = np.array(plane_no, dtype=np.float64)
    n = n / np.linalg.norm(n)

    # Use trimesh slice_plane (requires shapely)
    # slice_plane(plane_origin, plane_normal, cap=True)
    try:
        outer_mesh = mesh.slice_plane(p, n, cap=True)
        log.append(f"Slice result: {len(outer_mesh.vertices)} verts, {len(outer_mesh.faces)} faces")
    except Exception as e:
        return {"error": f"Slice failed: {e}"}

    if outer_mesh is None or len(outer_mesh.vertices) == 0:
        return {"error": "Slice produced empty mesh"}

    # Apply fill by triangulating the cut boundary (slice_plane fills by default)
    if not outer_mesh.is_watertight:
        try:
            outer_mesh.fill_holes()
        except Exception:
            pass

    if output_base is None:
        base = os.path.splitext(os.path.basename(input_path))[0]
        output_base = os.path.join(os.path.dirname(input_path) or ".", f"{base}_cut")

    out_outer = f"{output_base}_outer.stl"
    outer_mesh.export(out_outer)
    log.append(f"Saved outer to: {out_outer}")

    bounds = outer_mesh.bounds
    dimensions = [bounds[1][0] - bounds[0][0], bounds[1][1] - bounds[0][1], bounds[1][2] - bounds[0][2]]

    return {
        "output_outer": out_outer,
        "vertices": len(outer_mesh.vertices),
        "faces": len(outer_mesh.faces),
        "watertight": outer_mesh.is_watertight,
        "dimensions_mm": dimensions,
        "plane_co": plane_co,
        "plane_no": plane_no,
        "log": log,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mesh cutting via trimesh slice_plane")
    parser.add_argument("input_mesh", nargs="?", help="Input mesh file")
    parser.add_argument("--plane-co", dest="plane_co", default="0,0,0",
                        help="Plane origin as x,y,z (default: 0,0,0)")
    parser.add_argument("--plane-no", dest="plane_no", default="0,0,1",
                        help="Plane normal as nx,ny,nz (default: 0,0,1)")
    parser.add_argument("--fill", action="store_true", default=True,
                        help="Fill the cut face (default: True)")
    parser.add_argument("--no-fill", dest="fill", action="store_false",
                        help="Don't fill the cut face")
    parser.add_argument("--output-base", dest="output_base", default=None,
                        help="Output base path (default: input_base_cut)")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if not args.input_mesh:
        parser.print_help()
        sys.exit(1)

    try:
        plane_co = [float(x) for x in args.plane_co.split(',')]
        plane_no = [float(x) for x in args.plane_no.split(',')]
    except ValueError as e:
        print(json.dumps({"error": f"Invalid plane parameters: {e}"}))
        sys.exit(1)

    result = cut_mesh_plane(
        args.input_mesh, plane_co, plane_no,
        args.fill, args.output_base, args.verbose
    )

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    else:
        print(json.dumps(result, ensure_ascii=False))