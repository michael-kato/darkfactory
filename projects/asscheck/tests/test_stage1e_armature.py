"""Unit tests for pipeline/stage1/armature.py.

All tests use mock objects — no Blender installation required.
"""
from __future__ import annotations

import pytest

from pipeline.schema import CheckStatus, StageStatus
from pipeline.stage1.armature import (
    ArmatureBlenderContext,
    ArmatureBone,
    ArmatureConfig,
    ArmatureObject,
    SkinnedMesh,
    check_armature,
)


# ---------------------------------------------------------------------------
# Mock primitives
# ---------------------------------------------------------------------------

class MockBone(ArmatureBone):
    def __init__(self, name: str, parent: "MockBone | None" = None) -> None:
        self._name = name
        self._parent = parent

    @property
    def name(self) -> str:
        return self._name

    @property
    def parent(self) -> "MockBone | None":
        return self._parent


class MockArmature(ArmatureObject):
    def __init__(self, name: str, bones: list[MockBone] | None = None) -> None:
        self._name = name
        self._bones = bones or []

    @property
    def name(self) -> str:
        return self._name

    def bones(self) -> list[MockBone]:
        return self._bones


class MockSkinnedMesh(SkinnedMesh):
    def __init__(self, name: str, per_vertex_weights: list[list[float]]) -> None:
        self._name = name
        self._vertex_weights = per_vertex_weights

    @property
    def name(self) -> str:
        return self._name

    def per_vertex_weights(self) -> list[list[float]]:
        return self._vertex_weights


class MockArmatureContext(ArmatureBlenderContext):
    def __init__(
        self,
        armatures: list[MockArmature] | None = None,
        skinned_meshes: list[MockSkinnedMesh] | None = None,
    ) -> None:
        self._armatures = armatures or []
        self._skinned_meshes = skinned_meshes or []

    def armature_objects(self) -> list[MockArmature]:
        return self._armatures

    def skinned_meshes(self) -> list[MockSkinnedMesh]:
        return self._skinned_meshes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(**kwargs) -> ArmatureConfig:
    return ArmatureConfig(**kwargs)


def _ctx(
    armatures: list[MockArmature] | None = None,
    skinned_meshes: list[MockSkinnedMesh] | None = None,
) -> MockArmatureContext:
    return MockArmatureContext(armatures=armatures, skinned_meshes=skinned_meshes)


def _make_bones(count: int) -> list[MockBone]:
    """Create *count* bones: first is the root, rest are children of root."""
    if count == 0:
        return []
    root = MockBone("root")
    rest = [MockBone(f"bone_{i}", parent=root) for i in range(1, count)]
    return [root] + rest


# ---------------------------------------------------------------------------
# Tests — armature_present (early-exit and required checks)
# ---------------------------------------------------------------------------

class TestArmaturePresent:
    def test_no_armature_non_character_category_skipped(self) -> None:
        ctx = _ctx()
        result = check_armature(ctx, _config(category="env_prop"))

        assert result.status == StageStatus.SKIPPED

    def test_no_armature_character_category_fails(self) -> None:
        ctx = _ctx()
        result = check_armature(
            ctx,
            _config(
                category="character",
                categories_requiring_armature=["character"],
            ),
        )

        check = next(c for c in result.checks if c.name == "armature_present")
        assert check.status == CheckStatus.FAIL
        assert result.status == StageStatus.FAIL

    def test_armature_present_passes(self) -> None:
        arm = MockArmature("Armature", _make_bones(3))
        ctx = _ctx(armatures=[arm])
        result = check_armature(ctx, _config(category="character"))

        check = next(c for c in result.checks if c.name == "armature_present")
        assert check.status == CheckStatus.PASS
        assert check.measured_value == 1


# ---------------------------------------------------------------------------
# Tests — bone_count
# ---------------------------------------------------------------------------

