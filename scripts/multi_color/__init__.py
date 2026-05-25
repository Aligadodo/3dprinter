"""Multi-color 3D printing support for relief/lithophane generation.

Physical model: Beer-Lambert optical blending through stacked filament layers.
Target platform: Bambu Lab (AMS or manual filament swap), Orca Slicer.

Main entry points:
    compute_color_layers()  -- full pipeline: image → layer plan + height map
    export_3mf()            -- write Bambu-compatible .3mf with swap instructions
    calibrate_td()          -- measure filament TD from test swatches
"""

from .td_database import lookup_td, KNOWN_TD, find_closest_filaments
from .color_blending import (
    beer_lambert_blend,
    beer_lambert_transmission,
    delta_e_2000,
    generate_virtual_swatches,
)
from .layer_optimizer import optimize_layer_stack
from .height_mapper import map_colors_to_height, floyd_steinberg_dither
from .mesh_builder import build_multi_color_mesh
from .export_3mf import export_3mf
from .manga_mode import process_manga
from .flatforge import generate_flatforge

__all__ = [
    "compute_color_layers",
    "process_manga",
    "generate_flatforge",
    "lookup_td",
    "KNOWN_TD",
    "beer_lambert_blend",
    "beer_lambert_transmission",
    "delta_e_2000",
    "generate_virtual_swatches",
    "optimize_layer_stack",
    "map_colors_to_height",
    "floyd_steinberg_dither",
    "build_multi_color_mesh",
    "export_3mf",
]


def compute_color_layers(image_path, filaments=None, layer_height=0.08,
                         max_thickness_mm=3.0, base_thickness_mm=0.6,
                         pixel_spacing_mm=0.08, lithophane=False,
                         dither_strength=0.8, region_weight="uniform",
                         target_width_mm=160.0, target_height_mm=120.0,
                         num_colors=None):
    """Full multi-color pipeline: image → layer plan + height map + mesh.

    Args:
        image_path: Path to input image.
        filaments: Optional list of filament dicts with keys:
            color (hex str), td (float, optional), name (str).
            If None, num_colors is used to auto-extract from the image.
        num_colors: If filaments is None, auto-extract this many dominant
            colors from the image and map to known filaments. Default: None
            (falls back to Black+White 2-color palette).
        layer_height: mm per printed layer (default 0.08).
        max_thickness_mm: Maximum total Z thickness for color blending region.
        base_thickness_mm: Opaque base thickness beneath the blending region.
        pixel_spacing_mm: Physical mm per image pixel.
        lithophane: If True, thin=light (backlit), else thick=light (relief).
        dither_strength: Floyd-Steinberg error diffusion strength [0, 1].
        region_weight: "uniform", "center", or "edge".
        target_width_mm: Physical width of output (default 160).
        target_height_mm: Physical height of output (default 120).

    Returns:
        dict with keys: height_map, layer_plan, mesh_verts, mesh_faces,
        filament_info, swaps, total_thickness_mm, log
    """
    import time
    import json as _json
    import numpy as np
    from PIL import Image

    def _emit(stage, pct=None, message=""):
        """Emit a structured progress event to stdout (parsed by scheduler)."""
        data = {"event": "progress", "stage": stage, "message": message}
        if pct is not None:
            data["percent"] = pct
        print(_json.dumps(data, ensure_ascii=False), flush=True)

    log = []
    t0 = time.time()

    # Load image
    _emit("load", message="Loading image...")
    img = Image.open(image_path).convert("RGB")
    iw, ih = img.size
    aspect = iw / ih

    # Calculate physical dimensions
    target_w, target_h = target_width_mm, target_height_mm
    if aspect > target_w / target_h:
        phys_w = target_w
        phys_h = target_w / aspect
    else:
        phys_h = target_h
        phys_w = target_h * aspect

    pixels_w = int(phys_w / pixel_spacing_mm)
    pixels_h = int(phys_h / pixel_spacing_mm)

    _emit("load", message=f"Resizing to {pixels_w}×{pixels_h} px ({phys_w:.0f}×{phys_h:.0f} mm)")
    img_resized = img.resize((pixels_w, pixels_h), Image.LANCZOS)
    rgb = np.array(img_resized, dtype=np.float32)
    log.append(f"Image: {pixels_w}×{pixels_h} px, {phys_w:.1f}×{phys_h:.1f} mm")

    # Step 0: Auto-extract filaments from image if not explicitly provided
    if filaments is None:
        if num_colors and num_colors >= 2:
            _emit("extract_colors", message=f"Extracting {num_colors} dominant colors...")
            dominant_rgbs = _extract_dominant_colors(img, num_colors)
            filaments = find_closest_filaments(dominant_rgbs)
            log.append(f"Auto-extracted {num_colors} colors: {', '.join(f['name'] for f in filaments)}")
            _emit("extract_colors",
                  message=f"Extracted {num_colors} colors: {', '.join(f['name'] for f in filaments)}")
        else:
            filaments = [
                {"color": "#000000", "name": "Black PLA", "td": 0.6},
                {"color": "#FFFFFF", "name": "White PLA", "td": 4.4},
            ]
            log.append("Using default 2-color palette (Black + White)")

    # Step 1: Resolve TD values
    filaments = _resolve_td(filaments)
    log.append(f"Filaments: {len(filaments)} colors")

    # Step 2: Optimize layer stacking order
    _emit("optimize_order", message=f"Optimizing stacking order for {len(filaments)} filaments...")
    order_result = optimize_layer_stack(
        filaments, rgb, layer_height, max_thickness_mm,
        region_weight=region_weight)
    log.append(f"Optimal order: {' → '.join(f['name'] for f in order_result['ordered_filaments'])}")
    log.append(f"Total blend height: {order_result['total_height']:.2f} mm")
    _emit("optimize_order",
          message=f"Order: {' → '.join(f['name'] for f in order_result['ordered_filaments'])}")

    # Step 3: Generate virtual swatches for color matching
    _emit("swatches", message="Generating virtual swatches...")
    swatches = generate_virtual_swatches(
        order_result['ordered_filaments'],
        order_result['layer_assignments'],
        layer_height)
    log.append(f"Generated {len(swatches)} virtual swatches")
    _emit("swatches", message=f"Generated {len(swatches)} virtual swatches")
    n_pixels = rgb.shape[0] * rgb.shape[1]

    # Step 4: Map image pixels to layer heights
    # (map_colors_to_height emits its own progress events internally)
    height_map = map_colors_to_height(
        rgb, swatches, max_thickness_mm, layer_height,
        dither_strength=dither_strength,
        lithophane=lithophane)

    # Step 5: Build mesh
    _emit("mesh", message=f"Building mesh from {n_pixels} pixels...")
    log.append(f"Overhang prevention: enabled (max 50°, pixel_spacing={pixel_spacing_mm}mm)")
    verts, faces = build_multi_color_mesh(
        height_map, phys_w, phys_h, base_thickness_mm,
        pixel_spacing_mm=pixel_spacing_mm)

    total_thickness = base_thickness_mm + max_thickness_mm
    log.append(f"Mesh: {len(verts)} verts, {len(faces)} faces")
    log.append(f"Total time: {time.time() - t0:.1f}s")
    _emit("mesh", message=f"Mesh built: {len(verts)} verts, {len(faces)} faces")
    _emit("complete", message=f"Done in {time.time() - t0:.1f}s")

    # Build swap instructions
    swaps = _build_swap_list(order_result, layer_height)

    return {
        "height_map": height_map,
        "layer_plan": order_result,
        "mesh_verts": verts,
        "mesh_faces": faces,
        "filament_info": order_result['ordered_filaments'],
        "swaps": swaps,
        "total_thickness_mm": total_thickness,
        "base_thickness_mm": base_thickness_mm,
        "phys_width_mm": round(phys_w, 1),
        "phys_height_mm": round(phys_h, 1),
        "log": log,
    }


