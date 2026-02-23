"""Geometry Checks.

Analyses mesh geometry using bmesh to detect polycount violations,
non-manifold conditions, degenerate faces, normal inconsistencies,
loose geometry, and interior faces.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from pipeline.schema import CheckResult, CheckStatus, StageResult, StageStatus

# ---------------------------------------------------------------------------
# Default triangle budgets per asset category
# ---------------------------------------------------------------------------

_DEFAULT_BUDGETS = {
    "env_prop":  (500,   5_000),
    "hero_prop": (5_000, 15_000),
    "character": (15_000, 30_000),
    "vehicle":   (10_000, 25_000),
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class GeometryConfig:
    """Configuration for geometry checks.

    Attributes
    ----------
    triangle_budgets:
        Mapping of asset category → (min_tris, max_tris).
    category:
        Which budget to enforce for this asset.  Defaults to ``"env_prop"``.
        (Note: the spec does not list category as an explicit field; it is
        added here as the simplest way to pass it alongside the budgets.)
    """
    triangle_budgets: dict[str, tuple[int, int]] = field(
        default_factory=lambda: dict(_DEFAULT_BUDGETS)
    )
    category: str = "env_prop"


# ---------------------------------------------------------------------------
# Abstractions (bpy implementations in blender_tests/tests.py)
# ---------------------------------------------------------------------------

class MeshObject(ABC):
    """A single mesh object in the scene."""

    @property
    @abstractmethod
    def name(self): ...

    @abstractmethod
    def triangle_count(self):
        """Return the total number of triangles in this object."""
        ...

    @abstractmethod
    def bmesh_get(self):
        """Return a ``bmesh.types.BMesh`` for this object.

        The caller must not free/release the returned object; the concrete
        implementation manages its lifetime.
        """
        ...


class BlenderContext(ABC):
    """Access to the loaded Blender scene."""

    @abstractmethod
    def mesh_objects(self) -> list[MeshObject]: ...


# ---------------------------------------------------------------------------
# Individual check helpers
# ---------------------------------------------------------------------------

def _check_polycount(
    mesh_objects: list[MeshObject],
    config: GeometryConfig,
) -> CheckResult:
    total = sum(obj.triangle_count() for obj in mesh_objects)
    budget = config.triangle_budgets.get(
        config.category, _DEFAULT_BUDGETS.get("env_prop", (500, 5_000))
    )
    min_tris, max_tris = budget

    if total < min_tris or total > max_tris:
        return CheckResult(
            name="polycount_budget",
            status=CheckStatus.FAIL,
            measured_value=total,
            threshold=max_tris,
            message=(
                f"Triangle count {total} outside budget "
                f"({min_tris}, {max_tris}) for '{config.category}'"
            ),
        )
    return CheckResult(
        name="polycount_budget",
        status=CheckStatus.PASS,
        measured_value=total,
        threshold=max_tris,
        message=f"Triangle count {total} within budget ({min_tris}, {max_tris})",
    )


def _check_non_manifold(all_bm) -> CheckResult:
    count = sum(1 for bm in all_bm for e in bm.edges if not e.is_manifold)
    return CheckResult(
        name="non_manifold",
        status=CheckStatus.FAIL if count > 0 else CheckStatus.PASS,
        measured_value=count,
        threshold=0,
        message=(
            f"{count} non-manifold edge(s) found"
            if count else "No non-manifold edges"
        ),
    )


def _check_degenerate_faces(all_bm) -> CheckResult:
    count = sum(1 for bm in all_bm for f in bm.faces if f.calc_area() < 1e-6)
    return CheckResult(
        name="degenerate_faces",
        status=CheckStatus.FAIL if count > 0 else CheckStatus.PASS,
        measured_value=count,
        threshold=0,
        message=(
            f"{count} degenerate face(s) found (area < 1e-6)"
            if count else "No degenerate faces"
        ),
    )


def _check_normal_consistency(all_bm) -> CheckResult:
    """Detect faces with inconsistent winding order relative to neighbours.

    Two faces that share an edge are *consistently* wound when they traverse
    that edge in *opposite* directions.  If both faces traverse the edge
    starting from the same vertex, one of them has a flipped normal.

    Uses ``edge.link_faces``, ``face.loops``, ``loop.edge`` and ``loop.vert``.
    """
    inconsistent = set()
    for bm in all_bm:
        for edge in bm.edges:
            if len(edge.link_faces) != 2:
                continue
            f1, f2 = edge.link_faces[0], edge.link_faces[1]

            v_in_f1 = None
            for loop in f1.loops:
                if loop.edge is edge:
                    v_in_f1 = loop.vert
                    break

            v_in_f2 = None
            for loop in f2.loops:
                if loop.edge is edge:
                    v_in_f2 = loop.vert
                    break

            # Same start-vert → both faces traverse the edge in the same
            # direction → normals are inconsistent.
            if v_in_f1 is not None and v_in_f2 is not None and v_in_f1 is v_in_f2:
                inconsistent.add(id(f1))
                inconsistent.add(id(f2))

    count = len(inconsistent)
    return CheckResult(
        name="normal_consistency",
        status=CheckStatus.FAIL if count > 0 else CheckStatus.PASS,
        measured_value=count,
        threshold=0,
        message=(
            f"{count} face(s) with inconsistent normals"
            if count else "Face normals consistent"
        ),
    )


def _check_loose_geometry(all_bm) -> CheckResult:
    """Count vertices with no linked faces and edges with no linked faces."""
    count = 0
    for bm in all_bm:
        count += sum(1 for v in bm.verts if len(v.link_faces) == 0)
        count += sum(1 for e in bm.edges if len(e.link_faces) == 0)
    return CheckResult(
        name="loose_geometry",
        status=CheckStatus.FAIL if count > 0 else CheckStatus.PASS,
        measured_value=count,
        threshold=0,
        message=(
            f"{count} loose vertex/edge element(s) found"
            if count else "No loose geometry"
        ),
    )


def _check_interior_faces(all_bm) -> CheckResult:
    """Heuristic: faces whose every edge is shared by more than 2 faces.

    When all of a face's edges have 3+ linked faces the face is likely
    enclosed inside the mesh volume (interior geometry).
    """
    count = 0
    for bm in all_bm:
        for face in bm.faces:
            if face.loops and all(
                len(loop.edge.link_faces) > 2 for loop in face.loops
            ):
                count += 1
    return CheckResult(
        name="interior_faces",
        status=CheckStatus.FAIL if count > 0 else CheckStatus.PASS,
        measured_value=count,
        threshold=0,
        message=(
            f"{count} potential interior face(s) found"
            if count else "No interior faces detected"
        ),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def check_geometry(context: BlenderContext, config: GeometryConfig) -> StageResult:
    """Run all geometry checks and return a ``StageResult``.

    All six checks always run — earlier failures do not short-circuit later
    checks.
    """
    mesh_objects = context.mesh_objects()
    all_bm = [obj.bmesh_get() for obj in mesh_objects]

    checks = [
        _check_polycount(mesh_objects, config),
        _check_non_manifold(all_bm),
        _check_degenerate_faces(all_bm),
        _check_normal_consistency(all_bm),
        _check_loose_geometry(all_bm),
        _check_interior_faces(all_bm),
    ]

    stage_status = (
        StageStatus.FAIL
        if any(c.status == CheckStatus.FAIL for c in checks)
        else StageStatus.PASS
    )
    return StageResult(name="geometry", status=stage_status, checks=checks)
