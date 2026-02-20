"""Tests for pipeline/stage0/intake.py — Stage 0: Intake & Triage."""
from pathlib import Path

import pytest

from pipeline.schema import CheckStatus, StageStatus
from pipeline.stage0.intake import IntakeConfig, run_intake

ASSETS_DIR = Path(__file__).parent.parent / "assets"

_DEFAULT = dict(
    source="test",
    submitter="tester",
    category="env_prop",
    max_size_bytes={"env_prop": 500 * 1024 * 1024, "*": 500 * 1024 * 1024},
    hard_max_bytes=1024 * 1024 * 1024,
)


def _config(file_path, **overrides) -> IntakeConfig:
    return IntakeConfig(file_path=str(file_path), **{**_DEFAULT, **overrides})


def _skip_if_no_assets():
    if not ASSETS_DIR.exists():
        pytest.skip("assets/ directory not present")


# ---------------------------------------------------------------------------
# Accepted formats — real assets
# ---------------------------------------------------------------------------

def test_valid_gltf_passes():
    _skip_if_no_assets()
    report = run_intake(_config(ASSETS_DIR / "street_lamp_01.gltf"))
    stage = report.stages[0]
    assert stage.status == StageStatus.PASS
    assert report.metadata.asset_id != ""


def test_valid_glb_passes():
    _skip_if_no_assets()
    report = run_intake(_config(ASSETS_DIR / "large_iron_gate_left_door.glb"))
    assert report.stages[0].status == StageStatus.PASS


def test_valid_fbx_passes():
    _skip_if_no_assets()
    report = run_intake(_config(ASSETS_DIR / "tree_small_02_branches.fbx"))
    assert report.stages[0].status == StageStatus.PASS


def test_valid_obj_passes():
    _skip_if_no_assets()
    report = run_intake(_config(ASSETS_DIR / "double_door_standard_01.obj"))
    assert report.stages[0].status == StageStatus.PASS


# ---------------------------------------------------------------------------
# Rejected formats — tmp_path stubs
# ---------------------------------------------------------------------------

def test_blend_file_fails(tmp_path):
    f = tmp_path / "model.blend"
    f.write_bytes(b"BLENDER_v300")
    assert run_intake(_config(f)).stages[0].status == StageStatus.FAIL


def test_zip_file_fails(tmp_path):
    f = tmp_path / "model.zip"
    f.write_bytes(b"PK\x03\x04")
    assert run_intake(_config(f)).stages[0].status == StageStatus.FAIL


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------

def test_nonexistent_path_fails():
    report = run_intake(_config("/nonexistent/does_not_exist.gltf"))
    assert report.stages[0].status == StageStatus.FAIL


# ---------------------------------------------------------------------------
# File size checks — real FBX asset (~114 MB)
# ---------------------------------------------------------------------------

def test_exceeds_hard_max_fails():
    _skip_if_no_assets()
    fbx = ASSETS_DIR / "tree_small_02_branches.fbx"
    report = run_intake(_config(fbx, hard_max_bytes=50 * 1024 * 1024))
    assert report.stages[0].status == StageStatus.FAIL


def test_exceeds_category_limit_warns_but_passes():
    _skip_if_no_assets()
    fbx = ASSETS_DIR / "tree_small_02_branches.fbx"
    config = _config(
        fbx,
        max_size_bytes={"*": 50 * 1024 * 1024},
        hard_max_bytes=200 * 1024 * 1024,
    )
    report = run_intake(config)
    stage = report.stages[0]
    assert stage.status == StageStatus.PASS
    size_check = next(c for c in stage.checks if c.name == "file_size")
    assert size_check.status == CheckStatus.WARNING


# ---------------------------------------------------------------------------
# Asset ID uniqueness
# ---------------------------------------------------------------------------

def test_two_runs_produce_different_asset_ids():
    _skip_if_no_assets()
    config = _config(ASSETS_DIR / "street_lamp_01.gltf")
    report1 = run_intake(config)
    report2 = run_intake(config)
    assert report1.metadata.asset_id != report2.metadata.asset_id
