from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class OverallStatus(str, Enum):
    PASS = "PASS"
    PASS_WITH_FIXES = "PASS_WITH_FIXES"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAIL = "FAIL"


class StageStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: CheckStatus
    measured_value: Any
    threshold: Any
    message: str


@dataclass(frozen=True)
class FixEntry:
    action: str
    target: str
    before_value: Any
    after_value: Any


@dataclass(frozen=True)
class ReviewFlag:
    issue: str
    severity: Severity
    description: str


@dataclass
class StageResult:
    name: str
    status: StageStatus
    checks: list[CheckResult] = field(default_factory=list)
    fixes: list[FixEntry] = field(default_factory=list)
    review_flags: list[ReviewFlag] = field(default_factory=list)


@dataclass(frozen=True)
class PerformanceEstimates:
    triangle_count: int
    draw_call_estimate: int
    vram_estimate_mb: float
    bone_count: int


@dataclass(frozen=True)
class ExportInfo:
    format: str
    path: str
    axis_convention: str
    scale: float


@dataclass(frozen=True)
class AssetMetadata:
    asset_id: str
    source: str
    category: str
    submission_date: str
    processing_timestamp: str
    submitter: str


@dataclass
class QaReport:
    metadata: AssetMetadata
    overall_status: OverallStatus
    stages: list[StageResult] = field(default_factory=list)
    performance: Optional[PerformanceEstimates] = None
    export: Optional[ExportInfo] = None

    def to_dict(self) -> dict:
        def check_to_dict(c: CheckResult) -> dict:
            return {
                "name": c.name,
                "status": c.status.value,
                "measured_value": c.measured_value,
                "threshold": c.threshold,
                "message": c.message,
            }

        def fix_to_dict(f: FixEntry) -> dict:
            return {
                "action": f.action,
                "target": f.target,
                "before_value": f.before_value,
                "after_value": f.after_value,
            }

        def flag_to_dict(r: ReviewFlag) -> dict:
            return {
                "issue": r.issue,
                "severity": r.severity.value,
                "description": r.description,
            }

        def stage_to_dict(s: StageResult) -> dict:
            return {
                "name": s.name,
                "status": s.status.value,
                "checks": [check_to_dict(c) for c in s.checks],
                "fixes": [fix_to_dict(f) for f in s.fixes],
                "review_flags": [flag_to_dict(r) for r in s.review_flags],
            }

        return {
            "metadata": {
                "asset_id": self.metadata.asset_id,
                "source": self.metadata.source,
                "category": self.metadata.category,
                "submission_date": self.metadata.submission_date,
                "processing_timestamp": self.metadata.processing_timestamp,
                "submitter": self.metadata.submitter,
            },
            "overall_status": self.overall_status.value,
            "stages": [stage_to_dict(s) for s in self.stages],
            "performance": {
                "triangle_count": self.performance.triangle_count,
                "draw_call_estimate": self.performance.draw_call_estimate,
                "vram_estimate_mb": self.performance.vram_estimate_mb,
                "bone_count": self.performance.bone_count,
            } if self.performance is not None else None,
            "export": {
                "format": self.export.format,
                "path": self.export.path,
                "axis_convention": self.export.axis_convention,
                "scale": self.export.scale,
            } if self.export is not None else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> QaReport:
        meta = d["metadata"]
        metadata = AssetMetadata(
            asset_id=meta["asset_id"],
            source=meta["source"],
            category=meta["category"],
            submission_date=meta["submission_date"],
            processing_timestamp=meta["processing_timestamp"],
            submitter=meta["submitter"],
        )

        stages = []
        for s in d.get("stages", []):
            checks = [
                CheckResult(
                    name=c["name"],
                    status=CheckStatus(c["status"]),
                    measured_value=c["measured_value"],
                    threshold=c["threshold"],
                    message=c["message"],
                )
                for c in s.get("checks", [])
            ]
            fixes = [
                FixEntry(
                    action=f["action"],
                    target=f["target"],
                    before_value=f["before_value"],
                    after_value=f["after_value"],
                )
                for f in s.get("fixes", [])
            ]
            flags = [
                ReviewFlag(
                    issue=r["issue"],
                    severity=Severity(r["severity"]),
                    description=r["description"],
                )
                for r in s.get("review_flags", [])
            ]
            stages.append(StageResult(
                name=s["name"],
                status=StageStatus(s["status"]),
                checks=checks,
                fixes=fixes,
                review_flags=flags,
            ))

        performance = None
        if d.get("performance") is not None:
            p = d["performance"]
            performance = PerformanceEstimates(
                triangle_count=p["triangle_count"],
                draw_call_estimate=p["draw_call_estimate"],
                vram_estimate_mb=p["vram_estimate_mb"],
                bone_count=p["bone_count"],
            )

        export = None
        if d.get("export") is not None:
            e = d["export"]
            export = ExportInfo(
                format=e["format"],
                path=e["path"],
                axis_convention=e["axis_convention"],
                scale=e["scale"],
            )

        return cls(
            metadata=metadata,
            overall_status=OverallStatus(d["overall_status"]),
            stages=stages,
            performance=performance,
            export=export,
        )
