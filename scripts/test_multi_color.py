#!/usr/bin/env python
"""Comprehensive test suite for multi-color 3D printing pipeline.

Tests all scenarios: regression, 2/3/4-filament, lithophane, 3MF validation,
edge cases. Generates a structured test report.

Usage:
  python scripts/test_multi_color.py
  python scripts/test_multi_color.py --verbose
"""

import json
import os
import sys
import struct
import zipfile
import time
import numpy as np
from PIL import Image

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPTS_DIR)
os.chdir(PROJECT_ROOT)
sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, PROJECT_ROOT)

TEST_IMG_DIR = os.path.join(PROJECT_ROOT, "output", "test_images")
TEST_OUT_DIR = os.path.join(PROJECT_ROOT, "output", "test_results")
os.makedirs(TEST_IMG_DIR, exist_ok=True)
os.makedirs(TEST_OUT_DIR, exist_ok=True)

results = []
VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv


def log(msg, level="INFO"):
    if VERBOSE or level in ("PASS", "FAIL", "SKIP"):
        print(f"  [{level:5s}] {msg}")


def create_test_images():
    """Create tiny synthetic test images for fast test execution."""
    images = {}

    # All test images are intentionally small (≤30px) for fast execution.
    # Floyd-Steinberg dithering is O(W*H) in pure Python, so we keep
    # pixel counts very low for the test suite.

    # 1. Grayscale gradient (vertical) — 8x12 pixels
    grad = np.zeros((12, 8, 3), dtype=np.uint8)
    for y in range(12):
        val = int(255 * (1 - y / 11))
        grad[y, :] = [val, val, val]
    path = os.path.join(TEST_IMG_DIR, "gradient_bw.png")
    Image.fromarray(grad).save(path)
    images["gradient_bw"] = path

    # 2. Color bars: Black | Red | White — 9x6 pixels
    bars = np.zeros((9, 6, 3), dtype=np.uint8)
    bars[0:3, :] = [20, 20, 20]
    bars[3:6, :] = [220, 30, 30]
    bars[6:9, :] = [240, 240, 240]
    path = os.path.join(TEST_IMG_DIR, "bars_black_red_white.png")
    Image.fromarray(bars).save(path)
    images["bars_3color"] = path

    # 3. Four color quadrants — 10x10
    quad = np.zeros((10, 10, 3), dtype=np.uint8)
    quad[0:5, 0:5] = [20, 20, 20]
    quad[0:5, 5:10] = [220, 30, 30]
    quad[5:10, 0:5] = [220, 220, 30]
    quad[5:10, 5:10] = [240, 240, 240]
    path = os.path.join(TEST_IMG_DIR, "quad_4color.png")
    Image.fromarray(quad).save(path)
    images["quad_4color"] = path

    # 4. Small synthetic photo — 16x12
    photo = np.zeros((12, 16, 3), dtype=np.uint8)
    cx, cy = 8, 6
    for y in range(12):
        for x in range(16):
            dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            val = int(np.clip(255 - dist * 20, 0, 255))
            photo[y, x] = [val, val, val]
    path = os.path.join(TEST_IMG_DIR, "photo_synthetic.png")
    Image.fromarray(photo).save(path)
    images["photo_synthetic"] = path

    # 5. Pure white — 4x4
    Image.fromarray(np.full((4, 4, 3), 255, dtype=np.uint8)).save(
        os.path.join(TEST_IMG_DIR, "pure_white.png"))
    images["pure_white"] = os.path.join(TEST_IMG_DIR, "pure_white.png")

    # 6. Pure black — 4x4
    Image.fromarray(np.full((4, 4, 3), 5, dtype=np.uint8)).save(
        os.path.join(TEST_IMG_DIR, "pure_black.png"))
    images["pure_black"] = os.path.join(TEST_IMG_DIR, "pure_black.png")

    # 7. Tiny image for dithering test (20x15 = 300 px)
    dit_img = np.zeros((15, 20, 3), dtype=np.uint8)
    for y in range(15):
        val = int(255 * (1 - y / 14))
        dit_img[y, :] = [val, val, val]
    path = os.path.join(TEST_IMG_DIR, "dither_test.png")
    Image.fromarray(dit_img).save(path)
    images["dither_test"] = path

    return images


