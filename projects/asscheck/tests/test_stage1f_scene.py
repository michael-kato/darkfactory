"""Unit tests for pipeline/stage1/scene.py.

All tests use mock objects — no Blender installation required.
"""
from __future__ import annotations

import pytest

from pipeline.schema import CheckStatus, StageStatus
from pipeline.stage1.scene import (
    SceneArmatureObject,
    SceneBlenderContext,
    SceneConfig,
    SceneImage,
    SceneMeshObject,
    check_scene,
)


# ---------------------------------------------------------------------------
# Mock primitives
# ---------------------------------------------------------------------------

class MockMeshObject(SceneMeshObject):
    def __init__(
        self,
        name: str,
        triangle_count: int = 0,
        material_slot_count: int = 1,
    ) -> None:
        self._name = name
        self._triangle_count = triangle_count
        self._material_slot_count = material_slot_count

    @property
    def name(self) -> str:
        return self._name

    def triangle_count(self) -> int:
        return self._triangle_count

    def material_slot_count(self) -> int:
        return self._material_slot_count


class MockArmatureObject(SceneArmatureObject):
    def __init__(self, name: str, bone_count: int = 0) -> None:
        self._name = name
        self._bone_count = bone_count

    @property
    def name(self) -> str:
        return self._name

    def bone_count(self) -> int:
        return self._bone_count


class MockImage(SceneImage):
    def __init__(
        self,
        width: int,
        height: int,
        channels: int = 4,
        bit_depth: int = 8,
    ) -> None:
        self._width = width
        self._height = height
        self._channels = channels
        self._bit_depth = bit_depth

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def channels(self) -> int:
        return self._channels

    @property
    def bit_depth(self) -> int:
        return self._bit_depth


class MockSceneContext(SceneBlenderContext):
    def __init__(
        self,
        mesh_objects: list[MockMeshObject] | None = None,
        armature_objects: list[MockArmatureObject] | None = None,
        unique_images: list[MockImage] | None = None,
        orphan_counts: dict[str, int] | None = None,
    ) -> None:
        self._mesh_objects = mesh_objects or []
        self._armature_objects = armature_objects or []
        self._unique_images = unique_images or []
        self._orphan_counts = orphan_counts or {"meshes": 0, "materials": 0, "images": 0}

    def mesh_objects(self) -> list[MockMeshObject]:
        return self._mesh_objects

    def armature_objects(self) -> list[MockArmatureObject]:
        return self._armature_objects

    def unique_images(self) -> list[MockImage]:
        return self._unique_images

    def orphan_counts(self) -> dict[str, int]:
        return self._orphan_counts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NAMING_PATTERN = r"^[A-Z]{2,4}_[A-Za-z0-9_]+"
_LOD_SUFFIX = r"_LOD\d+$"
_COLLISION_SUFFIX = r"_Collision$"


def _config(**kwargs) -> SceneConfig:
    defaults = dict(
        object_naming_pattern=_NAMING_PATTERN,
        require_lod=False,
        require_collision=False,
        lod_suffix_pattern=_LOD_SUFFIX,
        collision_suffix_pattern=_COLLISION_SUFFIX,
    )
    defaults.update(kwargs)
    return SceneConfig(**defaults)


def _ctx(**kwargs) -> MockSceneContext:
    return MockSceneContext(**kwargs)


# ---------------------------------------------------------------------------
# Tests — naming_conventions
# ---------------------------------------------------------------------------

class TestNamingConventions:
    def test_all_valid_names_pass(self) -> None:
        objects = [MockMeshObject("ENV_Crate_Large")]
        ctx = _ctx(mesh_objects=objects)
        result, _ = check_scene(ctx, _config())

        check = next(c for c in result.checks if c.name == "naming_conventions")
        assert check.status == CheckStatus.PASS
        assert check.measured_value["count"] == 0

    def test_invalid_name_warns(self) -> None:
        objects = [MockMeshObject("crate")]
        ctx = _ctx(mesh_objects=objects)
        result, _ = check_scene(ctx, _config())

        check = next(c for c in result.checks if c.name == "naming_conventions")
        assert check.status == CheckStatus.WARNING
        assert "crate" in check.measured_value["violations"]
        assert check.measured_value["count"] == 1

    def test_mixed_names_warns_with_correct_count(self) -> None:
        objects = [
            MockMeshObject("ENV_Lamp_Base"),
            MockMeshObject("bad_name"),
            MockMeshObject("PROP_Chair"),
            MockMeshObject("123invalid"),
        ]
        ctx = _ctx(mesh_objects=objects)
        result, _ = check_scene(ctx, _config())

        check = next(c for c in result.checks if c.name == "naming_conventions")
        assert check.status == CheckStatus.WARNING
        assert check.measured_value["count"] == 2
        assert "bad_name" in check.measured_value["violations"]
        assert "123invalid" in check.measured_value["violations"]

    def test_warning_does_not_fail_stage(self) -> None:
        """naming_conventions is WARNING, not FAIL — should not cause stage FAIL."""
        objects = [MockMeshObject("bad")]
        ctx = _ctx(mesh_objects=objects)
        result, _ = check_scene(ctx, _config())

        check = next(c for c in result.checks if c.name == "naming_conventions")
        assert check.status == CheckStatus.WARNING
        assert result.status == StageStatus.PASS


