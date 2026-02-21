"""Unit tests for pipeline/stage1/geometry.py.

All tests use mock objects — no Blender installation required.

Mock topology used for "clean mesh" tests
-----------------------------------------
Two triangles sharing one edge (a simple quad split along the diagonal):

    v0 ---- v1
     |  f1 / |
     |   /   |
     |  / f2 |
    v2 ---- v3

Edges:
    e01 : v0-v1, boundary (1 face: f1)
    e12 : v1-v2, shared   (2 faces: f1, f2)  ← used for normal-consistency check
    e20 : v2-v0, boundary (1 face: f1)
    e13 : v1-v3, boundary (1 face: f2)
    e32 : v3-v2, boundary (1 face: f2)

Winding:
    f1 visits e12 starting at v1  (v1 → v2)
    f2 visits e12 starting at v2  (v2 → v1) ← opposite → consistent normals
"""
from __future__ import annotations

import pytest

from pipeline.schema import CheckStatus, StageStatus
from pipeline.stage1.geometry import (
    BlenderContext,
    GeometryConfig,
    MeshObject,
    check_geometry,
)


# ---------------------------------------------------------------------------
# Mock primitives
# ---------------------------------------------------------------------------

class MockVert:
    def __init__(self, link_faces: list | None = None) -> None:
        self.link_faces: list = link_faces if link_faces is not None else []


class MockLoop:
    def __init__(self, edge: "MockEdge", vert: MockVert) -> None:
        self.edge = edge
        self.vert = vert


class MockFace:
    def __init__(self, area: float = 1.0, loops: list[MockLoop] | None = None) -> None:
        self._area = area
        self.loops: list[MockLoop] = loops if loops is not None else []

    def calc_area(self) -> float:
        return self._area


class MockEdge:
    def __init__(
        self,
        is_manifold: bool = True,
        link_faces: list | None = None,
    ) -> None:
        self.is_manifold = is_manifold
        self.link_faces: list = link_faces if link_faces is not None else []


class MockBMesh:
    def __init__(
        self,
        edges: list[MockEdge] | None = None,
        faces: list[MockFace] | None = None,
        verts: list[MockVert] | None = None,
    ) -> None:
        self.edges: list[MockEdge] = edges if edges is not None else []
        self.faces: list[MockFace] = faces if faces is not None else []
        self.verts: list[MockVert] = verts if verts is not None else []


class MockMeshObject(MeshObject):
    def __init__(self, name: str, tri_count: int, bm: MockBMesh) -> None:
        self._name = name
        self._tri_count = tri_count
        self._bm = bm

    @property
    def name(self) -> str:
        return self._name

    def triangle_count(self) -> int:
        return self._tri_count

    def bmesh_get(self) -> MockBMesh:
        return self._bm


class MockBlenderContext(BlenderContext):
    def __init__(self, objects: list[MockMeshObject]) -> None:
        self._objects = objects

    def mesh_objects(self) -> list[MockMeshObject]:
        return self._objects


# ---------------------------------------------------------------------------
# Helpers to build mesh topologies
# ---------------------------------------------------------------------------

