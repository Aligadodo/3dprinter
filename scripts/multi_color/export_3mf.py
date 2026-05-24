"""Bambu Studio / Orca Slicer compatible 3MF export.

Generates a .3mf project file containing:
  - Mesh geometry (3MF XML format in separate object file)
  - Filament color/material definitions (project_settings.config)
  - Layer-height filament change events (custom_gcode_per_layer.xml)

Uses the official Bambu Studio base 3MF template for correct metadata,
thumbnails, and namespace declarations — then replaces only the mesh,
filament colors, and layer-change G-code.

MultiAsSingle mode: single extruder prints multiple filaments via AMS,
with tool-change events at specific layer heights from bottom to top.
"""

import os
import json
import zipfile
import numpy as np
import trimesh


def export_3mf(output_path, stl_path, swaps, filaments,
               layer_height=0.08, first_layer_height=0.16,
               total_thickness_mm=2.0, infill=100):
    """Export a Bambu-compatible 3MF project with filament swap instructions.

    Args:
        output_path: Path for the output .3mf file.
        stl_path: Path to the existing binary STL mesh file.
        swaps: List of {z_mm, layer_number, filament_index, filament_name, color}.
        filaments: List of {name, color, td} dicts (in print order, bottom→top).
        layer_height: mm per layer (default 0.08).
        first_layer_height: mm for first layer (default 0.16).
        total_thickness_mm: Total model Z thickness.
        infill: Infill percentage (default 100 for lithophane/relief).
    """
    # ── Load mesh ──
    mesh = trimesh.load(stl_path, force='mesh')
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(mesh.dump())
    verts = np.array(mesh.vertices, dtype=np.float64)
    faces = np.array(mesh.faces, dtype=np.int32)
    face_count = len(faces)

    # Decimate huge meshes for manageable 3MF file size
    max_faces = 250000
    if face_count > max_faces:
        try:
            mesh_simp = mesh.simplify_quadric_decimation(face_count=max_faces)
            verts = np.array(mesh_simp.vertices, dtype=np.float64)
            faces = np.array(mesh_simp.faces, dtype=np.int32)
            face_count = len(faces)
        except Exception:
            stride = max(1, face_count // max_faces)
            faces = faces[::stride].copy()
            face_count = len(faces)

    model_name = os.path.splitext(os.path.basename(output_path))[0]
    stl_base = os.path.splitext(os.path.basename(stl_path))[0]

    # ── Build XML mesh (separate object file format) ──
    xml_mesh_bytes = _build_object_mesh_xml(verts, faces)

    # ── Build custom_gcode_per_layer.xml (MultiAsSingle) ──
    gcode_xml = _build_custom_gcode_xml(swaps, filaments, layer_height)

    # ── Locate base 3MF template ──
    base_path = _find_base_3mf()

    # ── Update model_settings from base ──
    base_model_settings = _read_base_file(base_path, 'Metadata/model_settings.config')
    model_settings = _update_model_settings(base_model_settings, face_count, stl_base)

    # ── Update project_settings from base ──
    base_project_settings = _read_base_file(base_path, 'Metadata/project_settings.config')
    project_settings = _update_project_settings(base_project_settings, filaments,
                                                 layer_height, first_layer_height,
                                                 total_thickness_mm, infill)

    # ── Write output 3MF ──
    with zipfile.ZipFile(base_path, 'r') as base_zf:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as out_zf:
            for item in base_zf.infolist():
                if item.filename == '3D/Objects/object_2.model':
                    out_zf.writestr(item.filename, xml_mesh_bytes)
                elif item.filename == 'Metadata/custom_gcode_per_layer.xml':
                    out_zf.writestr(item.filename, gcode_xml.encode('utf-8'))
                elif item.filename == 'Metadata/model_settings.config':
                    out_zf.writestr(item.filename, model_settings.encode('utf-8'))
                elif item.filename == 'Metadata/project_settings.config':
                    out_zf.writestr(item.filename, project_settings.encode('utf-8'))
                else:
                    out_zf.writestr(item.filename, base_zf.read(item.filename))


def export_swap_text(output_path, swaps, filaments, layer_height=0.08,
                     first_layer_height=0.16):
    """Export human-readable filament swap instructions as text."""
    lines = [
        "Multi-Color Print — Filament Swap Instructions",
        "=" * 50,
        "",
        "Print Settings:",
        f"  Layer height: {layer_height} mm",
        f"  First layer height: {first_layer_height} mm",
        f"  Infill: 100%",
        "",
        "Filaments Used:",
    ]
    for i, f in enumerate(filaments):
        lines.append(f"  Slot {i + 1}: {f['name']} ({f['color']})  TD={f.get('td', '?')}")

    lines.append("")
    lines.append("Swap Sequence (bottom → top):")
    lines.append("  Layer  |  Z (mm)   |  Filament")
    lines.append("  -------|-----------|----------")

    for swap in swaps:
        lines.append(f"  {swap['layer_number']:>6}  |  {swap['z_mm']:>8.3f}  |  {swap['filament_name']}")

    lines.append("")
    lines.append("Instructions:")
    lines.append("  1. Open the .3mf file in Bambu Studio.")
    lines.append("  2. Verify filament colors match your AMS slots.")
    lines.append("  3. Slice — filament changes happen automatically at each layer.")
    lines.append("  4. Print.")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return output_path


# ═══════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════

def _find_base_3mf():
    """Find the official Bambu Studio base 3MF template."""
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tpl_path = os.path.join(script_dir, 'templates', 'bambu', 'base.3mf')
    if os.path.exists(tpl_path):
        return tpl_path
    raise FileNotFoundError(
        f"Base 3MF template not found at {tpl_path}. "
        "Run image-to-layered-relief.py once to generate it."
    )


def _read_base_file(base_path, internal_path):
    """Read a file from inside the base 3MF ZIP."""
    with zipfile.ZipFile(base_path, 'r') as zf:
        return zf.read(internal_path).decode('utf-8')


def _build_object_mesh_xml(verts, faces):
    """Build the 3MF object mesh XML for a separate object file.

    Uses the Production extension namespace so Bambu Studio can
    assign per-triangle materials if needed in the future.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<model unit="millimeter" xml:lang="en-US"',
        ' xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"',
        ' xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"',
        ' xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"',
        ' requiredextensions="p">',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        ' <resources>',
        '  <object id="1" type="model">',
        '   <mesh>',
        '    <vertices>',
    ]
    for v in verts:
        lines.append(f'     <vertex x="{v[0]:.6f}" y="{v[1]:.6f}" z="{v[2]:.6f}"/>')
    lines.append('    </vertices>')
    lines.append('    <triangles>')
    for tri in faces:
        lines.append(f'     <triangle v1="{tri[0]}" v2="{tri[1]}" v3="{tri[2]}"/>')
    lines.append('    </triangles>')
    lines.append('   </mesh>')
    lines.append('  </object>')
    lines.append(' </resources>')
    lines.append(' <build/>')
    lines.append('</model>')
    return '\n'.join(lines).encode('utf-8')


def _build_custom_gcode_xml(swaps, filaments, layer_height):
    """Build custom_gcode_per_layer.xml with MultiAsSingle mode.

    type="2" = filament change event at this Z height.
    MultiAsSingle = single extruder drives multiple AMS filaments.
    """
    n_filaments = len(filaments)

    # Generate tool-change events at each swap boundary.
    # Extruder 1 is active by default at Z=0; the first swap switches
    # to extruder 2, then 3, etc. One event per filament after the first.
    events = []
    swap_list = sorted(swaps, key=lambda s: s["z_mm"])
    for i, swap in enumerate(swap_list):
        if i == 0 and swap["z_mm"] <= 0.001:
            continue  # first filament starts at Z=0, no event needed
        extruder = min(swap["filament_index"] + 1, n_filaments)
        color = swap.get("color", "#000000").upper()
        events.append(
            f'  <layer top_z="{swap["z_mm"]:.3f}" type="2" '
            f'extruder="{extruder}" color="{color}" '
            f'extra="" gcode="tool_change"/>'
        )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<custom_gcodes_per_layer>',
        ' <plate>',
        '  <plate_info id="1"/>',
    ]
    lines.extend(events)
    lines.extend([
        '  <mode value="MultiAsSingle"/>',
        ' </plate>',
        '</custom_gcodes_per_layer>',
    ])
    return '\n'.join(lines)


def _update_model_settings(base_xml, face_count, model_name):
    """Update model_settings.config from the base template.

    Replaces the face_count and model name, preserves all other
    Bambu metadata (plate info, filament_map_mode, assemble, etc.).
    """
    result = base_xml
    # Update face_count in both locations
    import re
    result = re.sub(r'face_count="\d+"', f'face_count="{face_count}"', result, count=2)
    # Update mesh_stat face_count
    result = re.sub(
        r'mesh_stat face_count="\d+"',
        f'mesh_stat face_count="{face_count}"', result
    )
    # Update STL name (may appear in both object and part metadata)
    result = re.sub(
        r'value="[^"]*\.stl"',
        f'value="{model_name}.stl"', result
    )
    return result


def _update_project_settings(base_json_str, filaments, layer_height,
                              first_layer_height, total_thickness_mm, infill=100):
    """Update project_settings.config with our filament colors.

    Preserves the full base template structure and only replaces
    filament-related fields to match our computed filaments.
    Auto-resizes all per-filament arrays from base_n to n.
    """
    ps = json.loads(base_json_str)
    n = len(filaments)
    colors = [f["color"] for f in filaments]
    names = [f.get("name", f"Filament {i+1}") for i, f in enumerate(filaments)]

    # Number of filaments in base template
    base_n = len(ps.get("filament_colour", []))

    # Auto-resize all filament_* arrays from base_n to n
    if n != base_n:
        for key, val in list(ps.items()):
            if isinstance(val, list) and len(val) == base_n and key.startswith("filament_"):
                if n > base_n:
                    ps[key] = list(val) + [val[-1]] * (n - base_n)
                else:
                    ps[key] = val[:n]

    # ── Override key filament fields explicitly ──
    ps["filament_colour"] = colors
    ps["filament_multi_colour"] = colors
    ps["default_filament_colour"] = colors
    ps["filament_settings_id"] = [f"Generic PLA - {name}" for name in names]
    ps["filament_type"] = ["PLA"] * n
    ps["filament_vendor"] = ["Generic"] * n
    ps["filament_diameter"] = ["1.75"] * n
    ps["filament_density"] = ["1.26"] * n
    ps["filament_cost"] = ["20"] * n

    # Generate plausible filament IDs
    import hashlib
    fil_ids = []
    for f in filaments:
        h = hashlib.md5(f["color"].encode()).hexdigest()[:8].upper()
        fil_ids.append(f"GFB{h}")
    ps["filament_ids"] = fil_ids

    # ── Flush volumes ──
    flush_matrix = [0 if i == j else 280 for i in range(n) for j in range(n)]
    ps["flush_volumes_matrix"] = [str(v) for v in flush_matrix]
    ps["flush_volumes_vector"] = ["140"] * n

    # Filament map: all mapped to slot 1 (MultiAsSingle)
    ps["filament_map"] = ["1"] * n

    # Update basic settings
    ps["layer_height"] = str(layer_height)
    ps["initial_layer_print_height"] = str(first_layer_height)
    ps["sparse_infill_density"] = str(infill) + "%"

    return json.dumps(ps, indent=2)


