"""test_inline_nodes.py — Unit tests for inline image/mesh handlers.

Covers image resize/grayscale/crop/adjust/convert, remove_background,
mesh_transform, mesh_select.

Usage:
    pytest tests/test_inline_nodes.py -v
    pytest tests/test_inline_nodes.py -v -k resize
"""

import os
import sys
import tempfile
import uuid

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.inline_nodes import (
    run_image_resize,
    run_image_grayscale,
    run_image_crop,
    run_image_adjust,
    run_image_convert,
    run_remove_background,
    run_mesh_transform,
    run_mesh_select,
    _resolve_input,
    _resolve_input_file,
)
from web.workflow_engine import WorkflowEngine


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_test_image(path, size=(200, 150), color=(100, 150, 200)):
    """Create a simple RGB test PNG."""
    img = Image.new("RGB", size, color)
    img.save(path, "PNG")


def _make_test_image_rgba(path, size=(200, 150)):
    """Create an RGBA test PNG with partial transparency."""
    img = Image.new("RGBA", size, (100, 150, 200, 200))
    img.save(path, "PNG")


async def _run_handler(handler, node_params=None, ctx_extra=None, node_id="2"):
    """Run an inline handler with minimal boilerplate context."""
    work_dir = tempfile.mkdtemp()
    src_path = os.path.join(work_dir, "input.png")
    _make_test_image(src_path)

    ctx = {
        "_work_dir": work_dir,
        "1": {"image": src_path},
        **(ctx_extra or {}),
    }

    node_map = {
        "1": {"id": 1, "type": "file_input"},
        node_id: {"id": int(node_id), "type": "test"},
    }
    edges = [{"source": "1", "source_port": "image", "target": node_id, "target_port": "image"}]
    engine = WorkflowEngine()

    result = await handler(
        node_id, {}, node_params or {}, ctx,
        "test-instance", "test-node-run",
        engine, node_map, edges,
    )
    return result, ctx, work_dir


# ═══════════════════════════════════════════════════════════
# Image Resize Tests
# ═══════════════════════════════════════════════════════════

class TestImageResize:
    @pytest.mark.asyncio
    async def test_cover_mode(self):
        """Cover mode outputs the exact requested dimensions."""
        result, ctx, work_dir = await _run_handler(
            run_image_resize, {"width": 64, "height": 64, "fit": "cover"},
        )
        assert os.path.isfile(result)
        out_img = Image.open(result)
        assert out_img.size == (64, 64)

    @pytest.mark.asyncio
    async def test_contain_mode(self):
        """Contain mode preserves aspect ratio within bounds."""
        result, ctx, work_dir = await _run_handler(
            run_image_resize, {"width": 64, "height": 64, "fit": "contain"},
        )
        assert os.path.isfile(result)
        out_img = Image.open(result)
        # contain fits the image within 64x64 without changing aspect ratio
        # Source is 200x150 (4:3). Contain in 64x64 → width constrained
        assert out_img.size[0] <= 64 and out_img.size[1] <= 64
        # aspect ratio preserved: 200/150 = 1.333
        ratio = out_img.size[0] / out_img.size[1]
        assert abs(ratio - (200 / 150)) < 0.05

    @pytest.mark.asyncio
    async def test_stretch_mode(self):
        """Stretch mode forces exact target dimensions."""
        result, ctx, work_dir = await _run_handler(
            run_image_resize, {"width": 100, "height": 50, "fit": "stretch"},
        )
        assert os.path.isfile(result)
        out_img = Image.open(result)
        assert out_img.size == (100, 50)

    @pytest.mark.asyncio
    async def test_no_input_image_raises(self):
        """ValueError when no upstream image is available."""
        work_dir = tempfile.mkdtemp()
        ctx = {"_work_dir": work_dir}
        node_map = {"2": {"id": 2, "type": "test"}}
        edges = []
        engine = WorkflowEngine()
        with pytest.raises(ValueError, match="no input image"):
            await run_image_resize(
                "2", {}, {}, ctx, "test-inst", "test-nr",
                engine, node_map, edges,
            )

    @pytest.mark.asyncio
    async def test_ctx_output_set(self):
        """Handler sets ctx[nid] with output image path."""
        result, ctx, work_dir = await _run_handler(
            run_image_resize, {"width": 32, "height": 32},
        )
        assert "2" in ctx
        assert ctx["2"]["image"] == result


