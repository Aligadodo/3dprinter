#!/usr/bin/env python
"""hunyuan-to-3d.py - Single image → 3D mesh using Hunyuan3D-2.1 (ComfyUI portable).

Usage:
  python hunyuan-to-3d.py <image_path> [--mode geometry|full] [--resolution N]
                           [--steps N] [--format glb|obj|stl] [--seed N]
                           [--skip-bg-remove]

VRAM requirements:
  - 8GB+ GPU: normal operation (~30s/step)
  - 6GB GPU: works but slow due to shared-memory swapping (~60s/step)
  - Use --steps 10 for faster preview on 6GB cards
"""
import argparse
import sys
import os
import json
import time


def setup_environment(base_dir: str):
    """Configure Python path for ComfyUI portable environment."""
    comfy_portable = os.path.join(base_dir, "extracted", "ComfyUI_windows_portable")
    comfy_root = os.path.join(comfy_portable, "ComfyUI")
    python_embeded = os.path.join(comfy_portable, "python_embeded")

    # Add to Python path
    for p in [comfy_root, python_embeded,
              os.path.join(python_embeded, "Lib", "site-packages")]:
        if p not in sys.path:
            sys.path.insert(0, p)

    os.environ.setdefault("COMFYUI_PATH", comfy_root)
    os.environ.setdefault("PYTHONPATH", os.pathsep.join(
        [x for x in [comfy_root, python_embeded] if x]))

    return comfy_portable, comfy_root


def _patch_get_obj_from_str():
    """Monkey-patch hy3dshape.pipelines.get_obj_from_str to handle
    the hyphenated directory name (ComfyUI-Hunyuan3d-2-1) which
    is not a valid Python module name.

    The YAML config uses relative imports like:
      .hy3dshape.hy3dshape.models.denoisers.hunyuandit.HunYuanDiTPlain
    We strip the leading dot to make them absolute imports, since
    hy3dshape is already on sys.path as a namespace package.
    """
    import importlib
    from hy3dshape.hy3dshape import pipelines as _p

    _original = _p.get_obj_from_str

    def _patched(string, reload=False):
        module_path, cls = string.rsplit(".", 1)
        if module_path.startswith("."):
            module_path = module_path[1:]
        if reload:
            mod = importlib.import_module(module_path)
            importlib.reload(mod)
        return getattr(importlib.import_module(module_path), cls)

    _p.get_obj_from_str = _patched


