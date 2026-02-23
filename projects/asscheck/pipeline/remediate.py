"""Auto-Remediation.

Applies four deterministic auto-fix actions based on Stage 1 check results.
Every change is logged as a ``FixEntry`` with before/after values.  Issues
that cannot be safely auto-fixed are promoted to ``ReviewFlag`` entries.

"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from pipeline.schema import (
    CheckStatus,
    FixEntry,
    ReviewFlag,
    Severity,
    StageResult,
    StageStatus,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class RemediationConfig:
    """Configuration for the auto-remediation stage.

    Attributes
    ----------
    merge_distance:
        Threshold for merge-by-distance (``bpy.ops.mesh.remove_doubles``).
    max_bone_influences:
        Hard limit for skinning influences per vertex.
    max_texture_resolution:
        Maximum texture dimension (pixels) for standard assets.
    hero_asset:
        If True, use 4096 as the texture resolution limit instead of
        ``max_texture_resolution``.
    """

    merge_distance: float = 0.0001
    max_bone_influences: int = 4
    max_texture_resolution: int = 2048
    hero_asset: bool = False


# ---------------------------------------------------------------------------
# Abstractions (bpy implementations in blender_tests/tests.py)
# ---------------------------------------------------------------------------

class RemediationMeshObject(ABC):
    """A mesh object that can have geometry fixes applied to it."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def vertex_count(self) -> int:
        """Return the current number of vertices."""
        ...

    @abstractmethod
    def recalculate_normals(self) -> None:
        """Call bpy.ops.mesh.normals_make_consistent(inside=False) on this object."""
        ...

    @abstractmethod
    def merge_by_distance(self, threshold: float) -> int:
        """Call bpy.ops.mesh.remove_doubles(threshold=threshold) on this object.

        Returns the vertex count *after* the merge.
        """
        ...


class RemediationImage(ABC):
    """An image that can be resized."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def size(self) -> tuple[int, int]:
        """Return (width, height) in pixels."""
        ...

    @abstractmethod
    def scale(self, new_w: int, new_h: int) -> None:
        """Call image.scale(new_w, new_h) to resize in-place."""
        ...


class RemediationSkinnedMesh(ABC):
    """A skinned mesh whose per-vertex influence count can be inspected."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def max_influences(self) -> int:
        """Return the maximum number of non-zero weight influences on any vertex."""
        ...


class RemediationBlenderContext(ABC):
    """Access to the Blender scene for remediation."""

    @abstractmethod
    def mesh_objects(self) -> list[RemediationMeshObject]: ...

    @abstractmethod
    def images(self) -> list[RemediationImage]: ...

    @abstractmethod
    def skinned_meshes(self) -> list[RemediationSkinnedMesh]: ...

    @abstractmethod
    def limit_bone_weights(self, limit: int) -> None:
        """Call vertex_group_limit_total(limit=limit) then vertex_group_normalize_all()
        on all objects in the scene.
        """
        ...


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_check(
    stage1_results: list[StageResult],
    stage_name: str,
    check_name: str,
):
    """Return the first CheckResult matching stage_name and check_name, or None."""
    for stage in stage1_results:
        if stage.name == stage_name:
            for check in stage.checks:
                if check.name == check_name:
                    return check
    return None


def _largest_pot(n: int) -> int:
    """Return the largest power-of-two that is ≤ n (minimum 1)."""
    if n <= 0:
        return 1
    pot = 1
    while pot * 2 <= n:
        pot *= 2
    return pot


def _compute_new_size(w: int, h: int, limit: int) -> tuple[int, int]:
    """Compute resized (width, height) preserving aspect ratio.

    The largest dimension is scaled to the largest PoT ≤ limit.  The other
    dimension is scaled proportionally and also rounded to the largest PoT
    that fits within the proportionally-scaled value.
    """
    max_dim = max(w, h)
    target = _largest_pot(limit)
    scale = target / max_dim
    return _largest_pot(int(w * scale)), _largest_pot(int(h * scale))


# ---------------------------------------------------------------------------
# Review-flag rules
# ---------------------------------------------------------------------------

# (stage_name, check_name, trigger_status, severity, description)
_REVIEW_RULES: list[tuple[str, str, CheckStatus, Severity, str]] = [
    (
        "uv", "uv_overlap", CheckStatus.FAIL, Severity.WARNING,
        "UV islands overlap; may be intentional (mirroring/tiling)",
    ),
    (
        "pbr", "albedo_range", CheckStatus.WARNING, Severity.WARNING,
        "Albedo values outside PBR range; may be stylistic",
    ),
    (
        "pbr", "metalness_binary", CheckStatus.WARNING, Severity.WARNING,
        "Metalness gradient detected; verify intent",
    ),
    (
        "pbr", "roughness_range", CheckStatus.WARNING, Severity.WARNING,
        "Extreme roughness values; verify intent",
    ),
    (
        "geometry", "non_manifold", CheckStatus.FAIL, Severity.ERROR,
        "Non-manifold geometry; requires manual retopology",
    ),
    (
        "geometry", "interior_faces", CheckStatus.FAIL, Severity.ERROR,
        "Interior faces; requires manual removal",
    ),
    (
        "uv", "texel_density", CheckStatus.WARNING, Severity.WARNING,
        "Texel density outliers; requires artistic judgment",
    ),
    (
        "scene", "lod_presence", CheckStatus.FAIL, Severity.WARNING,
        "LODs missing; requires artist to create",
    ),
]


