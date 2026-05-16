# Multi-Color 3MF Export for Bambu Studio

## Overview

The layered relief pipeline (`image-to-layered-relief.py`) generates 3MF files that are fully compatible with Bambu Studio's multi-color AMS printing. When opened, all filaments are auto-configured with correct colors from the k-means palette, and filament change events are pre-set at each color band's Z-height boundary — no manual configuration needed.

## How It Works

### Architecture

```
image-to-layered-relief.py
  └── _export_3mf()
        ├── Loads printer profile (profile.json)
        ├── Loads project_settings.template (~483 keys for P1S, ~557 for A1)
        ├── Loads 4 G-code templates (machine start/end, layer change, filament change)
        ├── Computes dynamic values (filament colors, flush matrix, etc.)
        ├── _resolve_template_json() — walks JSON dict, replaces {{PLACEHOLDER}} with Python objects
        ├── Generates custom_gcode_per_layer.xml (MultiAsSingle mode)
        └── Writes 10-file ZIP archive
```

### 3MF Internal Structure

| File | Purpose |
|------|---------|
| `[Content_Types].xml` | OPC content type registry |
| `_rels/.rels` | Root relationships (points to 3dmodel) |
| `3D/3dmodel.model` | Scene graph, metadata, build plate layout |
| `3D/Objects/object.model` | Binary STL mesh data |
| `3D/_rels/3dmodel.model.rels` | Model-to-mesh relationship |
| `Metadata/project_settings.config` | Full slicer config (filaments, G-code, printer) |
| `Metadata/model_settings.config` | Plate layout, filament mapping per object |
| `Metadata/custom_gcode_per_layer.xml` | Z-height-based filament change events |
| `Metadata/cut_information.xml` | Connector cut info (stub) |
| `Metadata/filament_sequence.json` | AMS slot assignment (stub) |

### MultiAsSingle Mode

A single mesh is printed with multiple filaments. At each color band's Z-end boundary, a `tool_change` event switches to the next extruder. Extruder 1 is active by default at Z=0.

For N colors, there are N-1 filament change events. Example for 4 colors:
```xml
<custom_gcodes_per_layer>
 <plate>
  <plate_info id="1"/>
  <layer top_z="0.70" type="2" extruder="2" color="#263D1E" gcode="tool_change"/>
  <layer top_z="1.10" type="2" extruder="3" color="#597547" gcode="tool_change"/>
  <layer top_z="1.50" type="2" extruder="4" color="#9FA28C" gcode="tool_change"/>
  <mode value="MultiAsSingle"/>
 </plate>
</custom_gcodes_per_layer>
```

### Template System

`scripts/templates/bambu/<printer>/project_settings.template` contains ~483-557 key JSON with `{{PLACEHOLDER}}` markers. The `_resolve_template_json()` function:

1. Parses the template as JSON
2. Walks the resulting dict recursively
3. Replaces exact `{{KEY}}` strings with Python objects (lists, dicts, strings)
4. For strings *containing* placeholders (like `"{{BED_SIZE_X}}x0"`), uses regex substitution with `str()` conversion
5. Re-serializes as valid JSON via `json.dumps`

### Dynamic Values

| Value | Source |
|-------|--------|
| `filament_colour` | k-means palette from image |
| `flush_volumes_matrix` | N×N, 280 off-diagonal, 0 diagonal |
| `filament_self_index` | `list(range(N)) * 2` |
| `filament_map` | `"1 1 1 1"` for N=4 |
| `wipe_tower_x/y` | `bed_size - 60 / bed_size - 40` |
| `printable_area` | Computed from bed dimensions |

## Bambu Studio 3MF Format Reference

### Official Sample Analysis

Reference files: `D:/拓竹打印/模型收藏合集/` (大量官方导出文件)

#### `Metadata/model_settings.config` — Critical for Import

