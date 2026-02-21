# Spec: Stage 0 — Intake & Triage

## Goal
File-system-level validation that runs before Blender opens anything. Validates format,
checks size, assigns a unique asset ID, logs metadata, and initialises the QA report.
Invalid assets are rejected here before any expensive processing begins.

## Depends On
- `stage0-qa-schema.md` (pipeline/schema.py must exist)

## Acceptance Criteria

1. A module `pipeline/stage0/intake.py` exists and exports `run_intake(config: IntakeConfig) -> QaReport`.

2. **`IntakeConfig` dataclass** (defined in `pipeline/stage0/intake.py` or `pipeline/config.py`):
   ```python
   @dataclass
   class IntakeConfig:
       file_path: str
       source: str              # e.g. "vendor/marketplace/internal"
       submitter: str
       category: str            # character | env_prop | hero_prop | vehicle | weapon | ui
       max_size_bytes: dict[str, int]   # category → byte limit; "*" key for default
       hard_max_bytes: int      # absolute reject threshold regardless of category
   ```

3. **Format validation** — accepted extensions: `.fbx`, `.gltf`, `.glb`, `.obj`.
   Any other extension: `StageStatus.FAIL`, `CheckStatus.FAIL`, overall status `FAIL`.

4. **File existence** — if file does not exist: `StageStatus.FAIL`.

5. **File size check**:
   - Lookup `max_size_bytes[category]`, fallback to `max_size_bytes["*"]`.
   - Exceeds category limit → `CheckStatus.WARNING` (flag, do not fail).
   - Exceeds `hard_max_bytes` → `CheckStatus.FAIL`, stage fails.

6. **Asset ID generation** — UUID4 string assigned and stored in `AssetMetadata.asset_id`.
   The same file path submitted twice gets a different asset ID each run.

7. **Metadata logging** — `AssetMetadata` populated with: `asset_id`, `source`,
   `submitter`, `category`, `submission_date` (ISO 8601 date), `processing_timestamp`
   (ISO 8601 datetime).

8. **Returns** a `QaReport` with one completed `StageResult` (name `"intake"`).
   The report is not yet finalised (no `overall_status` computed — that happens in stage 3).

9. **No external dependencies** beyond stdlib. Blender is not involved.

10. A CLI entry point `python -m pipeline.stage0.intake <file> --source <s> --submitter <s> --category <c>`
    prints the intake stage result as JSON and exits 0 on pass, 1 on fail.

## Tests (`tests/test_stage0_intake.py`)

Define at the top of the test file:
```python
ASSETS_DIR = Path(__file__).parent.parent / "assets"
```

Use real assets from `assets/` for format tests — do not create fake stubs for accepted formats:

- Valid `.gltf` → `ASSETS_DIR / "street_lamp_01.gltf"` → `StageStatus.PASS`, asset_id is a non-empty string
- Valid `.glb`  → `ASSETS_DIR / "large_iron_gate_left_door.glb"` → `StageStatus.PASS`
- Valid `.fbx`  → `ASSETS_DIR / "tree_small_02_branches.fbx"` → `StageStatus.PASS`
- Valid `.obj`  → `ASSETS_DIR / "double_door_standard_01.obj"` → `StageStatus.PASS`
- `.blend` file (tmp_path stub) → `StageStatus.FAIL`
- `.zip` file (tmp_path stub) → `StageStatus.FAIL`
- Non-existent path → `StageStatus.FAIL`
- File exceeding `hard_max_bytes` → `ASSETS_DIR / "tree_small_02_branches.fbx"` (≈114 MB) with `hard_max_bytes=50 * 1024 * 1024` → `StageStatus.FAIL`
- File exceeding category limit but under hard max → same FBX with `max_size_bytes={"*": 50 * 1024 * 1024}` and `hard_max_bytes=200 * 1024 * 1024` → `StageStatus.PASS` with a WARNING on the `file_size` check
- Two runs on the same file produce different asset IDs → `ASSETS_DIR / "street_lamp_01.gltf"`

All tests must skip (not fail) if `ASSETS_DIR` does not exist, so the suite can run in CI without the binary assets present.

## Out of Scope
- Deduplication by content hash (future)
- Database/API submission logging (future)
- File format correctness (Blender handles this in Stage 1)
