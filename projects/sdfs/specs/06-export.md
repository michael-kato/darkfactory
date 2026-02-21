# Spec: Export & Serialization

## Goal
Add ability to export the combined SDF as mesh and serialize scene data.

## Depends On
- `05-materials.md`

## Acceptance Criteria

1. Mesh export via Marching Cubes:
   - Compute shader runs MC on CPU-structured buffer
   - Outputs vertex buffer
   - Unity Mesh created from compute buffer

2. Export formats:
   - OBJ file export (vertices, normals, faces)
   - GLTF export via Unity's built-in
   - Binary SDF data (primitive list + transforms)

3. Export UI:
   - "Export Mesh" button → file save dialog
   - Format dropdown (OBJ, GLTF)
   - Resolution slider ( MC grid: 32³ - 256³)

4. Scene serialization:
   - `SDFSceneManager.Save(string path)` → JSON
   - `SDFSceneManager.Load(string path)` → reconstructs scene
   - Persists: primitives, transforms, materials, physics params

5. Runtime API:
   - Public methods for external script access
   - `AddPrimitive()`, `RemovePrimitive()`, `GetSDFData()`

## Out of Scope
- Incremental mesh export
- Network serialization
- Import from external SDF formats
