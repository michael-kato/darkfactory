"""Unit tests for pipeline/stage2/remediate.py.

All tests use mock objects — no Blender installation required.
"""
from __future__ import annotations

import pytest

from pipeline.schema import CheckResult, CheckStatus, StageResult, StageStatus
from pipeline.stage2.remediate import (
    RemediationBlenderContext,
    RemediationConfig,
    RemediationImage,
    RemediationMeshObject,
    RemediationSkinnedMesh,
    run_remediation,
)


# ---------------------------------------------------------------------------
# Mock primitives
# ---------------------------------------------------------------------------

class MockMeshObject(RemediationMeshObject):
    def __init__(
        self,
        name: str,
        vertex_count: int,
        post_merge_vertex_count: int | None = None,
    ) -> None:
        self._name = name
        self._vertex_count = vertex_count
        self._post_merge = (
            post_merge_vertex_count
            if post_merge_vertex_count is not None
            else vertex_count
        )
        self.recalculate_normals_called = False
        self.merge_by_distance_called = False
        self.last_merge_threshold: float | None = None

    @property
    def name(self) -> str:
        return self._name

    def vertex_count(self) -> int:
        return self._vertex_count

    def recalculate_normals(self) -> None:
        self.recalculate_normals_called = True

    def merge_by_distance(self, threshold: float) -> int:
        self.merge_by_distance_called = True
        self.last_merge_threshold = threshold
        return self._post_merge


class MockImage(RemediationImage):
    def __init__(self, name: str, width: int, height: int) -> None:
        self._name = name
        self._size = (width, height)
        self.scale_called = False
        self.last_scale_args: tuple[int, int] | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def size(self) -> tuple[int, int]:
        return self._size

    def scale(self, new_w: int, new_h: int) -> None:
        self.scale_called = True
        self.last_scale_args = (new_w, new_h)
        self._size = (new_w, new_h)


class MockSkinnedMesh(RemediationSkinnedMesh):
    def __init__(self, name: str, max_influences: int) -> None:
        self._name = name
        self._max_influences = max_influences

    @property
    def name(self) -> str:
        return self._name

    def max_influences(self) -> int:
        return self._max_influences


class MockContext(RemediationBlenderContext):
    def __init__(
        self,
        mesh_objects: list[MockMeshObject] | None = None,
        images: list[MockImage] | None = None,
        skinned_meshes: list[MockSkinnedMesh] | None = None,
    ) -> None:
        self._mesh_objects = mesh_objects or []
        self._images = images or []
        self._skinned_meshes = skinned_meshes or []
        self.limit_bone_weights_called = False
        self.last_limit: int | None = None

    def mesh_objects(self) -> list[MockMeshObject]:
        return self._mesh_objects

    def images(self) -> list[MockImage]:
        return self._images

    def skinned_meshes(self) -> list[MockSkinnedMesh]:
        return self._skinned_meshes

    def limit_bone_weights(self, limit: int) -> None:
        self.limit_bone_weights_called = True
        self.last_limit = limit


# ---------------------------------------------------------------------------
# Stage1 result builder helpers
# ---------------------------------------------------------------------------

def _check(
    name: str,
    status: CheckStatus,
    measured_value: object = None,
) -> CheckResult:
    return CheckResult(
        name=name,
        status=status,
        measured_value=measured_value if measured_value is not None else 0,
        threshold=None,
        message="test",
    )


def _stage(name: str, checks: list[CheckResult]) -> StageResult:
    has_fail = any(c.status == CheckStatus.FAIL for c in checks)
    return StageResult(
        name=name,
        status=StageStatus.FAIL if has_fail else StageStatus.PASS,
        checks=checks,
    )


# ---------------------------------------------------------------------------
# Tests — recalculate_normals
# ---------------------------------------------------------------------------

