"""inline_nodes.py — PIL-based image processing nodes executed directly in engine."""
import os
import uuid
from PIL import Image, ImageEnhance, ImageOps, ImageFilter


def _resolve_input_file(nid, node_params, ctx, engine):
    """Find the upstream input image file for an inline node."""
    # Check context outputs
    outputs = ctx.get(str(nid), {})
    for key in ("image", "file", "stl", "mesh", "color_preview"):
        if key in outputs and isinstance(outputs[key], str):
            path = outputs[key]
            if os.path.isfile(path):
                return path

    # Try edge map resolution
    port_edge_map = engine._build_port_edge_map(
        {str(n["id"]): n for n in []},  # will be built by engine before calling
        []  # placeholder
    )

    # Fallback: scan all context keys for file paths
    for src_nid, src_outputs in ctx.items():
        if src_nid.startswith("_"):
            continue
        if isinstance(src_outputs, dict):
            for port, path in src_outputs.items():
                if isinstance(path, str) and os.path.isfile(path) and port in ("image", "file"):
                    return path
    return None


def _resolve_input(nid, ctx, engine, node_map, edges):
    """Resolve input image from upstream node via port edge map."""
    # Use engine's port edge map
    port_edge_map = engine._build_port_edge_map(node_map, edges)
    edge_key = (str(nid), "image")
    if edge_key in port_edge_map:
        src_nid, src_port = port_edge_map[edge_key]
        src_outputs = ctx.get(str(src_nid), {})
        path = src_outputs.get(src_port, "")
        if isinstance(path, str) and os.path.isfile(path):
            return path

    # Try any file port
    edge_key_file = (str(nid), "file")
    if edge_key_file in port_edge_map:
        src_nid, src_port = port_edge_map[edge_key_file]
        src_outputs = ctx.get(str(src_nid), {})
        path = src_outputs.get(src_port, "")
        if isinstance(path, str) and os.path.isfile(path):
            return path

    return None


def _output_path(work_dir, suffix=".png"):
    """Generate an output file path in work_dir."""
    return os.path.join(work_dir, f"inline_{uuid.uuid4().hex[:8]}{suffix}")


def _safe_open(path):
    """Open an image, handling RGBA/P modes."""
    img = Image.open(path)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGBA")
    elif img.mode != "RGB" and img.mode != "L":
        img = img.convert("RGB")
    return img


# ═══════════════════════════════════════════
#  Image Resize
# ═══════════════════════════════════════════

