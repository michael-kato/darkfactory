"""Blender integration test for Stage 1e — Armature & Rig Checks.

Run with:
    blender --background --python blender_tests/test_stage1e_blender.py

Loads the sample glTF asset (street_lamp_01_quant.gltf — no armature),
runs the armature checks with category 'env_prop', and asserts the result
is SKIPPED (no armature required for env_prop assets).
"""
from __future__ import annotations

import json
import os
import sys

try:
    import bpy
except ImportError:
    print("ERROR: bpy not available — run this script via Blender headless")
    sys.exit(1)

# Add the project root to sys.path so pipeline imports work.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from pipeline.schema import StageStatus  # noqa: E402
from pipeline.stage1.armature import (  # noqa: E402
    ArmatureBlenderContext,
    ArmatureBone,
    ArmatureConfig,
    ArmatureObject,
    SkinnedMesh,
    check_armature,
)


# ---------------------------------------------------------------------------
# Real bpy wrappers
# ---------------------------------------------------------------------------

class BpyArmatureBone(ArmatureBone):
    """Wraps a bpy.types.Bone."""

    def __init__(self, bone: "bpy.types.Bone") -> None:
        self._bone = bone

    @property
    def name(self) -> str:
        return self._bone.name

    @property
    def parent(self) -> "BpyArmatureBone | None":
        if self._bone.parent is None:
            return None
        return BpyArmatureBone(self._bone.parent)


class BpyArmatureObject(ArmatureObject):
    """Wraps a bpy.types.Object of type ARMATURE."""

    def __init__(self, obj: "bpy.types.Object") -> None:
        self._obj = obj

    @property
    def name(self) -> str:
        return self._obj.name

    def bones(self) -> list[BpyArmatureBone]:
        return [BpyArmatureBone(b) for b in self._obj.data.bones]


class BpySkinnedMesh(SkinnedMesh):
    """Wraps a bpy.types.Object of type MESH that has vertex groups."""

    def __init__(self, obj: "bpy.types.Object") -> None:
        self._obj = obj

    @property
    def name(self) -> str:
        return self._obj.name

    def per_vertex_weights(self) -> list[list[float]]:
        """Return non-zero weights per vertex, derived from vertex groups."""
        mesh = self._obj.data
        result: list[list[float]] = []
        for vert in mesh.vertices:
            weights = [g.weight for g in vert.groups if g.weight > 0.0]
            result.append(weights)
        return result


class BpyArmatureContext(ArmatureBlenderContext):
    """Reads armature objects and skinned meshes from the active Blender scene."""

    def armature_objects(self) -> list[BpyArmatureObject]:
        return [
            BpyArmatureObject(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "ARMATURE"
        ]

    def skinned_meshes(self) -> list[BpySkinnedMesh]:
        return [
            BpySkinnedMesh(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "MESH" and obj.vertex_groups
        ]


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def main() -> None:
    sample = os.path.join(
        _PROJECT_ROOT,
        "asscheck_uproj",
        "Assets",
        "Models",
        "street_lamp_01_quant.gltf",
    )

    if os.path.exists(sample):
        bpy.ops.import_scene.gltf(filepath=sample)
    else:
        print(f"WARNING: sample asset not found at {sample} — using default scene")

    ctx = BpyArmatureContext()
    config = ArmatureConfig(category="env_prop")
    result = check_armature(ctx, config)

    # Serialise to JSON and verify round-trip.
    stage_dict = {
        "name": result.name,
        "status": result.status.value,
        "checks": [
            {
                "name": c.name,
                "status": c.status.value,
                "measured_value": c.measured_value,
                "threshold": c.threshold,
                "message": c.message,
            }
            for c in result.checks
        ],
    }

    json_str = json.dumps(stage_dict, indent=2)
    data = json.loads(json_str)  # Verify it round-trips without error.

    assert data["name"] == "armature", (
        f"Expected stage name 'armature', got '{data['name']}'"
    )
    assert data["status"] == StageStatus.SKIPPED.value, (
        f"Expected SKIPPED for env_prop with no armature, got '{data['status']}'"
    )
    assert len(data["checks"]) >= 1, "Expected at least one check entry"

    print(json_str)
    print("PASS: Stage 1e armature integration test passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
