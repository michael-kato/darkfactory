# Spec: Faux Physics Simulation

## Goal
Implement jello-like dynamics with wiggling and rippling in response to user interaction.

## Depends On
- `03-ui-interaction.md`

## Implementation Notes

### ComputeShader Integration
- The physics simulation should run on GPU via ComputeShader for performance, but the results need to sync back to CPU for:
  - Rendering (via modified SDF parameters)
  - Selection/interaction callbacks
- **Pattern**: Use double-buffering with ComputeBuffer - compute shader writes to buffer, SDF shader reads from same buffer.

### SDF Parameter Animation
- Rather than modifying primitive transforms directly (which requires CPU→GPU sync), pass physics state through ComputeBuffer alongside SDFPrimitiveData.
- Add new fields to `SDFPrimitiveData`:
  ```hlsl
  struct SDFPrimitiveData {
      float3 position;
      float3 scale;
      int type;
      float blendRadius;
      int blendMode;
      float3 velocity;      // NEW: for physics
      float3 displacement;  // NEW: for wobble
      float timeOffset;     // NEW: for wave phase
  };
  ```

### Performance Considerations
- Spring physics per-primitive is cheap; rippling from click point requires evaluating SDF at hit location.
- Consider using the same raymarching loop for both rendering AND physics - compute once, use for both.
- **Critical**: Don't readback from GPU every frame. Keep physics on GPU, only read back for editor gizmos.

### Interaction with Selection
- Current selection system uses raycasting against bounding volumes. With animated SDFs, the visual position differs from stored position.
- Solution: Use same SDF evaluation function for both rendering and hit testing.

## Acceptance Criteria

1. A `FauxPhysicsSystem` compute shader in `Assets/Shaders/` that:
   - Takes current SDF parameters as input
   - Applies damped spring oscillation per primitive
   - Uses sine wave displacement based on time
   - Supports poke interaction (click adds impulse)

2. Physics parameters exposed in UI:
   - Stiffness (0.1 - 10.0, default 2.0)
   - Damping (0.1 - 5.0, default 0.8)
   - Amplitude (0.0 - 2.0, default 0.5)
   - Wave frequency

3. Interaction integration:
   - Click on surface triggers ripple from hit point
   - Dragging primitive adds momentum
   - Release triggers settling oscillation

4. Stability guarantees:
   - No NaN/Inf values in output
   - Clamped displacement to prevent visual explosion
   - Frame-rate independent physics (deltaTime)

5. Visual feedback:
   - Subtle glow intensity modulation during motion

## Out of Scope
- True soft-body collision
- Gravity simulation
- Complex compound physics
