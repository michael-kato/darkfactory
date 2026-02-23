"""PBR Material Validation.

Validates PBR material compliance: workflow type, albedo/metalness/roughness
value ranges, normal map validity, material slot count, and Principled BSDF
node graph structure.

Pixel data conventions:
- albedo_pixels():   flat RGBA floats in sRGB [0, 1]  (Pillow-normalised or
                     bpy linear converted to sRGB before return)
- metalness/roughness/normal pixels: flat RGBA floats in linear [0, 1]
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pipeline.schema import CheckResult, CheckStatus, StageResult, StageStatus


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class PBRConfig:
    """Configuration for PBR material validation checks.

    Attributes
    ----------
    max_material_slots:
        Maximum material slots allowed per mesh object.
    albedo_min_srgb:
        Minimum allowed sRGB value (0–255) for albedo pixels.
    albedo_max_srgb:
        Maximum allowed sRGB value (0–255) for albedo pixels.
    albedo_sample_count:
        Maximum pixels sampled per image for pixel checks.
    metalness_binary_threshold:
        Metalness values in (threshold, 1 − threshold) are flagged as gradient.
    """

    max_material_slots: int = 3
    albedo_min_srgb: int = 30
    albedo_max_srgb: int = 240
    albedo_sample_count: int = 1000
    metalness_binary_threshold: float = 0.1


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class NormalMapData:
    """Pixel data for one normal map image connected to a Normal Map node.

    Attributes
    ----------
    image_name:
        Name of the image (for reporting).
    colorspace:
        Color space setting on the image node (e.g. 'Non-Color', 'sRGB').
    pixels:
        Flat RGBA pixel array in linear [0, 1], or None if unavailable.
    """

    image_name: str
    colorspace: str
    pixels: list[float] | None


# ---------------------------------------------------------------------------
# Abstractions (bpy implementations in blender_tests/tests.py)
# ---------------------------------------------------------------------------

class PBRMaterial(ABC):
    """A single material with PBR node graph information."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def has_nodes(self) -> bool:
        """Return True if the material has any nodes (non-empty node tree)."""
        ...

    @abstractmethod
    def uses_principled_bsdf(self) -> bool:
        """Return True if a Principled BSDF node is connected to the output."""
        ...

    @abstractmethod
    def uses_spec_gloss(self) -> bool:
        """Return True if a Specular BSDF or Glossiness socket is in use."""
        ...

    @abstractmethod
    def orphan_image_node_count(self) -> int:
        """Return count of Image Texture nodes with no connected outputs."""
        ...

    @abstractmethod
    def has_node_cycles(self) -> bool:
        """Return True if the node graph contains a directed cycle."""
        ...

    @abstractmethod
    def albedo_pixels(self) -> list[float] | None:
        """Flat RGBA pixel data in sRGB [0, 1] from the Base Color texture.

        Returns None if no base color texture is present.
        """
        ...

    @abstractmethod
    def metalness_pixels(self) -> list[float] | None:
        """Flat RGBA pixel data in linear [0, 1] from the Metallic texture."""
        ...

    @abstractmethod
    def roughness_pixels(self) -> list[float] | None:
        """Flat RGBA pixel data in linear [0, 1] from the Roughness texture."""
        ...

    @abstractmethod
    def normal_map_data(self) -> list[NormalMapData]:
        """Return NormalMapData for each image connected to a Normal Map node."""
        ...