def test_scenario_1_regression():
    """Verify existing single-color pipeline still works."""
    log("Scenario 1: Single-color regression", "INFO")

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "image_to_relief", os.path.join(SCRIPTS_DIR, "image-to-relief.py"))
    image_to_relief_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(image_to_relief_mod)
    image_to_relief = image_to_relief_mod.image_to_relief

    img = os.path.join(TEST_IMG_DIR, "gradient_bw.png")

    # Test 1.1: Basic STL generation (coarse for speed)
    t0 = time.time()
    r = image_to_relief(img, width_mm=100, height_mm=75, max_depth_mm=2.0,
                        base_thickness_mm=0.5, detail_strength=0.25,
                        num_colors=0, pixel_spacing_mm=2.0, lithophane=False)
    elapsed = time.time() - t0
    checks = []
    checks.append(("STL output exists", "stl" in r and os.path.exists(r["stl"])))
    checks.append(("STL > 1KB", os.path.getsize(r["stl"]) > 1000))
    checks.append(("Has log entries", len(r.get("log", [])) > 0))
    checks.append(("No error", "error" not in r))
    checks.append(("Dimensions correct", abs(r.get("width_mm", 0) - 100) < 2))
    checks.append(("Responds < 5s", elapsed < 5.0))
    all_pass = all(c[1] for c in checks)
    results.append({"scenario": "1.1 Basic STL", "pass": all_pass, "checks": checks})
    log(f"{'PASS' if all_pass else 'FAIL'}: Basic STL ({elapsed:.1f}s)", "PASS" if all_pass else "FAIL")

    # Test 1.2: Colored OBJ
    r2 = image_to_relief(img, width_mm=100, height_mm=75, max_depth_mm=2.0,
                         base_thickness_mm=0.5, num_colors=4,
                         pixel_spacing_mm=3.0)
    checks2 = []
    checks2.append(("Colored OBJ exists", "colored_obj" in r2 and os.path.exists(r2["colored_obj"])))
    checks2.append(("Palette has 4 colors", len(r2.get("palette", [])) == 4))
    checks2.append(("Color preview exists", "color_preview" in r2))
    all_pass2 = all(c[1] for c in checks2)
    results.append({"scenario": "1.2 Colored OBJ", "pass": all_pass2, "checks": checks2})
    log(f"{'PASS' if all_pass2 else 'FAIL'}: Colored OBJ (4 colors)", "PASS" if all_pass2 else "FAIL")

    # Test 1.3: Lithophane
    r3 = image_to_relief(img, width_mm=100, height_mm=75, max_depth_mm=2.0,
                         base_thickness_mm=0.6, num_colors=0,
                         pixel_spacing_mm=3.0, lithophane=True)
    checks3 = []
    checks3.append(("Lithophane STL exists", "stl" in r3 and os.path.exists(r3["stl"])))
    checks3.append(("Lithophane flag true", r3.get("lithophane") is True))
    checks3.append(("Base thickness >= 0.5", r3.get("base_thickness_mm", 0) >= 0.5))
    all_pass3 = all(c[1] for c in checks3)
    results.append({"scenario": "1.3 Lithophane", "pass": all_pass3, "checks": checks3})
    log(f"{'PASS' if all_pass3 else 'FAIL'}: Lithophane mode", "PASS" if all_pass3 else "FAIL")

    return all_pass and all_pass2 and all_pass3


