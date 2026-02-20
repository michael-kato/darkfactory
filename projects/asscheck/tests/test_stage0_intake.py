"""Tests for pipeline/stage0/intake.py — Stage 0: Intake & Triage."""
from pathlib import Path

import pytest

from pipeline.schema import CheckStatus, StageStatus
from pipeline.stage0.intake import IntakeConfig, run_intake

SAMPLE_GLTF = (
    Path(__file__).parent.parent
    / "asscheck_uproj/Assets/Models/street_lamp_01_quant.gltf"
)

_DEFAULT = dict(
    source="test",
    submitter="tester",
    category="env_prop",
    max_size_bytes={"env_prop": 100 * 1024 * 1024, "*": 50 * 1024 * 1024},
    hard_max_bytes=500 * 1024 * 1024,
)


def _config(file_path, **overrides) -> IntakeConfig:
    return IntakeConfig(file_path=str(file_path), **{**_DEFAULT, **overrides})


# ---------------------------------------------------------------------------
# Accepted formats
# ---------------------------------------------------------------------------

def test_valid_gltf_passes():
    report = run_intake(_config(SAMPLE_GLTF))
    stage = report.stages[0]
    assert stage.status == StageStatus.PASS
    assert report.metadata.asset_id != ""


def test_valid_glb_passes(tmp_path):
    f = tmp_path / "model.glb"
    f.write_bytes(b"fake glb content")
    assert run_intake(_config(f)).stages[0].status == StageStatus.PASS


def test_valid_fbx_passes(tmp_path):
    f = tmp_path / "model.fbx"
    f.write_bytes(b"fake fbx content")
    assert run_intake(_config(f)).stages[0].status == StageStatus.PASS


def test_valid_obj_passes(tmp_path):
    f = tmp_path / "model.obj"
    f.write_bytes(b"v 0 0 0\n")
    assert run_intake(_config(f)).stages[0].status == StageStatus.PASS


# ---------------------------------------------------------------------------
# Rejected formats
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
# File size checks
# ---------------------------------------------------------------------------

def test_exceeds_hard_max_fails(tmp_path):
    f = tmp_path / "model.gltf"
    f.write_bytes(b"x" * 1000)
    report = run_intake(_config(f, hard_max_bytes=100))
    assert report.stages[0].status == StageStatus.FAIL


def test_exceeds_category_limit_warns_but_passes(tmp_path):
    f = tmp_path / "model.gltf"
    f.write_bytes(b"x" * 1000)
    config = _config(
        f,
        max_size_bytes={"env_prop": 500, "*": 500},
        hard_max_bytes=10_000,
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
    config = _config(SAMPLE_GLTF)
    report1 = run_intake(config)
    report2 = run_intake(config)
    assert report1.metadata.asset_id != report2.metadata.asset_id


# ---------------------------------------------------------------------------
# Sample asset exists and passes
# ---------------------------------------------------------------------------

def test_sample_asset_exists_and_passes():
    assert SAMPLE_GLTF.exists(), f"Sample asset missing: {SAMPLE_GLTF}"
    report = run_intake(_config(SAMPLE_GLTF))
    stage = report.stages[0]
    assert stage.status == StageStatus.PASS
    assert report.metadata.asset_id  # non-empty string