def _extract_dominant_colors(img, num_colors):
    """Extract N dominant colors from an image using K-means clustering.

    Args:
        img: PIL Image in RGB mode.
        num_colors: Number of dominant colors to extract (≥2).

    Returns:
        List of (R, G, B) tuples in [0, 255], sorted by luminance.
    """
    import numpy as np
    from sklearn.cluster import KMeans

    rgb = np.array(img, dtype=np.float32)
    H, W = rgb.shape[:2]
    pixels = rgb.reshape(-1, 3)

    # Subsample for speed (every 4th pixel)
    sample = pixels[::4]
    km = KMeans(n_clusters=num_colors, random_state=42, n_init=3, max_iter=50)
    km.fit(sample)

    centers = np.clip(km.cluster_centers_, 0, 255).astype(np.uint8)
    rgb_list = [tuple(c) for c in centers]

    # Sort by luminance (dark→light)
    rgb_list.sort(key=lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])
    return rgb_list


def _resolve_td(filaments):
    """Fill in missing TD values from the known database."""
    resolved = []
    for f in filaments:
        name = f.get("name", f.get("color", "unknown"))
        color = f["color"]
        if "td" in f and f["td"] is not None:
            td = f["td"]
        else:
            td = lookup_td(name, color)
        resolved.append({"name": name, "color": color, "td": td})
    return resolved


def _build_swap_list(order_result, layer_height):
    """Convert layer assignments to printer swap instructions."""
    swaps = []
    current_z = 0.0
    for i, assignment in enumerate(order_result['layer_assignments']):
        filament = order_result['ordered_filaments'][assignment['filament_index']]
        if i == 0 or assignment['filament_index'] != order_result['layer_assignments'][i - 1]['filament_index']:
            swaps.append({
                "z_mm": round(current_z, 3),
                "layer_number": int(current_z / layer_height) + 1,
                "filament_index": assignment['filament_index'],
                "filament_name": filament['name'],
                "color": filament['color'],
            })
        current_z += assignment['thickness']
    return swaps
