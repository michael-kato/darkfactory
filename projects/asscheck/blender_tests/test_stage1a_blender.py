"""Integration test for Stage 1a geometry checks — runs inside Blender headless.

Usage (headless):  blender --background --python blender_tests/test_stage1a_blender.py
Usage (GUI):       Open in Blender Text Editor, press Alt+R

Tests:
  1. Smoke test: load street_lamp_01.gltf, run check_geometry, assert valid structure.
  2. Known-bad GLBs: one per check type, assert the expected check returns FAIL.

Both tests skip gracefully if assets/ is missing.
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
import bmesh as _bmesh  # noqa: E402

from pipeline.stage1.geometry import (  # noqa: E402
    BlenderContext,
    GeometryConfig,
    MeshObject,
    check_geometry,
)


# ---------------------------------------------------------------------------
# bpy-backed wrappers
# ---------------------------------------------------------------------------

class BpyMeshObject(MeshObject):
    def __init__(self, obj: bpy.types.Object) -> None:
        self._obj = obj

    @property
    def name(self) -> str:
        return self._obj.name

    def triangle_count(self) -> int:
        return sum(len(p.vertices) - 2 for p in self._obj.data.polygons)

    def bmesh_get(self):
        bm = _bmesh.new()
        bm.from_mesh(self._obj.data)
        return bm


class BpyBlenderContext(BlenderContext):
    def mesh_objects(self) -> list[BpyMeshObject]:
        return [
            BpyMeshObject(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
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


# (filename in assets/known-bad/, check name expected to FAIL)
KNOWN_BAD_CASES = [
    ("non_manifold.glb",     "non_manifold"),
    ("degenerate_faces.glb", "degenerate_faces"),
    ("flipped_normals.glb",  "normal_consistency"),
    ("loose_geometry.glb",   "loose_geometry"),
    ("overbudget_tris.glb",  "polycount_budget"),
    ("underbudget_tris.glb", "polycount_budget"),
]


# ---------------------------------------------------------------------------
# Test entry point
# ---------------------------------------------------------------------------

def run_tests() -> dict:
    """Run all stage1a geometry tests. Returns dict with 'passed' key."""
    if not ASSETS_DIR.exists():
        return {"skipped": True, "reason": f"assets dir not found: {ASSETS_DIR}"}

    failures: list[str] = []
    tests_run = 0

    # Smoke test: real asset — no crash, valid result structure
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    if asset.exists():
        _clear_scene()
        bpy.ops.import_scene.gltf(filepath=str(asset))
        ctx = BpyBlenderContext()
        assert len(ctx.mesh_objects()) > 0, "No mesh objects after import"
        result = check_geometry(ctx, GeometryConfig(category="env_prop"))
        tests_run += 1

        if result.name != "geometry":
            failures.append(f"smoke: stage name '{result.name}' != 'geometry'")
        if len(result.checks) != 6:
            failures.append(f"smoke: expected 6 checks, got {len(result.checks)}")
        json.loads(json.dumps({
            "stage": result.name,
            "status": result.status.value,
            "checks": [{"name": c.name, "status": c.status.value} for c in result.checks],
        }))

    # Known-bad: each GLB should trigger exactly the stated check failure
    bad_dir = ASSETS_DIR / "known-bad"
    if bad_dir.exists():
        for filename, check_name in KNOWN_BAD_CASES:
            glb = bad_dir / filename
            if not glb.exists():
                continue
            _clear_scene()
            bpy.ops.import_scene.gltf(filepath=str(glb))
            ctx = BpyBlenderContext()
            result = check_geometry(ctx, GeometryConfig(category="env_prop"))
            tests_run += 1

            check = next((c for c in result.checks if c.name == check_name), None)
            if check is None:
                failures.append(f"{filename}: check '{check_name}' not found")
            elif check.status.value != "FAIL":
                failures.append(
                    f"{filename}: expected '{check_name}' FAIL, got {check.status.value}"
                )

    return {"passed": len(failures) == 0, "tests_run": tests_run, "failures": failures}


def _main() -> None:
    r = run_tests()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("passed", r.get("skipped", False)) else 1)


if __name__ == "__main__":
    _main()
