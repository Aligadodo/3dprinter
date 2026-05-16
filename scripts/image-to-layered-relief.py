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
            "color_name": f"Color {band_order+1}",
            "color_rgb": rgb_c,
            "color_hex": hex_c,
            "area_ratio": round(area / (H * W), 3),
            "z_start_mm": round(base_thickness_mm + band_start, 2),
            "z_end_mm": round(base_thickness_mm + band_start + layer_height_mm, 2),
            "luminance_mean": float(g_vals.mean()),
        })

    return height_map, bands


# ═══════════════════════════════════════════════════════════════════
#  Watertight thin-plate mesh building
# ═══════════════════════════════════════════════════════════════════

def _build_relief_mesh(height_map, phys_w, phys_h, base_thickness_mm=0.3):
    """Build a watertight thin-plate mesh from a height field.

    Front face at z = base_thickness + height, back face at z = 0.
    Side walls close the volume.
    """
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
#  Preview & colour-map export
# ═══════════════════════════════════════════════════════════════════

def _export_preview(labels, palette, out_path):
    from PIL import Image
    H, W = labels.shape
    img_arr = np.zeros((H, W, 3), dtype=np.uint8)
    for c in range(len(palette)):
        img_arr[labels == c] = palette[c]
    Image.fromarray(img_arr).save(out_path)


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
            f"  Z {b['z_start_mm']:.1f} – {b['z_end_mm']:.1f} mm → 换 {b['color_hex']} ({b['color_name']})")
        color_map["instructions"]["en"].append(
            f"  Z {b['z_start_mm']:.1f} – {b['z_end_mm']:.1f} mm → change to {b['color_hex']} ({b['color_name']})")

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


