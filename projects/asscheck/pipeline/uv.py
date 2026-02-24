"""UV Checks.

Analyses UV layouts for all mesh objects in the Blender scene: detects missing
UVs, out-of-bounds islands, overlapping islands, texel density violations, and
lightmap UV2 issues.

"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.schema import CheckResult, StageResult, Status

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class UVConfig:
    """Configuration for UV checks.

    Attributes
    ----------
    texel_density_target_px_per_m:
        (min, max) acceptable density range expressed as UV-area / world-area
        (uv_area in [0,1]² / world_area in m²).
    require_lightmap_uv2:
        If True, verify that ``lightmap_layer_name`` UV layer exists on every
        mesh and has no overlapping islands.
    uv_layer_name:
        Primary UV layer name (default ``"UVMap"``).
    lightmap_layer_name:
        Lightmap UV layer name (default ``"UVMap2"``).
    """

    texel_density_target_px_per_m: tuple[float, float] = (512.0, 1024.0)
    require_lightmap_uv2: bool = False
    uv_layer_name: str = "UVMap"
    lightmap_layer_name: str = "UVMap2"

def _cross_2d(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

def _segments_intersect(a0, a1, b0, b1):
    """Return True if segments a0-a1 and b0-b1 properly intersect."""
    d1 = _cross_2d(b0, b1, a0)
    d2 = _cross_2d(b0, b1, a1)
    d3 = _cross_2d(a0, a1, b0)
    d4 = _cross_2d(a0, a1, b1)
    return (
        ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0))
        and ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0))
    )

def _point_in_triangle(p, t0, t1, t2):
    """Return True if point p lies inside (or on the boundary of) triangle t0-t1-t2."""
    d0 = _cross_2d(t0, t1, p)
    d1 = _cross_2d(t1, t2, p)
    d2 = _cross_2d(t2, t0, p)
    has_neg = (d0 < 0) or (d1 < 0) or (d2 < 0)
    has_pos = (d0 > 0) or (d1 > 0) or (d2 > 0)
    return not (has_neg and has_pos)

def _triangles_overlap(t1, t2):
    """Exact 2-D triangle-triangle overlap test.

    Returns True if the triangles share any interior area (edge crossings or
    containment).
    """
    v1 = [t1[0], t1[1], t1[2]]
    v2 = [t2[0], t2[1], t2[2]]

    # Check all edge pairs for intersection.
    for i in range(3):
        for j in range(3):
            if _segments_intersect(
                v1[i], v1[(i + 1) % 3], v2[j], v2[(j + 1) % 3]
            ):
                return True

    # Check containment (one triangle entirely inside the other).
    if _point_in_triangle(v1[0], *v2):
        return True
    if _point_in_triangle(v2[0], *v1):
        return True

    return False

def _triangle_aabb(tri):
    xs = (tri[0][0], tri[1][0], tri[2][0])
    ys = (tri[0][1], tri[1][1], tri[2][1])
    return min(xs), min(ys), max(xs), max(ys)

def _triangle_area_2d(tri):
    (x0, y0), (x1, y1), (x2, y2) = tri
    return abs((x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)) / 2.0

_GRID = 16  # spatial-hash grid resolution

def _find_overlapping_pairs(triangles):
    """Return the count of overlapping triangle pairs using spatial hashing."""
    if len(triangles) < 2:
        return 0

    # Build spatial hash: grid cell → list of triangle indices.
    grid = {}
    for idx, tri in enumerate(triangles):
        x0, y0, x1, y1 = _triangle_aabb(tri)
        cx0 = int(x0 * _GRID)
        cy0 = int(y0 * _GRID)
        cx1 = int(x1 * _GRID)
        cy1 = int(y1 * _GRID)
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                grid.setdefault((cx, cy), []).append(idx)

    # Check all candidate pairs exactly once.
    checked = set()
    overlap_count = 0
    for cell_indices in grid.values():
        n = len(cell_indices)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = cell_indices[i], cell_indices[j]
                pair = (min(a, b), max(a, b))
                if pair in checked:
                    continue
                checked.add(pair)
                if _triangles_overlap(triangles[a], triangles[b]):
                    overlap_count += 1

    return overlap_count

# ---------------------------------------------------------------------------
# Individual check helpers
# ---------------------------------------------------------------------------

def _check_missing_uvs(
    objects: list,
    config: UVConfig,
) -> CheckResult:
    count = sum(1 for obj in objects if len(obj.uv_layer_names()) == 0)
    return CheckResult(
        name="missing_uvs",
        status=Status.FAIL if count > 0 else Status.PASS,
        value=count,
        threshold=0,
        message=(
            f"{count} mesh object(s) have no UV layers"
            if count else "All mesh objects have UV layers"
        ),
    )

def _check_uv_bounds(
    objects: list,
    config: UVConfig,
) -> CheckResult:
    count = 0
    for obj in objects:
        if config.uv_layer_name not in obj.uv_layer_names():
            continue
        for u, v in obj.uv_loops(config.uv_layer_name):
            if not (0.0 <= u <= 1.0 and 0.0 <= v <= 1.0):
                count += 1
    return CheckResult(
        name="uv_bounds",
        status=Status.FAIL if count > 0 else Status.PASS,
        value=count,
        threshold=0,
        message=(
            f"{count} UV loop(s) outside [0, 1] bounds"
            if count else "All UV coordinates within [0, 1]"
        ),
    )

def _check_uv_overlap(
    objects: list,
    config: UVConfig,
) -> CheckResult:
    all_tris = []
    for obj in objects:
        if config.uv_layer_name in obj.uv_layer_names():
            all_tris.extend(obj.uv_triangles(config.uv_layer_name))

    overlap_count = _find_overlapping_pairs(all_tris)
    return CheckResult(
        name="uv_overlap",
        status=Status.FAIL if overlap_count > 0 else Status.PASS,
        value=overlap_count,
        threshold=0,
        message=(
            f"{overlap_count} overlapping UV island pair(s) found"
            if overlap_count else "No overlapping UV islands"
        ),
    )

def _check_texel_density(
    objects: list,
    config: UVConfig,
) -> CheckResult:
    min_target, max_target = config.texel_density_target_px_per_m
    densities = []

    for obj in objects:
        if config.uv_layer_name not in obj.uv_layer_names():
            continue
        tris = obj.uv_triangles(config.uv_layer_name)
        uv_area = sum(_triangle_area_2d(t) for t in tris)
        world_area = obj.world_surface_area()
        if world_area > 0 and uv_area > 0:
            densities.append(uv_area / world_area)

    if not densities:
        return CheckResult(
            name="texel_density",
            status=Status.SKIPPED,
            value={"min": 0.0, "max": 0.0, "mean": 0.0, "outlier_count": 0},
            threshold=(min_target, max_target),
            message="No UV data available for texel density check",
        )

    d_min = min(densities)
    d_max = max(densities)
    d_mean = sum(densities) / len(densities)
    outlier_count = sum(
        1 for d in densities if d < min_target or d > max_target
    )

    measured = {
        "min": d_min,
        "max": d_max,
        "mean": d_mean,
        "outlier_count": outlier_count,
    }
    return CheckResult(
        name="texel_density",
        status=Status.WARNING if outlier_count > 0 else Status.PASS,
        value=measured,
        threshold=(min_target, max_target),
        message=(
            f"Texel density: {outlier_count} island(s) outside target range "
            f"({min_target}, {max_target}) — flagged for human review"
            if outlier_count else
            f"Texel density within target range ({min_target}, {max_target})"
        ),
    )

def _check_lightmap_uv2(
    objects: list,
    config: UVConfig,
) -> CheckResult:
    if not config.require_lightmap_uv2:
        return CheckResult(
            name="lightmap_uv2",
            status=Status.SKIPPED,
            value={"present": False, "overlap_count": 0},
            threshold=0,
            message="Lightmap UV2 check skipped (require_lightmap_uv2=False)",
        )

    missing = [
        obj for obj in objects
        if config.lightmap_layer_name not in obj.uv_layer_names()
    ]
    if missing:
        return CheckResult(
            name="lightmap_uv2",
            status=Status.FAIL,
            value={"present": False, "overlap_count": 0},
            threshold=0,
            message=(
                f"Lightmap UV layer '{config.lightmap_layer_name}' missing on "
                f"{len(missing)} object(s)"
            ),
        )

    all_tris = []
    for obj in objects:
        all_tris.extend(obj.uv_triangles(config.lightmap_layer_name))

    overlap_count = _find_overlapping_pairs(all_tris)
    return CheckResult(
        name="lightmap_uv2",
        status=Status.FAIL if overlap_count > 0 else Status.PASS,
        value={"present": True, "overlap_count": overlap_count},
        threshold=0,
        message=(
            f"Lightmap UV2 has {overlap_count} overlapping island pair(s)"
            if overlap_count else "Lightmap UV2 present with no overlaps"
        ),
    )

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def check_uvs(context, config: UVConfig) -> StageResult:
    """Run all UV checks and return a ``StageResult``.

    All checks always run — earlier failures do not short-circuit later checks.
    ``texel_density`` is reported as WARNING (not FAIL) when out of range, so
    it does not cause the stage to fail.
    """
    objects = context.mesh_objects()

    checks = [
        _check_missing_uvs(objects, config),
        _check_uv_bounds(objects, config),
        _check_uv_overlap(objects, config),
        _check_texel_density(objects, config),
        _check_lightmap_uv2(objects, config),
    ]

    stage_status = (
        Status.FAIL
        if any(c.status == Status.FAIL for c in checks)
        else Status.PASS
    )
    return StageResult(name="uv", status=stage_status, checks=checks)
