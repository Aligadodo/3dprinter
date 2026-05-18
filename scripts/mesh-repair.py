#!/usr/bin/env python
"""mesh-repair.py - Convert AI-generated 3D mesh to watertight, 3D-print-ready STL/3MF.

Usage: python mesh-repair.py <input_file> [--output stl|3mf|obj] [--scale N] [--verbose]
"""
import argparse, sys, os, json

def repair_mesh(input_path: str, output_format: str = "stl", scale: float = 1.0, verbose: bool = False):
    import trimesh
    import pymeshfix

    if not os.path.exists(input_path):
        return {"error": f"File not found: {input_path}"}

    # Guard against non-mesh inputs (images, text, etc.)
    ext = os.path.splitext(input_path)[1].lower()
    if ext not in (".stl", ".obj", ".glb", ".gltf", ".3mf", ".ply"):
        return {"error": f"Unsupported file type '{ext}' for mesh repair. Expected: .stl/.obj/.glb/.gltf/.3mf/.ply"}

    log = []

    # Load
    mesh = trimesh.load(input_path, force="mesh")
    log.append(f"Loaded: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")
    log.append(f"Initial watertight: {mesh.is_watertight}")

    # If multiple bodies, take the largest
    if isinstance(mesh, trimesh.Scene):
        meshes = [m for m in mesh.geometry.values() if hasattr(m, "vertices")]
        if not meshes:
            return {"error": "No mesh geometry found in scene"}
        mesh = max(meshes, key=lambda m: len(m.vertices))
        log.append(f"Scene detected - using largest body: {len(mesh.vertices)} verts")

    # Clean — apply both masks at once to avoid stale mask references
    keep_mask = mesh.unique_faces() & mesh.nondegenerate_faces()
    mesh.update_faces(keep_mask)
    mesh.remove_unreferenced_vertices()
    if hasattr(mesh, "remove_infinite_values"):
        mesh.remove_infinite_values()
    log.append(f"After clean: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

    # Deep repair via PyMeshFix
    try:
        fix = pymeshfix.MeshFix(mesh.vertices.copy(), mesh.faces.copy())
        fix.repair()
        # pymeshfix returns pyvista PolyData in .mesh
        points = fix.mesh.points
        raw_faces = fix.mesh.faces
        if raw_faces.ndim == 2 and raw_faces.shape[1] == 4:
            faces = raw_faces[:, 1:]  # VTK format: (N, 4) with first col = 3
        else:
            faces = raw_faces.reshape(-1, 3)  # Already (N, 3) or flat
        mesh = trimesh.Trimesh(vertices=points, faces=faces)
        log.append(f"After repair: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")
        log.append(f"Watertight: {mesh.is_watertight}")
    except Exception as e:
        log.append(f"PyMeshFix failed: {e}, falling back to trimesh fill_holes")
        mesh.fill_holes()
        mesh.fix_normals()
        mesh.merge_vertices()

    # Scale
    if scale != 1.0:
        mesh.apply_scale(scale)
        log.append(f"Scaled by {scale}x")

    # Center and place on base
    mesh.vertices -= mesh.centroid
    mesh.vertices[:, 2] -= mesh.vertices[:, 2].min()
    log.append(f"Centered and grounded")

    # Export
    base = os.path.splitext(input_path)[0]
    out_path = f"{base}_print.{output_format}"
    mesh.export(out_path)
    log.append(f"Exported: {out_path}")

    # Stats
    bounds = mesh.bounds
    dims = bounds[1] - bounds[0]
    result = {
        "output": out_path,
        "format": output_format,
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "watertight": bool(mesh.is_watertight),
        "dimensions_mm": [round(d * 1000, 1) for d in dims.tolist()],  # assuming meters input
        "volume_mm3": round(mesh.volume * 1e9, 2) if hasattr(mesh, "volume") and mesh.volume else 0,
        "log": log
    }
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Repair and prepare 3D mesh for printing")
    parser.add_argument("input", help="Input mesh file (.glb/.obj/.stl)")
    parser.add_argument("--output", choices=["stl","3mf","obj"], default="stl", help="Output format")
    parser.add_argument("--scale", type=float, default=1.0, help="Uniform scale factor")
    parser.add_argument("--verbose", action="store_true", help="Verbose repair logging")
    args = parser.parse_args()

    result = repair_mesh(args.input, args.output, args.scale, args.verbose)
    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