# ═══════════════════════════════════════════════════════════
# Image Grayscale Tests
# ═══════════════════════════════════════════════════════════

class TestImageGrayscale:
    @pytest.mark.asyncio
    async def test_luminosity(self):
        """Luminosity grayscale produces output file with same dimensions."""
        result, ctx, work_dir = await _run_handler(
            run_image_grayscale, {"method": "luminosity"},
        )
        assert os.path.isfile(result)
        out_img = Image.open(result)
        assert out_img.size == (200, 150)
        # Luminosity output should be grayscale ('L' mode or RGB gray)
        assert out_img.mode in ("L", "RGB")

    @pytest.mark.asyncio
    async def test_average_method(self):
        """Average grayscale method doesn't crash."""
        result, ctx, work_dir = await _run_handler(
            run_image_grayscale, {"method": "average"},
        )
        assert os.path.isfile(result)

    @pytest.mark.asyncio
    async def test_lightness_method(self):
        """Lightness method works on RGB images."""
        result, ctx, work_dir = await _run_handler(
            run_image_grayscale, {"method": "lightness"},
        )
        assert os.path.isfile(result)
        out_img = Image.open(result)
        assert out_img.size == (200, 150)

    @pytest.mark.asyncio
    async def test_red_channel(self):
        """Red channel extraction produces valid output."""
        result, ctx, work_dir = await _run_handler(
            run_image_grayscale, {"method": "red_channel"},
        )
        assert os.path.isfile(result)

    @pytest.mark.asyncio
    async def test_green_channel(self):
        """Green channel extraction produces valid output."""
        result, ctx, work_dir = await _run_handler(
            run_image_grayscale, {"method": "green_channel"},
        )
        assert os.path.isfile(result)

    @pytest.mark.asyncio
    async def test_blue_channel(self):
        """Blue channel extraction produces valid output."""
        result, ctx, work_dir = await _run_handler(
            run_image_grayscale, {"method": "blue_channel"},
        )
        assert os.path.isfile(result)


# ═══════════════════════════════════════════════════════════
# Image Crop Tests
# ═══════════════════════════════════════════════════════════

class TestImageCrop:
    @pytest.mark.asyncio
    async def test_basic_crop(self):
        """Crop to specified region."""
        result, ctx, work_dir = await _run_handler(
            run_image_crop, {"x": 10, "y": 10, "width": 80, "height": 60},
        )
        assert os.path.isfile(result)
        out_img = Image.open(result)
        assert out_img.size == (80, 60)

    @pytest.mark.asyncio
    async def test_bounds_clamped(self):
        """Crop bounds beyond image dimensions are clamped."""
        result, ctx, work_dir = await _run_handler(
            run_image_crop, {"x": -100, "y": -100, "width": 9999, "height": 9999},
        )
        assert os.path.isfile(result)
        out_img = Image.open(result)
        # Clamped to actual image bounds (200x150)
        assert out_img.size[0] <= 200
        assert out_img.size[1] <= 150
        assert out_img.size[0] > 0 and out_img.size[1] > 0

    @pytest.mark.asyncio
    async def test_aspect_ratio_1x1(self):
        """Aspect ratio 1:1 constraint applied, then clamped to image bounds."""
        result, ctx, work_dir = await _run_handler(
            run_image_crop, {"x": 0, "y": 0, "width": 150, "height": 150, "aspect_ratio": "1:1"},
        )
        assert os.path.isfile(result)
        out_img = Image.open(result)
        # After aspect ratio constraint and bounds clamping, result fits within source
        assert out_img.size[0] <= 200 and out_img.size[1] <= 150
        # 1:1 aspect ratio applied before clamping: with width=150, height becomes 150
        assert out_img.size[0] == out_img.size[1]


