# CLAUDE.md

This file provides guidance to Claude Code when working with the 3D Print Pipeline project.

## Project Overview

End-to-end AI-powered 3D printing pipeline: reference image → 3D mesh → repair → print-ready STL. Two AI engines (TripoSR fast, Hunyuan3D-2.1 high-quality), plus relief/lithophane generation, mesh repair, and orthographic view rendering.

**Target printer:** Bambu Lab (4-color AMS), 0.4mm nozzle, PLA/PETG.

## Hardware Constraints

- **GPU:** RTX 5070 Ti 16GB VRAM (Blackwell, CC 12.0)
- **RAM:** 64GB
- **OS:** Windows 11
- **Python:** 3.11 (system)
- **CUDA:** 12.8 (torch nightly required for Blackwell)

**VRAM budget per engine:**
| Engine | VRAM | RAM | Disk |
|--------|------|-----|------|
| TripoSR | ~3.5 GB | 8GB+ | ~3GB (model.ckpt) |
| Hunyuan3D-2.1 | ~7 GB | 32GB+ | ~50GB (ComfyUI portable) |
| Relief/Lithophane | <1 GB | any | — |

16GB VRAM comfortably fits Hunyuan3D-2.1 without shared-memory spill. Full `--steps 25` quality runs feasible.

## Directory Structure

```
3dprint/
├── scripts/
│   ├── image-to-3d.py        # TripoSR: image → 3D mesh (~2s inference)
│   ├── hunyuan-to-3d.py      # Hunyuan3D-2.1: image → high-quality mesh
│   ├── image-to-relief.py    # Image → bas-relief / lithophane STL
│   ├── mesh-repair.py        # Watertight repair + decimation → print STL
│   ├── mesh-to-views.py      # 6-view orthographic rendering (front/back/left/right/top/bottom)
│   └── pipeline.py           # End-to-end orchestrator (image → STL)
├── models/                   # TripoSR weights (model.ckpt 1.6GB, config.yaml)
├── config/                   # Model configs
├── triposr/src/              # TripoSR inference code (tsr/ package)
├── start-server.py      # Web server launcher (Python, cross-platform)
├── docs/
│   ├── index.html            # Complete usage guide (dark theme, sidebar nav)
│   ├── dev-journey.html      # 0-to-1 development story
│   └── iterations/           # Design iteration snapshots
├── hunyuan3d/                # Hunyuan3D analysis and download links
│   ├── engine-report.md
│   └── download-links.md
├── output/                   # Generated meshes and views
│   ├── lithophane/           # Backlit lithophane STLs
│   ├── relief/               # Bas-relief STLs
│   └── views/                # Orthographic view renders
└── 混元3D2.1+comfyui便携版+.../  # Hunyuan3D ComfyUI portable package
    └── extracted/ComfyUI_windows_portable/
        ├── python_embeded/   # Embedded Python 3.12
        └── ComfyUI/
            ├── models/       # DiT + VAE weights
            └── custom_nodes/ # Hunyuan3D plugin
```

## Script Reference

### `pipeline.py` — End-to-End Orchestrator

```bash
# Fast preview (TripoSR, ~30s)
python scripts/pipeline.py photo.jpg

# High quality (Hunyuan3D-2.1)
python scripts/pipeline.py photo.jpg --engine hunyuan --steps 10

# With orthographic views
python scripts/pipeline.py photo.jpg --views

# Repair-only mode
python scripts/pipeline.py existing.glb --skip-generate --scale 0.5
```

**Args:** `--engine triposr|hunyuan` `--views` `--steps N` `--seed N` `--resolution N` `--scale N` `--no-bg-remove` `--skip-generate` `--skip-repair` `--base-dir PATH`

### `image-to-3d.py` — TripoSR Generation

```bash
python scripts/image-to-3d.py photo.jpg
python scripts/image-to-3d.py photo.jpg --format obj --resolution 384
python scripts/image-to-3d.py render.png --no-bg-remove
```

**Args:** `--format glb|obj` `--resolution 64-384` `--no-bg-remove` `--foreground-ratio 0.7-0.95`

### `hunyuan-to-3d.py` — Hunyuan3D-2.1 Generation

