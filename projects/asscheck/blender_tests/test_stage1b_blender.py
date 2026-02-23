"""Integration test for Stage 1b UV checks — runs inside Blender headless.

Usage (headless):  blender --background --python blender_tests/test_stage1b_blender.py
Usage (GUI):       Open in Blender Text Editor, press Alt+R

Tests:
  1. Smoke test: load street_lamp_01.gltf, run check_uvs, assert valid structure.
  2. Known-bad GLBs: no_uvs, uvs_out_of_bounds, uv_overlap — assert expected FAIL.

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

from pipeline.stage1.uv import (  # noqa: E402
    UVBlenderContext,
    UVConfig,
    UVMeshObject,
    check_uvs,
)


# ---------------------------------------------------------------------------
# bpy-backed wrappers
# ---------------------------------------------------------------------------

class BpyUVMeshObject(UVMeshObject):
    def __init__(self, obj: bpy.types.Object) -> None:
        self._obj = obj
        self._bm = None

    @property
    def name(self) -> str:
        return self._obj.name

    def _ensure_bm(self):
        if self._bm is None:
            self._bm = _bmesh.new()
            self._bm.from_mesh(self._obj.data)
            _bmesh.ops.triangulate(self._bm, faces=self._bm.faces[:])
        return self._bm

    def uv_layer_names(self) -> list[str]:
        return [layer.name for layer in self._obj.data.uv_layers]

    def uv_loops(self, layer_name: str) -> list[tuple[float, float]]:
        mesh = self._obj.data
        layer = mesh.uv_layers.get(layer_name)
        if layer is None:
            return []
        return [(ld.uv[0], ld.uv[1]) for ld in layer.data]

    def uv_triangles(self, layer_name: str) -> list[tuple]:
        bm = self._ensure_bm()
        uv_layer = bm.loops.layers.uv.get(layer_name)
        if uv_layer is None:
            return []
        result = []
        for face in bm.faces:
            if len(face.loops) == 3:
                coords = tuple(
                    (loop[uv_layer].uv[0], loop[uv_layer].uv[1])
                    for loop in face.loops
                )
                result.append(coords)
        return result

    def world_surface_area(self) -> float:
        bm = self._ensure_bm()
        matrix = self._obj.matrix_world
        total = 0.0
        for face in bm.faces:
            verts_world = [matrix @ v.co for v in face.verts]
            if len(verts_world) == 3:
                a, b, c = verts_world
                total += (b - a).cross(c - a).length / 2.0
        return total

    def __del__(self) -> None:
        if self._bm is not None:
            self._bm.free()
            self._bm = None


class BpyUVBlenderContext(UVBlenderContext):
    def mesh_objects(self) -> list[UVMeshObject]:
        return [
            BpyUVMeshObject(obj)
            for obj in bpy.data.objects
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


KNOWN_BAD_CASES = [
    ("no_uvs.glb",            "missing_uvs"),
    ("uvs_out_of_bounds.glb", "uv_bounds"),
    ("uv_overlap.glb",        "uv_overlap"),
]

EXPECTED_CHECK_NAMES = {
    "missing_uvs", "uv_bounds", "uv_overlap", "texel_density", "lightmap_uv2",
}


# ---------------------------------------------------------------------------
# Test entry point
# ---------------------------------------------------------------------------

def run_tests() -> dict:
    """Run all stage1b UV tests. Returns dict with 'passed' key."""
    if not ASSETS_DIR.exists():
        return {"skipped": True, "reason": f"assets dir not found: {ASSETS_DIR}"}

    failures: list[str] = []
    tests_run = 0

    # Smoke test: real asset
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    if asset.exists():
        _clear_scene()
        bpy.ops.import_scene.gltf(filepath=str(asset))
        ctx = BpyUVBlenderContext()
        result = check_uvs(ctx, UVConfig())
        tests_run += 1

        if result.name != "uv":
            failures.append(f"smoke: stage name '{result.name}' != 'uv'")
        if len(result.checks) != 5:
            failures.append(f"smoke: expected 5 checks, got {len(result.checks)}")
        missing = EXPECTED_CHECK_NAMES - {c.name for c in result.checks}
        if missing:
            failures.append(f"smoke: missing checks: {missing}")
        json.loads(json.dumps({
            "stage": result.name,
            "checks": [{"name": c.name, "status": c.status.value} for c in result.checks],
        }))

    # Known-bad GLBs
    bad_dir = ASSETS_DIR / "known-bad"
    if bad_dir.exists():
        for filename, check_name in KNOWN_BAD_CASES:
            glb = bad_dir / filename
            if not glb.exists():
                continue
            _clear_scene()
            bpy.ops.import_scene.gltf(filepath=str(glb))
            ctx = BpyUVBlenderContext()
            result = check_uvs(ctx, UVConfig())
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
