from __future__ import annotations

from pipeline.schema import (
    AssetMetadata,
    ExportInfo,
    OverallStatus,
    PerformanceEstimates,
    QaReport,
    StageResult,
    StageStatus,
)


class ReportBuilder:
    def __init__(self, metadata: AssetMetadata):
        self._metadata = metadata
        self._stages: list[StageResult] = []
        self._performance: PerformanceEstimates | None = None
        self._export: ExportInfo | None = None

    def add_stage(self, stage_result: StageResult):
        self._stages.append(stage_result)

    def set_performance(self, p: PerformanceEstimates):
        self._performance = p

    def set_export(self, e: ExportInfo):
        self._export = e

    def finalize(self) -> QaReport:
        return QaReport(
            metadata=self._metadata,
            overall_status=self._compute_status(),
            stages=list(self._stages),
            performance=self._performance,
            export=self._export,
        )

    def _compute_status(self) -> OverallStatus:
        for stage in self._stages:
            if stage.status == StageStatus.FAIL:
                return OverallStatus.FAIL

        for stage in self._stages:
            if stage.review_flags:
                return OverallStatus.NEEDS_REVIEW

        for stage in self._stages:
            if stage.fixes:
                return OverallStatus.PASS_WITH_FIXES

        return OverallStatus.PASS
