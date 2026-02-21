"""Stage 3 — Export & Handoff.

Exports the remediated Blender scene as FBX or glTF with Unity-compatible
settings, writes the JSON sidecar manifest, and routes output files to the
correct directory based on the overall QA status.

The ``ExportBlenderContext`` ABC separates bpy export operators from pure
routing and I/O logic, enabling unit tests that never import bpy.
"""
from __future__ import annotations

import json
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pipeline.report_builder import ReportBuilder
from pipeline.schema import (
    ExportInfo,
    OverallStatus,
    QaReport,
    StageResult,
    StageStatus,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ExportConfig:
    """Configuration for the export & handoff stage.

    Attributes
    ----------
    output_dir:
        Base directory where ``{asset_id}/`` subdirectories are created.
    unity_drop_dir:
        Root of the Unity Assets drop folder.  PASS/PASS_WITH_FIXES assets
        are copied here under ``Art/{CategoryFolder}/{AssetName}/``.
    review_queue_dir:
        Destination for NEEDS_REVIEW assets: ``{review_queue_dir}/{asset_id}/``.
    quarantine_dir:
        Destination for FAIL assets: ``{quarantine_dir}/{asset_id}/``.
    format:
        Export format — ``"gltf"`` (default) or ``"fbx"``.
    embed_textures:
        When *True* the glTF exporter produces a single ``.glb`` with
        embedded textures.  When *False* (default) textures are written as
        external files and referenced by relative paths.
    """

    output_dir: str
    unity_drop_dir: str
    review_queue_dir: str
    quarantine_dir: str
    format: Literal["fbx", "gltf"] = "gltf"
    embed_textures: bool = False


# ---------------------------------------------------------------------------
# Category → Unity folder mapping
# ---------------------------------------------------------------------------

CATEGORY_FOLDER: dict[str, str] = {
    "character": "Characters",
    "env_prop": "Environment/Props",
    "hero_prop": "Environment/Props",
    "vehicle": "Vehicles",
    "weapon": "Weapons",
    "ui": "UI",
}


# ---------------------------------------------------------------------------
# Abstraction (implemented by real bpy wrappers and by test mocks)
# ---------------------------------------------------------------------------

class ExportBlenderContext(ABC):
    """Wraps bpy export operators so they can be replaced by test mocks."""

    @abstractmethod
    def export_gltf(self, filepath: str, embed_textures: bool) -> None:
        """Export the active scene to *filepath* using the glTF exporter.

        Must apply all modifiers, use ``-Z`` forward / ``Y`` up, scale 1.0.
        Uses ``export_format='GLB'`` when *embed_textures* is True,
        ``'GLTF_SEPARATE'`` otherwise.
        """
        ...

    @abstractmethod
    def export_fbx(self, filepath: str) -> None:
        """Export the active scene to *filepath* using the FBX exporter.

        Must apply all modifiers, use ``-Z`` forward / ``Y`` up, scale 1.0,
        with settings compatible with Unity's FBX importer.
        """
        ...


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _route(
    qa_report: QaReport,
    export_path: Path,
    manifest_path: Path,
    config: ExportConfig,
    asset_id: str,
    category: str,
) -> None:
    """Copy the exported file and sidecar manifest to the routing directory."""
    status = qa_report.overall_status

    if status in (OverallStatus.PASS, OverallStatus.PASS_WITH_FIXES):
        category_folder = CATEGORY_FOLDER.get(category, "Other")
        dest = Path(config.unity_drop_dir) / "Art" / category_folder / asset_id
    elif status == OverallStatus.NEEDS_REVIEW:
        dest = Path(config.review_queue_dir) / asset_id
    else:  # FAIL
        dest = Path(config.quarantine_dir) / asset_id

    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(export_path), str(dest / export_path.name))
    shutil.copy2(str(manifest_path), str(dest / manifest_path.name))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_export(
    context: ExportBlenderContext,
    report_builder: ReportBuilder,
    config: ExportConfig,
) -> tuple[StageResult, QaReport]:
    """Export the scene, write the sidecar manifest, and route the outputs.

    Steps
    -----
    1. Create ``{output_dir}/{asset_id}/`` and export the scene there.
    2. Populate ``ExportInfo`` in *report_builder*, then finalise the report.
    3. Write ``{asset_id}_qa.json`` alongside the exported file.
    4. Route both files to the correct directory based on ``overall_status``.
    5. Return ``(StageResult(name="export", status=PASS), finalised QaReport)``.
    """
    metadata = report_builder._metadata
    asset_id = metadata.asset_id
    category = metadata.category

    # ------------------------------------------------------------------
    # Create output directory and compute file paths
    # ------------------------------------------------------------------
    asset_out_dir = Path(config.output_dir) / asset_id
    asset_out_dir.mkdir(parents=True, exist_ok=True)

    export_path = asset_out_dir / f"{asset_id}.{config.format}"
    manifest_path = asset_out_dir / f"{asset_id}_qa.json"

    # ------------------------------------------------------------------
    # Export scene via abstraction (bpy or mock)
    # ------------------------------------------------------------------
    if config.format == "gltf":
        context.export_gltf(str(export_path), config.embed_textures)
    else:
        context.export_fbx(str(export_path))

    # ------------------------------------------------------------------
    # Populate ExportInfo and finalise the report
    # ------------------------------------------------------------------
    export_info = ExportInfo(
        format=config.format,
        path=str(export_path.resolve()),
        axis_convention="-Z forward, Y up",
        scale=1.0,
    )
    report_builder.set_export(export_info)
    qa_report = report_builder.finalize()

    # ------------------------------------------------------------------
    # Write sidecar manifest
    # ------------------------------------------------------------------
    manifest_path.write_text(json.dumps(qa_report.to_dict(), indent=2))

    # ------------------------------------------------------------------
    # Route output files based on overall QA status
    # ------------------------------------------------------------------
    _route(qa_report, export_path, manifest_path, config, asset_id, category)

    return (
        StageResult(name="export", status=StageStatus.PASS),
        qa_report,
    )
