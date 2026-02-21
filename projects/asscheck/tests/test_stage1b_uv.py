"""Unit tests for pipeline/stage1/uv.py.

All tests use mock objects — no Blender installation required.
"""
from __future__ import annotations

import pytest

from pipeline.schema import CheckStatus, StageStatus
from pipeline.stage1.uv import (
    UVBlenderContext,
    UVConfig,
    UVMeshObject,
    check_uvs,
    _Tri,
)


# ---------------------------------------------------------------------------
# Mock primitives
# ---------------------------------------------------------------------------

class MockUVMeshObject(UVMeshObject):
    def __init__(
        self,
        name: str,
        layer_names: list[str],
        loops: dict[str, list[tuple[float, float]]],
        triangles: dict[str, list[_Tri]],
        world_area: float = 1.0,
    ) -> None:
        self._name = name
        self._layer_names = layer_names
        self._loops = loops
        self._triangles = triangles
        self._world_area = world_area

    @property
    def name(self) -> str:
        return self._name

    def uv_layer_names(self) -> list[str]:
        return self._layer_names

    def uv_loops(self, layer_name: str) -> list[tuple[float, float]]:
        return self._loops.get(layer_name, [])

    def uv_triangles(self, layer_name: str) -> list[_Tri]:
        return self._triangles.get(layer_name, [])

    def world_surface_area(self) -> float:
        return self._world_area


class MockUVBlenderContext(UVBlenderContext):
    def __init__(self, objects: list[MockUVMeshObject]) -> None:
        self._objects = objects

    def mesh_objects(self) -> list[MockUVMeshObject]:
        return self._objects


# ---------------------------------------------------------------------------
# Shared UV data fixtures
# ---------------------------------------------------------------------------

# A simple non-overlapping right triangle in UV space.
#   Area = 0.5 * 0.5 * 0.5 / 2 = 0.125  (base=0.5, height=0.5, area=0.125)
_TRI_A: _Tri = ((0.0, 0.0), (0.5, 0.0), (0.0, 0.5))

# A triangle that overlaps _TRI_A (vertex (0.1, 0.1) is inside _TRI_A).
_TRI_OVERLAP: _Tri = ((0.1, 0.1), (0.6, 0.1), (0.1, 0.6))

# A triangle that does NOT overlap _TRI_A.
_TRI_SEPARATE: _Tri = ((0.6, 0.6), (1.0, 0.6), (0.6, 1.0))


def _make_object(
    name: str = "Mesh",
    layer_names: list[str] | None = None,
    loops: list[tuple[float, float]] | None = None,
    triangles: list[_Tri] | None = None,
    world_area: float = 1.0,
) -> MockUVMeshObject:
    if layer_names is None:
        layer_names = ["UVMap"]
    if loops is None:
        loops = [_TRI_A[0], _TRI_A[1], _TRI_A[2]]
    if triangles is None:
        triangles = [_TRI_A]
    return MockUVMeshObject(
        name=name,
        layer_names=layer_names,
        loops={"UVMap": loops},
        triangles={"UVMap": triangles},
        world_area=world_area,
    )


def _default_config(**kwargs) -> UVConfig:
    return UVConfig(**kwargs)


# ---------------------------------------------------------------------------
# Tests — missing_uvs
# ---------------------------------------------------------------------------

class TestMissingUVs:
    def test_object_with_uv_layer_passes(self) -> None:
        ctx = MockUVBlenderContext([_make_object()])
        result = check_uvs(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "missing_uvs")
        assert check.status == CheckStatus.PASS
        assert check.measured_value == 0

    def test_object_with_no_uv_layers_fails(self) -> None:
        obj = MockUVMeshObject(name="NoUV", layer_names=[], loops={}, triangles={})
        ctx = MockUVBlenderContext([obj])
        result = check_uvs(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "missing_uvs")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value >= 1


# ---------------------------------------------------------------------------
# Tests — uv_bounds
# ---------------------------------------------------------------------------

