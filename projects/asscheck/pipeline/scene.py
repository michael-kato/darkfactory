"""Scene & Hierarchy Checks + Performance Estimates.

Validates scene-level conventions: object naming, orphan data, LOD and
collision mesh presence.  Computes performance estimates (draw calls, VRAM,
bone/skinning cost) and returns them alongside the stage result.

``check_scene`` returns a ``tuple[StageResult, PerformanceEstimates]``.  The
caller should pass the ``PerformanceEstimates`` to
``ReportBuilder.set_performance()``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from pipeline.schema import (
    CheckResult,
    PerformanceEstimates,
    StageResult,
    Status,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class SceneConfig:
    object_naming_pattern: str
    require_lod: bool
    require_collision: bool
    lod_suffix_pattern: str
    collision_suffix_pattern: str


# ---------------------------------------------------------------------------
# Individual check helpers
# ---------------------------------------------------------------------------

def _check_naming_conventions(mesh_objects, config: SceneConfig) -> CheckResult:
    pattern = re.compile(config.object_naming_pattern)
    violations = [obj.name for obj in mesh_objects if not pattern.match(obj.name)]
    count = len(violations)
    return CheckResult(
        name="naming_conventions",
        status=Status.WARNING if count > 0 else Status.PASS,
        value={"violations": violations, "count": count},
        threshold=config.object_naming_pattern,
        message=(
            f"{count} object name(s) do not match pattern "
            f"'{config.object_naming_pattern}'"
            if count
            else f"All object names match pattern '{config.object_naming_pattern}'"
        ),
    )


def _check_orphan_data(orphan_counts) -> CheckResult:
    total = sum(orphan_counts.values())
    return CheckResult(
        name="orphan_data",
        status=Status.WARNING if total > 0 else Status.PASS,
        value=total,
        threshold=0,
        message=(
            f"{total} orphan data block(s) found: {orphan_counts}"
            if total
            else "No orphan data blocks"
        ),
    )


def _check_lod_presence(mesh_objects, config: SceneConfig) -> CheckResult:
    if not config.require_lod:
        return CheckResult(
            name="lod_presence",
            status=Status.SKIPPED,
            value=0,
            threshold=None,
            message="LOD presence check skipped (not required)",
        )

    pattern = re.compile(config.lod_suffix_pattern)
    count = sum(1 for obj in mesh_objects if pattern.search(obj.name))

    if count == 0:
        return CheckResult(
            name="lod_presence",
            status=Status.FAIL,
            value=0,
            threshold=config.lod_suffix_pattern,
            message=f"No LOD objects found matching '{config.lod_suffix_pattern}' (required)",
        )

    return CheckResult(
        name="lod_presence",
        status=Status.PASS,
        value=count,
        threshold=config.lod_suffix_pattern,
        message=f"{count} LOD object(s) found matching '{config.lod_suffix_pattern}'",
    )


def _check_collision_presence(mesh_objects, config: SceneConfig) -> CheckResult:
    if not config.require_collision:
        return CheckResult(
            name="collision_presence",
            status=Status.SKIPPED,
            value=0,
            threshold=None,
            message="Collision presence check skipped (not required)",
        )

    pattern = re.compile(config.collision_suffix_pattern)
    count = sum(1 for obj in mesh_objects if pattern.search(obj.name))

    if count == 0:
        return CheckResult(
            name="collision_presence",
            status=Status.FAIL,
            value=0,
            threshold=config.collision_suffix_pattern,
            message=(
                f"No collision objects found matching "
                f"'{config.collision_suffix_pattern}' (required)"
            ),
        )

    return CheckResult(
        name="collision_presence",
        status=Status.PASS,
        value=count,
        threshold=config.collision_suffix_pattern,
        message=(
            f"{count} collision object(s) found matching "
            f"'{config.collision_suffix_pattern}'"
        ),
    )


# ---------------------------------------------------------------------------
# Performance estimate helpers
# ---------------------------------------------------------------------------

_MIP_MULTIPLIER = 4.0 / 3.0


def _compute_performance(mesh_objects, armature_objects, unique_images) -> PerformanceEstimates:
    triangles = sum(obj.triangle_count() for obj in mesh_objects)
    draw_calls = sum(obj.material_slot_count() for obj in mesh_objects)

    vram_mb = 0.0
    for img in unique_images:
        bytes_raw = img.width * img.height * img.channels * img.bit_depth / 8
        vram_mb += bytes_raw / 1024.0 / 1024.0 * _MIP_MULTIPLIER

    bones = sum(arm.bone_count() for arm in armature_objects)

    return PerformanceEstimates(
        triangles=triangles,
        draw_calls=draw_calls,
        vram_mb=vram_mb,
        bones=bones,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def check_scene(context, config: SceneConfig) -> tuple[StageResult, PerformanceEstimates]:
    """Run all scene checks and compute performance estimates."""
    mesh_objects = context.mesh_objects()
    armature_objects = context.armature_objects()
    unique_images = context.unique_images()
    orphan_counts = context.orphan_counts()

    checks = [
        _check_naming_conventions(mesh_objects, config),
        _check_orphan_data(orphan_counts),
        _check_lod_presence(mesh_objects, config),
        _check_collision_presence(mesh_objects, config),
    ]

    stage_status = (
        Status.FAIL
        if any(c.status == Status.FAIL for c in checks)
        else Status.PASS
    )

    stage_result = StageResult(name="scene", status=stage_status, checks=checks)
    perf = _compute_performance(mesh_objects, armature_objects, unique_images)

    return stage_result, perf