class TestRecalculateNormals:
    def test_normal_consistency_fail_triggers_fix(self) -> None:
        stage1 = [
            _stage("geometry", [
                _check("normal_consistency", CheckStatus.FAIL, measured_value=4),
            ])
        ]
        obj = MockMeshObject("Mesh", vertex_count=100)
        ctx = MockContext(mesh_objects=[obj])

        result = run_remediation(ctx, stage1, RemediationConfig())

        assert obj.recalculate_normals_called
        fixes = [f for f in result.fixes if f.action == "recalculate_normals"]
        assert len(fixes) == 1
        assert fixes[0].target == "Mesh"
        assert fixes[0].before_value == 4
        assert fixes[0].after_value == 0

    def test_normal_consistency_pass_no_fix_applied(self) -> None:
        stage1 = [
            _stage("geometry", [
                _check("normal_consistency", CheckStatus.PASS, measured_value=0),
            ])
        ]
        obj = MockMeshObject("Mesh", vertex_count=100)
        ctx = MockContext(mesh_objects=[obj])

        result = run_remediation(ctx, stage1, RemediationConfig())

        assert not obj.recalculate_normals_called
        assert not any(f.action == "recalculate_normals" for f in result.fixes)

    def test_fix_logged_per_mesh_object(self) -> None:
        stage1 = [
            _stage("geometry", [
                _check("normal_consistency", CheckStatus.FAIL, measured_value=6),
            ])
        ]
        obj_a = MockMeshObject("MeshA", 50)
        obj_b = MockMeshObject("MeshB", 80)
        ctx = MockContext(mesh_objects=[obj_a, obj_b])

        result = run_remediation(ctx, stage1, RemediationConfig())

        targets = [f.target for f in result.fixes if f.action == "recalculate_normals"]
        assert "MeshA" in targets
        assert "MeshB" in targets
        assert len(targets) == 2


# ---------------------------------------------------------------------------
# Tests — merge_by_distance
# ---------------------------------------------------------------------------

class TestMergeByDistance:
    def test_degenerate_faces_fail_triggers_merge(self) -> None:
        stage1 = [
            _stage("geometry", [
                _check("degenerate_faces", CheckStatus.FAIL),
            ])
        ]
        obj = MockMeshObject("Mesh", vertex_count=200, post_merge_vertex_count=195)
        ctx = MockContext(mesh_objects=[obj])
        config = RemediationConfig(merge_distance=0.0001)

        result = run_remediation(ctx, stage1, config)

        assert obj.merge_by_distance_called
        assert obj.last_merge_threshold == pytest.approx(0.0001)
        fixes = [f for f in result.fixes if f.action == "merge_by_distance"]
        assert len(fixes) == 1
        assert fixes[0].before_value == 200
        assert fixes[0].after_value == 195

    def test_loose_geometry_fail_triggers_merge(self) -> None:
        stage1 = [
            _stage("geometry", [
                _check("loose_geometry", CheckStatus.FAIL),
            ])
        ]
        obj = MockMeshObject("Mesh", vertex_count=150, post_merge_vertex_count=148)
        ctx = MockContext(mesh_objects=[obj])

        result = run_remediation(ctx, stage1, RemediationConfig())

        assert obj.merge_by_distance_called
        fixes = [f for f in result.fixes if f.action == "merge_by_distance"]
        assert len(fixes) == 1

    def test_both_pass_no_merge(self) -> None:
        stage1 = [
            _stage("geometry", [
                _check("degenerate_faces", CheckStatus.PASS),
                _check("loose_geometry", CheckStatus.PASS),
            ])
        ]
        obj = MockMeshObject("Mesh", 100)
        ctx = MockContext(mesh_objects=[obj])

        result = run_remediation(ctx, stage1, RemediationConfig())

        assert not obj.merge_by_distance_called


# ---------------------------------------------------------------------------
# Tests — resize_textures
# ---------------------------------------------------------------------------

