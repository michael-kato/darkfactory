"""Blender integration test for Stage 1c Texture checks.

Run with:
    blender --background --python blender_tests/test_stage1c_blender.py

Loads the sample glTF asset, runs texture checks, and asserts the result is
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

from pipeline.stage1.texture import (  # noqa: E402
    ImageTextureNode,
    TextureBlenderContext,
    TextureConfig,
    TextureImage,
    TextureMaterial,
    check_textures,
)


# ---------------------------------------------------------------------------
# Real bpy wrappers
# ---------------------------------------------------------------------------

def _get_socket_name(node: "bpy.types.Node") -> str:
    """Return the downstream socket name for color space inference.

    Follows the first outgoing link from the Color output. Falls back to the
    image name so color space inference can still use it as a keyword source.
    """
    try:
        links = node.outputs["Color"].links
        if links:
            return links[0].to_socket.name
    except (KeyError, AttributeError):
        pass
    return node.image.name if node.image else ""


def _filepath_is_missing(image: "bpy.types.Image") -> bool:
    """Return True if image has an external filepath that cannot be resolved."""
    if not image.filepath:
        return False  # No filepath: packed or generated — not "missing"
    if image.packed_file:
        return False  # Packed — file is embedded, not external
    abs_path = bpy.path.abspath(image.filepath)
    return not os.path.exists(abs_path)


class BpyTextureMaterial(TextureMaterial):
    """Wraps a bpy.types.Material for texture node extraction."""

    def __init__(self, mat: "bpy.types.Material") -> None:
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
    """Wraps a bpy.types.Image for size/depth/colorspace access."""

    def __init__(self, image: "bpy.types.Image") -> None:
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
    """Reads materials and images from the active Blender scene."""

    def materials(self) -> list[TextureMaterial]:
        return [
            BpyTextureMaterial(mat)
            for mat in bpy.data.materials
            if mat.use_nodes
        ]

    def images(self) -> list[TextureImage]:
        return [BpyTextureImage(img) for img in bpy.data.images]


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

    ctx = BpyTextureBlenderContext()
    config = TextureConfig()
    result = check_textures(ctx, config)

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

    assert data["name"] == "texture", (
        f"Expected stage name 'texture', got '{data['name']}'"
    )
    assert len(data["checks"]) == 6, (
        f"Expected 6 checks, got {len(data['checks'])}"
    )

    check_names = {c["name"] for c in data["checks"]}
    expected_names = {
        "missing_textures",
        "resolution_limit",
        "power_of_two",
        "texture_count",
        "channel_depth",
        "color_space",
    }
    assert check_names == expected_names, (
        f"Unexpected check names: {check_names - expected_names}"
    )

    print(json_str)
    print("PASS: Stage 1c texture checks integration test passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
