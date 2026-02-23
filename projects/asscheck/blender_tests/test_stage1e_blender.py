"""Integration test for Stage 1e armature checks — runs inside Blender headless.

Usage (headless):  blender --background --python blender_tests/test_stage1e_blender.py
Usage (GUI):       Open in Blender Text Editor, press Alt+R

Tests:
  1. env_prop category with no armature → stage should be SKIPPED.
  2. (Real asset used for env_prop test if available; otherwise uses empty scene.)

Note: No known-bad armature GLBs are in the test suite yet. Armature errors
require a rigged character asset, which the current known-bad set does not include.

Skips gracefully if assets/ is missing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

ASSETS_DIR = _PROJECT_ROOT / "assets"

import bpy  # noqa: E402

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
# bpy-backed wrappers
# ---------------------------------------------------------------------------

class BpyArmatureBone(ArmatureBone):
    def __init__(self, bone: bpy.types.Bone) -> None:
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
    def __init__(self, obj: bpy.types.Object) -> None:
        self._obj = obj

    @property
    def name(self) -> str:
        return self._obj.name

    def bones(self) -> list[BpyArmatureBone]:
        return [BpyArmatureBone(b) for b in self._obj.data.bones]


class BpySkinnedMesh(SkinnedMesh):
    def __init__(self, obj: bpy.types.Object) -> None:
        self._obj = obj

    @property
    def name(self) -> str:
        return self._obj.name

    def per_vertex_weights(self) -> list[list[float]]:
        mesh = self._obj.data
        result: list[list[float]] = []
        for vert in mesh.vertices:
            weights = [g.weight for g in vert.groups if g.weight > 0.0]
            result.append(weights)
        return result


class BpyArmatureContext(ArmatureBlenderContext):
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


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block, do_unlink=True)
    for block in list(bpy.data.materials):
        bpy.data.materials.remove(block, do_unlink=True)
    for block in list(bpy.data.images):
        bpy.data.images.remove(block, do_unlink=True)


# ---------------------------------------------------------------------------
# Test entry point
# ---------------------------------------------------------------------------

def run_tests() -> dict:
    """Run all stage1e armature tests. Returns dict with 'passed' key."""
    if not ASSETS_DIR.exists():
        return {"skipped": True, "reason": f"assets dir not found: {ASSETS_DIR}"}

    failures: list[str] = []
    tests_run = 0

    # Test: env_prop with no armature → should be SKIPPED
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    _clear_scene()
    if asset.exists():
        bpy.ops.import_scene.gltf(filepath=str(asset))

    ctx = BpyArmatureContext()
    config = ArmatureConfig(category="env_prop")
    result = check_armature(ctx, config)
    tests_run += 1

    if result.name != "armature":
        failures.append(f"env_prop: stage name '{result.name}' != 'armature'")
    if result.status != StageStatus.SKIPPED:
        failures.append(
            f"env_prop: expected SKIPPED (no armature), got {result.status.value}"
        )
    if len(result.checks) < 1:
        failures.append("env_prop: expected at least one check entry")

    json.loads(json.dumps({
        "stage": result.name,
        "status": result.status.value,
        "checks": [{"name": c.name, "status": c.status.value} for c in result.checks],
    }))

    return {"passed": len(failures) == 0, "tests_run": tests_run, "failures": failures}


def _main() -> None:
    r = run_tests()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("passed", r.get("skipped", False)) else 1)


if __name__ == "__main__":
    _main()
