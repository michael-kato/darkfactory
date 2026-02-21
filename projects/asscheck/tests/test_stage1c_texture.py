"""Unit tests for pipeline/stage1/texture.py.

All tests use mock objects — no Blender installation required.
"""
from __future__ import annotations

import pytest

from pipeline.schema import CheckStatus, StageStatus
from pipeline.stage1.texture import (
    ImageTextureNode,
    TextureBlenderContext,
    TextureConfig,
    TextureImage,
    TextureMaterial,
    check_textures,
)


# ---------------------------------------------------------------------------
# Mock primitives
# ---------------------------------------------------------------------------

class MockTextureImage(TextureImage):
    def __init__(
        self,
        name: str,
        size: tuple[int, int],
        depth: int = 32,
        colorspace_name: str = "sRGB",
    ) -> None:
        self._name = name
        self._size = size
        self._depth = depth
        self._colorspace = colorspace_name

    @property
    def name(self) -> str:
        return self._name

    @property
    def size(self) -> tuple[int, int]:
        return self._size

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def colorspace_name(self) -> str:
        return self._colorspace


class MockTextureMaterial(TextureMaterial):
    def __init__(self, name: str, nodes: list[ImageTextureNode]) -> None:
        self._name = name
        self._nodes = nodes

    @property
    def name(self) -> str:
        return self._name

    def image_texture_nodes(self) -> list[ImageTextureNode]:
        return self._nodes


class MockTextureBlenderContext(TextureBlenderContext):
    def __init__(
        self,
        materials: list[MockTextureMaterial],
        images: list[MockTextureImage],
    ) -> None:
        self._materials = materials
        self._images = images

    def materials(self) -> list[MockTextureMaterial]:
        return self._materials

    def images(self) -> list[MockTextureImage]:
        return self._images


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_image(
    name: str = "tex",
    size: tuple[int, int] = (1024, 1024),
    depth: int = 32,
    colorspace: str = "sRGB",
) -> MockTextureImage:
    return MockTextureImage(name, size, depth, colorspace)


def _make_node(
    socket_name: str = "Base Color",
    image_name: str = "tex",
    filepath_missing: bool = False,
) -> ImageTextureNode:
    return ImageTextureNode(
        socket_name=socket_name,
        image_name=image_name,
        filepath_missing=filepath_missing,
    )


def _make_ctx(
    materials: list[MockTextureMaterial] | None = None,
    images: list[MockTextureImage] | None = None,
) -> MockTextureBlenderContext:
    return MockTextureBlenderContext(
        materials=materials or [],
        images=images or [],
    )


def _default_config(**kwargs) -> TextureConfig:
    return TextureConfig(**kwargs)


# ---------------------------------------------------------------------------
# Tests — resolution_limit
# ---------------------------------------------------------------------------

class TestResolutionLimit:
    def test_2048_standard_passes(self) -> None:
        img = _make_image(size=(2048, 2048))
        ctx = _make_ctx(images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "resolution_limit")
        assert check.status == CheckStatus.PASS
        assert check.measured_value["violations"] == []

    def test_4096_standard_fails(self) -> None:
        img = _make_image(size=(4096, 4096))
        ctx = _make_ctx(images=[img])
        result = check_textures(ctx, _default_config(is_hero_asset=False))

        check = next(c for c in result.checks if c.name == "resolution_limit")
        assert check.status == CheckStatus.FAIL
        assert len(check.measured_value["violations"]) >= 1

    def test_4096_hero_passes(self) -> None:
        img = _make_image(size=(4096, 4096))
        ctx = _make_ctx(images=[img])
        result = check_textures(ctx, _default_config(is_hero_asset=True))

        check = next(c for c in result.checks if c.name == "resolution_limit")
        assert check.status == CheckStatus.PASS

    def test_violation_records_name_size_limit(self) -> None:
        img = _make_image(name="big_tex", size=(4096, 4096))
        ctx = _make_ctx(images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "resolution_limit")
        assert check.status == CheckStatus.FAIL
        v = check.measured_value["violations"][0]
        assert v["name"] == "big_tex"
        assert v["size"] == [4096, 4096]
        assert v["limit"] == 2048


