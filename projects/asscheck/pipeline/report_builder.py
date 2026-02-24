from __future__ import annotations

from pipeline.schema import QaReport, Status, StageResult


class ReportBuilder:
    def __init__(self, asset_id, source, category, submitter, submitted, processed):
        self._asset_id = asset_id
        self._source = source
        self._category = category
        self._submitter = submitter
        self._submitted = submitted
        self._processed = processed
        self._stages: list[StageResult] = []
        self._performance = None
        self._export = None

    @property
    def asset_id(self):
        return self._asset_id

    @property
    def category(self):
        return self._category

    def add_stage(self, stage: StageResult):
        self._stages.append(stage)

    def set_performance(self, p):
        self._performance = p

    def set_export(self, e):
        self._export = e

    def finalize(self) -> QaReport:
        return QaReport(
            asset_id=self._asset_id,
            source=self._source,
            category=self._category,
            submitter=self._submitter,
            submitted=self._submitted,
            processed=self._processed,
            status=self._compute_status(),
            stages=list(self._stages),
            performance=self._performance,
            export=self._export,
        )

    def _compute_status(self) -> Status:
        if any(s.status == Status.FAIL for s in self._stages):
            return Status.FAIL
        if any(s.flags for s in self._stages):
            return Status.NEEDS_REVIEW
        if any(s.fixes for s in self._stages):
            return Status.PASS_WITH_FIXES
        return Status.PASS
