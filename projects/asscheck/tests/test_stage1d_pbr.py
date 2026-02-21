"""Unit tests for pipeline/stage1/pbr.py.

All tests use mock objects — no Blender installation required.
"""
from __future__ import annotations

import pytest

from pipeline.schema import CheckStatus, StageStatus
from pipeline.stage1.pbr import (
    NormalMapData,
    PBRBlenderContext,
    PBRConfig,
    PBRMaterial,
    PBRMeshObject,
    check_pbr,
)


# ---------------------------------------------------------------------------
# Mock primitives
# ---------------------------------------------------------------------------

class MockPBRMeshObject(PBRMeshObject):
    def __init__(self, name: str, material_slot_count: int) -> None:
        self._name = name
        self._slot_count = material_slot_count

    @property
    def name(self) -> str:
        return self._name

    @property
    def material_slot_count(self) -> int:
        return self._slot_count


class MockPBRMaterial(PBRMaterial):
    def __init__(
        self,
        name: str,
        has_nodes: bool = True,
        uses_principled_bsdf: bool = True,
        uses_spec_gloss: bool = False,
        orphan_image_node_count: int = 0,
        has_node_cycles: bool = False,
        albedo_pixels: list[float] | None = None,
        metalness_pixels: list[float] | None = None,
        roughness_pixels: list[float] | None = None,
        normal_map_data: list[NormalMapData] | None = None,
    ) -> None:
        self._name = name
        self._has_nodes = has_nodes
        self._uses_principled_bsdf = uses_principled_bsdf
        self._uses_spec_gloss = uses_spec_gloss
        self._orphan_count = orphan_image_node_count
        self._has_cycles = has_node_cycles
        self._albedo_pixels = albedo_pixels
        self._metalness_pixels = metalness_pixels
        self._roughness_pixels = roughness_pixels
        self._normal_map_data = normal_map_data or []

    @property
    def name(self) -> str:
        return self._name

    def has_nodes(self) -> bool:
        return self._has_nodes

    def uses_principled_bsdf(self) -> bool:
        return self._uses_principled_bsdf

    def uses_spec_gloss(self) -> bool:
        return self._uses_spec_gloss

    def orphan_image_node_count(self) -> int:
        return self._orphan_count

    def has_node_cycles(self) -> bool:
        return self._has_cycles

    def albedo_pixels(self) -> list[float] | None:
        return self._albedo_pixels

    def metalness_pixels(self) -> list[float] | None:
        return self._metalness_pixels

    def roughness_pixels(self) -> list[float] | None:
        return self._roughness_pixels

    def normal_map_data(self) -> list[NormalMapData]:
        return self._normal_map_data


class MockPBRBlenderContext(PBRBlenderContext):
    def __init__(
        self,
        materials: list[MockPBRMaterial] | None = None,
        mesh_objects: list[MockPBRMeshObject] | None = None,
    ) -> None:
        self._materials = materials or []
        self._mesh_objects = mesh_objects or []

    def materials(self) -> list[MockPBRMaterial]:
        return self._materials

    def mesh_objects(self) -> list[MockPBRMeshObject]:
        return self._mesh_objects


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_config(**kwargs) -> PBRConfig:
    return PBRConfig(**kwargs)


def _make_ctx(
    materials: list[MockPBRMaterial] | None = None,
    mesh_objects: list[MockPBRMeshObject] | None = None,
) -> MockPBRBlenderContext:
    return MockPBRBlenderContext(materials=materials, mesh_objects=mesh_objects)


def _solid_rgba(value: float, count: int) -> list[float]:
    """Return a flat RGBA pixel list where all channels are *value*."""
    return [value, value, value, 1.0] * count


# ---------------------------------------------------------------------------
# Tests — pbr_workflow
# ---------------------------------------------------------------------------

class TestPBRWorkflow:
    def test_principled_bsdf_passes(self) -> None:
        mat = MockPBRMaterial("Mat", uses_principled_bsdf=True, uses_spec_gloss=False)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "pbr_workflow")
        assert check.status == CheckStatus.PASS
        assert check.measured_value == []

    def test_no_principled_bsdf_fails(self) -> None:
        mat = MockPBRMaterial("BadMat", uses_principled_bsdf=False)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "pbr_workflow")
        assert check.status == CheckStatus.FAIL
        assert "BadMat" in check.measured_value

    def test_spec_gloss_material_fails(self) -> None:
        mat = MockPBRMaterial("GlossyMat", uses_principled_bsdf=True, uses_spec_gloss=True)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "pbr_workflow")
        assert check.status == CheckStatus.FAIL
        assert "GlossyMat" in check.measured_value

    def test_no_materials_passes(self) -> None:
        ctx = _make_ctx()
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "pbr_workflow")
        assert check.status == CheckStatus.PASS

    def test_mixed_materials_reports_non_compliant(self) -> None:
        good = MockPBRMaterial("Good", uses_principled_bsdf=True)
        bad = MockPBRMaterial("Bad", uses_principled_bsdf=False)
        ctx = _make_ctx(materials=[good, bad])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "pbr_workflow")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value == ["Bad"]


