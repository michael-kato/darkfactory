"""Export & Handoff.

Exports the remediated Blender scene as FBX or glTF with Unity-compatible
settings, writes the JSON sidecar manifest, and routes output files to the
correct directory based on the overall QA status.
"""
from __future__ import annotations

import dataclasses
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from pipeline.report_builder import ReportBuilder
from pipeline.schema import ExportInfo, QaReport, StageResult, Status


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ExportConfig:
    output_dir: str
    unity_drop_dir: str
    review_queue_dir: str
    quarantine_dir: str
    format: str = "gltf"
    embed_textures: bool = False


# ---------------------------------------------------------------------------
# Category → Unity folder mapping
# ---------------------------------------------------------------------------

CATEGORY_FOLDER = {
    "character": "Characters",
    "env_prop": "Environment/Props",
    "hero_prop": "Environment/Props",
    "vehicle": "Vehicles",
    "weapon": "Weapons",
    "ui": "UI",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _route(qa_report: QaReport, export_path, manifest_path, config: ExportConfig, asset_id, category):
    status = qa_report.status

    if status in (Status.PASS, Status.PASS_WITH_FIXES):
        category_folder = CATEGORY_FOLDER.get(category, "Other")
        dest = Path(config.unity_drop_dir) / "Art" / category_folder / asset_id
    elif status == Status.NEEDS_REVIEW:
        dest = Path(config.review_queue_dir) / asset_id
    else:  # FAIL
        dest = Path(config.quarantine_dir) / asset_id

    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(export_path), str(dest / export_path.name))
    shutil.copy2(str(manifest_path), str(dest / manifest_path.name))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_export(context, report_builder: ReportBuilder, config: ExportConfig) -> tuple[StageResult, QaReport]:
    asset_id = report_builder.asset_id
    category = report_builder.category

    asset_out_dir = Path(config.output_dir) / asset_id
    asset_out_dir.mkdir(parents=True, exist_ok=True)

    export_path = asset_out_dir / f"{asset_id}.{config.format}"
    manifest_path = asset_out_dir / f"{asset_id}_qa.json"

    if config.format == "gltf":
        context.export_gltf(str(export_path), config.embed_textures)
    else:
        context.export_fbx(str(export_path))

    export_info = ExportInfo(
        format=config.format,
        path=str(export_path.resolve()),
        axis="-Z forward, Y up",
        scale=1.0,
    )
    report_builder.set_export(export_info)
    qa_report = report_builder.finalize()

    manifest_path.write_text(json.dumps(dataclasses.asdict(qa_report), indent=2))

    _route(qa_report, export_path, manifest_path, config, asset_id, category)

    return StageResult(name="export", status=Status.PASS), qa_report