The most important file for Bambu Studio to successfully parse a 3MF. All official files share this structure:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="2">
    <metadata key="name" value="实体1"/>
    <metadata key="extruder" value="1"/>
    <metadata face_count="19568"/>           <!-- REQUIRED: triangle count -->
    <part id="1" subtype="normal_part">
      <metadata key="name" value="实体1"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>  <!-- REQUIRED: identity matrix -->
      <metadata key="source_object_id" value="0"/>
      <metadata key="source_volume_id" value="0"/>
      <metadata key="source_offset_x" value="25"/>   <!-- Position on print bed -->
      <metadata key="source_offset_y" value="42.5"/>
      <metadata key="source_offset_z" value="8"/>
      <mesh_stat face_count="19568"        <!-- REQUIRED: mesh statistics -->
                 edges_fixed="0"
                 degenerate_facets="0"
                 facets_removed="0"
                 facets_reversed="0"
                 backwards_edges="0"/>
    </part>
  </object>
  <plate>
    <metadata key="plater_id" value="1"/>
    <metadata key="plater_name" value=""/>
    <metadata key="locked" value="false"/>
    <metadata key="filament_map_mode" value="Auto For Flush"/>
    <metadata key="filament_maps" value="1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1"/>
    <metadata key="filament_volume_maps" value="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"/>  <!-- 16 slots! -->
    <metadata key="thumbnail_file" value="Metadata/plate_1.png"/>  <!-- Required thumbnails -->
    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_1.png"/>
    <metadata key="top_file" value="Metadata/top_1.png"/>
    <metadata key="pick_file" value="Metadata/pick_1.png"/>
    <model_instance>
      <metadata key="object_id" value="2"/>
      <metadata key="instance_id" value="0"/>
      <metadata key="identify_id" value="92"/>
    </model_instance>
  </plate>
  <assemble>
    <assemble_item object_id="2" instance_id="0"
     transform="1 0 0 0 1 0 0 0 1 128 128 8"
     offset="0 0 0" />
  </assemble>
</config>
```

**Critical fields (missing = parse error):**
- `object/metadata[@face_count]` — triangle count, must match actual STL
- `part/metadata[@matrix]` — 4x4 identity matrix, `1 0 0 0 1 0 0 0 1 0 0 0`
- `part/mesh_stat[@face_count]` — must equal object face_count
- `plate/metadata[@filament_volume_maps]` — 16 space-separated zeros `"0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"`

#### `3D/3dmodel.model` — Scene Graph

```xml
<?xml version='1.0' encoding='UTF-8'?>
<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
       xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
       xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"
       unit="millimeter" xml:lang="en-US" requiredextensions="p">
  <!-- Required metadata -->
  <metadata name="Application">BambuStudio-02.03.00.70</metadata>
  <metadata name="BambuStudio:3mfVersion">1</metadata>
  <metadata name="BambuStudio:CopyRight">[]</metadata>  <!-- Note: not "Copyright" -->
  <metadata name="BambuStudio:Copyright">[]</metadata>
  <metadata name="BambuStudio:Designer">...</metadata>
  <metadata name="BambuStudio:DesignerUserId">...</metadata>
  <metadata name="BambuStudio:DesignModelId">...</metadata>
  <metadata name="BambuStudio:DesignProfileId">...</metadata>
  <metadata name="BambuStudio:DesignRegion">CN</metadata>

  <resources>
    <object id="2" p:UUID="00000001-61cb-4c03-9d28-80fed5dfa1dc" type="model">
      <components>
        <component p:path="/3D/Objects/object_1.model" objectid="1"
                   p:UUID="00010000-b206-40ff-9872-83e8017abed1"
                   transform="1 0 0 0 1 0 0 0 1 0 0 0" />
      </components>
    </object>
  </resources>
  <build p:UUID="2c7c17d8-22b5-4d84-8835-1976022ea369">
    <item objectid="2" p:UUID="00000002-b1ec-4553-aec9-835e5b724bb4"
          transform="1 0 0 0 1 0 0 0 1 128 128 8"
          printable="1" />
  </build>
</model>
```

#### `3D/_rels/3dmodel.model.rels` — Mesh Relationship

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/Objects/object_1.model"
                Id="rel-1"
                Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
```

**Important**: `Id` uses format `rel-N` (with hyphen), not `relN`.

#### `Metadata/filament_sequence.json` — AMS Slot Assignment

```json
{"plate_1":{"sequence":[]}}
```

For multi-color, this is typically empty for MultiAsSingle mode (colors controlled via `custom_gcode_per_layer.xml`).

#### `Metadata/custom_gcode_per_layer.xml` — Filament Change Events

```xml
<?xml version="1.0" encoding="UTF-8"?>
<custom_gcodes_per_layer>
  <plate>
    <plate_info id="1"/>
    <layer top_z="0.70" type="2" extruder="2" color="#263D1E" extra="" gcode="tool_change"/>
    <layer top_z="1.10" type="2" extruder="3" color="#597547" extra="" gcode="tool_change"/>
    <layer top_z="1.50" type="2" extruder="4" color="#9FA28C" extra="" gcode="tool_change"/>
    <mode value="MultiAsSingle"/>
  </plate>
</custom_gcodes_per_layer>
```

