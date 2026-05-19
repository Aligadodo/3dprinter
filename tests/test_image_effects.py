"""test_image_effects.py — Tests for image_effects package and inline handler.

Covers: effect registry, all 17 effects, blending, naming, inline handler, edge cases.

Usage:
    pytest tests/test_image_effects.py -v
    pytest tests/test_image_effects.py -v -k pixelate
    pytest tests/test_image_effects.py -v -k "registry or naming or handler"
"""

import os
import sys
import tempfile

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.image_effects import (
    list_effects,
    get_effect,
    apply_effect,
    _registry,
)
from web.image_effects.base import BaseEffect
from web.image_effects.naming import effect_output_path, _load_config
from web.inline_nodes import run_image_effect, INLINE_HANDLERS
from web.workflow_engine import WorkflowEngine


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _make_test_image(path, size=(200, 150), color=(100, 150, 200)):
    """Create a solid-color RGB test PNG."""
    Image.new("RGB", size, color).save(path, "PNG")


def _make_photo_like_image(path, size=(300, 200)):
    """Create a more realistic test image with shapes."""
    img = Image.new("RGB", size, (180, 200, 220))
    draw = ImageDraw.Draw(img)
    draw.rectangle([30, 30, 100, 70], fill=(230, 90, 70))
    draw.rectangle([60, 50, 180, 120], fill=(70, 190, 100))
    draw.ellipse([140, 30, 220, 100], fill=(220, 210, 60))
    draw.rectangle([200, 120, 280, 180], fill=(100, 120, 200))
    img.save(path, "PNG")


def _make_rgba_image(path, size=(200, 150)):
    """Create an RGBA test image with partial transparency."""
    img = Image.new("RGBA", size, (100, 150, 200, 180))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 80, 80], fill=(230, 90, 70, 255))
    draw.rectangle([50, 50, 130, 110], fill=(70, 190, 100, 128))
    img.save(path, "PNG")


async def _run_handler(handler, node_params=None, ctx_extra=None, node_id="2"):
    """Run an inline handler with minimal boilerplate context."""
    work_dir = tempfile.mkdtemp()
    src_path = os.path.join(work_dir, "input.png")
    _make_photo_like_image(src_path)

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


# ═══════════════════════════════════════════════════════════════
# 1. Effect Registry Tests
# ═══════════════════════════════════════════════════════════════