# ---------------------------------------------------------------------------
# Tests — material_slots
# ---------------------------------------------------------------------------

class TestMaterialSlots:
    def test_within_limit_passes(self) -> None:
        obj = MockPBRMeshObject("Mesh", material_slot_count=3)
        ctx = _make_ctx(mesh_objects=[obj])
        result = check_pbr(ctx, _default_config(max_material_slots=3))

        check = next(c for c in result.checks if c.name == "material_slots")
        assert check.status == CheckStatus.PASS

    def test_four_slots_max_three_fails(self) -> None:
        obj = MockPBRMeshObject("Mesh", material_slot_count=4)
        ctx = _make_ctx(mesh_objects=[obj])
        result = check_pbr(ctx, _default_config(max_material_slots=3))

        check = next(c for c in result.checks if c.name == "material_slots")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value["max"] == 4
        assert check.measured_value["object"] == "Mesh"

    def test_no_mesh_objects_passes(self) -> None:
        ctx = _make_ctx()
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "material_slots")
        assert check.status == CheckStatus.PASS

    def test_reports_worst_offender(self) -> None:
        obj_a = MockPBRMeshObject("A", material_slot_count=2)
        obj_b = MockPBRMeshObject("B", material_slot_count=5)
        ctx = _make_ctx(mesh_objects=[obj_a, obj_b])
        result = check_pbr(ctx, _default_config(max_material_slots=3))

        check = next(c for c in result.checks if c.name == "material_slots")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value["object"] == "B"
        assert check.measured_value["max"] == 5


# ---------------------------------------------------------------------------
# Tests — albedo_range
# ---------------------------------------------------------------------------

class TestAlbedoRange:
    def test_pixels_in_range_no_warning(self) -> None:
        # 0.5 → sRGB 128, within [30, 240]
        pixels = _solid_rgba(0.5, 100)
        mat = MockPBRMaterial("Mat", albedo_pixels=pixels)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "albedo_range")
        assert check.status == CheckStatus.PASS
        assert check.measured_value["fraction_out_of_range"] == 0.0
        assert check.measured_value["sample_count"] == 100

    def test_twenty_percent_below_threshold_triggers_warning(self) -> None:
        # 0.1 → sRGB 26, below threshold 30; 0.5 → sRGB 128, in range
        bad_pixels = _solid_rgba(0.1, 20)   # 20 out-of-range pixels
        good_pixels = _solid_rgba(0.5, 80)  # 80 in-range pixels
        pixels = bad_pixels + good_pixels
        mat = MockPBRMaterial("Mat", albedo_pixels=pixels)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "albedo_range")
        assert check.status == CheckStatus.WARNING
        assert check.measured_value["fraction_out_of_range"] == pytest.approx(0.2)
        assert check.measured_value["sample_count"] == 100

    def test_warning_does_not_fail_stage(self) -> None:
        bad_pixels = _solid_rgba(0.1, 50)
        good_pixels = _solid_rgba(0.5, 50)
        pixels = bad_pixels + good_pixels
        mat = MockPBRMaterial("Mat", albedo_pixels=pixels)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "albedo_range")
        assert check.status == CheckStatus.WARNING
        assert result.status != StageStatus.FAIL

    def test_no_albedo_texture_passes(self) -> None:
        mat = MockPBRMaterial("Mat", albedo_pixels=None)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "albedo_range")
        assert check.status == CheckStatus.PASS
        assert check.measured_value["sample_count"] == 0

    def test_pixels_at_upper_boundary_passes(self) -> None:
        # 240/255 ≈ 0.9412; round(0.9412 * 255) = 240 → in range
        pixels = _solid_rgba(240 / 255, 50)
        mat = MockPBRMaterial("Mat", albedo_pixels=pixels)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "albedo_range")
        assert check.status == CheckStatus.PASS


# ---------------------------------------------------------------------------
# Tests — metalness_binary
# ---------------------------------------------------------------------------

