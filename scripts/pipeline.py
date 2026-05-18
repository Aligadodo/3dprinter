#!/usr/bin/env python
"""pipeline.py - End-to-end: image → 3D mesh → repair → print-ready STL.

Usage:
  python pipeline.py <image>                        # TripoSR (fast, ~2s)
  python pipeline.py <image> --engine hunyuan       # Hunyuan3D-2.1 (high quality)
  python pipeline.py <mesh> --skip-generate         # Repair an existing mesh only

Stages:
  1. image-to-3d / hunyuan-to-3d  → .glb mesh
  2. mesh-repair                   → watertight .stl
"""
import argparse, sys, os, json, subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_stage(name: str, cmd: list) -> dict:
    """Run a pipeline stage and return parsed JSON result."""
    print(f"\n{'='*50}")
    print(f"  STAGE: {name}")
    print(f"{'='*50}")
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
    if r.returncode != 0:
        stderr = r.stderr[:500] if r.stderr else "unknown error"
        stdout = r.stdout[:500] if r.stdout else ""
        return {"error": f"{name} failed", "stderr": stderr, "stdout": stdout}
    # Extract JSON from stdout (result is always the last JSON object printed)
    out = r.stdout.strip()
    # Try from the last '{' first — the JSON result is always last
    idx = out.rfind("{")
    if idx >= 0:
        try:
            return json.loads(out[idx:])
        except json.JSONDecodeError:
            # Fallback: try from first '{' if last didn't work
            idx2 = out.find("{")
            if idx2 >= 0 and idx2 != idx:
                try:
                    return json.loads(out[idx2:])
                except json.JSONDecodeError:
                    pass
    return {"raw_output": r.stdout[:1000]}


def pipeline(image_path: str, engine: str = "triposr", scale: float = 1.0,
             mc_resolution: int = 256, remove_bg: bool = True,
             generate: bool = True, repair: bool = True,
             hunyuan_steps: int = 15, hunyuan_seed: int = 42,
             hunyuan_base_dir: str = "", views: bool = False):
    results = {"engine": engine}
    current_mesh = os.path.abspath(image_path)

    # Stage 1: Image to 3D
    if generate:
        if engine == "hunyuan":
            script = "hunyuan-to-3d.py"
            cmd = [sys.executable, os.path.join(SCRIPT_DIR, script)]
            cmd.append(image_path)
            cmd += ["--format", "glb"]
            cmd += ["--resolution", str(mc_resolution)]
            cmd += ["--steps", str(hunyuan_steps)]
            cmd += ["--seed", str(hunyuan_seed)]
            if not remove_bg:
                cmd.append("--skip-bg-remove")
            if hunyuan_base_dir:
                cmd += ["--base-dir", hunyuan_base_dir]
            stage_label = f"Image → 3D (Hunyuan3D-2.1, steps={hunyuan_steps})"
        else:
            script = "image-to-3d.py"
            cmd = [sys.executable, os.path.join(SCRIPT_DIR, script)]
            cmd.append(image_path)
            cmd += ["--format", "glb"]
            cmd += ["--resolution", str(mc_resolution)]
            if not remove_bg:
                cmd.append("--no-bg-remove")
            stage_label = "Image → 3D (TripoSR)"

        r = run_stage(stage_label, cmd)
        results["generate"] = r
        if "error" in r:
            return results
        current_mesh = r.get("output", image_path)

    # Stage 2: Mesh repair
    if repair:
        cmd = [sys.executable, os.path.join(SCRIPT_DIR, "mesh-repair.py")]
        cmd.append(current_mesh)
        cmd += ["--output", "stl"]
        if scale != 1.0:
            cmd += ["--scale", str(scale)]

        r = run_stage("Mesh Repair", cmd)
        results["repair"] = r
        if "error" in r:
            return results
        current_mesh = r.get("output", current_mesh)

    # Stage 3: Orthographic views (optional)
    if views and current_mesh:
        cmd = [sys.executable, os.path.join(SCRIPT_DIR, "mesh-to-views.py")]
        cmd.append(current_mesh)
        cmd += ["--no-individual"]  # grid only for pipeline

        r = run_stage("Orthographic Views", cmd)
        results["views"] = r

    results["final_output"] = current_mesh
    results["pipeline_status"] = "complete"
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="3D Print Pipeline: image → mesh → print-ready STL",
        epilog="Examples:\n"
               "  python pipeline.py photo.jpg\n"
               "  python pipeline.py photo.jpg --engine hunyuan --steps 10\n"
               "  python pipeline.py existing.glb --skip-generate --scale 0.5"
    )
    parser.add_argument("image", help="Path to input image (or existing mesh with --skip-generate)")
    parser.add_argument("--engine", choices=["triposr", "hunyuan"], default="triposr",
                        help="3D generation engine (default: triposr)")
    parser.add_argument("--scale", type=float, default=1.0, help="Uniform scale factor")
    parser.add_argument("--resolution", type=int, default=256,
                        help="Marching cubes resolution (128-384)")
    parser.add_argument("--no-bg-remove", action="store_true", help="Skip background removal")
    parser.add_argument("--skip-generate", action="store_true",
                        help="Skip generation (repair existing mesh)")
    parser.add_argument("--skip-repair", action="store_true",
                        help="Skip repair (output raw mesh)")
    parser.add_argument("--views", action="store_true",
                        help="Generate 6 orthographic views of the final mesh")
    # Hunyuan3D-specific options
    parser.add_argument("--steps", type=int, default=15,
                        help="[Hunyuan] Diffusion steps (10-15 preview, 25-50 quality)")
    parser.add_argument("--seed", type=int, default=42,
                        help="[Hunyuan] Random seed for reproducibility")
    parser.add_argument("--base-dir", default="",
                        help="[Hunyuan] Path to Hunyuan3D portable package")

    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(json.dumps({"error": f"Image not found: {args.image}"}))
        sys.exit(1)

    if args.engine == "hunyuan" and not args.skip_generate and args.steps > 20:
        print(f"⚠  --steps {args.steps} may take 1-3 hours on 6GB GPUs.")
        print(f"   Consider --steps 10 for a quick preview first.")

    result = pipeline(
        args.image,
        engine=args.engine,
        scale=args.scale,
        mc_resolution=args.resolution,
        remove_bg=not args.no_bg_remove,
        generate=not args.skip_generate,
        repair=not args.skip_repair,
        hunyuan_steps=args.steps,
        hunyuan_seed=args.seed,
        hunyuan_base_dir=args.base_dir,
        views=args.views,
    )

    print(f"\n{'='*50}")
    print(f"  PIPELINE {'COMPLETE' if result.get('pipeline_status') == 'complete' else 'FAILED'}")
    print(f"{'='*50}")
    print(f"  Engine: {result.get('engine', 'N/A')}")
    print(f"  Final output: {result.get('final_output', 'N/A')}")
    if result.get("pipeline_status") != "complete":
        for stage, r in result.items():
            if "error" in str(r):
                print(f"  [{stage}] ERROR: {r}")
    print()
    print(json.dumps(result, ensure_ascii=False, indent=2))