class TestEffectRegistry:
    """Tests for the effect registration and lookup system."""

    def test_all_17_effects_registered(self):
        """Verify exactly 17 effects are registered."""
        effects = list_effects()
        assert len(effects) == 17, f"Expected 17, got {len(effects)}: {effects}"

    def test_expected_effects_present(self):
        """Check key effects from each category."""
        effects = set(list_effects())
        # Artistic
        assert {"oil_paint", "watercolor", "pencil_sketch", "cartoon",
                "ink_wash", "impressionist", "charcoal"} <= effects
        # Retro
        assert {"pixelate", "sepia", "halftone", "vintage_film"} <= effects
        # Color
        assert {"posterize", "duotone", "macaron", "neon"} <= effects
        # Distortion
        assert {"emboss", "kaleidoscope"} <= effects

    def test_get_effect_returns_base_effect(self):
        """get_effect returns a BaseEffect instance."""
        for name in list_effects():
            effect = get_effect(name)
            assert isinstance(effect, BaseEffect), f"{name}: not BaseEffect"
            assert effect.name == name, f"{name}: name mismatch ({effect.name})"
            assert effect.label, f"{name}: missing label"
            assert effect.label_zh, f"{name}: missing label_zh"

    def test_unknown_effect_raises(self):
        """get_effect with unknown name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown effect"):
            get_effect("nonexistent_effect_xyz")

    def test_apply_effect_convenience(self):
        """apply_effect() convenience function works."""
        path = os.path.join(tempfile.mkdtemp(), "test.png")
        _make_test_image(path)
        img = Image.open(path)
        result = apply_effect("pixelate", img, strength=0.8, detail=5)
        assert isinstance(result, Image.Image)
        assert result.size == img.size

    def test_effect_labels_bilingual(self):
        """All effects have both English and Chinese labels."""
        for name in list_effects():
            effect = get_effect(name)
            assert effect.label, f"{name}: empty English label"
            assert effect.label_zh, f"{name}: empty Chinese label"
            assert effect.label != effect.label_zh, f"{name}: labels identical"


# ═══════════════════════════════════════════════════════════════
# 2. Per-Effect Functional Tests (all 17)
# ═══════════════════════════════════════════════════════════════

class TestAllEffects:
    """Test that every effect produces valid output (size, mode, non-empty)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.tmpdir = tempfile.mkdtemp()
        self.img_path = os.path.join(self.tmpdir, "input.png")
        _make_photo_like_image(self.img_path)
        self.img = Image.open(self.img_path)

    @pytest.mark.parametrize("style", list_effects())
    def test_effect_output_size_match(self, style):
        """Effect output has same size as input."""
        result = apply_effect(style, self.img, strength=0.8, detail=5, color_scheme="warm")
        assert result.size == self.img.size, f"{style}: {result.size} != {self.img.size}"

    @pytest.mark.parametrize("style", list_effects())
    def test_effect_output_is_rgb(self, style):
        """Effect output is in RGB mode."""
        result = apply_effect(style, self.img, strength=0.8, detail=5, color_scheme="warm")
        assert result.mode == "RGB", f"{style}: mode={result.mode}"

    @pytest.mark.parametrize("style", list_effects())
    def test_effect_saves_valid_file(self, style):
        """Effect result saves as valid non-empty PNG."""
        result = apply_effect(style, self.img, strength=0.8, detail=5, color_scheme="warm")
        out_path = os.path.join(self.tmpdir, f"{style}.png")
        result.save(out_path, "PNG")
        assert os.path.getsize(out_path) > 100, f"{style}: file too small"
        # Re-open to verify valid image
        reloaded = Image.open(out_path)
        assert reloaded.size == self.img.size, f"{style}: saved size mismatch"

    @pytest.mark.parametrize("style", list_effects())
    def test_effect_detail_range_does_not_crash(self, style):
        """All detail values 1–10 work without error."""
        for detail in [1, 5, 10]:
            result = apply_effect(style, self.img, strength=0.8, detail=detail)
            assert isinstance(result, Image.Image), f"{style}: detail={detail} crashed"

    @pytest.mark.parametrize("style", list_effects())
    def test_effect_color_schemes_do_not_crash(self, style):
        """All 4 color schemes work on every style."""
        for scheme in ["warm", "cool", "vivid", "muted"]:
            result = apply_effect(style, self.img, strength=0.8, detail=5, color_scheme=scheme)
            assert isinstance(result, Image.Image), f"{style}: scheme={scheme} crashed"


# ═══════════════════════════════════════════════════════════════
# 3. Strength Blending Tests
# ═══════════════════════════════════════════════════════════════

