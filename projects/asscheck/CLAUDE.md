# asscheck — Project Conventions

## What This Project Is
3D asset QA pipeline for VR games. Validates and prepares Blender-exported assets
for Unity using Blender headless (bpy/bmesh) and Unity Editor scripts (C#/AssetPostprocessor).

## Stack
- Python 3.x + Blender 3.x/4.x headless — Stages 0–3
- C# Unity 6 / URP — Stages 4–5
- Unity project: `asscheck_uproj/`
- Python package: `pipeline/` (to be built per specs)

## Project Structure (target)
```
projects/asscheck/
  pipeline/           Python QA pipeline package
    stage0/           Intake & triage
    stage1/           Analysis checks (geometry, uv, texture, pbr, armature, scene)
    stage2/           Auto-remediation
    stage3/           Export & handoff
    stage4/           (orchestrates Unity import — invokes Unity CLI)
    stage5/           Visual verification (renders, SSIM)
  tests/              pytest unit tests (no Blender needed)
  blender_tests/      Integration tests run via: blender --background --python <script>
  asscheck_uproj/     Unity project
  specs/              Work items for this project
  .venv/              Python venv (create with: python -m venv .venv && pip install -r requirements.txt)
```

## Test Commands
- Unit tests: `python -m pytest tests/ -v` (from project root)
- Blender tests: `blender --background --python blender_tests/<script>.py`
- Unity tests: `Unity -batchmode -runTests -testPlatform editmode -logFile -`

## Code Conventions
- Python: `pipeline/schema.py` types must be used for all QA data — no ad-hoc dicts
- Validators return `StageResult` — never raw booleans
- `BlenderContext` abstraction separates bpy-specific code from pure logic (enables unit testing)
- Each spec's file paths are relative to this project root (`projects/asscheck/`)
- Unity C#: namespace `QAPipeline`, scripts in `asscheck_uproj/Assets/Editor/QAPipeline/`

## Automated Commit Format
- Subject: `[automated] asscheck: <description>`
- Branch: `automation/asscheck/<spec-slug>`

## Never Modify
- `asscheck_uproj/Library/`
- `asscheck_uproj/ProjectSettings/`
- `.git/`

## Sample Asset
`asscheck_uproj/Assets/Models/street_lamp_01_quant.gltf` — use for integration tests