class TestResizeTextures:
    def test_4096x4096_standard_resized_to_2048x2048(self) -> None:
        stage1 = [
            _stage("texture", [
                _check("resolution_limit", CheckStatus.FAIL),
            ])
        ]
        img = MockImage("tex.png", 4096, 4096)
        ctx = MockContext(images=[img])
        config = RemediationConfig(max_texture_resolution=2048)

        result = run_remediation(ctx, stage1, config)

        assert img.scale_called
        fixes = [f for f in result.fixes if f.action == "resize_textures"]
        assert len(fixes) == 1
        assert fixes[0].target == "tex.png"
        assert fixes[0].before_value == [4096, 4096]
        assert fixes[0].after_value == [2048, 2048]

    def test_3000x2000_standard_resized_to_2048x1024(self) -> None:
        stage1 = [
            _stage("texture", [
                _check("resolution_limit", CheckStatus.FAIL),
            ])
        ]
        img = MockImage("tex.png", 3000, 2000)
        ctx = MockContext(images=[img])
        config = RemediationConfig(max_texture_resolution=2048)

        result = run_remediation(ctx, stage1, config)

        fixes = [f for f in result.fixes if f.action == "resize_textures"]
        assert len(fixes) == 1
        assert fixes[0].before_value == [3000, 2000]
        assert fixes[0].after_value == [2048, 1024]

    def test_image_within_limit_not_resized(self) -> None:
        stage1 = [
            _stage("texture", [
                _check("resolution_limit", CheckStatus.FAIL),
            ])
        ]
        img = MockImage("small.png", 1024, 1024)
        ctx = MockContext(images=[img])
        config = RemediationConfig(max_texture_resolution=2048)

        result = run_remediation(ctx, stage1, config)

        assert not img.scale_called
        assert not any(f.action == "resize_textures" for f in result.fixes)

    def test_resolution_limit_pass_no_resize(self) -> None:
        stage1 = [
            _stage("texture", [
                _check("resolution_limit", CheckStatus.PASS),
            ])
        ]
        img = MockImage("tex.png", 4096, 4096)
        ctx = MockContext(images=[img])

        result = run_remediation(ctx, stage1, RemediationConfig())

        assert not img.scale_called

    def test_hero_asset_uses_4096_limit(self) -> None:
        stage1 = [
            _stage("texture", [
                _check("resolution_limit", CheckStatus.FAIL),
            ])
        ]
        img = MockImage("tex.png", 8192, 8192)
        ctx = MockContext(images=[img])
        config = RemediationConfig(max_texture_resolution=2048, hero_asset=True)

        result = run_remediation(ctx, stage1, config)

        fixes = [f for f in result.fixes if f.action == "resize_textures"]
        assert len(fixes) == 1
        assert fixes[0].after_value == [4096, 4096]

    def test_hero_asset_image_within_4096_not_resized(self) -> None:
        stage1 = [
            _stage("texture", [
                _check("resolution_limit", CheckStatus.FAIL),
            ])
        ]
        img = MockImage("tex.png", 3000, 3000)
        ctx = MockContext(images=[img])
        config = RemediationConfig(max_texture_resolution=2048, hero_asset=True)

        result = run_remediation(ctx, stage1, config)

        assert not img.scale_called


# ---------------------------------------------------------------------------
# Tests — limit_bone_weights
# ---------------------------------------------------------------------------

class TestLimitBoneWeights:
    def test_vertex_weights_fail_triggers_limit(self) -> None:
        stage1 = [
            _stage("armature", [
                _check("vertex_weights", CheckStatus.FAIL),
            ])
        ]
        mesh = MockSkinnedMesh("Body", max_influences=6)
        ctx = MockContext(skinned_meshes=[mesh])
        config = RemediationConfig(max_bone_influences=4)

        result = run_remediation(ctx, stage1, config)

        assert ctx.limit_bone_weights_called
        assert ctx.last_limit == 4
        fixes = [f for f in result.fixes if f.action == "limit_bone_weights"]
        assert len(fixes) == 1
        assert fixes[0].target == "scene"
        assert fixes[0].before_value == 6
        assert fixes[0].after_value == 4

    def test_vertex_weights_pass_no_fix(self) -> None:
        stage1 = [
            _stage("armature", [
                _check("vertex_weights", CheckStatus.PASS),
            ])
        ]
        mesh = MockSkinnedMesh("Body", max_influences=4)
        ctx = MockContext(skinned_meshes=[mesh])

        result = run_remediation(ctx, stage1, RemediationConfig())

        assert not ctx.limit_bone_weights_called

    def test_before_value_is_max_across_all_skinned_meshes(self) -> None:
        stage1 = [
            _stage("armature", [
                _check("vertex_weights", CheckStatus.FAIL),
            ])
        ]
        mesh_a = MockSkinnedMesh("MeshA", max_influences=5)
        mesh_b = MockSkinnedMesh("MeshB", max_influences=8)
        ctx = MockContext(skinned_meshes=[mesh_a, mesh_b])
        config = RemediationConfig(max_bone_influences=4)

        result = run_remediation(ctx, stage1, config)

        fix = next(f for f in result.fixes if f.action == "limit_bone_weights")
        assert fix.before_value == 8  # max across all meshes

    def test_no_skinned_meshes_before_value_is_zero(self) -> None:
        stage1 = [
            _stage("armature", [
                _check("vertex_weights", CheckStatus.FAIL),
            ])
        ]
        ctx = MockContext(skinned_meshes=[])
        config = RemediationConfig(max_bone_influences=4)

        result = run_remediation(ctx, stage1, config)

        fix = next(f for f in result.fixes if f.action == "limit_bone_weights")
        assert fix.before_value == 0


