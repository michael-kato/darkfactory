from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"
    PASS_WITH_FIXES = "PASS_WITH_FIXES"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    ERROR = "ERROR"
    INFO = "INFO"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    value: Any
    threshold: Any
    message: str


@dataclass(frozen=True)
class FixEntry:
    action: str
    target: str
    before: Any
    after: Any


@dataclass(frozen=True)
class ReviewFlag:
    issue: str
    severity: Status
    description: str


@dataclass
class StageResult:
    name: str
    status: Status
    checks: list[CheckResult] = field(default_factory=list)
    fixes: list[FixEntry] = field(default_factory=list)
    flags: list[ReviewFlag] = field(default_factory=list)


@dataclass(frozen=True)
class PerformanceEstimates:
    triangles: int
    draw_calls: int
    vram_mb: float
    bones: int


@dataclass(frozen=True)
class ExportInfo:
    format: str
    path: str
    axis: str
    scale: float


@dataclass
class QaReport:
    asset_id: str
    source: str
    category: str
    submitter: str
    submitted: str
    processed: str
    status: Status
    stages: list[StageResult] = field(default_factory=list)
    performance: Optional[PerformanceEstimates] = None
    export: Optional[ExportInfo] = None
