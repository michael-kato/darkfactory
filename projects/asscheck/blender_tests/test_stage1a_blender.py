"""Integration test for Stage 1a geometry checks — runs inside Blender headless.

Usage:
    blender --background --python blender_tests/test_stage1a_blender.py

The script:
  1. Skips gracefully (exit 0, JSON {"skipped": true}) if the assets dir
     does not contain street_lamp_01.gltf.
  2. Imports the asset, runs check_geometry via real bpy / bmesh wrappers.
  3. Prints the StageResult as a single JSON line and exits 0 on success.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Make the pipeline package importable from within Blender's Python
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

ASSETS_DIR = _PROJECT_ROOT / "assets"
ASSET_PATH = ASSETS_DIR / "street_lamp_01.gltf"

if not ASSET_PATH.exists():
    print(json.dumps({"skipped": True, "reason": f"asset not found: {ASSET_PATH}"}))
    sys.exit(0)

# ---------------------------------------------------------------------------
# Blender / bmesh imports (only available inside Blender)
# ---------------------------------------------------------------------------
import bpy  # noqa: E402
import bmesh as _bmesh  # noqa: E402

from pipeline.stage1.geometry import (  # noqa: E402
    BlenderContext,
    GeometryConfig,
    MeshObject,
    check_geometry,
)


# ---------------------------------------------------------------------------
# Concrete bpy-backed implementations
# ---------------------------------------------------------------------------

class BpyMeshObject(MeshObject):
    """Wraps a single bpy mesh object."""

    def __init__(self, obj: bpy.types.Object) -> None:
        self._obj = obj

    @property
    def name(self) -> str:
        return self._obj.name

    def triangle_count(self) -> int:
        # Count triangles without modifying the stored mesh.
        return sum(len(p.vertices) - 2 for p in self._obj.data.polygons)

    def bmesh_get(self):
        bm = _bmesh.new()
        bm.from_mesh(self._obj.data)
        return bm


class BpyBlenderContext(BlenderContext):
    """Wraps the active Blender scene."""

    def mesh_objects(self) -> list[BpyMeshObject]:
        return [
            BpyMeshObject(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
        ]


# ---------------------------------------------------------------------------
# Test body
# ---------------------------------------------------------------------------

def run() -> None:
    # Clear default scene objects
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    # Import the glTF asset
    bpy.ops.import_scene.gltf(filepath=str(ASSET_PATH))

    ctx = BpyBlenderContext()
    objects = ctx.mesh_objects()
    assert len(objects) > 0, "No mesh objects found after import"

    config = GeometryConfig(category="env_prop")
    result = check_geometry(ctx, config)

    assert result.name == "geometry", f"Unexpected stage name: {result.name}"
    assert len(result.checks) == 6, f"Expected 6 checks, got {len(result.checks)}"

    # Serialise to confirm valid JSON round-trip
    output = {
        "stage": result.name,
        "status": result.status.value,
        "checks": [
            {
                "name": c.name,
                "status": c.status.value,
                "measured_value": c.measured_value,
                "threshold": c.threshold,
            }
            for c in result.checks
        ],
    }
    print(json.dumps(output))


if __name__ == "__main__":
    run()