# ---------------------------------------------------------------------------
# Tests — orphan_data
# ---------------------------------------------------------------------------

class TestOrphanData:
    def test_no_orphans_passes(self) -> None:
        ctx = _ctx(orphan_counts={"meshes": 0, "materials": 0, "images": 0})
        result, _ = check_scene(ctx, _config())

        check = next(c for c in result.checks if c.name == "orphan_data")
        assert check.status == CheckStatus.PASS
        assert check.measured_value == 0

    def test_two_orphan_materials_warns(self) -> None:
        ctx = _ctx(orphan_counts={"meshes": 0, "materials": 2, "images": 0})
        result, _ = check_scene(ctx, _config())

        check = next(c for c in result.checks if c.name == "orphan_data")
        assert check.status == CheckStatus.WARNING
        assert check.measured_value == 2

    def test_orphan_count_sums_all_types(self) -> None:
        ctx = _ctx(orphan_counts={"meshes": 1, "materials": 2, "images": 3})
        result, _ = check_scene(ctx, _config())

        check = next(c for c in result.checks if c.name == "orphan_data")
        assert check.status == CheckStatus.WARNING
        assert check.measured_value == 6

    def test_warning_does_not_fail_stage(self) -> None:
        ctx = _ctx(orphan_counts={"meshes": 0, "materials": 1, "images": 0})
        result, _ = check_scene(ctx, _config())

        check = next(c for c in result.checks if c.name == "orphan_data")
        assert check.status == CheckStatus.WARNING
        assert result.status == StageStatus.PASS


# ---------------------------------------------------------------------------
# Tests — lod_presence
# ---------------------------------------------------------------------------

class TestLodPresence:
    def test_not_required_skipped(self) -> None:
        ctx = _ctx()
        result, _ = check_scene(ctx, _config(require_lod=False))

        check = next(c for c in result.checks if c.name == "lod_presence")
        assert check.status == CheckStatus.SKIPPED

    def test_required_no_lod_fails(self) -> None:
        objects = [MockMeshObject("ENV_Crate_Large")]
        ctx = _ctx(mesh_objects=objects)
        result, _ = check_scene(ctx, _config(require_lod=True))

        check = next(c for c in result.checks if c.name == "lod_presence")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value == 0
        assert result.status == StageStatus.FAIL

    def test_required_lod_present_passes(self) -> None:
        objects = [
            MockMeshObject("ENV_Crate_LOD0"),
            MockMeshObject("ENV_Crate_LOD1"),
        ]
        ctx = _ctx(mesh_objects=objects)
        result, _ = check_scene(ctx, _config(require_lod=True))

        check = next(c for c in result.checks if c.name == "lod_presence")
        assert check.status == CheckStatus.PASS
        assert check.measured_value == 2

    def test_lod_count_reflects_matched_objects(self) -> None:
        objects = [
            MockMeshObject("PROP_Table_LOD0"),
            MockMeshObject("PROP_Table_LOD1"),
            MockMeshObject("PROP_Table_LOD2"),
            MockMeshObject("PROP_Table"),  # base mesh, not a LOD
        ]
        ctx = _ctx(mesh_objects=objects)
        result, _ = check_scene(ctx, _config(require_lod=True))

        check = next(c for c in result.checks if c.name == "lod_presence")
        assert check.status == CheckStatus.PASS
        assert check.measured_value == 3


# ---------------------------------------------------------------------------
# Tests — collision_presence
# ---------------------------------------------------------------------------

class TestCollisionPresence:
    def test_not_required_skipped(self) -> None:
        ctx = _ctx()
        result, _ = check_scene(ctx, _config(require_collision=False))

        check = next(c for c in result.checks if c.name == "collision_presence")
        assert check.status == CheckStatus.SKIPPED

    def test_required_no_collision_fails(self) -> None:
        objects = [MockMeshObject("ENV_Crate_Large")]
        ctx = _ctx(mesh_objects=objects)
        result, _ = check_scene(ctx, _config(require_collision=True))

        check = next(c for c in result.checks if c.name == "collision_presence")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value == 0
        assert result.status == StageStatus.FAIL

    def test_required_collision_present_passes(self) -> None:
        objects = [
            MockMeshObject("ENV_Crate_Large"),
            MockMeshObject("ENV_Crate_Collision"),
        ]
        ctx = _ctx(mesh_objects=objects)
        result, _ = check_scene(ctx, _config(require_collision=True))

        check = next(c for c in result.checks if c.name == "collision_presence")
        assert check.status == CheckStatus.PASS
        assert check.measured_value == 1


