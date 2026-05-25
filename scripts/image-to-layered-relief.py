#!/usr/bin/env python
"""image-to-layered-relief.py — Single-mesh multi-color relief via height banding.

Decomposes an image into N colours via k-means, then builds a SINGLE relief mesh
where each colour occupies a distinct Z-height band. Darker colours sit lower,
brighter colours sit higher. In the slicer, assign different filaments to
different layer-height ranges for a multi-colour FDM print with a single-nozzle
printer + AMS / multi-material unit.

Usage:
  python image-to-layered-relief.py photo.jpg
  python image-to-layered-relief.py photo.jpg --colors 4 --layer-height 0.4
  python image-to-layered-relief.py photo.jpg --colors 5 --format 3mf
"""

import argparse, sys, os, json, time, struct
from pathlib import Path
import numpy as np
import trimesh


# ═══════════════════════════════════════════════════════════════════
#  Progress emission
# ═══════════════════════════════════════════════════════════════════

def _emit(event, data):
    """Emit a progress event as a single JSON line to stdout."""
    payload = {"event": event}
    payload.update(data)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════
#  Image loading
# ═══════════════════════════════════════════════════════════════════

def _load_and_preprocess(image_path, target_width_mm, target_height_mm,
                         pixel_spacing_mm=0.1):
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    iw, ih = img.size
    aspect = iw / ih

    if aspect > target_width_mm / target_height_mm:
        phys_w = target_width_mm
        phys_h = target_width_mm / aspect
    else:
        phys_h = target_height_mm
        phys_w = target_height_mm * aspect

    pixels_w = int(phys_w / pixel_spacing_mm)
    pixels_h = int(phys_h / pixel_spacing_mm)

    img_resized = img.resize((pixels_w, pixels_h), Image.LANCZOS)
    rgb = np.array(img_resized, dtype=np.float32)
    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

    return gray, rgb, phys_w, phys_h, pixels_w, pixels_h


# ═══════════════════════════════════════════════════════════════════
#  Colour decomposition
# ═══════════════════════════════════════════════════════════════════

def _quantize_colors(rgb, num_colors):
    from sklearn.cluster import KMeans
    H, W, _ = rgb.shape
    pixels = rgb.reshape(-1, 3)
    sample = pixels[::4]
    km = KMeans(n_clusters=num_colors, random_state=42, n_init=3, max_iter=100)
    km.fit(sample)
    labels = km.predict(pixels).reshape(H, W)
    palette = km.cluster_centers_.astype(np.uint8)
    return labels, palette


def _sort_by_luminance(labels, palette, gray):
    """Sort colour clusters by mean pixel luminance — darkest first (lowest Z)."""
    cluster_lum = []
    for i in range(len(palette)):
        mask = labels == i
        if mask.sum() == 0:
            cluster_lum.append((i, 0))
        else:
            cluster_lum.append((i, float(gray[mask].mean())))
    cluster_lum.sort(key=lambda x: x[1])
    sorted_indices = [c[0] for c in cluster_lum]
    return sorted_indices


# ═══════════════════════════════════════════════════════════════════
#  Height-map construction
# ═══════════════════════════════════════════════════════════════════

def _build_height_map(labels, palette, gray, sorted_indices,
                      base_thickness_mm, layer_height_mm):
    """Build a single continuous height field with colour banding.

    Each colour cluster maps to a Z-band of height `layer_height_mm`.
    Within each band, the original grayscale value of the pixel determines
    fine height variation (shading).

    Returns height_map (mm, 0-based at base_thickness offset) and band info.
    """
    H, W = labels.shape
    n = len(sorted_indices)
    height_map = np.zeros((H, W), dtype=np.float32)

    bands = []
    for band_order, ci in enumerate(sorted_indices):
        band_start = band_order * layer_height_mm
        rgb_c = palette[ci].tolist()
        hex_c = "#{:02x}{:02x}{:02x}".format(*rgb_c)
        area = int((labels == ci).sum())
        color_name = _rgb_to_color_name(*rgb_c)

        # Within-cluster grayscale range for shading
        mask = labels == ci
        g_vals = gray[mask]
        g_min, g_max = g_vals.min(), g_vals.max()
        g_range = g_max - g_min if g_max > g_min else 1.0

        # Map: grayscale → height within this band
        band_heights = (gray - g_min) / g_range * layer_height_mm
        height_map = np.where(mask, band_start + band_heights, height_map)

        bands.append({
            "order": band_order + 1,
            "color_name": color_name,
            "color_hex": hex_c,
            "color_rgb": rgb_c,
            "area_ratio": round(area / (H * W), 3),
            "z_start_mm": round(base_thickness_mm + band_start, 2),
            "z_end_mm": round(base_thickness_mm + band_start + layer_height_mm, 2),
            "luminance_mean": float(g_vals.mean()),
        })

    return height_map, bands


# ═══════════════════════════════════════════════════════════════════
#  Watertight thin-plate mesh building
# ═══════════════════════════════════════════════════════════════════