def _collect_review_flags(stage1_results: list[StageResult]) -> list[ReviewFlag]:
    """Build the human review queue from stage1 results."""
    flags: list[ReviewFlag] = []

    for stage_name, check_name, trigger_status, severity, description in _REVIEW_RULES:
        check = _find_check(stage1_results, stage_name, check_name)
        if check and check.status == trigger_status:
            flags.append(ReviewFlag(
                issue=f"{stage_name}:{check_name}",
                severity=severity,
                description=description,
            ))

    # Any polycount FAIL
    polycount_check = _find_check(stage1_results, "geometry", "polycount_budget")
    if polycount_check and polycount_check.status == CheckStatus.FAIL:
        flags.append(ReviewFlag(
            issue="geometry:polycount_budget",
            severity=Severity.ERROR,
            description="Polycount violation; requires manual retopology or LOD",
        ))

    return flags


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_remediation(
    context: RemediationBlenderContext,
    stage1_results: list[StageResult],
    config: RemediationConfig,
) -> StageResult:
    """Apply auto-fix actions and populate the human review queue.

    Each fix is applied only when the corresponding Stage 1 check returned
    FAIL.  Issues that cannot be safely auto-fixed are added as
    ``ReviewFlag`` entries without modifying the scene.

    Always returns ``StageResult(name="remediation", status=PASS, ...)``
    because remediation does not fail the pipeline — it either fixes or flags.
    """
    fixes: list[FixEntry] = []

    # ------------------------------------------------------------------
    # Fix 1: recalculate_normals
    # Trigger: geometry:normal_consistency FAIL
    # ------------------------------------------------------------------
    normal_check = _find_check(stage1_results, "geometry", "normal_consistency")
    if normal_check and normal_check.status == CheckStatus.FAIL:
        before_count = normal_check.measured_value
        for obj in context.mesh_objects():
            obj.recalculate_normals()
            fixes.append(FixEntry(
                action="recalculate_normals",
                target=obj.name,
                before_value=before_count,
                after_value=0,
            ))

    # ------------------------------------------------------------------
    # Fix 2: merge_by_distance
    # Trigger: geometry:degenerate_faces FAIL OR geometry:loose_geometry FAIL
    # ------------------------------------------------------------------
    degenerate_check = _find_check(stage1_results, "geometry", "degenerate_faces")
    loose_check = _find_check(stage1_results, "geometry", "loose_geometry")
    needs_merge = (
        (degenerate_check is not None and degenerate_check.status == CheckStatus.FAIL)
        or (loose_check is not None and loose_check.status == CheckStatus.FAIL)
    )
    if needs_merge:
        for obj in context.mesh_objects():
            before_verts = obj.vertex_count()
            after_verts = obj.merge_by_distance(config.merge_distance)
            fixes.append(FixEntry(
                action="merge_by_distance",
                target=obj.name,
                before_value=before_verts,
                after_value=after_verts,
            ))

    # ------------------------------------------------------------------
    # Fix 3: resize_textures
    # Trigger: texture:resolution_limit FAIL
    # ------------------------------------------------------------------
    texture_check = _find_check(stage1_results, "texture", "resolution_limit")
    if texture_check and texture_check.status == CheckStatus.FAIL:
        limit = 4096 if config.hero_asset else config.max_texture_resolution
        for img in context.images():
            w, h = img.size
            if w > limit or h > limit:
                new_w, new_h = _compute_new_size(w, h, limit)
                img.scale(new_w, new_h)
                fixes.append(FixEntry(
                    action="resize_textures",
                    target=img.name,
                    before_value=[w, h],
                    after_value=[new_w, new_h],
                ))

    # ------------------------------------------------------------------
    # Fix 4: limit_bone_weights
    # Trigger: armature:vertex_weights FAIL
    # ------------------------------------------------------------------
    weight_check = _find_check(stage1_results, "armature", "vertex_weights")
    if weight_check and weight_check.status == CheckStatus.FAIL:
        skinned = context.skinned_meshes()
        before_max = max((m.max_influences() for m in skinned), default=0)
        context.limit_bone_weights(config.max_bone_influences)
        fixes.append(FixEntry(
            action="limit_bone_weights",
            target="scene",
            before_value=before_max,
            after_value=config.max_bone_influences,
        ))

    # ------------------------------------------------------------------
    # Human review queue — flag but do NOT modify the scene
    # ------------------------------------------------------------------
    review_flags = _collect_review_flags(stage1_results)

    return StageResult(
        name="remediation",
        status=StageStatus.PASS,
        fixes=fixes,
        review_flags=review_flags,
    )