- `type="2"` = filament change event
- `extruder` = 2-4 (not 1-indexed from bands, but 1-indexed for actual extruder)
- Color values are hex RGB uppercase

#### `Metadata/slice_info.config` — Slicer Version Header

```xml
<?xml version="1.0" encoding="UTF-8"?>
<config>
  <header>
    <header_item key="X-BBL-Client-Type" value="slicer"/>
    <header_item key="X-BBL-Client-Version" value="02.05.00.66"/>
  </header>
</config>
```

#### `[Content_Types].xml` — OPC Content Types

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="gcode" ContentType="text/x.gcode"/>
</Types>
```

Known extensions: `rels`, `model`, `png`, `gcode`, `config`, `xml`, `json` (our files add these, tolerated).

#### Binary STL in `3D/Objects/object_N.model`

- Standard binary STL (little-endian)
- 80-byte header, 4-byte triangle count, 50-byte triangles
- NOT compressed inside the 3MF ZIP

## Key Design Decisions

- **Template format**: JSON with `{{PLACEHOLDER}}` strings. Parsing as JSON ensures the template itself is always valid, and `json.dumps` handles all escaping correctly.
- **G-code handling**: Raw G-code files are loaded as-is (with real newline characters) and passed directly to `_resolve_template_json`. The single `json.dumps` call at the end handles JSON escaping once — no manual escaping needed.
- **Printer profiles**: `profile.json` per printer contains bed dimensions, nozzle diameter, default print/filament profiles. New printers can be added by creating a new directory under `templates/bambu/`.

## Known Pitfalls (Fixed)

### G-code double-escaping

Originally `_escape_gcode()` pre-escaped newlines via `json.dumps(gcode)[1:-1]`, then `json.dumps` in `_resolve_template_json` escaped them again, producing `\\n` in the JSON output. This made Bambu Studio interpret literal `\n` text instead of newlines in the G-code.

**Fix**: Removed `_escape_gcode()`. Raw G-code passes through, single `json.dumps` handles all escaping.

### Compound-string placeholders not resolved

Strings like `"{{BED_SIZE_X}}x0"` in `printable_area` weren't resolved because the old walker only matched strings that were *exactly* a `{{KEY}}`.

**Fix**: Regex-based resolution — exact match returns Python objects, compound strings get string substitution.

### Wrong extruder indices in custom_gcode_per_layer.xml

Events were generated for all bands (including the last) with `extruder_idx = band["order"]` instead of `band["order"] + 1`, plus an unnecessary initial event at first band's z_start.

**Fix**: Iterate `sorted_bands[:-1]` (skip last), use `extruder_idx = band["order"] + 1` to switch to the next filament.

### model_settings.config missing critical fields (2026-05-15)

`model_settings.config` was missing `face_count`, `matrix`, `source_offset_*`, and `mesh_stat` that all official Bambu Studio exports include. This caused Bambu Studio to reject/garble the file on open.

**Fix**: Read face_count from binary STL header (offset 80, 4-byte little-endian uint32). Add `matrix` (identity), `source_offset_x/y/z` (0), and `mesh_stat` to part element. Add `filament_volume_maps` (16 zeros for N=4).

## CLI Usage

```bash
# 4-color P1S
python scripts/image-to-layered-relief.py photo.jpg --colors 4 --format 3mf --printer P1S

# 2-color A1
python scripts/image-to-layered-relief.py photo.jpg --colors 2 --format 3mf --printer A1
```

## Web UI

The web interface exposes the `printer` parameter as a choice field (P1S / A1) in the layered relief task form. The `scheduler.py` maps `"printer"` → `"--printer"` CLI flag.

## Iteration History

| Date | Change |
|------|--------|
| 2026-05-15 | Fix model_settings.config missing face_count, matrix, source_offset, mesh_stat, filament_volume_maps |
| 2026-05-14 | Fix extruder indices in custom_gcode_per_layer.xml (band order +1, skip last band) |
| 2026-05-13 | Fix compound-string placeholder resolution in _resolve_template_json |
| 2026-05-13 | Remove _escape_gcode() to fix G-code double-escaping |