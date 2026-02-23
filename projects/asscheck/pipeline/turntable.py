"""Blender Turntable Renderer.

Renders an asset from evenly-spaced azimuth angles using Blender's render
engine (EEVEE or CYCLES) to produce a set of turntable PNG images for visual
QA review.

This module **must be run inside Blender** (``bpy`` is required).  It can be
used as a library from within Blender Python or invoked as a CLI script:

    blender --background --python pipeline/turntable.py -- \\
        <asset_path> <output_dir>

All pure-Python types (``TurntableConfig``, ``render_turntable`` signature)
are defined at module level so the module is safely importable outside Blender
for type-checking purposes.  Calling :func:`render_turntable` without Blender
will raise ``ImportError``.
"""
from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class TurntableConfig:
    """Configuration for the turntable render pass.

    Attributes
    ----------
    num_angles:
        Number of evenly-spaced azimuth shots (default 8 → every 45°).
    camera_distance:
        Distance from the bounding-box centre in scene units (default 2.5).
    camera_elevation:
        Camera elevation above the horizon in degrees (default 25°).
    resolution:
        Render resolution as ``(width, height)`` in pixels.
    engine:
        ``"EEVEE"`` or ``"CYCLES"`` (default ``"EEVEE"``).
    samples:
        Render sample count (default 32).
    """
    num_angles: int = 8
    camera_distance: float = 2.5
    camera_elevation: float = 25.0
    resolution: tuple[int, int] = field(default_factory=lambda: (1024, 1024))
    engine: str = "EEVEE"
    samples: int = 32


# ---------------------------------------------------------------------------
# Blender helpers (all imports of bpy are deferred to inside the functions)
# ---------------------------------------------------------------------------

