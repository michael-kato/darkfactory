# Spec: SDF Ray Marching Renderer

## Goal
Implement a basic GPU-based ray marching renderer that can display a single sphere SDF in the Unity scene. This establishes the core rendering pipeline before adding primitives or interactions.

## Depends On
- None (first spec)

## Implementation Notes

### Rendering Approach
- **Two options**: ComputeShader or Fragment Shader raymarching
- Fragment shader approach (chosen): Simpler to integrate with Unity's rendering pipeline. Use fullscreen quad with custom shader.
- For editor preview: Can't easily render to Scene view. Consider separate "preview" camera or accept only Play mode rendering.

### Fullscreen Quad Setup
- Don't just disable camera and use OnRenderImage - create a child quad parented to camera.
- Quad position: `z = 1` relative to camera
- Quad scale: `width = 2 * tan(fov/2) * aspect`, `height = 2 * tan(fov/2)`

### Camera Parameters
- Pass to shader via:
  - `_CameraPosition` - world space camera position
  - `_InverseViewProjection` - for ray direction calculation
  - Alternatively: `_CameraForward`, `_CameraRight`, `_CameraUp` + FOV for manual ray construction

### Fragment Shader Pattern
```hlsl
// Vertex: output ray direction
v2f vert(appdata v) {
    float4 clipPos = float4(v.vertex.xy, 1.0, 1.0);
    float4 worldPos = mul(_InverseViewProjection, clipPos);
    worldPos /= worldPos.w;
    o.rayDir = normalize(worldPos.xyz - _CameraPosition);
}

// Fragment: ray march
float4 frag(v2f i) : SV_Target {
    float3 ro = _CameraPosition;
    float3 rd = normalize(i.rayDir);
    // ... march ...
}
```

### Debug Colors
- Add fallback colors to diagnose issues:
  - Red = no primitives in buffer
  - Blue = ray missed (max distance)
  - Green = hit!

## Acceptance Criteria

1. A fragment shader `SDFRender` exists in `Assets/Shaders/` that:
   - Performs sphere tracing from camera through each pixel
   - Returns hit point or background color
   - Uses max 64 ray steps, 0.001 surface threshold

2. A `SDFRenderer` MonoBehaviour in `Assets/Scripts/Rendering/` that:
   - Creates fullscreen quad parented to camera
   - Renders with the fragment shader
   - Passes camera matrices to shaders

3. A scene demonstrating:
   - A fullscreen quad rendering the SDF
   - Basic camera controls (orbit via OrbitCamera)

4. Performance: Renders at 1080p in <16ms on GTX 1060+

## Out of Scope
- Multiple primitives (single sphere only)
- UI controls
- Materials/lighting (unlit debug view)
- Editor Scene view rendering (Play mode only)