def test_scenario_2_two_filaments():
    """Test simplest multi-color: Black + White."""
    log("Scenario 2: Multi-color 2-filament (Black + White)", "INFO")

    from multi_color import compute_color_layers

    img = os.path.join(TEST_IMG_DIR, "gradient_bw.png")
    filaments = [
        {"color": "#000000", "td": 0.6, "name": "Black PLA"},
        {"color": "#FFFFFF", "td": 4.4, "name": "White PLA"},
    ]

    t0 = time.time()
    r = compute_color_layers(img, filaments=filaments, layer_height=0.08,
                             max_thickness_mm=3.0, base_thickness_mm=0.6,
                             pixel_spacing_mm=3.0, dither_strength=0.0)
    elapsed = time.time() - t0

    checks = []
    checks.append(("Has filament_info", "filament_info" in r))
    checks.append(("Has swaps", len(r.get("swaps", [])) >= 2))
    checks.append(("Has height_map", r.get("height_map") is not None))
    checks.append(("Has mesh_verts", len(r.get("mesh_verts", [])) > 0))
    checks.append(("Has mesh_faces", len(r.get("mesh_faces", [])) > 0))

    # Verify layer ordering: Black must be on bottom
    ordered = r.get("filament_info", [])
    if len(ordered) >= 2:
        lums = [0.2126 * int(c["color"][1:3], 16) + 0.7152 * int(c["color"][3:5], 16) + 0.0722 * int(c["color"][5:7], 16) for c in ordered]
        lums = [l / 255.0 for l in lums]
        checks.append(("Dark on bottom (luminance order)", lums[0] <= lums[-1]))

    # Verify swaps make sense
    swaps = r.get("swaps", [])
    if swaps:
        checks.append(("First swap at Z=0", abs(swaps[0]["z_mm"]) < 0.01))
        checks.append(("Swap filament names populated", all("filament_name" in s for s in swaps)))

    all_pass = all(c[1] for c in checks)
    results.append({"scenario": "2. 2-Filament", "pass": all_pass, "checks": checks,
                    "elapsed_s": round(elapsed, 1)})
    # Show swap plan
    if VERBOSE:
        for s in swaps:
            log(f"  Swap: Layer {s['layer_number']} @ Z={s['z_mm']}mm → {s['filament_name']} ({s['color']})", "INFO")
    log(f"{'PASS' if all_pass else 'FAIL'}: 2-filament ({elapsed:.1f}s)", "PASS" if all_pass else "FAIL")
    return all_pass


def test_scenario_3_three_filaments():
    """Test 3-color stacking with different TD values."""
    log("Scenario 3: Multi-color 3-filament (Black + Red + White)", "INFO")

    from multi_color import compute_color_layers

    img = os.path.join(TEST_IMG_DIR, "bars_black_red_white.png")
    filaments = [
        {"color": "#000000", "td": 0.6, "name": "Black PLA"},
        {"color": "#FF0000", "td": 3.5, "name": "Red PLA"},
        {"color": "#FFFFFF", "td": 4.4, "name": "White PLA"},
    ]

    t0 = time.time()
    r = compute_color_layers(img, filaments=filaments, layer_height=0.08,
                             max_thickness_mm=3.0, base_thickness_mm=0.6,
                             pixel_spacing_mm=3.0, dither_strength=0.0)
    elapsed = time.time() - t0

    checks = []
    # Order must be dark→light
    ordered = r.get("filament_info", [])
    names = [f["name"] for f in ordered]
    checks.append(("3 filaments in plan", len(ordered) == 3))
    checks.append(("Order: Black→Red→White (dark→light)",
                  names == ["Black PLA", "Red PLA", "White PLA"]))

    # Height map should cover full range
    hm = r.get("height_map")
    if hm is not None:
        checks.append(("Height range > 2.0mm", hm.max() - hm.min() > 2.0))
        checks.append(("Height min >= 0", hm.min() >= 0))
        checks.append(("Height max <= 3.0", hm.max() <= 3.0))

    # Transition zones should exist
    layer_plan = r.get("layer_plan", {})
    assignments = layer_plan.get("layer_assignments", [])
    checks.append(("At least 2 zones", len(assignments) >= 2))

    # Each filament should have some thickness
    for a in assignments:
        checks.append((f"Zone thickness > 0: {a['filament_index']}", a["thickness"] > 0))

    all_pass = all(c[1] for c in checks)
    results.append({"scenario": "3. 3-Filament", "pass": all_pass, "checks": checks,
                    "elapsed_s": round(elapsed, 1)})
    if VERBOSE:
        for a in assignments:
            fn = r['filament_info'][a['filament_index']]['name']
            log(f"  Zone: {fn}: {a['start_z']:.2f}→{a['start_z']+a['thickness']:.2f} ({a['thickness']:.2f}mm)", "INFO")
    log(f"{'PASS' if all_pass else 'FAIL'}: 3-filament ({elapsed:.1f}s)", "PASS" if all_pass else "FAIL")
    return all_pass