def _import_asset(path: str) -> None:
    """Load the asset file into the current Blender scene."""
    import bpy  # noqa: PLC0415

    ext = Path(path).suffix.lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=path)
    elif ext in (".gltf", ".glb"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        try:
            bpy.ops.wm.obj_import(filepath=path)
        except AttributeError:
            bpy.ops.import_scene.obj(filepath=path)
    else:
        raise ValueError(f"Unsupported asset format: {ext!r}")


def _get_scene_bounds():
    """Return (centre, radius) for all mesh objects in the scene."""
    import bpy  # noqa: PLC0415
    import mathutils

    INF = float("inf")
    min_co = [INF, INF, INF]
    max_co = [-INF, -INF, -INF]
    found = False

    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            found = True
            for corner in obj.bound_box:
                world = obj.matrix_world @ mathutils.Vector(corner)
                for i in range(3):
                    min_co[i] = min(min_co[i], world[i])
                    max_co[i] = max(max_co[i], world[i])

    if not found:
        centre = mathutils.Vector((0.0, 0.0, 0.0))
        radius = 1.0
    else:
        centre = mathutils.Vector(
            ((min_co[i] + max_co[i]) * 0.5 for i in range(3))
        )
        diag = mathutils.Vector(
            (max_co[i] - min_co[i] for i in range(3))
        )
        radius = diag.length * 0.5

    return centre, max(radius, 0.01)


def _setup_camera(x: float, y: float, z: float, target) -> None:
    """Position the scene camera at (x, y, z) pointing towards *target*."""
    import bpy  # noqa: PLC0415
    import mathutils

    cam_name = "QATurntableCamera"
    if cam_name not in bpy.data.cameras:
        cam_data = bpy.data.cameras.new(cam_name)
    else:
        cam_data = bpy.data.cameras[cam_name]

    if cam_name not in bpy.data.objects:
        cam_obj = bpy.data.objects.new(cam_name, cam_data)
        bpy.context.scene.collection.objects.link(cam_obj)
    else:
        cam_obj = bpy.data.objects[cam_name]

    cam_obj.location = (x, y, z)
    direction = mathutils.Vector(target) - mathutils.Vector((x, y, z))
    rot_quat = direction.to_track_quat("-Z", "Y")
    cam_obj.rotation_euler = rot_quat.to_euler()
    bpy.context.scene.camera = cam_obj


def _setup_lighting() -> None:
    """Set up a 3-point lighting rig.

    Attempts to configure an HDRI-based world material first; falls back to
    a basic sun + fill + back three-point rig if anything fails.
    """
    import bpy  # noqa: PLC0415

    try:
        _setup_world_lighting(bpy)
    except Exception:
        _setup_three_point_lighting(bpy)


def _setup_world_lighting(bpy) -> None:  # noqa: ANN001
    """Configure the world background as a uniform bright environment."""
    world = bpy.data.worlds.get("QAWorld") or bpy.data.worlds.new("QAWorld")
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links

    nodes.clear()
    bg = nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.0
    bg.inputs["Color"].default_value = (0.9, 0.9, 0.9, 1.0)
    out = nodes.new("ShaderNodeOutputWorld")
    links.new(bg.outputs["Background"], out.inputs["Surface"])
    bpy.context.scene.world = world


def _setup_three_point_lighting(bpy) -> None:  # noqa: ANN001
    """Add sun + fill + back point lights."""
    specs = [
        ("QASun",  3.0, (0.785,  0.0,   0.785)),
        ("QAFill", 1.0, (0.785,  3.14, -1.57)),
        ("QABack", 0.5, (-0.785, 0.0,   3.14)),
    ]
    for name, energy, rot in specs:
        if name not in bpy.data.objects:
            ld = bpy.data.lights.new(name, "SUN")
            ld.energy = energy
            lo = bpy.data.objects.new(name, ld)
            bpy.context.scene.collection.objects.link(lo)
            lo.rotation_euler = rot


def _setup_render_settings(config: TurntableConfig) -> None:
    """Apply resolution, engine, and sample count to the active scene."""
    import bpy  # noqa: PLC0415

    scene = bpy.context.scene
    scene.render.resolution_x = config.resolution[0]
    scene.render.resolution_y = config.resolution[1]
    scene.render.image_settings.file_format = "PNG"

    if config.engine == "CYCLES":
        scene.render.engine = "CYCLES"
        scene.cycles.samples = config.samples
    else:
        # Try EEVEE_NEXT (Blender 4.x) then fall back to classic EEVEE
        for engine_id in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try:
                scene.render.engine = engine_id
                break
            except Exception:
                continue
        if hasattr(scene, "eevee"):
            if hasattr(scene.eevee, "taa_render_samples"):
                scene.eevee.taa_render_samples = config.samples


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_turntable(
    asset_blend_or_gltf: str,
    output_dir: str,
    config: TurntableConfig | None = None,
) -> list[str]:
    """Render turntable views of an asset from Blender.

    Parameters
    ----------
    asset_blend_or_gltf:
        Path to the source asset (.blend, .gltf, .glb, .fbx, or .obj).
    output_dir:
        Directory where rendered PNGs are written.
    config:
        Render configuration; defaults to :class:`TurntableConfig` defaults.

    Returns
    -------
    list[str]
        Absolute paths to all rendered PNG files.
    """
    import bpy  # noqa: PLC0415

    if config is None:
        config = TurntableConfig()

    # Start from a clean scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    _import_asset(asset_blend_or_gltf)
    _setup_lighting()
    _setup_render_settings(config)

    centre, radius = _get_scene_bounds()
    asset_id = Path(asset_blend_or_gltf).stem
    os.makedirs(output_dir, exist_ok=True)

    angle_step = 360.0 / config.num_angles
    elev_rad = math.radians(config.camera_elevation)
    dist = config.camera_distance + radius

    rendered: list[str] = []
    for i in range(config.num_angles):
        angle_deg = i * angle_step
        az_rad = math.radians(angle_deg)

        cam_x = centre.x + dist * math.cos(elev_rad) * math.cos(az_rad)
        cam_y = centre.y + dist * math.cos(elev_rad) * math.sin(az_rad)
        cam_z = centre.z + dist * math.sin(elev_rad)

        _setup_camera(cam_x, cam_y, cam_z, centre)

        out_path = os.path.join(
            output_dir,
            f"{asset_id}_turntable_{int(angle_deg):03d}.png",
        )
        bpy.context.scene.render.filepath = out_path
        bpy.ops.render.render(write_still=True)
        rendered.append(out_path)

    return rendered


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    argv = sys.argv
    custom_args = argv[argv.index("--") + 1:] if "--" in argv else []
    if len(custom_args) < 2:
        print(
            "Usage: blender --background --python pipeline/turntable.py"
            " -- <asset_path> <output_dir> [num_angles]",
            file=sys.stderr,
        )
        sys.exit(1)

    asset_path_arg = custom_args[0]
    output_dir_arg = custom_args[1]
    cfg = TurntableConfig()
    if len(custom_args) >= 3:
        cfg.num_angles = int(custom_args[2])

    paths = render_turntable(asset_path_arg, output_dir_arg, cfg)
    for p in paths:
        print(f"Rendered: {p}")