def _build_relief_mesh(height_map, phys_w, phys_h, base_thickness_mm=0.3,
                       pixel_spacing_mm=None):
    """Build a watertight thin-plate mesh from a height field.

    Front face at z = base_thickness + height, back face at z = 0.
    Side walls close the volume.
    """
    from multi_color.mesh_builder import limit_overhang_slope

    if pixel_spacing_mm is not None:
        height_map = limit_overhang_slope(height_map, pixel_spacing_mm)

    H, W = height_map.shape

    x = np.linspace(0, phys_w, W)
    y = np.linspace(phys_h, 0, H)
    xv, yv = np.meshgrid(x, y)
    z_front = base_thickness_mm + height_map
    z_back = np.zeros_like(z_front)

    n_per_face = H * W
    verts = np.zeros((n_per_face * 2, 3), dtype=np.float32)
    verts[:n_per_face, 0] = xv.ravel()
    verts[:n_per_face, 1] = yv.ravel()
    verts[:n_per_face, 2] = z_front.ravel()
    verts[n_per_face:, 0] = xv.ravel()
    verts[n_per_face:, 1] = yv.ravel()
    verts[n_per_face:, 2] = z_back.ravel()

    faces = []
    # Front face
    for row in range(H - 1):
        for col in range(W - 1):
            a = row * W + col; b = a + 1; c = a + W; d = c + 1
            faces.append([a, b, d]); faces.append([a, d, c])
    offset = n_per_face
    # Back face (reversed winding)
    for row in range(H - 1):
        for col in range(W - 1):
            a = offset + row * W + col; b = a + 1; c = a + W; d = c + 1
            faces.append([a, d, b]); faces.append([a, c, d])
    # Side walls — bottom edge (y=0)
    for col in range(W - 1):
        f0, f1 = col, col + 1; b0, b1 = offset + f0, offset + f1
        faces.append([f0, b0, b1]); faces.append([f0, b1, f1])
    # Side walls — top edge (y=phys_h)
    for col in range(W - 1):
        f0 = (H - 1) * W + col; f1 = f0 + 1; b0, b1 = offset + f0, offset + f1
        faces.append([f0, f1, b1]); faces.append([f0, b1, b0])
    # Side walls — left edge (x=0)
    for row in range(H - 1):
        f0 = row * W; f1 = (row + 1) * W; b0, b1 = offset + f0, offset + f1
        faces.append([f0, f1, b1]); faces.append([f0, b1, b0])
    # Side walls — right edge (x=phys_w)
    for row in range(H - 1):
        f0 = row * W + (W - 1); f1 = (row + 1) * W + (W - 1); b0, b1 = offset + f0, offset + f1
        faces.append([f0, b0, b1]); faces.append([f0, b1, f1])

    faces = np.array(faces, dtype=np.int32)
    # Outward-facing normals for manifold3d compatibility
    faces = np.flip(faces, axis=1)
    return verts, faces


