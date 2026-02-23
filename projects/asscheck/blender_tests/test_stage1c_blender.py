"""Integration test for Stage 1c texture checks — runs inside Blender headless.

Usage (headless):  blender --background --python blender_tests/test_stage1c_blender.py
Usage (GUI):       Open in Blender Text Editor, press Alt+R

Tests:
  1. Smoke test: load street_lamp_01.gltf, run check_textures, assert valid structure.
  2. Programmatic known-bad: create a normal map with wrong colorspace (sRGB),
     assert the color_space check returns FAIL.

Note: GLB export/import normalises colorspace metadata, so the wrong-colorspace
known-bad GLB is not usable here. The colorspace violation is created programmatically
inside Blender (real bpy calls, not mocked).

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

from pipeline.stage1.texture import (  # noqa: E402
    ImageTextureNode,
    TextureBlenderContext,
    TextureConfig,
    TextureImage,
    TextureMaterial,
    check_textures,
)


# ---------------------------------------------------------------------------
# bpy-backed wrappers  (same as before, kept intact)
# ---------------------------------------------------------------------------

def _get_socket_name(node: bpy.types.Node) -> str:
    try:
        links = node.outputs["Color"].links
        if links:
            return links[0].to_socket.name
    except (KeyError, AttributeError):
        pass
    return node.image.name if node.image else ""


def _filepath_is_missing(image: bpy.types.Image) -> bool:
    import os
    if not image.filepath:
        return False
    if image.packed_file:
        return False
    abs_path = bpy.path.abspath(image.filepath)
    return not os.path.exists(abs_path)


class BpyTextureMaterial(TextureMaterial):
    def __init__(self, mat: bpy.types.Material) -> None:
        self._mat = mat

    @property
    def name(self) -> str:
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
                socket_name=_get_socket_name(node),
                image_name=node.image.name,
                filepath_missing=_filepath_is_missing(node.image),
            ))
        return nodes


class BpyTextureImage(TextureImage):
    def __init__(self, image: bpy.types.Image) -> None:
        self._image = image

    @property
    def name(self) -> str:
        return self._image.name

    @property
    def size(self) -> tuple[int, int]:
        return (self._image.size[0], self._image.size[1])

    @property
    def depth(self) -> int:
        return self._image.depth

    @property
    def colorspace_name(self) -> str:
        return self._image.colorspace_settings.name


class BpyTextureBlenderContext(TextureBlenderContext):
    def materials(self) -> list[TextureMaterial]:
        return [
            BpyTextureMaterial(mat)
            for mat in bpy.data.materials
            if mat.use_nodes
        ]

    def images(self) -> list[TextureImage]:
        return [BpyTextureImage(img) for img in bpy.data.images]


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block, do_unlink=True)
    for block in list(bpy.data.materials):
        bpy.data.materials.remove(block, do_unlink=True)
    for block in list(bpy.data.images):
        bpy.data.images.remove(block, do_unlink=True)


def _create_wrong_colorspace_scene() -> None:
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


EXPECTED_CHECK_NAMES = {
    "missing_textures", "resolution_limit", "power_of_two",
    "texture_count", "channel_depth", "color_space",
}


# ---------------------------------------------------------------------------
# Test entry point
# ---------------------------------------------------------------------------

def run_tests() -> dict:
    """Run all stage1c texture tests. Returns dict with 'passed' key."""
    if not ASSETS_DIR.exists():
        return {"skipped": True, "reason": f"assets dir not found: {ASSETS_DIR}"}

    failures: list[str] = []
    tests_run = 0

    # Smoke test: real asset
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    if asset.exists():
        _clear_scene()
        bpy.ops.import_scene.gltf(filepath=str(asset))
        ctx = BpyTextureBlenderContext()
        result = check_textures(ctx, TextureConfig())
        tests_run += 1

        if result.name != "texture":
            failures.append(f"smoke: stage name '{result.name}' != 'texture'")
        if len(result.checks) != 6:
            failures.append(f"smoke: expected 6 checks, got {len(result.checks)}")
        missing = EXPECTED_CHECK_NAMES - {c.name for c in result.checks}
        if missing:
            failures.append(f"smoke: missing checks: {missing}")
        json.loads(json.dumps({
            "stage": result.name,
            "checks": [{"name": c.name, "status": c.status.value} for c in result.checks],
        }))

    # Known-bad: programmatic wrong colorspace (GLB roundtrip loses colorspace info)
    _create_wrong_colorspace_scene()
    ctx = BpyTextureBlenderContext()
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


def _main() -> None:
    r = run_tests()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("passed", r.get("skipped", False)) else 1)


if __name__ == "__main__":
    _main()