def test_scenario_4_four_filaments():
    """Test 4-color exhaustive search optimization."""
    log("Scenario 4: Multi-color 4-filament exhaustive search", "INFO")

    from multi_color import compute_color_layers

    img = os.path.join(TEST_IMG_DIR, "quad_4color.png")
    filaments = [
        {"color": "#000000", "td": 0.6, "name": "Black PLA"},
        {"color": "#FF0000", "td": 3.5, "name": "Red PLA"},
        {"color": "#FFD700", "td": 5.0, "name": "Yellow PLA"},
        {"color": "#FFFFFF", "td": 4.4, "name": "White PLA"},
    ]

    t0 = time.time()
    r = compute_color_layers(img, filaments=filaments, layer_height=0.08,
                             max_thickness_mm=4.0, base_thickness_mm=0.6,
                             pixel_spacing_mm=3.0, dither_strength=0.3)
    elapsed = time.time() - t0

    checks = []
    ordered = r.get("filament_info", [])
    checks.append(("4 filaments in plan", len(ordered) == 4))

    # All 4 filaments should appear
    all_names = {f["name"] for f in ordered}
    checks.append(("All filaments used", all_names == {"Black PLA", "Red PLA", "Yellow PLA", "White PLA"}))

    # Luminance ordering
    if len(ordered) >= 2:
        lums = []
        for f in ordered:
            r_hex = int(f["color"][1:3], 16) / 255.0
            g_hex = int(f["color"][3:5], 16) / 255.0
            b_hex = int(f["color"][5:7], 16) / 255.0
            lums.append(0.2126 * r_hex + 0.7152 * g_hex + 0.0722 * b_hex)
        checks.append(("Monotonic luminance (dark→light)",
                      all(lums[i] <= lums[i + 1] for i in range(len(lums) - 1))))

    # Exhaustive search should complete quickly for 4 colors
    checks.append(("Exhaustive search < 30s", elapsed < 30.0))

    # Verify score is reasonable
    score = r.get("layer_plan", {}).get("score", 999)
    checks.append(("Score is finite", score < 100))

    all_pass = all(c[1] for c in checks)
    results.append({"scenario": "4. 4-Filament", "pass": all_pass, "checks": checks,
                    "elapsed_s": round(elapsed, 1)})
    if VERBOSE:
        log(f"  Order: {' → '.join(f['name'] for f in ordered)}", "INFO")
    log(f"{'PASS' if all_pass else 'FAIL'}: 4-filament exhaustive ({elapsed:.1f}s)", "PASS" if all_pass else "FAIL")
    return all_pass


def test_scenario_5_lithophane_multi():
    """Test multi-color with lithophane mode."""
    log("Scenario 5: Lithophane + Multi-color combined", "INFO")

    from multi_color import compute_color_layers

    img = os.path.join(TEST_IMG_DIR, "gradient_bw.png")
    filaments = [
        {"color": "#000000", "td": 0.6, "name": "Black PLA"},
        {"color": "#FFFFFF", "td": 4.4, "name": "White PLA"},
    ]

    # Standard relief
    r_relief = compute_color_layers(img, filaments=filaments, layer_height=0.08,
                                    max_thickness_mm=3.0, base_thickness_mm=0.6,
                                    pixel_spacing_mm=3.0, dither_strength=0.0,
                                    lithophane=False)
    # Lithophane
    r_litho = compute_color_layers(img, filaments=filaments, layer_height=0.08,
                                   max_thickness_mm=3.0, base_thickness_mm=0.6,
                                   pixel_spacing_mm=3.0, dither_strength=0.0,
                                   lithophane=True)

    checks = []
    hm_r = r_relief.get("height_map")
    hm_l = r_litho.get("height_map")

    if hm_r is not None and hm_l is not None:
        # In lithophane mode, bright areas should be THINNER (inverted)
        # For gradient image (top=bright, bottom=dark):
        # Relief: top_row > bottom_row (bright = raised)
        # Lithophane: top_row < bottom_row (bright = thin)
        relief_top = hm_r[0, :].mean()
        relief_bot = hm_r[-1, :].mean()
        litho_top = hm_l[0, :].mean()
        litho_bot = hm_l[-1, :].mean()
        checks.append(("Relief: bright=raised", relief_top > relief_bot))
        checks.append(("Lithophane: bright=thin (inverted)", litho_top < litho_bot))
        checks.append(("Lithophane & Relief differ", abs(relief_top - litho_top) > 0.1))

    # Both should produce valid meshes
    checks.append(("Relief mesh valid", len(r_relief.get("mesh_verts", [])) > 0))
    checks.append(("Lithophane mesh valid", len(r_litho.get("mesh_verts", [])) > 0))

    all_pass = all(c[1] for c in checks)
    results.append({"scenario": "5. Lithophane+Multi", "pass": all_pass, "checks": checks})
    log(f"{'PASS' if all_pass else 'FAIL'}: Lithophane + Multi-color", "PASS" if all_pass else "FAIL")
    return all_pass


