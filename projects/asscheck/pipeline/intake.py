"""Intake & Triage.

File-system-level validation that runs before Blender opens anything.
"""
from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pipeline.report_builder import ReportBuilder
from pipeline.schema import CheckResult, QaReport, StageResult, Status

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
    checks: list[CheckResult] = []
    asset_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    path = Path(config.file_path)
    ext = path.suffix.lower()

    if ext not in ACCEPTED_EXTENSIONS:
        checks.append(CheckResult(
            name="format",
            status=Status.FAIL,
            value=ext or "(none)",
            threshold=sorted(ACCEPTED_EXTENSIONS),
            message=f"Unsupported format '{ext}'. Accepted: {sorted(ACCEPTED_EXTENSIONS)}",
        ))
        return _build_report(asset_id, config, now, Status.FAIL, checks)

    checks.append(CheckResult(
        name="format",
        status=Status.PASS,
        value=ext,
        threshold=sorted(ACCEPTED_EXTENSIONS),
        message="Format accepted",
    ))

    if not path.exists():
        checks.append(CheckResult(
            name="file_exists",
            status=Status.FAIL,
            value=str(config.file_path),
            threshold=None,
            message=f"File not found: {config.file_path}",
        ))
        return _build_report(asset_id, config, now, Status.FAIL, checks)

    checks.append(CheckResult(
        name="file_exists",
        status=Status.PASS,
        value=str(config.file_path),
        threshold=None,
        message="File found",
    ))

    file_size = path.stat().st_size
    category_limit = config.max_size_bytes.get(
        config.category, config.max_size_bytes.get("*")
    )

    if file_size > config.hard_max_bytes:
        checks.append(CheckResult(
            name="file_size",
            status=Status.FAIL,
            value=file_size,
            threshold=config.hard_max_bytes,
            message=f"File size {file_size} B exceeds hard limit {config.hard_max_bytes} B",
        ))
        return _build_report(asset_id, config, now, Status.FAIL, checks)

    if category_limit is not None and file_size > category_limit:
        checks.append(CheckResult(
            name="file_size",
            status=Status.WARNING,
            value=file_size,
            threshold=category_limit,
            message=(
                f"File size {file_size} B exceeds category limit {category_limit} B "
                f"for '{config.category}'"
            ),
        ))
    else:
        checks.append(CheckResult(
            name="file_size",
            status=Status.PASS,
            value=file_size,
            threshold=category_limit if category_limit is not None else config.hard_max_bytes,
            message="File size within limits",
        ))

    return _build_report(asset_id, config, now, Status.PASS, checks)


def _build_report(asset_id, config: IntakeConfig, now, stage_status, checks) -> QaReport:
    stage = StageResult(name="intake", status=stage_status, checks=checks)
    builder = ReportBuilder(
        asset_id=asset_id,
        source=config.source,
        category=config.category,
        submitter=config.submitter,
        submitted=now.date().isoformat(),
        processed=now.isoformat(),
    )
    builder.add_stage(stage)
    return builder.finalize()


def _parse_args(argv=None):
    import argparse
    parser = argparse.ArgumentParser(
        description="Intake & Triage — filesystem-level asset validation"
    )
    parser.add_argument("file", help="Path to the asset file")
    parser.add_argument("--source", required=True)
    parser.add_argument("--submitter", required=True)
    parser.add_argument("--category", required=True,
                        choices=["character", "env_prop", "hero_prop", "vehicle", "weapon", "ui"])
    parser.add_argument("--max-mb", type=int, default=500)
    parser.add_argument("--hard-max-mb", type=int, default=1024)
    return parser.parse_args(argv)


if __name__ == "__main__":
    import dataclasses
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
    print(json.dumps(dataclasses.asdict(intake_stage), indent=2))
    sys.exit(0 if intake_stage.status == Status.PASS else 1)
