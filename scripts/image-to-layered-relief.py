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
#  3MF export (Bambu Studio compatible)
# ═══════════════════════════════════════════════════════════════════

def _export_3mf(out_path, stl_path, bands, phys_w, phys_h, total_mm,
                base_name):
    """Export a 3MF file with embedded STL mesh and Bambu Studio metadata.

    The 3MF format is a ZIP archive containing:
      [Content_Types].xml
      _rels/.rels
      3D/3dmodel.model       — model structure with BambuStudio namespace
      3D/Objects/object.model — the STL binary mesh
      Metadata/model_settings.config — plate & filament settings
    """
    import zipfile, io

    # Read STL binary data
    with open(stl_path, 'rb') as f:
        stl_data = f.read()

    # Build filament change description
    color_desc_parts = []
    for b in bands:
        color_desc_parts.append(
            f"{b['z_start_mm']:.2f}mm换{b['color_hex']}")
    color_desc = "，".join(color_desc_parts)
    desc_zh = f"<p>共{len(bands)}色版画 | {color_desc}</p><p>使用 Bambu Studio 打开后，在预览页面按高度范围设置耗材颜色。</p>"
    change_list = "; ".join(f"{b['z_start_mm']:.1f}mm={b['color_hex']}" for b in bands)
    desc_en = f"<p>{len(bands)}-color relief | filament changes at: {change_list}</p>"

    now = time.strftime("%Y-%m-%d")

    # [Content_Types].xml
    content_types = '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n</Types>'

    # _rels/.rels
    rels = '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n  <Relationship Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" Target="/3D/3dmodel.model" Id="rel0"/>\n</Relationships>'

    # 3D/3dmodel.model
    obj_uuid = "00000002-61cb-4c03-9d28-80fed5dfa1dc"
    build_uuid = "2c7c17d8-22b5-4d84-8835-1976022ea369"
    item_uuid = "00000002-b1ec-4553-aec9-835e5b724bb4"

    model_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
       xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
       unit="millimeter" xml:lang="en-US" requiredextensions="p"
       xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">
 <metadata name="Application">Claude-3DPrint-Pipeline</metadata>
 <metadata name="BambuStudio:3mfVersion">1</metadata>
 <metadata name="CreationDate">{now}</metadata>
 <metadata name="Description">{desc_en}</metadata>
 <metadata name="Title">{base_name}</metadata>
 <resources>
  <object id="2" p:UUID="{obj_uuid}" type="model">
   <components>
    <component p:path="/3D/Objects/object.model" objectid="1"
               p:UUID="00020000-b206-40ff-9872-83e8017abed1"
               transform="1 0 0 0 1 0 0 0 1 0 0 0"/>
   </components>
  </object>
 </resources>
 <build p:UUID="{build_uuid}">
  <item objectid="2" p:UUID="{item_uuid}"
        transform="1 0 0 0 1 0 0 0 1 0 0 0" printable="1"/>
 </build>
</model>'''

    # Metadata/model_settings.config
    model_settings = f'''<?xml version="1.0" encoding="UTF-8"?>
<config>
 <object id="2">
  <metadata key="name" value="{base_name}.stl"/>
  <part id="1" subtype="normal_part">
   <metadata key="name" value="{base_name}.stl"/>
  </part>
 </object>
 <plate>
  <metadata key="plater_id" value="1"/>
  <metadata key="plater_name" value=""/>
  <metadata key="locked" value="false"/>
  <metadata key="thumbnail_file" value=""/>
  <model_instance>
   <metadata key="object_id" value="2"/>
   <metadata key="instance_id" value="0"/>
   <metadata key="identify_id" value="1"/>
  </model_instance>
 </plate>
</config>'''

    # 3D/_rels/3dmodel.model.rels
    model_rels = '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n  <Relationship Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" Target="/3D/Objects/object.model" Id="rel1"/>\n</Relationships>'

    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', content_types)
        zf.writestr('_rels/.rels', rels)
        zf.writestr('3D/3dmodel.model', model_xml)
        zf.writestr('3D/_rels/3dmodel.model.rels', model_rels)
        zf.writestr('3D/Objects/object.model', stl_data)
        zf.writestr('Metadata/model_settings.config', model_settings)


# ═══════════════════════════════════════════════════════════════════
#  Main pipeline
# ═══════════════════════════════════════════════════════════════════

def image_to_layered_relief(image_path, width_mm=160.0, height_mm=120.0,
                            num_colors=4, layer_height_mm=0.4,
                            base_thickness_mm=0.3, edge_smooth=0.5,
                            output_format="stl", pixel_spacing_mm=0.08):
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
            _export_3mf(mf_path, stl_path, bands, phys_w, phys_h, total_mm, base)
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
    args = parser.parse_args()

    # Print input params for the scheduler to log
    print(json.dumps({
        "width_mm": args.width,
        "height_mm": args.height,
        "colors": args.colors,
        "layer_height_mm": args.layer_height,
        "base_thickness_mm": args.base_thickness,
        "format": args.format,
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
    )

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