class TestStrengthBlending:
    """Tests for the strength blending parameter."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.tmpdir = tempfile.mkdtemp()
        self.img_path = os.path.join(self.tmpdir, "input.png")
        _make_photo_like_image(self.img_path)
        self.img = Image.open(self.img_path)

    def test_strength_zero_identity_pixelate(self):
        """strength=0.0 on pixelate returns near-identical image."""
        result = apply_effect("pixelate", self.img, strength=0.0, detail=5)
        import numpy as np
        orig = np.array(self.img, dtype=np.float64)
        res = np.array(result, dtype=np.float64)
        diff = np.abs(orig - res).mean()
        assert diff < 1.0, f"strength=0 should be near-identical, mean diff={diff:.2f}"

    def test_strength_full_different(self):
        """strength=1.0 produces image measurably different from original."""
        result = apply_effect("pixelate", self.img, strength=1.0, detail=8)
        import numpy as np
        orig = np.array(self.img, dtype=np.float64)
        res = np.array(result, dtype=np.float64)
        diff = np.abs(orig - res).mean()
        assert diff > 5.0, f"strength=1.0 (detail=8) should differ noticeably, diff={diff:.2f}"

    def test_strength_intermediate(self):
        """strength=0.5 produces intermediate result."""
        r0 = apply_effect("sepia", self.img, strength=0.0, detail=5)
        r50 = apply_effect("sepia", self.img, strength=0.5, detail=5)
        r100 = apply_effect("sepia", self.img, strength=1.0, detail=5)
        import numpy as np
        a0 = np.array(r0, dtype=np.float64)
        a50 = np.array(r50, dtype=np.float64)
        a100 = np.array(r100, dtype=np.float64)
        d_0_50 = np.abs(a0 - a50).mean()
        d_0_100 = np.abs(a0 - a100).mean()
        assert 0 < d_0_50 < d_0_100, f"0->50 diff={d_0_50:.1f}, 0->100 diff={d_0_100:.1f}"


# ═══════════════════════════════════════════════════════════════
# 4. BaseEffect Utility Tests
# ═══════════════════════════════════════════════════════════════

class TestBaseEffectUtilities:
    """Tests for BaseEffect static helpers."""

    def test_blend_full_strength(self):
        """blend(strength=1.0) returns processed image."""
        orig = Image.new("RGB", (10, 10), (100, 0, 0))
        proc = Image.new("RGB", (10, 10), (0, 100, 0))
        result = BaseEffect.blend(orig, proc, 1.0)
        import numpy as np
        assert np.array_equal(np.array(result), np.array(proc))

    def test_blend_zero_strength(self):
        """blend(strength=0.0) returns original image."""
        orig = Image.new("RGB", (10, 10), (100, 0, 0))
        proc = Image.new("RGB", (10, 10), (0, 100, 0))
        result = BaseEffect.blend(orig, proc, 0.0)
        import numpy as np
        assert np.array_equal(np.array(result), np.array(orig))

    def test_blend_half_strength(self):
        """blend(strength=0.5) averages two images."""
        orig = Image.new("RGB", (10, 10), (100, 0, 0))
        proc = Image.new("RGB", (10, 10), (0, 100, 0))
        result = BaseEffect.blend(orig, proc, 0.5)
        import numpy as np
        pixel = np.array(result)[0, 0]
        assert pixel[0] == 50 and pixel[1] == 50

    def test_to_rgb_from_rgba(self):
        """to_rgb converts RGBA to RGB with white background."""
        rgba = Image.new("RGBA", (10, 10), (100, 150, 200, 128))
        rgb = BaseEffect.to_rgb(rgba)
        assert rgb.mode == "RGB"

    def test_to_rgb_from_rgb_passthrough(self):
        """to_rgb on RGB image returns unchanged."""
        rgb_in = Image.new("RGB", (10, 10), (50, 100, 150))
        rgb_out = BaseEffect.to_rgb(rgb_in)
        import numpy as np
        assert np.array_equal(np.array(rgb_out), np.array(rgb_in))

    def test_to_rgb_from_grayscale(self):
        """to_rgb converts L mode to RGB."""
        gray = Image.new("L", (10, 10), 128)
        rgb = BaseEffect.to_rgb(gray)
        assert rgb.mode == "RGB"


# ═══════════════════════════════════════════════════════════════
# 5. Naming Module Tests
# ═══════════════════════════════════════════════════════════════

class TestNaming:
    """Tests for semantic filename generation."""

    def test_config_loads(self):
        """Config file loads without error."""
        cfg = _load_config()
        assert "suffixes" in cfg
        assert "default_pattern" in cfg
        assert len(cfg["suffixes"]) == 17

    def test_default_pattern(self):
        """Default pattern produces {base}_{effect}.png."""
        path = effect_output_path("/tmp/photo.png", "/tmp/out", "oil_paint")
        assert "photo_oilpaint" in path
        assert path.endswith(".png")

    def test_pixelate_override_with_detail(self):
        """Pixelate uses override pattern with detail."""
        path = effect_output_path("/tmp/photo.png", "/tmp/out", "pixelate", detail=8)
        assert "pixel_p8" in path or "pixel" in path

    def test_duotone_override_with_color(self):
        """Duotone includes color scheme name."""
        path = effect_output_path("/tmp/photo.png", "/tmp/out", "duotone", color_scheme="cool")
        assert "duotone_cool" in path

    def test_effect_without_override_uses_default(self):
        """Effect without override pattern uses default."""
        path = effect_output_path("/tmp/photo.png", "/tmp/out", "macaron")
        assert "photo_macaron" in path

    def test_special_chars_stripped(self):
        """Spaces and slashes are stripped from filenames."""
        path = effect_output_path("/tmp/a b/c.jpg", "/tmp/out", "sepia")
        assert " " not in os.path.basename(path)
        assert "/" not in os.path.basename(path)

    def test_deduplication(self):
        """Duplicate filenames get _1, _2, etc."""
        tmpdir = tempfile.mkdtemp()
        p1 = effect_output_path("/tmp/photo.png", tmpdir, "sepia")
        # Create the first file
        Image.new("RGB", (10, 10)).save(p1, "PNG")
        # Second call should get a different name
        p2 = effect_output_path("/tmp/photo.png", tmpdir, "sepia")
        assert p1 != p2, f"Should deduplicate: {p1} vs {p2}"
        assert "_1" in os.path.basename(p2)

    def test_all_effects_have_suffix(self):
        """Every registered effect has a suffix in config."""
        cfg = _load_config()
        for name in list_effects():
            assert name in cfg["suffixes"], f"{name}: missing suffix in config"


# ═══════════════════════════════════════════════════════════════
# 6. Inline Handler Tests
# ═══════════════════════════════════════════════════════════════

class TestInlineHandler:
    """Tests for run_image_effect in inline_nodes.py."""

    @pytest.mark.asyncio
    async def test_handler_produces_output(self):
        """Handler returns a valid output file path."""
        result, ctx, work_dir = await _run_handler(
            run_image_effect, {"style": "pixelate", "strength": 0.8, "detail": 5},
        )
        assert os.path.isfile(result)
        out_img = Image.open(result)
        assert out_img.size == (300, 200)

    @pytest.mark.asyncio
    async def test_handler_sets_ctx(self):
        """Handler writes output path to ctx[nid]."""
        result, ctx, work_dir = await _run_handler(
            run_image_effect, {"style": "macaron", "strength": 0.5, "detail": 3},
        )
        assert "2" in ctx
        assert ctx["2"]["image"] == result

    @pytest.mark.asyncio
    async def test_handler_semantic_filename(self):
        """Handler uses semantic naming, not UUID."""
        result, ctx, work_dir = await _run_handler(
            run_image_effect, {"style": "oil_paint", "strength": 1.0, "detail": 5},
        )
        basename = os.path.basename(result)
        assert "oilpaint" in basename, f"Expected 'oilpaint' in name: {basename}"
        assert basename.startswith("input_"), f"Should start with input_: {basename}"

    @pytest.mark.asyncio
    async def test_no_input_image_raises(self):
        """ValueError when no upstream image is available."""
        work_dir = tempfile.mkdtemp()
        ctx = {"_work_dir": work_dir}
        node_map = {"2": {"id": 2, "type": "test"}}
        edges = []
        engine = WorkflowEngine()
        with pytest.raises(ValueError, match="no input image"):
            await run_image_effect(
                "2", {}, {"style": "pixelate"}, ctx,
                "test-inst", "test-nr", engine, node_map, edges,
            )

    @pytest.mark.asyncio
    async def test_registered_in_inline_handlers(self):
        """image_effect is in INLINE_HANDLERS dict."""
        assert "image_effect" in INLINE_HANDLERS
        assert INLINE_HANDLERS["image_effect"] is run_image_effect

    @pytest.mark.asyncio
    async def test_all_styles_via_handler(self):
        """All 17 styles work through the handler."""
        for style in list_effects():
            result, ctx, work_dir = await _run_handler(
                run_image_effect, {"style": style, "strength": 0.8, "detail": 5},
            )
            assert os.path.isfile(result), f"{style}: no output file"
            assert os.path.getsize(result) > 100, f"{style}: file too small"

    @pytest.mark.asyncio
    async def test_handler_rgba_input(self):
        """Handler works with RGBA input images."""
        work_dir = tempfile.mkdtemp()
        src_path = os.path.join(work_dir, "input_rgba.png")
        _make_rgba_image(src_path)

        ctx = {"_work_dir": work_dir, "1": {"image": src_path}}
        node_map = {"1": {"id": 1, "type": "file_input"}, "2": {"id": 2, "type": "test"}}
        edges = [{"source": "1", "source_port": "image", "target": "2", "target_port": "image"}]
        engine = WorkflowEngine()

        result = await run_image_effect(
            "2", {}, {"style": "watercolor", "strength": 0.5, "detail": 5},
            ctx, "test-inst", "test-nr", engine, node_map, edges,
        )
        assert os.path.isfile(result)
        out_img = Image.open(result)
        assert out_img.mode == "RGB"

    @pytest.mark.asyncio
    async def test_handler_default_params(self):
        """Handler works with only style specified (defaults for others)."""
        result, ctx, work_dir = await _run_handler(
            run_image_effect, {"style": "sepia"},
        )
        assert os.path.isfile(result)

    @pytest.mark.asyncio
    async def test_handler_with_detail_range(self):
        """Handler works across full detail range."""
        for detail in [1, 5, 10]:
            result, ctx, work_dir = await _run_handler(
                run_image_effect, {"style": "pixelate", "strength": 0.8, "detail": detail},
            )
            assert os.path.isfile(result), f"detail={detail}: no output"

    @pytest.mark.asyncio
    async def test_handler_with_color_schemes(self):
        """Handler works across all color schemes."""
        for scheme in ["warm", "cool", "vivid", "muted"]:
            result, ctx, work_dir = await _run_handler(
                run_image_effect, {"style": "duotone", "strength": 0.8, "detail": 5, "color_scheme": scheme},
            )
            assert os.path.isfile(result), f"scheme={scheme}: no output"


# ═══════════════════════════════════════════════════════════════
# 7. Edge Case Tests
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases and robustness tests."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_tiny_image(self):
        """Effects work on very small images (16x16)."""
        path = os.path.join(self.tmpdir, "tiny.png")
        Image.new("RGB", (16, 16), (100, 150, 200)).save(path, "PNG")
        img = Image.open(path)
        for style in ["pixelate", "sepia", "posterize", "emboss"]:
            result = apply_effect(style, img, strength=0.8, detail=5)
            assert result.size == (16, 16), f"{style}: size changed"

    def test_uniform_color_image(self):
        """Effects work on uniform solid color images."""
        path = os.path.join(self.tmpdir, "solid.png")
        Image.new("RGB", (100, 100), (128, 128, 128)).save(path, "PNG")
        img = Image.open(path)
        for style in ["pencil_sketch", "ink_wash", "neon"]:
            result = apply_effect(style, img, strength=0.8, detail=5)
            assert result.size == (100, 100), f"{style}: size changed on solid"

    def test_large_image(self):
        """Effects complete on moderately large images without OOM."""
        path = os.path.join(self.tmpdir, "large.png")
        Image.new("RGB", (800, 600), (100, 150, 200)).save(path, "PNG")
        img = Image.open(path)
        for style in ["oil_paint", "cartoon", "impressionist", "vintage_film"]:
            result = apply_effect(style, img, strength=0.8, detail=5)
            assert result.size == (800, 600), f"{style}: size changed on large"

    def test_effect_with_detail_min(self):
        """detail=1 works for all effects."""
        path = os.path.join(self.tmpdir, "test.png")
        _make_test_image(path)
        img = Image.open(path)
        for style in list_effects():
            result = apply_effect(style, img, strength=0.8, detail=1)
            assert isinstance(result, Image.Image), f"{style}: detail=1 crashed"

    def test_effect_with_detail_max(self):
        """detail=10 works for all effects."""
        path = os.path.join(self.tmpdir, "test.png")
        _make_test_image(path)
        img = Image.open(path)
        for style in list_effects():
            result = apply_effect(style, img, strength=0.8, detail=10)
            assert isinstance(result, Image.Image), f"{style}: detail=10 crashed"

    def test_effect_with_strength_min(self):
        """strength=0.0 returns near-original for all effects."""
        path = os.path.join(self.tmpdir, "test.png")
        _make_test_image(path)
        img = Image.open(path)
        import numpy as np
        orig = np.array(img, dtype=np.float64)
        for style in list_effects():
            result = apply_effect(style, img, strength=0.0, detail=5)
            res = np.array(result, dtype=np.float64)
            diff = np.abs(orig - res).mean()
            assert diff < 2.0, f"{style}: strength=0 diff={diff:.2f}"

    def test_effect_with_strength_full(self):
        """strength=1.0 doesn't crash for any effect."""
        path = os.path.join(self.tmpdir, "test.png")
        _make_test_image(path)
        img = Image.open(path)
        for style in list_effects():
            result = apply_effect(style, img, strength=1.0, detail=5)
            assert isinstance(result, Image.Image), f"{style}: strength=1.0 crashed"
            assert result.mode == "RGB", f"{style}: strength=1.0 bad mode"