# ---------------------------------------------------------------------------
# Tests — power_of_two
# ---------------------------------------------------------------------------

class TestPowerOfTwo:
    def test_512x512_passes(self) -> None:
        img = _make_image(size=(512, 512))
        ctx = _make_ctx(images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "power_of_two")
        assert check.status == CheckStatus.PASS
        assert check.measured_value["violations"] == []

    def test_512x384_fails(self) -> None:
        # 384 = 256 + 128, not a power of two
        img = _make_image(size=(512, 384))
        ctx = _make_ctx(images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "power_of_two")
        assert check.status == CheckStatus.FAIL
        assert len(check.measured_value["violations"]) >= 1

    def test_0x0_fails(self) -> None:
        img = _make_image(size=(0, 0))
        ctx = _make_ctx(images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "power_of_two")
        assert check.status == CheckStatus.FAIL

    def test_common_pot_sizes_pass(self) -> None:
        for sz in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096):
            img = _make_image(size=(sz, sz))
            ctx = _make_ctx(images=[img])
            result = check_textures(ctx, _default_config())
            check = next(c for c in result.checks if c.name == "power_of_two")
            assert check.status == CheckStatus.PASS, f"Failed for size {sz}×{sz}"

    def test_violation_records_name_and_size(self) -> None:
        img = _make_image(name="odd_tex", size=(512, 384))
        ctx = _make_ctx(images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "power_of_two")
        v = check.measured_value["violations"][0]
        assert v["name"] == "odd_tex"
        assert v["size"] == [512, 384]


# ---------------------------------------------------------------------------
# Tests — missing_textures
# ---------------------------------------------------------------------------

class TestMissingTextures:
    def test_resolved_reference_passes(self) -> None:
        node = _make_node(filepath_missing=False)
        mat = MockTextureMaterial("Mat", [node])
        ctx = _make_ctx(materials=[mat])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "missing_textures")
        assert check.status == CheckStatus.PASS
        assert check.measured_value == 0

    def test_missing_file_reference_fails(self) -> None:
        node = _make_node(filepath_missing=True)
        mat = MockTextureMaterial("Mat", [node])
        ctx = _make_ctx(materials=[mat])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "missing_textures")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value >= 1

    def test_mixed_references_counts_only_broken(self) -> None:
        good = _make_node(image_name="good", filepath_missing=False)
        bad1 = _make_node(image_name="bad1", filepath_missing=True)
        bad2 = _make_node(image_name="bad2", filepath_missing=True)
        mat = MockTextureMaterial("Mat", [good, bad1, bad2])
        ctx = _make_ctx(materials=[mat])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "missing_textures")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value == 2

    def test_no_materials_passes(self) -> None:
        ctx = _make_ctx()
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "missing_textures")
        assert check.status == CheckStatus.PASS


# ---------------------------------------------------------------------------
# Tests — color_space
# ---------------------------------------------------------------------------