def test_scenario_6_3mf_validation():
    """Validate 3MF export structure."""
    log("Scenario 6: 3MF export structure validation", "INFO")

    from multi_color import export_3mf, compute_color_layers
    from multi_color.export_3mf import export_swap_text

    # Generate a mesh first
    img = os.path.join(TEST_IMG_DIR, "bars_black_red_white.png")
    filaments = [
        {"color": "#000000", "td": 0.6, "name": "Black PLA"},
        {"color": "#FF0000", "td": 3.5, "name": "Red PLA"},
        {"color": "#FFFFFF", "td": 4.4, "name": "White PLA"},
    ]

    r = compute_color_layers(img, filaments=filaments, layer_height=0.08,
                             max_thickness_mm=3.0, base_thickness_mm=0.6,
                             pixel_spacing_mm=3.0, dither_strength=0.0)

    # Save STL using the function from image-to-relief
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "image_to_relief", os.path.join(SCRIPTS_DIR, "image-to-relief.py"))
    irl_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(irl_mod)

    stl_path = os.path.join(TEST_OUT_DIR, "test_3mf.stl")
    irl_mod._export_stl(r["mesh_verts"], r["mesh_faces"], stl_path)

    # Export 3MF
    mf3_path = os.path.join(TEST_OUT_DIR, "test_3mf.3mf")
    export_3mf(mf3_path, stl_path,
               swaps=r["swaps"],
               filaments=r["filament_info"],
               layer_height=0.08,
               total_thickness_mm=r["total_thickness_mm"])

    # Export swap text
    swaps_path = os.path.join(TEST_OUT_DIR, "test_3mf_swaps.txt")
    export_swap_text(swaps_path, swaps=r["swaps"],
                     filaments=r["filament_info"], layer_height=0.08)

    checks = []

    # Check 3MF is valid ZIP
    checks.append(("3MF file exists", os.path.exists(mf3_path)))
    checks.append(("3MF > 1KB", os.path.getsize(mf3_path) > 1000))

    try:
        with zipfile.ZipFile(mf3_path, 'r') as zf:
            names = zf.namelist()
            checks.append(("[Content_Types].xml exists", "[Content_Types].xml" in names))
            checks.append(("3D/3dmodel.model exists", "3D/3dmodel.model" in names))
            checks.append(("Metadata/project_settings.config exists",
                          "Metadata/project_settings.config" in names))
            checks.append(("Metadata/custom_gcode_per_layer.xml exists",
                          "Metadata/custom_gcode_per_layer.xml" in names))

            # Validate model XML content
            model_xml = zf.read("3D/3dmodel.model").decode("utf-8")
            checks.append(("Model has basematerials", "<basematerials" in model_xml))
            checks.append(("Model has vertices", "<vertices>" in model_xml))
            checks.append(("Model has triangles", "<triangles>" in model_xml))
            checks.append(("Model has build item", "<item objectid" in model_xml))

            # Validate project settings
            settings = json.loads(zf.read("Metadata/project_settings.config"))
            checks.append(("Settings has filament_colour", "filament_colour" in settings))
            checks.append(("Settings has 3 filaments", len(settings.get("filament_colour", [])) == 3))
            checks.append(("Layer height = 0.08", settings.get("layer_height") == "0.08"))

            # Validate custom gcode
            gcode_xml = zf.read("Metadata/custom_gcode_per_layer.xml").decode("utf-8")
            checks.append(("Has tool_change events", "tool_change" in gcode_xml))
            checks.append(("Has plate_info", "plate_info" in gcode_xml))
            checks.append(("Has layer elements", "<layer " in gcode_xml))
    except Exception as e:
        checks.append((f"ZIP read error: {e}", False))

    # Validate swap text
    if os.path.exists(swaps_path):
        with open(swaps_path, 'r') as f:
            txt = f.read()
        checks.append(("Swap text has instructions", "Swap Instructions" in txt))
        checks.append(("Swap text has filament names", "Black PLA" in txt))
        checks.append(("Swap text has layer numbers", "Layer" in txt))

    all_pass = all(c[1] for c in checks)
    results.append({"scenario": "6. 3MF Validation", "pass": all_pass, "checks": checks})
    log(f"{'PASS' if all_pass else 'FAIL'}: 3MF structure", "PASS" if all_pass else "FAIL")
    return all_pass


