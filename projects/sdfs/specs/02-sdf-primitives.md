# Spec: SDF Primitives & Operations

## Goal
Extend the ray marching renderer to support multiple primitive types (sphere, cube, cylinder, cone, torus, capsule) and CSG operations (union, subtraction, intersection) with smooth blending.

## Depends On
- `01-sdf-raymarching.md`

## Implementation Notes

### Naming Conflict
- **Important**: Unity has `UnityEngine.PrimitiveType` enum. Don't name your enum `PrimitiveType` - use `SDFPrimitiveType` instead to avoid conflicts with `GameObject.CreatePrimitive()`.

### Data Synchronization
- SDFPrimitive has local `position`, `scale`, `rotation` fields AND a Transform component.
- **Pattern**: In `Update()`, sync fields TO transform. Provide `SyncFromTransform()` method for reverse sync (editor gizmos → fields).
- This allows both programmatic control and editor manipulation.

### ComputeBuffer Layout
- Ensure C# struct `SDFPrimitiveData` matches HLSL struct exactly (same size, alignment).
- Use `[StructLayout(LayoutKind.Sequential)]` if padding issues occur.

### Scene Setup
- Primitives should be visible in Scene view for editing. Use `[RequireComponent]` to add MeshFilter/MeshRenderer, create meshes at runtime (Awake) that match the SDF type.

## Acceptance Criteria

1. Compute shader implements SDF functions for:
   - Sphere, Box, Cylinder, Cone, Torus, Capsule
   - Each as separate function, callable by type ID

2. CSG operations implemented:
   - `opUnion(d1, d2)` - smooth min blend
   - `opSubtraction(d1, d2)` - smooth max blend
   - `opIntersection(d1, d2)` - smooth max blend
   - Smooth blend factor configurable (k=0.5 default)

3. A `SDFPrimitive` component in `Assets/Scripts/Components/`:
   ```csharp
   public enum SDFPrimitiveType { Sphere, Box, Cylinder, Cone, Torus, Capsule }
   public enum BlendMode { Union, Subtraction, Intersection }
   
   [RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
   public class SDFPrimitive : MonoBehaviour {
       [SerializeField] SDFPrimitiveType type;
       [SerializeField] Vector3 position;
       [SerializeField] Vector3 scale = Vector3.one;
       [SerializeField] Quaternion rotation = Quaternion.identity;
       [SerializeField] float blendRadius = 0.5f;
       [SerializeField] BlendMode blendMode = BlendMode.Union;
       
       public void SyncFromTransform(); // for editor gizmos
   }
   ```

4. A `SDFSceneManager` in `Assets/Scripts/Scene/` that:
   - Collects all `SDFPrimitive` components in scene
   - Packs data into compute buffer each frame
   - Handles add/remove of primitives at runtime
   - Provides selection management

5. Test scene with 3+ primitives demonstrating all operations

## Out of Scope
- Hierarchical/grouping
- Runtime UI for editing
- Export
