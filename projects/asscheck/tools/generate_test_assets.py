"""
tools/generate_test_assets.py
Procedurally generates known-good and known-bad 3D assets for pipeline testing.

Usage:
    blender --background --python tools/generate_test_assets.py -- projects/asscheck/assets

Each generator function documents which pipeline check it is designed to trigger.
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


def add_principled_material(obj, name="material"):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    # Default node tree already has Principled BSDF → Material Output
    obj.data.materials.append(mat)
    return mat


# ---------------------------------------------------------------------------
# Known-good
# ---------------------------------------------------------------------------

def make_clean_mesh(out_dir: Path):
    """
    Simple cube with UVs and a Principled BSDF material.
    Passes all stage1a–1d checks for category env_prop.
    Triangle count: 12 (within env_prop 500–5000 budget with a permissive min).
    NOTE: for budget tests use a subdivided version (see make_within_budget below).
    """
    clear_scene()
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
    obj.name = "clean_prop"

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project()
    bpy.ops.object.mode_set(mode='OBJECT')

    add_principled_material(obj, "clean_mat")
    export_glb(out_dir / "known-good" / "clean_mesh.glb")


def make_within_budget(out_dir: Path):
    """
    Subdivided cube with ~768 triangles — within env_prop budget (500–5000).
    Use this as the baseline for geometry integration tests.
    """
    clear_scene()
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
    obj.name = "within_budget_prop"

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=4)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project()
    bpy.ops.object.mode_set(mode='OBJECT')

    add_principled_material(obj, "budget_mat")
    export_glb(out_dir / "known-good" / "within_budget.glb")


# ---------------------------------------------------------------------------
# Known-bad: geometry (stage1a)
# ---------------------------------------------------------------------------

def make_non_manifold(out_dir: Path):
    """
    Cube with one face deleted → 4 open boundary edges.
    Triggers: stage1a non_manifold check (measured_value == 4).
    """
    clear_scene()
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
    obj.name = "non_manifold_prop"

    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[0]], context='FACES')
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    export_glb(out_dir / "known-bad" / "non_manifold.glb")


def make_degenerate_faces(out_dir: Path):
    """
    Mesh with a zero-area triangle (3 collinear vertices at z=0).
    Triggers: stage1a degenerate_faces check.
    """
    clear_scene()
    mesh = bpy.data.meshes.new("degenerate_mesh")
    obj = bpy.data.objects.new("degenerate_prop", mesh)
    bpy.context.scene.collection.objects.link(obj)

    # A valid cube base via from_pydata
    verts = [
        (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
        (-1, -1,  1), (1, -1,  1), (1, 1,  1), (-1, 1,  1),
        # 3 collinear verts for the degenerate face
        (3, 0, 0), (4, 0, 0), (5, 0, 0),
    ]
    faces = [
        (0,1,2,3), (4,5,6,7), (0,1,5,4),
        (1,2,6,5), (2,3,7,6), (3,0,4,7),
        (8, 9, 10),  # degenerate zero-area triangle
    ]
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    export_glb(out_dir / "known-bad" / "degenerate_faces.glb")


def make_flipped_normals(out_dir: Path):
    """
    Cube with 3 faces having reversed normals.
    Triggers: stage1a normal_consistency check.
    """
    clear_scene()
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
    obj.name = "flipped_normals_prop"

    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.reverse_faces(bm, faces=bm.faces[:3])
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    export_glb(out_dir / "known-bad" / "flipped_normals.glb")


def make_loose_geometry(out_dir: Path):
    """
    Cube with 5 extra unconnected vertices.
    Triggers: stage1a loose_geometry check (measured_value >= 5).
    """
    clear_scene()
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
    obj.name = "loose_geo_prop"

    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for i in range(5):
        bm.verts.new(Vector((5.0 + i * 0.3, 0.0, 0.0)))
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    export_glb(out_dir / "known-bad" / "loose_geometry.glb")


def make_overbudget_tris(out_dir: Path):
    """
    Icosphere subdivided to ~20480 triangles — exceeds env_prop max budget (5000).
    Triggers: stage1a polycount_budget check (FAIL, over max).
    """
    clear_scene()
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5)
    obj = bpy.context.active_object
    obj.name = "overbudget_prop"

    export_glb(out_dir / "known-bad" / "overbudget_tris.glb")


def make_underbudget_tris(out_dir: Path):
    """
    Single triangle — below env_prop min budget (500 triangles).
    Triggers: stage1a polycount_budget check (FAIL, under min).
    """
    clear_scene()
    mesh = bpy.data.meshes.new("underbudget_mesh")
    obj = bpy.data.objects.new("underbudget_prop", mesh)
    bpy.context.scene.collection.objects.link(obj)

    verts = [(0, 0, 0), (1, 0, 0), (0.5, 1, 0)]
    faces = [(0, 1, 2)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    export_glb(out_dir / "known-bad" / "underbudget_tris.glb")


# ---------------------------------------------------------------------------
# Known-bad: UV (stage1b)
# ---------------------------------------------------------------------------

def make_no_uvs(out_dir: Path):
    """
    Cube with all UV layers removed.
    Triggers: stage1b missing_uvs check.
    """
    clear_scene()
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
    obj.name = "no_uvs_prop"

    while obj.data.uv_layers:
        obj.data.uv_layers.remove(obj.data.uv_layers[0])

    export_glb(out_dir / "known-bad" / "no_uvs.glb")


def make_uvs_out_of_bounds(out_dir: Path):
    """
    Cube where all UV coordinates are shifted to U=2.x, V=2.x (outside [0,1]).
    Triggers: stage1b uv_bounds check.
    """
    clear_scene()
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
    obj.name = "oob_uvs_prop"

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project()
    bpy.ops.object.mode_set(mode='OBJECT')

    uv_layer = obj.data.uv_layers.active
    for loop_uv in uv_layer.data:
        loop_uv.uv[0] += 2.0
        loop_uv.uv[1] += 2.0

    export_glb(out_dir / "known-bad" / "uvs_out_of_bounds.glb")


def make_uv_overlap(out_dir: Path):
    """
    Two-face plane where both faces have identical UV coordinates (fully overlapping islands).
    Triggers: stage1b uv_overlap check.
    """
    clear_scene()
    bpy.ops.mesh.primitive_plane_add()
    obj = bpy.context.active_object
    obj.name = "uv_overlap_prop"

    # Subdivide to get two faces
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=1)
    bpy.ops.uv.smart_project()
    bpy.ops.object.mode_set(mode='OBJECT')

    # Force all UV coords to the same small square → total overlap
    uv_layer = obj.data.uv_layers.active
    for loop_uv in uv_layer.data:
        loop_uv.uv[0] = 0.1
        loop_uv.uv[1] = 0.1

    export_glb(out_dir / "known-bad" / "uv_overlap.glb")


# ---------------------------------------------------------------------------
# Known-bad: materials / PBR (stage1c / stage1d)
# ---------------------------------------------------------------------------

def make_non_pbr_material(out_dir: Path):
    """
    Cube with an Emission shader instead of Principled BSDF.
    Triggers: stage1d pbr_workflow check.
    """
    clear_scene()
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
    obj.name = "non_pbr_prop"

    mat = bpy.data.materials.new("emission_mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value = (1.0, 0.5, 0.0, 1.0)
    output = nodes.new('ShaderNodeOutputMaterial')
    links.new(emission.outputs['Emission'], output.inputs['Surface'])

    obj.data.materials.append(mat)
    export_glb(out_dir / "known-bad" / "non_pbr_material.glb")


def make_wrong_colorspace_normal(out_dir: Path):
    """
    Cube with a normal map node connected but colorspace set to sRGB (should be Non-Color).
    Triggers: stage1d normal_map colorspace check.
    """
    clear_scene()
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
    obj.name = "wrong_colorspace_prop"

    # Create a flat blue image to simulate a normal map
    img = bpy.data.images.new("fake_normal", width=64, height=64)
    img.colorspace_settings.name = 'sRGB'  # wrong — should be Non-Color

    mat = bpy.data.materials.new("wrong_colorspace_mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = nodes.get('Principled BSDF')
    tex_node = nodes.new('ShaderNodeTexImage')
    tex_node.image = img
    normal_map = nodes.new('ShaderNodeNormalMap')

    links.new(tex_node.outputs['Color'], normal_map.inputs['Color'])
    links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])

    obj.data.materials.append(mat)
    export_glb(out_dir / "known-bad" / "wrong_colorspace_normal.glb")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

GENERATORS = [
    # known-good
    make_clean_mesh,
    make_within_budget,
    # geometry
    make_non_manifold,
    make_degenerate_faces,
    make_flipped_normals,
    make_loose_geometry,
    make_overbudget_tris,
    make_underbudget_tris,
    # UV
    make_no_uvs,
    make_uvs_out_of_bounds,
    make_uv_overlap,
    # material / PBR
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
            print(f"  FAILED: {exc}")
            failed.append((gen.__name__, exc))

    print(f"\n[generate] done — {len(GENERATORS) - len(failed)}/{len(GENERATORS)} succeeded")
    if failed:
        for name, exc in failed:
            print(f"  FAILED: {name}: {exc}")
        sys.exit(1)