def test_scenario_7_edge_cases():
    """Test edge cases and error handling."""
    log("Scenario 7: Edge cases and error handling", "INFO")
    from multi_color import compute_color_layers
    from multi_color.td_database import lookup_td

    all_scenarios_pass = True

    # 7.1: Single filament (should not crash)
    log("  7.1: Single filament", "INFO")
    try:
        r = compute_color_layers(
            os.path.join(TEST_IMG_DIR, "pure_white.png"),
            filaments=[{"color": "#FFFFFF", "name": "White PLA"}],
            layer_height=0.08, max_thickness_mm=3.0, base_thickness_mm=0.6,
            pixel_spacing_mm=3.0, dither_strength=0.0)
        checks = [("Single filament returns result", len(r.get("filament_info", [])) == 1),
                  ("Single filament has swaps", len(r.get("swaps", [])) >= 1)]
        passed = all(c[1] for c in checks)
        results.append({"scenario": "7.1 Single filament", "pass": passed, "checks": checks})
        log(f"{'PASS' if passed else 'FAIL'}: Single filament", "PASS" if passed else "FAIL")
        all_scenarios_pass = all_scenarios_pass and passed
    except Exception as e:
        results.append({"scenario": "7.1 Single filament", "pass": False,
                        "checks": [(f"Exception: {e}", False)]})
        log(f"FAIL: {e}", "FAIL")
        all_scenarios_pass = False

    # 7.2: Missing TD values (auto-resolve from database)
    log("  7.2: Auto-resolve TD", "INFO")
    try:
        r = compute_color_layers(
            os.path.join(TEST_IMG_DIR, "gradient_bw.png"),
            filaments=[{"color": "#000000", "name": "Bambu Basic Black"},
                       {"color": "#FFFFFF", "name": "Bambu Basic White"}],
            layer_height=0.08, max_thickness_mm=3.0, base_thickness_mm=0.6,
            pixel_spacing_mm=3.0, dither_strength=0.0)
        tds = [f.get("td", 0) for f in r.get("filament_info", [])]
        checks = [("Black TD resolved", tds[0] > 0.1 if len(tds) > 0 else False),
                  ("White TD resolved", tds[1] > 1.0 if len(tds) > 1 else False)]
        passed = all(c[1] for c in checks)
        results.append({"scenario": "7.2 Auto-resolve TD", "pass": passed, "checks": checks})
        log(f"{'PASS' if passed else 'FAIL'}: Auto-resolve TD ({tds})", "PASS" if passed else "FAIL")
        all_scenarios_pass = all_scenarios_pass and passed
    except Exception as e:
        results.append({"scenario": "7.2 Auto-resolve TD", "pass": False,
                        "checks": [(f"Exception: {e}", False)]})
        log(f"FAIL: {e}", "FAIL")
        all_scenarios_pass = False

    # 7.3: TD database edge cases
    log("  7.3: TD database edge cases", "INFO")
    checks = []
    checks.append(("Known brand+color", lookup_td("Bambu PLA Basic", "Black") == 0.6))
    checks.append(("Case insensitive", lookup_td("bambu pla basic", "black") == 0.6))
    checks.append(("Unknown returns default", lookup_td("NonExistent Brand XYZ", "Purple") > 0))
    checks.append(("Default is sensible (0.5-7)", 0.5 <= lookup_td("???", "???") <= 7.0))
    checks.append(("PETG is higher TD", lookup_td("PETG", "Natural") > 5.0))
    passed = all(c[1] for c in checks)
    results.append({"scenario": "7.3 TD database", "pass": passed, "checks": checks})
    log(f"{'PASS' if passed else 'FAIL'}: TD database edge cases", "PASS" if passed else "FAIL")
    all_scenarios_pass = all_scenarios_pass and passed

    # 7.4: 5-filament simulated annealing path
    log("  7.4: 5-filament (simulated annealing)", "INFO")
    try:
        filaments_5 = [
            {"color": "#000000", "td": 0.6, "name": "Black"},
            {"color": "#333333", "td": 1.0, "name": "DarkGray"},
            {"color": "#888888", "td": 2.5, "name": "Gray"},
            {"color": "#CCCCCC", "td": 3.5, "name": "LightGray"},
            {"color": "#FFFFFF", "td": 4.4, "name": "White"},
        ]
        r = compute_color_layers(
            os.path.join(TEST_IMG_DIR, "gradient_bw.png"),
            filaments=filaments_5, layer_height=0.08, max_thickness_mm=4.0,
            base_thickness_mm=0.6, pixel_spacing_mm=3.0, dither_strength=0.0)
        checks = [("5 filaments in plan", len(r.get("filament_info", [])) == 5),
                  ("Score is finite", r.get("layer_plan", {}).get("score", 999) < 200)]
        passed = all(c[1] for c in checks)
        results.append({"scenario": "7.4 5-filament SA", "pass": passed, "checks": checks})
        log(f"{'PASS' if passed else 'FAIL'}: Simulated annealing 5-color", "PASS" if passed else "FAIL")
        all_scenarios_pass = all_scenarios_pass and passed
    except Exception as e:
        results.append({"scenario": "7.4 5-filament SA", "pass": False,
                        "checks": [(f"Exception: {e}", False)]})
        log(f"FAIL: {e}", "FAIL")
        all_scenarios_pass = False

    # 7.5: Invalid filament JSON (tested via CLI separately)
    # 7.6: All-black image with black filament only
    log("  7.5: Pure black image, single black filament", "INFO")
    try:
        r = compute_color_layers(
            os.path.join(TEST_IMG_DIR, "pure_black.png"),
            filaments=[{"color": "#000000", "td": 0.6, "name": "Black PLA"}],
            layer_height=0.08, max_thickness_mm=3.0, base_thickness_mm=0.6,
            pixel_spacing_mm=3.0, dither_strength=0.0)
        checks = [("Pure black mesh valid", len(r.get("mesh_verts", [])) > 0)]
        passed = all(c[1] for c in checks)
        results.append({"scenario": "7.5 Pure black", "pass": passed, "checks": checks})
        log(f"{'PASS' if passed else 'FAIL'}: Pure black image", "PASS" if passed else "FAIL")
        all_scenarios_pass = all_scenarios_pass and passed
    except Exception as e:
        results.append({"scenario": "7.5 Pure black", "pass": False,
                        "checks": [(f"Exception: {e}", False)]})
        log(f"FAIL: {e}", "FAIL")
        all_scenarios_pass = False

    return all_scenarios_pass


