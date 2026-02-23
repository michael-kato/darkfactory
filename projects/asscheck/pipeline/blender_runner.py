"""Blender subprocess runner.

Invokes ``blender --background --python <script>`` with optional extra args,
then finds and parses the first complete JSON object emitted on stdout
(scanning from the last line backwards, because Blender prefixes its own
log messages before script output).
"""
from __future__ import annotations

import json
import subprocess


def run_in_blender(script, args=None):
    """Run *script* inside Blender headless and return parsed JSON output.

    The script must print a single JSON object to stdout (typically as the
    final line of output).

    Parameters
    ----------
    script:
        Path to the Python script to execute inside Blender.
    args:
        Extra positional arguments appended after ``--``.

    Returns
    -------
    dict
        Parsed JSON output from the script.

    Raises
    ------
    RuntimeError
        If Blender exits non-zero or no valid JSON line is found in stdout.
    """
    cmd = ["blender", "--background", "--python", script]
    if args:
        cmd += ["--"] + list(args)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"Blender exited with code {result.returncode}.\n"
            f"stderr:\n{result.stderr}"
        )

    # Scan lines in reverse so the last JSON line is found first.
    for line in reversed(result.stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue

    raise RuntimeError(
        f"No valid JSON found in Blender stdout.\nstdout:\n{result.stdout}"
    )
