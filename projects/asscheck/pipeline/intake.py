"""Intake & Triage.

File-system-level validation that runs before Blender opens anything.
Validates format, checks size, assigns a unique asset ID, logs metadata,
and initialises the QA report.
"""
from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pipeline.report_builder import ReportBuilder
from pipeline.schema import (
    AssetMetadata,
    CheckResult,
    CheckStatus,
    QaReport,
    StageResult,
    StageStatus,
)

ACCEPTED_EXTENSIONS = frozenset({".fbx", ".gltf", ".glb", ".obj"})


@dataclass
class IntakeConfig:
    file_path: str
    source: str
    submitter: str
    category: str
    max_size_bytes: dict  # category -> byte limit; "*" key for default
    hard_max_bytes: int   # absolute reject threshold regardless of category


def run_intake(config: IntakeConfig) -> QaReport:
    """Validate a file at the filesystem level and return an initialised QaReport."""
    checks: list[CheckResult] = []
    asset_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    path = Path(config.file_path)
    ext = path.suffix.lower()

    # --- Format check ---
    if ext not in ACCEPTED_EXTENSIONS:
        checks.append(CheckResult(
            name="format",
            status=CheckStatus.FAIL,
            measured_value=ext or "(none)",
            threshold=sorted(ACCEPTED_EXTENSIONS),
            message=f"Unsupported format '{ext}'. Accepted: {sorted(ACCEPTED_EXTENSIONS)}",
        ))
        return _build_report(asset_id, config, now, StageStatus.FAIL, checks)

    checks.append(CheckResult(
        name="format",
        status=CheckStatus.PASS,
        measured_value=ext,
        threshold=sorted(ACCEPTED_EXTENSIONS),
        message="Format accepted",
    ))

    # --- Existence check ---
    if not path.exists():
        checks.append(CheckResult(
            name="file_exists",
            status=CheckStatus.FAIL,
            measured_value=str(config.file_path),
            threshold=None,
            message=f"File not found: {config.file_path}",
        ))
        return _build_report(asset_id, config, now, StageStatus.FAIL, checks)

    checks.append(CheckResult(
        name="file_exists",
        status=CheckStatus.PASS,
        measured_value=str(config.file_path),
        threshold=None,
        message="File found",
    ))

    # --- Size check ---
    file_size = path.stat().st_size
    category_limit = config.max_size_bytes.get(
        config.category, config.max_size_bytes.get("*")
    )

    if file_size > config.hard_max_bytes:
        checks.append(CheckResult(
            name="file_size",
            status=CheckStatus.FAIL,
            measured_value=file_size,
            threshold=config.hard_max_bytes,
            message=(
                f"File size {file_size} B exceeds hard limit {config.hard_max_bytes} B"
            ),
        ))
        return _build_report(asset_id, config, now, StageStatus.FAIL, checks)

    if category_limit is not None and file_size > category_limit:
        checks.append(CheckResult(
            name="file_size",
            status=CheckStatus.WARNING,
            measured_value=file_size,
            threshold=category_limit,
            message=(
                f"File size {file_size} B exceeds category limit {category_limit} B "
                f"for '{config.category}'"
            ),
        ))
    else:
        checks.append(CheckResult(
            name="file_size",
            status=CheckStatus.PASS,
            measured_value=file_size,
            threshold=category_limit if category_limit is not None else config.hard_max_bytes,
            message="File size within limits",
        ))

    return _build_report(asset_id, config, now, StageStatus.PASS, checks)


def _build_report(
    asset_id,
    config: IntakeConfig,
    now,
    stage_status: StageStatus,
    checks: list[CheckResult],
) -> QaReport:
    metadata = AssetMetadata(
        asset_id=asset_id,
        source=config.source,
        category=config.category,
        submission_date=now.date().isoformat(),
        processing_timestamp=now.isoformat(),
        submitter=config.submitter,
    )
    stage = StageResult(name="intake", status=stage_status, checks=checks)
    builder = ReportBuilder(metadata)
    builder.add_stage(stage)
    return builder.finalize()


# ---------------------------------------------------------------------------
# CLI entry point:  python -m pipeline.intake <file> --source ... etc.
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Intake & Triage — filesystem-level asset validation"
    )
    parser.add_argument("file", help="Path to the asset file")
    parser.add_argument("--source", required=True, help="Asset source (e.g. vendor/marketplace/internal)")
    parser.add_argument("--submitter", required=True, help="Who submitted this asset")
    parser.add_argument("--category", required=True,
                        choices=["character", "env_prop", "hero_prop", "vehicle", "weapon", "ui"],
                        help="Asset category")
    parser.add_argument("--max-mb", type=int, default=500,
                        help="Category size limit in MB (default 500)")
    parser.add_argument("--hard-max-mb", type=int, default=1024,
                        help="Hard reject threshold in MB (default 1024)")
    return parser.parse_args(argv)


def _stage_to_dict(stage: StageResult):
    return {
        "name": stage.name,
        "status": stage.status.value,
        "checks": [
            {
                "name": c.name,
                "status": c.status.value,
                "measured_value": c.measured_value,
                "threshold": c.threshold,
                "message": c.message,
            }
            for c in stage.checks
        ],
    }


if __name__ == "__main__":
    args = _parse_args()

    config = IntakeConfig(
        file_path=args.file,
        source=args.source,
        submitter=args.submitter,
        category=args.category,
        max_size_bytes={args.category: args.max_mb * 1024 * 1024, "*": args.max_mb * 1024 * 1024},
        hard_max_bytes=args.hard_max_mb * 1024 * 1024,
    )

    report = run_intake(config)
    intake_stage = report.stages[0]
    print(json.dumps(_stage_to_dict(intake_stage), indent=2))
    sys.exit(0 if intake_stage.status == StageStatus.PASS else 1)