def test_scenario_8_performance():
    """Quick performance benchmarks."""
    log("Scenario 8: Performance benchmarks", "INFO")

    from multi_color import compute_color_layers

    img = os.path.join(TEST_IMG_DIR, "dither_test.png")
    filaments = [
        {"color": "#000000", "td": 0.6, "name": "Black PLA"},
        {"color": "#FFFFFF", "td": 4.4, "name": "White PLA"},
    ]

    # Without dithering (fast)
    t0 = time.time()
    r = compute_color_layers(img, filaments=filaments, layer_height=0.08,
                             max_thickness_mm=3.0, base_thickness_mm=0.6,
                             pixel_spacing_mm=3.0, dither_strength=0.0)
    t_no_dither = time.time() - t0

    # With dithering
    t0 = time.time()
    r2 = compute_color_layers(img, filaments=filaments, layer_height=0.08,
                              max_thickness_mm=3.0, base_thickness_mm=0.6,
                              pixel_spacing_mm=3.0, dither_strength=0.5)
    t_with_dither = time.time() - t0

    h, w = r["height_map"].shape
    n_pixels = h * w

    checks = [
        ("No-dither < 1s", t_no_dither < 1.0),
        ("With-dither < 2s", t_with_dither < 2.0),
        ("With-dither completes", r2.get("height_map") is not None),
    ]
    passed = all(c[1] for c in checks)
    results.append({"scenario": "8. Performance", "pass": passed, "checks": checks,
                    "metrics": {
                        "pixels": n_pixels,
                        "no_dither_s": round(t_no_dither, 2),
                        "with_dither_s": round(t_with_dither, 2),
                        "dither_overhead_x": round(t_with_dither / max(t_no_dither, 0.01), 1),
                    }})
    log(f"{'PASS' if passed else 'FAIL'}: Performance — "
        f"no_dither={t_no_dither:.1f}s, with_dither={t_with_dither:.1f}s "
        f"({n_pixels} px)", "PASS" if passed else "FAIL")
    return passed


