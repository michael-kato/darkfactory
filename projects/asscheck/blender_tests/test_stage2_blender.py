"""Integration test for Stage 2 auto-remediation — runs inside Blender headless.

Usage:
    blender --background --python blender_tests/test_stage2_blender.py

The script:
  1. Skips gracefully (exit 0, JSON {"skipped": true}) if the sample asset
     does not exist.
  2. Loads the sample glTF, runs Stage 1 checks via real bpy wrappers.
  3. Runs remediation on the Stage 1 results.
  4. Verifies the result is a valid StageResult and serialises it as JSON.
  5. Exits 0 on success.
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

from pipeline.schema import CheckStatus, StageResult, StageStatus  # noqa: E402
from pipeline.stage1.geometry import (  # noqa: E402
    BlenderContext as GeomContext,
    GeometryConfig,
    MeshObject,
    check_geometry,
)
from pipeline.stage1.texture import (  # noqa: E402
    TextureBlenderContext,
    TextureConfig,
    TextureImage,
    TextureMaterial,
    ImageTextureNode,
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
# Concrete bpy-backed geometry context (for Stage 1 checks)
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
# Concrete bpy-backed texture context (for Stage 1 checks)
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
# Concrete bpy-backed remediation context (for Stage 2)
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
            group_select_mode="ALL",
            limit=limit,
        )
        bpy.ops.object.vertex_group_normalize_all()


# ---------------------------------------------------------------------------
# Test body
# ---------------------------------------------------------------------------

def run() -> None:
    # Clear default scene
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    # Import the sample glTF asset
    bpy.ops.import_scene.gltf(filepath=str(ASSET_PATH))

    # Run Stage 1 checks to obtain stage1_results
    geom_ctx = BpyGeomContext()
    assert len(geom_ctx.mesh_objects()) > 0, "No mesh objects found after import"

    geom_result = check_geometry(geom_ctx, GeometryConfig(category="env_prop"))
    tex_result = check_textures(
        BpyTextureContext(),
        TextureConfig(max_resolution_standard=2048),
    )
    stage1_results: list[StageResult] = [geom_result, tex_result]

    # Run remediation
    rem_ctx = BpyRemediationContext()
    config = RemediationConfig()
    result = run_remediation(rem_ctx, stage1_results, config)

    # Validate result shape
    assert result.name == "remediation", f"Unexpected name: {result.name!r}"
    assert result.status == StageStatus.PASS, f"Expected PASS, got {result.status}"
    assert isinstance(result.fixes, list)
    assert isinstance(result.review_flags, list)

    # Verify JSON serialisability
    output = {
        "stage": result.name,
        "status": result.status.value,
        "fixes": [
            {
                "action": f.action,
                "target": f.target,
                "before_value": f.before_value,
                "after_value": f.after_value,
            }
            for f in result.fixes
        ],
        "review_flags": [
            {
                "issue": r.issue,
                "severity": r.severity.value,
                "description": r.description,
            }
            for r in result.review_flags
        ],
    }
    json_str = json.dumps(output)
    # Round-trip sanity check
    parsed = json.loads(json_str)
    assert parsed["stage"] == "remediation"

    print(json_str)


if __name__ == "__main__":
    run()