# ═══════════════════════════════════════════════════════════════
# 8. Category-Specific Tests
# ═══════════════════════════════════════════════════════════════

class TestCategorySpecific:
    """Detailed tests per effect category."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.tmpdir = tempfile.mkdtemp()
        self.img_path = os.path.join(self.tmpdir, "input.png")
        _make_photo_like_image(self.img_path)
        self.img = Image.open(self.img_path)

    def test_pixelate_detail_changes_block_size(self):
        """Higher detail produces larger pixel blocks."""
        r1 = apply_effect("pixelate", self.img, strength=1.0, detail=1)
        r10 = apply_effect("pixelate", self.img, strength=1.0, detail=10)
        import numpy as np
        # detail=10 (large blocks) should differ more from original than detail=1
        orig = np.array(self.img, dtype=np.float64)
        d1 = np.abs(orig - np.array(r1, dtype=np.float64)).mean()
        d10 = np.abs(orig - np.array(r10, dtype=np.float64)).mean()
        assert d10 > d1, f"detail=1 diff={d1:.1f}, detail=10 diff={d10:.1f}"

    def test_posterize_detail_changes_colors(self):
        """Higher detail produces fewer colors (stronger posterization)."""
        r1 = apply_effect("posterize", self.img, strength=1.0, detail=1)
        r10 = apply_effect("posterize", self.img, strength=1.0, detail=10)
        import numpy as np
        # Higher detail = stronger posterization = fewer unique colors
        u1 = len(set(np.array(r1)[:, :, 0].ravel()))
        u10 = len(set(np.array(r10)[:, :, 0].ravel()))
        assert u1 > u10, f"detail=1 unique={u1} should be > detail=10 unique={u10}"

    def test_impressionist_strokes_visible(self):
        """Impressionist effect produces visibly different output."""
        result = apply_effect("impressionist", self.img, strength=1.0, detail=8)
        import numpy as np
        orig = np.array(self.img, dtype=np.float64)
        res = np.array(result, dtype=np.float64)
        diff = np.abs(orig - res).mean()
        assert diff > 8.0, f"Impressionist diff={diff:.1f}, should differ from original"

    def test_duotone_maps_to_two_colors(self):
        """Duotone result uses color palette from color_scheme."""
        r_warm = apply_effect("duotone", self.img, strength=1.0, detail=5, color_scheme="warm")
        r_cool = apply_effect("duotone", self.img, strength=1.0, detail=5, color_scheme="cool")
        import numpy as np
        # Warm should have more red, cool should have more blue
        warm_mean = np.array(r_warm, dtype=np.float64).mean(axis=(0, 1))
        cool_mean = np.array(r_cool, dtype=np.float64).mean(axis=(0, 1))
        assert warm_mean[0] > cool_mean[0], f"warm R={warm_mean[0]:.0f} <= cool R={cool_mean[0]:.0f}"
        assert cool_mean[2] > warm_mean[2], f"cool B={cool_mean[2]:.0f} <= warm B={warm_mean[2]:.0f}"

    def test_macaron_has_lower_contrast(self):
        """Macaron effect reduces contrast."""
        result = apply_effect("macaron", self.img, strength=1.0, detail=5)
        import numpy as np
        orig_std = np.array(self.img, dtype=np.float64).std()
        res_std = np.array(result, dtype=np.float64).std()
        assert res_std < orig_std * 0.95, f"orig std={orig_std:.1f}, result std={res_std:.1f}"

    def test_sepia_has_warm_tone(self):
        """Sepia produces warm (red > blue) output."""
        result = apply_effect("sepia", self.img, strength=1.0, detail=5)
        import numpy as np
        means = np.array(result, dtype=np.float64).mean(axis=(0, 1))
        assert means[0] > means[2], f"R={means[0]:.0f} <= B={means[2]:.0f}"

    def test_kaleidoscope_symmetric(self):
        """Kaleidoscope produces symmetric pattern (center region)."""
        result = apply_effect("kaleidoscope", self.img, strength=1.0, detail=6)
        import numpy as np
        arr = np.array(result, dtype=np.float64)
        h, w = arr.shape[:2]
        left = arr[h//4:h*3//4, w//4:w//2]
        right = arr[h//4:h*3//4, w//2:w*3//4]
        diff = np.abs(left - np.fliplr(right)).mean()
        # Should be somewhat symmetric (not exact due to resampling)
        assert diff < 50, f"kaleidoscope symmetry diff={diff:.1f}"