class TestBoneCount:
    def test_74_bones_max_75_passes(self) -> None:
        arm = MockArmature("Armature", _make_bones(74))
        ctx = _ctx(armatures=[arm])
        result = check_armature(ctx, _config(max_bones=75, category="character"))

        check = next(c for c in result.checks if c.name == "bone_count")
        assert check.status == CheckStatus.PASS
        assert check.measured_value == 74

    def test_76_bones_max_75_fails(self) -> None:
        arm = MockArmature("Armature", _make_bones(76))
        ctx = _ctx(armatures=[arm])
        result = check_armature(ctx, _config(max_bones=75, category="character"))

        check = next(c for c in result.checks if c.name == "bone_count")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value == 76
        assert result.status == StageStatus.FAIL

    def test_zero_bones_within_budget(self) -> None:
        arm = MockArmature("Armature", [])
        ctx = _ctx(armatures=[arm])
        result = check_armature(ctx, _config(max_bones=75, category="character"))

        check = next(c for c in result.checks if c.name == "bone_count")
        assert check.status == CheckStatus.PASS
        assert check.measured_value == 0


# ---------------------------------------------------------------------------
# Tests — bone_naming
# ---------------------------------------------------------------------------

_STRICT_PATTERN = r"^[A-Za-z_][A-Za-z0-9_.]+$"


class TestBoneNaming:
    def test_no_pattern_skipped(self) -> None:
        arm = MockArmature("Armature", _make_bones(3))
        ctx = _ctx(armatures=[arm])
        result = check_armature(
            ctx, _config(category="character", bone_naming_pattern=None)
        )

        check = next(c for c in result.checks if c.name == "bone_naming")
        assert check.status == CheckStatus.SKIPPED

    def test_valid_names_pass(self) -> None:
        bones = [
            MockBone("Hips"),
            MockBone("Spine", parent=MockBone("Hips")),
            MockBone("Head", parent=MockBone("Spine")),
        ]
        arm = MockArmature("Armature", bones)
        ctx = _ctx(armatures=[arm])
        result = check_armature(
            ctx,
            _config(
                category="character",
                bone_naming_pattern=_STRICT_PATTERN,
            ),
        )

        check = next(c for c in result.checks if c.name == "bone_naming")
        assert check.status == CheckStatus.PASS
        assert check.measured_value["count"] == 0

    def test_mixamorig_colon_fails(self) -> None:
        """'mixamorig:Hips' contains ':' which is not in [A-Za-z0-9_.]+."""
        root = MockBone("mixamorig:Hips")
        arm = MockArmature("Armature", [root])
        ctx = _ctx(armatures=[arm])
        result = check_armature(
            ctx,
            _config(
                category="character",
                bone_naming_pattern=_STRICT_PATTERN,
            ),
        )

        check = next(c for c in result.checks if c.name == "bone_naming")
        assert check.status == CheckStatus.FAIL
        assert "mixamorig:Hips" in check.measured_value["violations"]
        assert check.measured_value["count"] == 1

    def test_multiple_violation_bones_all_recorded(self) -> None:
        root = MockBone("root")
        bad1 = MockBone("bone:one", parent=root)
        bad2 = MockBone("bone two", parent=root)
        arm = MockArmature("Armature", [root, bad1, bad2])
        ctx = _ctx(armatures=[arm])
        result = check_armature(
            ctx,
            _config(
                category="character",
                bone_naming_pattern=_STRICT_PATTERN,
            ),
        )

        check = next(c for c in result.checks if c.name == "bone_naming")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value["count"] == 2
        assert "bone:one" in check.measured_value["violations"]
        assert "bone two" in check.measured_value["violations"]


# ---------------------------------------------------------------------------
# Tests — vertex_weights
# ---------------------------------------------------------------------------

