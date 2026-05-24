#!/usr/bin/env python
"""Quick test runner for multi-color pipeline — all scenarios."""
import sys, os, time, json, zipfile, numpy as np

# Force flush stdout for real-time output
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util

from multi_color import compute_color_layers, export_3mf
from multi_color.export_3mf import export_swap_text
from multi_color.td_database import lookup_td

PASS, FAIL, CHECKS = 0, 0, []

def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}")
    CHECKS.append((name, condition))

# Load image-to-relief module
spec = importlib.util.spec_from_file_location("image_to_relief", "scripts/image-to-relief.py")
irl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(irl)

# ═══ Scenario 1: Regression ═══
print("=== Scenario 1: Single-color regression ===")
r = irl.image_to_relief("output/test_images/gradient_bw.png",
    width_mm=100, height_mm=75, max_depth_mm=2.0,
    base_thickness_mm=0.5, detail_strength=0.25,
    num_colors=0, pixel_spacing_mm=3.0, lithophane=False)
check("1.1 STL exists", "stl" in r and os.path.exists(r["stl"]))
check("1.1 STL > 1KB", os.path.getsize(r["stl"]) > 1000)
check("1.1 No error", "error" not in r)

r2 = irl.image_to_relief("output/test_images/gradient_bw.png",
    width_mm=100, height_mm=75, max_depth_mm=2.0,
    base_thickness_mm=0.5, num_colors=4, pixel_spacing_mm=3.0)
check("1.2 Colored OBJ", "colored_obj" in r2)
check("1.2 4-color palette", len(r2.get("palette", [])) == 4)

r3 = irl.image_to_relief("output/test_images/gradient_bw.png",
    width_mm=100, height_mm=75, max_depth_mm=2.0,
    base_thickness_mm=0.6, num_colors=0, pixel_spacing_mm=3.0, lithophane=True)
check("1.3 Lithophane mode", r3.get("lithophane") is True)

# ═══ Scenario 2: 2-filament ═══
print("\n=== Scenario 2: 2-filament (Black + White) ===")
fil2 = [{"color":"#000000","td":0.6,"name":"Black PLA"},
        {"color":"#FFFFFF","td":4.4,"name":"White PLA"}]
r = compute_color_layers("output/test_images/gradient_bw.png", filaments=fil2,
    layer_height=0.08, max_thickness_mm=3.0, base_thickness_mm=0.6,
    pixel_spacing_mm=3.0, dither_strength=0.0)
order_names = [f["name"] for f in r["filament_info"]]
check("2.1 2 filaments", len(r["filament_info"]) == 2)
check("2.2 Dark-on-bottom", order_names[0] == "Black PLA" and order_names[-1] == "White PLA")
check("2.3 Has swaps", len(r["swaps"]) >= 2)
check("2.4 Height map valid", r["height_map"] is not None and r["height_map"].max() > 0)
check("2.5 Mesh valid", len(r["mesh_verts"]) > 0 and len(r["mesh_faces"]) > 0)
print(f"    Order: {' -> '.join(order_names)}, Swaps: {len(r['swaps'])}")

# ═══ Scenario 3: 3-filament ═══
print("\n=== Scenario 3: 3-filament (Black + Red + White) ===")
fil3 = [{"color":"#000000","td":0.6,"name":"Black PLA"},
        {"color":"#FF0000","td":3.5,"name":"Red PLA"},
        {"color":"#FFFFFF","td":4.4,"name":"White PLA"}]
r = compute_color_layers("output/test_images/bars_3color.png", filaments=fil3,
    layer_height=0.08, max_thickness_mm=3.0, base_thickness_mm=0.6,
    pixel_spacing_mm=3.0, dither_strength=0.0)
names = [f["name"] for f in r["filament_info"]]
check("3.1 3 filaments", len(r["filament_info"]) == 3)
check("3.2 Order: Black->Red->White", names == ["Black PLA", "Red PLA", "White PLA"])
check("3.3 Height in bounds", 0 <= r["height_map"].min() <= r["height_map"].max() <= 3.0)
check("3.4 Score finite", r["layer_plan"]["score"] < 100)
print(f"    Order: {' -> '.join(names)}, Score: {r['layer_plan']['score']:.2f}")

# ═══ Scenario 4: 4-filament ═══
print("\n=== Scenario 4: 4-filament exhaustive ===")
fil4 = [{"color":"#000000","td":0.6,"name":"Black PLA"},
        {"color":"#FF0000","td":3.5,"name":"Red PLA"},
        {"color":"#FFD700","td":5.0,"name":"Yellow PLA"},
        {"color":"#FFFFFF","td":4.4,"name":"White PLA"}]
