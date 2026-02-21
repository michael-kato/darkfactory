# Spec: Export & Serialization

## Goal
Add ability to export the combined SDF as mesh and serialize scene data.

## Depends On
- `05-materials.md`

## Implementation Notes

### Marching Cubes Complexity
- **Critical Issue**: Full Marching Cubes implementation is complex (~250 case table entries). Consider using a simplified version or using Unity's `ComputeBuffer` approach.
- **Alternative**: For SDF export, consider "sphere tracing" to sample surface points, then mesh via Poisson reconstruction or simpler approaches.

### Performance Warning
- **Real-time mesh extraction at 60fps is extremely difficult** with marching cubes.
- Options:
  1. **Bake approach**: Only generate mesh on-demand (when user clicks Export), not real-time
  2. **Lower resolution**: Use lower grid resolution (32³) for preview, higher (256³) only on export
  3. **Async compute**: Use ComputeShader but read back asynchronously (requires Unity 2021+)

### Memory Considerations
- 256³ grid = 16.7M cells = ~50MB vertex buffer. This can cause memory pressure.
- Implement LOD: start with coarse grid, refine only near surfaces.

### Export Formats
- **OBJ**: Simple to implement manually - just write vertex/normal/face data
- **GLTF**: Use Unity's `GLTFSchema` or serialize Mesh directly to `.glb` binary format

### Serialization Pattern
- Use `[Serializable]` classes that mirror `SDFPrimitiveData`
- JSON serialization via `JsonUtility` (but it doesn't support all types - consider Newtonsoft.Json)
- Binary serialization for SDF data (faster, smaller)

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
