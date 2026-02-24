"""Autofix.

Applies four deterministic auto-fix actions based on Stage 1 check results.
Every change is logged as a ``FixEntry`` with before/after values.  Issues
that cannot be safely auto-fixed are promoted to ``ReviewFlag`` entries.
"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.schema import (
    FixEntry,
    ReviewFlag,
    StageResult,
    Status,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class AutofixConfig:
    merge_distance: float = 0.0001
    max_bone_influences: int = 4
    max_texture_resolution: int = 2048
    hero_asset: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_check(stage1_results: list[StageResult], stage_name, check_name):
    for stage in stage1_results:
        if stage.name == stage_name:
            for check in stage.checks:
                if check.name == check_name:
                    return check
    return None


def _largest_pot(n):
    if n <= 0:
        return 1
    pot = 1
    while pot * 2 <= n:
        pot *= 2
    return pot


def _compute_new_size(w, h, limit):
    max_dim = max(w, h)
    target = _largest_pot(limit)
    scale = target / max_dim
    return _largest_pot(int(w * scale)), _largest_pot(int(h * scale))


# ---------------------------------------------------------------------------
# Review-flag rules
# (stage_name, check_name, trigger_status, severity, description)
# ---------------------------------------------------------------------------

_REVIEW_RULES = [
    ("uv", "uv_overlap", Status.FAIL, Status.WARNING,
     "UV islands overlap; may be intentional (mirroring/tiling)"),
    ("pbr", "albedo_range", Status.WARNING, Status.WARNING,
     "Albedo values outside PBR range; may be stylistic"),
    ("pbr", "metalness_binary", Status.WARNING, Status.WARNING,
     "Metalness gradient detected; verify intent"),
    ("pbr", "roughness_range", Status.WARNING, Status.WARNING,
     "Extreme roughness values; verify intent"),
    ("geometry", "non_manifold", Status.FAIL, Status.ERROR,
     "Non-manifold geometry; requires manual retopology"),
    ("geometry", "interior_faces", Status.FAIL, Status.ERROR,
     "Interior faces; requires manual removal"),
    ("uv", "texel_density", Status.WARNING, Status.WARNING,
     "Texel density outliers; requires artistic judgment"),
    ("scene", "lod_presence", Status.FAIL, Status.WARNING,
     "LODs missing; requires artist to create"),
]


def _collect_review_flags(stage1_results: list[StageResult]) -> list[ReviewFlag]:
    flags: list[ReviewFlag] = []

    for stage_name, check_name, trigger_status, severity, description in _REVIEW_RULES:
        check = _find_check(stage1_results, stage_name, check_name)
        if check and check.status == trigger_status:
            flags.append(ReviewFlag(
                issue=f"{stage_name}:{check_name}",
                severity=severity,
                description=description,
            ))

    polycount_check = _find_check(stage1_results, "geometry", "polycount_budget")
    if polycount_check and polycount_check.status == Status.FAIL:
        flags.append(ReviewFlag(
            issue="geometry:polycount_budget",
            severity=Status.ERROR,
            description="Polycount violation; requires manual retopology or LOD",
        ))

    return flags


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_autofix(context, stage1_results: list[StageResult], config: AutofixConfig) -> StageResult:
    """Apply auto-fix actions and populate the human review queue.

    Always returns ``StageResult(name="autofix", status=PASS, ...)``
    because autofix does not fail the pipeline — it either fixes or flags.
    """
    fixes: list[FixEntry] = []

    # Fix 1: recalculate_normals
    normal_check = _find_check(stage1_results, "geometry", "normal_consistency")
    if normal_check and normal_check.status == Status.FAIL:
        before_count = normal_check.value
        for obj in context.mesh_objects():
            obj.recalculate_normals()
            fixes.append(FixEntry(
                action="recalculate_normals",
                target=obj.name,
                before=before_count,
                after=0,
            ))

    # Fix 2: merge_by_distance
    degenerate_check = _find_check(stage1_results, "geometry", "degenerate_faces")
    loose_check = _find_check(stage1_results, "geometry", "loose_geometry")
    needs_merge = (
        (degenerate_check is not None and degenerate_check.status == Status.FAIL)
        or (loose_check is not None and loose_check.status == Status.FAIL)
    )
    if needs_merge:
        for obj in context.mesh_objects():
            before_verts = obj.vertex_count()
            after_verts = obj.merge_by_distance(config.merge_distance)
            fixes.append(FixEntry(
                action="merge_by_distance",
                target=obj.name,
                before=before_verts,
                after=after_verts,
            ))

    # Fix 3: resize_textures
    texture_check = _find_check(stage1_results, "texture", "resolution_limit")
    if texture_check and texture_check.status == Status.FAIL:
        limit = 4096 if config.hero_asset else config.max_texture_resolution
        for img in context.images():
            w, h = img.size
            if w > limit or h > limit:
                new_w, new_h = _compute_new_size(w, h, limit)
                img.scale(new_w, new_h)
                fixes.append(FixEntry(
                    action="resize_textures",
                    target=img.name,
                    before=[w, h],
                    after=[new_w, new_h],
                ))

    # Fix 4: limit_bone_weights
    weight_check = _find_check(stage1_results, "armature", "vertex_weights")
    if weight_check and weight_check.status == Status.FAIL:
        skinned = context.skinned_meshes()
        before_max = max((m.max_influences() for m in skinned), default=0)
        context.limit_bone_weights(config.max_bone_influences)
        fixes.append(FixEntry(
            action="limit_bone_weights",
            target="scene",
            before=before_max,
            after=config.max_bone_influences,
        ))

    review_flags = _collect_review_flags(stage1_results)

    return StageResult(
        name="autofix",
        status=Status.PASS,
        fixes=fixes,
        flags=review_flags,
    )
