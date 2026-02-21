from pipeline.schema import (
    AssetMetadata,
    CheckResult,
    CheckStatus,
    ExportInfo,
    FixEntry,
    OverallStatus,
    PerformanceEstimates,
    QaReport,
    ReviewFlag,
    Severity,
    StageResult,
    StageStatus,
)
from pipeline.report_builder import ReportBuilder


def _make_metadata() -> AssetMetadata:
    return AssetMetadata(
        asset_id="asset-001",
        source="test.glb",
        category="prop",
        submission_date="2026-02-19",
        processing_timestamp="2026-02-19T12:00:00Z",
        submitter="test_user",
    )


def _make_full_report() -> QaReport:
    check = CheckResult(
        name="polycount",
        status=CheckStatus.PASS,
        measured_value=1000,
        threshold=5000,
        message="OK",
    )
    fix = FixEntry(
        action="merge_vertices",
        target="Mesh.001",
        before_value=100,
        after_value=95,
    )
    flag = ReviewFlag(
        issue="unusual_topology",
        severity=Severity.WARNING,
        description="Mesh has unusual topology",
    )
    stage = StageResult(
        name="geometry",
        status=StageStatus.PASS,
        checks=[check],
        fixes=[fix],
        review_flags=[flag],
    )
    perf = PerformanceEstimates(
        triangle_count=1000,
        draw_call_estimate=2,
        vram_estimate_mb=4.5,
        bone_count=0,
    )
    exp = ExportInfo(
        format="glTF",
        path="/output/asset.glb",
        axis_convention="Y_UP",
        scale=1.0,
    )
    return QaReport(
        metadata=_make_metadata(),
        overall_status=OverallStatus.PASS_WITH_FIXES,
        stages=[stage],
        performance=perf,
        export=exp,
    )


def test_roundtrip():
    report = _make_full_report()
    restored = QaReport.from_dict(report.to_dict())
    assert restored == report


def test_finalize_fail():
    builder = ReportBuilder(_make_metadata())
    builder.add_stage(StageResult(name="geometry", status=StageStatus.FAIL))
    report = builder.finalize()
    assert report.overall_status == OverallStatus.FAIL


def test_finalize_needs_review():
    builder = ReportBuilder(_make_metadata())
    flag = ReviewFlag(issue="weird", severity=Severity.WARNING, description="Something odd")
    stage = StageResult(
        name="geometry",
        status=StageStatus.PASS,
        review_flags=[flag],
    )
    builder.add_stage(stage)
    report = builder.finalize()
    assert report.overall_status == OverallStatus.NEEDS_REVIEW


def test_finalize_pass_with_fixes():
    builder = ReportBuilder(_make_metadata())
    fix = FixEntry(action="merge", target="mesh", before_value=10, after_value=8)
    stage = StageResult(
        name="geometry",
        status=StageStatus.PASS,
        fixes=[fix],
    )
    builder.add_stage(stage)
    report = builder.finalize()
    assert report.overall_status == OverallStatus.PASS_WITH_FIXES


def test_finalize_pass():
    builder = ReportBuilder(_make_metadata())
    builder.add_stage(StageResult(name="geometry", status=StageStatus.PASS))
    report = builder.finalize()
    assert report.overall_status == OverallStatus.PASS


def test_serialized_field_names():
    d = _make_full_report().to_dict()

    assert set(d.keys()) == {"metadata", "overall_status", "stages", "performance", "export"}

    meta = d["metadata"]
    assert set(meta.keys()) == {
        "asset_id", "source", "category", "submission_date",
        "processing_timestamp", "submitter",
    }

    stage = d["stages"][0]
    assert set(stage.keys()) == {"name", "status", "checks", "fixes", "review_flags"}

    check = stage["checks"][0]
    assert set(check.keys()) == {"name", "status", "measured_value", "threshold", "message"}

    fix_d = stage["fixes"][0]
    assert set(fix_d.keys()) == {"action", "target", "before_value", "after_value"}

    flag_d = stage["review_flags"][0]
    assert set(flag_d.keys()) == {"issue", "severity", "description"}

    perf = d["performance"]
    assert set(perf.keys()) == {
        "triangle_count", "draw_call_estimate", "vram_estimate_mb", "bone_count",
    }

    exp = d["export"]
    assert set(exp.keys()) == {"format", "path", "axis_convention", "scale"}
