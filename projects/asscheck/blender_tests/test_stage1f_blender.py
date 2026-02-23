"""Integration test for Stage 1f scene & hierarchy checks — runs inside Blender headless.

Usage (headless):  blender --background --python blender_tests/test_stage1f_blender.py
Usage (GUI):       Open in Blender Text Editor, press Alt+R

Tests:
  1. Smoke test: load street_lamp_01.gltf (or empty scene), run check_scene,
     assert valid result structure and non-negative PerformanceEstimates.

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
from pipeline.stage1.scene import (  # noqa: E402
    SceneArmatureObject,
    SceneBlenderContext,
    SceneConfig,
    SceneImage,
    SceneMeshObject,
    check_scene,
)


# ---------------------------------------------------------------------------
# bpy-backed wrappers
# ---------------------------------------------------------------------------

class BpyMeshObject(SceneMeshObject):
    def __init__(self, obj: bpy.types.Object) -> None:
        self._obj = obj

    @property
    def name(self) -> str:
        return self._obj.name

    def triangle_count(self) -> int:
        mesh = self._obj.data
        return sum(len(p.vertices) - 2 for p in mesh.polygons if len(p.vertices) >= 3)

    def material_slot_count(self) -> int:
        return max(1, len(self._obj.material_slots))


class BpyArmatureObject(SceneArmatureObject):
    def __init__(self, obj: bpy.types.Object) -> None:
        self._obj = obj

    @property
    def name(self) -> str:
        return self._obj.name

    def bone_count(self) -> int:
        return len(self._obj.data.bones)


class BpySceneImage(SceneImage):
    def __init__(self, image: bpy.types.Image) -> None:
        self._image = image

    @property
    def width(self) -> int:
        return self._image.size[0]

    @property
    def height(self) -> int:
        return self._image.size[1]

    @property
    def channels(self) -> int:
        return self._image.channels

    @property
    def bit_depth(self) -> int:
        if self._image.channels > 0:
            return self._image.depth // self._image.channels
        return 8


class BpySceneContext(SceneBlenderContext):
    def mesh_objects(self) -> list[BpyMeshObject]:
        return [
            BpyMeshObject(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
        ]

    def armature_objects(self) -> list[BpyArmatureObject]:
        return [
            BpyArmatureObject(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "ARMATURE"
        ]

    def unique_images(self) -> list[BpySceneImage]:
        return [
            BpySceneImage(img)
            for img in bpy.data.images
            if img.users > 0 and img.size[0] > 0 and img.size[1] > 0
        ]

    def orphan_counts(self) -> dict[str, int]:
        return {
            "meshes": sum(1 for m in bpy.data.meshes if m.users == 0),
            "materials": sum(1 for m in bpy.data.materials if m.users == 0),
            "images": sum(1 for i in bpy.data.images if i.users == 0),
        }


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
    """Run all stage1f scene tests. Returns dict with 'passed' key."""
    if not ASSETS_DIR.exists():
        return {"skipped": True, "reason": f"assets dir not found: {ASSETS_DIR}"}

    failures: list[str] = []
    tests_run = 0

    # Smoke test: real asset (or empty scene as fallback)
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    _clear_scene()
    if asset.exists():
        bpy.ops.import_scene.gltf(filepath=str(asset))

    config = SceneConfig(
        object_naming_pattern=r"^[A-Za-z0-9_]+",
        require_lod=False,
        require_collision=False,
        lod_suffix_pattern=r"_LOD\d+$",
        collision_suffix_pattern=r"_Collision$",
    )
    ctx = BpySceneContext()
    stage_result, perf = check_scene(ctx, config)
    tests_run += 1

    if stage_result.name != "scene":
        failures.append(f"smoke: stage name '{stage_result.name}' != 'scene'")
    if stage_result.status not in (StageStatus.PASS, StageStatus.FAIL):
        failures.append(f"smoke: unexpected status {stage_result.status.value}")
    if perf.triangle_count < 0:
        failures.append(f"smoke: triangle_count < 0: {perf.triangle_count}")
    if perf.draw_call_estimate < 0:
        failures.append(f"smoke: draw_call_estimate < 0: {perf.draw_call_estimate}")
    if perf.vram_estimate_mb < 0.0:
        failures.append(f"smoke: vram_estimate_mb < 0: {perf.vram_estimate_mb}")
    if perf.bone_count < 0:
        failures.append(f"smoke: bone_count < 0: {perf.bone_count}")

    json.loads(json.dumps({
        "stage": {
            "name": stage_result.name,
            "status": stage_result.status.value,
            "checks": [{"name": c.name, "status": c.status.value} for c in stage_result.checks],
        },
        "performance": {
            "triangle_count": perf.triangle_count,
            "draw_call_estimate": perf.draw_call_estimate,
            "vram_estimate_mb": perf.vram_estimate_mb,
            "bone_count": perf.bone_count,
        },
    }))

    return {"passed": len(failures) == 0, "tests_run": tests_run, "failures": failures}


def _main() -> None:
    r = run_tests()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("passed", r.get("skipped", False)) else 1)


if __name__ == "__main__":
    _main()