class TestVertexWeights:
    def test_zero_total_weight_fails(self) -> None:
        mesh = MockSkinnedMesh("Mesh", per_vertex_weights=[[]])
        ctx = _ctx(
            armatures=[MockArmature("Arm", _make_bones(1))],
            skinned_meshes=[mesh],
        )
        result = check_armature(ctx, _config(category="character"))

        check = next(c for c in result.checks if c.name == "vertex_weights")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value["zero_weight_count"] == 1
        assert check.measured_value["excess_influences_count"] == 0
        assert check.measured_value["unnormalized_count"] == 0

    def test_5_influences_max_4_fails(self) -> None:
        # 5 equal weights summing to 1.0 (normalized but too many influences)
        mesh = MockSkinnedMesh(
            "Mesh",
            per_vertex_weights=[[0.2, 0.2, 0.2, 0.2, 0.2]],
        )
        ctx = _ctx(
            armatures=[MockArmature("Arm", _make_bones(1))],
            skinned_meshes=[mesh],
        )
        result = check_armature(
            ctx, _config(category="character", max_influences_per_vertex=4)
        )

        check = next(c for c in result.checks if c.name == "vertex_weights")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value["excess_influences_count"] == 1
        assert check.measured_value["zero_weight_count"] == 0

    def test_unnormalized_weights_fail(self) -> None:
        """Weights [0.4, 0.4] sum to 0.8 ≠ 1.0 ± 0.001."""
        mesh = MockSkinnedMesh("Mesh", per_vertex_weights=[[0.4, 0.4]])
        ctx = _ctx(
            armatures=[MockArmature("Arm", _make_bones(1))],
            skinned_meshes=[mesh],
        )
        result = check_armature(ctx, _config(category="character"))

        check = next(c for c in result.checks if c.name == "vertex_weights")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value["unnormalized_count"] == 1
        assert check.measured_value["zero_weight_count"] == 0
        assert check.measured_value["excess_influences_count"] == 0

    def test_valid_weights_pass(self) -> None:
        """Four influences summing to 1.0."""
        mesh = MockSkinnedMesh("Mesh", per_vertex_weights=[[0.25, 0.25, 0.25, 0.25]])
        ctx = _ctx(
            armatures=[MockArmature("Arm", _make_bones(1))],
            skinned_meshes=[mesh],
        )
        result = check_armature(
            ctx, _config(category="character", max_influences_per_vertex=4)
        )

        check = next(c for c in result.checks if c.name == "vertex_weights")
        assert check.status == CheckStatus.PASS
        assert check.measured_value["zero_weight_count"] == 0
        assert check.measured_value["excess_influences_count"] == 0
        assert check.measured_value["unnormalized_count"] == 0

    def test_no_skinned_meshes_passes(self) -> None:
        ctx = _ctx(armatures=[MockArmature("Arm", _make_bones(1))])
        result = check_armature(ctx, _config(category="character"))

        check = next(c for c in result.checks if c.name == "vertex_weights")
        assert check.status == CheckStatus.PASS

    def test_weight_exactly_at_tolerance_boundary_passes(self) -> None:
        """sum = 1.001 is within tolerance."""
        mesh = MockSkinnedMesh("Mesh", per_vertex_weights=[[0.5, 0.501]])
        ctx = _ctx(
            armatures=[MockArmature("Arm", _make_bones(1))],
            skinned_meshes=[mesh],
        )
        result = check_armature(ctx, _config(category="character"))

        check = next(c for c in result.checks if c.name == "vertex_weights")
        assert check.status == CheckStatus.PASS

    def test_zero_weight_vertex_not_double_counted(self) -> None:
        """A zero-weight vertex must not also increment unnormalized_count."""
        mesh = MockSkinnedMesh("Mesh", per_vertex_weights=[[]])
        ctx = _ctx(
            armatures=[MockArmature("Arm", _make_bones(1))],
            skinned_meshes=[mesh],
        )
        result = check_armature(ctx, _config(category="character"))

        check = next(c for c in result.checks if c.name == "vertex_weights")
        assert check.measured_value["zero_weight_count"] == 1
        assert check.measured_value["unnormalized_count"] == 0


# ---------------------------------------------------------------------------
# Tests — bone_hierarchy
# ---------------------------------------------------------------------------

