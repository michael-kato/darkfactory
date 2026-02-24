"""All asscheck integration tests — runs inside Blender headless.

Usage (headless):  blender --background --python blender_tests/tests.py
Usage (GUI):       Open in Blender Text Editor, press Alt+R

Covers:
  - Stage 1a: geometry checks (polycount, non_manifold, degenerate, normals, loose)
  - Stage 1b: UV checks (missing, bounds, overlap, texel density)
  - Stage 1c: texture checks (resolution, depth, colorspace)
  - Stage 1d: PBR checks (workflow, albedo/metalness/roughness ranges, normal maps)
  - Stage 1e: armature checks (skipped for env_prop)
  - Stage 1f: scene checks (naming, hierarchy, performance estimates)
  - Stage 2:  autofix (fixes + review flags)
  - Stage 5:  turntable renderer

Exit code: 0 if all tests passed or skipped, 1 if any failed.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

ASSETS_DIR = _PROJECT_ROOT / "assets"

import bpy          # noqa: E402
import bmesh as _bmesh  # noqa: E402

from pipeline.schema import StageResult, Status  # noqa: E402

from pipeline.geometry import (  # noqa: E402
    GeometryConfig,
    check_geometry,
)
from pipeline.uv import (  # noqa: E402
    UVConfig,
    check_uvs,
)
from pipeline.texture import (  # noqa: E402
    ImageTextureNode,
    TextureConfig,
    check_textures,
)
from pipeline.pbr import (  # noqa: E402
    NormalMapData,
    PBRConfig,
    check_pbr,
)
from pipeline.armature import (  # noqa: E402
    ArmatureConfig,
    check_armature,
)
from pipeline.scene import (  # noqa: E402
    SceneConfig,
    check_scene,
)
from pipeline.autofix import (  # noqa: E402
    AutofixConfig,
    run_autofix,
)
from pipeline.turntable import TurntableConfig, render_turntable  # noqa: E402


# ---------------------------------------------------------------------------
# Shared utility
# ---------------------------------------------------------------------------

def _clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block, do_unlink=True)
    for block in list(bpy.data.materials):
        bpy.data.materials.remove(block, do_unlink=True)
    for block in list(bpy.data.images):
        bpy.data.images.remove(block, do_unlink=True)


# ===========================================================================
# Stage 1a — Geometry
# ===========================================================================

class BpyGeomMeshObject:
    def __init__(self, obj):
        self._obj = obj

    @property
    def name(self):
        return self._obj.name

    def triangle_count(self):
        return sum(len(p.vertices) - 2 for p in self._obj.data.polygons)

    def bmesh_get(self):
        bm = _bmesh.new()
        bm.from_mesh(self._obj.data)
        return bm


class BpyGeomContext:
    def mesh_objects(self) -> list[BpyGeomMeshObject]:
        return [
            BpyGeomMeshObject(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
        ]


_GEOM_EXPECTED_CHECKS = {
    "polycount_budget", "non_manifold", "degenerate_faces",
    "normal_consistency", "loose_geometry", "interior_faces",
}

_GEOM_KNOWN_BAD = [
    ("non_manifold.glb",     "non_manifold"),
    ("degenerate_faces.glb", "degenerate_faces"),
    ("flipped_normals.glb",  "normal_consistency"),
    ("loose_geometry.glb",   "loose_geometry"),
    ("overbudget_tris.glb",  "polycount_budget"),
    ("underbudget_tris.glb", "polycount_budget"),
]


def run_geometry_tests():
    """Run stage 1a geometry tests. Returns dict with 'passed' key."""
    if not ASSETS_DIR.exists():
        return {"skipped": True, "reason": f"assets dir not found: {ASSETS_DIR}"}

    failures = []
    tests_run = 0

    # Smoke test: real asset
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    if asset.exists():
        _clear_scene()
        bpy.ops.import_scene.gltf(filepath=str(asset))
        ctx = BpyGeomContext()
        assert len(ctx.mesh_objects()) > 0, "No mesh objects after import"
        result = check_geometry(ctx, GeometryConfig(category="env_prop"))
        tests_run += 1

        if result.name != "geometry":
            failures.append(f"smoke: stage name '{result.name}' != 'geometry'")
        if len(result.checks) != 6:
            failures.append(f"smoke: expected 6 checks, got {len(result.checks)}")
        missing = _GEOM_EXPECTED_CHECKS - {c.name for c in result.checks}
        if missing:
            failures.append(f"smoke: missing checks: {missing}")
        json.loads(json.dumps({
            "stage": result.name,
            "status": result.status.value,
            "checks": [{"name": c.name, "status": c.status.value} for c in result.checks],
        }))

    # Known-bad GLBs
    bad_dir = ASSETS_DIR / "known-bad"
    if bad_dir.exists():
        for filename, check_name in _GEOM_KNOWN_BAD:
            glb = bad_dir / filename
            if not glb.exists():
                continue
            _clear_scene()
            bpy.ops.import_scene.gltf(filepath=str(glb))
            ctx = BpyGeomContext()
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


# ===========================================================================
# Stage 1b — UV
# ===========================================================================

class BpyUVMeshObject:
    def __init__(self, obj):
        self._obj = obj
        self._bm = None

    @property
    def name(self):
        return self._obj.name

    def _ensure_bm(self):
        if self._bm is None:
            self._bm = _bmesh.new()
            self._bm.from_mesh(self._obj.data)
            _bmesh.ops.triangulate(self._bm, faces=self._bm.faces[:])
        return self._bm

    def uv_layer_names(self):
        return [layer.name for layer in self._obj.data.uv_layers]

    def uv_loops(self, layer_name):
        mesh = self._obj.data
        layer = mesh.uv_layers.get(layer_name)
        if layer is None:
            return []
        return [(ld.uv[0], ld.uv[1]) for ld in layer.data]

    def uv_triangles(self, layer_name):
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

    def world_surface_area(self):
        bm = self._ensure_bm()
        matrix = self._obj.matrix_world
        total = 0.0
        for face in bm.faces:
            verts_world = [matrix @ v.co for v in face.verts]
            if len(verts_world) == 3:
                a, b, c = verts_world
                total += (b - a).cross(c - a).length / 2.0
        return total

    def __del__(self):
        if self._bm is not None:
            self._bm.free()
            self._bm = None


class BpyUVContext:
    def mesh_objects(self):
        return [
            BpyUVMeshObject(obj)
            for obj in bpy.data.objects
            if obj.type == "MESH"
        ]


_UV_EXPECTED_CHECKS = {
    "missing_uvs", "uv_bounds", "uv_overlap", "texel_density", "lightmap_uv2",
}

_UV_KNOWN_BAD = [
    ("no_uvs.glb",            "missing_uvs"),
    ("uvs_out_of_bounds.glb", "uv_bounds"),
    ("uv_overlap.glb",        "uv_overlap"),
]


def run_uv_tests():
    """Run stage 1b UV tests. Returns dict with 'passed' key."""
    if not ASSETS_DIR.exists():
        return {"skipped": True, "reason": f"assets dir not found: {ASSETS_DIR}"}

    failures = []
    tests_run = 0

    # Smoke test: real asset
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    if asset.exists():
        _clear_scene()
        bpy.ops.import_scene.gltf(filepath=str(asset))
        ctx = BpyUVContext()
        result = check_uvs(ctx, UVConfig())
        tests_run += 1

        if result.name != "uv":
            failures.append(f"smoke: stage name '{result.name}' != 'uv'")
        if len(result.checks) != 5:
            failures.append(f"smoke: expected 5 checks, got {len(result.checks)}")
        missing = _UV_EXPECTED_CHECKS - {c.name for c in result.checks}
        if missing:
            failures.append(f"smoke: missing checks: {missing}")
        json.loads(json.dumps({
            "stage": result.name,
            "checks": [{"name": c.name, "status": c.status.value} for c in result.checks],
        }))

    # Known-bad GLBs
    bad_dir = ASSETS_DIR / "known-bad"
    if bad_dir.exists():
        for filename, check_name in _UV_KNOWN_BAD:
            glb = bad_dir / filename
            if not glb.exists():
                continue
            _clear_scene()
            bpy.ops.import_scene.gltf(filepath=str(glb))
            ctx = BpyUVContext()
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


# ===========================================================================
# Stage 1c — Texture
# ===========================================================================

def _tex_get_socket_name(node):
    try:
        links = node.outputs["Color"].links
        if links:
            return links[0].to_socket.name
    except (KeyError, AttributeError):
        pass
    return node.image.name if node.image else ""


def _tex_filepath_is_missing(image):
    import os
    if not image.filepath:
        return False
    if image.packed_file:
        return False
    abs_path = bpy.path.abspath(image.filepath)
    return not os.path.exists(abs_path)


class BpyTexMaterial:
    def __init__(self, mat):
        self._mat = mat

    @property
    def name(self):
        return self._mat.name

    def image_texture_nodes(self) -> list[ImageTextureNode]:
        if not self._mat.use_nodes or self._mat.node_tree is None:
            return []
        nodes: list[ImageTextureNode] = []
        for node in self._mat.node_tree.nodes:
            if node.type != "TEX_IMAGE":
                continue
            if node.image is None:
                continue
            nodes.append(ImageTextureNode(
                socket_name=_tex_get_socket_name(node),
                image_name=node.image.name,
                filepath_missing=_tex_filepath_is_missing(node.image),
            ))
        return nodes


class BpyTexImage:
    def __init__(self, image):
        self._image = image

    @property
    def name(self):
        return self._image.name

    @property
    def size(self):
        return (self._image.size[0], self._image.size[1])

    @property
    def depth(self):
        return self._image.depth

    @property
    def colorspace_name(self):
        return self._image.colorspace_settings.name


class BpyTexContext:
    def materials(self) -> list[TextureMaterial]:
        return [
            BpyTexMaterial(mat)
            for mat in bpy.data.materials
            if mat.use_nodes
        ]

    def images(self) -> list[TextureImage]:
        return [BpyTexImage(img) for img in bpy.data.images]


def _create_wrong_colorspace_scene():
    """Create a minimal scene: one mesh with a normal map image set to sRGB (wrong)."""
    _clear_scene()
    mesh = bpy.data.meshes.new("test_mesh")
    obj = bpy.data.objects.new("test_obj", mesh)
    bpy.context.scene.collection.objects.link(obj)
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0.5, 1, 0)], [], [(0, 1, 2)])
    mesh.update()

    img = bpy.data.images.new("normal_wrong", width=4, height=4)
    img.colorspace_settings.name = "sRGB"  # wrong: normal maps must be Non-Color

    mat = bpy.data.materials.new("mat_wrong_colorspace")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = img
    nmap = nodes.new("ShaderNodeNormalMap")
    links.new(tex.outputs["Color"], nmap.inputs["Color"])
    links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    obj.data.materials.append(mat)


_TEX_EXPECTED_CHECKS = {
    "missing_textures", "resolution_limit", "power_of_two",
    "texture_count", "channel_depth", "color_space",
}


def run_texture_tests():
    """Run stage 1c texture tests. Returns dict with 'passed' key."""
    if not ASSETS_DIR.exists():
        return {"skipped": True, "reason": f"assets dir not found: {ASSETS_DIR}"}

    failures = []
    tests_run = 0

    # Smoke test: real asset
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    if asset.exists():
        _clear_scene()
        bpy.ops.import_scene.gltf(filepath=str(asset))
        ctx = BpyTexContext()
        result = check_textures(ctx, TextureConfig())
        tests_run += 1

        if result.name != "texture":
            failures.append(f"smoke: stage name '{result.name}' != 'texture'")
        if len(result.checks) != 6:
            failures.append(f"smoke: expected 6 checks, got {len(result.checks)}")
        missing = _TEX_EXPECTED_CHECKS - {c.name for c in result.checks}
        if missing:
            failures.append(f"smoke: missing checks: {missing}")
        json.loads(json.dumps({
            "stage": result.name,
            "checks": [{"name": c.name, "status": c.status.value} for c in result.checks],
        }))

    # Known-bad: programmatic wrong colorspace
    _create_wrong_colorspace_scene()
    ctx = BpyTexContext()
    result = check_textures(ctx, TextureConfig())
    tests_run += 1

    check = next((c for c in result.checks if c.name == "color_space"), None)
    if check is None:
        failures.append("wrong_colorspace: check 'color_space' not found")
    elif check.status.value != "FAIL":
        failures.append(
            f"wrong_colorspace: expected 'color_space' FAIL, got {check.status.value}"
        )

    return {"passed": len(failures) == 0, "tests_run": tests_run, "failures": failures}


# ===========================================================================
# Stage 1d — PBR
# ===========================================================================

def _linear_to_srgb(v):
    v = max(0.0, min(1.0, v))
    if v <= 0.0031308:
        return v * 12.92
    return 1.055 * (v ** (1.0 / 2.4)) - 0.055


def _get_image_pixels_srgb(image):
    try:
        if not image.has_data:
            return None
        linear = list(image.pixels)
        out = []
        for i in range(0, len(linear), 4):
            out.append(_linear_to_srgb(linear[i]))
            out.append(_linear_to_srgb(linear[i + 1]))
            out.append(_linear_to_srgb(linear[i + 2]))
            out.append(linear[i + 3])
        return out
    except Exception:
        return None


def _get_image_pixels_linear(image):
    try:
        if not image.has_data:
            return None
        return list(image.pixels)
    except Exception:
        return None


def _get_tex_image_for_socket(node_tree, socket_name):
    pbsdf = next(
        (n for n in node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None
    )
    if pbsdf is None:
        return None
    socket = pbsdf.inputs.get(socket_name)
    if socket is None or not socket.links:
        return None
    from_node = socket.links[0].from_node
    if from_node.type == "TEX_IMAGE":
        return from_node.image
    return None


def _has_output_link(node, node_tree):
    return any(link.from_node == node for link in node_tree.links)


def _detect_cycles(node_tree):
    successors = {n.name: [] for n in node_tree.nodes}
    for link in node_tree.links:
        successors[link.from_node.name].append(link.to_node.name)

    visited = set()
    rec_stack = set()

    def dfs(name):
        visited.add(name)
        rec_stack.add(name)
        for neighbor in successors.get(name, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True
        rec_stack.discard(name)
        return False

    for node in node_tree.nodes:
        if node.name not in visited:
            if dfs(node.name):
                return True
    return False


class BpyPBRMesh:
    def __init__(self, obj):
        self._obj = obj

    @property
    def name(self):
        return self._obj.name

    @property
    def material_slot_count(self):
        return len(self._obj.material_slots)


class BpyPBRMaterial:
    def __init__(self, mat):
        self._mat = mat

    @property
    def name(self):
        return self._mat.name

    def has_nodes(self):
        return (
            self._mat.use_nodes
            and self._mat.node_tree is not None
            and len(self._mat.node_tree.nodes) > 0
        )

    def uses_principled_bsdf(self):
        if not self.has_nodes():
            return False
        tree = self._mat.node_tree
        output_nodes = [n for n in tree.nodes if n.type == "OUTPUT_MATERIAL"]
        for output in output_nodes:
            surface_input = output.inputs.get("Surface")
            if surface_input and surface_input.links:
                from_node = surface_input.links[0].from_node
                if from_node.type == "BSDF_PRINCIPLED":
                    return True
        return False

    def uses_spec_gloss(self):
        if not self.has_nodes():
            return False
        tree = self._mat.node_tree
        for node in tree.nodes:
            if node.type in ("BSDF_GLOSSY", "BSDF_SPECULAR"):
                return True
            for socket in node.inputs:
                if "gloss" in socket.name.lower():
                    return True
        return False

    def orphan_image_node_count(self):
        if not self.has_nodes():
            return 0
        tree = self._mat.node_tree
        return sum(
            1 for node in tree.nodes
            if node.type == "TEX_IMAGE" and not _has_output_link(node, tree)
        )

    def has_node_cycles(self):
        if not self.has_nodes():
            return False
        return _detect_cycles(self._mat.node_tree)

    def albedo_pixels(self):
        if not self.has_nodes():
            return None
        image = _get_tex_image_for_socket(self._mat.node_tree, "Base Color")
        if image is None:
            return None
        return _get_image_pixels_srgb(image)

    def metalness_pixels(self):
        if not self.has_nodes():
            return None
        image = _get_tex_image_for_socket(self._mat.node_tree, "Metallic")
        if image is None:
            return None
        return _get_image_pixels_linear(image)

    def roughness_pixels(self):
        if not self.has_nodes():
            return None
        image = _get_tex_image_for_socket(self._mat.node_tree, "Roughness")
        if image is None:
            return None
        return _get_image_pixels_linear(image)

    def normal_map_data(self) -> list[NormalMapData]:
        if not self.has_nodes():
            return []
        tree = self._mat.node_tree
        data: list[NormalMapData] = []
        for node in tree.nodes:
            if node.type != "NORMAL_MAP":
                continue
            color_input = node.inputs.get("Color")
            if color_input is None or not color_input.links:
                continue
            img_node = color_input.links[0].from_node
            if img_node.type != "TEX_IMAGE" or img_node.image is None:
                continue
            image = img_node.image
            data.append(NormalMapData(
                image_name=image.name,
                colorspace=image.colorspace_settings.name,
                pixels=_get_image_pixels_linear(image),
            ))
        return data


class BpyPBRContext:
    def mesh_objects(self):
        return [
            BpyPBRMesh(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
        ]

    def materials(self):
        return [
            BpyPBRMaterial(mat)
            for mat in bpy.data.materials
            if mat.use_nodes
        ]


def _create_emission_scene():
    """Create a minimal scene: mesh with Emission shader (non-PBR)."""
    _clear_scene()
    mesh = bpy.data.meshes.new("test_mesh")
    obj = bpy.data.objects.new("test_obj", mesh)
    bpy.context.scene.collection.objects.link(obj)
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0.5, 1, 0)], [], [(0, 1, 2)])
    mesh.update()

    mat = bpy.data.materials.new("emission_mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    emission = nodes.new("ShaderNodeEmission")
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    obj.data.materials.append(mat)


_PBR_EXPECTED_CHECKS = {
    "pbr_workflow", "material_slots", "albedo_range",
    "metalness_binary", "roughness_range", "normal_map", "node_graph",
}


def run_pbr_tests():
    """Run stage 1d PBR tests. Returns dict with 'passed' key."""
    if not ASSETS_DIR.exists():
        return {"skipped": True, "reason": f"assets dir not found: {ASSETS_DIR}"}

    failures = []
    tests_run = 0

    # Smoke test: real asset
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    if asset.exists():
        _clear_scene()
        bpy.ops.import_scene.gltf(filepath=str(asset))
        ctx = BpyPBRContext()
        result = check_pbr(ctx, PBRConfig())
        tests_run += 1

        if result.name != "pbr":
            failures.append(f"smoke: stage name '{result.name}' != 'pbr'")
        if len(result.checks) != 7:
            failures.append(f"smoke: expected 7 checks, got {len(result.checks)}")
        missing = _PBR_EXPECTED_CHECKS - {c.name for c in result.checks}
        if missing:
            failures.append(f"smoke: missing checks: {missing}")
        json.loads(json.dumps({
            "stage": result.name,
            "checks": [{"name": c.name, "status": c.status.value} for c in result.checks],
        }))

    # Known-bad: Emission shader → pbr_workflow should FAIL
    _create_emission_scene()
    ctx = BpyPBRContext()
    result = check_pbr(ctx, PBRConfig())
    tests_run += 1

    check = next((c for c in result.checks if c.name == "pbr_workflow"), None)
    if check is None:
        failures.append("emission_mat: check 'pbr_workflow' not found")
    elif check.status.value != "FAIL":
        failures.append(
            f"emission_mat: expected 'pbr_workflow' FAIL, got {check.status.value}"
        )

    return {"passed": len(failures) == 0, "tests_run": tests_run, "failures": failures}


# ===========================================================================
# Stage 1e — Armature
# ===========================================================================

class BpyArmBone:
    def __init__(self, bone):
        self._bone = bone

    @property
    def name(self):
        return self._bone.name

    @property
    def parent(self) -> "BpyArmBone | None":
        if self._bone.parent is None:
            return None
        return BpyArmBone(self._bone.parent)


class BpyArmObject:
    def __init__(self, obj):
        self._obj = obj

    @property
    def name(self):
        return self._obj.name

    def bones(self) -> list[BpyArmBone]:
        return [BpyArmBone(b) for b in self._obj.data.bones]


class BpySkinned:
    def __init__(self, obj):
        self._obj = obj

    @property
    def name(self):
        return self._obj.name

    def per_vertex_weights(self):
        mesh = self._obj.data
        result = []
        for vert in mesh.vertices:
            weights = [g.weight for g in vert.groups if g.weight > 0.0]
            result.append(weights)
        return result


class BpyArmContext:
    def armature_objects(self) -> list[BpyArmObject]:
        return [
            BpyArmObject(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "ARMATURE"
        ]

    def skinned_meshes(self) -> list[BpySkinned]:
        return [
            BpySkinned(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "MESH" and obj.vertex_groups
        ]


def run_armature_tests():
    """Run stage 1e armature tests. Returns dict with 'passed' key."""
    if not ASSETS_DIR.exists():
        return {"skipped": True, "reason": f"assets dir not found: {ASSETS_DIR}"}

    failures = []
    tests_run = 0

    # Test: env_prop with no armature → should be SKIPPED
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    _clear_scene()
    if asset.exists():
        bpy.ops.import_scene.gltf(filepath=str(asset))

    ctx = BpyArmContext()
    config = ArmatureConfig(category="env_prop")
    result = check_armature(ctx, config)
    tests_run += 1

    if result.name != "armature":
        failures.append(f"env_prop: stage name '{result.name}' != 'armature'")
    if result.status != Status.SKIPPED:
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


# ===========================================================================
# Stage 1f — Scene
# ===========================================================================

class BpySceneMesh:
    def __init__(self, obj):
        self._obj = obj

    @property
    def name(self):
        return self._obj.name

    def triangle_count(self):
        mesh = self._obj.data
        return sum(len(p.vertices) - 2 for p in mesh.polygons if len(p.vertices) >= 3)

    def material_slot_count(self):
        return max(1, len(self._obj.material_slots))


class BpySceneArm:
    def __init__(self, obj):
        self._obj = obj

    @property
    def name(self):
        return self._obj.name

    def bone_count(self):
        return len(self._obj.data.bones)


class BpySceneImage:
    def __init__(self, image):
        self._image = image

    @property
    def width(self):
        return self._image.size[0]

    @property
    def height(self):
        return self._image.size[1]

    @property
    def channels(self):
        return self._image.channels

    @property
    def bit_depth(self):
        if self._image.channels > 0:
            return self._image.depth // self._image.channels
        return 8


class BpySceneCtx:
    def mesh_objects(self) -> list[BpySceneMesh]:
        return [
            BpySceneMesh(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
        ]

    def armature_objects(self) -> list[BpySceneArm]:
        return [
            BpySceneArm(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "ARMATURE"
        ]

    def unique_images(self) -> list[BpySceneImage]:
        return [
            BpySceneImage(img)
            for img in bpy.data.images
            if img.users > 0 and img.size[0] > 0 and img.size[1] > 0
        ]

    def orphan_counts(self):
        return {
            "meshes": sum(1 for m in bpy.data.meshes if m.users == 0),
            "materials": sum(1 for m in bpy.data.materials if m.users == 0),
            "images": sum(1 for i in bpy.data.images if i.users == 0),
        }


def run_scene_tests():
    """Run stage 1f scene tests. Returns dict with 'passed' key."""
    if not ASSETS_DIR.exists():
        return {"skipped": True, "reason": f"assets dir not found: {ASSETS_DIR}"}

    failures = []
    tests_run = 0

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
    ctx = BpySceneCtx()
    stage_result, perf = check_scene(ctx, config)
    tests_run += 1

    if stage_result.name != "scene":
        failures.append(f"smoke: stage name '{stage_result.name}' != 'scene'")
    if stage_result.status not in (Status.PASS, Status.FAIL):
        failures.append(f"smoke: unexpected status {stage_result.status.value}")
    if perf.triangles < 0:
        failures.append(f"smoke: triangle_count < 0: {perf.triangles}")
    if perf.draw_calls < 0:
        failures.append(f"smoke: draw_call_estimate < 0: {perf.draw_calls}")
    if perf.vram_mb < 0.0:
        failures.append(f"smoke: vram_estimate_mb < 0: {perf.vram_mb}")
    if perf.bones < 0:
        failures.append(f"smoke: bone_count < 0: {perf.bones}")

    json.loads(json.dumps({
        "stage": {
            "name": stage_result.name,
            "status": stage_result.status.value,
            "checks": [{"name": c.name, "status": c.status.value} for c in stage_result.checks],
        },
        "performance": {
            "triangles": perf.triangles,
            "draw_calls": perf.draw_calls,
            "vram_mb": perf.vram_mb,
            "bones": perf.bones,
        },
    }))

    return {"passed": len(failures) == 0, "tests_run": tests_run, "failures": failures}


# ===========================================================================
# Stage 2 — Remediation
# ===========================================================================

class BpyAutofixMesh:
    def __init__(self, obj):
        self._obj = obj

    @property
    def name(self):
        return self._obj.name

    def vertex_count(self):
        return len(self._obj.data.vertices)

    def recalculate_normals(self):
        bpy.context.view_layer.objects.active = self._obj
        self._obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")

    def merge_by_distance(self, threshold):
        bpy.context.view_layer.objects.active = self._obj
        self._obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        bpy.ops.object.mode_set(mode="OBJECT")
        return len(self._obj.data.vertices)


class BpyAutofixImage:
    def __init__(self, img):
        self._img = img

    @property
    def name(self):
        return self._img.name

    @property
    def size(self):
        return (self._img.size[0], self._img.size[1])

    def scale(self, new_w, new_h):
        self._img.scale(new_w, new_h)


class BpyAutofixSkinned:
    def __init__(self, obj):
        self._obj = obj

    @property
    def name(self):
        return self._obj.name

    def max_influences(self):
        mesh = self._obj.data
        max_inf = 0
        for vert in mesh.vertices:
            count = sum(1 for g in vert.groups if g.weight > 1e-6)
            if count > max_inf:
                max_inf = count
        return max_inf


class BpyAutofixContext:
    def mesh_objects(self) -> list[BpyAutofixMesh]:
        return [
            BpyAutofixMesh(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
        ]

    def images(self) -> list[BpyAutofixImage]:
        return [BpyAutofixImage(img) for img in bpy.data.images]

    def skinned_meshes(self) -> list[BpyAutofixSkinned]:
        return [
            BpyAutofixSkinned(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "MESH" and obj.vertex_groups
        ]

    def limit_bone_weights(self, limit):
        bpy.ops.object.vertex_group_limit_total(
            group_select_mode="ALL", limit=limit,
        )
        bpy.ops.object.vertex_group_normalize_all()


def run_autofix_tests():
    """Run stage 2 autofix tests. Returns dict with 'passed' key."""
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    if not ASSETS_DIR.exists() or not asset.exists():
        return {"skipped": True, "reason": f"asset not found: {asset}"}

    failures = []

    _clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(asset))
    assert len(BpyGeomContext().mesh_objects()) > 0, "No mesh objects after import"

    geom_result = check_geometry(BpyGeomContext(), GeometryConfig(category="env_prop"))
    tex_result = check_textures(BpyTexContext(), TextureConfig(max_resolution_standard=2048))
    stage1_results: list[StageResult] = [geom_result, tex_result]

    result = run_autofix(BpyAutofixContext(), stage1_results, AutofixConfig())

    if result.name != "autofix":
        failures.append(f"stage name '{result.name}' != 'autofix'")
    if result.status != Status.PASS:
        failures.append(f"expected PASS, got {result.status.value}")
    if not isinstance(result.fixes, list):
        failures.append("result.fixes is not a list")
    if not isinstance(result.flags, list):
        failures.append("result.flags is not a list")

    json.loads(json.dumps({
        "stage": result.name,
        "status": result.status.value,
        "fixes": [{"action": f.action, "target": f.target} for f in result.fixes],
        "flags": [{"issue": r.issue, "severity": r.severity.value} for r in result.flags],
    }))

    return {"passed": len(failures) == 0, "tests_run": 1, "failures": failures}


# ===========================================================================
# Stage 5 — Turntable
# ===========================================================================

def run_stage5_tests():
    """Run stage 5 turntable render tests. Returns dict with 'passed' key."""
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    if not ASSETS_DIR.exists() or not asset.exists():
        return {"skipped": True, "reason": f"asset not found: {asset}"}

    failures = []

    config = TurntableConfig(
        num_angles=4,
        engine="EEVEE",
        resolution=(256, 256),
        samples=8,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        paths = render_turntable(str(asset), tmp_dir, config)

        if len(paths) != 4:
            failures.append(f"expected 4 render paths, got {len(paths)}: {paths}")
        else:
            for p in paths:
                if not Path(p).exists():
                    failures.append(f"render file not found: {p}")
                elif Path(p).stat().st_size == 0:
                    failures.append(f"render file is empty: {p}")

    return {"passed": len(failures) == 0, "tests_run": 1, "failures": failures}


# ===========================================================================
# Run all
# ===========================================================================

_ALL_TESTS = [
    ("geometry",    run_geometry_tests),
    ("uv",          run_uv_tests),
    ("texture",     run_texture_tests),
    ("pbr",         run_pbr_tests),
    ("armature",    run_armature_tests),
    ("scene",       run_scene_tests),
    ("autofix", run_autofix_tests),
    ("stage5",      run_stage5_tests),
]


def run_all():
    results = {}
    failed = []

    for name, fn in _ALL_TESTS:
        print(f"[tests] {name} ...", flush=True)
        try:
            r = fn()
            results[name] = r
            if r.get("skipped"):
                print(f"[tests] {name}: SKIP ({r.get('reason', '')})")
            elif r.get("passed"):
                n = r.get("tests_run", "?")
                print(f"[tests] {name}: PASS ({n} tests)")
            else:
                print(f"[tests] {name}: FAIL — {r.get('failures', [])}")
                failed.append(name)
        except Exception as exc:
            import traceback
            results[name] = {"passed": False, "error": str(exc), "traceback": traceback.format_exc()}
            failed.append(name)
            print(f"[tests] {name}: ERROR — {exc}")

    return {"passed": len(failed) == 0, "failed": failed, "results": results}


def _main():
    r = run_all()
    summary = {"passed": r["passed"], "failed": r["failed"]}
    print(json.dumps(summary, indent=2))
    sys.exit(0 if r["passed"] else 1)


if __name__ == "__main__":
    _main()