# ---------------------------------------------------------------------------
# Tests — review flags
# ---------------------------------------------------------------------------

class TestReviewFlags:
    def test_uv_overlap_fail_adds_review_flag_no_scene_change(self) -> None:
        stage1 = [
            _stage("uv", [
                _check("uv_overlap", CheckStatus.FAIL),
            ])
        ]
        ctx = MockContext()

        result = run_remediation(ctx, stage1, RemediationConfig())

        assert result.fixes == []
        flags = [f for f in result.review_flags if f.issue == "uv:uv_overlap"]
        assert len(flags) == 1
        assert "UV islands overlap" in flags[0].description

    def test_non_manifold_fail_adds_review_flag_no_scene_change(self) -> None:
        stage1 = [
            _stage("geometry", [
                _check("non_manifold", CheckStatus.FAIL),
                _check("normal_consistency", CheckStatus.PASS),
                _check("degenerate_faces", CheckStatus.PASS),
                _check("loose_geometry", CheckStatus.PASS),
            ])
        ]
        obj = MockMeshObject("Mesh", 100)
        ctx = MockContext(mesh_objects=[obj])

        result = run_remediation(ctx, stage1, RemediationConfig())

        assert result.fixes == []
        flags = [f for f in result.review_flags if f.issue == "geometry:non_manifold"]
        assert len(flags) == 1
        assert not obj.recalculate_normals_called
        assert not obj.merge_by_distance_called

    def test_pbr_albedo_warning_adds_review_flag(self) -> None:
        stage1 = [
            _stage("pbr", [
                _check("albedo_range", CheckStatus.WARNING),
            ])
        ]
        result = run_remediation(MockContext(), stage1, RemediationConfig())

        flags = [f for f in result.review_flags if f.issue == "pbr:albedo_range"]
        assert len(flags) == 1
        assert "Albedo values outside PBR range" in flags[0].description

    def test_pbr_metalness_binary_warning_adds_flag(self) -> None:
        stage1 = [_stage("pbr", [_check("metalness_binary", CheckStatus.WARNING)])]
        result = run_remediation(MockContext(), stage1, RemediationConfig())

        flags = [f for f in result.review_flags if f.issue == "pbr:metalness_binary"]
        assert len(flags) == 1

    def test_pbr_roughness_range_warning_adds_flag(self) -> None:
        stage1 = [_stage("pbr", [_check("roughness_range", CheckStatus.WARNING)])]
        result = run_remediation(MockContext(), stage1, RemediationConfig())

        flags = [f for f in result.review_flags if f.issue == "pbr:roughness_range"]
        assert len(flags) == 1

    def test_interior_faces_fail_adds_review_flag(self) -> None:
        stage1 = [
            _stage("geometry", [
                _check("interior_faces", CheckStatus.FAIL),
                _check("normal_consistency", CheckStatus.PASS),
                _check("degenerate_faces", CheckStatus.PASS),
                _check("loose_geometry", CheckStatus.PASS),
            ])
        ]
        result = run_remediation(MockContext(), stage1, RemediationConfig())

        flags = [f for f in result.review_flags if f.issue == "geometry:interior_faces"]
        assert len(flags) == 1
        assert result.fixes == []

    def test_texel_density_warning_adds_review_flag(self) -> None:
        stage1 = [_stage("uv", [_check("texel_density", CheckStatus.WARNING)])]
        result = run_remediation(MockContext(), stage1, RemediationConfig())

        flags = [f for f in result.review_flags if f.issue == "uv:texel_density"]
        assert len(flags) == 1

    def test_lod_presence_fail_adds_review_flag(self) -> None:
        stage1 = [_stage("scene", [_check("lod_presence", CheckStatus.FAIL)])]
        result = run_remediation(MockContext(), stage1, RemediationConfig())

        flags = [f for f in result.review_flags if f.issue == "scene:lod_presence"]
        assert len(flags) == 1

    def test_polycount_fail_adds_review_flag(self) -> None:
        stage1 = [
            _stage("geometry", [
                _check("polycount_budget", CheckStatus.FAIL),
                _check("normal_consistency", CheckStatus.PASS),
                _check("degenerate_faces", CheckStatus.PASS),
                _check("loose_geometry", CheckStatus.PASS),
            ])
        ]
        result = run_remediation(MockContext(), stage1, RemediationConfig())

        flags = [f for f in result.review_flags if f.issue == "geometry:polycount_budget"]
        assert len(flags) == 1
        assert "Polycount violation" in flags[0].description

    def test_non_fail_check_does_not_add_flag(self) -> None:
        stage1 = [_stage("uv", [_check("uv_overlap", CheckStatus.PASS)])]
        result = run_remediation(MockContext(), stage1, RemediationConfig())

        flags = [f for f in result.review_flags if f.issue == "uv:uv_overlap"]
        assert len(flags) == 0