def generate_report(all_pass):
    """Generate test report markdown."""
    report_path = os.path.join(PROJECT_ROOT, "docs", "iterations",
                               "multi-color-test-report-20260522.md")

    total = sum(1 for r in results if "scenario" in r)
    passed = sum(1 for r in results if r.get("pass"))

    lines = [
        "# Multi-Color Pipeline Test Report",
        "",
        f"> 2026-05-22 | Auto-generated | {passed}/{total} scenarios passed",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total scenarios | {total} |",
        f"| Passed | {passed} |",
        f"| Failed | {total - passed} |",
        f"| Overall | **{'PASS' if all_pass else 'FAIL'}** |",
        "",
        "## Scenario Results",
        "",
    ]

    for r in results:
        status = "✅" if r.get("pass") else "❌"
        name = r.get("scenario", "Unknown")
        elapsed = r.get("elapsed_s", None)
        time_str = f" ({elapsed:.1f}s)" if elapsed else ""
        lines.append(f"### {status} {name}{time_str}")
        lines.append("")

        for check in r.get("checks", []):
            label, ok = check
            lines.append(f"- {'✅' if ok else '❌'} {label}")

        metrics = r.get("metrics", {})
        if metrics:
            lines.append("")
            lines.append("**Metrics:**")
            for k, v in metrics.items():
                lines.append(f"- {k}: {v}")

        lines.append("")

    # Detailed check counts
    total_checks = sum(len(r.get("checks", [])) for r in results)
    passed_checks = sum(sum(1 for c in r.get("checks", []) if c[1]) for r in results)
    lines.append("## Check Summary")
    lines.append("")
    lines.append(f"- Total checks: {total_checks}")
    lines.append(f"- Passed: {passed_checks}")
    lines.append(f"- Failed: {total_checks - passed_checks}")
    lines.append(f"- Check pass rate: {100 * passed_checks / max(total_checks, 1):.1f}%")
    lines.append("")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return report_path


if __name__ == "__main__":
    print("=" * 60)
    print("Multi-Color Pipeline — Comprehensive Test Suite")
    print("=" * 60)

    create_test_images()
    print()

    all_pass = True
    all_pass &= test_scenario_1_regression()
    print()
    all_pass &= test_scenario_2_two_filaments()
    print()
    all_pass &= test_scenario_3_three_filaments()
    print()
    all_pass &= test_scenario_4_four_filaments()
    print()
    all_pass &= test_scenario_5_lithophane_multi()
    print()
    all_pass &= test_scenario_6_3mf_validation()
    print()
    all_pass &= test_scenario_7_edge_cases()
    print()
    all_pass &= test_scenario_8_performance()

    report = generate_report(all_pass)

    print()
    print("=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r.get("pass"))
    print(f"RESULTS: {passed}/{total} scenarios passed")
    total_checks = sum(len(r.get("checks", [])) for r in results)
    passed_checks = sum(sum(1 for c in r.get("checks", []) if c[1]) for r in results)
    print(f"CHECKS:  {passed_checks}/{total_checks} checks passed")
    print(f"REPORT:  {report}")
    print("=" * 60)

    sys.exit(0 if all_pass else 1)
