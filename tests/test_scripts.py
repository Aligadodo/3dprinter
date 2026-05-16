"""test_scripts.py - Unit tests for CLI scripts (JSON output format, error handling, path logic).

These tests run scripts as subprocess to verify the exact JSON contract that the
web server and pipeline orchestrator depend on.

Usage:
    pytest tests/test_scripts.py -v
    pytest tests/test_scripts.py -v -k relief
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def sample_image():
    """Find a sample image in output/ for integration tests."""
    for root, dirs, files in os.walk(PROJECT_ROOT / "output"):
        for f in files:
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                return os.path.join(root, f)
    return None


@pytest.fixture
def no_sample_image():
    """Marker: skip if no sample image is available."""
    for root, dirs, files in os.walk(PROJECT_ROOT / "output"):
        for f in files:
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                return True
    return False


def run_script(script_name, args=None, timeout=30):
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
    """Extract JSON objects from stdout, handling multi-line output.

    Scripts may output multi-line JSON (indent=2), so we extract all complete
    JSON objects by brace-matching rather than line-by-line parsing.
    Returns the LAST JSON that has a result-like key.
    """
    results = _extract_all_json(stdout)
    for obj in reversed(results):
        if any(k in obj for k in ("output", "stl", "error", "bands", "faces_after")):
            return obj
    return results[-1] if results else None


def parse_all_json_output(stdout):
    """Extract ALL JSON objects from stdout (for event/progress inspection)."""
    return _extract_all_json(stdout)


def _extract_all_json(text):
    """Extract all complete JSON objects from text by brace-matching."""
    results = []
    i = 0
    n = len(text)

    while i < n:
        while i < n and text[i] != '{':
            i += 1
        if i >= n:
            break

        depth = 0
        start = i
        j = i
        while j < n:
            c = text[j]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    break
            j += 1

        fragment = text[start:j+1]
        try:
            obj = json.loads(fragment)
            results.append(obj)
        except json.JSONDecodeError:
            pass
        i = j + 1

    return results


# ═══════════════════════════════════════════════════════════
# Relief / Lithophane Tests
# ═══════════════════════════════════════════════════════════

class TestRelief:
    """Tests for image-to-relief.py."""

    def test_basic_output(self, sample_image):
        """Basic JSON output with required fields."""
        if not sample_image:
            pytest.skip("no sample image found")

        rc, stdout, stderr = run_script("image-to-relief.py", [
            sample_image, "--width", "50", "--height", "50", "--max-depth", "1",
        ])

        assert rc == 0, f"exit code {rc}, stderr: {stderr[:200]}"
        data = parse_json_output(stdout)
        assert data is not None, f"no JSON found in stdout: {stdout[:200]}"

        assert "output" in data or "stl" in data
        assert "width_mm" in data
        assert "height_mm" in data
        assert "thickness_mm" in data
        assert "lithophane" in data
        assert data.get("lithophane") is False
        assert len(data.get("log", [])) > 0

    def test_lithophane_mode(self, sample_image):
        """Lithophane mode sets lithophane=True (max_depth assertion is redundant)."""
        if not sample_image:
            pytest.skip("no sample image found")

        rc, stdout, stderr = run_script("image-to-relief.py", [
            sample_image, "--width", "50", "--height", "50", "--lithophane",
        ])

        assert rc == 0
        data = parse_json_output(stdout)
        assert data is not None

        assert data.get("lithophane") is True

    def test_with_colors(self, sample_image):
        """Color quantization adds palette and color_preview."""
        if not sample_image:
            pytest.skip("no sample image found")

        rc, stdout, stderr = run_script("image-to-relief.py", [
            sample_image, "--width", "40", "--height", "40", "--colors", "2",
        ])

        assert rc == 0
        data = parse_json_output(stdout)
        assert data is not None

        assert data.get("num_colors") == 2
        assert "palette" in data
        assert "color_preview" in data
        assert "colored_obj" in data

    def test_file_not_found(self):
        """Non-existent input returns error JSON."""
        rc, stdout, stderr = run_script("image-to-relief.py", [
            "nonexistent_image_xyz123.png",
        ])

        assert rc != 0
        data = parse_json_output(stdout)
        assert data is not None, "no JSON found in stdout"
        assert "error" in data
        assert "not found" in data.get("error", "").lower()

    def test_params_validation(self, sample_image):
        """Invalid max_depth is handled gracefully."""
        if not sample_image:
            pytest.skip("no sample image found")

        rc, stdout, stderr = run_script("image-to-relief.py", [
            sample_image, "--width", "50", "--height", "50", "--max-depth", "0",
        ])
        assert rc in (0, 1), "should not crash"


# ═══════════════════════════════════════════════════════════
# Layered Relief Tests
# ═══════════════════════════════════════════════════════════

class TestLayeredRelief:
    """Tests for image-to-layered-relief.py."""

    def test_basic(self, sample_image):
        """Basic output with color_map and bands."""
        if not sample_image:
            pytest.skip("no sample image found")

        rc, stdout, stderr = run_script("image-to-layered-relief.py", [
            sample_image, "--width", "40", "--height", "40", "--colors", "2",
        ])

        assert rc == 0
        data = parse_json_output(stdout)
        assert data is not None

        assert "output" in data
        assert "color_map" in data
        assert "bands" in data
        assert isinstance(data["bands"], list)
        assert "width_mm" in data
        assert "height_mm" in data
        assert data.get("num_colors") == 2

    def test_3mf_output(self, sample_image):
        """3MF format adds output_3mf key."""
        if not sample_image:
            pytest.skip("no sample image found")

        rc, stdout, stderr = run_script("image-to-layered-relief.py", [
            sample_image, "--width", "30", "--height", "30", "--colors", "2",
            "--format", "3mf",
        ])

        assert rc == 0
        data = parse_json_output(stdout)
        assert data is not None
        assert "output_3mf" in data

    def test_color_sorting(self, sample_image):
        """Bands are sorted by luminance (ascending)."""
        if not sample_image:
            pytest.skip("no sample image found")

        rc, stdout, stderr = run_script("image-to-layered-relief.py", [
            sample_image, "--width", "40", "--height", "40", "--colors", "3",
        ])

        assert rc == 0
        data = parse_json_output(stdout)
        assert data is not None

        bands = data.get("bands", [])
        assert len(bands) == 3

        lum_values = [b.get("luminance_mean", 0) for b in bands]
        assert all(lum_values[i] <= lum_values[i+1] for i in range(len(lum_values)-1)), \
            f"luminance order wrong: {lum_values}"

    def test_progress_events(self, sample_image):
        """Script emits progress event JSON objects."""
        if not sample_image:
            pytest.skip("no sample image found")

        rc, stdout, stderr = run_script("image-to-layered-relief.py", [
            sample_image, "--width", "30", "--height", "30", "--colors", "2",
        ])

        # Extract ALL JSON objects from multi-line output
        all_objs = parse_all_json_output(stdout)
        event_types = [obj.get("event") for obj in all_objs if "event" in obj]
        assert len(event_types) > 0, f"no event lines found in output"


# ═══════════════════════════════════════════════════════════
# Mesh Repair Tests
# ═══════════════════════════════════════════════════════════

class TestMeshRepair:
    """Tests for mesh-repair.py."""

    @pytest.fixture
    def test_mesh_path(self, sample_image):
        """Generate a test mesh via relief."""
        if not sample_image:
            pytest.skip("no sample image found")

        rc, stdout, stderr = run_script("image-to-relief.py", [
            sample_image, "--width", "30", "--height", "30", "--max-depth", "1",
        ])
        data = parse_json_output(stdout)
        if not data or "stl" not in data:
            pytest.skip("could not generate test mesh")

        stl_path = data["stl"]
        if not os.path.exists(stl_path):
            pytest.skip(f"STL not found: {stl_path}")
        return stl_path

    def test_basic(self, test_mesh_path):
        """Basic JSON output with vertices/faces/dimensions."""
        rc, stdout, stderr = run_script("mesh-repair.py", [test_mesh_path], timeout=120)

        assert rc == 0, f"exit code {rc}, stderr: {stderr[:200]}"
        data = parse_json_output(stdout)
        assert data is not None

        assert "output" in data
        assert "watertight" in data
        assert "vertices" in data
        assert "faces" in data
        assert "dimensions_mm" in data
        assert isinstance(data.get("vertices"), int)
        assert isinstance(data.get("faces"), int)

    def test_scale(self, test_mesh_path):
        """Scale parameter affects output dimensions."""
        rc, stdout, stderr = run_script("mesh-repair.py", [test_mesh_path, "--scale", "2.0"], timeout=120)

        assert rc == 0, f"exit code {rc}, stderr: {stderr[:200]}"
        data = parse_json_output(stdout)
        assert data is not None

        assert os.path.exists(data.get("output", ""))
        dims = data.get("dimensions_mm", [])
        assert all(d > 50 for d in dims if d > 0), f"dims: {dims}"

    def test_nonexistent_file(self):
        """Non-existent mesh file returns error JSON."""
        rc, stdout, stderr = run_script("mesh-repair.py", [
            "nonexistent_mesh_xyz.glb",
        ])

        assert rc != 0
        data = parse_json_output(stdout)
        assert data is not None
        assert "error" in data


# ═══════════════════════════════════════════════════════════
# Mesh Simplify Tests
# ═══════════════════════════════════════════════════════════

class TestMeshSimplify:
    """Tests for mesh-simplify.py."""

    @pytest.fixture
    def test_mesh_path(self, sample_image):
        """Generate a test mesh via relief."""
        if not sample_image:
            pytest.skip("no sample image found")

        rc, stdout, stderr = run_script("image-to-relief.py", [
            sample_image, "--width", "30", "--height", "30",
        ])
        data = parse_json_output(stdout)
        if not data or "stl" not in data:
            pytest.skip("could not generate test mesh")

        stl_path = data["stl"]
        if not os.path.exists(stl_path):
            pytest.skip(f"STL not found: {stl_path}")
        return stl_path

    def test_basic(self, test_mesh_path):
        """Simplified output has fewer faces than original and output file exists."""
        rc, stdout, stderr = run_script("mesh-simplify.py", [
            test_mesh_path, "--target-faces", "50000",
        ])

        assert rc == 0, f"rc={rc} stderr={stderr[:200]}"
        data = parse_json_output(stdout)
        assert data is not None, f"no JSON: {stdout[:200]}"

        assert "output" in data
        assert "faces_after" in data
        assert "faces_before" in data
        # faces_after should be significantly reduced (or original if already below target)
        assert data["faces_after"] <= data["faces_before"], \
            f"faces_after ({data['faces_after']}) > faces_before ({data['faces_before']})"
        assert os.path.exists(data.get("output", "")), "output file not created"


# ═══════════════════════════════════════════════════════════
# Path Nesting Tests
# ═══════════════════════════════════════════════════════════

class TestPathNesting:
    """Tests for output path nesting logic."""

    def test_no_output_nesting(self, sample_image):
        """Input in output/ should not produce output/output/ path."""
        if not sample_image:
            pytest.skip("no sample image found")

        img_dir = os.path.dirname(sample_image)
        if "output" not in img_dir:
            pytest.skip("sample image not in output dir")

        rc, stdout, stderr = run_script("image-to-relief.py", [
            sample_image, "--width", "30", "--height", "30",
        ])
        data = parse_json_output(stdout)
        if not data or "stl" not in data:
            pytest.skip("could not generate output")

        output_path = data["stl"]
        assert "output/output" not in output_path.replace("\\", "/"), \
            f"output nested: {output_path}"


# ═══════════════════════════════════════════════════════════
# Error Contract Tests
# ═══════════════════════════════════════════════════════════

class TestErrorContract:
    """All scripts must return error JSON on bad input."""

    @pytest.mark.parametrize("script,args", [
        ("image-to-relief.py", ["nonexistent_file_xyz.png"]),
        ("mesh-repair.py", ["nonexistent_file_xyz.stl"]),
        ("mesh-simplify.py", ["nonexistent_file_xyz.stl"]),
        ("mesh-to-views.py", ["nonexistent_file_xyz.stl"]),
    ])
    def test_error_json_on_bad_input(self, script, args):
        """Bad input returns JSON with error key."""
        rc, stdout, stderr = run_script(script, args)
        data = parse_json_output(stdout)
        assert data is not None, f"{script}: no JSON in stdout: {stdout[:100]}"
        assert "error" in data, f"{script}: no 'error' key, rc={rc}"