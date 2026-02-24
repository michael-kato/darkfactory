"""Texture Checks.

Validates all textures referenced by materials in the Blender scene:
resolution limits, power-of-two dimensions, missing references, texture
count per material, channel count/bit depth, and color space assignment.

"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.schema import CheckResult, StageResult, Status

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class TextureConfig:
    """Configuration for texture checks.

    Attributes
    ----------
    max_resolution_standard:
        Maximum allowed dimension (width or height) for standard assets.
    max_resolution_hero:
        Maximum allowed dimension for hero assets.
    is_hero_asset:
        If True, use hero resolution limit; otherwise use standard limit.
    max_textures_per_material:
        Maximum number of Image Texture nodes permitted on a single material.
    """

    max_resolution_standard: int = 2048
    max_resolution_hero: int = 4096
    is_hero_asset: bool = False
    max_textures_per_material: int = 8

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ImageTextureNode:
    """One Image Texture node in a material's node graph.

    Attributes
    ----------
    socket_name:
        The downstream socket name this node's Color output connects to
        (used for color space inference). Falls back to the image name if
        the node is unconnected.
    image_name:
        The name of the referenced ``bpy.data.images`` entry.
    filepath_missing:
        True if the image's filepath cannot be resolved to an existing file.
    """

    socket_name: str
    image_name: str
    filepath_missing: bool

_SRGB_KEYWORDS = (
    "albedo", "diffuse", "color", "colour", "basecolor", "base_color",
)
_LINEAR_KEYWORDS = (
    "normal", "rough", "roughness", "metal", "metallic",
    "ao", "ambient_occlusion", "specular", "height", "bump", "displacement",
)

def _infer_expected_colorspace(socket_name, image_name):
    """Infer expected color space from socket and image name keywords.

    Returns ``'sRGB'``, ``'Non-Color'``, or ``None`` if no keyword matches.
    Socket name is checked before image name so explicit wiring takes priority.
    """
    for text in (socket_name.lower(), image_name.lower()):
        for kw in _SRGB_KEYWORDS:
            if kw in text:
                return "sRGB"
        for kw in _LINEAR_KEYWORDS:
            if kw in text:
                return "Non-Color"
    return None

# ---------------------------------------------------------------------------
# Individual check helpers
# ---------------------------------------------------------------------------

def _check_missing_textures(
    materials: list[TextureMaterial],
) -> CheckResult:
    broken = sum(
        1
        for mat in materials
        for node in mat.image_texture_nodes()
        if node.filepath_missing
    )
    return CheckResult(
        name="missing_textures",
        status=Status.FAIL if broken > 0 else Status.PASS,
        value=broken,
        threshold=0,
        message=(
            f"{broken} texture reference(s) with missing files"
            if broken else "All texture references resolve to existing files"
        ),
    )

def _is_power_of_two(n):
    return n > 0 and (n & (n - 1)) == 0

def _check_resolution_limit(
    images: list[TextureImage],
    config: TextureConfig,
) -> CheckResult:
    limit = (
        config.max_resolution_hero if config.is_hero_asset
        else config.max_resolution_standard
    )
    violations = []
    for img in images:
        w, h = img.size
        if w > limit or h > limit:
            violations.append({"name": img.name, "size": [w, h], "limit": limit})
    return CheckResult(
        name="resolution_limit",
        status=Status.FAIL if violations else Status.PASS,
        value={"violations": violations},
        threshold=limit,
        message=(
            f"{len(violations)} image(s) exceed resolution limit of {limit}px"
            if violations else f"All images within resolution limit of {limit}px"
        ),
    )

def _check_power_of_two(
    images: list[TextureImage],
) -> CheckResult:
    violations = []
    for img in images:
        w, h = img.size
        if not (_is_power_of_two(w) and _is_power_of_two(h)):
            violations.append({"name": img.name, "size": [w, h]})
    return CheckResult(
        name="power_of_two",
        status=Status.FAIL if violations else Status.PASS,
        value={"violations": violations},
        threshold=0,
        message=(
            f"{len(violations)} image(s) have non-power-of-two dimensions"
            if violations else "All images have power-of-two dimensions"
        ),
    )

def _check_texture_count(
    materials: list[TextureMaterial],
    config: TextureConfig,
) -> CheckResult:
    worst_count = 0
    worst_mat = ""
    for mat in materials:
        count = len(mat.image_texture_nodes())
        if count > worst_count:
            worst_count = count
            worst_mat = mat.name
    failed = worst_count > config.max_textures_per_material
    return CheckResult(
        name="texture_count",
        status=Status.FAIL if failed else Status.PASS,
        value={"max": worst_count, "material": worst_mat},
        threshold=config.max_textures_per_material,
        message=(
            f"Material '{worst_mat}' has {worst_count} texture(s) "
            f"(limit {config.max_textures_per_material})"
            if failed else
            f"All materials within texture limit of {config.max_textures_per_material}"
        ),
    )

_STANDARD_DEPTHS: frozenset[int] = frozenset({24, 32})

def _check_channel_depth(
    images: list[TextureImage],
) -> CheckResult:
    flagged = [
        {"name": img.name, "depth": img.depth}
        for img in images
        if img.depth not in _STANDARD_DEPTHS
    ]
    return CheckResult(
        name="channel_depth",
        status=Status.WARNING if flagged else Status.PASS,
        value={"images": flagged},
        threshold=sorted(_STANDARD_DEPTHS),
        message=(
            f"{len(flagged)} image(s) have non-standard bit depth "
            "(16-bit or HDR) — flagged for review"
            if flagged else "All images have standard bit depth (24 or 32)"
        ),
    )

def _check_color_space(
    materials: list[TextureMaterial],
    images: list[TextureImage],
) -> CheckResult:
    image_by_name = {img.name: img for img in images}
    violations = []

    for mat in materials:
        for node in mat.image_texture_nodes():
            expected = _infer_expected_colorspace(node.socket_name, node.image_name)
            if expected is None:
                continue  # Cannot infer map type — skip
            img = image_by_name.get(node.image_name)
            if img is None:
                continue  # Image not available in context

            actual = img.colorspace_name
            if expected == "Non-Color":
                # Both "Non-Color" and "Linear" are acceptable for linear maps.
                if actual not in ("Non-Color", "Linear"):
                    violations.append({
                        "name": node.image_name,
                        "expected": "Non-Color",
                        "actual": actual,
                    })
            else:
                if actual != expected:
                    violations.append({
                        "name": node.image_name,
                        "expected": expected,
                        "actual": actual,
                    })

    return CheckResult(
        name="color_space",
        status=Status.WARNING if violations else Status.PASS,
        value={"violations": violations},
        threshold=None,
        message=(
            f"{len(violations)} color space mismatch(es) detected — flagged for review"
            if violations else "All texture color spaces match expected values"
        ),
    )

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def check_textures(
    context,
    config: TextureConfig,
) -> StageResult:
    """Run all texture checks and return a ``StageResult``.

    All checks always run — earlier failures do not short-circuit later checks.
    ``channel_depth`` and ``color_space`` are WARNING-only and never cause the
    stage to fail.
    """
    materials = context.materials()
    images = context.images()

    checks = [
        _check_missing_textures(materials),
        _check_resolution_limit(images, config),
        _check_power_of_two(images),
        _check_texture_count(materials, config),
        _check_channel_depth(images),
        _check_color_space(materials, images),
    ]

    stage_status = (
        Status.FAIL
        if any(c.status == Status.FAIL for c in checks)
        else Status.PASS
    )
    return StageResult(name="texture", status=stage_status, checks=checks)