def _build_xml_mesh(verts, faces, obj_id=1, obj_uuid=None):
    """Convert binary mesh data to 3MF XML mesh format.

    Returns UTF-8 encoded XML string in the OPC mesh representation
    (object with <mesh><vertices>/<triangles>) used by all official
    Bambu Studio 3MF files — binary STL is NOT used internally.
    """
    if obj_uuid is None:
        import uuid
        obj_uuid = str(uuid.uuid4()).replace('-', '')[:16].upper()
        obj_uuid = f"00020000-{obj_uuid[:4]}-{obj_uuid[4:8]}-{obj_uuid[8:12]}-{obj_uuid[12:]}"

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<model unit="millimeter" xml:lang="en-US"',
        ' xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"',
        ' xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"',
        ' xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"',
        ' requiredextensions="p">',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        ' <resources>',
        f'  <object id="{obj_id}" p:UUID="{obj_uuid}" type="model">',
        '   <mesh>',
        '    <vertices>',
    ]
    for x, y, z in verts:
        lines.append(f'     <vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>')
    lines.append('    </vertices>')
    lines.append('    <triangles>')
    for a, b, c in faces:
        lines.append(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>')
    lines.append('    </triangles>')
    lines.append('   </mesh>')
    lines.append('  </object>')
    lines.append(' </resources>')
    lines.append(' <build/>')
    lines.append('</model>')
    return '\n'.join(lines).encode('utf-8')


# ═══════════════════════════════════════════════════════════════════
#  Binary STL export
# ═══════════════════════════════════════════════════════════════════

def _export_stl(verts, faces, out_path):
    verts = verts.astype(np.float32)
    faces = faces.astype(np.int32)
    with open(out_path, 'wb') as f:
        f.write(b'\x00' * 80)
        f.write(struct.pack('<I', len(faces)))
        for tri in faces:
            v0, v1, v2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
            e1, e2 = v1 - v0, v2 - v0
            n = np.cross(e1, e2)
            n = n / (np.linalg.norm(n) + 1e-10)
            f.write(struct.pack('<3f', *n))
            f.write(struct.pack('<3f', *v0))
            f.write(struct.pack('<3f', *v1))
            f.write(struct.pack('<3f', *v2))
            f.write(struct.pack('<H', 0))


# ═══════════════════════════════════════════════════════════════════
#  Human-readable colour naming
# ═══════════════════════════════════════════════════════════════════

def _rgb_to_color_name(r, g, b):
    """Map an RGB triplet to a Chinese colour name.

    Uses a tiered hue→ lightness→ value decision tree.
    Names are approximate — matches within ±15° hue, ±20% lightness.
    """
    import math

    # Normalise to [0,1]
    r, g, b = r / 255.0, g / 255.0, b / 255.0

    # Hue in degrees
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    delta = max_c - min_c

    if delta < 0.02:
        if max_c < 0.2:
            return "黑色"
        if max_c < 0.45:
            return "深灰色"
        if max_c < 0.7:
            return "灰色"
        if max_c > 0.9 and delta < 0.05:
            return "白色"
        return "浅灰色"

    if max_c == r:
        h = 60 * ((g - b) / delta) % 360
    elif max_c == g:
        h = 60 * ((b - r) / delta) + 120
    else:
        h = 60 * ((r - g) / delta) + 240

    lightness = (max_c + min_c) / 2
    sat = delta / max_c if max_c > 0 else 0

    # ── Red zone (350°–15°) ──────────────────────────────
    if h < 15 or h >= 350:
        if lightness < 0.25:
            return "深红色"
        if lightness < 0.45:
            return "暗红色"
        if lightness > 0.8 and sat < 0.25:
            return "浅粉色"
        if lightness > 0.7:
            return "粉色"
        return "红色"

    # ── Orange zone (15°–45°) ───────────────────────────
    if h < 45:
        if lightness < 0.3:
            return "深棕色"
        if lightness < 0.45:
            return "棕色"
        if lightness > 0.8:
            return "浅橙色"
        return "橙色"

    # ── Yellow zone (45°–70°) ───────────────────────────
    if h < 70:
        if lightness < 0.35:
            return "深黄绿色"
        if lightness < 0.5:
            return "橄榄色"
        if lightness > 0.82:
            return "浅黄色"
        return "黄色"

    # ── Green zone (70°–165°) ───────────────────────────
    if h < 165:
        if lightness < 0.25:
            return "深绿色"
        if lightness < 0.4:
            return "暗绿色"
        if lightness < 0.65:
            return "绿色"
        if lightness > 0.8:
            return "浅绿色"
        return "黄绿色"

    # ── Cyan zone (165°–200°) ──────────────────────────
    if h < 200:
        if lightness < 0.35:
            return "深青色"
        if lightness < 0.5:
            return "青色"
        return "浅蓝色"

    # ── Blue zone (200°–260°) ──────────────────────────
    if h < 260:
        if lightness < 0.25:
            return "深蓝色"
        if lightness < 0.4:
            return "深蓝紫色"
        if lightness < 0.55:
            return "蓝色"
        if lightness > 0.78:
            return "浅蓝色"
        return "蓝色"

    # ── Purple zone (260°–290°) ────────────────────────
    if h < 290:
        if lightness < 0.3:
            return "深紫色"
        if lightness < 0.5:
            return "紫罗兰色"
        if lightness > 0.75:
            return "薰衣草色"
        return "紫色"

    # ── Pink/magenta zone (290°–350°) ─────────────────
    if lightness < 0.3:
        return "深粉紫色"
    if lightness < 0.55:
        return "紫红色"
    if lightness > 0.78:
        return "浅粉色"
    return "洋红色"


# ═══════════════════════════════════════════════════════════════════
#  Preview & colour-map export
# ═══════════════════════════════════════════════════════════════════

def _export_preview(labels, palette, out_path):
    from PIL import Image
    H, W = labels.shape
    img_arr = np.zeros((H, W, 3), dtype=np.uint8)
    for c in range(len(palette)):
        img_arr[labels == c] = palette[c]
    Image.fromarray(img_arr).save(out_path)


def _build_color_config(bands, phys_w, phys_h, total_mm, base_mm,
                        layer_mm, stl_name, printer, out_dir, base):
    """Generate color_config.json — human-readable slicer configuration guide.

    Provides Z-height → colour-name mapping with specific setup steps
    for Bambu Studio manual filament assignment.
    """
    import io
    from PIL import Image

    config = {
        "version": 1,
        "printer": printer,
        "model": {
            "width_mm": round(phys_w, 1),
            "height_mm": round(phys_h, 1),
            "depth_mm": round(total_mm, 2),
            "base_thickness_mm": base_mm,
            "layer_height_mm": layer_mm,
            "stl_file": stl_name,
        },
        "colors": [],
        "steps": {
            "zh": [
                "在Bambu Studio中打开导出的3MF文件",
                "点击右侧「对象设置」中的「耗材」标签",
                "为每个颜色层段手动分配AMS槽位：",
            ],
            "en": [
                "Open the exported 3MF file in Bambu Studio",
                "In the right-panel 'Object Settings' click the 'Filament' tab",
                "Manually assign AMS slots for each colour band:",
            ],
        },
    }

    for b in bands:
        color_name = b["color_name"]
        hex_val = b["color_hex"]
        z_start = b["z_start_mm"]
        z_end = b["z_end_mm"]

        config["colors"].append({
            "slot": b["order"],
            "name": color_name,
            "hex": hex_val,
            "rgb": b["color_rgb"],
            "z_start_mm": z_start,
            "z_end_mm": z_end,
            "area_ratio": b["area_ratio"],
            "filament_note_zh": f"第{b['order']}色层：{z_start:.1f}–{z_end:.1f}mm，{color_name} {hex_val}",
            "filament_note_en": f"Layer {b['order']}: {z_start:.1f}–{z_end:.1f}mm, {color_name} {hex_val}",
        })

        config["steps"]["zh"].append(
            f"  第{b['order']}段（Z {z_start:.1f}–{z_end:.1f}mm）："
            f"在「{color_name}」槽位选择对应耗材色号{hex_val}"
        )
        config["steps"]["en"].append(
            f"  Band {b['order']} (Z {z_start:.1f}–{z_end:.1f}mm): "
            f"assign filament colour {hex_val} ({color_name}) to slot {b['order']}"
        )

    config["steps"]["zh"].extend([
        "切片时确认「多色模式」或「按层换料」已启用",
        "在预览窗口验证各段高度与颜色对应关系正确",
    ])
    config["steps"]["en"].extend([
        "Ensure 'Multi-colour mode' or 'Tool-change at height' is enabled before slicing",
        "Verify in the preview that each band height matches the colour assignment",
    ])

    path = os.path.join(out_dir, f"{base}_color_config.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return path, config


def _export_color_map(map_path, bands, phys_w, phys_h, base_mm, layer_mm,
                      total_mm, stl_name):
    """Write colour-map.json with height→colour mapping for slicer setup."""
    color_map = {
        "width_mm": round(phys_w, 1),
        "height_mm": round(phys_h, 1),
        "num_colors": len(bands),
        "base_thickness_mm": base_mm,
        "band_height_mm": layer_mm,
        "total_relief_mm": round(total_mm, 2),
        "stl_file": stl_name,
        "bands": bands,
        "instructions": {
            "zh": [
                f"共 {len(bands)} 色，总厚度 {total_mm:.1f} mm。",
                "在切片软件中，使用「层高范围」或「暂停换料」功能：",
            ],
            "en": [
                f"{len(bands)} colours, total thickness {total_mm:.1f} mm.",
                "In your slicer, use 'Height Range' or 'Pause at Height' feature:",
            ],
        },
    }

    for b in bands:
        color_map["instructions"]["zh"].append(
            f"  Z {b['z_start_mm']:.1f}–{b['z_end_mm']:.1f} mm → 换 {b['color_name']} {b['color_hex']}")
        color_map["instructions"]["en"].append(
            f"  Z {b['z_start_mm']:.1f}–{b['z_end_mm']:.1f} mm → change to {b['color_name']} {b['color_hex']}")

    with open(map_path, 'w', encoding='utf-8') as f:
        json.dump(color_map, f, ensure_ascii=False, indent=2)
    return color_map


# ═══════════════════════════════════════════════════════════════════
#  3MF export (Bambu Studio multi-color compatible)
# ═══════════════════════════════════════════════════════════════════

def _resolve_template_dir():
    return Path(__file__).resolve().parent / "templates" / "bambu"


def _load_template(printer, filename, tpl_dir=None):
    if tpl_dir is None:
        tpl_dir = _resolve_template_dir()
    path = tpl_dir / printer.lower() / filename
    if not path.exists():
        path = tpl_dir / "p1s" / filename
    return path.read_text("utf-8")


def _load_profile(printer, tpl_dir=None):
    return json.loads(_load_template(printer, "profile.json", tpl_dir))


def _resolve_template_json(json_str, vars):
    """Parse a template JSON string with {{PLACEHOLDER}} values,
    walk the resulting dict, and replace placeholder strings with
    Python objects from vars. Returns a valid JSON string.
    """
    import re
    cfg = json.loads(json_str)
    _placeholder_re = re.compile(r'\{\{(.+?)\}\}')

    def _walk(obj):
        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_walk(v) for v in obj]
        elif isinstance(obj, str):
            # Single exact placeholder -> Python object (list, dict, str, etc.)
            m = _placeholder_re.fullmatch(obj)
            if m:
                key = m.group(1)
                if key in vars:
                    return vars[key]
            # String with embedded placeholders -> string substitution
            if "{{" in obj:
                def _replace(m):
                    key = m.group(1)
                    val = vars.get(key, m.group(0))
                    if isinstance(val, (list, dict)):
                        raise TypeError(
                            f"Cannot substitute list/dict placeholder {{{{ {key} }}}} "
                            f"inside compound string: \"{obj}\""
                        )
                    return str(val)
                return _placeholder_re.sub(_replace, obj)
            return obj
        return obj

    resolved = _walk(cfg)
    return json.dumps(resolved, indent=4, ensure_ascii=False)



def _build_defaults(N, profile):
    """Build per-filament and per-extruder default values sized for N filaments.
    Returns Python dict with list/string values (not JSON-encoded).
    """
    fa = lambda val, n=N: [str(val)] * n
    nil8 = ["nil"] * (2 * N)

    dfp = profile.get("default_filament_profile", "Bambu PLA Basic @BBL X1C")
    ftype = "PLA"
    default_bed_temp = "55"
    default_pla_temp = "220"

    return {
        # --- Per-filament defaults (size N) ---
        "FILAMENT_FILAMENT_COLOUR": ["#000000"] * N,
        "FILAMENT_FILAMENT_TYPE": [ftype] * N,
        "FILAMENT_FILAMENT_IDS": ["GFL99"] * N,
        "FILAMENT_FILAMENT_VENDOR": ["Bambu Lab"] * N,
        "FILAMENT_FILAMENT_SETTINGS_ID": [dfp] * N,
        "FILAMENT_FILAMENT_COST": fa("24.99"),
        "FILAMENT_FILAMENT_DENSITY": fa("1.26"),
        "FILAMENT_FILAMENT_DIAMETER": fa("1.75"),
        "FILAMENT_FILAMENT_SHRINK": fa("100%"),
        "FILAMENT_FILAMENT_IS_SUPPORT": fa("0"),
        "FILAMENT_FILAMENT_SOLUBLE": fa("0"),
        "FILAMENT_FILAMENT_PRINTABLE": fa("3"),
        "FILAMENT_FILAMENT_CHANGE_LENGTH": fa("5"),
        "FILAMENT_FILAMENT_MINIMAL_PURGE_ON_WIPE_TOWER": fa("15"),
        "FILAMENT_FILAMENT_MULTI_COLOUR": ["#000000"] * N,
        "FILAMENT_FILAMENT_COLOUR_TYPE": fa("1"),
        "FILAMENT_FILAMENT_END_GCODE": ["; filament end gcode \n\n"] * N,
        "FILAMENT_FILAMENT_START_GCODE": ["; filament start gcode\n{if  (bed_temperature[current_extruder] >55)||(bed_temperature_initial_layer[current_extruder] >55)}M106 P3 S200\n{elsif(bed_temperature[current_extruder] >50)||(bed_temperature_initial_layer[current_extruder] >50)}M106 P3 S150\n{elsif(bed_temperature[current_extruder] >45)||(bed_temperature_initial_layer[current_extruder] >45)}M106 P3 S50\n{endif}\nM142 P1 R35 S40\n{if activate_air_filtration[current_extruder] && support_air_filtration}\nM106 P3 S{during_print_exhaust_fan_speed_num[current_extruder]} \n{endif}"] * N,
        "FILAMENT_FILAMENT_VELOCITY_ADAPTATION_FACTOR": fa("1"),
        "FILAMENT_FILAMENT_SCARF_GAP": fa("0%"),
        "FILAMENT_FILAMENT_SCARF_HEIGHT": fa("10%"),
        "FILAMENT_FILAMENT_SCARF_LENGTH": fa("10"),
        "FILAMENT_FILAMENT_SCARF_SEAM_TYPE": fa("none"),
        "FILAMENT_NOZZLE_TEMPERATURE_RANGE_HIGH": fa("240"),
        "FILAMENT_NOZZLE_TEMPERATURE_RANGE_LOW": fa("190"),
        "FILAMENT_HOT_PLATE_TEMP": fa(default_bed_temp),
        "FILAMENT_HOT_PLATE_TEMP_INITIAL_LAYER": fa(default_bed_temp),
        "FILAMENT_COOL_PLATE_TEMP": fa("35"),
        "FILAMENT_COOL_PLATE_TEMP_INITIAL_LAYER": fa("35"),
        "FILAMENT_ENG_PLATE_TEMP": fa("0"),
        "FILAMENT_ENG_PLATE_TEMP_INITIAL_LAYER": fa("0"),
        "FILAMENT_TEXTURED_PLATE_TEMP": fa(default_bed_temp),
        "FILAMENT_TEXTURED_PLATE_TEMP_INITIAL_LAYER": fa(default_bed_temp),
        "FILAMENT_SUPERTACK_PLATE_TEMP": fa("45"),
        "FILAMENT_SUPERTACK_PLATE_TEMP_INITIAL_LAYER": fa("45"),
        "FILAMENT_ACTIVATE_AIR_FILTRATION": ["0"] * N,
        "FILAMENT_ADDITIONAL_COOLING_FAN_SPEED": fa("70"),
        "FILAMENT_CHAMBER_TEMPERATURES": fa("0"),
        "FILAMENT_CLOSE_FAN_THE_FIRST_X_LAYERS": fa("1"),
        "FILAMENT_DEFAULT_FILAMENT_COLOUR": [""] * N,
        "FILAMENT_DURING_PRINT_EXHAUST_FAN_SPEED": fa("70"),
        "FILAMENT_FAN_COOLING_LAYER_TIME": fa("100"),
        "FILAMENT_FAN_MAX_SPEED": fa("100"),
        "FILAMENT_FAN_MIN_SPEED": fa("100"),
        "FILAMENT_FIRST_X_LAYER_FAN_SPEED": fa("0"),
        "FILAMENT_FULL_FAN_SPEED_LAYER": fa("0"),
        "FILAMENT_IMPACT_STRENGTH_Z": fa("13.8"),
        "FILAMENT_NO_SLOW_DOWN_FOR_COOLING_ON_OUTWALLS": fa("0"),
        "FILAMENT_OVERHANG_FAN_SPEED": fa("100"),
        "FILAMENT_OVERHANG_FAN_THRESHOLD": fa("50%"),
        "FILAMENT_OVERHANG_THRESHOLD_PARTICIPATING_COOLING": fa("95%"),
        "FILAMENT_PRE_START_FAN_TIME": fa("0"),
        "FILAMENT_REDUCE_FAN_STOP_START_FREQ": fa("1"),
        "FILAMENT_REQUIRED_NOZZLE_HRC": fa("3"),
        "FILAMENT_SLOW_DOWN_FOR_LAYER_COOLING": fa("1"),
        "FILAMENT_SLOW_DOWN_LAYER_TIME": fa("4"),
        "FILAMENT_SLOW_DOWN_MIN_SPEED": fa("20"),
        "FILAMENT_TEMPERATURE_VITRIFICATION": fa("45"),
        # --- Per-extruder arrays (size 2*N) ---
        "FILAMENT_NY_FILAMENT_SELF_INDEX": list(range(N)) * 2,
        "FILAMENT_NY_FILAMENT_EXTRUDER_VARIANT": ["Direct Drive Standard", "Direct Drive High Flow"] * N,
        "FILAMENT_NY_NOZZLE_TEMPERATURE": fa(default_pla_temp, 2 * N),
        "FILAMENT_NY_NOZZLE_TEMPERATURE_INITIAL_LAYER": fa(default_pla_temp, 2 * N),
        "FILAMENT_NY_FILAMENT_FLOW_RATIO": fa("0.98", 2 * N),
        "FILAMENT_NY_FILAMENT_MAX_VOLUMETRIC_SPEED": fa("21", 2 * N),
        "FILAMENT_NY_FILAMENT_FLUSH_TEMP": fa("0", 2 * N),
        "FILAMENT_NY_FILAMENT_FLUSH_VOLUMETRIC_SPEED": fa("0", 2 * N),
        "FILAMENT_NY_FILAMENT_LONG_RETRACTIONS_WHEN_CUT": fa("1", 2 * N),
        "FILAMENT_NY_FILAMENT_RETRACTION_DISTANCES_WHEN_CUT": fa("18", 2 * N),
        "FILAMENT_NY_FILAMENT_PRE_COOLING_TEMPERATURE": fa("0", 2 * N),
        "FILAMENT_NY_FILAMENT_RAMMING_VOLUMETRIC_SPEED": fa("-1", 2 * N),
        "FILAMENT_NY_FILAMENT_RAMMING_TRAVEL_TIME": fa("0", 2 * N),
        "FILAMENT_NY_FILAMENT_ADAPTIVE_VOLUMETRIC_SPEED": fa("0", 2 * N),
        "FILAMENT_NY_FILAMENT_DERETRACTION_SPEED": nil8,
        "FILAMENT_NY_FILAMENT_RETRACT_BEFORE_WIPE": nil8,
        "FILAMENT_NY_FILAMENT_RETRACT_RESTART_EXTRA": nil8,
        "FILAMENT_NY_FILAMENT_RETRACT_WHEN_CHANGING_LAYER": nil8,
        "FILAMENT_NY_FILAMENT_RETRACTION_LENGTH": nil8,
        "FILAMENT_NY_FILAMENT_RETRACTION_MINIMUM_TRAVEL": nil8,
        "FILAMENT_NY_FILAMENT_RETRACTION_SPEED": nil8,
        "FILAMENT_NY_FILAMENT_WIPE": nil8,
        "FILAMENT_NY_FILAMENT_WIPE_DISTANCE": nil8,
        "FILAMENT_NY_FILAMENT_Z_HOP": nil8,
        "FILAMENT_NY_FILAMENT_Z_HOP_TYPES": nil8,
        "FILAMENT_NY_LONG_RETRACTIONS_WHEN_EC": fa("0", 2 * N),
        "FILAMENT_NY_RETRACTION_DISTANCES_WHEN_EC": fa("0", 2 * N),
        "FILAMENT_NY_VOLUMETRIC_SPEED_COEFFICIENTS": ["0 0 0 0 0 0"] * (2 * N),
    }


def _get_base_3mf_path():
    """Locate or copy the official Bambu Studio base 3MF for multi-color export.

    Uses the confirmed-working 'test_minimal_swap.3mf' (single-color, opens correctly
    in Bambu Studio) as the base structure. Copies it to templates/bambu/base.3mf
    on first call so it's stable across sessions.
    """
    tpl_dir = _resolve_template_dir()
    base_path = os.path.join(tpl_dir, "base.3mf")
    if not os.path.exists(base_path):
        src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "output", "test_minimal_swap.3mf")
        if os.path.exists(src):
            import shutil
            shutil.copy2(src, base_path)
    if not os.path.exists(base_path):
        raise FileNotFoundError(
            f"Base 3MF not found at {base_path} or {src}. "
            "Run pipeline once to generate test_minimal_swap.3mf first.")
    return base_path