class TestColorSpace:
    def test_albedo_with_non_color_is_warning(self) -> None:
        node = ImageTextureNode(
            socket_name="albedo",
            image_name="albedo_tex",
            filepath_missing=False,
        )
        mat = MockTextureMaterial("Mat", [node])
        img = MockTextureImage("albedo_tex", (1024, 1024), 32, "Non-Color")
        ctx = _make_ctx(materials=[mat], images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "color_space")
        assert check.status == CheckStatus.WARNING
        assert len(check.measured_value["violations"]) >= 1
        v = check.measured_value["violations"][0]
        assert v["name"] == "albedo_tex"
        assert v["expected"] == "sRGB"
        assert v["actual"] == "Non-Color"

    def test_roughness_with_srgb_is_warning(self) -> None:
        node = ImageTextureNode(
            socket_name="Roughness",
            image_name="rough_tex",
            filepath_missing=False,
        )
        mat = MockTextureMaterial("Mat", [node])
        img = MockTextureImage("rough_tex", (1024, 1024), 24, "sRGB")
        ctx = _make_ctx(materials=[mat], images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "color_space")
        assert check.status == CheckStatus.WARNING
        v = check.measured_value["violations"][0]
        assert v["expected"] == "Non-Color"
        assert v["actual"] == "sRGB"

    def test_albedo_with_srgb_passes(self) -> None:
        node = ImageTextureNode(
            socket_name="Base Color",
            image_name="color_tex",
            filepath_missing=False,
        )
        mat = MockTextureMaterial("Mat", [node])
        img = MockTextureImage("color_tex", (1024, 1024), 32, "sRGB")
        ctx = _make_ctx(materials=[mat], images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "color_space")
        assert check.status == CheckStatus.PASS

    def test_normal_with_non_color_passes(self) -> None:
        node = ImageTextureNode(
            socket_name="normal",
            image_name="normal_tex",
            filepath_missing=False,
        )
        mat = MockTextureMaterial("Mat", [node])
        img = MockTextureImage("normal_tex", (1024, 1024), 24, "Non-Color")
        ctx = _make_ctx(materials=[mat], images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "color_space")
        assert check.status == CheckStatus.PASS

    def test_normal_with_linear_passes(self) -> None:
        node = ImageTextureNode(
            socket_name="normal",
            image_name="normal_tex",
            filepath_missing=False,
        )
        mat = MockTextureMaterial("Mat", [node])
        img = MockTextureImage("normal_tex", (1024, 1024), 24, "Linear")
        ctx = _make_ctx(materials=[mat], images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "color_space")
        assert check.status == CheckStatus.PASS

    def test_unrecognized_socket_skipped(self) -> None:
        node = ImageTextureNode(
            socket_name="CustomSocket",
            image_name="mystery_tex",
            filepath_missing=False,
        )
        mat = MockTextureMaterial("Mat", [node])
        img = MockTextureImage("mystery_tex", (1024, 1024), 32, "sRGB")
        ctx = _make_ctx(materials=[mat], images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "color_space")
        assert check.status == CheckStatus.PASS
        assert check.measured_value["violations"] == []

    def test_warning_does_not_fail_stage(self) -> None:
        node = ImageTextureNode(
            socket_name="albedo",
            image_name="albedo_tex",
            filepath_missing=False,
        )
        mat = MockTextureMaterial("Mat", [node])
        img = MockTextureImage("albedo_tex", (1024, 1024), 32, "Non-Color")
        ctx = _make_ctx(materials=[mat], images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "color_space")
        assert check.status == CheckStatus.WARNING
        assert result.status != StageStatus.FAIL


# ---------------------------------------------------------------------------
# Tests — texture_count
# ---------------------------------------------------------------------------

class TestTextureCount:
    def test_within_limit_passes(self) -> None:
        nodes = [_make_node(image_name=f"tex{i}") for i in range(8)]
        mat = MockTextureMaterial("Mat", nodes)
        ctx = _make_ctx(materials=[mat])
        result = check_textures(ctx, _default_config(max_textures_per_material=8))

        check = next(c for c in result.checks if c.name == "texture_count")
        assert check.status == CheckStatus.PASS

    def test_ten_nodes_on_material_exceeds_limit_of_8(self) -> None:
        nodes = [_make_node(image_name=f"tex{i}") for i in range(10)]
        mat = MockTextureMaterial("OverloadedMat", nodes)
        ctx = _make_ctx(materials=[mat])
        result = check_textures(ctx, _default_config(max_textures_per_material=8))

        check = next(c for c in result.checks if c.name == "texture_count")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value["max"] == 10
        assert check.measured_value["material"] == "OverloadedMat"

    def test_reports_worst_offender(self) -> None:
        mat_a = MockTextureMaterial("A", [_make_node(image_name="t1")])
        mat_b = MockTextureMaterial("B", [_make_node(image_name=f"t{i}") for i in range(10)])
        ctx = _make_ctx(materials=[mat_a, mat_b])
        result = check_textures(ctx, _default_config(max_textures_per_material=8))

        check = next(c for c in result.checks if c.name == "texture_count")
        assert check.measured_value["material"] == "B"

    def test_no_materials_passes(self) -> None:
        ctx = _make_ctx()
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "texture_count")
        assert check.status == CheckStatus.PASS


