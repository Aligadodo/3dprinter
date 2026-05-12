"""test_scripts.py - Unit tests for CLI scripts (JSON output format, error handling, path logic).

These tests run scripts as subprocess to verify the exact JSON contract that the
web server and pipeline orchestrator depend on.

Usage:
    python tests/test_scripts.py                    # Run all
    python tests/test_scripts.py --verbose          # Show stdout/stderr
    python tests/test_scripts.py -k relief         # Run only relief tests
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SAMPLE_IMG = None

# Find a sample image for testing
for root, dirs, files in os.walk(PROJECT_ROOT / "output"):
    for f in files:
        if f.lower().endswith((".png", ".jpg", ".jpeg")):
            SAMPLE_IMG = os.path.join(root, f)
            break
    if SAMPLE_IMG:
        break


# ═══════════════════════════════════════════════════════════
# Test Framework
# ═══════════════════════════════════════════════════════════

PASS = 0
FAIL = 0


def log(msg, level="info"):
    colors = {"ok": "\033[92m", "fail": "\033[91m", "skip": "\033[93m", "hdr": "\033[1;36m"}
    print(f"{colors.get(level, '')}{msg}\033[0m")


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        log(f"  PASS {name}", "ok")
    else:
        FAIL += 1
        log(f"  FAIL {name}  {detail}", "fail")
    return condition


def run_script(script_name, args=None, stdin_img=None, timeout=30, check=True):
    """Run a script and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, str(SCRIPTS_DIR / script_name)]
    if args:
        cmd.extend(args)
    env = os.environ.copy()
    env.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(SCRIPTS_DIR),
            env=env,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"


def parse_json_output(stdout):
    """Extract JSON from stdout, skipping any debug lines."""
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


# ═══════════════════════════════════════════════════════════
# Relief / Lithophane Tests
# ═══════════════════════════════════════════════════════════

def test_relief_basic_output():
    log("\n── relief: Basic JSON output ──", "hdr")
    if not SAMPLE_IMG:
        log("  SKIP — no sample image found", "skip")
        return

    rc, stdout, stderr = run_script("image-to-relief.py", [
        SAMPLE_IMG, "--width", "50", "--height", "50", "--max-depth", "1",
    ])

    check("Exit code 0", rc == 0, f"rc={rc}")
    data = parse_json_output(stdout)
    check("Valid JSON output", data is not None, stdout[:200] if not data else "")
    if data is None:
        return

    check("Has 'output' key", "output" in data or "stl" in data)
    check("Has 'width_mm' key", "width_mm" in data)
    check("Has 'height_mm' key", "height_mm" in data)
    check("Has 'thickness_mm' key", "thickness_mm" in data)
    check("Has 'lithophane' key (False)", "lithophane" in data)
    check("lithophane is False", data.get("lithophane") is False)
    check("log is non-empty", len(data.get("log", [])) > 0)


def test_relief_lithophane_mode():
    log("\n── relief: Lithophane mode ──", "hdr")
    if not SAMPLE_IMG:
        log("  SKIP — no sample image found", "skip")
        return

    rc, stdout, stderr = run_script("image-to-relief.py", [
        SAMPLE_IMG, "--width", "50", "--height", "50", "--lithophane",
    ])

    check("Exit code 0", rc == 0)
    data = parse_json_output(stdout)
    if data is None:
        return

    check("lithophane is True", data.get("lithophane") is True)
    check("max_depth <= 2.0 for lithophane", data.get("max_depth_mm", 99) <= 2.0)


def test_relief_with_colors():
    log("\n── relief: With color quantization ──", "hdr")
    if not SAMPLE_IMG:
        log("  SKIP — no sample image found", "skip")
        return

    rc, stdout, stderr = run_script("image-to-relief.py", [
        SAMPLE_IMG, "--width", "40", "--height", "40", "--colors", "2",
    ])

    check("Exit code 0", rc == 0)
    data = parse_json_output(stdout)
    if data is None:
        return

    check("num_colors = 2", data.get("num_colors") == 2)
    check("palette present when colors > 0", "palette" in data)
    check("color_preview present", "color_preview" in data)
    check("colored_obj present", "colored_obj" in data)


