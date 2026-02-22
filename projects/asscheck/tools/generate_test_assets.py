"""
tools/generate_test_assets.py
Procedurally generates known-bad 3D assets for pipeline testing.

Design rules:
  - Minimum triangles needed to reproduce the error — nothing more.
  - Only the components required for the specific check are included.
    Geometry checks need no material or UV. UV checks need no material.
    Material/PBR checks need a material but minimal geometry.
  - Mesh names end in _01 and increment as new examples are added.

Usage:
    blender --background --python tools/generate_test_assets.py -- projects/asscheck/assets
"""

import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block, do_unlink=True)
    for block in list(bpy.data.materials):
        bpy.data.materials.remove(block, do_unlink=True)
    for block in list(bpy.data.images):
        bpy.data.images.remove(block, do_unlink=True)


def export_glb(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format='GLB',
        export_apply=True,
    )
    print(f"  wrote {path.relative_to(path.parents[3])}")


def make_mesh(name: str, verts, faces):
    """Create a mesh object from raw vert/face lists. Returns obj."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return obj


TRIANGLE_VERTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)]
TRIANGLE_FACES = [(0, 1, 2)]
TRIANGLE_UVS   = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]


def single_triangle(name: str):
    return make_mesh(name, TRIANGLE_VERTS, TRIANGLE_FACES)


def set_triangle_uvs(obj, uvs=TRIANGLE_UVS):
    uv_layer = obj.data.uv_layers.new(name="UVMap")
    for i, uv in enumerate(uvs):
        uv_layer.data[i].uv = uv


def add_principled_material(obj, name=None):
    mat = bpy.data.materials.new(name or (obj.name + "_mat"))
    mat.use_nodes = True  # default node tree: Principled BSDF → Material Output
    obj.data.materials.append(mat)
    return mat


# ---------------------------------------------------------------------------
# Known-bad: geometry (stage1a)
# No material or UV needed — geometry checks operate on mesh topology only.
# ---------------------------------------------------------------------------

def make_non_manifold_01(out_dir: Path):
    """
    Single triangle.
    Its 3 edges are each shared by only 1 face → all 3 are non-manifold.
    Triggers: non_manifold check (measured_value == 3).
    """
    clear_scene()
    single_triangle("non_manifold_01")
    export_glb(out_dir / "known-bad" / "non_manifold_01.glb")


def make_degenerate_faces_01(out_dir: Path):
    """
    Single triangle whose 3 vertices are collinear (zero area).
    Triggers: degenerate_faces check (measured_value == 1).
    """
    clear_scene()
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]  # collinear on x-axis
    make_mesh("degenerate_faces_01", verts, [(0, 1, 2)])
    export_glb(out_dir / "known-bad" / "degenerate_faces_01.glb")


def make_flipped_normals_01(out_dir: Path):
    """
    Tetrahedron (4 triangles, closed manifold) with one face's winding reversed.
    The reversed face's normal points inward while its neighbours point outward.
    Triggers: normal_consistency check.
    Minimum closed shape that gives the checker meaningful neighbour context.
    """
    clear_scene()
    s = 1.0
    verts = [
        ( s,  s,  s),
        ( s, -s, -s),
        (-s,  s, -s),
        (-s, -s,  s),
    ]
    faces = [
        (2, 1, 0),   # face 0: winding reversed → normal points inward
        (0, 1, 3),
        (1, 2, 3),
        (0, 2, 3),
    ]
    make_mesh("flipped_normals_01", verts, faces)
    export_glb(out_dir / "known-bad" / "flipped_normals_01.glb")


def make_loose_geometry_01(out_dir: Path):
    """
    Two connected triangles (share an edge, forming a diamond) plus one isolated vertex.
    Triggers: loose_geometry check (measured_value == 1 isolated vert).
    """
    clear_scene()
    verts = [
        (0.0,  0.0, 0.0),   # 0 — shared by both tris
        (1.0,  0.0, 0.0),   # 1 — shared by both tris
        (0.5,  0.5, 0.0),   # 2 — top
        (0.5, -0.5, 0.0),   # 3 — bottom
        (5.0,  0.0, 0.0),   # 4 — isolated, no faces
    ]
    faces = [(0, 1, 2), (0, 1, 3)]
    make_mesh("loose_geometry_01", verts, faces)
    export_glb(out_dir / "known-bad" / "loose_geometry_01.glb")


def make_overbudget_tris_01(out_dir: Path):
    """
    Grid of 5100 triangles — just over the env_prop max budget (5000).
    51 × 50 quads = 2550 quads → 5100 triangles when triangulated.
    Triggers: polycount_budget check (over max).
    """
    clear_scene()
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=51, y_subdivisions=50)
    obj = bpy.context.active_object
    obj.name = "overbudget_tris_01"
    obj.data.name = "overbudget_tris_01"

    # Triangulate so the triangle count is exact on export
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.object.mode_set(mode='OBJECT')

    export_glb(out_dir / "known-bad" / "overbudget_tris_01.glb")


def make_underbudget_tris_01(out_dir: Path):
    """
    Single triangle — clearly below the env_prop min budget (500).
    Triggers: polycount_budget check (under min).
    Note: also non-manifold (boundary edges), but the primary signal is polycount.
    """
    clear_scene()
    single_triangle("underbudget_tris_01")
    export_glb(out_dir / "known-bad" / "underbudget_tris_01.glb")


# ---------------------------------------------------------------------------
# Known-bad: UV (stage1b)
# No material needed — UV checks operate on the mesh UV layer only.
# ---------------------------------------------------------------------------

def make_no_uvs_01(out_dir: Path):
    """
    Single triangle with no UV layer.
    Triggers: missing_uvs check.
    """
    clear_scene()
    single_triangle("no_uvs_01")
    # No UV layer added — that's the whole point.
    export_glb(out_dir / "known-bad" / "no_uvs_01.glb")


def make_uvs_out_of_bounds_01(out_dir: Path):
    """
    Single triangle with UV coordinates at (2.5, 2.5) — outside [0, 1].
    Triggers: uv_bounds check.
    """
    clear_scene()
    obj = single_triangle("uvs_out_of_bounds_01")
    set_triangle_uvs(obj, [(2.5, 2.5), (3.5, 2.5), (3.0, 3.5)])
    export_glb(out_dir / "known-bad" / "uvs_out_of_bounds_01.glb")


def make_uv_overlap_01(out_dir: Path):
    """
    Two triangles occupying identical UV space (both mapped to the same coords).
    Triggers: uv_overlap check.
    """
    clear_scene()
    # Two coplanar triangles side by side in 3D, but same UV coords
    verts = [
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0),  # tri 0
        (2.0, 0.0, 0.0), (3.0, 0.0, 0.0), (2.5, 1.0, 0.0),  # tri 1
    ]
    faces = [(0, 1, 2), (3, 4, 5)]
    obj = make_mesh("uv_overlap_01", verts, faces)

    # Both faces use the same UV coordinates → complete overlap
    uv_layer = obj.data.uv_layers.new(name="UVMap")
    for i in range(6):
        uv_layer.data[i].uv = TRIANGLE_UVS[i % 3]

    export_glb(out_dir / "known-bad" / "uv_overlap_01.glb")


# ---------------------------------------------------------------------------
# Known-bad: materials / PBR (stage1c / stage1d)
# ---------------------------------------------------------------------------

def make_non_pbr_material_01(out_dir: Path):
    """
    Single triangle with an Emission shader instead of Principled BSDF.
    Triggers: pbr_workflow check.
    """
    clear_scene()
    obj = single_triangle("non_pbr_material_01")
    set_triangle_uvs(obj)

    mat = bpy.data.materials.new("non_pbr_material_01_mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value = (1.0, 0.4, 0.0, 1.0)
    output = nodes.new('ShaderNodeOutputMaterial')
    links.new(emission.outputs['Emission'], output.inputs['Surface'])
    obj.data.materials.append(mat)

    export_glb(out_dir / "known-bad" / "non_pbr_material_01.glb")


def make_wrong_colorspace_normal_01(out_dir: Path):
    """
    Single triangle with a normal map connected to Principled BSDF
    but colorspace set to sRGB instead of Non-Color.
    Triggers: normal_map colorspace check.
    """
    clear_scene()
    obj = single_triangle("wrong_colorspace_normal_01")
    set_triangle_uvs(obj)

    img = bpy.data.images.new("fake_normal_01", width=4, height=4)
    img.colorspace_settings.name = 'sRGB'  # intentionally wrong

    mat = bpy.data.materials.new("wrong_colorspace_normal_01_mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    tex  = nodes.new('ShaderNodeTexImage')
    tex.image = img
    nmap = nodes.new('ShaderNodeNormalMap')
    links.new(tex.outputs['Color'], nmap.inputs['Color'])
    links.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])
    obj.data.materials.append(mat)

    export_glb(out_dir / "known-bad" / "wrong_colorspace_normal_01.glb")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

GENERATORS = [
    # geometry (stage1a)
    make_non_manifold_01,
    make_degenerate_faces_01,
    make_flipped_normals_01,
    make_loose_geometry_01,
    make_overbudget_tris_01,
    make_underbudget_tris_01,
    # UV (stage1b)
    make_no_uvs_01,
    make_uvs_out_of_bounds_01,
    make_uv_overlap_01,
    # material / PBR (stage1c / stage1d)
    make_non_pbr_material_01,
    make_wrong_colorspace_normal_01,
]


if __name__ == "__main__":
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    if not argv:
        print("Usage: blender --background --python tools/generate_test_assets.py -- <assets_dir>")
        sys.exit(1)

    out_dir = Path(argv[0]).resolve()
    print(f"[generate] output dir: {out_dir}")
    print(f"[generate] {len(GENERATORS)} assets to generate\n")

    failed = []
    for gen in GENERATORS:
        print(f"[generate] {gen.__name__} ...", flush=True)
        try:
            gen(out_dir)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            failed.append((gen.__name__, exc))

    print(f"\n[generate] done — {len(GENERATORS) - len(failed)}/{len(GENERATORS)} succeeded")
    if failed:
        for name, exc in failed:
            print(f"  FAILED: {name}: {exc}")
        sys.exit(1)
