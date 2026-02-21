# Spec: SDF Ray Marching Renderer

## Goal
Implement a basic GPU-based ray marching renderer that can display a single sphere SDF in the Unity scene. This establishes the core rendering pipeline before adding primitives or interactions.

## Depends On
- None (first spec)

## Acceptance Criteria

1. A compute shader `SDFCompute` exists in `Assets/Shaders/` that:
   - Defines a sphere SDF function
   - Takes a `StructuredBuffer` of primitive data (position, type, scale)
   - Outputs distance to nearest surface for each thread

2. A fragment shader `SDFRender` exists in `Assets/Shaders/` that:
   - Performs sphere tracing from camera through each pixel
   - Returns hit point or background color
   - Uses max 64 ray steps, 0.001 surface threshold

3. A `SDFRenderer` MonoBehaviour in `Assets/Scripts/Rendering/` that:
   - Creates and dispatches the compute shader
   - Renders fullscreen quad with the fragment shader
   - Passes camera matrices to shaders

4. A scene `PrototypeScene.unity` demonstrating:
   - A fullscreen quad rendering the SDF
   - Camera orbit controls (mouse drag to rotate)

5. Performance: Renders at 1080p in <16ms on GTX 1060+

## Out of Scope
- Multiple primitives (single sphere only)
- UI controls
- Materials/lighting (unlit debug view)