# ---------------------------------------------------------------------------
# Tests — channel_depth
# ---------------------------------------------------------------------------

class TestChannelDepth:
    def test_depth_24_passes(self) -> None:
        img = _make_image(depth=24)
        ctx = _make_ctx(images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "channel_depth")
        assert check.status == CheckStatus.PASS
        assert check.measured_value["images"] == []

    def test_depth_32_passes(self) -> None:
        img = _make_image(depth=32)
        ctx = _make_ctx(images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "channel_depth")
        assert check.status == CheckStatus.PASS

    def test_hdr_depth_is_warning(self) -> None:
        img = _make_image(name="hdr_tex", depth=96)  # HDR float
        ctx = _make_ctx(images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "channel_depth")
        assert check.status == CheckStatus.WARNING
        assert any(e["name"] == "hdr_tex" for e in check.measured_value["images"])

    def test_warning_does_not_fail_stage(self) -> None:
        img = _make_image(depth=96)
        ctx = _make_ctx(images=[img])
        result = check_textures(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "channel_depth")
        assert check.status == CheckStatus.WARNING
        assert result.status != StageStatus.FAIL


# ---------------------------------------------------------------------------
# Tests — stage result shape and no-short-circuit behaviour
# ---------------------------------------------------------------------------

class TestStageResultShape:
    def test_stage_name_is_texture(self) -> None:
        ctx = _make_ctx()
        result = check_textures(ctx, _default_config())
        assert result.name == "texture"

    def test_six_checks_always_run(self) -> None:
        ctx = _make_ctx()
        result = check_textures(ctx, _default_config())
        expected = {
            "missing_textures",
            "resolution_limit",
            "power_of_two",
            "texture_count",
            "channel_depth",
            "color_space",
        }
        assert {c.name for c in result.checks} == expected

    def test_all_checks_run_even_when_missing_textures_fails(self) -> None:
        node = _make_node(filepath_missing=True)
        mat = MockTextureMaterial("Mat", [node])
        ctx = _make_ctx(materials=[mat])
        result = check_textures(ctx, _default_config())

        assert len(result.checks) == 6
        assert result.status == StageStatus.FAIL

    def test_warning_only_checks_do_not_fail_stage(self) -> None:
        # Channel depth warning + color space warning → stage should PASS
        node = ImageTextureNode(
            socket_name="roughness",
            image_name="rough_tex",
            filepath_missing=False,
        )
        mat = MockTextureMaterial("Mat", [node])
        img = MockTextureImage("rough_tex", (1024, 1024), 96, "sRGB")
        ctx = _make_ctx(materials=[mat], images=[img])
        result = check_textures(ctx, _default_config())

        depth_check = next(c for c in result.checks if c.name == "channel_depth")
        cs_check = next(c for c in result.checks if c.name == "color_space")
        assert depth_check.status == CheckStatus.WARNING
        assert cs_check.status == CheckStatus.WARNING
        assert result.status == StageStatus.PASS

    def test_fail_check_causes_stage_fail(self) -> None:
        # resolution_limit FAIL → stage FAIL
        img = _make_image(size=(4096, 4096))  # exceeds standard 2048 limit
        ctx = _make_ctx(images=[img])
        result = check_textures(ctx, _default_config(is_hero_asset=False))
        assert result.status == StageStatus.FAIL