# ---------------------------------------------------------------------------
# Tests — all stage1 results PASS → no fixes, no flags
# ---------------------------------------------------------------------------

class TestAllPass:
    def test_all_pass_yields_empty_fixes_and_flags(self) -> None:
        stage1 = [
            _stage("geometry", [
                _check("normal_consistency", CheckStatus.PASS),
                _check("non_manifold", CheckStatus.PASS),
                _check("degenerate_faces", CheckStatus.PASS),
                _check("loose_geometry", CheckStatus.PASS),
                _check("interior_faces", CheckStatus.PASS),
                _check("polycount_budget", CheckStatus.PASS),
            ]),
            _stage("uv", [
                _check("uv_overlap", CheckStatus.PASS),
                _check("texel_density", CheckStatus.PASS),
            ]),
            _stage("texture", [
                _check("resolution_limit", CheckStatus.PASS),
            ]),
            _stage("armature", [
                _check("vertex_weights", CheckStatus.PASS),
            ]),
            _stage("pbr", [
                _check("albedo_range", CheckStatus.PASS),
                _check("metalness_binary", CheckStatus.PASS),
                _check("roughness_range", CheckStatus.PASS),
            ]),
            _stage("scene", [
                _check("lod_presence", CheckStatus.PASS),
            ]),
        ]
        result = run_remediation(MockContext(), stage1, RemediationConfig())

        assert result.fixes == []
        assert result.review_flags == []
        assert result.status == StageStatus.PASS

    def test_empty_stage1_results_no_fixes_no_flags(self) -> None:
        result = run_remediation(MockContext(), [], RemediationConfig())

        assert result.fixes == []
        assert result.review_flags == []
        assert result.status == StageStatus.PASS


# ---------------------------------------------------------------------------
# Tests — StageResult shape
# ---------------------------------------------------------------------------

class TestStageResultShape:
    def test_result_name_is_remediation(self) -> None:
        result = run_remediation(MockContext(), [], RemediationConfig())
        assert result.name == "remediation"

    def test_result_status_is_always_pass(self) -> None:
        """Remediation never fails the pipeline."""
        stage1 = [
            _stage("geometry", [
                _check("non_manifold", CheckStatus.FAIL),
                _check("interior_faces", CheckStatus.FAIL),
                _check("polycount_budget", CheckStatus.FAIL),
            ])
        ]
        result = run_remediation(MockContext(), stage1, RemediationConfig())
        assert result.status == StageStatus.PASS