async def run_image_resize(nid, node, node_params, ctx, instance_id, node_run_id, engine, node_map, edges):
    input_path = _resolve_input(nid, ctx, engine, node_map, edges)
    if not input_path:
        raise ValueError("Image resize: no input image found")

    width = int(node_params.get("width", 512))
    height = int(node_params.get("height", 512))
    fit = node_params.get("fit", "cover")
    filter_name = node_params.get("filter", "lanczos")

    filter_map = {"lanczos": Image.Resampling.LANCZOS, "bilinear": Image.Resampling.BILINEAR,
                  "bicubic": Image.Resampling.BICUBIC, "nearest": Image.Resampling.NEAREST}
    resample = filter_map.get(filter_name, Image.Resampling.LANCZOS)

    img = _safe_open(input_path)

    if fit == "cover":
        img = ImageOps.fit(img, (width, height), method=resample)
    elif fit == "contain":
        img = ImageOps.contain(img, (width, height), method=resample)
    elif fit == "stretch":
        img = img.resize((width, height), resample)
    elif fit == "scale_width":
        ratio = width / img.width
        new_h = int(img.height * ratio)
        img = img.resize((width, new_h), resample)
    elif fit == "scale_height":
        ratio = height / img.height
        new_w = int(img.width * ratio)
        img = img.resize((new_w, height), resample)
    else:
        img = img.resize((width, height), resample)

    # Convert RGBA to RGB for JPEG/PNG-safe output
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    work_dir = ctx.get("_work_dir", "")
    out_path = _output_path(work_dir, ".png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, "PNG")

    ctx[str(nid)] = {"image": out_path}
    return out_path


# ═══════════════════════════════════════════
#  Grayscale
# ═══════════════════════════════════════════

async def run_image_grayscale(nid, node, node_params, ctx, instance_id, node_run_id, engine, node_map, edges):
    input_path = _resolve_input(nid, ctx, engine, node_map, edges)
    if not input_path:
        raise ValueError("Grayscale: no input image found")

    method = node_params.get("method", "luminosity")
    img = Image.open(input_path)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGBA")

    if method == "luminosity":
        # Standard luminosity: 0.299 R + 0.587 G + 0.114 B
        gray = img.convert("L")
    elif method == "average":
        gray = ImageOps.grayscale(img)
    elif method == "lightness":
        if img.mode == "RGBA":
            img = img.convert("RGB")
        arr = img.split()
        gray = Image.fromarray(
            (sum(a for a in arr[:3]) / 3).astype("uint8"), mode="L"
        ) if len(arr) >= 3 else img.convert("L")
    elif method in ("red_channel", "green_channel", "blue_channel"):
        ch = {"red_channel": 0, "green_channel": 1, "blue_channel": 2}[method]
        if img.mode == "RGBA":
            img = img.convert("RGB")
        gray = img.split()[ch]
    else:
        gray = img.convert("L")

    work_dir = ctx.get("_work_dir", "")
    out_path = _output_path(work_dir, ".png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    gray.save(out_path, "PNG")

    ctx[str(nid)] = {"image": out_path}
    return out_path


# ═══════════════════════════════════════════
#  Image Crop
# ═══════════════════════════════════════════

async def run_image_crop(nid, node, node_params, ctx, instance_id, node_run_id, engine, node_map, edges):
    input_path = _resolve_input(nid, ctx, engine, node_map, edges)
    if not input_path:
        raise ValueError("Crop: no input image found")

    img = _safe_open(input_path)
    iw, ih = img.size

    x = int(node_params.get("x", 0))
    y = int(node_params.get("y", 0))
    w = int(node_params.get("width", min(512, iw)))
    h = int(node_params.get("height", min(512, ih)))
    aspect = node_params.get("aspect_ratio", "free")

    # Apply aspect ratio constraint
    if aspect != "free":
        ratio_map = {"1:1": 1, "4:3": 4/3, "3:4": 3/4, "16:9": 16/9, "9:16": 9/16, "3:2": 3/2, "2:3": 2/3}
        target_ratio = ratio_map.get(aspect, 1)
        if w / h > target_ratio:
            w = int(h * target_ratio)
        else:
            h = int(w / target_ratio)

    # Clamp to image bounds
    x = max(0, min(x, iw - 1))
    y = max(0, min(y, ih - 1))
    w = max(1, min(w, iw - x))
    h = max(1, min(h, ih - y))

    cropped = img.crop((x, y, x + w, y + h))

    if cropped.mode == "RGBA":
        bg = Image.new("RGB", cropped.size, (255, 255, 255))
        bg.paste(cropped, mask=cropped.split()[3])
        cropped = bg

    work_dir = ctx.get("_work_dir", "")
    out_path = _output_path(work_dir, ".png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cropped.save(out_path, "PNG")

    ctx[str(nid)] = {"image": out_path}
    return out_path


# ═══════════════════════════════════════════
#  Image Adjust (brightness, contrast, saturation, sharpness)
# ═══════════════════════════════════════════

async def run_image_adjust(nid, node, node_params, ctx, instance_id, node_run_id, engine, node_map, edges):
    input_path = _resolve_input(nid, ctx, engine, node_map, edges)
    if not input_path:
        raise ValueError("Adjust: no input image found")

    brightness = float(node_params.get("brightness", 0.0))
    contrast = float(node_params.get("contrast", 1.0))
    saturation = float(node_params.get("saturation", 1.0))
    sharpness = float(node_params.get("sharpness", 0.0))

    img = _safe_open(input_path)

    if brightness != 0.0:
        img = ImageEnhance.Brightness(img).enhance(1.0 + brightness)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(saturation)
    if sharpness > 0.0:
        img = ImageEnhance.Sharpness(img).enhance(1.0 + sharpness)

    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    work_dir = ctx.get("_work_dir", "")
    out_path = _output_path(work_dir, ".png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, "PNG")

    ctx[str(nid)] = {"image": out_path}
    return out_path


# ═══════════════════════════════════════════
#  Format Convert
# ═══════════════════════════════════════════

async def run_image_convert(nid, node, node_params, ctx, instance_id, node_run_id, engine, node_map, edges):
    input_path = _resolve_input(nid, ctx, engine, node_map, edges)
    if not input_path:
        raise ValueError("Convert: no input image found")

    fmt = node_params.get("format", "png")
    quality = int(node_params.get("quality", 95))
    optimize = node_params.get("optimize", True)

    img = _safe_open(input_path)
    ext_map = {"png": ".png", "jpeg": ".jpg", "webp": ".webp", "bmp": ".bmp", "tiff": ".tif"}
    ext = ext_map.get(fmt, "." + fmt)

    work_dir = ctx.get("_work_dir", "")
    out_path = _output_path(work_dir, ext)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    save_kwargs = {"format": fmt.upper(), "optimize": optimize}
    if fmt in ("jpeg", "webp"):
        save_kwargs["quality"] = quality

    # Convert RGBA to RGB for formats that don't support alpha
    if img.mode == "RGBA" and fmt in ("jpeg", "bmp"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg

    img.save(out_path, **save_kwargs)

    ctx[str(nid)] = {"image": out_path}
    return out_path


# ═══════════════════════════════════════════
#  Remove Background (rembg)
# ═══════════════════════════════════════════

async def run_remove_background(nid, node, node_params, ctx, instance_id, node_run_id, engine, node_map, edges):
    input_path = _resolve_input(nid, ctx, engine, node_map, edges)
    if not input_path:
        raise ValueError("Remove BG: no input image found")

    try:
        from rembg import remove, new_session
    except ImportError:
        raise RuntimeError("rembg package not installed. Run: pip install rembg")

    model_name = node_params.get("model", "u2net")
    alpha_matting = node_params.get("alpha_matting", False)
    bg_color = str(node_params.get("bg_color", ""))

    img = Image.open(input_path).convert("RGBA")

    session = new_session(model_name)
    result = remove(
        img,
        session=session,
        alpha_matting=alpha_matting,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
        alpha_matting_erode_size=10,
    )

    # Replace transparent background with solid color if requested
    if bg_color:
        bg = Image.new("RGBA", result.size, bg_color)
        bg.paste(result, mask=result.split()[3])
        result = bg

    work_dir = ctx.get("_work_dir", "")
    out_path = _output_path(work_dir, ".png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    result.save(out_path, "PNG")

    ctx[str(nid)] = {"image": out_path}
    return out_path


# ═══════════════════════════════════════════
#  Mesh Inline Handlers
# ═══════════════════════════════════════════

async def run_mesh_transform(nid, node, node_params, ctx, instance_id, node_run_id, engine, node_map, edges):
    """Transform mesh: translate, rotate, scale."""
    import numpy as np
    import trimesh

    input_file = _resolve_input(nid, ctx, engine, node_map, edges)
    if not input_file:
        raise ValueError(f"mesh_transform: no input mesh for node {nid}")

    mesh = trimesh.load(input_file, force="mesh")
    if isinstance(mesh, trimesh.Scene):
        meshes = [m for m in mesh.geometry.values() if hasattr(m, "vertices")]
        mesh = max(meshes, key=lambda m: len(m.vertices)) if meshes else None

    # Parse transform params
    translate_str = node_params.get("tf_translate", "0,0,0")
    rotate_str = node_params.get("tf_rotate", "0,0,1")
    scale_val = float(node_params.get("tf_scale", 1.0))

    translate = [float(x) for x in translate_str.split(",")][:3]
    rotate_angle = float(node_params.get("tf_rotate_angle", 0))
    if "tf_rotate" in node_params:
        # rotate is expressed as angle,axis format
        parts = node_params.get("tf_rotate", "0,0,1").split(",")
        if len(parts) >= 4:
            rotate_angle = float(parts[0])
            axis = np.array([float(parts[1]), float(parts[2]), float(parts[3])])
            axis = axis / np.linalg.norm(axis)
        else:
            rotate_angle = 0
            axis = np.array([0, 0, 1])
    else:
        axis = np.array([0, 0, 1])

    work_dir = ctx.get("_work_dir", "")
    os.makedirs(work_dir, exist_ok=True)

    # Apply translate
    if any(t != 0 for t in translate):
        mesh.apply_translation(translate)

    # Apply rotation
    if rotate_angle != 0:
        angle_rad = np.radians(rotate_angle)
        K = np.array([
            [0, -axis[2], axis[1]],
            [axis[2], 0, -axis[0]],
            [-axis[1], axis[0], 0]
        ])
        R = np.eye(3) + np.sin(angle_rad) * K + (1 - np.cos(angle_rad)) * (K @ K)
        mesh.apply_transform(np.column_stack([R, [0, 0, 0]]).ravel().tolist() + [0, 0, 0, 1])

    # Apply scale
    if scale_val != 1.0:
        mesh.apply_scale(scale_val)

    out_path = os.path.join(work_dir, f"mesh_tf_{nid}.glb")
    mesh.export(out_path)

    ctx[str(nid)] = {"mesh": out_path}
    return out_path


async def run_mesh_select(nid, node, node_params, ctx, instance_id, node_run_id, engine, node_map, edges):
    """Select mesh region by bounding box."""
    import numpy as np
    import trimesh

    input_file = _resolve_input(nid, ctx, engine, node_map, edges)
    if not input_file:
        raise ValueError(f"mesh_select: no input mesh for node {nid}")

    mesh = trimesh.load(input_file, force="mesh")
    if isinstance(mesh, trimesh.Scene):
        meshes = [m for m in mesh.geometry.values() if hasattr(m, "vertices")]
        mesh = max(meshes, key=lambda m: len(m.vertices)) if meshes else None

    bbox_str = node_params.get("sel_bbox", "")
    if not bbox_str:
        # No selection - pass through
        out_path = os.path.join(ctx.get("_work_dir", "."), f"mesh_sel_{nid}.glb")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        mesh.export(out_path)
        ctx[str(nid)] = {"mesh": out_path}
        return out_path

    parts = [float(x) for x in bbox_str.split(",")]
    if len(parts) != 6:
        raise ValueError(f"sel_bbox needs xmin,ymin,zmin,xmax,ymax,zmax, got: {bbox_str}")

    xmin, ymin, zmin, xmax, ymax, zmax = parts

    # Select vertices within bounding box
    v = mesh.vertices
    mask = (
        (v[:, 0] >= xmin) & (v[:, 0] <= xmax) &
        (v[:, 1] >= ymin) & (v[:, 1] <= ymax) &
        (v[:, 2] >= zmin) & (v[:, 2] <= zmax)
    )
    face_mask = np.any(mask[mesh.faces], axis=1)

    if face_mask.sum() == 0:
        raise ValueError(f"No faces in bounding box {bbox_str}")

    selected = mesh.copy()
    selected.update_faces(face_mask)
    selected.remove_unreferenced_vertices()
    selected.merge_vertices()

    work_dir = ctx.get("_work_dir", "")
    os.makedirs(work_dir, exist_ok=True)
    out_path = os.path.join(work_dir, f"mesh_sel_{nid}.glb")
    selected.export(out_path)

    ctx[str(nid)] = {"mesh": out_path}
    return out_path


# ═══════════════════════════════════════════
#  Handler Registry
# ═══════════════════════════════════════════

INLINE_HANDLERS = {
    "image_resize": run_image_resize,
    "image_grayscale": run_image_grayscale,
    "image_crop": run_image_crop,
    "image_adjust": run_image_adjust,
    "image_convert": run_image_convert,
    "remove_background": run_remove_background,
    "mesh_transform": run_mesh_transform,
    "mesh_select": run_mesh_select,
}
