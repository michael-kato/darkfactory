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
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pipeline.schema import (
    CheckResult,
    CheckStatus,
    PerformanceEstimates,
    StageResult,
    StageStatus,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class SceneConfig:
    """Configuration for scene and hierarchy validation checks.

    Attributes
    ----------
    object_naming_pattern:
        Regex that every mesh object name must match (WARNING if violated).
    require_lod:
        If ``True``, at least one object matching ``lod_suffix_pattern`` must
        exist (FAIL if absent).
    require_collision:
        If ``True``, at least one object matching ``collision_suffix_pattern``
        must exist (FAIL if absent).
    lod_suffix_pattern:
        Regex matched against object names to detect LOD meshes, e.g.
        ``r"_LOD\\d+$"``.
    collision_suffix_pattern:
        Regex matched against object names to detect collision meshes, e.g.
        ``r"_Collision$"``.
    """

    object_naming_pattern: str
    require_lod: bool
    require_collision: bool
    lod_suffix_pattern: str
    collision_suffix_pattern: str


# ---------------------------------------------------------------------------
# Abstractions (bpy implementations in blender_tests/tests.py)
# ---------------------------------------------------------------------------

class SceneMeshObject(ABC):
    """A mesh object present in the scene."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def triangle_count(self) -> int: ...

    @abstractmethod
    def material_slot_count(self) -> int: ...


class SceneArmatureObject(ABC):
    """An armature object present in the scene."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def bone_count(self) -> int: ...


class SceneImage(ABC):
    """An image data-block used for VRAM estimation."""

    @property
    @abstractmethod
    def width(self) -> int: ...

    @property
    @abstractmethod
    def height(self) -> int: ...

    @property
    @abstractmethod
    def channels(self) -> int:
        """Number of colour channels (e.g. 3 for RGB, 4 for RGBA)."""
        ...

    @property
    @abstractmethod
    def bit_depth(self) -> int:
        """Bits per channel per pixel (e.g. 8 for standard 8-bit images)."""
        ...


class SceneBlenderContext(ABC):
    """Access to scene data in the Blender scene."""

    @abstractmethod
    def mesh_objects(self) -> list[SceneMeshObject]: ...

    @abstractmethod
    def armature_objects(self) -> list[SceneArmatureObject]: ...

    @abstractmethod
    def unique_images(self) -> list[SceneImage]:
        """Return the de-duplicated list of images referenced in the scene."""
        ...

    @abstractmethod
    def orphan_counts(self) -> dict[str, int]:
        """Return counts of data-blocks with zero users.

        Expected keys: ``'meshes'``, ``'materials'``, ``'images'``.
        """
        ...


# ---------------------------------------------------------------------------
# Individual check helpers
# ---------------------------------------------------------------------------

def _check_naming_conventions(
    mesh_objects: list[SceneMeshObject],
    config: SceneConfig,
) -> CheckResult:
    pattern = re.compile(config.object_naming_pattern)
    violations = [obj.name for obj in mesh_objects if not pattern.match(obj.name)]
    count = len(violations)
    return CheckResult(
        name="naming_conventions",
        status=CheckStatus.WARNING if count > 0 else CheckStatus.PASS,
        measured_value={"violations": violations, "count": count},
        threshold=config.object_naming_pattern,
        message=(
            f"{count} object name(s) do not match pattern "
            f"'{config.object_naming_pattern}'"
            if count
            else f"All object names match pattern '{config.object_naming_pattern}'"
        ),
    )


def _check_orphan_data(orphan_counts: dict[str, int]) -> CheckResult:
    total = sum(orphan_counts.values())
    return CheckResult(
        name="orphan_data",
        status=CheckStatus.WARNING if total > 0 else CheckStatus.PASS,
        measured_value=total,
        threshold=0,
        message=(
            f"{total} orphan data block(s) found: {orphan_counts}"
            if total
            else "No orphan data blocks"
        ),
    )


def _check_lod_presence(
    mesh_objects: list[SceneMeshObject],
    config: SceneConfig,
) -> CheckResult:
    if not config.require_lod:
        return CheckResult(
            name="lod_presence",
            status=CheckStatus.SKIPPED,
            measured_value=0,
            threshold=None,
            message="LOD presence check skipped (not required)",
        )

    pattern = re.compile(config.lod_suffix_pattern)
    lod_names = [obj.name for obj in mesh_objects if pattern.search(obj.name)]
    count = len(lod_names)

    if count == 0:
        return CheckResult(
            name="lod_presence",
            status=CheckStatus.FAIL,
            measured_value=0,
            threshold=config.lod_suffix_pattern,
            message=(
                f"No LOD objects found matching '{config.lod_suffix_pattern}' "
                f"(required)"
            ),
        )

    return CheckResult(
        name="lod_presence",
        status=CheckStatus.PASS,
        measured_value=count,
        threshold=config.lod_suffix_pattern,
        message=f"{count} LOD object(s) found matching '{config.lod_suffix_pattern}'",
    )


def _check_collision_presence(
    mesh_objects: list[SceneMeshObject],
    config: SceneConfig,
) -> CheckResult:
    if not config.require_collision:
        return CheckResult(
            name="collision_presence",
            status=CheckStatus.SKIPPED,
            measured_value=0,
            threshold=None,
            message="Collision presence check skipped (not required)",
        )

    pattern = re.compile(config.collision_suffix_pattern)
    collision_names = [obj.name for obj in mesh_objects if pattern.search(obj.name)]
    count = len(collision_names)

    if count == 0:
        return CheckResult(
            name="collision_presence",
            status=CheckStatus.FAIL,
            measured_value=0,
            threshold=config.collision_suffix_pattern,
            message=(
                f"No collision objects found matching "
                f"'{config.collision_suffix_pattern}' (required)"
            ),
        )

    return CheckResult(
        name="collision_presence",
        status=CheckStatus.PASS,
        measured_value=count,
        threshold=config.collision_suffix_pattern,
        message=(
            f"{count} collision object(s) found matching "
            f"'{config.collision_suffix_pattern}'"
        ),
    )


# ---------------------------------------------------------------------------
# Performance estimate helpers
# ---------------------------------------------------------------------------

_MIP_MULTIPLIER: float = 4.0 / 3.0


def _compute_performance(
    mesh_objects: list[SceneMeshObject],
    armature_objects: list[SceneArmatureObject],
    unique_images: list[SceneImage],
) -> PerformanceEstimates:
    triangle_count = sum(obj.triangle_count() for obj in mesh_objects)
    draw_call_estimate = sum(obj.material_slot_count() for obj in mesh_objects)

    vram_estimate_mb = 0.0
    for img in unique_images:
        bytes_raw = img.width * img.height * img.channels * img.bit_depth / 8
        vram_estimate_mb += bytes_raw / 1024.0 / 1024.0 * _MIP_MULTIPLIER

    bone_count = sum(arm.bone_count() for arm in armature_objects)

    return PerformanceEstimates(
        triangle_count=triangle_count,
        draw_call_estimate=draw_call_estimate,
        vram_estimate_mb=vram_estimate_mb,
        bone_count=bone_count,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def check_scene(
    context: SceneBlenderContext,
    config: SceneConfig,
) -> tuple[StageResult, PerformanceEstimates]:
    """Run all scene checks and compute performance estimates.

    Returns a ``(StageResult, PerformanceEstimates)`` tuple.  The caller should
    pass the ``PerformanceEstimates`` to ``ReportBuilder.set_performance()``.
    """
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
        StageStatus.FAIL
        if any(c.status == CheckStatus.FAIL for c in checks)
        else StageStatus.PASS
    )

    stage_result = StageResult(name="scene", status=stage_status, checks=checks)
    perf = _compute_performance(mesh_objects, armature_objects, unique_images)

    return stage_result, perf