class TestUVBounds:
    def test_all_uvs_in_range_passes(self) -> None:
        obj = _make_object(loops=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)])
        ctx = MockUVBlenderContext([obj])
        result = check_uvs(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "uv_bounds")
        assert check.status == CheckStatus.PASS
        assert check.measured_value == 0

    def test_uv_at_1_5_fails_with_count_ge_1(self) -> None:
        obj = _make_object(loops=[(0.0, 0.0), (1.5, 0.5), (0.0, 1.0)])
        ctx = MockUVBlenderContext([obj])
        result = check_uvs(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "uv_bounds")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value >= 1

    def test_uv_exactly_at_boundary_passes(self) -> None:
        obj = _make_object(loops=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)])
        ctx = MockUVBlenderContext([obj])
        result = check_uvs(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "uv_bounds")
        assert check.status == CheckStatus.PASS

    def test_negative_uv_fails(self) -> None:
        obj = _make_object(loops=[(-0.1, 0.5)])
        ctx = MockUVBlenderContext([obj])
        result = check_uvs(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "uv_bounds")
        assert check.status == CheckStatus.FAIL


# ---------------------------------------------------------------------------
# Tests — uv_overlap
# ---------------------------------------------------------------------------

class TestUVOverlap:
    def test_two_overlapping_triangles_fails(self) -> None:
        obj = MockUVMeshObject(
            name="Mesh",
            layer_names=["UVMap"],
            loops={"UVMap": []},
            triangles={"UVMap": [_TRI_A, _TRI_OVERLAP]},
        )
        ctx = MockUVBlenderContext([obj])
        result = check_uvs(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "uv_overlap")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value >= 1

    def test_non_overlapping_triangles_passes(self) -> None:
        obj = MockUVMeshObject(
            name="Mesh",
            layer_names=["UVMap"],
            loops={"UVMap": []},
            triangles={"UVMap": [_TRI_A, _TRI_SEPARATE]},
        )
        ctx = MockUVBlenderContext([obj])
        result = check_uvs(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "uv_overlap")
        assert check.status == CheckStatus.PASS

    def test_single_triangle_no_overlap(self) -> None:
        obj = MockUVMeshObject(
            name="Mesh",
            layer_names=["UVMap"],
            loops={"UVMap": []},
            triangles={"UVMap": [_TRI_A]},
        )
        ctx = MockUVBlenderContext([obj])
        result = check_uvs(ctx, _default_config())

        check = next(c for c in result.checks if c.name == "uv_overlap")
        assert check.status == CheckStatus.PASS
        assert check.measured_value == 0


# ---------------------------------------------------------------------------
# Tests — texel_density
# ---------------------------------------------------------------------------

class TestTexelDensity:
    def test_density_in_range_passes(self) -> None:
        # _TRI_A area = 0.125; world_area = 1.0 → density = 0.125
        # Config range (0.0, 1.0) includes 0.125 → PASS
        obj = _make_object(triangles=[_TRI_A], world_area=1.0)
        ctx = MockUVBlenderContext([obj])
        config = _default_config(texel_density_target_px_per_m=(0.0, 1.0))
        result = check_uvs(ctx, config)

        check = next(c for c in result.checks if c.name == "texel_density")
        assert check.status == CheckStatus.PASS
        assert result.status == StageStatus.PASS

    def test_density_out_of_range_is_warning_not_fail(self) -> None:
        # _TRI_A area = 0.125; world_area = 1.0 → density = 0.125
        # Config range (0.5, 1.0) excludes 0.125 → WARNING
        obj = _make_object(triangles=[_TRI_A], world_area=1.0)
        ctx = MockUVBlenderContext([obj])
        config = _default_config(texel_density_target_px_per_m=(0.5, 1.0))
        result = check_uvs(ctx, config)

        check = next(c for c in result.checks if c.name == "texel_density")
        assert check.status == CheckStatus.WARNING
        assert result.status != StageStatus.FAIL
        assert check.measured_value["outlier_count"] >= 1

    def test_measured_value_has_required_keys(self) -> None:
        obj = _make_object(triangles=[_TRI_A], world_area=1.0)
        ctx = MockUVBlenderContext([obj])
        result = check_uvs(ctx, _default_config(texel_density_target_px_per_m=(0.0, 1.0)))

        check = next(c for c in result.checks if c.name == "texel_density")
        assert isinstance(check.measured_value, dict)
        assert {"min", "max", "mean", "outlier_count"} <= check.measured_value.keys()


