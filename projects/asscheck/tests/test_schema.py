import dataclasses
import json

from pipeline.report_builder import ReportBuilder
from pipeline.schema import (
    CheckResult,
    ExportInfo,
    FixEntry,
    PerformanceEstimates,
    QaReport,
    ReviewFlag,
    StageResult,
    Status,
)


def _make_builder():
    return ReportBuilder(
        asset_id="asset-001",
        source="test.glb",
        category="prop",
        submitter="test_user",
        submitted="2026-02-19",
        processed="2026-02-19T12:00:00Z",
    )


def _make_full_report() -> QaReport:
    check = CheckResult(
        name="polycount",
        status=Status.PASS,
        value=1000,
        threshold=5000,
        message="OK",
    )
    fix = FixEntry(
        action="merge_vertices",
        target="Mesh.001",
        before=100,
        after=95,
    )
    flag = ReviewFlag(
        issue="unusual_topology",
        severity=Status.WARNING,
        description="Mesh has unusual topology",
    )
    stage = StageResult(
        name="geometry",
        status=Status.PASS,
        checks=[check],
        fixes=[fix],
        flags=[flag],
    )
    builder = _make_builder()
    builder.add_stage(stage)
    builder.set_performance(PerformanceEstimates(triangles=1000, draw_calls=2, vram_mb=4.5, bones=0))
    builder.set_export(ExportInfo(format="glTF", path="/output/asset.glb", axis="Y_UP", scale=1.0))
    return builder.finalize()


def test_finalize_fail():
    builder = _make_builder()
    builder.add_stage(StageResult(name="geometry", status=Status.FAIL))
    report = builder.finalize()
    assert report.status == Status.FAIL


def test_finalize_needs_review():
    builder = _make_builder()
    stage = StageResult(
        name="geometry",
        status=Status.PASS,
        flags=[ReviewFlag(issue="weird", severity=Status.WARNING, description="Something odd")],
    )
    builder.add_stage(stage)
    report = builder.finalize()
    assert report.status == Status.NEEDS_REVIEW


def test_finalize_pass_with_fixes():
    builder = _make_builder()
    stage = StageResult(
        name="geometry",
        status=Status.PASS,
        fixes=[FixEntry(action="merge", target="mesh", before=10, after=8)],
    )
    builder.add_stage(stage)
    report = builder.finalize()
    assert report.status == Status.PASS_WITH_FIXES


def test_finalize_pass():
    builder = _make_builder()
    builder.add_stage(StageResult(name="geometry", status=Status.PASS))
    report = builder.finalize()
    assert report.status == Status.PASS


def test_report_field_names():
    report = _make_full_report()
    d = dataclasses.asdict(report)

    assert set(d.keys()) == {
        "asset_id", "source", "category", "submitter", "submitted", "processed",
        "status", "stages", "performance", "export",
    }

    stage = d["stages"][0]
    assert set(stage.keys()) == {"name", "status", "checks", "fixes", "flags"}

    check = stage["checks"][0]
    assert set(check.keys()) == {"name", "status", "value", "threshold", "message"}

    fix = stage["fixes"][0]
    assert set(fix.keys()) == {"action", "target", "before", "after"}

    flag = stage["flags"][0]
    assert set(flag.keys()) == {"issue", "severity", "description"}

    perf = d["performance"]
    assert set(perf.keys()) == {"triangles", "draw_calls", "vram_mb", "bones"}

    exp = d["export"]
    assert set(exp.keys()) == {"format", "path", "axis", "scale"}


def test_json_serializable():
    report = _make_full_report()
    serialized = json.dumps(dataclasses.asdict(report))
    restored = json.loads(serialized)
    assert restored["asset_id"] == "asset-001"
    assert restored["stages"][0]["checks"][0]["value"] == 1000
    assert restored["performance"]["triangles"] == 1000