class TestMetalnessBinary:
    def test_binary_values_no_warning(self) -> None:
        # 0.02 → below threshold 0.1 (not gradient); 0.98 → above 0.9 (not gradient)
        near_zero = _solid_rgba(0.02, 50)
        near_one = _solid_rgba(0.98, 50)
        pixels = near_zero + near_one
        mat = MockPBRMaterial("Mat", metalness_pixels=pixels)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "metalness_binary")
        assert check.status == CheckStatus.PASS
        assert check.measured_value["fraction_gradient"] == pytest.approx(0.0)

    def test_fifty_percent_gradient_triggers_warning(self) -> None:
        # 0.5 → in (0.1, 0.9) gradient zone; 0.0 → not gradient
        gradient = _solid_rgba(0.5, 50)
        binary = _solid_rgba(0.0, 50)
        pixels = gradient + binary
        mat = MockPBRMaterial("Mat", metalness_pixels=pixels)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "metalness_binary")
        assert check.status == CheckStatus.WARNING
        assert check.measured_value["fraction_gradient"] == pytest.approx(0.5)

    def test_warning_does_not_fail_stage(self) -> None:
        pixels = _solid_rgba(0.5, 100)
        mat = MockPBRMaterial("Mat", metalness_pixels=pixels)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "metalness_binary")
        assert check.status == CheckStatus.WARNING
        assert result.status != StageStatus.FAIL

    def test_no_metalness_texture_passes(self) -> None:
        mat = MockPBRMaterial("Mat", metalness_pixels=None)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "metalness_binary")
        assert check.status == CheckStatus.PASS


# ---------------------------------------------------------------------------
# Tests — roughness_range
# ---------------------------------------------------------------------------

class TestRoughnessRange:
    def test_varied_roughness_passes(self) -> None:
        # Mix of values — no extreme dominance
        pixels = _solid_rgba(0.3, 50) + _solid_rgba(0.7, 50)
        mat = MockPBRMaterial("Mat", roughness_pixels=pixels)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "roughness_range")
        assert check.status == CheckStatus.PASS

    def test_all_pure_zero_warns(self) -> None:
        pixels = _solid_rgba(0.0, 100)
        mat = MockPBRMaterial("Mat", roughness_pixels=pixels)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "roughness_range")
        assert check.status == CheckStatus.WARNING
        assert check.measured_value["fraction_pure_zero"] == pytest.approx(1.0)

    def test_all_pure_one_warns(self) -> None:
        pixels = _solid_rgba(1.0, 100)
        mat = MockPBRMaterial("Mat", roughness_pixels=pixels)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "roughness_range")
        assert check.status == CheckStatus.WARNING
        assert check.measured_value["fraction_pure_one"] == pytest.approx(1.0)

    def test_warning_does_not_fail_stage(self) -> None:
        pixels = _solid_rgba(0.0, 100)
        mat = MockPBRMaterial("Mat", roughness_pixels=pixels)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "roughness_range")
        assert check.status == CheckStatus.WARNING
        assert result.status != StageStatus.FAIL


# ---------------------------------------------------------------------------
# Tests — normal_map
# ---------------------------------------------------------------------------

class TestNormalMap:
    def test_correct_colorspace_and_blue_dominant_passes(self) -> None:
        # B-dominant pixels (typical normal map): R=0.5, G=0.5, B=0.8
        pixels = [0.5, 0.5, 0.8, 1.0] * 10
        nm = NormalMapData("normal_tex", "Non-Color", pixels)
        mat = MockPBRMaterial("Mat", normal_map_data=[nm])
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "normal_map")
        assert check.status == CheckStatus.PASS
        assert check.measured_value["colorspace_violations"] == []
        assert check.measured_value["channel_violations"] == []

    def test_srgb_colorspace_fails(self) -> None:
        pixels = [0.5, 0.5, 0.8, 1.0] * 10
        nm = NormalMapData("normal_tex", "sRGB", pixels)
        mat = MockPBRMaterial("Mat", normal_map_data=[nm])
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "normal_map")
        assert check.status == CheckStatus.FAIL
        assert "normal_tex" in check.measured_value["colorspace_violations"]

    def test_r_dominant_pixels_fails(self) -> None:
        # R-dominant pixels: R=0.8, G=0.3, B=0.3
        pixels = [0.8, 0.3, 0.3, 1.0] * 10
        nm = NormalMapData("normal_tex", "Non-Color", pixels)
        mat = MockPBRMaterial("Mat", normal_map_data=[nm])
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "normal_map")
        assert check.status == CheckStatus.FAIL
        assert "normal_tex" in check.measured_value["channel_violations"]

    def test_g_dominant_pixels_fails(self) -> None:
        # G-dominant: R=0.3, G=0.9, B=0.5
        pixels = [0.3, 0.9, 0.5, 1.0] * 10
        nm = NormalMapData("normal_tex", "Non-Color", pixels)
        mat = MockPBRMaterial("Mat", normal_map_data=[nm])
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "normal_map")
        assert check.status == CheckStatus.FAIL
        assert "normal_tex" in check.measured_value["channel_violations"]

    def test_no_normal_maps_passes(self) -> None:
        mat = MockPBRMaterial("Mat", normal_map_data=[])
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "normal_map")
        assert check.status == CheckStatus.PASS

    def test_colorspace_and_channel_violations_both_recorded(self) -> None:
        # sRGB + R-dominant → both violations
        pixels = [0.8, 0.3, 0.3, 1.0] * 10
        nm = NormalMapData("nm_tex", "sRGB", pixels)
        mat = MockPBRMaterial("Mat", normal_map_data=[nm])
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "normal_map")
        assert check.status == CheckStatus.FAIL
        assert "nm_tex" in check.measured_value["colorspace_violations"]
        assert "nm_tex" in check.measured_value["channel_violations"]