# ═══════════════════════════════════════════════════════════
# Image Adjust Tests
# ═══════════════════════════════════════════════════════════

class TestImageAdjust:
    @pytest.mark.asyncio
    async def test_identity(self):
        """brightness=0, contrast=1, saturation=1, sharpness=0 = identity."""
        result, ctx, work_dir = await _run_handler(
            run_image_adjust, {"brightness": 0, "contrast": 1, "saturation": 1, "sharpness": 0},
        )
        assert os.path.isfile(result)
        out_img = Image.open(result)
        assert out_img.size == (200, 150)

    @pytest.mark.asyncio
    async def test_brightness_increase(self):
        """Positive brightness doesn't crash."""
        result, ctx, work_dir = await _run_handler(
            run_image_adjust, {"brightness": 0.5},
        )
        assert os.path.isfile(result)

    @pytest.mark.asyncio
    async def test_contrast_boost(self):
        """Contrast > 1 doesn't crash and keeps dimensions."""
        result, ctx, work_dir = await _run_handler(
            run_image_adjust, {"contrast": 2.0},
        )
        assert os.path.isfile(result)
        out_img = Image.open(result)
        assert out_img.size == (200, 150)

    @pytest.mark.asyncio
    async def test_sharpness(self):
        """Sharpness > 0 doesn't crash."""
        result, ctx, work_dir = await _run_handler(
            run_image_adjust, {"sharpness": 1.0},
        )
        assert os.path.isfile(result)


# ═══════════════════════════════════════════════════════════
# Image Convert Tests
# ═══════════════════════════════════════════════════════════

class TestImageConvert:
    @pytest.mark.asyncio
    async def test_to_png(self):
        """PNG output produced."""
        result, ctx, work_dir = await _run_handler(
            run_image_convert, {"format": "png"},
        )
        assert os.path.isfile(result)
        assert result.lower().endswith(".png")

    @pytest.mark.asyncio
    async def test_to_jpeg(self):
        """JPEG output converts RGBA→RGB."""
        result, ctx, work_dir = await _run_handler(
            run_image_convert, {"format": "jpeg", "quality": 85},
        )
        assert os.path.isfile(result)
        assert result.lower().endswith(".jpg")
        out_img = Image.open(result)
        assert out_img.mode == "RGB"  # JPEG must be RGB, no alpha

    @pytest.mark.asyncio
    async def test_to_webp(self):
        """WebP output produced."""
        result, ctx, work_dir = await _run_handler(
            run_image_convert, {"format": "webp", "quality": 80},
        )
        assert os.path.isfile(result)
        assert result.lower().endswith(".webp")

    @pytest.mark.asyncio
    async def test_rgba_to_jpeg_handles_alpha(self):
        """RGBA source converted to JPEG strips alpha channel safely."""
        work_dir = tempfile.mkdtemp()
        src_path = os.path.join(work_dir, "input_rgba.png")
        _make_test_image_rgba(src_path)

        ctx = {"_work_dir": work_dir, "1": {"image": src_path}}
        node_map = {"1": {"id": 1, "type": "file_input"}, "2": {"id": 2, "type": "test"}}
        edges = [{"source": "1", "source_port": "image", "target": "2", "target_port": "image"}]
        engine = WorkflowEngine()

        result = await run_image_convert(
            "2", {}, {"format": "jpeg", "quality": 85}, ctx,
            "test-inst", "test-nr", engine, node_map, edges,
        )
        assert os.path.isfile(result)
        out_img = Image.open(result)
        assert out_img.mode == "RGB"


# ═══════════════════════════════════════════════════════════
# Remove Background Tests
# ═══════════════════════════════════════════════════════════

