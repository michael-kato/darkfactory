"""Blender integration test for Stage 1f — Scene & Hierarchy Checks.

Run with:
    blender --background --python blender_tests/test_stage1f_blender.py

Loads the sample glTF asset (street_lamp_01_quant.gltf), runs the scene
checks, and verifies that all PerformanceEstimates fields are non-negative
numbers.
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
from pipeline.stage1.scene import (  # noqa: E402
    SceneArmatureObject,
    SceneBlenderContext,
    SceneConfig,
    SceneImage,
    SceneMeshObject,
    check_scene,
)


# ---------------------------------------------------------------------------
# Real bpy wrappers
# ---------------------------------------------------------------------------

class BpyMeshObject(SceneMeshObject):
    """Wraps a bpy.types.Object of type MESH."""

    def __init__(self, obj: "bpy.types.Object") -> None:
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
    """Wraps a bpy.types.Object of type ARMATURE."""

    def __init__(self, obj: "bpy.types.Object") -> None:
        self._obj = obj

    @property
    def name(self) -> str:
        return self._obj.name

    def bone_count(self) -> int:
        return len(self._obj.data.bones)


class BpySceneImage(SceneImage):
    """Wraps a bpy.types.Image."""

    def __init__(self, image: "bpy.types.Image") -> None:
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
        # bpy.types.Image.depth reports total bits per pixel; divide by channels.
        if self._image.channels > 0:
            return self._image.depth // self._image.channels
        return 8


class BpySceneContext(SceneBlenderContext):
    """Reads scene, armature, image, and orphan data from the active Blender scene."""

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

    config = SceneConfig(
        object_naming_pattern=r"^[A-Za-z0-9_]+",
        require_lod=False,
        require_collision=False,
        lod_suffix_pattern=r"_LOD\d+$",
        collision_suffix_pattern=r"_Collision$",
    )

    ctx = BpySceneContext()
    stage_result, perf = check_scene(ctx, config)

    # Verify performance estimates are non-negative numbers.
    assert perf.triangle_count >= 0, (
        f"Expected triangle_count >= 0, got {perf.triangle_count}"
    )
    assert perf.draw_call_estimate >= 0, (
        f"Expected draw_call_estimate >= 0, got {perf.draw_call_estimate}"
    )
    assert perf.vram_estimate_mb >= 0.0, (
        f"Expected vram_estimate_mb >= 0.0, got {perf.vram_estimate_mb}"
    )
    assert perf.bone_count >= 0, (
        f"Expected bone_count >= 0, got {perf.bone_count}"
    )

    # Serialise to JSON and verify round-trip.
    output = {
        "stage": {
            "name": stage_result.name,
            "status": stage_result.status.value,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "measured_value": c.measured_value,
                    "threshold": c.threshold,
                    "message": c.message,
                }
                for c in stage_result.checks
            ],
        },
        "performance": {
            "triangle_count": perf.triangle_count,
            "draw_call_estimate": perf.draw_call_estimate,
            "vram_estimate_mb": perf.vram_estimate_mb,
            "bone_count": perf.bone_count,
        },
    }

    json_str = json.dumps(output, indent=2)
    json.loads(json_str)  # Verify it round-trips without error.

    assert output["stage"]["name"] == "scene", (
        f"Expected stage name 'scene', got '{output['stage']['name']}'"
    )
    assert output["stage"]["status"] in (
        StageStatus.PASS.value,
        StageStatus.FAIL.value,
    ), f"Unexpected stage status: {output['stage']['status']}"

    print(json_str)
    print("PASS: Stage 1f scene integration test passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
