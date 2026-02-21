"""Unit tests for pipeline/stage5/ssim_diff.py and pipeline/stage5/summary.py.

All tests use mocks or temp files — no Blender, scikit-image, or Pillow
installation required.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from pipeline.schema import (
    AssetMetadata,
    OverallStatus,
    QaReport,
    Severity,
)
from pipeline.stage5.ssim_diff import SSIMResult, compare_renders
from pipeline.stage5.summary import write_review_package


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(asset_id: str = "test_asset") -> QaReport:
    return QaReport(
        metadata=AssetMetadata(
            asset_id=asset_id,
            source="test.gltf",
            category="prop",
            submission_date="2026-01-01",
            processing_timestamp="2026-01-01T00:00:00",
            submitter="tester",
        ),
        overall_status=OverallStatus.NEEDS_REVIEW,
    )


def _write_dummy_file(path: str) -> None:
    """Write a small placeholder file (valid enough to be 'non-zero size')."""
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)


# ---------------------------------------------------------------------------
# Tests — SSIMResult flagging via compare_renders
# ---------------------------------------------------------------------------

class TestSSIMFlagging:

    def test_high_score_not_flagged(self, tmp_path: Path) -> None:
        """SSIM score ≥ 0.85 must set flagged=False."""
        render = str(tmp_path / "test_asset_turntable_000.png")
        ref_dir = str(tmp_path / "ref")
        os.makedirs(ref_dir)
        _write_dummy_file(render)
        _write_dummy_file(os.path.join(ref_dir, "test_asset_turntable_000.png"))

        results = compare_renders(
            [render],
            ref_dir,
            _compute_ssim=lambda _a, _b: (0.92, None),
        )

        assert len(results) == 1
        assert results[0].score == pytest.approx(0.92)
        assert not results[0].flagged

    def test_boundary_score_085_not_flagged(self, tmp_path: Path) -> None:
        """SSIM score exactly 0.85 must NOT be flagged (threshold is < 0.85)."""
        render = str(tmp_path / "asset_turntable_090.png")
        ref_dir = str(tmp_path / "ref")
        os.makedirs(ref_dir)
        _write_dummy_file(render)
        _write_dummy_file(os.path.join(ref_dir, "asset_turntable_090.png"))

        results = compare_renders(
            [render],
            ref_dir,
            _compute_ssim=lambda _a, _b: (0.85, None),
        )

        assert not results[0].flagged

    def test_low_score_flagged(self, tmp_path: Path) -> None:
        """SSIM score 0.72 must set flagged=True."""
        render = str(tmp_path / "asset_turntable_045.png")
        ref_dir = str(tmp_path / "ref")
        os.makedirs(ref_dir)
        _write_dummy_file(render)
        _write_dummy_file(os.path.join(ref_dir, "asset_turntable_045.png"))

        results = compare_renders(
            [render],
            ref_dir,
            _compute_ssim=lambda _a, _b: (0.72, None),
        )

        assert len(results) == 1
        assert results[0].score == pytest.approx(0.72)
        assert results[0].flagged

    def test_no_reference_score_is_one_not_flagged(self, tmp_path: Path) -> None:
        """When no golden reference exists, score must be 1.0 and flagged=False."""
        render = str(tmp_path / "test_asset_turntable_000.png")
        _write_dummy_file(render)
        ref_dir = str(tmp_path / "empty_ref")
        os.makedirs(ref_dir)

        # No _compute_ssim mock needed — the 'no reference' path doesn't call it
        results = compare_renders([render], ref_dir)

        assert len(results) == 1
        assert results[0].score == pytest.approx(1.0)
        assert not results[0].flagged

    def test_angle_parsed_from_filename(self, tmp_path: Path) -> None:
        """The angle field must reflect the value encoded in the filename."""
        render = str(tmp_path / "lamp_turntable_135.png")
        ref_dir = str(tmp_path / "ref")
        os.makedirs(ref_dir)
        _write_dummy_file(render)
        _write_dummy_file(os.path.join(ref_dir, "lamp_turntable_135.png"))

        results = compare_renders(
            [render],
            ref_dir,
            _compute_ssim=lambda _a, _b: (0.90, None),
        )

        assert results[0].angle == 135

    def test_diff_image_path_none_when_not_flagged(self, tmp_path: Path) -> None:
        """diff_image_path must be None when the render is not flagged."""
        render = str(tmp_path / "x_turntable_000.png")
        ref_dir = str(tmp_path / "ref")
        os.makedirs(ref_dir)
        _write_dummy_file(render)
        _write_dummy_file(os.path.join(ref_dir, "x_turntable_000.png"))

        results = compare_renders(
            [render],
            ref_dir,
            _compute_ssim=lambda _a, _b: (0.95, None),
        )

        assert results[0].diff_image_path is None

    def test_multiple_renders_processed(self, tmp_path: Path) -> None:
        """compare_renders must return one SSIMResult per valid render path."""
        ref_dir = str(tmp_path / "ref")
        os.makedirs(ref_dir)
        renders = []
        for angle in (0, 45, 90):
            fname = f"item_turntable_{angle:03d}.png"
            p = str(tmp_path / fname)
            _write_dummy_file(p)
            _write_dummy_file(os.path.join(ref_dir, fname))
            renders.append(p)

        results = compare_renders(
            renders,
            ref_dir,
            _compute_ssim=lambda _a, _b: (0.91, None),
        )

        assert len(results) == 3


# ---------------------------------------------------------------------------
# Tests — write_review_package
# ---------------------------------------------------------------------------

class TestWriteReviewPackage:

    def test_creates_review_summary_html(self, tmp_path: Path) -> None:
        """write_review_package must create review_summary.html in the asset dir."""
        report = _make_report("my_asset")
        render1 = str(tmp_path / "my_asset_turntable_000.png")
        scale_img = str(tmp_path / "my_asset_scale_reference.png")
        _write_dummy_file(render1)
        _write_dummy_file(scale_img)

        write_review_package(
            report,
            [render1],
            [],
            scale_img,
            str(tmp_path),
        )

        html_path = tmp_path / "my_asset" / "review_summary.html"
        assert html_path.exists(), "review_summary.html must be created"

        content = html_path.read_text(encoding="utf-8")
        assert "my_asset" in content, "HTML must mention the asset_id"
        assert "<img" in content, "HTML must contain at least one <img> tag"

    def test_html_contains_title_with_asset_id(self, tmp_path: Path) -> None:
        """The HTML <title> must contain the asset_id."""
        report = _make_report("lamp_001")
        write_review_package(report, [], [], "", str(tmp_path))

        content = (tmp_path / "lamp_001" / "review_summary.html").read_text()
        assert "lamp_001" in content

    def test_output_dir_created_if_missing(self, tmp_path: Path) -> None:
        """write_review_package must create the asset sub-directory."""
        report = _make_report("newasset")
        nested = tmp_path / "deep" / "output"
        write_review_package(report, [], [], "", str(nested))
        assert (nested / "newasset" / "review_summary.html").exists()

    def test_render_images_copied_to_package_dir(self, tmp_path: Path) -> None:
        """Render images must be copied into the asset output directory."""
        report = _make_report("prop_x")
        render = str(tmp_path / "prop_x_turntable_000.png")
        _write_dummy_file(render)

        out = tmp_path / "out"
        write_review_package(report, [render], [], "", str(out))

        copied = out / "prop_x" / "prop_x_turntable_000.png"
        assert copied.exists()

    def test_scale_image_copied_to_package_dir(self, tmp_path: Path) -> None:
        """The scale reference image must be copied into the asset output directory."""
        report = _make_report("door_01")
        scale_img = str(tmp_path / "door_01_scale_reference.png")
        _write_dummy_file(scale_img)

        out = tmp_path / "out"
        write_review_package(report, [], [], scale_img, str(out))

        assert (out / "door_01" / "door_01_scale_reference.png").exists()

    # --- Scale verification ReviewFlag ---

    def test_scale_verification_adds_review_flag(self, tmp_path: Path) -> None:
        """write_review_package must add a ReviewFlag with severity INFO."""
        report = _make_report("asset_xyz")

        write_review_package(report, [], [], "", str(tmp_path))

        all_flags = [f for s in report.stages for f in s.review_flags]
        info_flags = [f for f in all_flags if f.severity == Severity.INFO]
        assert len(info_flags) >= 1, "At least one INFO flag must be added"
        assert any(
            "scale" in f.description.lower() for f in info_flags
        ), "The INFO flag must mention scale"

    def test_scale_flag_always_added_regardless_of_image(self, tmp_path: Path) -> None:
        """The scale ReviewFlag must be added even when no scale image exists."""
        report = _make_report("no_scale_img")
        # Pass an empty string — image does not exist
        write_review_package(report, [], [], "", str(tmp_path))

        stage5 = next(
            (s for s in report.stages if s.name == "visual_verification"), None
        )
        assert stage5 is not None
        assert any(
            f.severity == Severity.INFO for f in stage5.review_flags
        )

    def test_ssim_flagged_renders_included_in_html(self, tmp_path: Path) -> None:
        """Flagged SSIM renders with diff images must appear in the HTML."""
        report = _make_report("box")
        diff_img = str(tmp_path / "box_turntable_000_diff.png")
        _write_dummy_file(diff_img)

        ssim_result = SSIMResult(
            angle=0, score=0.72, diff_image_path=diff_img, flagged=True
        )

        out = tmp_path / "out"
        write_review_package(report, [], [ssim_result], "", str(out))

        content = (out / "box" / "review_summary.html").read_text()
        assert "0.7200" in content or "0.72" in content, \
            "SSIM score must appear in HTML"

    def test_review_flags_from_existing_stages_appear_in_html(
        self, tmp_path: Path
    ) -> None:
        """Flags from earlier pipeline stages must be listed in the HTML."""
        from pipeline.schema import ReviewFlag, StageResult, StageStatus

        report = _make_report("flagged_asset")
        report.stages.append(StageResult(
            name="geometry",
            status=StageStatus.FAIL,
            review_flags=[
                ReviewFlag(
                    issue="geometry:non_manifold",
                    severity=Severity.ERROR,
                    description="Non-manifold geometry detected",
                )
            ],
        ))

        write_review_package(report, [], [], "", str(tmp_path))

        content = (tmp_path / "flagged_asset" / "review_summary.html").read_text()
        assert "non_manifold" in content
