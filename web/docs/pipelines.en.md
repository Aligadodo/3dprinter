# Pipeline Types Reference

## Overview

The system supports **10 pipeline types**, each with different input requirements, parameters, and outputs. This page documents all types in detail.

---

## 1. Bas-Relief (Relief)

**Script**: `image-to-relief.py` | **Type**: CPU | **Input**: Image (.jpg/.png/.webp/.bmp)

Converts an image to a 3D bas-relief — viewed from the front, reflective surface. Supports 4-color AMS multi-color printing.

### Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| width | float | 160.0 | 20–500 | Target physical width (mm) |
| height | float | 120.0 | 20–500 | Target physical height (mm) |
| max_depth | float | 3.0 | 0.5–10.0 | Maximum relief depth (mm) |
| base_thickness | float | 0.5 | 0.2–5.0 | Minimum base plate thickness (mm) |
| detail | float | 0.25 | 0.0–1.0 | Fine detail preservation (0=smooth, 1=full) |
| colors | int | 0 | 0–4 | Quantize to N colors (0=mono) |
| pixel_spacing | float | 0.08 | 0.05–0.5 | Height field resolution |

### Output

- STL mesh file
- Color preview image (PNG, if colors > 0)

---

## 2. Lithophane

**Script**: `image-to-relief.py` | **Type**: CPU | **Input**: Image

Converts an image to a backlit lithophane — thin areas let light through, thick areas block it. Perfect for photo frames and lamps.

### Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| width | float | 160.0 | 20–500 | Target width (mm) |
| height | float | 120.0 | 20–500 | Target height (mm) |
| max_depth | float | 2.0 | 0.5–5.0 | Thickness variation range (mm) |
| base_thickness | float | 0.6 | 0.3–3.0 | Minimum thickness (mm) |
| detail | float | 0.15 | 0.0–1.0 | Fine detail preservation |
| colors | int | 0 | 0–4 | Quantize to N colors |

### Output

- STL mesh file

---

## 3. Layered Color Relief

**Script**: `image-to-layered-relief.py` | **Type**: CPU | **Input**: Image

Single-mesh multi-color relief via height banding. Different Z-height ranges map to different filament colors. Works with AMS / multi-material systems.

### Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| width | float | 160.0 | 20–500 | Target width (mm) |
| height | float | 120.0 | 20–500 | Target height (mm) |
| colors | int | 4 | 2–16 | Number of filament colors |
| layer_height | float | 0.4 | 0.2–1.0 | Z-height per color band (mm) |
| base_thickness | float | 0.3 | 0.2–1.0 | Minimum base plate thickness (mm) |
| edge_smooth | float | 0.5 | 0.0–1.0 | Anti-aliasing at color boundaries |
| pixel_spacing | float | 0.08 | 0.05–0.5 | Height field resolution |
| format | choice | stl | stl/3mf | Output format |

### Output

- STL mesh file
- Color map JSON (colors, Z ranges, area ratios)
- Optional: Bambu Studio compatible 3MF file
- Color preview image

---

## 4. TripoSR (Fast 3D)

**Script**: `image-to-3d.py` | **Type**: GPU | **Input**: Image

Fast AI image-to-3D. ~2s inference, vertex-color GLB output. Best for quick previews and prototypes.

### Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| format | choice | glb | glb/obj | Output format |
| resolution | int | 256 | 64–384 | Marching cubes grid resolution |
| foreground_ratio | float | 0.85 | 0.7–0.95 | Crop ratio for background removal |
| no_bg_remove | bool | false | — | Skip background removal |

### Output

- GLB/OBJ mesh file
- Render preview image

---

## 5. Hunyuan3D-2.1 (Quality)

**Script**: `hunyuan-to-3d.py` | **Type**: GPU | **Input**: Image

High-quality AI image-to-3D. 10-60 min, geometry mode. Best for final output. Needs ~7 GB VRAM.

### Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| mode | choice | geometry | geometry/full | Mode (geometry-only or with texture) |
| steps | int | 15 | 5–50 | Diffusion steps (10-15 preview, 25-50 quality) |
| resolution | int | 256 | 128–384 | Marching cubes resolution |
| seed | int | 42 | 0–2147483647 | Random seed for reproducibility |
| format | choice | glb | glb/obj/stl | Output format |
| skip_bg_remove | bool | false | — | Skip background removal |

### Output

- GLB/OBJ/STL mesh file
- Render preview image

---

## 6. Mesh Simplify

**Script**: `mesh-simplify.py` | **Type**: CPU | **Input**: 3D mesh (.glb/.obj/.stl/.gltf)

Reduce mesh face count via quadratic decimation while preserving shape. Useful for reducing print file size and slicing time.

### Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| target_faces | int | 50000 | 1000–1000000 | Target face count after simplification |
| method | choice | quadric | quadric/cluster | Algorithm (quadric=quality preservation, cluster=fast) |

### Output

- Simplified mesh file (same format as input)

---

## 7. Mesh Smooth

**Script**: `mesh-smooth.py` | **Type**: CPU | **Input**: 3D mesh (.glb/.obj/.stl/.gltf)

Apply Taubin smoothing to reduce surface noise while preserving volume. Great for improving AI-generated model surfaces.

### Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| iterations | int | 3 | 1–20 | Number of smoothing passes |
| lambda | float | 0.5 | 0.0–1.0 | Taubin smoothing strength |
| mu | float | -0.53 | -1.0–0.0 | Taubin expansion factor (negative prevents shrinkage) |

### Output

- Smoothed mesh file

---

## 8. Mesh Scale

**Script**: `mesh-scale.py` | **Type**: CPU | **Input**: 3D mesh (.glb/.obj/.stl/.gltf)

Uniformly scale a mesh by factor or to a target physical size. Useful for fitting models to print bed dimensions.

### Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| scale | float | 1.0 | 0.01–100.0 | Uniform scale multiplier (1.0=no change) |
| target_width | float | 0.0 | 0.0–1000.0 | Target physical width in mm (0=use scale factor) |
| uniform | bool | true | — | Scale all axes equally (preserve proportions) |

### Output

- Scaled mesh file

---

## 9. Mesh Views

**Script**: `mesh-to-views.py` | **Type**: CPU | **Input**: 3D mesh (.glb/.obj/.stl/.gltf)

Renders 6 orthographic views (front/back/left/right/top/bottom) from a 3D mesh. Outputs PNG images.

### Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| resolution | int | 1024 | 256–4096 | Output image resolution per view |
| no_grid | bool | false | — | Only generate individual views, skip grid |

### Output

- Six individual view PNGs
- 3×2 grid composite PNG
- Views directory

---

## 10. Mesh Repair

**Script**: `mesh-repair.py` | **Type**: CPU | **Input**: 3D mesh (.glb/.obj/.stl/.gltf)

Repairs and waterproofs a mesh. Outputs print-ready STL with deduplication, hole filling, and decimation.

### Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| output_format | choice | stl | stl/obj/3mf | Output format |
| scale | float | 1.0 | 0.1–10.0 | Uniform scale factor |

### Output

- Repaired mesh file