def make_clean_bmesh() -> MockBMesh:
    """Two triangles with consistent normals, no degenerate faces, no loose
    geometry and no interior faces."""
    v0, v1, v2, v3 = MockVert(), MockVert(), MockVert(), MockVert()

    e01 = MockEdge(is_manifold=True)   # boundary
    e12 = MockEdge(is_manifold=True)   # shared edge
    e20 = MockEdge(is_manifold=True)   # boundary
    e13 = MockEdge(is_manifold=True)   # boundary
    e32 = MockEdge(is_manifold=True)   # boundary

    # f1: v0 → v1 → v2; shared edge e12 starts at v1
    loop_f1_01 = MockLoop(edge=e01, vert=v0)
    loop_f1_12 = MockLoop(edge=e12, vert=v1)   # traverses e12 as v1→v2
    loop_f1_20 = MockLoop(edge=e20, vert=v2)
    f1 = MockFace(area=1.0, loops=[loop_f1_01, loop_f1_12, loop_f1_20])

    # f2: v2 → v1 → v3; shared edge e12 starts at v2 (opposite to f1 → consistent)
    loop_f2_12 = MockLoop(edge=e12, vert=v2)   # traverses e12 as v2→v1
    loop_f2_13 = MockLoop(edge=e13, vert=v1)
    loop_f2_32 = MockLoop(edge=e32, vert=v3)
    f2 = MockFace(area=1.0, loops=[loop_f2_12, loop_f2_13, loop_f2_32])

    e01.link_faces = [f1]
    e12.link_faces = [f1, f2]
    e20.link_faces = [f1]
    e13.link_faces = [f2]
    e32.link_faces = [f2]

    v0.link_faces = [f1]
    v1.link_faces = [f1, f2]
    v2.link_faces = [f1, f2]
    v3.link_faces = [f2]

    return MockBMesh(
        edges=[e01, e12, e20, e13, e32],
        faces=[f1, f2],
        verts=[v0, v1, v2, v3],
    )


def make_default_config(category: str = "env_prop") -> GeometryConfig:
    return GeometryConfig(category=category)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCleanMesh:
    def test_all_checks_pass(self) -> None:
        bm = make_clean_bmesh()
        ctx = MockBlenderContext([MockMeshObject("Lamp", 1_000, bm)])
        config = make_default_config("env_prop")

        result = check_geometry(ctx, config)

        assert result.name == "geometry"
        assert result.status == StageStatus.PASS
        assert len(result.checks) == 6
        for check in result.checks:
            assert check.status == CheckStatus.PASS, (
                f"Expected PASS for '{check.name}', got {check.status}: {check.message}"
            )


class TestPolycountBudget:
    def test_triangle_count_above_max_fails(self) -> None:
        bm = make_clean_bmesh()
        # env_prop max is 5 000; use 10 000 to exceed it
        ctx = MockBlenderContext([MockMeshObject("Mesh", 10_000, bm)])
        result = check_geometry(ctx, make_default_config("env_prop"))

        pc = next(c for c in result.checks if c.name == "polycount_budget")
        assert pc.status == CheckStatus.FAIL
        assert pc.measured_value == 10_000

    def test_triangle_count_below_min_fails(self) -> None:
        bm = make_clean_bmesh()
        # env_prop min is 500; use 100 to go below
        ctx = MockBlenderContext([MockMeshObject("Mesh", 100, bm)])
        result = check_geometry(ctx, make_default_config("env_prop"))

        pc = next(c for c in result.checks if c.name == "polycount_budget")
        assert pc.status == CheckStatus.FAIL
        assert pc.measured_value == 100

    def test_triangle_count_at_min_passes(self) -> None:
        bm = make_clean_bmesh()
        ctx = MockBlenderContext([MockMeshObject("Mesh", 500, bm)])
        result = check_geometry(ctx, make_default_config("env_prop"))

        pc = next(c for c in result.checks if c.name == "polycount_budget")
        assert pc.status == CheckStatus.PASS

    def test_triangle_count_at_max_passes(self) -> None:
        bm = make_clean_bmesh()
        ctx = MockBlenderContext([MockMeshObject("Mesh", 5_000, bm)])
        result = check_geometry(ctx, make_default_config("env_prop"))

        pc = next(c for c in result.checks if c.name == "polycount_budget")
        assert pc.status == CheckStatus.PASS

    def test_hero_prop_budget_used_when_category_is_hero_prop(self) -> None:
        bm = make_clean_bmesh()
        # hero_prop range is (5000, 15000); 8000 is inside
        ctx = MockBlenderContext([MockMeshObject("Mesh", 8_000, bm)])
        result = check_geometry(ctx, make_default_config("hero_prop"))

        pc = next(c for c in result.checks if c.name == "polycount_budget")
        assert pc.status == CheckStatus.PASS


