#!/usr/bin/env python
"""mesh-decorate.py - Apply 2D image decoration to 3D mesh via UV mapping.

Applies UV displacement (surface embossing/engraving) and vertex colors
from a PNG image. Requires mesh to have UV coordinates (can be generated
via Blender UV unwrap).

Usage:
    python mesh-decorate.py <input_mesh> <texture_image> --output PATH
                          [--displacement 0.5] [--color-mode vertex]
                          [--verbose]
    python mesh-decorate.py --check
"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def decorate_mesh(input_mesh_path: str, texture_path: str,
                  output_path: str = None,
                  displacement: float = 0.5,
                  color_mode: str = "vertex",
                  verbose: bool = False):
    import numpy as np
    import trimesh
    from PIL import Image

    log = []

    if not os.path.exists(input_mesh_path):
        return {"error": f"File not found: {input_mesh_path}"}
    if not os.path.exists(texture_path):
        return {"error": f"Texture file not found: {texture_path}"}

    exts = {".stl", ".obj", ".glb", ".gltf", ".3mf", ".ply"}
    if os.path.splitext(input_mesh_path)[1].lower() not in exts:
        return {"error": f"Unsupported file type: {os.path.splitext(input_mesh_path)[1]}"}

    try:
        mesh = trimesh.load(input_mesh_path, force="mesh")
        if isinstance(mesh, trimesh.Scene):
            meshes = [m for m in mesh.geometry.values() if hasattr(m, "vertices")]
            mesh = max(meshes, key=lambda m: len(m.vertices)) if meshes else None
        if mesh is None:
            return {"error": "No mesh geometry found"}
        log.append(f"Loaded: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")
    except Exception as e:
        return {"error": f"Failed to load mesh: {e}"}

    # Check UV
    if not hasattr(mesh.visual, 'uv') or mesh.visual.uv is None:
        return {"error": "Mesh has no UV coordinates. Run mesh-unwrap first or use an OBJ/glTF with embedded UV."}

    uv = mesh.visual.uv
    if uv.shape[0] != len(mesh.vertices):
        return {"error": f"UV count ({uv.shape[0]}) != vertex count ({len(mesh.vertices)}). Cannot apply decoration."}

    try:
        img = Image.open(texture_path)
        img_array = np.array(img)
        h, w = img_array.shape[:2]
        log.append(f"Loaded texture: {w}x{h} {img.mode}")
    except Exception as e:
        return {"error": f"Failed to load texture: {e}"}

    # ── UV Displacement ──────────────────────────────────────────
    if img.mode != 'L':
        gray = np.array(img.convert('L'))
    else:
        gray = np.array(img)

    u_px = (uv[:, 0] * (w - 1)).astype(int).clip(0, w - 1)
    v_px = (uv[:, 1] * (h - 1)).astype(int).clip(0, h - 1)
    heights = gray[v_px, u_px] / 255.0 * displacement

    normals = mesh.vertex_normals.copy()
    # Normalize to handle degenerate normals
    norms = np.linalg.norm(normals, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normals /= norms

    displaced_verts = mesh.vertices + normals * heights.reshape(-1, 1)
    log.append(f"Applied UV displacement: max={heights.max():.4f}, mean={heights.mean():.4f}")

    # ── Vertex Colors ─────────────────────────────────────────────
    if img.mode == 'RGBA':
        rgba = np.array(img)
        colors = rgba[v_px, u_px, :3] / 255.0
        alpha = rgba[v_px, u_px, 3] / 255.0
        log.append(f"Applied RGBA vertex colors (alpha range: {alpha.min():.2f}-{alpha.max():.2f})")
    else:
        colors = np.array(img.convert('RGB'))[v_px, u_px, :3] / 255.0
        log.append("Applied RGB vertex colors")

    # Build decorated mesh with vertex colors
    decorated = trimesh.Trimesh(
        vertices=displaced_verts,
        faces=mesh.faces,
        vertex_colors=np.clip(colors, 0, 1),
        process=False,
    )
    # Recompute normals after displacement
    decorated.vertex_normals

    if output_path is None:
        base = os.path.splitext(os.path.basename(input_mesh_path))[0]
        output_path = os.path.join(os.path.dirname(input_mesh_path) or ".", f"{base}_decorated.glb")

    # Export with vertex colors
    try:
        decorated.export(output_path)
        log.append(f"Saved to: {output_path}")
    except Exception as e:
        # Fallback: save as OBJ with MTL
        output_obj = output_path.replace('.glb', '.obj').replace('.3mf', '.obj')
        decorated.export(output_obj)
        log.append(f"Saved to: {output_obj} (OBJ format for vertex color)")

    bounds = decorated.bounds
    dimensions = [bounds[1][0] - bounds[0][0], bounds[1][1] - bounds[0][1], bounds[1][2] - bounds[0][2]]

    return {
        "output": output_path,
        "vertices": len(decorated.vertices),
        "faces": len(decorated.faces),
        "has_vertex_colors": True,
        "displacement_max": float(heights.max()),
        "dimensions_mm": dimensions,
        "log": log,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply UV decoration to mesh")
    parser.add_argument("input_mesh", nargs="?", help="Input mesh file")
    parser.add_argument("texture_image", nargs="?", help="PNG decoration image")
    parser.add_argument("--output", "-o", dest="output", default=None)
    parser.add_argument("--displacement", "-d", type=float, default=0.5,
                        help="Max displacement in mesh units (default: 0.5)")
    parser.add_argument("--color-mode", default="vertex",
                        choices=["vertex", "none"],
                        help="Color application mode (default: vertex)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="Check dependencies")

    args = parser.parse_args()

    if args.check:
        try:
            import trimesh, numpy as np, PIL.Image
            print("trimesh, numpy, Pillow OK")
            sys.exit(0)
        except Exception as e:
            print(f"Check FAILED: {e}")
            sys.exit(1)

    if not args.input_mesh or not args.texture_image:
        parser.print_help()
        sys.exit(1)

    result = decorate_mesh(
        args.input_mesh, args.texture_image,
        args.output, args.displacement, args.color_mode, args.verbose
    )

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    else:
        print(json.dumps(result, ensure_ascii=False))