class TestRemoveBackground:
    @pytest.mark.asyncio
    async def test_no_rembg_gives_clear_error(self):
        """If rembg is not installed, RuntimeError is raised."""
        import importlib
        rembg_spec = importlib.util.find_spec("rembg")
        if rembg_spec is not None:
            pytest.skip("rembg is installed — test requires it absent")

        with pytest.raises(RuntimeError, match="rembg"):
            await _run_handler(run_remove_background, {})


# ═══════════════════════════════════════════════════════════
# _resolve_input / _resolve_input_file unit tests
# ═══════════════════════════════════════════════════════════

class TestResolveInput:
    def test_no_edge_map_returns_none(self):
        """If no edges connect to the node, returns None."""
        ctx = {"1": {"image": "/tmp/img.png"}}
        node_map = {"1": {"id": 1, "type": "file_input"}, "2": {"id": 2, "type": "test"}}
        edges = []
        engine = WorkflowEngine()
        result = _resolve_input("2", ctx, engine, node_map, edges)
        assert result is None

    def test_resolves_correctly(self):
        """Upstream file path resolved via edge map."""
        ctx = {"1": {"image": "/tmp/img.png"}}
        node_map = {"1": {"id": 1, "type": "file_input"}, "2": {"id": 2, "type": "test"}}
        edges = [{"source": "1", "source_port": "image", "target": "2", "target_port": "image"}]
        engine = WorkflowEngine()
        result = _resolve_input("2", ctx, engine, node_map, edges)
        # Returns None because /tmp/img.png doesn't exist
        assert result is None

    def test_resolve_input_file_finds_in_ctx(self):
        """_resolve_input_file scans ctx outputs for file paths."""
        work_dir = tempfile.mkdtemp()
        img_path = os.path.join(work_dir, "test.png")
        _make_test_image(img_path)
        ctx = {"1": {"image": img_path}}
        engine = WorkflowEngine()
        result = _resolve_input_file("2", {}, ctx, engine)
        assert result == img_path

    def test_resolve_input_file_no_match(self):
        """_resolve_input_file returns None when no file found."""
        ctx = {"_inputs": {}}
        engine = WorkflowEngine()
        result = _resolve_input_file("2", {}, ctx, engine)
        assert result is None


# ═══════════════════════════════════════════════════════════
# Mesh Transform Tests
# ═══════════════════════════════════════════════════════════

class TestMeshTransform:
    @pytest.fixture
    def mesh_setup(self):
        """Create a test mesh and context."""
        import numpy as np
        import trimesh

        work_dir = tempfile.mkdtemp()
        mesh = trimesh.creation.box(extents=[10, 10, 10])
        mesh_path = os.path.join(work_dir, "input.glb")
        mesh.export(mesh_path)

        ctx = {"_work_dir": work_dir, "1": {"mesh": mesh_path}}
        node_map = {"1": {"id": 1, "type": "mesh_transform"}, "2": {"id": 2, "type": "mesh_transform"}}
        edges = [{"source": "1", "source_port": "mesh", "target": "2", "target_port": "mesh"}]
        engine = WorkflowEngine()

        return mesh, mesh_path, ctx, node_map, edges, engine, work_dir

    @pytest.mark.asyncio
    async def test_translate(self, mesh_setup):
        """Translation changes mesh centroid."""
        mesh, mesh_path, ctx, node_map, edges, engine, work_dir = mesh_setup
        import trimesh

        orig_centroid = mesh.centroid.copy()

        result = await run_mesh_transform(
            "2", {}, {"tf_translate": "5,0,0", "tf_scale": "1.0"},
            ctx, "test-inst", "test-nr", engine, node_map, edges,
        )
        assert os.path.isfile(result)
        result_mesh = trimesh.load(result, force="mesh")
        new_centroid = result_mesh.centroid
        # X should have moved by ~5
        assert abs((new_centroid[0] - orig_centroid[0]) - 5.0) < 0.01

    @pytest.mark.asyncio
    async def test_scale(self, mesh_setup):
        """Scale changes mesh extents."""
        mesh, mesh_path, ctx, node_map, edges, engine, work_dir = mesh_setup
        import trimesh

        orig_extents = mesh.extents.copy()

        result = await run_mesh_transform(
            "2", {}, {"tf_scale": "2.0"},
            ctx, "test-inst", "test-nr", engine, node_map, edges,
        )
        assert os.path.isfile(result)
        result_mesh = trimesh.load(result, force="mesh")
        new_extents = result_mesh.extents
        # Extents should be ~2x
        for i in range(3):
            assert abs(new_extents[i] - orig_extents[i] * 2.0) < 0.1

    @pytest.mark.asyncio
    async def test_no_input_mesh_raises(self):
        """ValueError when no upstream mesh is available."""
        work_dir = tempfile.mkdtemp()
        ctx = {"_work_dir": work_dir}
        node_map = {"2": {"id": 2, "type": "mesh_transform"}}
        edges = []
        engine = WorkflowEngine()
        with pytest.raises(ValueError, match="no input mesh"):
            await run_mesh_transform(
                "2", {}, {}, ctx, "test-inst", "test-nr",
                engine, node_map, edges,
            )


