# Spec: SDF Primitives & Operations

## Goal
Extend the ray marching renderer to support multiple primitive types (sphere, cube, cylinder, cone, torus, capsule) and CSG operations (union, subtraction, intersection) with smooth blending.

## Depends On
- `01-sdf-raymarching.md`

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
   public enum PrimitiveType { Sphere, Box, Cylinder, Cone, Torus, Capsule }
   public enum BlendMode { Union, Subtraction, Intersection }
   
   [SerializeField] PrimitiveType type;
   [SerializeField] Vector3 position;
   [SerializeField] Vector3 scale = Vector3.one;
   [SerializeField] Quaternion rotation = Quaternion.identity;
   [SerializeField] float blendRadius = 0.5f;
   [SerializeField] BlendMode blendMode = BlendMode.Union;
   ```

4. A `SDFSceneManager` in `Assets/Scripts/Scene/` that:
   - Collects all `SDFPrimitive` components in scene
   - Packs data into compute buffer each frame
   - Handles add/remove of primitives at runtime

5. Test scene with 3+ primitives demonstrating all operations

## Out of Scope
- Hierarchical/grouping
- Runtime UI for editing
- Export