# ---------------------------------------------------------------------------
# Tests — node_graph
# ---------------------------------------------------------------------------

class TestNodeGraph:
    def test_clean_graph_passes(self) -> None:
        mat = MockPBRMaterial(
            "Mat",
            has_nodes=True,
            uses_principled_bsdf=True,
            orphan_image_node_count=0,
            has_node_cycles=False,
        )
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "node_graph")
        assert check.status == CheckStatus.PASS
        assert check.measured_value == []

    def test_empty_material_slot_warns(self) -> None:
        mat = MockPBRMaterial("EmptyMat", has_nodes=False)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "node_graph")
        assert check.status == CheckStatus.WARNING
        assert any("EmptyMat" in issue for issue in check.measured_value)

    def test_orphan_image_node_warns(self) -> None:
        mat = MockPBRMaterial(
            "Mat",
            uses_principled_bsdf=True,
            orphan_image_node_count=2,
        )
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "node_graph")
        assert check.status == CheckStatus.WARNING

    def test_node_cycle_warns(self) -> None:
        mat = MockPBRMaterial("Mat", uses_principled_bsdf=True, has_node_cycles=True)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "node_graph")
        assert check.status == CheckStatus.WARNING
        assert any("cycle" in issue for issue in check.measured_value)

    def test_warning_does_not_fail_stage(self) -> None:
        mat = MockPBRMaterial("Mat", has_nodes=False)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "node_graph")
        assert check.status == CheckStatus.WARNING
        assert result.status != StageStatus.FAIL


# ---------------------------------------------------------------------------
# Tests — stage result shape and no-short-circuit behaviour
# ---------------------------------------------------------------------------

class TestStageResultShape:
    def test_stage_name_is_pbr(self) -> None:
        ctx = _make_ctx()
        result = check_pbr(ctx, _default_config())
        assert result.name == "pbr"

    def test_seven_checks_always_run(self) -> None:
        ctx = _make_ctx()
        result = check_pbr(ctx, _default_config())
        expected = {
            "pbr_workflow",
            "material_slots",
            "albedo_range",
            "metalness_binary",
            "roughness_range",
            "normal_map",
            "node_graph",
        }
        assert {c.name for c in result.checks} == expected

    def test_all_checks_run_even_when_pbr_workflow_fails(self) -> None:
        mat = MockPBRMaterial("Bad", uses_principled_bsdf=False)
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        assert len(result.checks) == 7
        wf = next(c for c in result.checks if c.name == "pbr_workflow")
        assert wf.status == CheckStatus.FAIL
        assert result.status == StageStatus.FAIL

    def test_warning_only_does_not_fail_stage(self) -> None:
        # Albedo + metalness warnings → stage should PASS
        bad_albedo = _solid_rgba(0.1, 50) + _solid_rgba(0.5, 50)
        gradient_metal = _solid_rgba(0.5, 100)
        mat = MockPBRMaterial(
            "Mat",
            albedo_pixels=bad_albedo,
            metalness_pixels=gradient_metal,
        )
        ctx = _make_ctx(materials=[mat])
        result = check_pbr(ctx, _default_config())

        albedo_check = next(c for c in result.checks if c.name == "albedo_range")
        metal_check = next(c for c in result.checks if c.name == "metalness_binary")
        assert albedo_check.status == CheckStatus.WARNING
        assert metal_check.status == CheckStatus.WARNING
        assert result.status == StageStatus.PASS

    def test_fail_check_causes_stage_fail(self) -> None:
        # material_slots FAIL → stage FAIL
        obj = MockPBRMeshObject("Mesh", material_slot_count=10)
        ctx = _make_ctx(mesh_objects=[obj])
        result = check_pbr(ctx, _default_config(max_material_slots=3))
        assert result.status == StageStatus.FAIL