# ═══════════════════════════════════════════════════════════
# Mesh Select Tests
# ═══════════════════════════════════════════════════════════

class TestMeshSelect:
    @pytest.fixture
    def mesh_select_setup(self):
        """Create a test mesh and context for selection."""
        import trimesh

        work_dir = tempfile.mkdtemp()
        mesh = trimesh.creation.box(extents=[10, 10, 10])
        mesh_path = os.path.join(work_dir, "input.glb")
        mesh.export(mesh_path)

        ctx = {"_work_dir": work_dir, "1": {"mesh": mesh_path}}
        node_map = {"1": {"id": 1, "type": "mesh_select"}, "2": {"id": 2, "type": "mesh_select"}}
        edges = [{"source": "1", "source_port": "mesh", "target": "2", "target_port": "mesh"}]
        engine = WorkflowEngine()

        return mesh, mesh_path, ctx, node_map, edges, engine, work_dir

    @pytest.mark.asyncio
    async def test_no_bbox_passthrough(self, mesh_select_setup):
        """Empty bbox passes through the original mesh."""
        mesh, mesh_path, ctx, node_map, edges, engine, work_dir = mesh_select_setup

        result = await run_mesh_select(
            "2", {}, {"sel_bbox": ""},
            ctx, "test-inst", "test-nr", engine, node_map, edges,
        )
        assert os.path.isfile(result)

    @pytest.mark.asyncio
    async def test_with_bbox_selects_region(self, mesh_select_setup):
        """Valid bbox that covers entire mesh selects all faces."""
        mesh, mesh_path, ctx, node_map, edges, engine, work_dir = mesh_select_setup

        # Box is centered at origin with extents 10 (-5 to 5). Use larger bbox.
        result = await run_mesh_select(
            "2", {}, {"sel_bbox": "-6,-6,-6,6,6,6"},
            ctx, "test-inst", "test-nr", engine, node_map, edges,
        )
        assert os.path.isfile(result)
        import trimesh
        result_mesh = trimesh.load(result, force="mesh")
        # Should have same number of faces as the original box (bbox covers all)
        assert len(result_mesh.faces) == len(mesh.faces)
        assert len(result_mesh.faces) > 0

    @pytest.mark.asyncio
    async def test_bbox_no_match_raises(self, mesh_select_setup):
        """Bbox that matches nothing raises ValueError."""
        mesh, mesh_path, ctx, node_map, edges, engine, work_dir = mesh_select_setup

        with pytest.raises(ValueError, match="No faces"):
            await run_mesh_select(
                "2", {}, {"sel_bbox": "100,100,100,101,101,101"},
                ctx, "test-inst", "test-nr", engine, node_map, edges,
            )
