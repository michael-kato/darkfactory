"""Integration test for Stage 2 auto-remediation — runs inside Blender headless.

Usage (headless):  blender --background --python blender_tests/test_stage2_blender.py
Usage (GUI):       Open in Blender Text Editor, press Alt+R

Tests:
  1. Load street_lamp_01.gltf, run Stage 1 geometry + texture checks, then run
     remediation. Assert result is valid JSON with fixes/review_flags arrays.

Skips gracefully if assets/street_lamp_01.gltf is missing.
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

from pipeline.schema import StageResult, StageStatus  # noqa: E402
from pipeline.stage1.geometry import (  # noqa: E402
    BlenderContext as GeomContext,
    GeometryConfig,
    MeshObject,
    check_geometry,
)
from pipeline.stage1.texture import (  # noqa: E402
    ImageTextureNode,
    TextureBlenderContext,
    TextureConfig,
    TextureImage,
    TextureMaterial,
    check_textures,
)
from pipeline.stage2.remediate import (  # noqa: E402
    RemediationBlenderContext,
    RemediationConfig,
    RemediationImage,
    RemediationMeshObject,
    RemediationSkinnedMesh,
    run_remediation,
)


# ---------------------------------------------------------------------------
# bpy-backed geometry context
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


class BpyGeomContext(GeomContext):
    def mesh_objects(self) -> list[BpyMeshObject]:
        return [
            BpyMeshObject(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
        ]


# ---------------------------------------------------------------------------
# bpy-backed texture context
# ---------------------------------------------------------------------------

class BpyTextureImage(TextureImage):
    def __init__(self, img: bpy.types.Image) -> None:
        self._img = img

    @property
    def name(self) -> str:
        return self._img.name

    @property
    def size(self) -> tuple[int, int]:
        return (self._img.size[0], self._img.size[1])

    @property
    def depth(self) -> int:
        return self._img.depth

    @property
    def colorspace_name(self) -> str:
        return self._img.colorspace_settings.name


class BpyTextureMaterial(TextureMaterial):
    def __init__(self, mat: bpy.types.Material) -> None:
        self._mat = mat

    @property
    def name(self) -> str:
        return self._mat.name

    def image_texture_nodes(self) -> list[ImageTextureNode]:
        nodes = []
        if not self._mat.use_nodes or self._mat.node_tree is None:
            return nodes
        for node in self._mat.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image is not None:
                socket_name = ""
                for link in self._mat.node_tree.links:
                    if link.from_node is node:
                        socket_name = link.to_socket.name
                        break
                nodes.append(ImageTextureNode(
                    socket_name=socket_name,
                    image_name=node.image.name,
                    filepath_missing=not node.image.has_data,
                ))
        return nodes


class BpyTextureContext(TextureBlenderContext):
    def materials(self) -> list[BpyTextureMaterial]:
        return [BpyTextureMaterial(m) for m in bpy.data.materials]

    def images(self) -> list[BpyTextureImage]:
        return [BpyTextureImage(img) for img in bpy.data.images]


# ---------------------------------------------------------------------------
# bpy-backed remediation context
# ---------------------------------------------------------------------------

class BpyRemediationMeshObject(RemediationMeshObject):
    def __init__(self, obj: bpy.types.Object) -> None:
        self._obj = obj

    @property
    def name(self) -> str:
        return self._obj.name

    def vertex_count(self) -> int:
        return len(self._obj.data.vertices)

    def recalculate_normals(self) -> None:
        bpy.context.view_layer.objects.active = self._obj
        self._obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")

    def merge_by_distance(self, threshold: float) -> int:
        bpy.context.view_layer.objects.active = self._obj
        self._obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        bpy.ops.object.mode_set(mode="OBJECT")
        return len(self._obj.data.vertices)


class BpyRemediationImage(RemediationImage):
    def __init__(self, img: bpy.types.Image) -> None:
        self._img = img

    @property
    def name(self) -> str:
        return self._img.name

    @property
    def size(self) -> tuple[int, int]:
        return (self._img.size[0], self._img.size[1])

    def scale(self, new_w: int, new_h: int) -> None:
        self._img.scale(new_w, new_h)


class BpyRemediationSkinnedMesh(RemediationSkinnedMesh):
    def __init__(self, obj: bpy.types.Object) -> None:
        self._obj = obj

    @property
    def name(self) -> str:
        return self._obj.name

    def max_influences(self) -> int:
        mesh = self._obj.data
        max_inf = 0
        for vert in mesh.vertices:
            count = sum(1 for g in vert.groups if g.weight > 1e-6)
            if count > max_inf:
                max_inf = count
        return max_inf


class BpyRemediationContext(RemediationBlenderContext):
    def mesh_objects(self) -> list[BpyRemediationMeshObject]:
        return [
            BpyRemediationMeshObject(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
        ]

    def images(self) -> list[BpyRemediationImage]:
        return [BpyRemediationImage(img) for img in bpy.data.images]

    def skinned_meshes(self) -> list[BpyRemediationSkinnedMesh]:
        return [
            BpyRemediationSkinnedMesh(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "MESH" and obj.vertex_groups
        ]

    def limit_bone_weights(self, limit: int) -> None:
        bpy.ops.object.vertex_group_limit_total(
            group_select_mode="ALL", limit=limit,
        )
        bpy.ops.object.vertex_group_normalize_all()


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
    """Run stage2 remediation tests. Returns dict with 'passed' key."""
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    if not ASSETS_DIR.exists() or not asset.exists():
        return {"skipped": True, "reason": f"asset not found: {asset}"}

    failures: list[str] = []

    _clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(asset))
    assert len(BpyGeomContext().mesh_objects()) > 0, "No mesh objects after import"

    geom_result = check_geometry(BpyGeomContext(), GeometryConfig(category="env_prop"))
    tex_result = check_textures(BpyTextureContext(), TextureConfig(max_resolution_standard=2048))
    stage1_results: list[StageResult] = [geom_result, tex_result]

    result = run_remediation(BpyRemediationContext(), stage1_results, RemediationConfig())

    if result.name != "remediation":
        failures.append(f"stage name '{result.name}' != 'remediation'")
    if result.status != StageStatus.PASS:
        failures.append(f"expected PASS, got {result.status.value}")
    if not isinstance(result.fixes, list):
        failures.append("result.fixes is not a list")
    if not isinstance(result.review_flags, list):
        failures.append("result.review_flags is not a list")

    json.loads(json.dumps({
        "stage": result.name,
        "status": result.status.value,
        "fixes": [{"action": f.action, "target": f.target} for f in result.fixes],
        "review_flags": [{"issue": r.issue, "severity": r.severity.value} for r in result.review_flags],
    }))

    return {"passed": len(failures) == 0, "tests_run": 1, "failures": failures}


def _main() -> None:
    r = run_tests()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("passed", r.get("skipped", False)) else 1)


if __name__ == "__main__":
    _main()