def generate_hunyuan3d(image_path: str, base_dir: str = "",
                       mode: str = "geometry", steps: int = 15,
                       guidance_scale: float = 5.0, seed: int = 42,
                       mc_resolution: int = 256, output_format: str = "glb",
                       skip_bg_remove: bool = False):
    """Generate a 3D mesh using Hunyuan3D-2.1.

    Args:
        image_path: Path to input image.
        base_dir: Root of the Hunyuan3D ComfyUI portable package.
        mode: 'geometry' (white model) or 'full' (with PBR texture, WIP).
        steps: Diffusion steps. 10-15 for preview, 25-50 for quality.
        guidance_scale: CFG scale. Default 5.0.
        seed: Random seed for reproducibility.
        mc_resolution: Marching cubes resolution (128-384).
        output_format: 'glb', 'obj', or 'stl'.
        skip_bg_remove: Skip background removal (use if image already has
                        transparent background).
    """
    if not base_dir:
        base_dir = os.environ.get("HUNYUAN3D_HOME", "")
        if not base_dir:
            base_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "混元3D2.1+comfyui便携版+工作流+模型+环境")

    if not os.path.exists(image_path):
        return {"error": f"Image not found: {image_path}"}
    if not os.path.exists(base_dir):
        return {"error": f"Hunyuan3D base dir not found: {base_dir}"}

    log = []
    comfy_portable, comfy_root = setup_environment(base_dir)

    # Add the custom node plugin directory for namespace package access.
    # The outer hy3dshape/ (no __init__.py) acts as a namespace package,
    # the inner hy3dshape/ (with __init__.py) is the actual package.
    hy3d_plugin_dir = os.path.join(
        comfy_root, "custom_nodes", "ComfyUI-Hunyuan3d-2-1")
    if hy3d_plugin_dir not in sys.path:
        sys.path.insert(0, hy3d_plugin_dir)

    try:
        import torch
        from PIL import Image
    except ImportError as e:
        return {"error": f"Missing dependency: {e}"}

    if not torch.cuda.is_available():
        return {"error": "CUDA not available. Hunyuan3D requires an NVIDIA GPU."}

    device = "cuda"
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    gpu_name = torch.cuda.get_device_name(0)
    log.append(f"GPU: {gpu_name} ({vram_gb:.1f} GB VRAM)")

    if vram_gb < 7.0:
        log.append(f"WARNING: VRAM ({vram_gb:.1f} GB) below recommended 8GB. "
                   f"Model will spill to shared memory (~60s/step). "
                   f"Use --steps 10 for faster previews.")
    log.append(f"Mode: {mode} | steps={steps} | resolution={mc_resolution}")

    # Initialize ComfyUI infrastructure (for model_management)
    log.append("Initializing ComfyUI environment...")
    try:
        import folder_paths
        import comfy.model_management as mm

        folder_paths.base_path = comfy_root
        folder_paths.models_dir = os.path.join(comfy_root, "models")
        mm.unload_all_models()
        mm.soft_empty_cache()
        log.append("ComfyUI environment ready")
    except ImportError as e:
        return {"error": f"Failed to init ComfyUI environment: {e}. "
                         f"Ensure ComfyUI portable is at: {comfy_portable}"}

    # Patch the broken module loader before importing pipeline
    _patch_get_obj_from_str()

    # === Stage 1: Geometry Generation ===
    log.append("Loading geometry pipeline...")
    t0 = time.time()

    try:
        from hy3dshape.hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline
        from hy3dshape.hy3dshape.postprocessors import (
            FloaterRemover, DegenerateFaceRemover,
        )
        from hy3dshape.hy3dshape.rembg import BackgroundRemover
    except ImportError as e:
        return {"error": f"Failed to import Hunyuan3D modules: {e}"}

    # Load DiT pipeline (model + VAE + conditioner from config)
    dit_path = os.path.join(comfy_root, "models", "diffusion_models",
                            "hunyuan3d-dit-v2-1.ckpt")
    config_path = os.path.join(hy3d_plugin_dir, "configs", "dit_config_2_1.yaml")

    if not os.path.exists(dit_path):
        return {"error": f"DiT model not found: {dit_path}"}
    if not os.path.exists(config_path):
        return {"error": f"Pipeline config not found: {config_path}"}

    pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_single_file(
        ckpt_path=dit_path,
        config_path=config_path,
        device="cuda",
        torch_dtype=torch.float16,
    )
    log.append(f"Pipeline loaded in {time.time() - t0:.1f}s")

    # Report VRAM status
    vram_used = torch.cuda.memory_allocated() / 1024**3
    log.append(f"VRAM used: {vram_used:.1f} GB / {vram_gb:.1f} GB")

    # Load and preprocess image
    image = Image.open(image_path).convert("RGB")
    log.append(f"Image: {image.size[0]}x{image.size[1]}")

    if not skip_bg_remove:
        t0 = time.time()
        remover = BackgroundRemover()
        image = remover(image)
        log.append(f"Background removed in {time.time() - t0:.1f}s")

    # Stage 1a: Generate latents via DiT flow matching.
    # The FlowMatchingPipeline.__call__ returns raw latents (Tensor),
    # NOT a mesh. We decode them separately.
    log.append(f"Generating latents (steps={steps})...")
    t0 = time.time()

    with torch.inference_mode():
        latents = pipeline(
            image=image,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            generator=torch.Generator(device=device).manual_seed(seed),
        )

    log.append(f"Latents generated in {time.time() - t0:.1f}s")

    # Clone latents: the pipeline's @torch.inference_mode() decorator marks
    # them as inference-only. Use clone() for explicit copy.
    latents = latents.clone()

    # Stage 1b: Decode latents → mesh via standalone VAE.
    log.append("Decoding mesh from latents...")
    t_decode = time.time()

    from comfy.utils import load_torch_file
    from hy3dshape.hy3dshape.models.autoencoders import ShapeVAE

    vae_path = os.path.join(comfy_root, "models", "vae",
                            "hunyuan3d-vae-v2-1.ckpt")
    if not os.path.exists(vae_path):
        return {"error": f"VAE model not found: {vae_path}"}

    vae_sd = load_torch_file(vae_path)
    vae_config = {
        "num_latents": 4096,
        "embed_dim": 64,
        "num_freqs": 8,
        "include_pi": False,
        "heads": 16,
        "width": 1024,
        "num_encoder_layers": 8,
        "num_decoder_layers": 16,
        "qkv_bias": False,
        "qk_norm": True,
        "scale_factor": 1.0039506158752403,
        "geo_decoder_mlp_expand_ratio": 4,
        "geo_decoder_downsample_ratio": 1,
        "geo_decoder_ln_post": True,
        "point_feats": 4,
        "pc_size": 81920,
        "pc_sharpedge_size": 0,
    }
    vae = ShapeVAE(**vae_config)
    vae.load_state_dict(vae_sd)
    vae.eval().to(device=device, dtype=torch.float16)

    latents = vae.decode(latents)
    mesh_outputs = vae.latents2mesh(
        latents,
        bounds=1.01,
        mc_level=0.03,
        num_chunks=5000,
        octree_resolution=mc_resolution,
        mc_algo="mc",
        enable_pbar=True,
    )

    # latents2mesh returns a list of mesh data objects; grab the first
    if isinstance(mesh_outputs, list):
        mesh_data = mesh_outputs[0] if mesh_outputs else None
    else:
        mesh_data = mesh_outputs

    if mesh_data is None:
        return {"error": "Failed to decode mesh from latents"}

    # Convert raw mesh output (has .mesh_v / .mesh_f) to trimesh
    import trimesh as Trimesh
    mesh_data.mesh_f = mesh_data.mesh_f[:, ::-1]  # flip face winding
    mesh = Trimesh.Trimesh(mesh_data.mesh_v, mesh_data.mesh_f)

    log.append(f"Mesh decoded in {time.time() - t_decode:.1f}s")
    log.append(f"Raw mesh: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

    # Postprocess
    t0 = time.time()
    mesh = FloaterRemover()(mesh)
    mesh = DegenerateFaceRemover()(mesh)
    # FaceReduce not applied here; use mesh-repair.py for decimation
    log.append(f"Postprocessed in {time.time() - t0:.1f}s")
    log.append(f"Final mesh: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

    # === Stage 2: Texture (full mode — WIP) ===
    if mode == "full":
        log.append("Full texture pipeline is WIP — exporting geometry only.")
        # TODO: implement PBR texture generation using hy3dpaint modules.
        # Requires the PaintPBR diffusers model in models/diffusers/ and
        # separate VRAM budgeting (texture stage needs ~6GB on its own).

    # Export
    mm.unload_all_models()
    mm.soft_empty_cache()

    base = os.path.splitext(os.path.basename(image_path))[0]
    img_dir = os.path.dirname(image_path) or "."
    # Avoid nested output/output/ when image is already in output/
    if os.path.basename(img_dir) == "output":
        out_dir = img_dir
    else:
        out_dir = os.path.join(img_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{base}_hy3d.{output_format}")

    mesh.export(out_path)
    log.append(f"Exported: {out_path}")

    # Dimensions
    bounds = mesh.bounds if hasattr(mesh, "bounds") else [[0, 0, 0], [1, 1, 1]]
    dims = [round((bounds[1][i] - bounds[0][i]) * 1000, 1) for i in range(3)]
    is_watertight = bool(mesh.is_watertight) if hasattr(mesh, "is_watertight") else False

    result = {
        "output": out_path,
        "format": output_format,
        "engine": "hunyuan3d-2.1",
        "mode": mode,
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "watertight": is_watertight,
        "dimensions_mm": dims,
        "log": log,
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Image to 3D via Hunyuan3D-2.1 (ComfyUI portable)")
    parser.add_argument("image", help="Path to input image")
    parser.add_argument("--mode", choices=["geometry", "full"],
                        default="geometry",
                        help="geometry-only (faster, less VRAM) or full (with texture, WIP)")
    parser.add_argument("--steps", type=int, default=15,
                        help="Diffusion steps (10-15 for preview, 25-50 for quality)")
    parser.add_argument("--resolution", type=int, default=256,
                        help="MC resolution (128-512)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed")
    parser.add_argument("--format", choices=["glb", "obj", "stl"],
                        default="glb")
    parser.add_argument("--skip-bg-remove", action="store_true",
                        help="Skip background removal")
    parser.add_argument("--base-dir", default="",
                        help="Hunyuan3D base directory path")
    args = parser.parse_args()

    result = generate_hunyuan3d(
        args.image,
        base_dir=args.base_dir,
        mode=args.mode,
        steps=args.steps,
        mc_resolution=args.resolution,
        seed=args.seed,
        output_format=args.format,
        skip_bg_remove=args.skip_bg_remove,
    )
    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
