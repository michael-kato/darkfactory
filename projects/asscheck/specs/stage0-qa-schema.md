# Spec: QA Report Schema & Data Types

## Goal
Define the foundational Python data structures and JSON schema that every pipeline stage
writes to. All downstream specs depend on this existing before they can be implemented.

## Depends On
Nothing — implement this first.

## Acceptance Criteria

1. A Python module `pipeline/schema.py` exists and exports the following:

   **Enums:**
   - `OverallStatus`: `PASS | PASS_WITH_FIXES | NEEDS_REVIEW | FAIL`
   - `StageStatus`: `PASS | FAIL | SKIPPED`
   - `CheckStatus`: `PASS | FAIL | WARNING | SKIPPED`
   - `Severity`: `ERROR | WARNING | INFO`

   **Dataclasses (frozen where read-after-write):**
   - `CheckResult(name: str, status: CheckStatus, measured_value: Any, threshold: Any, message: str)`
   - `FixEntry(action: str, target: str, before_value: Any, after_value: Any)`
   - `ReviewFlag(issue: str, severity: Severity, description: str)`
   - `StageResult(name: str, status: StageStatus, checks: list[CheckResult], fixes: list[FixEntry], review_flags: list[ReviewFlag])`
   - `PerformanceEstimates(triangle_count: int, draw_call_estimate: int, vram_estimate_mb: float, bone_count: int)`
   - `ExportInfo(format: str, path: str, axis_convention: str, scale: float)`
   - `AssetMetadata(asset_id: str, source: str, category: str, submission_date: str, processing_timestamp: str, submitter: str)`
   - `QaReport(metadata: AssetMetadata, overall_status: OverallStatus, stages: list[StageResult], performance: PerformanceEstimates | None, export: ExportInfo | None)`

2. `QaReport` has a `to_dict() -> dict` method that produces the JSON-serializable dict
   matching the schema in section 13 of the design doc.

3. `QaReport` has a classmethod `from_dict(d: dict) -> QaReport` for round-trip loading.

4. A `pipeline/report_builder.py` module provides `ReportBuilder`:
   - `add_stage(stage_result: StageResult)` — append a stage
   - `set_performance(p: PerformanceEstimates)`
   - `set_export(e: ExportInfo)`
   - `finalize() -> QaReport` — computes `overall_status` from stage results and returns the report
   - Status derivation rules:
     - Any stage FAIL → `FAIL`
     - Any review flag present → `NEEDS_REVIEW`
     - Any fix applied → `PASS_WITH_FIXES`
     - Otherwise → `PASS`

5. `pipeline/__init__.py` exports `schema` and `report_builder` modules.

6. Project structure created:
   ```
   pipeline/
     __init__.py
     schema.py
     report_builder.py
   tests/
     test_schema.py
   ```

## Tests (`tests/test_schema.py`)
- Round-trip: `QaReport.from_dict(report.to_dict()) == report` for a fully-populated report
- `finalize()` returns `FAIL` when any stage is `StageStatus.FAIL`
- `finalize()` returns `NEEDS_REVIEW` when a review flag exists and no stage fails
- `finalize()` returns `PASS_WITH_FIXES` when a fix is logged and no failures/flags
- `finalize()` returns `PASS` for an all-clean report
- Serialized JSON matches the field names in section 13 of the design doc

## Out of Scope
- Config file loading (separate)
- CLI entry point (separate)
- Any actual checks — this spec is data structures only