class TestBoneHierarchy:
    def test_single_root_passes(self) -> None:
        root = MockBone("root")
        child = MockBone("child", parent=root)
        arm = MockArmature("Arm", [root, child])
        ctx = _ctx(armatures=[arm])
        result = check_armature(ctx, _config(category="character"))

        check = next(c for c in result.checks if c.name == "bone_hierarchy")
        assert check.status == CheckStatus.PASS
        assert check.measured_value["root_count"] == 1
        assert check.measured_value["orphan_count"] == 0

    def test_two_root_bones_fails(self) -> None:
        root1 = MockBone("root1")
        root2 = MockBone("root2")
        arm = MockArmature("Arm", [root1, root2])
        ctx = _ctx(armatures=[arm])
        result = check_armature(ctx, _config(category="character"))

        check = next(c for c in result.checks if c.name == "bone_hierarchy")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value["root_count"] == 2
        assert check.measured_value["orphan_count"] == 1
        assert result.status == StageStatus.FAIL

    def test_orphan_bone_no_parent_not_root_fails(self) -> None:
        """Three bones: root, child of root, orphan with no parent."""
        root = MockBone("root")
        child = MockBone("child", parent=root)
        orphan = MockBone("orphan")  # no parent, not the intended root
        arm = MockArmature("Arm", [root, child, orphan])
        ctx = _ctx(armatures=[arm])
        result = check_armature(ctx, _config(category="character"))

        check = next(c for c in result.checks if c.name == "bone_hierarchy")
        assert check.status == CheckStatus.FAIL
        assert check.measured_value["orphan_count"] == 1

    def test_no_armatures_hierarchy_passes(self) -> None:
        """No armatures → no orphans → hierarchy check passes."""
        ctx = _ctx(
            armatures=[MockArmature("Arm", _make_bones(1))],
        )
        result = check_armature(ctx, _config(category="character"))

        check = next(c for c in result.checks if c.name == "bone_hierarchy")
        assert check.status == CheckStatus.PASS

    def test_multiple_armatures_each_with_single_root_passes(self) -> None:
        arm1 = MockArmature("Arm1", _make_bones(3))
        arm2 = MockArmature("Arm2", _make_bones(5))
        ctx = _ctx(armatures=[arm1, arm2])
        result = check_armature(ctx, _config(category="character"))

        check = next(c for c in result.checks if c.name == "bone_hierarchy")
        assert check.status == CheckStatus.PASS
        assert check.measured_value["root_count"] == 2
        assert check.measured_value["orphan_count"] == 0


# ---------------------------------------------------------------------------
# Tests — stage result shape and full integration
# ---------------------------------------------------------------------------

class TestStageResultShape:
    def test_stage_name_is_armature(self) -> None:
        arm = MockArmature("Arm", _make_bones(1))
        ctx = _ctx(armatures=[arm])
        result = check_armature(ctx, _config(category="character"))
        assert result.name == "armature"

    def test_five_checks_always_run_when_armature_present(self) -> None:
        arm = MockArmature("Arm", _make_bones(3))
        ctx = _ctx(armatures=[arm])
        result = check_armature(ctx, _config(category="character"))

        expected = {
            "armature_present",
            "bone_count",
            "bone_naming",
            "vertex_weights",
            "bone_hierarchy",
        }
        assert {c.name for c in result.checks} == expected

    def test_all_checks_run_even_on_failure(self) -> None:
        """bone_count fails but remaining checks still run."""
        arm = MockArmature("Arm", _make_bones(76))
        ctx = _ctx(armatures=[arm])
        result = check_armature(ctx, _config(max_bones=75, category="character"))

        assert len(result.checks) == 5
        bone_check = next(c for c in result.checks if c.name == "bone_count")
        assert bone_check.status == CheckStatus.FAIL
        assert result.status == StageStatus.FAIL

    def test_skipped_stage_contains_armature_present_check(self) -> None:
        ctx = _ctx()
        result = check_armature(ctx, _config(category="env_prop"))

        assert result.status == StageStatus.SKIPPED
        assert len(result.checks) == 1
        assert result.checks[0].name == "armature_present"
        assert result.checks[0].status == CheckStatus.SKIPPED

    def test_all_passing_checks_yield_pass_stage(self) -> None:
        root = MockBone("root")
        child = MockBone("child", parent=root)
        arm = MockArmature("Arm", [root, child])
        mesh = MockSkinnedMesh("Mesh", [[0.6, 0.4]])
        ctx = _ctx(armatures=[arm], skinned_meshes=[mesh])
        result = check_armature(
            ctx,
            _config(
                max_bones=75,
                max_influences_per_vertex=4,
                category="character",
                bone_naming_pattern=None,
            ),
        )

        assert result.status == StageStatus.PASS
        for check in result.checks:
            assert check.status in (CheckStatus.PASS, CheckStatus.SKIPPED)
