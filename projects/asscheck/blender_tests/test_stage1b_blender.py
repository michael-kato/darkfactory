"""Blender integration test for Stage 1b UV checks.

Run with:
    blender --background --python blender_tests/test_stage1b_blender.py

Loads the sample glTF asset, runs UV checks, and asserts the result is valid
JSON with the expected structure and no crashes.
"""
from __future__ import annotations

import json
import os
import sys

try:
    import bpy
    import bmesh as _bmesh
except ImportError:
    print("ERROR: bpy not available — run this script via Blender headless")
    sys.exit(1)

# Add the project root to sys.path so pipeline imports work.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from pipeline.stage1.uv import (  # noqa: E402
    UVBlenderContext,
    UVConfig,
    UVMeshObject,
    check_uvs,
)


# ---------------------------------------------------------------------------
# Real bpy wrappers
# ---------------------------------------------------------------------------

class BpyUVMeshObject(UVMeshObject):
    """Wraps a bpy mesh object for UV analysis."""

    def __init__(self, obj: "bpy.types.Object") -> None:
        self._obj = obj
        self._bm: "_bmesh.types.BMesh | None" = None

    @property
    def name(self) -> str:
        return self._obj.name

    def _ensure_bm(self) -> "_bmesh.types.BMesh":
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

    def uv_triangles(
        self, layer_name: str
    ) -> list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]]:
        bm = self._ensure_bm()
        uv_layer = bm.loops.layers.uv.get(layer_name)
        if uv_layer is None:
            return []
        result = []
        for face in bm.faces:
            if len(face.loops) == 3:
                coords: tuple = tuple(
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

    ctx = BpyUVBlenderContext()
    config = UVConfig()
    result = check_uvs(ctx, config)

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

    assert data["name"] == "uv", f"Expected stage name 'uv', got '{data['name']}'"
    assert len(data["checks"]) == 5, f"Expected 5 checks, got {len(data['checks'])}"

    check_names = {c["name"] for c in data["checks"]}
    expected_names = {
        "missing_uvs",
        "uv_bounds",
        "uv_overlap",
        "texel_density",
        "lightmap_uv2",
    }
    assert check_names == expected_names, (
        f"Unexpected check names: {check_names - expected_names}"
    )

    print(json_str)
    print("PASS: Stage 1b UV checks integration test passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