def _export_3mf(out_path, stl_path, bands, phys_w, phys_h, total_mm,
                base_name, printer="P1S", layer_height_mm=0.2):
    """Export a 3MF file with full Bambu Studio multi-color configuration.

    Generates:
      [Content_Types].xml, _rels/.rels
      3D/3dmodel.model, 3D/_rels/3dmodel.model.rels
      3D/Objects/object.model (STL binary)
      Metadata/project_settings.config (slicer config with N filaments)
      Metadata/model_settings.config (plate + filament mapping)
      Metadata/custom_gcode_per_layer.xml (height-based filament changes)
      Metadata/cut_information.xml, Metadata/filament_sequence.json
    """
    import zipfile

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

    # --- Read STL binary ---
    with open(stl_path, 'rb') as f:
        stl_data = f.read()

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

    # Render project_settings.config
    ps_template = _load_template(printer, "project_settings.template", tpl_dir)
    project_settings = _resolve_template_json(ps_template, vars)

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

    # --- Build descriptions ---
    color_desc = ", ".join(
        f"{b['z_start_mm']:.1f}mm={b['color_hex']}" for b in sorted_bands)
    desc_text = f"{N}-color relief | {color_desc}"
    desc_html = "&lt;p&gt;" + desc_text + "&lt;/p&gt;"
    title = f"{N} color {layer_height_mm:.2f}mm"

    # --- 3D/3dmodel.model ---
    obj_uuid = "00000002-61cb-4c03-9d28-80fed5dfa1dc"
    build_uuid = "2c7c17d8-22b5-4d84-8835-1976022ea369"
    item_uuid = "00000002-b1ec-4553-aec9-835e5b724bb4"
    # Center model on bed
    tx = (bed_x - phys_w) / 2
    ty = (bed_y - phys_h) / 2

    model_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US"'
        ' xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"'
        ' xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"'
        ' xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"'
        ' requiredextensions="p">\n'
        f'  <metadata name="Application">BambuStudio-02.03.00.70</metadata>\n'
        f'  <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
        f'  <metadata name="Copyright" />\n'
        f'  <metadata name="CreationDate">{now}</metadata>\n'
        f'  <metadata name="Description">{desc_html}</metadata>\n'
        f'  <metadata name="Designer" />\n'
        f'  <metadata name="DesignerCover" />\n'
        f'  <metadata name="DesignerUserId">3178235157</metadata>\n'
        f'  <metadata name="License" />\n'
        f'  <metadata name="ModificationDate">{now}</metadata>\n'
        f'  <metadata name="Origin">original</metadata>\n'
        f'  <metadata name="Title">{base_name}</metadata>\n'
        f'  <resources>\n'
        f'   <object id="2" p:UUID="{obj_uuid}" type="model">\n'
        f'    <components>\n'
        f'     <component p:path="/3D/Objects/object.model" objectid="1"'
        f' p:UUID="00020000-b206-40ff-9872-83e8017abed1"'
        f' transform="1 0 0 0 1 0 0 0 1 0 0 0" />\n'
        f'    </components>\n'
        f'   </object>\n'
        f'  </resources>\n'
        f'  <build p:UUID="{build_uuid}">\n'
        f'   <item objectid="2" p:UUID="{item_uuid}"'
        f' transform="1 0 0 0 1 0 0 0 1 {tx:.6f} {ty:.6f} {total_mm:.6f}"'
        f' printable="1" />\n'
        f'  </build>\n'
        f'  <metadata name="CopyRight">[]</metadata>\n'
        f'  <metadata name="ProfileTitle">{title}</metadata>\n'
        f'  <metadata name="ProfileCover" />\n'
        f'  <metadata name="ProfileDescription">{desc_html}</metadata>\n'
        f'  <metadata name="ProfileUserId">3178235157</metadata>\n'
        f'  <metadata name="ProfileUserName" />\n'
        f'  <metadata name="DesignRegion">CN</metadata>\n'
        f'  <metadata name="DesignModelId">{base_name}</metadata>\n'
        f'  <metadata name="DesignProfileId">1</metadata>\n'
        f'</model>'
    )

    # --- Model settings config with filament_maps ---
    # Compute face count from STL binary (80-byte header + 4-byte triangle count)
    import struct as _struct
    face_count = _struct.unpack_from('<I', stl_data, 80)[0] if len(stl_data) > 84 else 0
    model_settings = f'''<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="2">
    <metadata key="name" value="{base_name}.stl"/>
    <metadata key="extruder" value="1"/>
    <metadata face_count="{face_count}"/>
    <part id="1" subtype="normal_part">
      <metadata key="name" value="{base_name}.stl"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
      <metadata key="source_object_id" value="0"/>
      <metadata key="source_volume_id" value="0"/>
      <metadata key="source_offset_x" value="0"/>
      <metadata key="source_offset_y" value="0"/>
      <metadata key="source_offset_z" value="0"/>
      <mesh_stat face_count="{face_count}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>
    </part>
  </object>
  <plate>
    <metadata key="plater_id" value="1"/>
    <metadata key="plater_name" value=""/>
    <metadata key="locked" value="false"/>
    <metadata key="filament_map_mode" value="Auto For Flush"/>
    <metadata key="filament_maps" value="{filament_map_str}"/>
    <metadata key="filament_volume_maps" value="{" ".join(["0"] * N)}"/>
    <metadata key="thumbnail_file" value=""/>
    <model_instance>
      <metadata key="object_id" value="2"/>
      <metadata key="instance_id" value="0"/>
      <metadata key="identify_id" value="1"/>
    </model_instance>
  </plate>
  <assemble>
    <assemble_item object_id="2" instance_id="0"
     transform="1 0 0 0 1 0 0 0 1 {tx:.6f} {ty:.6f} {total_mm:.6f}"
     offset="0 0 0"/>
  </assemble>
</config>'''

    # --- Compatibility files ---
    content_types = '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n</Types>'

    rels = '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n <Relationship Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" Target="/3D/3dmodel.model" Id="rel-1"/>\n</Relationships>'

    model_rels = '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n <Relationship Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" Target="/3D/Objects/object.model" Id="rel1"/>\n</Relationships>'

    cut_information = '<?xml version="1.0" encoding="UTF-8"?>\n<objects>\n <object id="1">\n  <cut_id id="0" check_sum="1" connectors_cnt="0"/>\n </object>\n</objects>'

    filament_sequence = '{"plate_1":{"nozzle_sequence":[],"optimal_assignment":[],"sequence":[]}}'

    # --- Write ZIP ---
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', content_types)
        zf.writestr('_rels/.rels', rels)
        zf.writestr('3D/3dmodel.model', model_xml)
        zf.writestr('3D/_rels/3dmodel.model.rels', model_rels)
        zf.writestr('3D/Objects/object.model', stl_data)
        zf.writestr('Metadata/project_settings.config', project_settings)
        zf.writestr('Metadata/model_settings.config', model_settings)
        zf.writestr('Metadata/custom_gcode_per_layer.xml', gcode_xml)
        zf.writestr('Metadata/cut_information.xml', cut_information)
        zf.writestr('Metadata/filament_sequence.json', filament_sequence)


# ═══════════════════════════════════════════════════════════════════
#  Main pipeline
# ═══════════════════════════════════════════════════════════════════

def image_to_layered_relief(image_path, width_mm=160.0, height_mm=120.0,
                            num_colors=4, layer_height_mm=0.4,
                            base_thickness_mm=0.3, edge_smooth=0.5,
                            output_format="stl", pixel_spacing_mm=0.08,
                            printer="P1S"):
    log = []

    if not os.path.exists(image_path):
        return {"error": f"Image not found: {image_path}"}
    if num_colors < 2:
        return {"error": "Need at least 2 colours"}
    if num_colors > 16:
        return {"error": "Too many colours (max 16)"}

    base = os.path.splitext(os.path.basename(image_path))[0]
    img_dir = os.path.dirname(os.path.abspath(image_path))
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
    verts, faces = _build_relief_mesh(height_map, phys_w, phys_h, base_thickness_mm)
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

    # Stage 8 — Colour map & instructions
    _emit("progress", {"percent": 90, "message": "Writing colour map..."})
    map_path = os.path.join(out_dir, f"{base}_color_map.json")
    color_map = _export_color_map(
        map_path, bands, phys_w, phys_h,
        base_thickness_mm, layer_height_mm, total_mm, stl_name)
    log.append(f"Colour map: {map_path}")

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

    # Stage 9 — 3MF export (if requested)
    if output_format == "3mf":
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
    )

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