# ---------------------------------------------------------------------------
# Tests — lightmap_uv2
# ---------------------------------------------------------------------------

class TestLightmapUV2:
    def test_require_false_yields_skipped(self) -> None:
        ctx = MockUVBlenderContext([_make_object()])
        config = _default_config(require_lightmap_uv2=False)
        result = check_uvs(ctx, config)

        check = next(c for c in result.checks if c.name == "lightmap_uv2")
        assert check.status == CheckStatus.SKIPPED

    def test_require_true_missing_layer_fails(self) -> None:
        # Object has "UVMap" but NOT "UVMap2"
        obj = _make_object(layer_names=["UVMap"])
        ctx = MockUVBlenderContext([obj])
        config = _default_config(require_lightmap_uv2=True, lightmap_layer_name="UVMap2")
        result = check_uvs(ctx, config)

        check = next(c for c in result.checks if c.name == "lightmap_uv2")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value["present"] is False

    def test_require_true_with_layer_no_overlaps_passes(self) -> None:
        obj = MockUVMeshObject(
            name="Mesh",
            layer_names=["UVMap", "UVMap2"],
            loops={"UVMap": [], "UVMap2": []},
            triangles={"UVMap": [_TRI_A], "UVMap2": [_TRI_A, _TRI_SEPARATE]},
        )
        ctx = MockUVBlenderContext([obj])
        config = _default_config(require_lightmap_uv2=True)
        result = check_uvs(ctx, config)

        check = next(c for c in result.checks if c.name == "lightmap_uv2")
        assert check.status == CheckStatus.PASS
        assert check.measured_value["present"] is True
        assert check.measured_value["overlap_count"] == 0

    def test_require_true_with_overlapping_uv2_fails(self) -> None:
        obj = MockUVMeshObject(
            name="Mesh",
            layer_names=["UVMap", "UVMap2"],
            loops={"UVMap": [], "UVMap2": []},
            triangles={"UVMap": [_TRI_A], "UVMap2": [_TRI_A, _TRI_OVERLAP]},
        )
        ctx = MockUVBlenderContext([obj])
        config = _default_config(require_lightmap_uv2=True)
        result = check_uvs(ctx, config)

        check = next(c for c in result.checks if c.name == "lightmap_uv2")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value["overlap_count"] >= 1


# ---------------------------------------------------------------------------
# Tests — stage result shape and no-short-circuit behaviour
# ---------------------------------------------------------------------------

class TestStageResultShape:
    def test_stage_name_is_uv(self) -> None:
        ctx = MockUVBlenderContext([_make_object()])
        result = check_uvs(ctx, _default_config())
        assert result.name == "uv"

    def test_five_checks_always_run(self) -> None:
        ctx = MockUVBlenderContext([_make_object()])
        result = check_uvs(ctx, _default_config())
        expected = {
            "missing_uvs",
            "uv_bounds",
            "uv_overlap",
            "texel_density",
            "lightmap_uv2",
        }
        assert {c.name for c in result.checks} == expected

    def test_all_checks_run_even_when_missing_uvs_fails(self) -> None:
        obj = MockUVMeshObject(name="NoUV", layer_names=[], loops={}, triangles={})
        ctx = MockUVBlenderContext([obj])
        result = check_uvs(ctx, _default_config())

        assert len(result.checks) == 5
        assert result.status == StageStatus.FAIL

    def test_warning_does_not_fail_stage(self) -> None:
        # Only texel density out of range → WARNING; all other checks PASS.
        obj = _make_object(triangles=[_TRI_A], world_area=1.0)
        ctx = MockUVBlenderContext([obj])
        config = _default_config(texel_density_target_px_per_m=(0.5, 1.0))
        result = check_uvs(ctx, config)

        td = next(c for c in result.checks if c.name == "texel_density")
        assert td.status == CheckStatus.WARNING
        assert result.status == StageStatus.PASS
