"""Integration test for Stage 1d PBR validation — runs inside Blender headless.

Usage (headless):  blender --background --python blender_tests/test_stage1d_blender.py
Usage (GUI):       Open in Blender Text Editor, press Alt+R

Tests:
  1. Smoke test: load street_lamp_01.gltf, run check_pbr, assert valid structure.
  2. Programmatic known-bad: create a scene with an Emission shader (non-PBR),
     assert the pbr_workflow check returns FAIL.

Note: GLB export/import converts Emission to a PBR-compatible material, so
non_pbr_material.glb cannot be used here. The violation is created programmatically.

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

from pipeline.stage1.pbr import (  # noqa: E402
    NormalMapData,
    PBRBlenderContext,
    PBRConfig,
    PBRMaterial,
    PBRMeshObject,
    check_pbr,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _linear_to_srgb(v: float) -> float:
    v = max(0.0, min(1.0, v))
    if v <= 0.0031308:
        return v * 12.92
    return 1.055 * (v ** (1.0 / 2.4)) - 0.055


def _get_image_pixels_srgb(image: bpy.types.Image) -> list[float] | None:
    try:
        if not image.has_data:
            return None
        linear = list(image.pixels)
        out: list[float] = []
        for i in range(0, len(linear), 4):
            out.append(_linear_to_srgb(linear[i]))
            out.append(_linear_to_srgb(linear[i + 1]))
            out.append(_linear_to_srgb(linear[i + 2]))
            out.append(linear[i + 3])
        return out
    except Exception:
        return None


def _get_image_pixels_linear(image: bpy.types.Image) -> list[float] | None:
    try:
        if not image.has_data:
            return None
        return list(image.pixels)
    except Exception:
        return None


def _get_tex_image_for_socket(node_tree: bpy.types.NodeTree, socket_name: str):
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


def _has_output_link(node: bpy.types.Node, node_tree: bpy.types.NodeTree) -> bool:
    return any(link.from_node == node for link in node_tree.links)


def _detect_cycles(node_tree: bpy.types.NodeTree) -> bool:
    successors: dict[str, list[str]] = {n.name: [] for n in node_tree.nodes}
    for link in node_tree.links:
        successors[link.from_node.name].append(link.to_node.name)

    visited: set[str] = set()
    rec_stack: set[str] = set()

    def dfs(name: str) -> bool:
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


# ---------------------------------------------------------------------------
# bpy-backed wrappers
# ---------------------------------------------------------------------------

class BpyPBRMeshObject(PBRMeshObject):
    def __init__(self, obj: bpy.types.Object) -> None:
        self._obj = obj

    @property
    def name(self) -> str:
        return self._obj.name

    @property
    def material_slot_count(self) -> int:
        return len(self._obj.material_slots)


class BpyPBRMaterial(PBRMaterial):
    def __init__(self, mat: bpy.types.Material) -> None:
        self._mat = mat

    @property
    def name(self) -> str:
        return self._mat.name

    def has_nodes(self) -> bool:
        return (
            self._mat.use_nodes
            and self._mat.node_tree is not None
            and len(self._mat.node_tree.nodes) > 0
        )

    def uses_principled_bsdf(self) -> bool:
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

    def uses_spec_gloss(self) -> bool:
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

    def orphan_image_node_count(self) -> int:
        if not self.has_nodes():
            return 0
        tree = self._mat.node_tree
        return sum(
            1 for node in tree.nodes
            if node.type == "TEX_IMAGE" and not _has_output_link(node, tree)
        )

    def has_node_cycles(self) -> bool:
        if not self.has_nodes():
            return False
        return _detect_cycles(self._mat.node_tree)

    def albedo_pixels(self) -> list[float] | None:
        if not self.has_nodes():
            return None
        image = _get_tex_image_for_socket(self._mat.node_tree, "Base Color")
        if image is None:
            return None
        return _get_image_pixels_srgb(image)

    def metalness_pixels(self) -> list[float] | None:
        if not self.has_nodes():
            return None
        image = _get_tex_image_for_socket(self._mat.node_tree, "Metallic")
        if image is None:
            return None
        return _get_image_pixels_linear(image)

    def roughness_pixels(self) -> list[float] | None:
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


class BpyPBRBlenderContext(PBRBlenderContext):
    def mesh_objects(self) -> list[PBRMeshObject]:
        return [
            BpyPBRMeshObject(obj)
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
        ]

    def materials(self) -> list[PBRMaterial]:
        return [
            BpyPBRMaterial(mat)
            for mat in bpy.data.materials
            if mat.use_nodes
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


def _create_emission_scene() -> None:
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


EXPECTED_CHECK_NAMES = {
    "pbr_workflow", "material_slots", "albedo_range",
    "metalness_binary", "roughness_range", "normal_map", "node_graph",
}


# ---------------------------------------------------------------------------
# Test entry point
# ---------------------------------------------------------------------------

def run_tests() -> dict:
    """Run all stage1d PBR tests. Returns dict with 'passed' key."""
    if not ASSETS_DIR.exists():
        return {"skipped": True, "reason": f"assets dir not found: {ASSETS_DIR}"}

    failures: list[str] = []
    tests_run = 0

    # Smoke test: real asset
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    if asset.exists():
        _clear_scene()
        bpy.ops.import_scene.gltf(filepath=str(asset))
        ctx = BpyPBRBlenderContext()
        result = check_pbr(ctx, PBRConfig())
        tests_run += 1

        if result.name != "pbr":
            failures.append(f"smoke: stage name '{result.name}' != 'pbr'")
        if len(result.checks) != 7:
            failures.append(f"smoke: expected 7 checks, got {len(result.checks)}")
        missing = EXPECTED_CHECK_NAMES - {c.name for c in result.checks}
        if missing:
            failures.append(f"smoke: missing checks: {missing}")
        json.loads(json.dumps({
            "stage": result.name,
            "checks": [{"name": c.name, "status": c.status.value} for c in result.checks],
        }))

    # Known-bad: Emission shader → pbr_workflow should FAIL
    _create_emission_scene()
    ctx = BpyPBRBlenderContext()
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


def _main() -> None:
    r = run_tests()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("passed", r.get("skipped", False)) else 1)


if __name__ == "__main__":
    _main()