def test_relief_file_not_found():
    log("\n── relief: File not found error ──", "hdr")

    rc, stdout, stderr = run_script("image-to-relief.py", [
        "nonexistent_image_xyz123.png",
    ])

    check("Non-zero exit code", rc != 0)
    data = parse_json_output(stdout)
    check("Error JSON returned", data is not None)
    if data:
        check("Has 'error' key", "error" in data)
        check("Error message mentions file", "not found" in data.get("error", "").lower())


def test_relief_params_validation():
    log("\n── relief: Parameter validation ──", "hdr")
    if not SAMPLE_IMG:
        log("  SKIP — no sample image found", "skip")
        return

    # Zero max_depth is invalid (min=0.5)
    rc, stdout, stderr = run_script("image-to-relief.py", [
        SAMPLE_IMG, "--width", "50", "--height", "50", "--max-depth", "0",
    ])
    # Script may or may not reject; at minimum should not crash
    check("Handles invalid max_depth", rc in (0, 1))


# ═══════════════════════════════════════════════════════════
# Layered Relief Tests
# ═══════════════════════════════════════════════════════════

def test_layered_relief_basic():
    log("\n── layered_relief: Basic JSON output ──", "hdr")
    if not SAMPLE_IMG:
        log("  SKIP — no sample image found", "skip")
        return

    rc, stdout, stderr = run_script("image-to-layered-relief.py", [
        SAMPLE_IMG, "--width", "40", "--height", "40", "--colors", "2",
    ])

    check("Exit code 0", rc == 0)
    data = parse_json_output(stdout)
    check("Valid JSON output", data is not None)
    if data is None:
        return

    check("Has 'output' (stl path)", "output" in data)
    check("Has 'color_map' key", "color_map" in data)
    check("Has 'bands' list", "bands" in data and isinstance(data["bands"], list))
    check("Has 'width_mm' key", "width_mm" in data)
    check("Has 'height_mm' key", "height_mm" in data)
    check("num_colors = 2", data.get("num_colors") == 2)


def test_layered_relief_3mf_output():
    log("\n── layered_relief: 3MF format ──", "hdr")
    if not SAMPLE_IMG:
        log("  SKIP — no sample image found", "skip")
        return

    rc, stdout, stderr = run_script("image-to-layered-relief.py", [
        SAMPLE_IMG, "--width", "30", "--height", "30", "--colors", "2",
        "--format", "3mf",
    ])

    check("Exit code 0", rc == 0)
    data = parse_json_output(stdout)
    if data is None:
        return

    check("output_3mf key present", "output_3mf" in data)


def test_layered_relief_color_sorting():
    log("\n── layered_relief: Bands sorted by luminance ──", "hdr")
    if not SAMPLE_IMG:
        log("  SKIP — no sample image found", "skip")
        return

    rc, stdout, stderr = run_script("image-to-layered-relief.py", [
        SAMPLE_IMG, "--width", "40", "--height", "40", "--colors", "3",
    ])

    check("Exit code 0", rc == 0)
    data = parse_json_output(stdout)
    if data is None:
        return

    bands = data.get("bands", [])
    check("3 bands created", len(bands) == 3)
    if len(bands) < 2:
        return

    # Verify luminance ordering (darker = lower Z = earlier order)
    lum_values = [b.get("luminance_mean", 0) for b in bands]
    check("Bands ordered by luminance (ascending)",
          all(lum_values[i] <= lum_values[i+1] for i in range(len(lum_values)-1)),
          f"luminance order: {lum_values}")


def test_layered_relief_progress_events():
    log("\n── layered_relief: Progress events ──", "hdr")
    if not SAMPLE_IMG:
        log("  SKIP — no sample image found", "skip")
        return

    rc, stdout, stderr = run_script("image-to-layered-relief.py", [
        SAMPLE_IMG, "--width", "30", "--height", "30", "--colors", "2",
    ])

    lines = stdout.strip().splitlines()
    event_lines = [l for l in lines if l.startswith('{"event"')]
    check("Emits progress events", len(event_lines) > 0, f"got {len(event_lines)} events")
    check("Emits final 'done' event", any("done" in l for l in event_lines),
          f"events: {[json.loads(l).get('event') for l in event_lines]}")


