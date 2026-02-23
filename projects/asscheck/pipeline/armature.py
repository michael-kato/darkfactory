"""Armature & Rig Checks.

Validates armature and skinning data: bone count budgets, naming conventions,
vertex weight validity, and bone hierarchy integrity.

Non-character assets without armatures skip this check cleanly via an early
exit.  Character (or other category-requiring) assets that are missing an
armature receive a FAIL on the ``armature_present`` check instead.

The ArmatureBone / ArmatureObject / SkinnedMesh / ArmatureBlenderContext ABCs
allow pure-Python unit testing via mock implementations that never import bpy.

``per_vertex_weights()`` contract
----------------------------------
``per_vertex_weights()[i]`` returns the list of *non-zero* weight values for
vertex *i*.  An empty list signals that vertex *i* has no group assignments
(zero total weight).
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from pipeline.schema import CheckResult, CheckStatus, StageResult, StageStatus


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ArmatureConfig:
    """Configuration for armature and rig validation checks.

    Attributes
    ----------
    max_bones:
        Total bone budget across all armatures in the scene.
    max_influences_per_vertex:
        Maximum number of non-zero vertex group weights per vertex.
    bone_naming_pattern:
        Compiled regex string that every bone name must match.
        ``None`` disables the naming check.
    categories_requiring_armature:
        Asset categories for which a missing armature is an error.
    category:
        The category of the asset being checked.
    """

    max_bones: int = 75
    max_influences_per_vertex: int = 4
    bone_naming_pattern: str | None = None
    categories_requiring_armature: list[str] = field(
        default_factory=lambda: ["character"]
    )
    category: str = "env_prop"


# ---------------------------------------------------------------------------
# Abstractions (implemented by real bpy wrappers and by test mocks)
# ---------------------------------------------------------------------------

class ArmatureBone(ABC):
    """A single bone inside an armature."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def parent(self) -> "ArmatureBone | None":
        """Parent bone, or ``None`` if this is a root bone."""
        ...


class ArmatureObject(ABC):
    """An armature object in the scene."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def bones(self) -> list[ArmatureBone]: ...


class SkinnedMesh(ABC):
    """A mesh object with vertex group (skinning) data."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def per_vertex_weights(self) -> list[list[float]]:
        """Return one entry per vertex — a list of its *non-zero* weights.

        Vertices with no group assignment return an empty list ``[]``.
        """
        ...


class ArmatureBlenderContext(ABC):
    """Access to armature and skinned-mesh data (real bpy scene or test mock)."""

    @abstractmethod
    def armature_objects(self) -> list[ArmatureObject]: ...

    @abstractmethod
    def skinned_meshes(self) -> list[SkinnedMesh]: ...


# ---------------------------------------------------------------------------
# Individual check helpers
# ---------------------------------------------------------------------------

def _check_armature_present(
    armatures: list[ArmatureObject],
    config: ArmatureConfig,
) -> CheckResult:
    present = len(armatures) > 0
    required = config.category in config.categories_requiring_armature

    if not present and required:
        return CheckResult(
            name="armature_present",
            status=CheckStatus.FAIL,
            measured_value=0,
            threshold=1,
            message=(
                f"Category '{config.category}' requires an armature but none found"
            ),
        )

    return CheckResult(
        name="armature_present",
        status=CheckStatus.PASS,
        measured_value=len(armatures),
        threshold=1,
        message=(
            f"{len(armatures)} armature(s) found"
            if present
            else f"No armature (not required for category '{config.category}')"
        ),
    )


def _check_bone_count(
    armatures: list[ArmatureObject],
    config: ArmatureConfig,
) -> CheckResult:
    total = sum(len(arm.bones()) for arm in armatures)

    if total > config.max_bones:
        return CheckResult(
            name="bone_count",
            status=CheckStatus.FAIL,
            measured_value=total,
            threshold=config.max_bones,
            message=f"Total bone count {total} exceeds limit {config.max_bones}",
        )
    return CheckResult(
        name="bone_count",
        status=CheckStatus.PASS,
        measured_value=total,
        threshold=config.max_bones,
        message=f"Total bone count {total} within limit {config.max_bones}",
    )


def _check_bone_naming(
    armatures: list[ArmatureObject],
    config: ArmatureConfig,
) -> CheckResult:
    if config.bone_naming_pattern is None:
        return CheckResult(
            name="bone_naming",
            status=CheckStatus.SKIPPED,
            measured_value={"violations": [], "count": 0},
            threshold=None,
            message="Bone naming check skipped (no pattern configured)",
        )

    pattern = re.compile(config.bone_naming_pattern)
    violations: list[str] = []
    for arm in armatures:
        for bone in arm.bones():
            if not pattern.match(bone.name):
                violations.append(bone.name)

    count = len(violations)
    return CheckResult(
        name="bone_naming",
        status=CheckStatus.FAIL if count > 0 else CheckStatus.PASS,
        measured_value={"violations": violations, "count": count},
        threshold=config.bone_naming_pattern,
        message=(
            f"{count} bone name(s) do not match pattern '{config.bone_naming_pattern}'"
            if count
            else f"All bone names match pattern '{config.bone_naming_pattern}'"
        ),
    )


