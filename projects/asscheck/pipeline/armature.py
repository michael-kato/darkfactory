"""Armature & Rig Checks.

Validates armature and skinning data: bone count budgets, naming conventions,
vertex weight validity, and bone hierarchy integrity.

Non-character assets without armatures skip this check cleanly via an early
exit.  Character (or other category-requiring) assets that are missing an
armature receive a FAIL on the ``armature_present`` check instead.

``per_vertex_weights()`` contract
----------------------------------
``per_vertex_weights()[i]`` returns the list of *non-zero* weight values for
vertex *i*.  An empty list signals that vertex *i* has no group assignments
(zero total weight).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from pipeline.schema import CheckResult, StageResult, Status

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

def _check_armature_present(
    armatures: list[ArmatureObject],
    config: ArmatureConfig,
) -> CheckResult:
    present = len(armatures) > 0
    required = config.category in config.categories_requiring_armature

    if not present and required:
        return CheckResult(
            name="armature_present",
            status=Status.FAIL,
            value=0,
            threshold=1,
            message=(
                f"Category '{config.category}' requires an armature but none found"
            ),
        )

    return CheckResult(
        name="armature_present",
        status=Status.PASS,
        value=len(armatures),
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
            status=Status.FAIL,
            value=total,
            threshold=config.max_bones,
            message=f"Total bone count {total} exceeds limit {config.max_bones}",
        )
    return CheckResult(
        name="bone_count",
        status=Status.PASS,
        value=total,
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
            status=Status.SKIPPED,
            value={"violations": [], "count": 0},
            threshold=None,
            message="Bone naming check skipped (no pattern configured)",
        )

    pattern = re.compile(config.bone_naming_pattern)
    violations = []
    for arm in armatures:
        for bone in arm.bones():
            if not pattern.match(bone.name):
                violations.append(bone.name)

    count = len(violations)
    return CheckResult(
        name="bone_naming",
        status=Status.FAIL if count > 0 else Status.PASS,
        value={"violations": violations, "count": count},
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

    measured = {
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
        parts = []
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
            status=Status.FAIL,
            value=measured,
            threshold=config.max_influences_per_vertex,
            message="; ".join(parts),
        )

    return CheckResult(
        name="vertex_weights",
        status=Status.PASS,
        value=measured,
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

    measured = {
        "root_count": total_root_count,
        "orphan_count": total_orphan_count,
    }

    if total_orphan_count > 0:
        return CheckResult(
            name="bone_hierarchy",
            status=Status.FAIL,
            value=measured,
            threshold={"max_roots_per_armature": 1},
            message=(
                f"Hierarchy invalid: {total_root_count} root bone(s), "
                f"{total_orphan_count} orphan bone(s)"
            ),
        )

    return CheckResult(
        name="bone_hierarchy",
        status=Status.PASS,
        value=measured,
        threshold={"max_roots_per_armature": 1},
        message=(
            f"Bone hierarchy valid: {total_root_count} root bone(s), no orphans"
        ),
    )

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def check_armature(
    context,
    config: ArmatureConfig,
) -> StageResult:
    """Run all armature checks and return a ``StageResult``.

    Early-exits with ``Status.SKIPPED`` when no armatures are present and
    the asset category does not require one.
    """
    armatures = context.armature_objects()

    # Early exit: no armature and category doesn't require one.
    if not armatures and config.category not in config.categories_requiring_armature:
        return StageResult(
            name="armature",
            status=Status.SKIPPED,
            checks=[
                CheckResult(
                    name="armature_present",
                    status=Status.SKIPPED,
                    value=0,
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
        Status.FAIL
        if any(c.status == Status.FAIL for c in checks)
        else Status.PASS
    )
    return StageResult(name="armature", status=stage_status, checks=checks)