def _export_3mf(out_path, stl_path, bands, phys_w, phys_h, total_mm,
                base_name, printer="P1S", layer_height_mm=0.2):
    """Export a 3MF file with full Bambu Studio multi-color configuration.

    Uses the official Bambu Studio base structure (Auxiliaries/, proper metadata,
    thumbnails) and only replaces: the mesh (object_2.model), model_settings.config
    (face_count), and adds custom_gcode_per_layer.xml (MultiAsSingle filament changes).
    """
    import zipfile, random

    tpl_dir = _resolve_template_dir()
    profile = _load_profile(printer, tpl_dir)

    # Load G-code templates
    gcode_files = {
        "MACHINE_START_GCODE": "machine_start_gcode.gcode",
        "MACHINE_END_GCODE": "machine_end_gcode.gcode",
        "LAYER_CHANGE_GCODE": "layer_change_gcode.gcode",
        "CHANGE_FILAMENT_GCODE": "change_filament_gcode.gcode",
    }
    gcode_args = {}
    for gvar, gfile in gcode_files.items():
        gcode_args[gvar] = _load_template(printer, gfile, tpl_dir)

    # --- Read mesh data using trimesh (handles all STL formats + vertex dedup) ---
    mesh = trimesh.load(stl_path, force='mesh')
    verts_arr = np.asarray(mesh.vertices, dtype=np.float64)
    faces_arr = np.asarray(mesh.faces, dtype=np.int32)
    face_count = len(faces_arr)
    xml_mesh_bytes = _build_xml_mesh(verts_arr, faces_arr, obj_id=1)

    # --- Compute dynamic values ---
    N = len(bands)
    sorted_bands = sorted(bands, key=lambda b: b["order"])

    # Flush volumes matrix (NxN, diagonal=0, off-diagonal=280)
    flush_default = 280
    flush_matrix = [[0 if i == j else flush_default for j in range(N)] for i in range(N)]

    # Flush volumes vector (N entries, 140 each)
    flush_vector = [140] * N

    # Filament map: "1 1 1 1" for N=4 (single extruder, all mapped to slot 1)
    filament_map_str = " ".join(["1"] * N)

    # Wipe tower position (60mm from right, 40mm from top)
    bed_x = profile.get("bed_size_x", 256)
    bed_y = profile.get("bed_size_y", 256)
    wipe_tower_x = str(bed_x - 60)
    wipe_tower_y = str(bed_y - 40)

    # Inherits group
    inherits = [profile.get("default_print_profile", "0.20mm Standard @BBL X1C")] + [""] * 5

    # Print settings
    print_settings_id = f"{layer_height_mm:.2f}mm Layered Relief"
    now = time.strftime("%Y-%m-%d")
    bed_z = str(profile.get("bed_size_z", 250))
    nozzle_volume = str(profile.get("nozzle_volume", "107"))
    ecr = str(profile.get("extruder_clearance_max_radius", "68"))
    ecr_h = str(profile.get("extruder_clearance_height_to_rod", "34"))
    ecr_l = str(profile.get("extruder_clearance_height_to_lid", "90"))

    # Build defaults for N filaments, then override with computed values
    vars = {}
    vars.update(_build_defaults(N, profile))
    vars.update(gcode_args)
    vars.update({
        # Printer info
        "PRINTER_MODEL": profile["printer_model"],
        "PRINTER_SETTINGS_ID": profile["printer_settings_id"],
        "PRINTER_STRUCTURE": profile.get("printer_structure", "corexy"),
        "PRINTER_VARIANT": profile["printer_variant"],
        "PRINTER_TECHNOLOGY": profile.get("printer_technology", "FFF"),
        # Bed
        "BED_SIZE_X": str(bed_x),
        "BED_SIZE_Y": str(bed_y),
        "BED_SIZE_Z": bed_z,
        # Clearances
        "EXTRUDER_CLEARANCE_MAX_RADIUS": ecr,
        "EXTRUDER_CLEARANCE_HEIGHT_TO_ROD": ecr_h,
        "EXTRUDER_CLEARANCE_HEIGHT_TO_LID": ecr_l,
        # Nozzle
        "NOZZLE_VOLUME": nozzle_volume,
        # Profiles
        "DEFAULT_PRINT_PROFILE": profile.get("default_print_profile", "0.20mm Standard @BBL X1C"),
        "DEFAULT_FILAMENT_PROFILE": profile.get("default_filament_profile", "Bambu PLA Basic @BBL X1C"),
        "INHERITS_GROUP": inherits,
        "COMPATIBLE_PRINTERS": profile.get("compatible_printers", ["Bambu Lab P1S 0.4 nozzle"]),
        "PRINT_SETTINGS_ID": print_settings_id,
        # Filament colors (from k-means palette) — override defaults
        "FILAMENT_FILAMENT_COLOUR": [b["color_hex"].upper() for b in sorted_bands],
        "FILAMENT_FILAMENT_MULTI_COLOUR": [b["color_hex"].upper() for b in sorted_bands],
        # Flush
        "FLUSH_VOLUMES_MATRIX": flush_matrix,
        "FLUSH_VOLUMES_VECTOR": flush_vector,
        # Mapping
        "FILAMENT_MAP": filament_map_str,
        # Wipe tower
        "WIPE_TOWER_X": wipe_tower_x,
        "WIPE_TOWER_Y": wipe_tower_y,
        # Print quality
        "LAYER_HEIGHT": f"{layer_height_mm:.2f}",
        "INITIAL_LAYER_PRINT_HEIGHT": f"{max(0.08, layer_height_mm):.2f}",
        "SPARSE_INFILL_DENSITY": "100%",
        "WALL_LOOPS": "2",
        "TOP_SHELL_LAYERS": "5",
        "BOTTOM_SHELL_LAYERS": "3",
        "TOP_SHELL_THICKNESS": "0.6",
        # Date
        "CREATION_DATE": now,
    })

    # --- Use official base 3MF (with Auxiliaries/thumbnails) ---
    base_path = _get_base_3mf_path()
    base_3mf = zipfile.ZipFile(base_path, 'r')

    # Get base model_settings as template (preserve official structure/fields)
    base_model_settings = base_3mf.read('Metadata/model_settings.config').decode('utf-8')

    # Update face_count in base model_settings
    model_settings = base_model_settings.replace(
        'face_count="640032"', f'face_count="{face_count}"', 1)
    model_settings = model_settings.replace(
        'mesh_stat face_count="640032"', f'mesh_stat face_count="{face_count}"', 1)
    # Update name in part metadata
    model_settings = model_settings.replace(
        'value="鬼灭_Front_84x150.stl"', f'value="{base_name}.stl"', 1)

    # --- Build custom_gcode_per_layer.xml ---
    # MultiAsSingle: at each band's z_end, switch to the NEXT extruder.
    # Extruder 1 is active by default at Z=0; last band needs no event.
    layer_events = []
    for b in sorted_bands[:-1]:
        next_extruder = b["order"] + 1
        layer_events.append(
            f'  <layer top_z="{b["z_end_mm"]:.2f}" type="2" '
            f'extruder="{next_extruder}" color="{b["color_hex"].upper()}" '
            f'extra="" gcode="tool_change"/>'
        )
    gcode_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<custom_gcodes_per_layer>\n'
        ' <plate>\n'
        '  <plate_info id="1"/>\n'
        + "\n".join(layer_events) + "\n"
        '  <mode value="MultiAsSingle"/>\n'
        ' </plate>\n'
        '</custom_gcodes_per_layer>'
    )

    # --- Build project_settings.config ---
    ps_template = _load_template(printer, "project_settings.template", tpl_dir)
    project_settings = _resolve_template_json(ps_template, vars)

    # --- Write ZIP using base structure ---
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for item in base_3mf.infolist():
            if item.filename == '3D/Objects/object_2.model':
                # Replace mesh with our XML mesh
                zf.writestr(item.filename, xml_mesh_bytes)
            elif item.filename == 'Metadata/model_settings.config':
                # Updated face_count + name
                zf.writestr(item.filename, model_settings.encode('utf-8'))
            elif item.filename == 'Metadata/custom_gcode_per_layer.xml':
                # MultiAsSingle filament change events
                zf.writestr(item.filename, gcode_xml.encode('utf-8'))
            elif item.filename == 'Metadata/project_settings.config':
                # Filament colors + flush volumes
                zf.writestr(item.filename, project_settings.encode('utf-8'))
            elif item.filename == 'Metadata/filament_sequence.json':
                # Skip (official base doesn't have this)
                pass
            else:
                # Keep base file as-is (includes Auxiliaries/, slice_info, etc.)
                zf.writestr(item.filename, base_3mf.read(item.filename))
    base_3mf.close()