```bash
# Quick preview (~10min)
python scripts/hunyuan-to-3d.py photo.jpg --steps 10 --resolution 128

# Quality (~30min)
python scripts/hunyuan-to-3d.py photo.jpg --steps 25 --resolution 256
```

**Args:** `--steps 5-50` `--resolution 128-384` `--format glb|obj|stl` `--seed N` `--mode geometry|full` `--skip-bg-remove` `--base-dir PATH`

### `image-to-relief.py` — Bas-Relief & Lithophane

```bash
# Standard relief (viewed from front, reflective)
python scripts/image-to-relief.py photo.jpg --width 160 --height 120

# Lithophane (backlit, light passes through)
python scripts/image-to-relief.py photo.jpg --lithophane

# 4-color quantized
python scripts/image-to-relief.py photo.jpg --colors 4
```

**Args:** `--width N` `--height N` `--max-depth N` `--base-thickness N` `--detail 0-1` `--colors 0|2|4` `--lithophane` `--pixel-spacing N`

**Modes:**
- Relief: `invert=True`, light=high (raised), viewed by reflection
- Lithophane: `invert=False`, light=thin (transparent), viewed by backlight

### `mesh-repair.py` — Watertight Repair

```bash
python scripts/mesh-repair.py model.glb
python scripts/mesh-repair.py model.glb --output stl --scale 0.5 --verbose
```

**Args:** `--output stl|3mf|obj` `--scale N` `--verbose`

### `mesh-to-views.py` — Orthographic View Rendering

```bash
python scripts/mesh-to-views.py model.glb
python scripts/mesh-to-views.py model.stl --resolution 2048 --no-grid
```

**Args:** `--resolution N` `--output-dir PATH` `--no-grid` `--no-individual`

## Pipeline Architecture

```
                 ┌──────────────────────┐
                 │     Input Image       │
                 └─────────┬────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
    ┌───────────┐  ┌────────────┐  ┌──────────────┐
    │ TripoSR   │  │ Hunyuan3D  │  │ Relief/      │
    │ (~2s)     │  │ (~30min)   │  │ Lithophane   │
    └─────┬─────┘  └──────┬─────┘  └──────┬───────┘
          │               │               │
          └───────────────┼───────────────┘
                          ▼
                  ┌──────────────┐
                  │  Mesh Repair  │
                  │ (watertight)  │
                  └──────┬───────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │   STL    │ │  Views   │ │  Print   │
    │ (print)  │ │  (PNG)   │ │  (Bambu) │
    └──────────┘ └──────────┘ └──────────┘
```

## Feature Map

### Image → 3D (AI Generation)
| Feature | TripoSR | Hunyuan3D-2.1 |
|---------|---------|---------------|
| Speed | ~2s | ~67s/step (16GB), ~287s/step (6GB thermal throttle) |
| VRAM | 3.5 GB | 6.86 GB |
| Texture | Vertex color | Geometry-only (WIP) |
| Watertight | Sometimes | Yes |
| License | MIT | Tencent non-commercial |
| Multi-view input | No | Code exists but commented out |

### Post-Processing
| Tool | Function |
|------|----------|
| `mesh-repair.py` | Watertight + unique faces + nondegenerate + pymeshfix fill |
| `mesh-to-views.py` | 6 orthographic views (pyrender, headless) |
| `pipeline.py` | Full orchestration with `--engine` and `--views` flags |

### Relief & Lithophane
| Mode | Thickness | Viewing | Use Case |
|------|-----------|---------|----------|
| Relief | 0.5mm base + 0-3mm | Front (reflective) | Wall art, panel |
| Lithophane | 0.6-2.6mm | Back (transmissive) | Backlit photo frame |

## Key Behaviors & Gotchas

1. **Output path nesting:** Both `image-to-3d.py` and `hunyuan-to-3d.py` avoid `output/output/` nesting when input is already in an `output/` directory.

2. **Hunyuan3D monkey-patch:** `hunyuan-to-3d.py` patches `get_obj_from_str` to handle the hyphenated directory name `ComfyUI-Hunyuan3d-2-1`. This must run before any pipeline imports.