class PBRMeshObject(ABC):
    """A single mesh object exposing its material slot count."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def material_slot_count(self) -> int: ...


class PBRBlenderContext(ABC):
    """Access to the loaded Blender scene for PBR checking."""

    @abstractmethod
    def mesh_objects(self) -> list[PBRMeshObject]: ...

    @abstractmethod
    def materials(self) -> list[PBRMaterial]: ...


# ---------------------------------------------------------------------------
# Pixel sampling helpers
# ---------------------------------------------------------------------------

_NEAR_ZERO: float = 1e-6
_NEAR_ONE: float = 1.0 - 1e-6


def _rgb_samples(
    pixels: list[float],
    max_samples: int,
) -> list[tuple[float, float, float]]:
    """Extract up to *max_samples* (R, G, B) tuples from a flat RGBA list."""
    total = len(pixels) // 4
    if total == 0:
        return []
    indices: list[int] = (
        random.sample(range(total), max_samples)
        if total > max_samples
        else list(range(total))
    )
    return [(pixels[i * 4], pixels[i * 4 + 1], pixels[i * 4 + 2]) for i in indices]


def _r_samples(pixels: list[float], max_samples: int) -> list[float]:
    """Extract up to *max_samples* R-channel values from a flat RGBA list."""
    total = len(pixels) // 4
    if total == 0:
        return []
    if total > max_samples:
        chosen = random.sample(range(total), max_samples)
        return [pixels[i * 4] for i in chosen]
    return [pixels[i * 4] for i in range(total)]


# ---------------------------------------------------------------------------
# Individual check helpers
# ---------------------------------------------------------------------------

def _check_pbr_workflow(materials: list[PBRMaterial]) -> CheckResult:
    non_compliant = [
        mat.name
        for mat in materials
        if not mat.uses_principled_bsdf() or mat.uses_spec_gloss()
    ]
    return CheckResult(
        name="pbr_workflow",
        status=CheckStatus.FAIL if non_compliant else CheckStatus.PASS,
        measured_value=non_compliant,
        threshold=0,
        message=(
            f"{len(non_compliant)} material(s) not using Principled BSDF: "
            + ", ".join(f"'{n}'" for n in non_compliant)
            if non_compliant
            else "All materials use Principled BSDF workflow"
        ),
    )


def _check_material_slots(
    mesh_objects: list[PBRMeshObject],
    config: PBRConfig,
) -> CheckResult:
    worst_count = 0
    worst_object = ""
    for obj in mesh_objects:
        count = obj.material_slot_count
        if count > worst_count:
            worst_count = count
            worst_object = obj.name
    failed = worst_count > config.max_material_slots
    return CheckResult(
        name="material_slots",
        status=CheckStatus.FAIL if failed else CheckStatus.PASS,
        measured_value={"max": worst_count, "object": worst_object},
        threshold=config.max_material_slots,
        message=(
            f"Object '{worst_object}' has {worst_count} material slot(s) "
            f"(limit {config.max_material_slots})"
            if failed
            else f"All objects within material slot limit of {config.max_material_slots}"
        ),
    )


def _check_albedo_range(
    materials: list[PBRMaterial],
    config: PBRConfig,
) -> CheckResult:
    """Sample albedo pixels (sRGB [0,1]) and check they fall in [min, max] range."""
    all_rgb: list[tuple[float, float, float]] = []
    for mat in materials:
        pix = mat.albedo_pixels()
        if not pix:
            continue
        all_rgb.extend(_rgb_samples(pix, config.albedo_sample_count))

    if not all_rgb:
        return CheckResult(
            name="albedo_range",
            status=CheckStatus.PASS,
            measured_value={"fraction_out_of_range": 0.0, "sample_count": 0},
            threshold={"min": config.albedo_min_srgb, "max": config.albedo_max_srgb},
            message="No albedo textures found — skipped",
        )

    if len(all_rgb) > config.albedo_sample_count:
        all_rgb = random.sample(all_rgb, config.albedo_sample_count)

    out_of_range = sum(
        1
        for r, g, b in all_rgb
        if (
            round(r * 255) < config.albedo_min_srgb
            or round(r * 255) > config.albedo_max_srgb
            or round(g * 255) < config.albedo_min_srgb
            or round(g * 255) > config.albedo_max_srgb
            or round(b * 255) < config.albedo_min_srgb
            or round(b * 255) > config.albedo_max_srgb
        )
    )
    fraction = out_of_range / len(all_rgb)
    warning = fraction > 0.05
    return CheckResult(
        name="albedo_range",
        status=CheckStatus.WARNING if warning else CheckStatus.PASS,
        measured_value={"fraction_out_of_range": fraction, "sample_count": len(all_rgb)},
        threshold={"min": config.albedo_min_srgb, "max": config.albedo_max_srgb},
        message=(
            f"{fraction:.1%} of sampled albedo pixels outside sRGB "
            f"[{config.albedo_min_srgb}, {config.albedo_max_srgb}] range "
            "— flagged for review"
            if warning
            else "Albedo pixel values within expected sRGB range"
        ),
    )


def _check_metalness_binary(
    materials: list[PBRMaterial],
    config: PBRConfig,
) -> CheckResult:
    """Check that metalness pixels are predominantly binary (near 0 or 1)."""
    all_values: list[float] = []
    for mat in materials:
        pix = mat.metalness_pixels()
        if not pix:
            continue
        all_values.extend(_r_samples(pix, config.albedo_sample_count))

    if not all_values:
        return CheckResult(
            name="metalness_binary",
            status=CheckStatus.PASS,
            measured_value={"fraction_gradient": 0.0},
            threshold=config.metalness_binary_threshold,
            message="No metalness textures found — skipped",
        )

    if len(all_values) > config.albedo_sample_count:
        all_values = random.sample(all_values, config.albedo_sample_count)

    t = config.metalness_binary_threshold
    gradient = sum(1 for v in all_values if t < v < (1.0 - t))
    fraction = gradient / len(all_values)
    warning = fraction > 0.10
    return CheckResult(
        name="metalness_binary",
        status=CheckStatus.WARNING if warning else CheckStatus.PASS,
        measured_value={"fraction_gradient": fraction},
        threshold=config.metalness_binary_threshold,
        message=(
            f"{fraction:.1%} of metalness pixels are gradient values "
            f"(between {t:.2f} and {1.0 - t:.2f}) — flagged for review"
            if warning
            else "Metalness values are predominantly binary (near 0 or 1)"
        ),
    )


def _check_roughness_range(
    materials: list[PBRMaterial],
    config: PBRConfig,
) -> CheckResult:
    """Warn if roughness texture is dominated (>50%) by pure 0 or pure 1 values."""
    all_values: list[float] = []
    for mat in materials:
        pix = mat.roughness_pixels()
        if not pix:
            continue
        all_values.extend(_r_samples(pix, config.albedo_sample_count))

    if not all_values:
        return CheckResult(
            name="roughness_range",
            status=CheckStatus.PASS,
            measured_value={"fraction_pure_zero": 0.0, "fraction_pure_one": 0.0},
            threshold=0.5,
            message="No roughness textures found — skipped",
        )

    if len(all_values) > config.albedo_sample_count:
        all_values = random.sample(all_values, config.albedo_sample_count)

    total = len(all_values)
    pure_zero = sum(1 for v in all_values if v < _NEAR_ZERO)
    pure_one = sum(1 for v in all_values if v > _NEAR_ONE)
    frac_zero = pure_zero / total
    frac_one = pure_one / total
    warning = frac_zero > 0.5 or frac_one > 0.5
    return CheckResult(
        name="roughness_range",
        status=CheckStatus.WARNING if warning else CheckStatus.PASS,
        measured_value={"fraction_pure_zero": frac_zero, "fraction_pure_one": frac_one},
        threshold=0.5,
        message=(
            "Roughness dominated by extreme values "
            f"(pure 0: {frac_zero:.1%}, pure 1: {frac_one:.1%}) — flagged for review"
            if warning
            else "Roughness values have reasonable spread"
        ),
    )


def _check_normal_map(materials: list[PBRMaterial]) -> CheckResult:
    """Verify normal maps use Non-Color colorspace and are blue-channel dominant."""
    colorspace_violations: list[str] = []
    channel_violations: list[str] = []

    for mat in materials:
        for nm in mat.normal_map_data():
            if nm.colorspace != "Non-Color":
                colorspace_violations.append(nm.image_name)
            if nm.pixels is not None and len(nm.pixels) >= 4:
                total = len(nm.pixels) // 4
                mean_r = sum(nm.pixels[i * 4] for i in range(total)) / total
                mean_g = sum(nm.pixels[i * 4 + 1] for i in range(total)) / total
                mean_b = sum(nm.pixels[i * 4 + 2] for i in range(total)) / total
                if not (mean_b > mean_r and mean_b > mean_g):
                    channel_violations.append(nm.image_name)

    failed = bool(colorspace_violations or channel_violations)
    return CheckResult(
        name="normal_map",
        status=CheckStatus.FAIL if failed else CheckStatus.PASS,
        measured_value={
            "colorspace_violations": colorspace_violations,
            "channel_violations": channel_violations,
        },
        threshold=None,
        message=(
            f"Normal map issues — colorspace violations: {colorspace_violations}, "
            f"channel violations: {channel_violations}"
            if failed
            else "All normal maps use correct colorspace and are blue-channel dominant"
        ),
    )


def _check_node_graph(materials: list[PBRMaterial]) -> CheckResult:
    """Flag node graph issues: orphan image nodes, cycles, empty material slots."""
    issues: list[str] = []
    for mat in materials:
        if not mat.has_nodes():
            issues.append(f"'{mat.name}': empty material slot (no nodes)")
        elif mat.uses_principled_bsdf():
            orphans = mat.orphan_image_node_count()
            if orphans > 0:
                issues.append(
                    f"'{mat.name}': {orphans} orphan Image Texture node(s) "
                    "not connected to any output"
                )
            if mat.has_node_cycles():
                issues.append(f"'{mat.name}': cycle detected in node graph")

    return CheckResult(
        name="node_graph",
        status=CheckStatus.WARNING if issues else CheckStatus.PASS,
        measured_value=issues,
        threshold=None,
        message=(
            f"{len(issues)} node graph issue(s) detected — flagged for review"
            if issues
            else "Node graphs are clean (no orphans, cycles, or empty slots)"
        ),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def check_pbr(
    context: PBRBlenderContext,
    config: PBRConfig,
) -> StageResult:
    """Run all PBR material checks and return a ``StageResult``.

    All checks always run — earlier failures do not short-circuit later checks.
    ``albedo_range``, ``metalness_binary``, ``roughness_range``, and
    ``node_graph`` are WARNING-only and never cause the stage to fail.
    ``pbr_workflow``, ``material_slots``, and ``normal_map`` use FAIL on
    violation.
    """
    mesh_objects = context.mesh_objects()
    materials = context.materials()

    checks = [
        _check_pbr_workflow(materials),
        _check_material_slots(mesh_objects, config),
        _check_albedo_range(materials, config),
        _check_metalness_binary(materials, config),
        _check_roughness_range(materials, config),
        _check_normal_map(materials),
        _check_node_graph(materials),
    ]

    stage_status = (
        StageStatus.FAIL
        if any(c.status == CheckStatus.FAIL for c in checks)
        else StageStatus.PASS
    )
    return StageResult(name="pbr", status=stage_status, checks=checks)
