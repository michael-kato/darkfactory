"""
tools/generate_test_assets.py
Procedurally generates known-bad 3D assets for pipeline testing.

Design rules:
  - Minimum triangles needed to reproduce the error — nothing more.
  - Only the components required for the specific check are included.
    Geometry checks need no material or UV. UV checks need no material.
    Material/PBR checks need a material but minimal geometry.
  - Mesh names are descriptive of the error they contain.

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
# ---------------------------------------------------------------------------

def make_non_manifold(out_dir: Path):
    """
    Single triangle. Boundary edges are non-manifold.
    Triggers: non_manifold check.
    """
    clear_scene()
    single_triangle("non_manifold")
    export_glb(out_dir / "known-bad" / "non_manifold.glb")


def make_degenerate_faces(out_dir: Path):
    """
    Single triangle whose 3 vertices are collinear (zero area).
    Triggers: degenerate_faces check.
    """
    clear_scene()
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
    make_mesh("degenerate_faces", verts, [(0, 1, 2)])
    export_glb(out_dir / "known-bad" / "degenerate_faces.glb")


def make_flipped_normals(out_dir: Path):
    """
    Tetrahedron with one face's winding reversed.
    Triggers: normal_consistency check.
    """
    clear_scene()
    s = 1.0
    verts = [(s, s, s), (s, -s, -s), (-s, s, -s), (-s, -s, s)]
    faces = [
        (2, 1, 0),   # reversed
        (0, 1, 3),
        (1, 2, 3),
        (0, 2, 3),
    ]
    make_mesh("flipped_normals", verts, faces)
    export_glb(out_dir / "known-bad" / "flipped_normals.glb")


def make_loose_geometry(out_dir: Path):
    """
    Two connected triangles plus one isolated vertex.
    Triggers: loose_geometry check.
    """
    clear_scene()
    verts = [
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 0.5, 0.0),
        (0.5, -0.5, 0.0), (5.0, 0.0, 0.0), # isolated
    ]
    faces = [(0, 1, 2), (0, 1, 3)]
    make_mesh("loose_geometry", verts, faces)
    export_glb(out_dir / "known-bad" / "loose_geometry.glb")


def make_overbudget_tris(out_dir: Path):
    """
    Grid of 5100 triangles — over max budget.
    Triggers: polycount_budget check.
    """
    clear_scene()
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=51, y_subdivisions=50)
    obj = bpy.context.active_object
    obj.name = "overbudget_tris"
    obj.data.name = "overbudget_tris"

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.object.mode_set(mode='OBJECT')

    export_glb(out_dir / "known-bad" / "overbudget_tris.glb")


def make_underbudget_tris(out_dir: Path):
    """
    Single triangle — under min budget.
    Triggers: polycount_budget check.
    """
    clear_scene()
    single_triangle("underbudget_tris")
    export_glb(out_dir / "known-bad" / "underbudget_tris.glb")


# ---------------------------------------------------------------------------
# Known-bad: UV (stage1b)
# ---------------------------------------------------------------------------

def make_no_uvs(out_dir: Path):
    """
    Single triangle with no UV layer.
    Triggers: missing_uvs check.
    """
    clear_scene()
    single_triangle("no_uvs")
    export_glb(out_dir / "known-bad" / "no_uvs.glb")


def make_uvs_out_of_bounds(out_dir: Path):
    """
    Single triangle with UV coordinates outside [0, 1].
    Triggers: uv_bounds check.
    """
    clear_scene()
    obj = single_triangle("uvs_out_of_bounds")
    set_triangle_uvs(obj, [(2.5, 2.5), (3.5, 2.5), (3.0, 3.5)])
    export_glb(out_dir / "known-bad" / "uvs_out_of_bounds.glb")


def make_uv_overlap(out_dir: Path):
    """
    Two triangles occupying identical UV space.
    Triggers: uv_overlap check.
    """
    clear_scene()
    verts = [
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0),
        (2.0, 0.0, 0.0), (3.0, 0.0, 0.0), (2.5, 1.0, 0.0),
    ]
    faces = [(0, 1, 2), (3, 4, 5)]
    obj = make_mesh("uv_overlap", verts, faces)

    uv_layer = obj.data.uv_layers.new(name="UVMap")
    for i in range(6):
        uv_layer.data[i].uv = TRIANGLE_UVS[i % 3]

    export_glb(out_dir / "known-bad" / "uv_overlap.glb")


# ---------------------------------------------------------------------------
# Known-bad: materials / PBR (stage1c / stage1d)
# ---------------------------------------------------------------------------

def make_non_pbr_material(out_dir: Path):
    """
    Single triangle with an Emission shader instead of Principled BSDF.
    Triggers: pbr_workflow check.
    """
    clear_scene()
    obj = single_triangle("non_pbr_material")
    set_triangle_uvs(obj)

    mat = bpy.data.materials.new("non_pbr_material_mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    emission = nodes.new('ShaderNodeEmission')
    output = nodes.new('ShaderNodeOutputMaterial')
    links.new(emission.outputs['Emission'], output.inputs['Surface'])
    obj.data.materials.append(mat)

    export_glb(out_dir / "known-bad" / "non_pbr_material.glb")


def make_wrong_colorspace_normal(out_dir: Path):
    """
    Normal map set to sRGB instead of Non-Color.
    Triggers: normal_map colorspace check.
    """
    clear_scene()
    obj = single_triangle("wrong_colorspace_normal")
    set_triangle_uvs(obj)

    img = bpy.data.images.new("fake_normal", width=4, height=4)
    img.colorspace_settings.name = 'sRGB'

    mat = bpy.data.materials.new("wrong_colorspace_normal_mat")
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

    export_glb(out_dir / "known-bad" / "wrong_colorspace_normal.glb")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

GENERATORS = [
    make_non_manifold,
    make_degenerate_faces,
    make_flipped_normals,
    make_loose_geometry,
    make_overbudget_tris,
    make_underbudget_tris,
    make_no_uvs,
    make_uvs_out_of_bounds,
    make_uv_overlap,
    make_non_pbr_material,
    make_wrong_colorspace_normal,
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