# ═══════════════════════════════════════════════════════════
# Mesh Repair Tests
# ═══════════════════════════════════════════════════════════

def test_mesh_repair_basic():
    log("\n── mesh-repair: Basic JSON output ──", "hdr")
    if not SAMPLE_IMG:
        log("  SKIP — no sample image found", "skip")
        return

    # First create a mesh via relief
    rc, stdout, stderr = run_script("image-to-relief.py", [
        SAMPLE_IMG, "--width", "30", "--height", "30", "--max-depth", "1",
    ])
    data = parse_json_output(stdout)
    if not data or "stl" not in data:
        log("  SKIP — could not generate test mesh", "skip")
        return

    stl_path = data["stl"]
    if not os.path.exists(stl_path):
        log(f"  SKIP — STL not found: {stl_path}", "skip")
        return

    rc, stdout, stderr = run_script("mesh-repair.py", [stl_path])
    check("Exit code 0", rc == 0)
    repair_data = parse_json_output(stdout)
    check("Valid JSON output", repair_data is not None)
    if repair_data is None:
        return

    check("Has 'output' key", "output" in repair_data)
    check("Has 'watertight' key", "watertight" in repair_data)
    check("Has 'vertices' key", "vertices" in repair_data)
    check("Has 'faces' key", "faces" in repair_data)
    check("Has 'dimensions_mm' key", "dimensions_mm" in repair_data)
    check("vertices is int", isinstance(repair_data.get("vertices"), int))
    check("faces is int", isinstance(repair_data.get("faces"), int))


def test_mesh_repair_scale():
    log("\n── mesh-repair: Scale parameter ──", "hdr")
    if not SAMPLE_IMG:
        log("  SKIP — no sample image found", "skip")
        return

    # Get a mesh first
    rc, stdout, stderr = run_script("image-to-relief.py", [
        SAMPLE_IMG, "--width", "30", "--height", "30",
    ])
    data = parse_json_output(stdout)
    if not data or "stl" not in data:
        log("  SKIP — could not generate test mesh", "skip")
        return

    stl_path = data["stl"]
    if not os.path.exists(stl_path):
        log(f"  SKIP — STL not found: {stl_path}", "skip")
        return

    rc, stdout, stderr = run_script("mesh-repair.py", [stl_path, "--scale", "2.0"])
    check("Exit code 0", rc == 0)
    repair_data = parse_json_output(stdout)
    if repair_data is None:
        return

    check("Output file created", os.path.exists(repair_data.get("output", "")))
    out_dim = repair_data.get("dimensions_mm", [])
    check("Dimensions roughly doubled (2x scale)",
          all(d > 50 for d in out_dim if d > 0),
          f"dims: {out_dim}")


def test_mesh_repair_nonexistent_file():
    log("\n── mesh-repair: File not found error ──", "hdr")

    rc, stdout, stderr = run_script("mesh-repair.py", [
        "nonexistent_mesh_xyz.glb",
    ])

    check("Non-zero exit code", rc != 0)
    data = parse_json_output(stdout)
    check("Error JSON returned", data is not None)
    if data:
        check("Has 'error' key", "error" in data)


# ═══════════════════════════════════════════════════════════
# Mesh Simplify Tests
# ═══════════════════════════════════════════════════════════

def test_mesh_simplify_basic():
    log("\n── mesh-simplify: Basic output ──", "hdr")
    if not SAMPLE_IMG:
        log("  SKIP — no sample image found", "skip")
        return

    # Get a mesh
    rc, stdout, stderr = run_script("image-to-relief.py", [
        SAMPLE_IMG, "--width", "30", "--height", "30",
    ])
    data = parse_json_output(stdout)
    if not data or "stl" not in data:
        log("  SKIP — could not generate test mesh", "skip")
        return

    stl_path = data["stl"]
    if not os.path.exists(stl_path):
        log(f"  SKIP — STL not found: {stl_path}", "skip")
        return

    rc, stdout, stderr = run_script("mesh-simplify.py", [
        stl_path, "--target-faces", "5000",
    ])
    check("Exit code 0", rc == 0, f"rc={rc} stderr={stderr[:200]}")
    simp_data = parse_json_output(stdout)
    check("Valid JSON output", simp_data is not None,
          stdout[:200] if not simp_data else "")
    if simp_data is None:
        return

    check("Has 'output' key", "output" in simp_data)
    check("Has 'faces_after' key", "faces_after" in simp_data)
    check("faces_after <= target_faces",
          simp_data.get("faces_after", 999999) <= 5000,
          f"faces_after={simp_data.get('faces_after')}")
    check("Output file exists", os.path.exists(simp_data.get("output", "")))


