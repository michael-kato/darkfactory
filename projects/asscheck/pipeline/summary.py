"""QA Output Summary."""
import os
import shutil
from html import escape

from pipeline.schema import ReviewFlag, Status


def _img_tag(src, alt="", style=""):
    s = f' style="{escape(style)}"' if style else ""
    return f'<img src="{escape(src)}" alt="{escape(alt)}"{s}>'


def _flag_row(flag):
    colour = {"ERROR": "#c0392b", "WARNING": "#e67e22", "INFO": "#2980b9"}
    bg = colour.get(flag.severity.value, "#555")
    badge = (
        f'<span style="background:{bg};color:#fff;padding:2px 6px;'
        f'border-radius:3px;font-size:0.8em">{escape(flag.severity.value)}</span>'
    )
    return (
        f"<tr><td>{badge}</td>"
        f"<td><code>{escape(flag.issue)}</code></td>"
        f"<td>{escape(flag.description)}</td></tr>"
    )


def _build_html(report, asset_id, render_basenames, scale_basename, ssim_results, diff_basenames, all_flags):
    status = report.status.value

    status_colour = {
        "PASS": "#27ae60",
        "PASS_WITH_FIXES": "#2ecc71",
        "NEEDS_REVIEW": "#e67e22",
        "FAIL": "#c0392b",
    }.get(status, "#555")

    render_cells = "".join(
        f'<td style="padding:4px;text-align:center">'
        f'{_img_tag(b, alt=b, style="max-width:200px;max-height:200px;border:1px solid #ddd")}'
        f'<br><small>{escape(b)}</small></td>'
        for b in render_basenames
    )
    renders_section = (
        f"<h2>Turntable Renders</h2>"
        f'<table><tr>{render_cells}</tr></table>'
        if render_cells
        else "<h2>Turntable Renders</h2><p>No renders available.</p>"
    )

    if scale_basename:
        scale_section = (
            f"<h2>Scale Reference</h2>"
            f'<p>{_img_tag(scale_basename, alt="Scale reference", style="max-width:600px;border:1px solid #ddd")}</p>'
        )
    else:
        scale_section = "<h2>Scale Reference</h2><p>Not available.</p>"

    if diff_basenames:
        diff_cells = "".join(
            f'<td style="padding:4px;text-align:center">'
            f'{_img_tag(b, alt=b, style="max-width:200px;max-height:200px;border:1px solid #c0392b")}'
            f'<br><small>{escape(b)}</small></td>'
            for b in diff_basenames
        )
        diffs_section = f"<h2>SSIM Diff Images (Flagged)</h2><table><tr>{diff_cells}</tr></table>"
    else:
        diffs_section = ""

    if ssim_results:
        score_rows = "".join(
            f"<tr>"
            f"<td>{r['angle']}&deg;</td>"
            f"<td>{r['score']:.4f}</td>"
            f'<td style="color:{"#c0392b" if r["flagged"] else "#27ae60"}">'
            f'{"&#x26A0; FLAGGED" if r["flagged"] else "OK"}</td>'
            f"</tr>"
            for r in ssim_results
        )
        ssim_section = (
            f"<h2>SSIM Scores</h2>"
            f"<table><tr><th>Angle</th><th>Score</th><th>Status</th></tr>"
            f"{score_rows}</table>"
        )
    else:
        ssim_section = ""

    if all_flags:
        flag_rows = "".join(_flag_row(f) for f in all_flags)
        flags_section = (
            f"<h2>Review Flags</h2>"
            f"<table><tr><th>Severity</th><th>Issue</th><th>Description</th></tr>"
            f"{flag_rows}</table>"
        )
    else:
        flags_section = "<h2>Review Flags</h2><p>None.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>QA Review &mdash; {escape(asset_id)}</title>
<style>
  body {{font-family:sans-serif;margin:2em;color:#222;background:#fff}}
  h1 {{border-bottom:2px solid #ddd;padding-bottom:.4em}}
  h2 {{color:#444;margin-top:1.6em}}
  table {{border-collapse:collapse;margin:.5em 0}}
  th,td {{border:1px solid #ddd;padding:6px 10px;text-align:left;vertical-align:top}}
  th {{background:#f0f0f0}}
  .status {{display:inline-block;padding:4px 12px;border-radius:4px;
            color:#fff;font-weight:bold;background:{status_colour}}}
  dl {{margin:.5em 0}} dt {{font-weight:bold;float:left;width:12em}} dd {{margin-left:13em}}
</style>
</head>
<body>
<h1>QA Review &mdash; {escape(asset_id)}</h1>
<p class="status">{escape(status)}</p>

<h2>Asset Metadata</h2>
<dl>
  <dt>Asset ID</dt><dd>{escape(report.asset_id)}</dd>
  <dt>Source</dt><dd>{escape(report.source)}</dd>
  <dt>Category</dt><dd>{escape(report.category)}</dd>
  <dt>Submitter</dt><dd>{escape(report.submitter)}</dd>
  <dt>Submission Date</dt><dd>{escape(report.submitted)}</dd>
  <dt>Processing Time</dt><dd>{escape(report.processed)}</dd>
</dl>

{renders_section}
{scale_section}
{ssim_section}
{diffs_section}
{flags_section}
</body>
</html>
"""


def write_review_package(report, render_paths, ssim_results, scale_image, output_dir):
    asset_id = report.asset_id
    package_dir = os.path.join(output_dir, asset_id)
    os.makedirs(package_dir, exist_ok=True)

    render_basenames = []
    for render_path in render_paths:
        if os.path.exists(render_path):
            bn = os.path.basename(render_path)
            shutil.copy2(render_path, os.path.join(package_dir, bn))
            render_basenames.append(bn)

    diff_basenames = []
    for r in ssim_results:
        if r["diff_image_path"] and os.path.exists(r["diff_image_path"]):
            bn = os.path.basename(r["diff_image_path"])
            shutil.copy2(r["diff_image_path"], os.path.join(package_dir, bn))
            diff_basenames.append(bn)

    scale_basename = None
    if scale_image and os.path.exists(scale_image):
        scale_basename = os.path.basename(scale_image)
        shutil.copy2(scale_image, os.path.join(package_dir, scale_basename))

    stage5_flags = [ReviewFlag(
        issue="scale_verification",
        severity=Status.INFO,
        description="Scale reference screenshot generated. Human reviewer must verify scale is correct.",
    )]
    # Append a pseudo-stage for visual verification flags
    report.stages.append(type('_Stage', (), {
        'name': 'visual_verification',
        'status': Status.PASS,
        'checks': [],
        'fixes': [],
        'flags': stage5_flags,
    })())

    all_flags = []
    for stage in report.stages:
        all_flags.extend(stage.flags)

    html = _build_html(
        report=report,
        asset_id=asset_id,
        render_basenames=render_basenames,
        scale_basename=scale_basename,
        ssim_results=ssim_results,
        diff_basenames=diff_basenames,
        all_flags=all_flags,
    )
    html_path = os.path.join(package_dir, "review_summary.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html)