t0 = time.time()
r = compute_color_layers("output/test_images/quad_4color.png", filaments=fil4,
    layer_height=0.08, max_thickness_mm=4.0, base_thickness_mm=0.6,
    pixel_spacing_mm=3.0, dither_strength=0.0)
elapsed = time.time() - t0
names = [f["name"] for f in r["filament_info"]]
all_names = set(f["name"] for f in r["filament_info"])
check("4.1 4 filaments", len(r["filament_info"]) == 4)
check("4.2 All colors used", all_names == {"Black PLA","Red PLA","Yellow PLA","White PLA"})
lums = []
for f in r["filament_info"]:
    rh=int(f["color"][1:3],16)/255.0; gh=int(f["color"][3:5],16)/255.0; bh=int(f["color"][5:7],16)/255.0
    lums.append(0.2126*rh+0.7152*gh+0.0722*bh)
mono = all(lums[i] <= lums[i+1] for i in range(len(lums)-1))
check("4.3 Luminance monotonic", mono)
check("4.4 Exhaustive < 60s", elapsed < 60.0)
print(f"    Order: {' -> '.join(names)}, {elapsed:.1f}s")

# ═══ Scenario 5: Lithophane + Multi ═══
print("\n=== Scenario 5: Lithophane + Multi-color ===")
r_relief = compute_color_layers("output/test_images/gradient_bw.png", filaments=fil2,
    layer_height=0.08, max_thickness_mm=3.0, base_thickness_mm=0.6,
    pixel_spacing_mm=3.0, dither_strength=0.0, lithophane=False)
r_litho = compute_color_layers("output/test_images/gradient_bw.png", filaments=fil2,
    layer_height=0.08, max_thickness_mm=3.0, base_thickness_mm=0.6,
    pixel_spacing_mm=3.0, dither_strength=0.0, lithophane=True)
hm_r = r_relief["height_map"]; hm_l = r_litho["height_map"]
relief_top = hm_r[0,:].mean(); relief_bot = hm_r[-1,:].mean()
litho_top = hm_l[0,:].mean(); litho_bot = hm_l[-1,:].mean()
check("5.1 Relief bright=raised", relief_top > relief_bot)
check("5.2 Litho bright=thin", litho_top < litho_bot)
check("5.3 Relief != Litho", abs(relief_top - litho_top) > 0.1)
print(f"    Relief: top={relief_top:.2f} bot={relief_bot:.2f}")
print(f"    Litho:  top={litho_top:.2f} bot={litho_bot:.2f}")

# ═══ Scenario 6: 3MF Validation ═══
print("\n=== Scenario 6: 3MF Validation ===")
r = compute_color_layers("output/test_images/bars_3color.png", filaments=fil3,
    layer_height=0.08, max_thickness_mm=3.0, base_thickness_mm=0.6,
    pixel_spacing_mm=3.0, dither_strength=0.0)
os.makedirs("output/test_results", exist_ok=True)
stl_path = "output/test_results/test_3mf.stl"
irl._export_stl(r["mesh_verts"], r["mesh_faces"], stl_path)
mf3_path = "output/test_results/test_3mf.3mf"
export_3mf(mf3_path, stl_path, swaps=r["swaps"], filaments=r["filament_info"],
    layer_height=0.08, total_thickness_mm=r["total_thickness_mm"])
swaps_path = "output/test_results/test_3mf_swaps.txt"
export_swap_text(swaps_path, swaps=r["swaps"], filaments=r["filament_info"],
    layer_height=0.08)

check("6.1 3MF exists", os.path.exists(mf3_path))
check("6.2 3MF > 1KB", os.path.getsize(mf3_path) > 1000)
with zipfile.ZipFile(mf3_path, 'r') as zf:
    names = zf.namelist()
    check("6.3 [Content_Types].xml", "[Content_Types].xml" in names)
    check("6.4 3D/3dmodel.model", "3D/3dmodel.model" in names)
    check("6.5 project_settings.config", "Metadata/project_settings.config" in names)
    check("6.6 custom_gcode_per_layer.xml", "Metadata/custom_gcode_per_layer.xml" in names)
    settings = json.loads(zf.read("Metadata/project_settings.config"))
    check("6.7 filament_colour in settings", "filament_colour" in settings)
    check("6.8 3 filaments in settings", len(settings["filament_colour"]) == 3)
    check("6.9 layer_height in settings", settings.get("layer_height") == "0.08")
    gcode = zf.read("Metadata/custom_gcode_per_layer.xml").decode()
    check("6.10 tool_change events", "tool_change" in gcode)
    check("6.11 layer elements present", "<layer " in gcode)