def _check_vertex_weights(
    skinned_meshes: list[SkinnedMesh],
    config: ArmatureConfig,
) -> CheckResult:
    zero_weight_count = 0
    excess_influences_count = 0
    unnormalized_count = 0

    for mesh in skinned_meshes:
        for weights in mesh.per_vertex_weights():
            total = sum(weights)
            if total < 1e-6:
                # Vertex has no meaningful weight assignment.
                zero_weight_count += 1
            else:
                if len(weights) > config.max_influences_per_vertex:
                    excess_influences_count += 1
                if abs(total - 1.0) > 0.001:
                    unnormalized_count += 1

    measured: dict = {
        "zero_weight_count": zero_weight_count,
        "excess_influences_count": excess_influences_count,
        "unnormalized_count": unnormalized_count,
    }

    has_violation = (
        zero_weight_count > 0
        or excess_influences_count > 0
        or unnormalized_count > 0
    )

    if has_violation:
        parts: list[str] = []
        if zero_weight_count:
            parts.append(f"{zero_weight_count} zero-weight vertex(ices)")
        if excess_influences_count:
            parts.append(
                f"{excess_influences_count} vertex(ices) with >{config.max_influences_per_vertex} influences"
            )
        if unnormalized_count:
            parts.append(f"{unnormalized_count} unnormalized vertex(ices)")
        return CheckResult(
            name="vertex_weights",
            status=CheckStatus.FAIL,
            measured_value=measured,
            threshold=config.max_influences_per_vertex,
            message="; ".join(parts),
        )

    return CheckResult(
        name="vertex_weights",
        status=CheckStatus.PASS,
        measured_value=measured,
        threshold=config.max_influences_per_vertex,
        message="All vertex weights valid",
    )


def _check_bone_hierarchy(armatures: list[ArmatureObject]) -> CheckResult:
    """Verify each armature has exactly one root bone.

    A root bone is one with ``parent is None``.  Any armature with more than
    one root bone contributes ``(root_count - 1)`` orphan bones to the total.
    """
    total_root_count = 0
    total_orphan_count = 0

    for arm in armatures:
        roots = [b for b in arm.bones() if b.parent is None]
        root_count = len(roots)
        total_root_count += root_count
        if root_count > 1:
            total_orphan_count += root_count - 1

    measured: dict = {
        "root_count": total_root_count,
        "orphan_count": total_orphan_count,
    }

    if total_orphan_count > 0:
        return CheckResult(
            name="bone_hierarchy",
            status=CheckStatus.FAIL,
            measured_value=measured,
            threshold={"max_roots_per_armature": 1},
            message=(
                f"Hierarchy invalid: {total_root_count} root bone(s), "
                f"{total_orphan_count} orphan bone(s)"
            ),
        )

    return CheckResult(
        name="bone_hierarchy",
        status=CheckStatus.PASS,
        measured_value=measured,
        threshold={"max_roots_per_armature": 1},
        message=(
            f"Bone hierarchy valid: {total_root_count} root bone(s), no orphans"
        ),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def check_armature(
    context: ArmatureBlenderContext,
    config: ArmatureConfig,
) -> StageResult:
    """Run all armature checks and return a ``StageResult``.

    Early-exits with ``StageStatus.SKIPPED`` when no armatures are present and
    the asset category does not require one.
    """
    armatures = context.armature_objects()

    # Early exit: no armature and category doesn't require one.
    if not armatures and config.category not in config.categories_requiring_armature:
        return StageResult(
            name="armature",
            status=StageStatus.SKIPPED,
            checks=[
                CheckResult(
                    name="armature_present",
                    status=CheckStatus.SKIPPED,
                    measured_value=0,
                    threshold=None,
                    message=(
                        f"No armature; category '{config.category}' does not require one"
                    ),
                )
            ],
        )

    skinned_meshes = context.skinned_meshes()

    checks = [
        _check_armature_present(armatures, config),
        _check_bone_count(armatures, config),
        _check_bone_naming(armatures, config),
        _check_vertex_weights(skinned_meshes, config),
        _check_bone_hierarchy(armatures),
    ]

    stage_status = (
        StageStatus.FAIL
        if any(c.status == CheckStatus.FAIL for c in checks)
        else StageStatus.PASS
    )
    return StageResult(name="armature", status=stage_status, checks=checks)