class TestNonManifold:
    def test_three_non_manifold_edges_fail_with_correct_count(self) -> None:
        bm = make_clean_bmesh()
        # Inject 3 non-manifold edges
        nm1 = MockEdge(is_manifold=False, link_faces=[MockFace()])
        nm2 = MockEdge(is_manifold=False, link_faces=[MockFace()])
        nm3 = MockEdge(is_manifold=False, link_faces=[MockFace()])
        bm.edges.extend([nm1, nm2, nm3])

        ctx = MockBlenderContext([MockMeshObject("Mesh", 1_000, bm)])
        result = check_geometry(ctx, make_default_config())

        nm = next(c for c in result.checks if c.name == "non_manifold")
        assert nm.status == CheckStatus.FAIL
        assert nm.measured_value == 3


class TestDegenerateFaces:
    def test_degenerate_face_fails(self) -> None:
        bm = make_clean_bmesh()
        # Inject a degenerate face (area below threshold)
        degen = MockFace(area=1e-8, loops=[])
        bm.faces.append(degen)

        ctx = MockBlenderContext([MockMeshObject("Mesh", 1_000, bm)])
        result = check_geometry(ctx, make_default_config())

        df = next(c for c in result.checks if c.name == "degenerate_faces")
        assert df.status == CheckStatus.FAIL
        assert df.measured_value >= 1

    def test_face_exactly_at_threshold_passes(self) -> None:
        bm = make_clean_bmesh()
        # area == 1e-6 is NOT < 1e-6 so should pass
        borderline = MockFace(area=1e-6, loops=[])
        bm.faces.append(borderline)

        ctx = MockBlenderContext([MockMeshObject("Mesh", 1_000, bm)])
        result = check_geometry(ctx, make_default_config())

        df = next(c for c in result.checks if c.name == "degenerate_faces")
        assert df.status == CheckStatus.PASS


class TestNoShortCircuit:
    def test_all_six_checks_run_even_when_polycount_fails(self) -> None:
        bm = make_clean_bmesh()
        # Triangle count outside env_prop budget (too high)
        ctx = MockBlenderContext([MockMeshObject("Mesh", 99_999, bm)])
        result = check_geometry(ctx, make_default_config("env_prop"))

        expected_names = {
            "polycount_budget",
            "non_manifold",
            "degenerate_faces",
            "normal_consistency",
            "loose_geometry",
            "interior_faces",
        }
        actual_names = {c.name for c in result.checks}
        assert actual_names == expected_names

        # Overall stage fails because polycount failed
        assert result.status == StageStatus.FAIL

        # The remaining checks still ran and passed (clean mesh geometry)
        for check in result.checks:
            if check.name != "polycount_budget":
                assert check.status == CheckStatus.PASS, (
                    f"'{check.name}' should PASS but got {check.status}"
                )

    def test_all_six_checks_run_when_multiple_checks_fail(self) -> None:
        bm = make_clean_bmesh()
        # Add a non-manifold edge and a degenerate face to trigger 3 failures
        bm.edges.append(MockEdge(is_manifold=False, link_faces=[MockFace()]))
        bm.faces.append(MockFace(area=0.0, loops=[]))

        ctx = MockBlenderContext([MockMeshObject("Mesh", 99_999, bm)])
        result = check_geometry(ctx, make_default_config("env_prop"))

        assert len(result.checks) == 6
        assert result.status == StageStatus.FAIL


class TestStageResultShape:
    def test_stage_result_name_is_geometry(self) -> None:
        bm = make_clean_bmesh()
        ctx = MockBlenderContext([MockMeshObject("M", 1_000, bm)])
        result = check_geometry(ctx, make_default_config())
        assert result.name == "geometry"

    def test_threshold_is_zero_for_binary_checks(self) -> None:
        bm = make_clean_bmesh()
        ctx = MockBlenderContext([MockMeshObject("M", 1_000, bm)])
        result = check_geometry(ctx, make_default_config())

        binary_names = {
            "non_manifold",
            "degenerate_faces",
            "normal_consistency",
            "loose_geometry",
            "interior_faces",
        }
        for check in result.checks:
            if check.name in binary_names:
                assert check.threshold == 0, (
                    f"'{check.name}' threshold should be 0, got {check.threshold}"
                )