with open(swaps_path) as f:
    txt = f.read()
check("6.12 Swap text instructions", "Swap Instructions" in txt)
check("6.13 Swap text has color names", "Black PLA" in txt)
print(f"    3MF size: {os.path.getsize(mf3_path)}B")

# ═══ Scenario 7: Edge Cases ═══
print("\n=== Scenario 7: Edge Cases ===")

r = compute_color_layers("output/test_images/gradient_bw.png",
    filaments=[{"color":"#FFFFFF","name":"White PLA"}],
    layer_height=0.08, max_thickness_mm=3.0, base_thickness_mm=0.6,
    pixel_spacing_mm=3.0, dither_strength=0.0)
check("7.1 Single filament", len(r["filament_info"]) == 1 and len(r["swaps"]) >= 1)

r = compute_color_layers("output/test_images/gradient_bw.png",
    filaments=[{"color":"#000000","name":"Bambu Basic Black"},
               {"color":"#FFFFFF","name":"Bambu Basic White"}],
    layer_height=0.08, max_thickness_mm=3.0, base_thickness_mm=0.6,
    pixel_spacing_mm=3.0, dither_strength=0.0)
tds = [f["td"] for f in r["filament_info"]]
check("7.2 Auto-resolve TD", tds[0] > 0.1 and tds[1] > 1.0)

check("7.3a Known TD (Bambu Black)", lookup_td("Bambu PLA Basic", "Black") == 0.6)
check("7.3b Case insensitive", lookup_td("bambu pla basic", "black") == 0.6)
check("7.3c Unknown default", 0.5 <= lookup_td("???", "???") <= 7.0)
check("7.3d PETG higher TD", lookup_td("PETG", "Natural") > 5.0)

fil5 = [{"color":"#000000","td":0.6,"name":"Black"},
        {"color":"#333333","td":1.0,"name":"DarkGray"},
        {"color":"#888888","td":2.5,"name":"Gray"},
        {"color":"#CCCCCC","td":3.5,"name":"LightGray"},
        {"color":"#FFFFFF","td":4.4,"name":"White"}]
r = compute_color_layers("output/test_images/gradient_bw.png", filaments=fil5,
    layer_height=0.08, max_thickness_mm=4.0, base_thickness_mm=0.6,
    pixel_spacing_mm=3.0, dither_strength=0.0)
lums = [0.2126*int(f["color"][1:3],16)/255.0+0.7152*int(f["color"][3:5],16)/255.0+0.0722*int(f["color"][5:7],16)/255.0 for f in r["filament_info"]]
mono = all(lums[i] <= lums[i+1] for i in range(len(lums)-1))
check("7.4 SA 5-color", len(r["filament_info"]) == 5 and mono)

check("7.5 Worst-case TD", lookup_td("NonExistent Brand 123", "Magenta") > 0)

# ═══ Scenario 8: Performance ═══
print("\n=== Scenario 8: Performance ===")
t0 = time.time()
r = compute_color_layers("output/test_images/dither_test.png", filaments=fil2,
    layer_height=0.08, max_thickness_mm=3.0, base_thickness_mm=0.6,
    pixel_spacing_mm=3.0, dither_strength=0.0)
t_nd = time.time() - t0
t0 = time.time()
r2 = compute_color_layers("output/test_images/dither_test.png", filaments=fil2,
    layer_height=0.08, max_thickness_mm=3.0, base_thickness_mm=0.6,
    pixel_spacing_mm=3.0, dither_strength=0.5)
t_wd = time.time() - t0
n_px = r["height_map"].size
check("8.1 No-dither < 8s", t_nd < 8.0)
check("8.2 With-dither < 5s", t_wd < 5.0)
check("8.3 Both produce valid mesh", r2["mesh_verts"] is not None and len(r2["mesh_verts"]) > 0)
print(f"    Pixels: {n_px}, No-dither: {t_nd:.2f}s, Dither: {t_wd:.2f}s")

# ═══ Summary ═══
print(f"\n{'='*50}")
print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS+FAIL} checks")
print(f"{'ALL TESTS PASSED' if FAIL == 0 else 'SOME TESTS FAILED'}")
print(f"{'='*50}")
sys.exit(0 if FAIL == 0 else 1)
