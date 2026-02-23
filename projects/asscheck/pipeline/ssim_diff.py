"""SSIM Perceptual Diff.

Compares new turntable renders against golden reference images using
structural similarity (SSIM). Flagged renders are marked for human review.

"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass
class SSIMResult:
    angle: int
    score: float
    diff_image_path: str | None
    flagged: bool


# ---------------------------------------------------------------------------
# Filename parsing helpers
# ---------------------------------------------------------------------------

def _parse_angle_from_path(path):
    """Extract the angle (int degrees) from a turntable filename.

    Expected pattern: ``{asset_id}_turntable_{angle:03d}.png``
    """
    m = re.search(r"_turntable_(\d{3})\.png$", os.path.basename(path))
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Default SSIM computation (requires scikit-image + Pillow)
# ---------------------------------------------------------------------------

def _default_ssim_fn(path1, path2):
    """Compute SSIM between two images.  Returns (score, diff_array).

    Requires ``scikit-image`` and ``Pillow``.  Both images are converted to
    greyscale before comparison so that channel count differences are handled.
    """
    try:
        import numpy as np
        from PIL import Image
        from skimage.metrics import structural_similarity
    except ImportError as exc:
        raise ImportError(
            "scikit-image and Pillow are required for SSIM computation. "
            "Install with: pip install scikit-image Pillow"
        ) from exc

    img1 = np.array(Image.open(path1).convert("L"))
    img2 = np.array(Image.open(path2).convert("L"))
    score, diff = structural_similarity(img1, img2, full=True)
    return float(score), diff


def _save_diff_image(diff_arr, path):
    """Save an SSIM diff array as a PNG highlighting changed pixels."""
    try:
        import numpy as np
        from PIL import Image

        # SSIM map is high where similar, low where different.
        # Invert so that changed pixels appear bright.
        changed = 1.0 - diff_arr
        changed = (changed * 255).clip(0, 255).astype(np.uint8)
        Image.fromarray(changed).save(path)
    except ImportError:
        pass  # Skip diff image if Pillow unavailable


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

SSIM_THRESHOLD = 0.85


def compare_renders(
    new_renders,
    reference_dir,
    *,
    _compute_ssim=None,
) -> list[SSIMResult]:
    """Compare new turntable renders against golden references.

    Parameters
    ----------
    new_renders:
        Paths to the newly-rendered PNG files.
    reference_dir:
        Directory containing golden reference images with the same filenames.
    _compute_ssim:
        Optional callable ``(path1, path2) -> (float, array|None)``.
        Defaults to :func:`_default_ssim_fn`.

    Returns
    -------
    list[SSIMResult]
        One entry per input render.  If no reference image exists the score
        is 1.0 and ``flagged`` is False (first run establishes the baseline).
    """
    compute = _compute_ssim if _compute_ssim is not None else _default_ssim_fn
    results: list[SSIMResult] = []

    for render_path in new_renders:
        angle = _parse_angle_from_path(render_path)
        if angle is None:
            continue

        basename = os.path.basename(render_path)
        ref_path = os.path.join(reference_dir, basename)

        if not os.path.exists(ref_path):
            # First run — no golden reference yet; treat as perfect match.
            results.append(SSIMResult(
                angle=angle,
                score=1.0,
                diff_image_path=None,
                flagged=False,
            ))
            continue

        score, diff_arr = compute(render_path, ref_path)
        flagged = score < SSIM_THRESHOLD

        diff_path = None
        if flagged and diff_arr is not None:
            diff_path = render_path[:-4] + "_diff.png"
            _save_diff_image(diff_arr, diff_path)

        results.append(SSIMResult(
            angle=angle,
            score=score,
            diff_image_path=diff_path,
            flagged=flagged,
        ))

    return results