3. **FlowMatchingPipeline returns latents, not mesh:** Hunyuan3D's pipeline `__call__` returns raw latents. VAE must be loaded separately and `latents2mesh` called manually.

4. **VRAM warning:** Model at fp16 ≈ 7.4GB (DiT 3B + VAE 328M + conditioner 304M). On 6GB cards, ~1.4GB spills to shared GPU memory.

5. **STL units:** STL is unitless; scripts use mm coordinates. Bambu Studio imports 1 unit = 1 mm by default.

6. **Chinese paths:** ComfyUI portable path can contain Chinese characters — the embedded Python handles this.

7. **HF mirror:** Set `HF_ENDPOINT=https://hf-mirror.com` for faster model downloads in China.

## Extension Points

### Adding a New AI Engine
1. Create `scripts/<engine>-to-3d.py` following the pattern of `image-to-3d.py`
2. Output JSON with keys: `output`, `format`, `engine`, `vertices`, `faces`, `watertight`, `dimensions_mm`, `log`
3. Register in `pipeline.py` `--engine` choices and generation branch

### Adding a New Post-Processing Step
1. Create standalone script with argparse + JSON output
2. Add to `pipeline.py` as an optional stage (follow `--views` pattern)
3. Document in `docs/index.html`

### Adding Texture/PBR Support
- Hunyuan3D-2.1 has `hy3dpaint` module for PBR texture generation
- Requires separate VRAM budget (~6GB for texture stage alone)
- Entry point: `hy3dpaint/textureGenPipeline.py`

### Multi-View Input Support
- Hunyuan3D-2.1 has `DinoImageEncoderMV` + `MVImageProcessorV2` in codebase
- Node `Hy3D21MultiViewsMeshGenerator` is commented out in `nodes.py`
- Missing config file: `dit_config_2_1_mv.yaml`
- Alternative: MV-DUSt3R+ (Meta, 4-8GB VRAM)

### Adding New Output Formats
- `mesh-repair.py` supports `stl|3mf|obj`
- Add format handling in export methods of target script
- 3MF requires ZIP+XML generation (more complex)

### Slicer Integration
- Future: auto-generate Bambu Studio `.3mf` project files
- Future: auto-arrange print bed, set layer heights, filament mapping

## Dependencies

**Core (all scripts):** `numpy` `trimesh` `Pillow`
**TripoSR:** `torch torchvision rembg[gpu] huggingface_hub omegaconf`
**Hunyuan3D:** ComfyUI portable (embedded Python, no pip install needed)
**Relief/Lithophane:** `scipy scikit-learn fast_simplification`
**Views:** `pyrender pyglet<2`
**Repair:** `pymeshfix`
**Web UI:** `fastapi uvicorn python-multipart`

## Web UI

Web-based task management interface at `web/`.

```bash
python start-server.py              # default 127.0.0.1:8080
python start-server.py --port 9090   # custom port
python start-server.py --lan        # LAN access
python start-server.py --no-browser # skip browser auto-open
```

The launcher checks dependencies, auto-detects network, and opens the browser by default.

Architecture: FastAPI + vanilla JS SPA (ES modules, zero build) + SSE + SQLite. The frontend is modular — 4 CSS files, 8 lazy-loaded page modules, JSON-based i18n (zh/en). Zero modifications to existing CLI scripts — web server calls them via subprocess.

**Key files:** `web/server.py` (FastAPI app), `web/scheduler.py` (async task runner + GPU lock), `web/models.py` (SQLite), `web/schemas.py` (pipeline definitions), `web/node_types.py` (25+ node type definitions), `web/workflow_engine.py` (DAG workflow execution), `web/static/` (modular SPA frontend).

## Iteration History

Every design change is auto-saved to `docs/iterations/` as timestamped snapshots via a Stop hook (`.claude/hooks/save-iteration.ps1`). See `docs/iterations/INDEX.md` for the full list. The hook compares plan file hash — only saves when plan content actually changed.

## Standards & Checklist

For project-wide conventions, design rationale, and quality checklists, see:

- [STANDARDS.md](STANDARDS.md) — Business goals, technical specs, code quality norms, security rules, and quick reference.

When updating CLAUDE.md itself, also update STANDARDS.md if the change affects any documented standards.
