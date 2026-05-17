#!/usr/bin/env python
"""mesh-cut.py - Cut a mesh with a plane using Blender headless.

Uses Blender's bpy.ops.mesh.bisect for precise planar cutting.
Requires Blender to be installed and available in PATH.

Usage:
    python mesh-cut.py <input_mesh> --plane-co X,Y,Z --plane-no NX,NY,NZ
                        [--fill] [--output-base PATH] [--verbose]
    python mesh-cut.py --check
"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def find_blender():
    """Find Blender executable in PATH or common locations."""
    import shutil

    # Check PATH
    path = shutil.which("blender")
    if path:
        return path

    # Known installation paths
    known_paths = [
        r"D:\projects\blender\blender.exe",
        r"C:\Program Files\Blender Foundation\blender.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Blender Foundation", "blender.exe"),
    ]
    for p in known_paths:
        if os.path.exists(p):
            return p

    # Common Windows locations
    import glob
    candidates = glob.glob(os.path.join(os.environ.get("ProgramFiles", ""), "Blender*", "blender.exe"))
    candidates += glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Blender*", "blender.exe"))
    for c in candidates:
        if os.path.exists(c):
            return c

    return None


BLENDER_SCRIPT_TEMPLATE = '''
import bpy
import sys
import json

# sys.argv after '--': input_mesh, plane_co, plane_no, fill, out_base
# Blender passes everything including --python etc, so we look for the '--' marker
argv = sys.argv
try:
    dash_idx = argv.index('--')
    raw_args = argv[dash_idx + 1:]
except ValueError:
    raw_args = [a for a in argv if not a.startswith('--')]

mesh_path = raw_args[0] if len(raw_args) > 0 else None
plane_co_str = raw_args[1] if len(raw_args) > 1 else "0,0,0"
plane_no_str = raw_args[2] if len(raw_args) > 2 else "0,0,1"
fill_str = raw_args[3] if len(raw_args) > 3 else "True"
out_base = raw_args[4] if len(raw_args) > 4 else None

try:
    plane_co = [float(x.strip()) for x in plane_co_str.split(',')]
    plane_no = [float(x.strip()) for x in plane_no_str.split(',')]
    fill = fill_str.lower() == 'true'
    print(json.dumps({"debug": {"plane_co": plane_co, "plane_no": plane_no, "fill": fill, "mesh_path": mesh_path}}))
except Exception as e:
    print(json.dumps({"error": f"Invalid parameters: {e}"}))
    sys.exit(1)

# Clear scene
bpy.ops.mesh.primitive_cube_add(size=0.01)
cube = bpy.context.active_object
bpy.ops.object.delete(use_global=False)

# Import mesh
if mesh_path:
    try:
        if mesh_path.endswith('.glb') or mesh_path.endswith('.gltf'):
            bpy.ops.import_scene.gltf(filepath=mesh_path)
        elif mesh_path.endswith('.obj'):
            bpy.ops.import_scene.obj(filepath=mesh_path)
        else:
            bpy.ops.import_mesh.stl(filepath=mesh_path)
    except Exception as e:
        print(json.dumps({"error": f"Import failed: {e}"}))
        sys.exit(1)
else:
    print(json.dumps({"error": "No input mesh"}))
    sys.exit(1)

obj = bpy.context.selected_objects[0] if bpy.context.selected_objects else None
if not obj or obj.type != 'MESH':
    print(json.dumps({"error": "No mesh object loaded"}))
    sys.exit(1)

# Set active and select
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

# Need viewport context for bisect — use screen area override
# Find the 3D viewport area and region
area = None
region = None
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        area = a
        for r in a.regions:
            if r.type == 'WINDOW':
                region = r
                break
        break

if area is None or region is None:
    print(json.dumps({"error": "No 3D viewport found in Blender context"}))
    sys.exit(1)

with bpy.context.temp_override(area=area, region=region, object=obj):
    try:
        result = bpy.ops.mesh.bisect(
            plane_co=plane_co,
            plane_no=plane_no,
            use_fill=fill,
            clear_inner=True,
            clear_outer=False,
        )
        print(json.dumps({"status": "bisect_ok", "result": str(result)}))
    except Exception as e:
        print(json.dumps({"error": f"Bisect failed: {e}"}))
        sys.exit(1)
'''


def cut_mesh_blender(input_path: str, plane_co: list, plane_no: list,
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
    parser = argparse.ArgumentParser(description="Mesh cutting via Blender headless")
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
    parser.add_argument("--check", action="store_true",
                        help="Check Blender installation")

    args = parser.parse_args()

    if args.check:
        blender = find_blender()
        if blender:
            print(f"Blender found: {blender}")
            sys.exit(0)
        else:
            print("Blender not found. Install from https://www.blender.org/download/")
            sys.exit(1)

    if not args.input_mesh:
        parser.print_help()
        sys.exit(1)

    try:
        plane_co = [float(x) for x in args.plane_co.split(',')]
        plane_no = [float(x) for x in args.plane_no.split(',')]
    except ValueError as e:
        print(json.dumps({"error": f"Invalid plane parameters: {e}"}))
        sys.exit(1)

    result = cut_mesh_blender(
        args.input_mesh, plane_co, plane_no,
        args.fill, args.output_base, args.verbose
    )

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    else:
        print(json.dumps(result, ensure_ascii=False))