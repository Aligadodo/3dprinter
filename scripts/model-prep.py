#!/usr/bin/env python
"""model-prep.py — Convert generated mesh to print-ready STL/3MF/OBJ.

Usage: python model-prep.py <input_file> [--format stl|3mf|obj] [--simplify N] [--no-repair]
              [--target-size N] [--no-ground] [--verbose]
"""
import argparse, sys, os, json


def prep_mesh(input_path, output_format="stl", simplify=0, repair=True,
              fill_holes=True, target_size_mm=0, ground=True, verbose=False):
    import trimesh

    if not os.path.exists(input_path):
        return {"error": f"File not found: {input_path}"}

    # Guard against non-mesh inputs (images, text, etc.)
    ext = os.path.splitext(input_path)[1].lower()
    if ext not in (".stl", ".obj", ".glb", ".gltf", ".3mf", ".ply"):
        return {"error": f"Unsupported file type '{ext}' for model prep. Expected: .stl/.obj/.glb/.gltf/.3mf/.ply"}

    log = []

    # ── Load ──
    mesh = trimesh.load(input_path, force="mesh")
    log.append(f"Loaded: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

    # If scene (multi-body), take largest
    if isinstance(mesh, trimesh.Scene):
        meshes = [m for m in mesh.geometry.values() if hasattr(m, "vertices")]
        if not meshes:
            return {"error": "No mesh geometry found in scene"}
        mesh = max(meshes, key=lambda m: len(m.vertices))
        log.append(f"Scene detected — using largest body: {len(mesh.vertices)} verts")

    # ── Simplify (reduce face count) ──
    if simplify > 0 and len(mesh.faces) > simplify:
        reduction = 1 - (simplify / len(mesh.faces))
        try:
            mesh = mesh.simplify_quadric_decimation(simplify)
            log.append(f"Simplified to {len(mesh.faces)} faces (target {simplify})")
        except Exception as e:
            log.append(f"Simplify failed: {e}, keeping original face count")

    # ── Clean ──
    keep_mask = mesh.unique_faces() & mesh.nondegenerate_faces()
    mesh.update_faces(keep_mask)
    mesh.remove_unreferenced_vertices()
    mesh.remove_infinite_values()
    log.append(f"After clean: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

    # ── Repair ──
    if repair:
        try:
            import pymeshfix
            fix = pymeshfix.MeshFix(mesh.vertices.copy(), mesh.faces.copy())
            fix.repair()
            points = fix.mesh.points
            faces = fix.mesh.faces.reshape(-1, 4)[:, 1:]
            mesh = trimesh.Trimesh(vertices=points, faces=faces)
            log.append(f"After PyMeshFix: {len(mesh.vertices)} verts, {len(mesh.faces)} faces, watertight={mesh.is_watertight}")
        except Exception as e:
            log.append(f"PyMeshFix failed: {e}, falling back to trimesh repair")
            if fill_holes:
                mesh.fill_holes()
            mesh.fix_normals()
            mesh.merge_vertices()
            log.append(f"After trimesh repair: watertight={mesh.is_watertight}")
    elif fill_holes:
        mesh.fill_holes()
        mesh.fix_normals()
        log.append("Holes filled (repair skipped)")

    # ── Scale to target size ──
    if target_size_mm > 0:
        bounds = mesh.bounds
        current_max_mm = float((bounds[1] - bounds[0]).max() * 1000)
        if current_max_mm > 0:
            scale_factor = target_size_mm / current_max_mm
            mesh.apply_scale(scale_factor)
            log.append(f"Scaled to {target_size_mm}mm max dim (was {current_max_mm:.1f}mm, factor {scale_factor:.3f})")

    # ── Ground ──
    if ground:
        mesh.vertices -= mesh.centroid
        mesh.vertices[:, 2] -= mesh.vertices[:, 2].min()
        log.append("Centered and grounded")

    # ── Export ──
    base = os.path.splitext(input_path)[0]
    out_path = f"{base}_prep.{output_format}"
    mesh.export(out_path)
    log.append(f"Exported: {out_path}")

    # ── Stats ──
    bounds = mesh.bounds
    dims_mm = ((bounds[1] - bounds[0]) * 1000).tolist()
    result = {
        "output": out_path,
        "format": output_format,
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "watertight": bool(mesh.is_watertight),
        "dimensions_mm": [round(d, 1) for d in dims_mm],
        "volume_mm3": round(float(mesh.volume) * 1e9, 2) if hasattr(mesh, "volume") and mesh.volume else 0,
        "log": log,
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare 3D mesh for printing")
    parser.add_argument("input", help="Input mesh file (.glb/.obj/.stl/.ply)")
    parser.add_argument("--format", choices=["stl", "3mf", "obj"], default="stl")
    parser.add_argument("--simplify", type=int, default=0, help="Target face count (0=skip)")
    parser.add_argument("--no-repair", action="store_true", help="Skip watertight repair")
    parser.add_argument("--no-fill-holes", action="store_true", help="Skip hole filling")
    parser.add_argument("--target-size", type=float, default=0, help="Target max dimension in mm (0=keep)")
    parser.add_argument("--no-ground", action="store_true", help="Skip centering and grounding")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    result = prep_mesh(
        args.input,
        output_format=args.format,
        simplify=args.simplify,
        repair=not args.no_repair,
        fill_holes=not args.no_fill_holes,
        target_size_mm=args.target_size,
        ground=not args.no_ground,
        verbose=args.verbose,
    )
    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
