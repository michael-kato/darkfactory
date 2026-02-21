# Spec: Faux Physics Simulation

## Goal
Implement jello-like dynamics with wiggling and rippling in response to user interaction.

## Depends On
- `03-ui-interaction.md`

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
