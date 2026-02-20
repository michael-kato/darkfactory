# Spec: Mesh Validator

## Goal
Add a validator to `asscheck.py` that checks a glTF file for common mesh problems
that cause issues in Unity with glTFast.

## Acceptance Criteria

1. `validate_mesh(gltf_path: str) -> tuple[bool, str]` function exists in `asscheck.py`
2. It checks for:
   - File exists and has `.gltf` or `.glb` extension
   - File is valid JSON (for `.gltf`)
   - At least one mesh node is present in the scene
   - No mesh has zero triangles (degenerate geometry)
3. Returns `(True, "ok")` on pass, `(False, "<reason>")` on first failure
4. A `__main__` block in `asscheck.py` accepts a file path argument and prints the result

## Tests
- `tests/test_mesh_validator.py` covers:
  - Valid `.gltf` file passes
  - Missing file returns `(False, ...)`
  - Non-gltf extension returns `(False, ...)`
  - Malformed JSON returns `(False, ...)`
  - Use the existing sample: `asscheck_uproj/Assets/Models/street_lamp_01_quant.gltf`

## Out of Scope
- UV validation (separate spec)
- Unity runtime import (separate spec)
- Binary `.glb` parsing beyond extension check
