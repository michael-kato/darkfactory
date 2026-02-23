"""Run all asscheck integration tests in a single Blender process.

Usage (headless):  blender --background --python blender_tests/run_all.py
Usage (GUI):       Open in Blender Text Editor, press Alt+R

Each test module must export a run_tests() -> dict function. The dict must have:
  - "passed": bool            (required, unless "skipped" is True)
  - "skipped": bool           (optional, suppresses pass/fail)
  - "tests_run": int          (optional)
  - "failures": list[str]     (optional, present when passed=False)

Exit code: 0 if all tests passed or skipped, 1 if any test failed.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_TESTS_DIR = Path(__file__).resolve().parent

_TEST_SCRIPTS = [
    "test_stage1a_blender.py",
    "test_stage1b_blender.py",
    "test_stage1c_blender.py",
    "test_stage1d_blender.py",
    "test_stage1e_blender.py",
    "test_stage1f_blender.py",
    "test_stage2_blender.py",
    "test_stage5_blender.py",
]


def _load_and_run(script_name: str) -> dict:
    """Load a test module by file path and call its run_tests() function."""
    filepath = _TESTS_DIR / script_name
    spec = importlib.util.spec_from_file_location("_blender_test_module", filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # __name__ != "__main__" → _main() not called
    return mod.run_tests()


def run_all() -> dict:
    results: dict[str, dict] = {}
    failed: list[str] = []

    for script in _TEST_SCRIPTS:
        name = script.replace("test_", "").replace("_blender.py", "")
        print(f"[run_all] {name} ...", flush=True)
        try:
            r = _load_and_run(script)
            results[name] = r
            if r.get("skipped"):
                print(f"[run_all] {name}: SKIP ({r.get('reason', '')})")
            elif r.get("passed"):
                n = r.get("tests_run", "?")
                print(f"[run_all] {name}: PASS ({n} tests)")
            else:
                print(f"[run_all] {name}: FAIL — {r.get('failures', [])}")
                failed.append(name)
        except Exception as exc:
            import traceback
            results[name] = {"passed": False, "error": str(exc), "traceback": traceback.format_exc()}
            failed.append(name)
            print(f"[run_all] {name}: ERROR — {exc}")

    return {"passed": len(failed) == 0, "failed": failed, "results": results}


def _main() -> None:
    r = run_all()
    summary = {"passed": r["passed"], "failed": r["failed"]}
    print(json.dumps(summary, indent=2))
    sys.exit(0 if r["passed"] else 1)


if __name__ == "__main__":
    _main()