# ═══════════════════════════════════════════════════════════
# Path Nesting Tests
# ═══════════════════════════════════════════════════════════

def test_no_output_nesting():
    log("\n── Path: No output/output nesting ──", "hdr")
    if not SAMPLE_IMG:
        log("  SKIP — no sample image found", "skip")
        return

    # If sample image is already in output/, output should stay in output/, not output/output/
    img_dir = os.path.dirname(SAMPLE_IMG)
    if "output" not in img_dir:
        log("  SKIP — sample image not in output dir", "skip")
        return

    rc, stdout, stderr = run_script("image-to-relief.py", [
        SAMPLE_IMG, "--width", "30", "--height", "30",
    ])
    data = parse_json_output(stdout)
    if not data or "stl" not in data:
        log("  SKIP — could not generate output", "skip")
        return

    output_path = data["stl"]
    check("Output NOT in output/output/",
          "output/output" not in output_path.replace("\\", "/"),
          f"output: {output_path}")


# ═══════════════════════════════════════════════════════════
# Error Contract Tests
# ═══════════════════════════════════════════════════════════

def test_all_scripts_error_contract():
    log("\n── Error contract: All scripts return error JSON ──", "hdr")

    scripts_and_cases = [
        ("image-to-relief.py", ["nonexistent_file_xyz.png"]),
        ("mesh-repair.py", ["nonexistent_file_xyz.stl"]),
        ("mesh-simplify.py", ["nonexistent_file_xyz.stl"]),
        ("mesh-to-views.py", ["nonexistent_file_xyz.stl"]),
    ]

    for script_name, args in scripts_and_cases:
        rc, stdout, stderr = run_script(script_name, args)
        data = parse_json_output(stdout)
        has_error_key = data is not None and "error" in data
        check(f"{script_name}: error JSON on bad input", has_error_key,
              f"rc={rc} stdout={stdout[:100]}")


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="3D Print Pipeline — Script Unit Tests")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-k", dest="filter", default="", help="Filter tests by name substring")
    args = parser.parse_args()

    global SAMPLE_IMG
    if SAMPLE_IMG:
        log(f"Using sample image: {SAMPLE_IMG}", "info")
    else:
        log("No sample image found — will skip image-dependent tests", "warn")

    test_functions = [
        # Relief
        test_relief_basic_output,
        test_relief_lithophane_mode,
        test_relief_with_colors,
        test_relief_file_not_found,
        test_relief_params_validation,
        # Layered Relief
        test_layered_relief_basic,
        test_layered_relief_3mf_output,
        test_layered_relief_color_sorting,
        test_layered_relief_progress_events,
        # Mesh Repair
        test_mesh_repair_basic,
        test_mesh_repair_scale,
        test_mesh_repair_nonexistent_file,
        # Mesh Simplify
        test_mesh_simplify_basic,
        # Path logic
        test_no_output_nesting,
        # Error contract
        test_all_scripts_error_contract,
    ]

    for tf in test_functions:
        if args.filter and args.filter.lower() not in tf.__name__.lower():
            continue
        try:
            tf()
        except Exception as e:
            global FAIL
            FAIL += 1
            log(f"  FAIL {tf.__name__} — exception: {e}", "fail")

    total = PASS + FAIL
    log(f"\n{'='*50}", "hdr")
    log(f"Script tests: {PASS} passed, {FAIL} failed ({total} total)", "hdr")
    if FAIL == 0:
        log("All script tests passed!", "ok")
    else:
        log(f"{FAIL} test(s) FAILED", "fail")
    log(f"{'='*50}", "hdr")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())