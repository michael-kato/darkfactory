"""Blender integration test for Stage 1d PBR validation.

Run with:
    blender --background --python blender_tests/test_stage1d_blender.py

Loads the sample glTF asset, runs PBR checks, and asserts the result is
valid JSON with the expected structure and no crashes.
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
    """Convert a single linear [0, 1] value to sRGB [0, 1]."""
    v = max(0.0, min(1.0, v))
    if v <= 0.0031308:
        return v * 12.92
    return 1.055 * (v ** (1.0 / 2.4)) - 0.055


def _get_image_pixels_srgb(image: "bpy.types.Image") -> list[float] | None:
    """Return flat RGBA pixels from a bpy Image, converted to sRGB [0, 1].

    bpy stores pixels in linear space; we convert to sRGB for the albedo check.
    Returns None if the image has no data loaded.
    """
    try:
        if not image.has_data:
            return None
        linear = list(image.pixels)
        # Apply linear → sRGB to R, G, B; keep A as-is.
        out: list[float] = []
        for i in range(0, len(linear), 4):
            out.append(_linear_to_srgb(linear[i]))
            out.append(_linear_to_srgb(linear[i + 1]))
            out.append(_linear_to_srgb(linear[i + 2]))
            out.append(linear[i + 3])
        return out
    except Exception:
        return None


def _get_image_pixels_linear(image: "bpy.types.Image") -> list[float] | None:
    """Return flat RGBA pixels in linear [0, 1] from a bpy Image."""
    try:
        if not image.has_data:
            return None
        return list(image.pixels)
    except Exception:
        return None


def _get_tex_image_for_socket(
    node_tree: "bpy.types.NodeTree",
    socket_name: str,
) -> "bpy.types.Image | None":
    """Follow the link on a Principled BSDF socket back to a TEX_IMAGE node."""
    pbsdf = next(
        (n for n in node_tree.nodes if n.type == "BSDF_PRINCIPLED"),
        None,
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


def _has_output_link(
    node: "bpy.types.Node",
    node_tree: "bpy.types.NodeTree",
) -> bool:
    return any(link.from_node == node for link in node_tree.links)


def _detect_cycles(node_tree: "bpy.types.NodeTree") -> bool:
    """Detect directed cycles using DFS on the node graph."""
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
# Real bpy wrappers
# ---------------------------------------------------------------------------

class BpyPBRMeshObject(PBRMeshObject):
    """Wraps a bpy.types.Object for material slot inspection."""

    def __init__(self, obj: "bpy.types.Object") -> None:
        self._obj = obj

    @property
    def name(self) -> str:
        return self._obj.name

    @property
    def material_slot_count(self) -> int:
        return len(self._obj.material_slots)


class BpyPBRMaterial(PBRMaterial):
    """Wraps a bpy.types.Material for PBR node graph introspection."""

    def __init__(self, mat: "bpy.types.Material") -> None:
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
            1
            for node in tree.nodes
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
            pixels = _get_image_pixels_linear(image)
            data.append(NormalMapData(
                image_name=image.name,
                colorspace=image.colorspace_settings.name,
                pixels=pixels,
            ))
        return data


class BpyPBRBlenderContext(PBRBlenderContext):
    """Reads mesh objects and materials from the active Blender scene."""

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

    ctx = BpyPBRBlenderContext()
    config = PBRConfig()
    result = check_pbr(ctx, config)

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

    assert data["name"] == "pbr", (
        f"Expected stage name 'pbr', got '{data['name']}'"
    )
    assert len(data["checks"]) == 7, (
        f"Expected 7 checks, got {len(data['checks'])}"
    )

    check_names = {c["name"] for c in data["checks"]}
    expected_names = {
        "pbr_workflow",
        "material_slots",
        "albedo_range",
        "metalness_binary",
        "roughness_range",
        "normal_map",
        "node_graph",
    }
    assert check_names == expected_names, (
        f"Unexpected check names: {check_names - expected_names}"
    )

    print(json_str)
    print("PASS: Stage 1d PBR validation integration test passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
