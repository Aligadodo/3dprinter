#!/usr/bin/env python
"""mesh-to-views.py - Render orthographic views from a 3D mesh.

Generates front, back, left, right, top, bottom views as PNG images.
Useful for:
  - Visually verifying AI-generated meshes
  - Providing multi-view input for further refinement
  - Documenting/model-card generation

Usage:
  python mesh-to-views.py model.glb
  python mesh-to-views.py model.stl --resolution 2048 --no-grid
"""

import argparse, sys, os, json
import numpy as np


def _normalize_mesh(mesh):
    """Center and scale mesh to fit unit cube."""
    mesh.vertices -= mesh.centroid
    max_ext = max(mesh.extents)
    if max_ext > 0:
        mesh.vertices *= 0.9 / max_ext
    return mesh


def _view_pose(direction, distance=2.2):
    """Build a 4x4 camera pose matrix that looks at origin from a direction.

    Camera looks along -Z in its local frame. The pose matrix [R|t] places
    the camera at world position t with orientation R. To position the
    camera `distance` units away from origin looking inward:
      camera_position = R * (0, 0, distance) = R[:3, 2] * distance
    because R's column-2 is the camera's +Z axis in world space.
    """
    import trimesh
    rot = np.eye(4)
    if direction == 'back':
        rot = trimesh.transformations.rotation_matrix(np.pi, [0, 1, 0])
    elif direction == 'right':
        rot = trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0])
    elif direction == 'left':
        rot = trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 1, 0])
    elif direction == 'top':
        rot = trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])
    elif direction == 'bottom':
        rot = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
    # front = identity (looking along -Z)

    pose = rot.copy()
    pose[:3, 3] = rot[:3, 2] * distance
    return pose


def render_views(mesh_path, output_dir=None, resolution=1024,
                 grid=True, individual=True):
    """Render 6 orthographic views of a mesh."""
    import trimesh
    try:
        import pyrender
    except ImportError:
        return {"error": "pyrender not installed. Run: pip install pyrender pyglet"}

    log = []

    # Load and normalize
    scene_in = trimesh.load(mesh_path, force='mesh')
    if isinstance(scene_in, trimesh.Scene):
        mesh = scene_in.dump(concatenate=True)
    else:
        mesh = scene_in
    log.append(f"Loaded: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")
    log.append(f"Dimensions: {[round(float(x)*1000,1) for x in mesh.extents]} mm")

    mesh = _normalize_mesh(mesh)

    # Create pyrender mesh (flat shading: compute face normals)
    pr_mesh = pyrender.Mesh.from_trimesh(mesh, smooth=False)

    views = ['front', 'back', 'left', 'right', 'top', 'bottom']
    # Grid layout: 3 columns × 2 rows
    grid_order = ['front', 'right', 'back', 'left', 'top', 'bottom']

    base = os.path.splitext(os.path.basename(mesh_path))[0]
    if output_dir:
        out_dir = output_dir
    else:
        img_dir = os.path.dirname(os.path.abspath(mesh_path))
        out_dir = os.path.join(img_dir, "views")
    os.makedirs(out_dir, exist_ok=True)

    images = {}
    r = pyrender.OffscreenRenderer(resolution, resolution)

    for name in views:
        scene = pyrender.Scene(bg_color=[1.0, 1.0, 1.0, 1.0])
        scene.add(pr_mesh)

        # Key light (directional, from upper-front-right)
        light_pose = _view_pose('top')
        light_pose[:3, 3] = [0.5, 0.8, 1.5]  # light from upper-front-right
        light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=4.0)
        scene.add(light, pose=light_pose)

        # Fill light (weaker, from opposite side)
        fill_pose = np.eye(4)
        fill_pose[:3, 3] = [-0.5, -0.3, -1.0]
        fill = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=1.5)
        scene.add(fill, pose=fill_pose)

        # Orthographic camera
        camera = pyrender.OrthographicCamera(xmag=1.0, ymag=1.0,
                                              znear=0.01, zfar=100.0)
        scene.add(camera, pose=_view_pose(name, distance=2.2))

        color, _ = r.render(scene)
        from PIL import Image
        img = Image.fromarray(color)

        if individual:
            img_path = os.path.join(out_dir, f"{base}_{name}.png")
            img.save(img_path)
        images[name] = img

    r.delete()

    if individual:
        log.append(f"Saved {len(views)} views to {out_dir}/")

    # Grid composition
    if grid:
        from PIL import Image as PILImage
        grid_img = PILImage.new('RGB', (resolution * 3, resolution * 2),
                                (255, 255, 255))
        for i, name in enumerate(grid_order):
            row, col = divmod(i, 3)
            grid_img.paste(images[name],
                          (col * resolution, row * resolution))
        grid_path = os.path.join(out_dir, f"{base}_views_grid.png")
        grid_img.save(grid_path)
        log.append(f"Grid: {grid_path}")

    return {
        "views_dir": out_dir,
        "resolution": resolution,
        "grid": grid_path if grid else None,
        "log": log,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Render 6 orthographic views from a 3D mesh")
    parser.add_argument("mesh", help="Input mesh (.glb/.obj/.stl)")
    parser.add_argument("--resolution", type=int, default=1024,
                        help="Output image resolution per view (default: 1024)")
    parser.add_argument("--output-dir", default="",
                        help="Output directory (default: <mesh_dir>/views/)")
    parser.add_argument("--no-grid", action="store_true",
                        help="Skip combined grid image")
    parser.add_argument("--no-individual", action="store_true",
                        help="Skip individual view images")
    args = parser.parse_args()

    if not os.path.exists(args.mesh):
        print(json.dumps({"error": f"Mesh not found: {args.mesh}"}))
        sys.exit(1)

    result = render_views(
        args.mesh,
        output_dir=args.output_dir or None,
        resolution=args.resolution,
        grid=not args.no_grid,
        individual=not args.no_individual,
    )
    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