# ═══════════════════════════════════════════════════════════════════
#  Main pipeline
# ═══════════════════════════════════════════════════════════════════

def image_to_layered_relief(image_path, width_mm=160.0, height_mm=120.0,
                            num_colors=4, layer_height_mm=0.4,
                            base_thickness_mm=0.3, edge_smooth=0.5,
                            output_format="stl", pixel_spacing_mm=0.08,
                            printer="P1S", multi_color_mode="both"):
    log = []

    if not os.path.exists(image_path):
        return {"error": f"Image not found: {image_path}"}
    if num_colors < 2:
        return {"error": "Need at least 2 colours"}
    if num_colors > 16:
        return {"error": "Too many colours (max 16)"}

    base = os.path.splitext(os.path.basename(image_path))[0]
    img_dir = os.path.dirname(os.path.abspath(image_path))
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.normpath(img_dir) == os.path.normpath(project_root):
        out_dir = os.path.join(project_root, "output", "layered_relief")
    else:
        out_dir = os.path.join(img_dir, "layered_relief")
    os.makedirs(out_dir, exist_ok=True)

    # Stage 1 — Load & preprocess
    _emit("progress", {"percent": 5, "message": "Loading image..."})
    gray, rgb, phys_w, phys_h, pw, ph = _load_and_preprocess(
        image_path, width_mm, height_mm, pixel_spacing_mm)
    log.append(f"Image: {pw}×{ph} px, physical: {phys_w:.1f}×{phys_h:.1f} mm")

    # Stage 2 — Colour quantisation
    _emit("progress", {"percent": 15, "message": f"Quantizing to {num_colors} colours..."})
    t0 = time.time()
    labels, palette = _quantize_colors(rgb, num_colors)
    log.append(f"Quantized to {num_colors} colours in {time.time()-t0:.1f}s")

    # Preview image
    preview_path = os.path.join(out_dir, f"{base}_color_preview.png")
    _export_preview(labels, palette, preview_path)
    _emit("preview", {"path": preview_path, "filename": os.path.basename(preview_path)})
    log.append(f"Preview: {preview_path}")

    # Stage 3 — Sort colours by luminance (dark→bright)
    _emit("progress", {"percent": 30, "message": "Sorting colours by luminance..."})
    sorted_indices = _sort_by_luminance(labels, palette, gray)
    log.append("Layer order (bottom→top, by luminance):")
    for band_order, ci in enumerate(sorted_indices):
        hex_c = "#{:02x}{:02x}{:02x}".format(*palette[ci])
        area = (labels == ci).sum() / labels.size * 100
        log.append(f"  {band_order+1}. Color {ci+1} {hex_c} — {area:.1f}% area")

    # Stage 4 — Build single height map with colour bands
    _emit("progress", {"percent": 40, "message": "Building height map..."})
    height_map, bands = _build_height_map(
        labels, palette, gray, sorted_indices,
        base_thickness_mm, layer_height_mm)
    total_mm = base_thickness_mm + num_colors * layer_height_mm
    log.append(f"Height map: {height_map.min():.2f}–{height_map.max():.2f} mm (total: {total_mm:.2f} mm)")

    # Stage 5 — Build watertight mesh
    _emit("progress", {"percent": 55, "message": "Building mesh..."})
    verts, faces = _build_relief_mesh(height_map, phys_w, phys_h, base_thickness_mm,
                         pixel_spacing_mm=pixel_spacing_mm)
    log.append(f"Mesh: {len(verts)} vertices, {len(faces)} faces")

    # Stage 6 — Decimate if needed
    _emit("progress", {"percent": 65, "message": "Optimizing mesh..."})
    try:
        import trimesh
        tm = trimesh.Trimesh(verts, faces)
        target_faces = min(250000, len(faces) // 3)
        if len(faces) > target_faces:
            tm = tm.simplify_quadric_decimation(face_count=target_faces)
            verts = np.array(tm.vertices, dtype=np.float32)
            faces = np.array(tm.faces, dtype=np.int32)
            # Ensure watertight after decimation
            if not tm.is_watertight:
                tm.process(validate=True)
                if not tm.is_watertight:
                    tm.fill_holes()
                verts = np.array(tm.vertices, dtype=np.float32)
                faces = np.array(tm.faces, dtype=np.int32)
            log.append(f"After decimation: {len(verts)} vertices, {len(faces)} faces")
    except Exception as e:
        log.append(f"Decimation skipped: {e}")

    # Stage 7 — Export STL
    _emit("progress", {"percent": 80, "message": "Exporting STL..."})
    stl_name = f"{base}_{num_colors}color.stl"
    stl_path = os.path.join(out_dir, stl_name)
    t0 = time.time()
    _export_stl(verts, faces, stl_path)
    stl_mb = os.path.getsize(stl_path) / 1024**2
    log.append(f"STL: {stl_name} ({len(verts)} verts, {len(faces)} faces, {stl_mb:.1f} MB) — {time.time()-t0:.1f}s")

    # Stage 8 — Colour map & optional color_config
    _emit("progress", {"percent": 90, "message": "Writing colour map..."})
    map_path = os.path.join(out_dir, f"{base}_color_map.json")
    color_map = _export_color_map(
        map_path, bands, phys_w, phys_h,
        base_thickness_mm, layer_height_mm, total_mm, stl_name)
    log.append(f"Colour map: {map_path}")

    color_config_path = None
    if multi_color_mode in ("manual", "both"):
        _, color_config = _build_color_config(
            bands, phys_w, phys_h, total_mm,
            base_thickness_mm, layer_height_mm, stl_name,
            printer, out_dir, base)
        color_config_path = os.path.join(out_dir, f"{base}_color_config.json")
        log.append(f"Color config: {color_config_path}")

    # Build result
    result = {
        "preview": preview_path,
        "output": stl_path,
        "color_map": map_path,
        "num_colors": num_colors,
        "width_mm": round(phys_w, 1),
        "height_mm": round(phys_h, 1),
        "base_thickness_mm": base_thickness_mm,
        "band_height_mm": layer_height_mm,
        "total_relief_mm": round(total_mm, 2),
        "vertices": int(len(verts)),
        "faces": int(len(faces)),
        "bands": bands,
        "log": log,
    }
    if color_config_path:
        result["color_config"] = color_config_path

    # Stage 9 — 3MF export (if requested)
    if output_format == "3mf" and multi_color_mode in ("auto", "both"):
        _emit("progress", {"percent": 95, "message": "Exporting 3MF..."})
        mf_path = os.path.join(out_dir, f"{base}_{num_colors}color.3mf")
        try:
            _export_3mf(mf_path, stl_path, bands, phys_w, phys_h, total_mm, base,
                         printer=printer, layer_height_mm=layer_height_mm)
            mf_mb = os.path.getsize(mf_path) / 1024**2
            log.append(f"3MF: {mf_path} ({mf_mb:.1f} MB)")
            result["output_3mf"] = mf_path
        except Exception as e:
            log.append(f"3MF export failed: {e}")

    _emit("progress", {"percent": 100, "message": "Done"})
    return result


# ═══════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Single-mesh multi-colour relief via height banding")
    parser.add_argument("image", help="Input image path")
    parser.add_argument("--width", type=float, default=160.0,
                        help="Target width in mm (default: 160)")
    parser.add_argument("--height", type=float, default=120.0,
                        help="Target height in mm (default: 120)")
    parser.add_argument("--colors", type=int, default=4,
                        help="Number of colours (default: 4)")
    parser.add_argument("--layer-height", type=float, default=0.4,
                        help="Height band per colour in mm (default: 0.4)")
    parser.add_argument("--base-thickness", type=float, default=0.3,
                        help="Base plate thickness in mm (default: 0.3)")
    parser.add_argument("--edge-smooth", type=float, default=0.5,
                        help="Edge smoothing strength 0-1 (default: 0.5)")
    parser.add_argument("--pixel-spacing", type=float, default=0.08,
                        help="Pixel spacing in mm (default: 0.08)")
    parser.add_argument("--format", type=str, default="stl", choices=["stl", "3mf"],
                        help="Output format: stl or 3mf (default: stl)")
    parser.add_argument("--printer", type=str, default="P1S",
                        choices=["P1S", "A1"],
                        help="Bambu printer model for 3MF config (default: P1S)")
    parser.add_argument("--multi-color-mode", type=str, default="both",
                        choices=["auto", "manual", "both"],
                        help="Multi-color strategy: auto=full 3MF (no manual setup), "
                             "manual=3MF + color_config.json (human-guided), "
                             "both=generate both (default: both)")
    args = parser.parse_args()

    # Print input params for the scheduler to log
    print(json.dumps({
        "width_mm": args.width,
        "height_mm": args.height,
        "colors": args.colors,
        "layer_height_mm": args.layer_height,
        "base_thickness_mm": args.base_thickness,
        "format": args.format,
        "printer": args.printer,
    }, indent=2))

    result = image_to_layered_relief(
        args.image,
        width_mm=args.width,
        height_mm=args.height,
        num_colors=args.colors,
        layer_height_mm=args.layer_height,
        base_thickness_mm=args.base_thickness,
        edge_smooth=args.edge_smooth,
        output_format=args.format,
        pixel_spacing_mm=args.pixel_spacing,
        printer=args.printer,
        multi_color_mode=args.multi_color_mode,
    )

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
