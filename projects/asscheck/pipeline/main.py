"""Pipeline orchestrator.

Runs the full QA pipeline in sequence:
  0. intake      — filesystem validation, asset ID assignment
  1. geometry    — polycount, manifold, normals, degenerate faces, loose geo
  1. uv          — UV presence, bounds, overlap, texel density
  1. texture     — resolution, channel depth, colorspace
  1. pbr         — PBR workflow, albedo/metalness/roughness ranges, normal maps
  1. armature    — skeleton structure, bone count, vertex weights (skippable)
  1. scene       — naming, hierarchy, LOD presence, performance estimates
  2. remediation — auto-fix geometry issues; flag what can't be auto-fixed
  3. export      — export + sidecar manifest + route to Unity/review/quarantine
  5. visual      — turntable renders + SSIM diff + HTML review package

Usage from Blender headless:
    blender --background --python pipeline/main.py -- <asset_path> [options]

The bpy-backed context implementations live in blender_tests/tests.py.
Import them from there when running inside Blender, or provide your own
implementations of the ABC interfaces defined in each pipeline module.
"""
from __future__ import annotations

from pipeline.armature import ArmatureBlenderContext, ArmatureConfig, check_armature
from pipeline.export import ExportBlenderContext, ExportConfig, run_export
from pipeline.geometry import BlenderContext as GeomContext, GeometryConfig, check_geometry
from pipeline.intake import IntakeConfig, run_intake
from pipeline.pbr import PBRBlenderContext, PBRConfig, check_pbr
from pipeline.remediate import RemediationBlenderContext, RemediationConfig, run_remediation
from pipeline.report_builder import ReportBuilder
from pipeline.scene import SceneBlenderContext, SceneConfig, check_scene
from pipeline.schema import QaReport, StageResult
from pipeline.ssim_diff import SSIMResult, compare_renders
from pipeline.summary import write_review_package
from pipeline.texture import TextureBlenderContext, TextureConfig, check_textures
from pipeline.turntable import TurntableConfig, render_turntable
from pipeline.uv import UVBlenderContext, UVConfig, check_uvs


def run_checks(
    geom_ctx: GeomContext,
    uv_ctx: UVBlenderContext,
    tex_ctx: TextureBlenderContext,
    pbr_ctx: PBRBlenderContext,
    arm_ctx: ArmatureBlenderContext,
    scene_ctx: SceneBlenderContext,
    rem_ctx: RemediationBlenderContext,
    geom_config: GeometryConfig,
    uv_config: UVConfig,
    tex_config: TextureConfig,
    pbr_config: PBRConfig,
    arm_config: ArmatureConfig,
    scene_config: SceneConfig,
    rem_config: RemediationConfig,
) -> tuple[list[StageResult], list[StageResult]]:
    """Run stage 1 checks and stage 2 remediation.

    Returns
    -------
    stage1_results:
        Results from all stage 1 checks.
    stage2_results:
        Results from stage 2 remediation (fixes + review flags).
    """
    geom_result = check_geometry(geom_ctx, geom_config)
    uv_result = check_uvs(uv_ctx, uv_config)
    tex_result = check_textures(tex_ctx, tex_config)
    pbr_result = check_pbr(pbr_ctx, pbr_config)
    arm_result = check_armature(arm_ctx, arm_config)
    scene_result, _perf = check_scene(scene_ctx, scene_config)

    stage1_results = [geom_result, uv_result, tex_result, pbr_result, arm_result, scene_result]
    rem_result = run_remediation(rem_ctx, stage1_results, rem_config)

    return stage1_results, [rem_result]