# ---------------------------------------------------------------------------
# Tests — performance estimates
# ---------------------------------------------------------------------------

class TestPerformanceEstimates:
    def test_triangle_count_sums_all_mesh_objects(self) -> None:
        objects = [MockMeshObject("A", triangle_count=1000), MockMeshObject("B", triangle_count=500)]
        ctx = _ctx(mesh_objects=objects)
        _, perf = check_scene(ctx, _config())

        assert perf.triangle_count == 1500

    def test_draw_call_estimate_two_objects_two_slots_each(self) -> None:
        objects = [
            MockMeshObject("A", material_slot_count=2),
            MockMeshObject("B", material_slot_count=2),
        ]
        ctx = _ctx(mesh_objects=objects)
        _, perf = check_scene(ctx, _config())

        assert perf.draw_call_estimate == 4

    def test_vram_estimate_2048_rgba_8bit(self) -> None:
        """2048×2048 RGBA 8-bit image: 16 MB × 4/3 ≈ 21.333 MB."""
        images = [MockImage(width=2048, height=2048, channels=4, bit_depth=8)]
        ctx = _ctx(unique_images=images)
        _, perf = check_scene(ctx, _config())

        expected = 2048 * 2048 * 4 * 8 / 8 / 1024 / 1024 * (4.0 / 3.0)
        assert perf.vram_estimate_mb == pytest.approx(expected, rel=1e-6)

    def test_vram_multiple_images_summed(self) -> None:
        images = [
            MockImage(width=1024, height=1024, channels=3, bit_depth=8),
            MockImage(width=512, height=512, channels=4, bit_depth=8),
        ]
        ctx = _ctx(unique_images=images)
        _, perf = check_scene(ctx, _config())

        expected = sum(
            img.width * img.height * img.channels * img.bit_depth / 8 / 1024 / 1024 * (4.0 / 3.0)
            for img in images
        )
        assert perf.vram_estimate_mb == pytest.approx(expected, rel=1e-6)

    def test_bone_count_sums_all_armatures(self) -> None:
        armatures = [
            MockArmatureObject("Arm1", bone_count=10),
            MockArmatureObject("Arm2", bone_count=5),
        ]
        ctx = _ctx(armature_objects=armatures)
        _, perf = check_scene(ctx, _config())

        assert perf.bone_count == 15

    def test_no_armatures_bone_count_zero(self) -> None:
        ctx = _ctx()
        _, perf = check_scene(ctx, _config())

        assert perf.bone_count == 0

    def test_empty_scene_all_zeros(self) -> None:
        ctx = _ctx()
        _, perf = check_scene(ctx, _config())

        assert perf.triangle_count == 0
        assert perf.draw_call_estimate == 0
        assert perf.vram_estimate_mb == 0.0
        assert perf.bone_count == 0


# ---------------------------------------------------------------------------
# Tests — stage result shape
# ---------------------------------------------------------------------------

class TestStageResultShape:
    def test_stage_name_is_scene(self) -> None:
        ctx = _ctx()
        result, _ = check_scene(ctx, _config())
        assert result.name == "scene"

    def test_four_checks_always_present(self) -> None:
        ctx = _ctx()
        result, _ = check_scene(ctx, _config())

        expected = {
            "naming_conventions",
            "orphan_data",
            "lod_presence",
            "collision_presence",
        }
        assert {c.name for c in result.checks} == expected

    def test_all_skipped_optional_checks_yield_pass_stage(self) -> None:
        ctx = _ctx()
        result, _ = check_scene(
            ctx,
            _config(require_lod=False, require_collision=False),
        )
        assert result.status == StageStatus.PASS

    def test_fail_check_yields_fail_stage(self) -> None:
        ctx = _ctx()
        result, _ = check_scene(ctx, _config(require_lod=True))

        assert result.status == StageStatus.FAIL

    def test_only_warnings_yield_pass_stage(self) -> None:
        """WARNING checks must not escalate the stage to FAIL."""
        objects = [MockMeshObject("badname")]
        ctx = _ctx(
            mesh_objects=objects,
            orphan_counts={"meshes": 1, "materials": 0, "images": 0},
        )
        result, _ = check_scene(ctx, _config())

        assert result.status == StageStatus.PASS
        warn_names = {c.name for c in result.checks if c.status == CheckStatus.WARNING}
        assert "naming_conventions" in warn_names
        assert "orphan_data" in warn_names

    def test_returns_tuple_of_stage_result_and_performance(self) -> None:
        from pipeline.schema import PerformanceEstimates, StageResult

        ctx = _ctx()
        result = check_scene(ctx, _config())

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], StageResult)
        assert isinstance(result[1], PerformanceEstimates)
