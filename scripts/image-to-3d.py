#!/usr/bin/env python
"""image-to-3d.py - Single image → 3D mesh using TripoSR.

Usage: python image-to-3d.py <image_path> [--format glb|obj] [--no-bg-remove] [--resolution N]
Output: 3D mesh file + JSON metadata
"""
import argparse, sys, os, json, time


def generate_3d(image_path: str, output_format: str = "glb",
                remove_bg: bool = True, foreground_ratio: float = 0.85,
                mc_resolution: int = 256):
    """Generate a 3D mesh from a single image using TripoSR."""

    if not os.path.exists(image_path):
        return {"error": f"Image not found: {image_path}"}

    try:
        import torch
        import numpy as np
        from PIL import Image
    except ImportError as e:
        return {"error": f"Missing dependency: {e}"}

    if not torch.cuda.is_available():
        return {"error": "CUDA not available. TripoSR requires an NVIDIA GPU."}

    device = "cuda"
    log = []
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    log.append(f"GPU: {torch.cuda.get_device_name(0)} ({vram_gb:.1f} GB)")

    # Add triposr source to path (project-root/triposr/src/)
    project_root = os.environ.get("PROJECT_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(project_root, "triposr", "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    # Model path (project-root/models/)
    model_dir = os.path.join(project_root, "models")
    if not os.path.exists(os.path.join(model_dir, "model.ckpt")):
        return {"error": f"TripoSR model not found at {model_dir}. Please download it first."}

    log.append("Loading TripoSR model...")

    try:
        from tsr.system import TSR
        from tsr.utils import remove_background, resize_foreground
        import rembg
    except ImportError as e:
        return {"error": f"TripoSR not properly installed: {e}"}

    # Load model
    t0 = time.time()
    model = TSR.from_pretrained(
        model_dir,
        config_name="config.yaml",
        weight_name="model.ckpt",
    )
    model.renderer.set_chunk_size(8192)
    model.to(device)
    model.eval()
    log.append(f"Model loaded in {time.time()-t0:.1f}s")

    # Load and preprocess image
    image = Image.open(image_path)
    log.append(f"Image: {image.size[0]}x{image.size[1]} ({image.mode})")

    if remove_bg:
        rembg_session = rembg.new_session()
        image = image.convert("RGB")
        image = remove_background(image, rembg_session)
        image = resize_foreground(image, foreground_ratio)
        # Fill background with gray
        image_arr = np.array(image).astype(np.float32) / 255.0
        image_arr = image_arr[:, :, :3] * image_arr[:, :, 3:4] + (1 - image_arr[:, :, 3:4]) * 0.5
        image = Image.fromarray((image_arr * 255.0).astype(np.uint8))
        log.append("Background removed + foreground resized")
    elif image.mode == "RGBA":
        image_arr = np.array(image).astype(np.float32) / 255.0
        image_arr = image_arr[:, :, :3] * image_arr[:, :, 3:4] + (1 - image_arr[:, :, 3:4]) * 0.5
        image = Image.fromarray((image_arr * 255.0).astype(np.uint8))
        log.append("RGBA image composited on gray background")

    # Generate
    log.append(f"Generating 3D (resolution={mc_resolution})...")
    t0 = time.time()
    with torch.inference_mode():
        scene_codes = model(image, device=device)
        mesh = model.extract_mesh(scene_codes, resolution=mc_resolution)[0]
    log.append(f"Generation completed in {time.time()-t0:.1f}s")

    # Export (avoid nested output/output/ when image is already in output/)
    base = os.path.splitext(os.path.basename(image_path))[0]
    img_dir = os.path.dirname(image_path) or "."
    if os.path.basename(img_dir) == "output":
        out_dir = img_dir
    else:
        out_dir = os.path.join(img_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{base}_3d.{output_format}")

    mesh.export(out_path)
    log.append(f"Exported: {out_path}")
    log.append(f"Mesh: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

    # Dimensions (trimesh uses meters)
    bounds = mesh.bounds if hasattr(mesh, "bounds") else [[0, 0, 0], [1, 1, 1]]
    dims = [round((bounds[1][i] - bounds[0][i]) * 1000, 1) for i in range(3)]

    result = {
        "output": out_path,
        "format": output_format,
        "engine": "triposr",
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "dimensions_mm": dims,
        "watertight": bool(mesh.is_watertight) if hasattr(mesh, "is_watertight") else False,
        "log": log
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Image to 3D mesh via TripoSR")
    parser.add_argument("image", help="Path to input image")
    parser.add_argument("--format", choices=["glb", "obj"], default="glb", help="Output format")
    parser.add_argument("--no-bg-remove", action="store_true", help="Skip background removal")
    parser.add_argument("--foreground-ratio", type=float, default=0.85, help="Foreground ratio for resize")
    parser.add_argument("--resolution", type=int, default=256, help="Marching cubes resolution (64-384)")
    args = parser.parse_args()

    result = generate_3d(
        args.image,
        output_format=args.format,
        remove_bg=not args.no_bg_remove,
        foreground_ratio=args.foreground_ratio,
        mc_resolution=args.resolution,
    )
    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
